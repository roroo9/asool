"""Consensus-assisted gold drafting (CLAUDE.md §12.C).

Three independent readings of a page:
  A = Tesseract `ara` (non-LLM; votes on letters only; supplies word boxes for crops)
  B = Claude Opus 5.5 (pivot: its block structure is the skeleton of the draft)
  C = third reader (Claude Fable 5.1 provisional, or Mistral OCR)

Auto-accept rule for a word of B:
  normalize(A) == normalize(B) == normalize(C)  (letters agree)  AND  B == C exactly
  (diacritics agree between the two VLM readers).
Everything else becomes a review item. Consecutive disputed words are merged into one item
(max 4 words) so the reviewer clicks once per disputed phrase.

Output: data/gold/draft/{page_id}.json
"""

from __future__ import annotations

import json
import random
import re
from difflib import SequenceMatcher

from pipeline.config import GOLD, INTER, page_id
from pipeline.normalize import normalize, strip_diacritics

READER_B = "claude-opus-5-5"
READER_C = "claude-fable-5-1"
MAX_SPAN = 4
SPOTCHECK_RATE = 0.05
FURNITURE = {"page_number", "page_header"}

DRAFT = GOLD / "draft"
_DIAC = re.compile(r"[ً-ْٰ]")


def _key(tok: str) -> str:
    k = normalize(tok, "search")
    return k if k else strip_diacritics(tok)  # punctuation-only tokens compare as themselves


def _flat_tokens(blocks: list[dict]) -> list[dict]:
    out = []
    for bi, b in enumerate(blocks):
        for wi, w in enumerate(b["text"].split()):
            out.append({"block": bi, "i": wi, "raw": w, "key": _key(w)})
    return out


def _align(src: list[str], dst: list[str]) -> list[tuple[str, int, int, int, int]]:
    return SequenceMatcher(None, src, dst, autojunk=False).get_opcodes()


def _map(src_keys: list[str], dst_keys: list[str]) -> dict[int, tuple[int, int]]:
    """For each src index, the dst span (j1, j2) it aligns to (j1==j2 means missing in dst)."""
    m: dict[int, tuple[int, int]] = {}
    for tag, i1, i2, j1, j2 in _align(src_keys, dst_keys):
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                m[i1 + k] = (j1 + k, j1 + k + 1)
        else:  # unequal replace / delete: whole src run maps to whole dst run
            for k in range(i1, i2):
                m[k] = (j1, j2)
    return m


def _span_text(toks: list[dict], j1: int, j2: int) -> str:
    return " ".join(t["raw"] for t in toks[j1:j2])


def build_page(printed: int, seed: int = 7) -> dict:
    pid = page_id(printed)
    ocr = json.loads((INTER / "ocr" / f"{pid}.json").read_text())
    vb = json.loads((INTER / "vlm" / READER_B / f"{pid}.json").read_text())
    vc = json.loads((INTER / "vlm" / READER_C / f"{pid}.json").read_text())

    tb = _flat_tokens(vb["blocks"])
    tc = _flat_tokens(vc["blocks"])
    ta = [
        {"raw": w["text"], "key": _key(w["text"]), "bbox": w["bbox"], "line": li}
        for li, ln in enumerate(ocr["lines"])
        for w in ln["words"]
    ]
    kb = [t["key"] for t in tb]
    map_c = _map(kb, [t["key"] for t in tc])
    map_a = _map(kb, [t["key"] for t in ta])

    status = []
    for i, t in enumerate(tb):
        c1, c2 = map_c[i]
        a1, a2 = map_a[i]
        c_raw = _span_text(tc, c1, c2)
        a_key = " ".join(x["key"] for x in ta[a1:a2])
        vlm_agree = c2 - c1 == 1 and c_raw == t["raw"]
        if vb["blocks"][t["block"]]["type"] in FURNITURE:
            agree = vlm_agree  # page number/header: Tesseract often skips it; VLMs suffice
        else:
            agree = vlm_agree and (a2 - a1 == 1 and a_key == t["key"])
        status.append(agree)

    # Group consecutive disputed tokens (same block) into review items.
    items = []
    i = 0
    while i < len(tb):
        if status[i]:
            i += 1
            continue
        j = i
        while (
            j + 1 < len(tb)
            and not status[j + 1]
            and tb[j + 1]["block"] == tb[i]["block"]
            and j + 1 - i < MAX_SPAN
        ):
            j += 1
        c1, c2 = map_c[i][0], map_c[j][1]
        a1, a2 = map_a[i][0], map_a[j][1]
        boxes = [x["bbox"] for x in ta[a1:a2]]
        lines = sorted({x["line"] for x in ta[a1:a2]})
        if not boxes:  # nothing aligned in Tesseract: use neighbors' line for the crop
            for k in list(range(i - 1, -1, -1)) + list(range(j + 1, len(tb))):
                n1, n2 = map_a[k]
                if n2 > n1:
                    lines = [ta[n1]["line"]]
                    break
        line_boxes = [ocr["lines"][li]["bbox"] for li in lines]
        b_text = " ".join(t["raw"] for t in tb[i : j + 1])
        cands = []
        readings = (("B", b_text), ("C", _span_text(tc, c1, c2)), ("A", _span_text(ta, a1, a2)))
        for src, txt in readings:
            if txt and txt not in [c["text"] for c in cands]:
                cands.append({"text": txt, "readers": [src]})
            elif txt:
                next(c for c in cands if c["text"] == txt)["readers"].append(src)
        items.append(
            {
                "id": f"{pid}-r{len(items):03d}",
                "block": tb[i]["block"],
                "tok_from": i,
                "tok_to": j + 1,
                "candidates": cands,
                "word_boxes": boxes,
                "line_boxes": line_boxes,
                "decision": None,  # filled by reviewer: chosen/edited text ('' = delete)
            }
        )
        i = j + 1

    # 5% spot-check of auto-accepted words, weighted toward diacritized words.
    rng = random.Random(f"{seed}-{pid}")
    accepted = [k for k, s in enumerate(status) if s]
    n = max(1, round(len(accepted) * SPOTCHECK_RATE)) if accepted else 0
    weights = [3 if _DIAC.search(tb[k]["raw"]) else 1 for k in accepted]
    picked: set[int] = set()
    while len(picked) < n:
        picked.add(rng.choices(accepted, weights)[0])
    spot = []
    for k in sorted(picked):
        a1, a2 = map_a[k]
        spot.append(
            {
                "id": f"{pid}-s{len(spot):03d}",
                "tok": k,
                "text": tb[k]["raw"],
                "word_boxes": [x["bbox"] for x in ta[a1:a2]],
                "line_boxes": [ocr["lines"][ta[a1]["line"]]["bbox"]] if a2 > a1 else [],
                "verdict": None,  # "ok" | "wrong"
                "fix": None,
            }
        )

    blocks_c_types = [b["type"] for b in vc["blocks"]]
    draft = {
        "page_id": pid,
        "printed": printed,
        "readers": {
            "A": ocr["engine"],
            "B": READER_B,
            "C": READER_C,
        },
        "rule": "auto-accept iff letters agree across A,B,C and diacritics agree between B,C",
        "blocks": [
            {k: b[k] for k in ("order", "type", "author_role", "column", "footnote_marker", "text")}
            | {"type_reader_c": None, "type_confirmed": None}
            for b in vb["blocks"]
        ],
        "tokens": [{"block": t["block"], "raw": t["raw"]} for t in tb],
        "auto_accepted": sum(status),
        "total_tokens": len(tb),
        "review_items": items,
        "spotcheck": spot,
        "structure_reviewed": False,
    }
    # Block types according to reader C, matched by best text overlap (for the structure step).
    for b in draft["blocks"]:
        best, best_r = None, 0.0
        for bc, tcx in zip(vc["blocks"], blocks_c_types, strict=True):
            r = SequenceMatcher(None, _key(b["text"]), _key(bc["text"])).ratio()
            if r > best_r:
                best, best_r = tcx, r
        b["type_reader_c"] = best if best_r > 0.5 else None
    DRAFT.mkdir(parents=True, exist_ok=True)
    out = DRAFT / f"{pid}.json"
    if out.exists():  # never overwrite human decisions
        old = json.loads(out.read_text())
        if any(it["decision"] is not None for it in old["review_items"]):
            return old
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=1))
    return draft


def gold_text(draft: dict) -> list[dict]:
    """Apply review decisions and return final gold blocks."""
    toks = [t["raw"] for t in draft["tokens"]]
    repl: dict[int, tuple[int, str]] = {}
    for it in draft["review_items"]:
        if it["decision"] is None:
            raise ValueError(f"unreviewed item {it['id']}")
        repl[it["tok_from"]] = (it["tok_to"], it["decision"])
    for s in draft["spotcheck"]:
        if s["verdict"] == "wrong" and s["fix"] is not None:
            repl.setdefault(s["tok"], (s["tok"] + 1, s["fix"]))
    out_words: list[list[str]] = [[] for _ in draft["blocks"]]
    i = 0
    while i < len(toks):
        blk = draft["tokens"][i]["block"]
        if i in repl:
            j, txt = repl[i]
            if txt:
                out_words[blk].append(txt)
            i = j
        else:
            out_words[blk].append(toks[i])
            i += 1
    return [
        {
            "order": b["order"],
            "type": b["type_confirmed"] or b["type"],
            "author_role": b["author_role"],
            "footnote_marker": b["footnote_marker"],
            "text": " ".join(w),
        }
        for b, w in zip(draft["blocks"], out_words, strict=True)
    ]


if __name__ == "__main__":
    import sys

    for p in map(int, sys.argv[1:]):
        d = build_page(p)
        print(
            p,
            f"tokens={d['total_tokens']} auto={d['auto_accepted']}",
            f"review_items={len(d['review_items'])} spot={len(d['spotcheck'])}",
        )
