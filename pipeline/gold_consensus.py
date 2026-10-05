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
import unicodedata
from datetime import UTC, datetime
from difflib import SequenceMatcher

from pipeline.config import GOLD, INTER, page_id
from pipeline.gold_locate import locate_span, ocr_words, token_locations
from pipeline.normalize import normalize, strip_diacritics

READER_B = "claude-opus-5-5"
READER_C = "claude-fable-5-1"  # bake-off pages 41, 30, 20
READER_C_OTHER = "surya-ocr-2"  # the other 12 gold pages (open-source, local; owner decision)


def _reader_c(pid: str) -> tuple[str, dict]:
    p = INTER / "vlm" / READER_C / f"{pid}.json"
    if p.exists():
        return READER_C, json.loads(p.read_text())
    return READER_C_OTHER, json.loads((INTER / "surya" / f"{pid}.json").read_text())


MAX_SPAN = 4
SPOTCHECK_RATE = 0.05
SPOTCHECK_RATE_ABSTAIN = 0.10
TESS_MIN_CONF = 60.0
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
    reader_c, vc = _reader_c(pid)

    tb = _flat_tokens(vb["blocks"])
    tc = _flat_tokens(vc["blocks"])
    ta = [
        {"raw": w["text"], "key": _key(w["text"]), "bbox": w["bbox"], "line": li, "conf": w["conf"]}
        for li, ln in enumerate(ocr["lines"])
        for w in ln["words"]
    ]
    kb = [t["key"] for t in tb]
    map_c = _map(kb, [t["key"] for t in tc])
    map_a = _map(kb, [t["key"] for t in ta])

    # status: "agree" (all readers agree, tashkeel included), "abstain" (letters agree and a
    # reader printed no tashkeel on this word, so it abstains on tashkeel only; the remaining
    # reader(s) decide), or "" (disputed -> human review).
    status: list[str] = []
    for i, t in enumerate(tb):
        c1, c2 = map_c[i]
        a1, a2 = map_a[i]
        c_raw = _span_text(tc, c1, c2)
        a_key = " ".join(x["key"] for x in ta[a1:a2])
        furniture = vb["blocks"][t["block"]]["type"] in FURNITURE
        letters_c = c2 - c1 == 1 and _key(c_raw) == t["key"]
        letters_a = furniture or (a2 - a1 == 1 and a_key == t["key"])
        # Rule v3 (owner, Oct 4): Tesseract abstains on a word it read with < 60% confidence
        # (or did not read at all); B and C must then agree exactly, tashkeel included.
        a_conf = min([x["conf"] for x in ta[a1:a2]] or [0.0])
        a_abstains = not letters_a and a_conf < TESS_MIN_CONF
        if not letters_c:
            status.append("")
        elif letters_a and c_raw == t["raw"]:
            status.append("agree")
        elif letters_a and not _DIAC.search(c_raw) and _DIAC.search(t["raw"]):
            status.append("abstain")  # C printed no tashkeel: B's tashkeel stands
        elif a_abstains and c_raw == t["raw"]:
            status.append("abstain_a")  # Tesseract unsure; B and C agree exactly
        else:
            status.append("")
    # Word-level locations for crops (gold_locate: never borrow a neighbouring line).
    ow = ocr_words(ocr)
    locs = token_locations([x["raw"] for x in tb], ow)
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
                **locate_span(i, j, locs, ow, ocr),
                "decision": None,  # filled by reviewer: chosen/edited text ('' = delete)
            }
        )
        i = j + 1

    # 5% spot-check of auto-accepted words, weighted toward diacritized words.
    # Spot-check: 5% of fully agreed words (weighted toward tashkeel) + 10% of words whose
    # tashkeel was decided after a reader abstained.
    rng = random.Random(f"{seed}-{pid}")
    picked: set[int] = set()
    for kind, rate in (
        ("agree", SPOTCHECK_RATE),
        ("abstain", SPOTCHECK_RATE_ABSTAIN),
        ("abstain_a", SPOTCHECK_RATE_ABSTAIN),
    ):
        pool = [k for k, s in enumerate(status) if s == kind]
        n = min(len(pool), max(1, round(len(pool) * rate))) if pool else 0
        weights = [3 if _DIAC.search(tb[k]["raw"]) else 1 for k in pool]
        chosen: set[int] = set()
        while len(chosen) < n:
            chosen.add(rng.choices(pool, weights)[0])
        picked |= chosen
    spot = []
    for k in sorted(picked):
        spot.append(
            {
                "id": f"{pid}-s{len(spot):03d}",
                "tok": k,
                "text": tb[k]["raw"],
                **locate_span(k, k, locs, ow, ocr),
                "kind": status[k],  # agree | abstain | abstain_a
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
            "C": reader_c,
        },
        "rule": (
            "v3: auto-accept iff letters agree across A,B,C and tashkeel agrees between B,C; "
            "C printing no tashkeel abstains on tashkeel only; Tesseract below 60% confidence "
            "abstains and then B and C must agree exactly"
        ),
        "locator": "gold_locate v2 (word-level, honest uncertainty)",
        "blocks": [
            {k: b[k] for k in ("order", "type", "author_role", "column", "footnote_marker", "text")}
            | {"type_reader_c": None, "type_confirmed": None}
            for b in vb["blocks"]
        ],
        "tokens": [{"block": t["block"], "raw": t["raw"]} for t in tb],
        "auto_accepted": sum(1 for s in status if s),
        "auto_accepted_abstain": sum(1 for s in status if s == "abstain"),
        "auto_accepted_tesseract_abstain": sum(1 for s in status if s == "abstain_a"),
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
    draft["auto_resolved_equivalent"] = auto_resolve_equivalent(draft)
    DRAFT.mkdir(parents=True, exist_ok=True)
    out = DRAFT / f"{pid}.json"
    if out.exists():  # never overwrite human decisions
        old = json.loads(out.read_text())
        if any(it["decision"] is not None for it in old["review_items"]):
            return old
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=1))
    return draft


_SP_OPEN = re.compile(r"([(﴿«\[{])\s+")
_SP_CLOSE = re.compile(r"\s+([)﴾»\]}،؛.:,])")
_MARK_BEFORE = re.compile(r"\s+(\([\d٠-٩]{1,3}\))")
_MARK_AFTER = re.compile(r"(\([\d٠-٩]{1,3}\))(?=[^\s)،؛.:,])")


def canon(s: str) -> str:
    """Same printed text, written differently in Unicode: NFC (which also puts combining
    marks such as shadda + fatha in canonical order) and no whitespace just inside brackets,
    footnote markers or before punctuation. Spaces between words are kept: «يارسول» vs
    «يا رسول» is a real difference in the print and stays a human decision."""
    s = re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip()
    s = _SP_CLOSE.sub(r"\1", _SP_OPEN.sub(r"\1", s))
    s = _MARK_BEFORE.sub(r"\1", s)  # «شهدا (٨)» = «شهدا(٨)»
    return _MARK_AFTER.sub(r"\1 ", s)  # one space after a marker


def _letters(s: str) -> str:
    return re.sub(r"\s", "", normalize(s, "search"))


def auto_resolve_equivalent(draft: dict) -> int:
    """Owner rule (GATE 4 r2): a dispute whose readings differ only by Unicode mark order or
    whitespace around brackets/markers is not a real dispute. Auto-accept it when B and C are
    canonically identical and Tesseract either agrees on the letters or gave no reading
    (rule v3: an absent Tesseract reading abstains). Human decisions are never touched."""
    n = 0
    for it in draft["review_items"]:
        if it["decision"] is not None:
            continue
        by = {r: c["text"] for c in it["candidates"] for r in c["readers"]}
        b, c, a = by.get("B"), by.get("C"), by.get("A")
        if not b or not c or canon(b) != canon(c):
            continue
        if a and _letters(a) != _letters(b):
            continue
        it["decision"] = canon(b)
        it["reviewer"] = "auto (equivalent readings)"
        it["decided_at"] = datetime.now(UTC).isoformat()
        it["auto_equivalence"] = True
        n += 1
    return n


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
