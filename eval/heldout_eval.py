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


def by_marker(blocks: list[dict]) -> list[dict]:
    """Layout-normalized: main text in output order, then footnotes in marker order with the
    printed marker as text. Separates reading accuracy from footnote-column order."""
    main = [b for b in blocks if b.get("type") != "footnote"]
    fns = [dict(b) for b in blocks if b.get("type") == "footnote"]
    for b in fns:
        m = b.get("footnote_marker")
        if not m:
            mm = re.match(r"\s*(\([^)]*\))", b["text"])
            m = mm.group(1) if mm else None
        b["footnote_marker"] = m
        if m and not re.match(r"\s*\(", b["text"]):
            b["text"] = f"{m} {b['text']}"
    return main + sorted(fns, key=lambda b: _mnum(b["footnote_marker"]))


def footnotes_in_order(blocks: list[dict]) -> bool:
    nums = [
        _mnum(b.get("footnote_marker") or b["text"][:6])
        for b in blocks
        if b.get("type") == "footnote"
    ]
    nums = [n for n in nums if n != 999]
    return nums == sorted(nums)


def asool_blocks(con: sqlite3.Connection, printed: int) -> list[dict]:
    """Blocks exactly as stored in the index, in stored order."""
    rows = con.execute(
        "SELECT type, author_role, text_raw, footnote_marker FROM blocks "
        "WHERE page_id=? ORDER BY ord",
        (page_id(printed),),
    ).fetchall()
    return [{"type": t, "author_role": r, "text": x, "footnote_marker": m} for t, r, x, m in rows]


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


def _normalized(sys_blocks: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {k: (v if k == "tesseract-ara" else by_marker(v)) for k, v in sys_blocks.items()}


def _summ(rows: list[dict]) -> dict:
    return {
        "cer_strict": st.mean(r["strict"]["cer"] for r in rows),
        "cer_loose": st.mean(r["loose"]["cer"] for r in rows),
        "wer_loose": st.mean(r["loose"]["wer"] for r in rows),
        "footnote_f1": st.mean(r["footnote_links"]["f1"] for r in rows),
    }


def main() -> dict:
    con = sqlite3.connect(DB)
    held = [p for p in GOLD_PAGES if p not in BAKEOFF_PAGES]
    done = [p for p in held if (GOLD / f"{page_id(p)}.json").exists()]
    bake = [p for p in BAKEOFF_PAGES if (GOLD / f"{page_id(p)}.json").exists()]
    raw = {p: systems(con, p) for p in done + bake}
    as_output = {p: evaluate(p, raw[p]) for p in done}
    normed = {p: evaluate(p, _normalized(raw[p]), gold_transform=by_marker) for p in done + bake}
    out: dict = {
        "pages": len(done),
        "scored": done,
        "pending": sorted(set(held) - set(done)),
        "note": (
            "as_output = text in the order the system produced it (order-sensitive, like "
            "the bake-off); layout_normalized = footnotes in marker order after the main "
            "text, for the gold and every structured system alike (reading accuracy only). "
            "Tesseract is plain text and cannot be reordered."
        ),
        "systems": {},
    }
    for name, label in SYSTEMS.items():
        have = [p for p in done if name in raw[p]]
        if not have:
            continue
        s = {"label": label, "pages": len(have)}
        s["as_output"] = _summ([as_output[p][name] for p in have])
        s["layout_normalized"] = _summ([normed[p][name] for p in have])
        if name != "tesseract-ara":
            s["footnotes_in_reading_order"] = sum(
                footnotes_in_order(raw[p][name]) for p in have
            ) / len(have)
            tas = [as_output[p][name]["type_acc"] for p in have]
            s["type_acc"] = st.mean(tas) if tas[0] is not None else None
        bh = [p for p in bake if name in raw[p]]
        if bh:
            s["bakeoff_layout_normalized"] = _summ([normed[p][name] for p in bh])
        out["systems"][name] = s
    # Report keys used by eval.report: Asool = what users get (the final index), reading accuracy.
    ix, tb = out["systems"].get("asool-index"), out["systems"].get("tesseract-ara")
    if ix and tb:
        out["asool"] = ix["layout_normalized"]
        out["baseline"] = tb["as_output"]
    out["per_page"] = {
        p: {
            s: {
                "cer_strict": v["strict"]["cer"],
                "cer_loose": v["loose"]["cer"],
                "cer_strict_normalized": normed[p][s]["strict"]["cer"],
                "f1": v["footnote_links"]["f1"],
            }
            for s, v in r.items()
        }
        for p, r in as_output.items()
    }
    if done:
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "heldout.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    r = main()
    for v in r["systems"].values():
        a, n, b = v["as_output"], v["layout_normalized"], v.get("bakeoff_layout_normalized")
        fo = v.get("footnotes_in_reading_order")
        bs = "-" if not b else f"{b['cer_strict']:.1%}"
        print(
            f"{v['label'][:42]:42s} | as output: strict {a['cer_strict']:.1%} loose "
            f"{a['cer_loose']:.1%} | normalized: strict {n['cer_strict']:.1%} loose "
            f"{n['cer_loose']:.1%} | fn order ok {'-' if fo is None else f'{fo:.0%}'} | "
            f"bake-off normalized strict {bs}"
        )
