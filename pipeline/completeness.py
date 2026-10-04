"""Completeness check (owner rule, Oct 4: "page 28 lesson").

Compares the VLM's extracted blocks against the OCR line geometry (Tesseract) and flags any
region of the page with printed text that the extracted blocks do not cover. A flagged page
goes to the review queue and is never silently indexed.

Method: for every Tesseract line that looks like real text (enough Arabic letters, not a
speck), find its best fuzzy match inside the VLM page text (rapidfuzz partial_ratio on
normalized text). Tesseract is noisy, so the threshold is deliberately lenient; a line is
"uncovered" only when even a lenient match fails. Consecutive uncovered lines form a region.
"""

from __future__ import annotations

import json
import re

from rapidfuzz import fuzz

from pipeline.config import INTER, page_id
from pipeline.normalize import normalize

MIN_ARABIC = 8  # letters; shorter lines (page numbers, specks) are ignored
MIN_CONF = 50  # mean Tesseract word confidence; below this the "line" is mostly noise
MATCH_THRESHOLD = 65  # partial_ratio; calibrated Oct 4: 37/40 deletions caught, 2/15 false flags
SPLIT_RE = re.compile(r"\(\s*[^()]{0,3}\s*\)|\)\s*[^()]{0,3}\s*\(")
_AR = re.compile(r"[ء-ي]")


def check(printed: int, blocks: list[dict]) -> dict:
    ocr = json.loads((INTER / "ocr" / f"{page_id(printed)}.json").read_text())
    vtext = normalize(" ".join(b["text"] for b in blocks))
    lines = []
    for ln in ocr["lines"]:
        if ln["conf"] < MIN_CONF:
            continue
        # Multi-column footnote rows are read straight across the columns, mixing several
        # footnotes in one OCR line; check each marker-delimited segment on its own.
        segments = [s for s in SPLIT_RE.split(ln["text"]) if s.strip()]
        for seg in segments:
            n = normalize(seg)
            letters = len(_AR.findall(n))
            nonspace = len(n.replace(" ", "")) or 1
            words = [w for w in n.split() if len(_AR.findall(w)) >= 3]
            if letters < MIN_ARABIC or letters / nonspace < 0.8:
                continue
            if len(words) < (3 if len(segments) == 1 else 2):
                continue
            score = fuzz.partial_ratio(n, vtext) if vtext else 0.0
            lines.append({"bbox": ln["bbox"], "text": seg.strip(), "score": round(score, 1)})
    uncovered = [ln for ln in lines if ln["score"] < MATCH_THRESHOLD]
    regions: list[dict] = []
    for ln in sorted(uncovered, key=lambda x: x["bbox"][1]):
        if regions and ln["bbox"][1] - regions[-1]["bbox"][3] < 120:  # merge nearby lines
            r = regions[-1]
            r["bbox"] = [
                min(r["bbox"][0], ln["bbox"][0]),
                r["bbox"][1],
                max(r["bbox"][2], ln["bbox"][2]),
                max(r["bbox"][3], ln["bbox"][3]),
            ]
            r["lines"].append(ln["text"])
        else:
            regions.append({"bbox": list(ln["bbox"]), "lines": [ln["text"]]})
    coverage = 1 - len(uncovered) / len(lines) if lines else 1.0
    return {
        "page_id": page_id(printed),
        "text_lines": len(lines),
        "uncovered_lines": len(uncovered),
        "coverage": round(coverage, 3),
        "complete": not uncovered,
        "regions": regions,
    }


if __name__ == "__main__":
    import sys

    from pipeline.vlm_parse import model_dir

    model, prompt = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
    folder = model_dir(model) + (f"@{prompt}" if prompt else "")
    for f in sorted((INTER / "vlm" / folder).glob("*.json")):
        d = json.loads(f.read_text())
        r = check(d["printed"], d["blocks"])
        flag = "OK  " if r["complete"] else "FLAG"
        print(
            flag,
            d["printed"],
            f"coverage={r['coverage']:.0%}",
            f"uncovered={r['uncovered_lines']}/{r['text_lines']}",
            [x["lines"][0][:40] for x in r["regions"]][:3],
        )
