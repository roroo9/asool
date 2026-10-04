"""One interface for every LLM call (Gemini + Claude), with a disk cache.

Every call is cached under data/cache/llm/ keyed by (prompt version, model, input hash),
so pipeline reruns are free and deterministic. Token usage is logged per call to
data/cache/llm_usage.jsonl for docs/COSTS.md.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from api.settings import ROOT, settings

CACHE = ROOT / "data" / "cache" / "llm"
USAGE_LOG = ROOT / "data" / "cache" / "llm_usage.jsonl"

CLAUDE_MAX_EDGE = 2576  # documented max long edge for high-res vision models


@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cached: bool
    seconds: float


def _key(*parts: str | bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def _log_usage(stage: str, r: LLMResult) -> None:
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_LOG.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "stage": stage,
                    "model": r.model,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cached": r.cached,
                    "seconds": round(r.seconds, 2),
                }
            )
            + "\n"
        )


def _png_bytes(path: Path, max_edge: int | None) -> bytes:
    im = Image.open(path)
    if max_edge and max(im.size) > max_edge:
        s = max_edge / max(im.size)
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
    """Generate text (JSON if `schema` is given) with Gemini or Claude, cached on disk."""
    is_claude = model.startswith("claude")
    img = _png_bytes(image, CLAUDE_MAX_EDGE if is_claude else None) if image else b""
    key = _key(
        prompt_version,
        model,
        system,
        user,
        img,
        json.dumps(schema, sort_keys=True) if schema else "",
        effort,
    )
    path = CACHE / stage / f"{key}.json"
    if path.exists() and not force:
        d = json.loads(path.read_text())
        r = LLMResult(d["text"], d["model"], d["input_tokens"], d["output_tokens"], True, 0.0)
        _log_usage(stage, r)
        return r
    t0 = time.time()
    if is_claude:
        r = _claude(model, system, user, img, schema, effort, max_tokens)
    else:
        r = _gemini(model, system, user, img, schema, max_tokens)
    r.seconds = time.time() - t0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "text": r.text,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
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
    from google.genai import errors as gerr

    delay = 10.0
    for attempt in range(6):
        try:
            resp = client.models.generate_content(model=model, contents=parts, config=cfg)
            break
        except gerr.APIError as e:
            # 503 = overloaded, 429 = per-minute limit: back off and retry.
            # A daily quota (retry delay of hours) is not worth waiting for.
            if e.code not in (429, 503, 500) or attempt == 5 or "PerDay" in str(e):
                raise
            time.sleep(delay)
            delay = min(delay * 2, 120)
    um = resp.usage_metadata
    out_tokens = (um.candidates_token_count or 0) + (um.thoughts_token_count or 0)
    if not resp.text:
        raise RuntimeError(f"{model} returned no text: {resp.candidates}")
    return LLMResult(resp.text, model, um.prompt_token_count or 0, out_tokens, False, 0.0)
