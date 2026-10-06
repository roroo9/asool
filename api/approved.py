"""Approved sources OUTSIDE the indexed book (owner decision, Oct 6; scientific package pp.6, 9).

For a foundational level A/B question that the book does not answer (or answers only in part),
the answer may also use, clearly labeled as outside the indexed book:
  - verses of the King Fahd Complex Mushaf, found by meaning (pipeline.quran_search), each with
    its meaning from «التفسير الميسر» via QuranEnc;
  - definitions from the Encyclopedia of Translated Islamic Terminology (terminologyenc.com);
and always ends with a referral to the package's approved resources. Nothing here is written by
a model: every text comes from the reference files, with its source and link.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

from pipeline import quran
from pipeline.normalize import normalize
from pipeline.quran_search import search as quran_search

ROOT = Path(__file__).resolve().parents[1]
TERMS = ROOT / "data" / "reference" / "terminologyenc" / "terms.json"

REFERRALS = {
    "doubts": {
        "title": "بينات: أسئلة وأجوبة عن الإسلام",
        "url": "https://dawa.center/file/7937",
    },
    "history": {"title": "الدرر السنية: الموسوعة التاريخية", "url": "https://dorar.net/history"},
    "fiqh": {"title": "الدرر السنية: الموسوعة الفقهية", "url": "https://dorar.net/feqhia"},
    "concept": {
        "title": "موسوعة المصطلحات الإسلامية المترجمة",
        "url": "https://terminologyenc.com",
    },
}


@lru_cache(maxsize=1)
def _terms() -> dict:
    return json.loads(TERMS.read_text(encoding="utf-8")) if TERMS.exists() else {}


def _plain(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def term_entries(text: str, limit: int = 3) -> list[dict]:
    """Encyclopedia entries whose term occurs in the text (question + search query)."""
    words = set(normalize(text).split())
    out = []
    for ar, e in _terms().items():
        k = normalize(ar)
        if k in words or k.removeprefix("ال") in words or f"ال{k}" in words:
            a = e.get("ar") or {}
            en = e.get("en") or {}
            out.append(
                {
                    "kind": "term",
                    "term": ar,
                    "term_en": en.get("term"),
                    "definition": _plain(a.get("idio_def", "")),
                    "explanation": _plain(a.get("brief_expl", ""))[:900],
                    "definition_en": _plain(en.get("idio_def", "")),
                    "source": "موسوعة المصطلحات الإسلامية المترجمة (terminologyenc.com)",
                    "url": e["url"],
                }
            )
    return out[:limit]


def verse_entries(query: str, qvec: np.ndarray | None, k: int = 4) -> list[dict]:
    out = []
    for v in quran_search(query, qvec, k):
        t = quran.tafsir(v["surah"], v["ayah"])
        out.append(
            {
                "kind": "quran",
                "surah": v["surah"],
                "surah_name": v["surah_name"],
                "ayah": v["ayah"],
                "text": v["text"],
                "tafsir": t,
                "source": v["reference_source"],
                "url": v["quranpedia_url"],
            }
        )
    return out


def context(question: str, cls: dict, qvec: np.ndarray | None, verses: bool = True) -> dict:
    """External items tagged Q1.. / T1.. for the prompt, plus referrals."""
    mq = cls.get("mushaf_query_ar") or ""
    q = f"{question} {mq or cls.get('search_query_ar', '')}"
    if mq and verses:
        from api.search import embed_query

        qvec = embed_query(f"{question}\n{mq}")
    verse_items = verse_entries(q, qvec, k=3) if verses else []
    terms = term_entries(" ".join([question, *(cls.get("key_terms_ar") or [])]))
    items = {}
    for i, v in enumerate(verse_items, 1):
        items[f"Q{i}"] = v
    for i, t in enumerate(terms, 1):
        items[f"T{i}"] = t
    topics = cls.get("referral_topics") or [cls.get("referral_topic") or "doubts"]
    refs = [REFERRALS["doubts"]]
    refs += [REFERRALS[x] for x in ("history", "fiqh", "concept") if x in topics]
    return {"items": items, "referrals": refs}


def prompt_block(items: dict) -> str:
    parts = []
    for tag, it in items.items():
        if it["kind"] == "quran":
            parts.append(
                f"[{tag}] (verse from the King Fahd Mushaf, OUTSIDE the indexed book) "
                f"سورة {it['surah_name']} {it['ayah']}: {' '.join(_verse_words(it))}\n"
                f"    meaning (التفسير الميسر, QuranEnc): {it['tafsir']['text'] or '-'}"
            )
        else:
            parts.append(
                f"[{tag}] (definition from the Encyclopedia of Translated Islamic Terminology, "
                f"OUTSIDE the indexed book) {it['term']}: {it['definition']} {it['explanation']}"
                + (
                    f"\n    English: {it['term_en']}: {it['definition_en']}"
                    if it["term_en"]
                    else ""
                )
            )
    return "\n".join(parts)


def _verse_words(it: dict) -> list[str]:
    a = next(
        (x for x in quran.load_index().ayahs if (x.surah, x.ayah) == (it["surah"], it["ayah"])),
        None,
    )
    return a.words if a else it["text"].split()


def verify_external(quote: str, it: dict) -> bool:
    """A quote from an external item must occur verbatim (normalized) in its approved text."""
    if it["kind"] == "term":  # «القرآن: …»: the entry label as laid out in the prompt
        quote = re.sub(rf"^\s*{re.escape(it['term'])}\s*:\s*", "", quote)
    q = normalize(quote, "quran")
    if len(q.split()) < 2:
        return False
    if it["kind"] == "quran":
        hay = " ".join(_verse_words(it)) + " " + normalize(it["tafsir"]["text"] or "", "quran")
    else:
        hay = normalize(
            " ".join([it["definition"], it["explanation"], it.get("definition_en") or ""]),
            "quran",
        )
    return f" {q} " in f" {hay} "
