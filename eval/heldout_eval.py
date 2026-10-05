"""Extraction quality on the HELD-OUT gold pages (CLAUDE.md §12.E1).

The page parser and prompt (Gemini 3.1 Pro + page_parse.v2) were chosen and tuned on the three
bake-off pages (41, 30, 20). This re-measures the final indexed output on the other gold pages,
which played no part in that choice, against the baseline (Tesseract `ara` plain text).

Only pages the reviewer has finalized (data/gold/{page}.json) are scored; the rest are listed as
pending. Asool's text = the blocks stored in the index, i.e. after owner-confirmed corrections
(data/corrections.json), exactly what users see.

Usage: uv run python -m eval.heldout_eval      -> data/eval/results/heldout.json
"""

from __future__ import annotations

import json
import sqlite3
import statistics as st

from eval.extraction_eval import evaluate
from eval.run_eval import DB, RESULTS
from pipeline.config import BAKEOFF_PAGES, GOLD, INTER, page_id

GOLD_PAGES = [12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 33, 35, 37, 39, 41]


def asool_blocks(con: sqlite3.Connection, printed: int) -> list[dict]:
    rows = con.execute(
        "SELECT type, author_role, text_raw, footnote_marker FROM blocks "
        "WHERE page_id=? ORDER BY ord",
        (page_id(printed),),
    ).fetchall()
    return [{"type": t, "author_role": r, "text": x, "footnote_marker": m} for t, r, x, m in rows]


def main() -> dict:
    con = sqlite3.connect(DB)
    held = [p for p in GOLD_PAGES if p not in BAKEOFF_PAGES]
    done = [p for p in held if (GOLD / f"{page_id(p)}.json").exists()]
    per_page = {}
    for p in done:
        ocr = json.loads((INTER / "ocr" / f"{page_id(p)}.json").read_text())
        per_page[p] = evaluate(
            p,
            {
                "asool": asool_blocks(con, p),
                "baseline": [{"type": "body", "text": ocr["text"]}],
            },
        )
    out: dict = {"pages": len(done), "scored": done, "pending": sorted(set(held) - set(done))}
    for sysname in ("asool", "baseline"):
        if not done:
            break
        rs = [per_page[p][sysname] for p in done]
        out[sysname] = {
            "cer_strict": st.mean(r["strict"]["cer"] for r in rs),
            "cer_loose": st.mean(r["loose"]["cer"] for r in rs),
            "wer_loose": st.mean(r["loose"]["wer"] for r in rs),
            "footnote_f1": st.mean(r["footnote_links"]["f1"] for r in rs),
            "type_acc": st.mean(r["type_acc"] for r in rs) if sysname == "asool" else None,
        }
    out["per_page"] = {
        p: {
            s: {"cer_strict": v["strict"]["cer"], "f1": v["footnote_links"]["f1"]}
            for s, v in r.items()
        }
        for p, r in per_page.items()
    }
    if done:
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "heldout.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: v for k, v in r.items() if k != "per_page"}, ensure_ascii=False, indent=1))
