"""Extraction quality vs. gold: CER/WER (strict + loose), block-type accuracy,
footnote-link P/R/F1, and editor/matn separation.

Text for CER is compared in reading order with page furniture (page_number/page_header)
excluded, since both are trivial and not part of the content.
"""

from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher

import jiwer

from pipeline.config import GOLD, INTER, page_id
from pipeline.gold_consensus import canon
from pipeline.normalize import normalize, normalize_marker

SKIP = {"page_number", "page_header"}


def page_text(blocks: list[dict]) -> str:
    return "\n".join(b["text"] for b in blocks if b["type"] not in SKIP)


def _clean(s: str, level: str) -> str:
    if level == "strict":
        # NFC puts combining marks in canonical order (e.g. shadda+fatha), so the same
        # printed marks typed in a different order are not counted as an error.
        # canon(): NFC (canonical mark order) + no whitespace just inside brackets/markers,
        # the same equivalence the gold review applies (owner rule, GATE 4 r2).
        return canon(s)
    return normalize(s, "cer_loose")


def cer_wer(ref: str, hyp: str, level: str) -> dict:
    r, h = _clean(ref, level), _clean(hyp, level)
    return {"cer": jiwer.cer(r, h), "wer": jiwer.wer(r, h), "ref_chars": len(r)}


def footnote_links(blocks: list[dict]) -> set[tuple[str, str]]:
    """(marker, normalized first 3 words of the footnote) pairs: a body marker counts as
    linked when a footnote with the same marker exists on the page."""
    fns = {}
    for b in blocks:
        if b["type"] == "footnote":
            m = normalize_marker(b.get("footnote_marker") or b["text"][:6])
            if m:
                body = re.sub(r"^\s*\(?\s*[\d٠-٩]+\s*\)?", "", b["text"])
                fns[m] = " ".join(normalize(body).split()[:3])
    links = set()
    for b in blocks:
        if b["type"] in ("footnote",):
            continue
        for mk in re.findall(r"\(\s*[\d٠-٩]+\s*\)", b["text"]):
            m = normalize_marker(mk)
            if m in fns:
                links.add((m, fns[m]))
    return links


def prf(gold: set, pred: set) -> dict:
    tp = len(gold & pred)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    return {"p": p, "r": r, "f1": 2 * p * r / (p + r) if p + r else 0.0, "gold": len(gold)}


def type_accuracy(gold: list[dict], pred: list[dict]) -> float:
    """Each gold block is matched to the predicted block with the most similar text;
    accuracy = share of gold blocks (by characters) whose match has the same type."""
    tot = ok = 0
    for g in gold:
        if g["type"] in SKIP:
            continue
        gk = normalize(g["text"])
        best, br = None, 0.0
        for p in pred:
            r = SequenceMatcher(None, gk, normalize(p["text"]), autojunk=False).ratio()
            if r > br:
                best, br = p, r
        tot += len(gk)
        if best and br > 0.5 and best["type"] == g["type"]:
            ok += len(gk)
    return ok / tot if tot else 0.0


def evaluate(printed: int, systems: dict[str, list[dict]], gold_transform=None) -> dict:
    gold = json.loads((GOLD / f"{page_id(printed)}.json").read_text())["blocks"]
    if gold_transform:  # e.g. the same layout normalization applied to the systems
        gold = gold_transform(gold)
    gt = page_text(gold)
    gl = footnote_links(gold)
    res = {}
    for name, blocks in systems.items():
        ht = page_text(blocks)
        res[name] = {
            "strict": cer_wer(gt, ht, "strict"),
            "loose": cer_wer(gt, ht, "loose"),
            "type_acc": type_accuracy(gold, blocks) if blocks and "type" in blocks[0] else None,
            "footnote_links": prf(gl, footnote_links(blocks)),
        }
    return res


def systems_for_page(printed: int, models: list[str]) -> dict[str, list[dict]]:
    pid = page_id(printed)
    out = {}
    ocr = json.loads((INTER / "ocr" / f"{pid}.json").read_text())
    out["tesseract-ara"] = [{"type": "body", "text": ocr["text"]}]
    for m in models:
        p = INTER / "vlm" / m / f"{pid}.json"
        if p.exists():
            out[m] = json.loads(p.read_text())["blocks"]
    return out


if __name__ == "__main__":
    pages = list(map(int, sys.argv[1:]))
    models = [
        "gemini-3.5-flash",
        "gemini-3.8-flash",
        "gemini-3.1-pro-preview",
        "claude-opus-5-5",
        "claude-fable-5-1",
    ]
    allres = {p: evaluate(p, systems_for_page(p, models)) for p in pages}
    print(json.dumps(allres, ensure_ascii=False, indent=1))
