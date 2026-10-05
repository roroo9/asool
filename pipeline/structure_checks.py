"""Automatic structure checks (owner request, Oct 4: overlay checks on pages 18 and 41).

Run on every page during ingestion; anything suspicious becomes a review flag.
  1. attach_colon_continuations: an editor block (poetry/body) that directly follows a footnote
     ending with ":" belongs to that footnote (e.g. p.41 footnote (٤) introduces a poetry line).
  2. duplicate_runs: the same long run of words (>= 12 words, not just formulae) in two blocks
     of a page -> possible duplicated extraction.
  3. tighten_boxes: a VLM-only box is snapped to the OCR words inside it that match the block's
     words (loose footnote boxes).
"""

from __future__ import annotations

import re

from rapidfuzz.distance import Levenshtein

from pipeline.normalize import normalize

MARK = re.compile(r"\(\s*[\d٠-٩]+\s*\)")
RUN = 12


def attach_colon_continuations(blocks: list[dict]) -> list[dict]:
    for prev, b in zip(blocks, blocks[1:], strict=False):
        if (
            prev["type"] == "footnote"
            and prev["text"].rstrip().endswith((":", "："))
            and b.get("author_role") == "editor"
            and b["type"] in ("poetry", "body", "other")
        ):
            b["attached_to"] = prev["id"]
    return blocks


def duplicate_runs(blocks: list[dict]) -> list[dict]:
    seen: dict[str, str] = {}
    flags = []
    for b in blocks:
        if b["type"] in ("page_number", "page_header"):
            continue
        w = normalize(MARK.sub(" ", b["text"])).split()
        for i in range(len(w) - RUN + 1):
            sh = " ".join(w[i : i + RUN])
            other = seen.get(sh)
            if other and other != b["id"]:
                flags.append({"block_id": b["id"], "reason": f"text duplicated from {other}"})
                break
            seen.setdefault(sh, b["id"])
    return flags


def tighten_boxes(blocks: list[dict], ocr: dict) -> list[dict]:
    words = [w for ln in ocr["lines"] for w in ln["words"]]
    for b in blocks:
        if b.get("bbox_source") != "vlm" or not b.get("bbox"):
            continue
        x0, y0, x1, y1 = b["bbox"]
        keys = {normalize(w) for w in b["text"].split() if len(normalize(w)) > 1}
        hit = []
        for w in words:
            cx = (w["bbox"][0] + w["bbox"][2]) / 2
            cy = (w["bbox"][1] + w["bbox"][3]) / 2
            if not (x0 - 15 <= cx <= x1 + 15 and y0 - 15 <= cy <= y1 + 15):
                continue
            k = normalize(w["text"])
            if k and any(1 - Levenshtein.normalized_distance(k, q) >= 0.6 for q in keys):
                hit.append(w["bbox"])
        if len(hit) >= max(1, len(keys) // 3):
            pad = 6
            nb = [
                min(h[0] for h in hit) - pad,
                min(h[1] for h in hit) - pad,
                max(h[2] for h in hit) + pad,
                max(h[3] for h in hit) + pad,
            ]
            b["bbox_vlm"] = b["bbox"]
            b["bbox"] = nb
            b["rects"] = [nb]
            b["bbox_source"] = "vlm+ocr_snap"
    return blocks


def _marker_num(b: dict) -> int | None:
    m = MARK.search(b.get("footnote_marker") or "") or (
        MARK.match(b["text"].lstrip()) if b.get("text") else None
    )
    if not m:
        return None
    d = re.sub(r"\D", "", m.group(0).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
    return int(d) if d else None


def order_footnote_runs(blocks: list[dict]) -> list[dict]:
    """Two-column footnotes come out of the parser row by row ((١)(٥)(٢)(٦)…) on some pages;
    the print reads the right column, then the left. Within each contiguous run of numbered
    footnotes, put them in marker order. Runs separated by other content (p.41: notes (١)-(٤),
    commentary, notes (٥)-(٨)) stay separate; unnumbered continuations keep their place.
    Sets b["seq"], the stored reading order (ids are not changed)."""
    out: list[dict] = []
    i = 0
    while i < len(blocks):
        if blocks[i]["type"] == "footnote" and _marker_num(blocks[i]) is not None:
            j = i
            while (
                j < len(blocks)
                and blocks[j]["type"] == "footnote"
                and _marker_num(blocks[j]) is not None
            ):
                j += 1
            out += sorted(blocks[i:j], key=_marker_num)
            i = j
        else:
            out.append(blocks[i])
            i += 1
    for k, b in enumerate(out, 1):
        b["seq"] = k
    return out
