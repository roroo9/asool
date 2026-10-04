"""Semantic lane: a vision-language model reads a page into typed blocks.

Used both by Asool's main pipeline (Gemini family) and by the independent gold-set readers
(Claude, see CLAUDE.md §12.C). Output: data/intermediate/vlm/{model}/{page_id}.json
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor

from pydantic import ValidationError

from api.llm import generate
from pipeline.config import BOOK, INTER, PAGES, page_id
from pipeline.schemas import PAGE_SCHEMA, ParsedPage

PROMPT_VERSION = "page_parse.v1"
SYSTEM = (INTER.parent.parent / "pipeline" / "prompts" / f"{PROMPT_VERSION}.md").read_text()


def out_path(model: str, printed: int):
    return INTER / "vlm" / model / f"{page_id(printed)}.json"


def parse_page(printed: int, model: str, force: bool = False) -> dict:
    out = out_path(model, printed)
    if out.exists() and not force:
        return json.loads(out.read_text())
    user = (
        f"Book: {BOOK['title_ar']} — {BOOK['author_ar']}. Edition: {BOOK['edition']}. "
        f"Printed page number (if known): {printed}. Parse this page."
    )
    errors: list[str] = []
    for attempt in range(2):
        u = user if not errors else user + "\n\nYour previous output was invalid: " + errors[-1]
        r = generate(
            stage=f"vlm_parse/{model}",
            prompt_version=PROMPT_VERSION + (f"-retry{attempt}" if attempt else ""),
            model=model,
            system=SYSTEM,
            user=u,
            image=PAGES / f"{page_id(printed)}.png",
            schema=PAGE_SCHEMA,
            effort="high",
            force=force,
        )
        try:
            page = ParsedPage.model_validate_json(r.text)
            break
        except ValidationError as e:
            errors.append(str(e)[:2000])
    else:
        raise RuntimeError(f"{model} p{printed}: invalid output twice: {errors[-1][:300]}")
    res = {
        "page_id": page_id(printed),
        "printed": printed,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "usage": {"input_tokens": r.input_tokens, "output_tokens": r.output_tokens},
        **page.model_dump(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def run(pages: list[int], models: list[str], workers: int = 4) -> None:
    jobs = [(p, m) for m in models for p in pages]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for (p, m), fut in zip(jobs, [ex.submit(parse_page, p, m) for p, m in jobs], strict=True):
            try:
                d = fut.result()
                print(f"ok  {m:28s} p{p:03d} blocks={len(d['blocks'])}")
            except Exception as e:  # report and continue; a failed page gets flagged later
                print(f"ERR {m:28s} p{p:03d} {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, nargs="+", required=True)
    ap.add_argument("--models", nargs="+", required=True)
    a = ap.parse_args()
    run(a.pages, a.models)
