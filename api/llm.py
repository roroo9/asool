"""One provider-agnostic interface for every LLM and embedding call, with a disk cache.

Models are named "provider:model", e.g.
  anthropic:claude-opus-5-5
  google:gemini-3.5-flash                      (Google AI Studio key, free tier)
  openrouter:google/gemini-3.1-pro-preview     (OpenRouter key)
Bare "claude-*" / "gemini-*" names are accepted for backwards compatibility.
Which model does which job is configured in api/settings.py (env-overridable), never
hard-coded in pipeline or API code.

Every call is cached under data/cache/llm/ keyed by (prompt version, model, input hash), so
reruns are free and deterministic. Every non-cached call is logged with tokens and USD cost
to data/cache/llm_usage.jsonl (source for docs/COSTS.md).
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image

from api.settings import ROOT, settings

CACHE = ROOT / "data" / "cache" / "llm"
USAGE_LOG = ROOT / "data" / "cache" / "llm_usage.jsonl"
MAX_EDGE = 2576  # long edge sent to vision models (Claude's documented high-res limit)
OPENROUTER_URL = "https://openrouter.ai/api/v1"

# USD per 1M tokens (input, output) for providers that do not report cost themselves.
# Source: Anthropic model table (skill cache dated 2026-09-25). Google AI Studio free tier = 0.
PRICES = {
    "anthropic:claude-opus-5-5": (4.0, 20.0),
    "anthropic:claude-fable-5-1": (10.0, 50.0),
    "anthropic:claude-sonnet-5-5": (2.0, 10.0),
}


@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cached: bool
    seconds: float
    cost_usd: float = 0.0


def split_model(model: str) -> tuple[str, str]:
    if ":" in model and model.split(":", 1)[0] in ("anthropic", "google", "openrouter"):
        p, m = model.split(":", 1)
        return p, m
    if model.startswith("claude"):
        return "anthropic", model
    if model.startswith("gemini"):
        return "google", model
    raise ValueError(f"unknown provider for model {model!r}")


def _key(*parts: str | bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def _log_usage(stage: str, r: LLMResult) -> None:
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    provider, _ = split_model(r.model)
    with USAGE_LOG.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "stage": stage,
                    "provider": provider,
                    "model": r.model,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cost_usd": round(r.cost_usd, 6),
                    "cached": r.cached,
                    "seconds": round(r.seconds, 2),
                }
            )
            + "\n"
        )


def _png_bytes(path: Path) -> bytes:
    im = Image.open(path)
    if max(im.size) > MAX_EDGE:
        s = MAX_EDGE / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def generate(
    *,
    stage: str,
    prompt_version: str,
    model: str,
    system: str,
    user: str,
    image: Path | None = None,
    schema: dict | None = None,
    effort: str = "high",
    max_tokens: int = 32000,
    force: bool = False,
) -> LLMResult:
    """Generate text (JSON if `schema` is given), cached on disk."""
    provider, name = split_model(model)
    canonical = f"{provider}:{name}"
    img = _png_bytes(image) if image else b""
    # Cache key ignores the provider prefix for the two legacy providers so earlier
    # cached results stay valid.
    key_model = name if provider in ("anthropic", "google") else canonical
    key = _key(
        prompt_version,
        key_model,
        system,
        user,
        img,
        json.dumps(schema, sort_keys=True) if schema else "",
        effort,
    )
    path = CACHE / stage / f"{key}.json"
    if path.exists() and not force:
        d = json.loads(path.read_text())
        r = LLMResult(d["text"], canonical, d["input_tokens"], d["output_tokens"], True, 0.0)
        _log_usage(stage, r)
        return r
    t0 = time.time()
    if provider == "anthropic":
        r = _claude(name, system, user, img, schema, effort, max_tokens)
    elif provider == "google":
        r = _gemini(name, system, user, img, schema, max_tokens)
    else:
        r = _openrouter(name, system, user, img, schema, effort, max_tokens)
    r.model = canonical
    r.seconds = time.time() - t0
    if canonical in PRICES:
        pi, po = PRICES[canonical]
        r.cost_usd = (r.input_tokens * pi + r.output_tokens * po) / 1e6
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "text": r.text,
                "model": canonical,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost_usd": r.cost_usd,
                "prompt_version": prompt_version,
                "seconds": r.seconds,
            },
            ensure_ascii=False,
        )
    )
    _log_usage(stage, r)
    return r


def _claude(model, system, user, img, schema, effort, max_tokens) -> LLMResult:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
    content: list[dict] = []
    if img:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.standard_b64encode(img).decode(),
                },
            }
        )
    content.append({"type": "text", "text": user})
    output_config: dict = {"effort": effort}
    if schema:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config=output_config,
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"{model} refused: {msg.stop_details}")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError(f"{model} hit max_tokens")
    text = next(b.text for b in msg.content if b.type == "text")
    return LLMResult(text, model, msg.usage.input_tokens, msg.usage.output_tokens, False, 0.0)


def _gemini(model, system, user, img, schema, max_tokens) -> LLMResult:
    from google import genai
    from google.genai import errors as gerr
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    parts = []
    if img:
        parts.append(types.Part.from_bytes(data=img, mime_type="image/png"))
    parts.append(user)
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=max_tokens,
        temperature=0.0,
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
    )
    if schema:
        cfg.response_mime_type = "application/json"
        cfg.response_json_schema = schema
    delay = 10.0
    for attempt in range(6):
        try:
            resp = client.models.generate_content(model=model, contents=parts, config=cfg)
            break
        except gerr.APIError as e:
            # 503 overloaded / 429 per-minute limit: back off. Daily quotas are not retried.
            if e.code not in (429, 503, 500) or attempt == 5 or "PerDay" in str(e):
                raise
            time.sleep(delay)
            delay = min(delay * 2, 120)
    um = resp.usage_metadata
    out_tokens = (um.candidates_token_count or 0) + (um.thoughts_token_count or 0)
    if not resp.text:
        raise RuntimeError(f"{model} returned no text: {resp.candidates}")
    return LLMResult(resp.text, model, um.prompt_token_count or 0, out_tokens, False, 0.0)


def _openrouter(model, system, user, img, schema, effort, max_tokens) -> LLMResult:
    content: list[dict] = []
    if img:
        b64 = base64.standard_b64encode(img).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    content.append({"type": "text", "text": user})
    body: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "usage": {"include": True},
        "reasoning": {"effort": "high" if effort in ("high", "xhigh", "max") else effort},
    }
    if schema:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "output", "strict": True, "schema": schema},
        }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://github.com/roroo9/asool",
        "X-Title": "Asool",
    }
    delay = 5.0
    for attempt in range(5):
        r = httpx.post(
            f"{OPENROUTER_URL}/chat/completions", json=body, headers=headers, timeout=600
        )
        if r.status_code in (429, 500, 502, 503) and attempt < 4:
            time.sleep(delay)
            delay *= 2
            continue
        break
    d = r.json()
    if "error" in d or r.status_code != 200:
        raise RuntimeError(f"openrouter {model}: {r.status_code} {d.get('error', d)}")
    ch = d["choices"][0]
    if ch.get("finish_reason") == "length":
        raise RuntimeError(f"{model} hit max_tokens")
    u = d.get("usage", {})
    return LLMResult(
        ch["message"]["content"] or "",
        model,
        u.get("prompt_tokens", 0),
        u.get("completion_tokens", 0),
        False,
        0.0,
        float(u.get("cost", 0.0)),
    )


def embed(texts: list[str], *, stage: str = "embed", model: str | None = None) -> list[list[float]]:
    """Embeddings via OpenRouter (paid, no free-tier limits during judging). Cached per text."""
    model = model or settings.embed_model
    out: list[list[float] | None] = []
    todo: list[int] = []
    for t in texts:
        p = CACHE / stage / f"{_key(model, t)}.json"
        out.append(json.loads(p.read_text()) if p.exists() else None)
    todo = [i for i, v in enumerate(out) if v is None]
    _, name = split_model(model)
    for s in range(0, len(todo), 64):
        idx = todo[s : s + 64]
        r = httpx.post(
            f"{OPENROUTER_URL}/embeddings",
            json={"model": name, "input": [texts[i] for i in idx]},
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            timeout=120,
        )
        d = r.json()
        if r.status_code != 200 or "data" not in d:
            raise RuntimeError(f"embeddings {name}: {r.status_code} {d}")
        u = d.get("usage", {})
        _log_usage(
            stage,
            LLMResult(
                "",
                f"openrouter:{name}",
                u.get("prompt_tokens", 0),
                0,
                False,
                0.0,
                float(u.get("cost", 0.0)),
            ),
        )
        for i, item in zip(idx, d["data"], strict=True):
            out[i] = item["embedding"]
            p = CACHE / stage / f"{_key(model, texts[i])}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(item["embedding"]))
    return out  # type: ignore[return-value]
