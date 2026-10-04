"""Fusion of the semantic lane (VLM blocks) with the geometry lane (Tesseract word boxes).

Each VLM block gets:
  - rects: one rectangle per printed line the block occupies (RTL aware: a block that
           starts mid-line runs from its first word leftwards to the line's left edge; a block
           that ends mid-line runs from the line's right edge to its last word)
  - bbox:  union of rects, [x0,y0,x1,y1] in 300-DPI page pixels
  - align_score: share of the block's words matched to OCR words (feeds confidence)
  - bbox_source: "fusion" (aligned to OCR words), "interpolated" (OCR could not read it, e.g.
           ornate Quran type; placed on the lines between its aligned neighbours), or "none"
           (no geometry -> flagged, never silently trusted)

Alignment is done per block against the whole page (so footnote columns and reading order
differences do not matter), then only the densest cluster of matched lines is kept (common
phrases such as «صلى الله عليه وسلم» also match elsewhere on the page).
"""

from __future__ import annotations

from difflib import SequenceMatcher

from rapidfuzz.distance import Levenshtein

from pipeline.normalize import normalize

FUZZY_WORD = 0.6
MIN_ALIGN = 0.3
MAX_LINE_GAP = 1  # lines between matched lines allowed inside one cluster


def _k(w: str) -> str:
    return normalize(w) or w


def _align_block(keys: list[str], ocr_keys: list[str]) -> list[int]:
    """OCR word indices matched to this block (order-preserving, exact + fuzzy)."""
    out = []
    sm = SequenceMatcher(None, keys, ocr_keys, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.extend(range(j1, j2))
        elif tag == "replace":
            for k in range(min(i2 - i1, j2 - j1)):
                if (
                    1 - Levenshtein.normalized_distance(keys[i1 + k], ocr_keys[j1 + k])
                    >= FUZZY_WORD
                ):
                    out.append(j1 + k)
    return out


def _densest_cluster(words: list[int], line_of: list[int]) -> list[int]:
    if not words:
        return []
    by_line: dict[int, list[int]] = {}
    for w in words:
        by_line.setdefault(line_of[w], []).append(w)
    lines = sorted(by_line)
    clusters, cur = [], [lines[0]]
    for ln in lines[1:]:
        if ln - cur[-1] <= MAX_LINE_GAP + 1:
            cur.append(ln)
        else:
            clusters.append(cur)
            cur = [ln]
    clusters.append(cur)
    best = max(clusters, key=lambda c: sum(len(by_line[ln]) for ln in c))
    return sorted(w for ln in best for w in by_line[ln])


def _rects(word_ids: list[int], ow: list[dict], ocr: dict) -> list[list[int]]:
    lines = sorted({ow[w]["line"] for w in word_ids})
    rects = []
    for ln in lines:
        ws = [ow[w]["bbox"] for w in word_ids if ow[w]["line"] == ln]
        lb = ocr["lines"][ln]["bbox"]
        x0, x1 = min(w[0] for w in ws), max(w[2] for w in ws)
        if ln != lines[0]:
            x1 = lb[2]
        if ln != lines[-1]:
            x0 = lb[0]
        rects.append([x0, lb[1], x1, lb[3]])
    return rects


def _bbox(rects: list[list[int]]) -> list[int]:
    return [
        min(r[0] for r in rects),
        min(r[1] for r in rects),
        max(r[2] for r in rects),
        max(r[3] for r in rects),
    ]


def fuse(blocks: list[dict], ocr: dict) -> list[dict]:
    ow = [
        {"key": _k(w["text"]), "bbox": w["bbox"], "line": li}
        for li, ln in enumerate(ocr["lines"])
        for w in ln["words"]
        if _k(w["text"])
    ]
    ocr_keys = [w["key"] for w in ow]
    line_of = [w["line"] for w in ow]
    out = []
    for blk in blocks:
        keys = [_k(w) for w in blk["text"].split() if _k(w)]
        nb = dict(blk)
        if not keys:
            nb.update(align_score=0.0, rects=[], bbox=None, bbox_source="none")
            out.append(nb)
            continue
        words = _densest_cluster(_align_block(keys, ocr_keys), line_of)
        score = len(words) / len(keys)
        nb["align_score"] = round(min(1.0, score), 3)
        if words and score >= MIN_ALIGN:
            nb["rects"] = _rects(words, ow, ocr)
            nb["bbox"] = _bbox(nb["rects"])
            nb["bbox_source"] = "fusion"
        else:
            nb.update(rects=[], bbox=None, bbox_source="none")
        out.append(nb)

    # Interpolate blocks OCR could not read (ornate Quran type, faint print): use the OCR
    # lines strictly between the nearest aligned neighbours in reading order.
    for i, b in enumerate(out):
        if b["bbox_source"] != "none" or b["type"] in ("page_number", "page_header"):
            continue
        prev = next(
            (out[j] for j in range(i - 1, -1, -1) if out[j]["bbox_source"] == "fusion"), None
        )
        nxt = next(
            (out[j] for j in range(i + 1, len(out)) if out[j]["bbox_source"] == "fusion"), None
        )
        top = prev["bbox"][3] if prev else 0
        bottom = nxt["bbox"][1] if nxt else ocr["height"]
        between = [
            ln["bbox"]
            for ln in ocr["lines"]
            if ln["bbox"][1] >= top - 5 and ln["bbox"][3] <= bottom + 5
        ]
        if between:
            b["rects"] = between
            b["bbox"] = _bbox(between)
            b["bbox_source"] = "interpolated"
    return out


def _iou(a: list[float], b: list[float]) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def fuse_two_lanes(blocks: list[dict], ocr: dict, vlm_boxes: dict[int, list[int]]) -> list[dict]:
    """Final geometry. Primary = the VLM's box for the block (box_2d, 0-1000). If the OCR-word
    alignment lands on the same place (IoU >= 0.5), the two lanes agree: keep the precise
    per-line OCR rects and mark bbox_source="fusion". Otherwise keep the VLM box,
    bbox_source="vlm", and record lanes_agree=False (a confidence signal)."""
    W, H = ocr["width"], ocr["height"]
    ocr_fused = fuse(blocks, ocr)
    out = []
    for b in ocr_fused:
        v = vlm_boxes.get(b["order"])
        vb = [v[1] * W / 1000, v[0] * H / 1000, v[3] * W / 1000, v[2] * H / 1000] if v else None
        nb = dict(b)
        if vb and b.get("bbox") and b["bbox_source"] == "fusion" and _iou(vb, b["bbox"]) >= 0.5:
            nb["lanes_agree"] = True
        elif vb:
            nb.update(
                bbox=[round(x) for x in vb],
                rects=[[round(x) for x in vb]],
                bbox_source="vlm",
                lanes_agree=False,
            )
        else:
            nb["lanes_agree"] = False  # only the OCR lane (or nothing) located this block
        out.append(nb)
    return out
