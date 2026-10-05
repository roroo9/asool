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
import re
import sqlite3
import statistics as st

from eval.extraction_eval import evaluate
from eval.run_eval import DB, RESULTS
from pipeline.config import BAKEOFF_PAGES, GOLD, INTER, page_id
from pipeline.normalize import normalize_marker
from pipeline.vlm_parse import model_dir

GOLD_PAGES = [12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 33, 35, 37, 39, 41]


V2 = "openrouter:google/gemini-3.1-pro-preview@page_parse.v2"
V1 = "openrouter:google/gemini-3.1-pro-preview"
SYSTEMS = {
    V2: "Gemini 3.1 Pro + prompt v2 (Asool's parser)",
    V1: "Gemini 3.1 Pro + prompt v1",
    "gemini-3.5-flash": "Gemini 3.5 Flash (free tier)",
    "asool-index": "Asool final index (after fusion, splits, corrections)",
    "tesseract-ara": "Tesseract ara (baseline)",
}


def _mnum(m: str | None) -> int:
    d = re.sub(r"\D", "", normalize_marker(m or "") or "")
    return int(d) if d else 999


def asool_blocks(con: sqlite3.Connection, printed: int) -> list[dict]:
    """Blocks as indexed. Footnotes are put in marker order and get their printed marker back
    as text (split footnotes keep the marker in a field), so storage layout is not scored as
    reading error."""
    rows = con.execute(
        "SELECT type, author_role, text_raw, footnote_marker FROM blocks "
        "WHERE page_id=? ORDER BY ord",
        (page_id(printed),),
    ).fetchall()
    out = [{"type": t, "author_role": r, "text": x, "footnote_marker": m} for t, r, x, m in rows]
    main = [b for b in out if b["type"] != "footnote"]
    fns = sorted(
        (b for b in out if b["type"] == "footnote"), key=lambda b: _mnum(b["footnote_marker"])
    )
    for b in fns:
        if b["footnote_marker"] and not re.match(r"\s*\(", b["text"]):
            b["text"] = f"{b['footnote_marker']} {b['text']}"
    return main + fns


def systems(con: sqlite3.Connection, printed: int) -> dict[str, list[dict]]:
    pid = page_id(printed)
    ocr = json.loads((INTER / "ocr" / f"{pid}.json").read_text())
    out = {"tesseract-ara": [{"type": "body", "text": ocr["text"]}]}
    for m in (V2, V1, "gemini-3.5-flash"):
        p = INTER / "vlm" / model_dir(m) / f"{pid}.json"
        if p.exists():
            out[m] = json.loads(p.read_text())["blocks"]
    out["asool-index"] = asool_blocks(con, printed)
    return out


def main() -> dict:
    con = sqlite3.connect(DB)
    held = [p for p in GOLD_PAGES if p not in BAKEOFF_PAGES]
    done = [p for p in held if (GOLD / f"{page_id(p)}.json").exists()]
    per_page = {p: evaluate(p, systems(con, p)) for p in done}
    out: dict = {
        "pages": len(done),
        "scored": done,
        "pending": sorted(set(held) - set(done)),
        "systems": {},
    }
    for name, label in SYSTEMS.items():
        have = [p for p in done if name in per_page[p]]
        if not have:
            continue
        rs = [per_page[p][name] for p in have]
        out["systems"][name] = {
            "label": label,
            "pages": len(have),
            "cer_strict": st.mean(r["strict"]["cer"] for r in rs),
            "cer_loose": st.mean(r["loose"]["cer"] for r in rs),
            "wer_loose": st.mean(r["loose"]["wer"] for r in rs),
            "footnote_f1": st.mean(r["footnote_links"]["f1"] for r in rs),
            "type_acc": st.mean(r["type_acc"] for r in rs)
            if rs[0]["type_acc"] is not None
            else None,
        }
    # Report keys used by eval.report: Asool = the parser with prompt v2; baseline = Tesseract.
    out["asool"] = out["systems"].get(V2, {})
    out["baseline"] = out["systems"].get("tesseract-ara", {})
    out["per_page"] = {
        p: {
            s: {
                "cer_strict": v["strict"]["cer"],
                "cer_loose": v["loose"]["cer"],
                "f1": v["footnote_links"]["f1"],
            }
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
    for v in r["systems"].values():
        print(
            f"{v['label']:58s} pages={v['pages']:2d} strict={v['cer_strict']:.1%} "
            f"loose={v['cer_loose']:.1%} fnF1={v['footnote_f1']:.2f}"
        )
