"""Where on the page is a disputed phrase? (fix of Oct 4: wrong or whole-line highlights)

For every token of the pivot reading (Reader B) we look for its OCR word box:
  - "word":   exact alignment with an OCR word
  - "approx": inside a mismatched run, the most similar OCR word (letters >= 50% similar)
For a disputed span:
  - all/some tokens located           -> highlight only those word boxes
  - none located, neighbours on the same printed line -> highlight the gap between them ("gap")
  - otherwise                          -> "uncertain": the reviewer sees the full page with the
                                          estimated area marked and the label «الموقع غير مؤكد»
The crop always shows the full printed line(s) that contain the highlight; it never borrows a
neighbouring line silently.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from rapidfuzz.distance import Levenshtein

from pipeline.normalize import normalize, strip_diacritics

APPROX_MIN = 0.5


def _k(w: str) -> str:
    return normalize(w) or strip_diacritics(w)


def ocr_words(ocr: dict) -> list[dict]:
    return [
        {"key": _k(w["text"]), "bbox": w["bbox"], "line": li, "conf": w.get("conf", 0)}
        for li, ln in enumerate(ocr["lines"])
        for w in ln["words"]
    ]


def token_locations(token_texts: list[str], ow: list[dict]) -> list[dict | None]:
    keys = [_k(t) for t in token_texts]
    okeys = [w["key"] for w in ow]
    locs: list[dict | None] = [None] * len(keys)
    strong: list[bool] = [False] * len(keys)
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, keys, okeys, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                locs[i1 + k] = {"loc": "word", "ow": j1 + k}
                strong[i1 + k] = i2 - i1 >= 2  # runs of 2+ exact words are reliable anchors
        elif tag == "replace" and max(i2 - i1, j2 - j1) <= 2 * min(i2 - i1, j2 - j1) + 1:
            used: set[int] = set()
            for i in range(i1, i2):
                best, bs = None, 0.0
                for j in range(j1, j2):
                    if j in used or not keys[i] or not okeys[j]:
                        continue
                    s = 1 - Levenshtein.normalized_distance(keys[i], okeys[j])
                    if s > bs:
                        best, bs = j, s
                if best is not None and bs >= APPROX_MIN:
                    used.add(best)
                    locs[i] = {"loc": "approx", "ow": best}
    # Weak locations (single exact words, fuzzy matches) must sit between the strong anchors
    # around them in reading order, otherwise they are coincidences elsewhere on the page.
    anchors = [i for i in range(len(keys)) if strong[i]]
    for i, loc in enumerate(locs):
        if loc is None or strong[i]:
            continue
        before = [a for a in anchors if a < i]
        after = [a for a in anchors if a > i]
        lo = ow[locs[before[-1]]["ow"]]["line"] if before else -1
        hi = ow[locs[after[0]]["ow"]]["line"] if after else 10**6
        line = ow[loc["ow"]]["line"]
        if not lo <= line <= hi or (before and after and hi - lo > 6):
            locs[i] = None
        elif loc["loc"] == "word":
            locs[i] = {"loc": "approx", "ow": loc["ow"]}  # lone exact word: treat as approximate
    return locs


def _line_box(ocr: dict, li: int) -> list[int]:
    return list(ocr["lines"][li]["bbox"])


def locate_span(i: int, j: int, locs: list[dict | None], ow: list[dict], ocr: dict) -> dict:
    """Location for disputed tokens i..j (inclusive)."""
    found = [locs[k] for k in range(i, j + 1) if locs[k]]
    if found:
        boxes = [ow[f["ow"]]["bbox"] for f in found]
        lines = sorted({ow[f["ow"]]["line"] for f in found})
        kind = (
            "word"
            if all(f["loc"] == "word" for f in found) and len(found) == j - i + 1
            else "approx"
        )
        return {
            "loc": kind,
            "word_boxes": boxes,
            "line_boxes": [_line_box(ocr, li) for li in lines],
            "hint_box": None,
        }
    pk = next((k for k in range(i - 1, -1, -1) if locs[k]), None)
    nk = next((k for k in range(j + 1, len(locs)) if locs[k]), None)
    prev = locs[pk] if pk is not None else None
    nxt = locs[nk] if nk is not None else None
    if prev and nxt and i - pk <= 2 and nk - j <= 2:  # only immediate neighbours
        pw, nw = ow[prev["ow"]], ow[nxt["ow"]]
        if pw["line"] == nw["line"] and nw["bbox"][2] < pw["bbox"][0]:
            # RTL: the previous word is to the right, the next word to the left.
            lb = _line_box(ocr, pw["line"])
            gap = [nw["bbox"][2] + 2, lb[1], pw["bbox"][0] - 2, lb[3]]
            return {"loc": "gap", "word_boxes": [gap], "line_boxes": [lb], "hint_box": None}
    # Uncertain: estimate a band between the neighbours, else the whole page.
    top = ow[prev["ow"]]["bbox"][1] if prev else 0
    bottom = ow[nxt["ow"]]["bbox"][3] if nxt else ocr["height"]
    if bottom <= top:
        top, bottom = 0, ocr["height"]
    return {
        "loc": "uncertain",
        "word_boxes": [],
        "line_boxes": [],
        "hint_box": [0, top, ocr["width"], bottom],
    }


def relocate_draft(draft: dict, ocr: dict) -> dict:
    """Recompute locations for every review and spot-check item of an existing draft."""
    ow = ocr_words(ocr)
    locs = token_locations([t["raw"] for t in draft["tokens"]], ow)
    for it in draft["review_items"]:
        it.update(locate_span(it["tok_from"], it["tok_to"] - 1, locs, ow, ocr))
    for s in draft["spotcheck"]:
        s.update(locate_span(s["tok"], s["tok"], locs, ow, ocr))
    draft["locator"] = "gold_locate v2 (word-level, honest uncertainty)"
    return draft
