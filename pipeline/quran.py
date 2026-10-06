"""Quran detection & verification (CLAUDE.md §4.3, §12.B2).

Reference: Quranpedia mushaf 1 (Hafs, matching the King Fahd Complex print).
The printed text is NEVER rewritten; we only report the best-matching reference window,
a similarity, a classification and word-level diff ops.
"""

from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from rapidfuzz.distance import Levenshtein

from pipeline.config import REF
from pipeline.normalize import normalize

# Primary: King Fahd Complex official developer data (Hafs, v3.0), qurancomplex.gov.sa/quran-dev
KFGQPC_FILE = (
    REF / "quran" / "kfgqpc" / "hafs_v30" / "kfgqpc_hafs_v30-data" / "kfgqpc_hafs_v30.json"
)
KFGQPC_SOURCE = "مجمع الملك فهد لطباعة المصحف الشريف، بيانات المطورين، رواية حفص، الإصدار 3.0"
# Documented fallback: Quranpedia mushaf 1 (Hafs, matches the King Fahd print)
QURAN_FILE = REF / "quran" / "qp_mushafs-1.json.gz"
MINOR = 0.85
MIN_WORDS = 6  # unmarked spans need >= 6 consecutive words hitting the 3-gram index
MARKERS = re.compile(r"\(\s*[\d٠-٩]+\s*\)|[¹²³⁴⁵⁶⁷⁸⁹⁰]+")
BRACKETS = re.compile(r"[﴿{]([^﴾}]+)[﴾}]")


@dataclass
class Ayah:
    surah: int
    ayah: int
    text: str  # display text, exactly as in the reference
    words: list[str]  # normalized words (imla'i spelling: used for matching)
    surah_name: str = ""


def _load_kfgqpc() -> list[Ayah]:
    rows = json.loads(KFGQPC_FILE.read_text(encoding="utf-8-sig"))
    out = []
    for r in rows:
        words = normalize(r["aya_text_emlaey"], "quran").split()  # imla'i text: for matching
        out.append(
            Ayah(
                int(r["sura_no"]),
                int(r["aya_no"]),
                r["aya_text_unicode"].strip(),
                words,
                r.get("sura_name_ar", "").strip(),
            )
        )
    return out


def _load_quranpedia() -> list[Ayah]:
    data = json.loads(gzip.decompress(QURAN_FILE.read_bytes()))["data"]
    out = []
    for s in data["surahs"]:
        for a in s["ayahs"]:
            text = a["text"].replace("\ufeff", "").strip()
            words = normalize(text, "quran").split()
            out.append(Ayah(int(a["surah"]), int(a["number"]), text, words))
    return out


def reference_source() -> str:
    return KFGQPC_SOURCE if KFGQPC_FILE.exists() else "Quranpedia mushaf 1 (fallback)"


@dataclass
class QuranIndex:
    ayahs: list[Ayah]
    words: list[str] = field(default_factory=list)  # all normalized words, mushaf order
    pos: list[tuple[int, int]] = field(default_factory=list)  # word -> (ayah idx, word idx)
    trigrams: dict[tuple[str, str, str], list[int]] = field(default_factory=dict)


@lru_cache(maxsize=1)
def load_index() -> QuranIndex:
    ayahs = _load_kfgqpc() if KFGQPC_FILE.exists() else _load_quranpedia()
    idx = QuranIndex(ayahs)
    for ai, a in enumerate(ayahs):
        for wi, w in enumerate(a.words):
            idx.words.append(w)
            idx.pos.append((ai, wi))
    for i in range(len(idx.words) - 2):
        idx.trigrams.setdefault(tuple(idx.words[i : i + 3]), []).append(i)
    return idx


@dataclass
class QuranMatch:
    printed_text: str
    surah: int
    ayah_start: int
    ayah_end: int
    canonical_text: str
    similarity: float
    match_type: str  # exact | minor_variant | mismatch
    diff_ops: list[dict]

    @property
    def quranpedia_url(self) -> str:
        return f"https://quranpedia.net/surah/{self.surah}/{self.ayah_start}"


def _sim(a: list[str], b: list[str]) -> float:
    """Character-level similarity of two word sequences (1 - normalized Levenshtein)."""
    return 1.0 - Levenshtein.normalized_distance(" ".join(a), " ".join(b))


def _candidates(idx: QuranIndex, words: list[str]) -> list[int]:
    """Global word positions where a window could start, voted by shared 3-grams."""
    votes: dict[int, int] = {}
    for i in range(len(words) - 2):
        for g in idx.trigrams.get(tuple(words[i : i + 3]), []):
            start = g - i
            votes[start] = votes.get(start, 0) + 1
    if not votes and len(words) >= 2:  # very short or noisy span: fall back to bigrams
        for gi in range(len(idx.words) - 1):
            if idx.words[gi : gi + 2] == words[:2]:
                votes[gi] = 1
    return [s for s, _ in sorted(votes.items(), key=lambda kv: -kv[1])[:20]]


def _best_window(idx: QuranIndex, words: list[str]) -> tuple[float, int, int] | None:
    best = None
    n = len(words)
    for start in _candidates(idx, words):
        for ln in range(max(1, n - 2), n + 3):  # allow small insertions/deletions
            s, e = max(0, start), min(len(idx.words), start + ln)
            if e <= s:
                continue
            sim = _sim(words, idx.words[s:e])
            if best is None or sim > best[0]:
                best = (sim, s, e)
    return best


def _diff(printed: list[str], ref: list[str]) -> list[dict]:
    ops = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, printed, ref, autojunk=False).get_opcodes():
        if tag != "equal":
            ops.append({"op": tag, "printed": printed[i1:i2], "reference": ref[j1:j2], "at": i1})
    return ops


def classify(sim: float, ops: list[dict]) -> str:
    """exact: no word differs (after normalization).
    minor_variant: only 1-2 one-word replacements that look like the same word
      (char similarity >= 0.6: an OCR slip or spelling variant). Shown with a diff.
    mismatch: a different word, a missing/extra word, or low overall similarity:
      a possible misquotation or extraction error -> review queue."""
    if not ops:
        return "exact"
    if sim < MINOR:
        return "mismatch"
    small = all(
        o["op"] == "replace"
        and len(o["printed"]) == len(o["reference"]) == 1
        and 1 - Levenshtein.normalized_distance(o["printed"][0], o["reference"][0]) >= 0.6
        for o in ops
    )
    return "minor_variant" if small and len(ops) <= 2 else "mismatch"


def verify(printed_text: str) -> QuranMatch | None:
    """Match a printed span to the reference. None if nothing Quranic is found."""
    idx = load_index()
    words = normalize(MARKERS.sub(" ", printed_text), "quran").split()
    if len(words) < 2:
        return None
    best = _best_window(idx, words)
    if not best:
        return None
    sim, s, e = best
    if sim < 0.6:
        return None
    # Trim reference-only words at the window edges (a partial quote of a longer ayah).
    ops = _diff(words, idx.words[s:e])
    while ops and ops[0]["op"] == "insert" and ops[0]["at"] == 0:
        s += len(ops[0]["reference"])
        ops = _diff(words, idx.words[s:e])
    while ops and ops[-1]["op"] == "insert" and ops[-1]["at"] == len(words):
        e -= len(ops[-1]["reference"])
        ops = _diff(words, idx.words[s:e])
    sim = _sim(words, idx.words[s:e])
    a0, _ = idx.pos[s]
    a1, _ = idx.pos[e - 1]
    if ops:
        # The print may follow the Uthmani spelling (e.g. «أيه المؤمنون», 24:31) where the
        # imla'i reference differs. If the printed words appear verbatim in the Uthmani text of
        # the same ayahs, it is not a variant.
        uth_text = " ".join(a.text for a in idx.ayahs[a0 : a1 + 1])
        uth = [w for w in normalize(uth_text, "quran").split() if not w.isdigit()]
        if f" {' '.join(words)} " in f" {' '.join(uth)} ":
            ops, sim = [], 1.0
    mtype = classify(sim, ops)
    first, last = idx.ayahs[a0], idx.ayahs[a1]
    canonical = " ".join(a.text for a in idx.ayahs[a0 : a1 + 1])
    return QuranMatch(
        printed_text=printed_text,
        surah=first.surah,
        ayah_start=first.ayah,
        ayah_end=last.ayah if last.surah == first.surah else first.ayah,
        canonical_text=canonical,
        similarity=round(sim, 4),
        match_type=mtype,
        diff_ops=ops,
    )


def find_unmarked(text: str) -> list[QuranMatch]:
    """Spans of >= MIN_WORDS consecutive words that hit the 3-gram index (unmarked quotes)."""
    idx = load_index()
    raw = text.split()
    norm = [normalize(w, "quran") for w in raw]
    hits = [False] * len(norm)
    for i in range(len(norm) - 2):
        if tuple(norm[i : i + 3]) in idx.trigrams:
            hits[i] = hits[i + 1] = hits[i + 2] = True
    out, i = [], 0
    while i < len(hits):
        if hits[i]:
            j = i
            while j + 1 < len(hits) and hits[j + 1]:
                j += 1
            if j - i + 1 >= MIN_WORDS:
                m = verify(" ".join(raw[i : j + 1]))
                # Unmarked text is only reported when it is clearly Quran; a loose match on
                # common phrases (رضي الله عنهم أن …) is not evidence of a quotation.
                if m and m.match_type in ("exact", "minor_variant"):
                    out.append(m)
            i = j + 1
        else:
            i += 1
    return out


def bracketed_spans(text: str) -> list[str]:
    return [m.group(1).strip() for m in BRACKETS.finditer(text)]


@lru_cache(maxsize=1)
def _bigrams() -> dict[tuple[str, str], list[int]]:
    idx = load_index()
    bg: dict[tuple[str, str], list[int]] = {}
    for i in range(len(idx.words) - 1):
        bg.setdefault((idx.words[i], idx.words[i + 1]), []).append(i)
    return bg


def _word_variants(w: str) -> set[str]:
    out = {w}
    if w.startswith("و") and len(w) > 3:
        out.add(w[1:])
    else:
        out.add("و" + w)
    return out


@lru_cache(maxsize=1)
def _idf() -> dict[str, float]:
    import math
    from collections import Counter

    idx = load_index()
    df = Counter()
    for a in idx.ayahs:
        df.update(set(a.words))
    n = len(idx.ayahs)
    return {w: math.log(n / c) for w, c in df.items()}


def _weighted_overlap(words: list[str], ref: list[str]) -> float:
    """Share of the quote's information (IDF-weighted words) found in the reference window;
    tolerant of the conjunction «و». Rare, content-bearing words (الصابرين) count more than
    frequent ones (الله، إن)."""
    idf = _idf()
    refset = set(ref) | {w[1:] for w in ref if w.startswith("و")}
    total = sum(idf.get(w, 8.0) for w in words) or 1.0
    got = sum(idf.get(w, 8.0) for w in words if w in refset or ("و" + w) in refset)
    return got / total


def candidates(printed_text: str, top: int = 3) -> list[QuranMatch]:
    """Several plausible verses for a short or altered quotation (a 4-word misquote can be
    close to more than one verse). Votes from shared word pairs (with and without the
    conjunction «و»), ranked by character similarity. Distinct ayahs, best first."""
    idx = load_index()
    words = normalize(MARKERS.sub(" ", printed_text), "quran").split()
    if len(words) < 2:
        return []
    bg = _bigrams()
    starts: set[int] = set(_candidates(idx, words))
    for i in range(len(words) - 1):
        for a in _word_variants(words[i]):
            for b in _word_variants(words[i + 1]):
                for pos in bg.get((a, b), [])[:200]:
                    # tolerate one extra/missing word before the pair (e.g. «إن الله» vs «والله»)
                    starts.update((pos - i - 1, pos - i, pos - i + 1))
    scored = []
    for start in starts:
        for ln in range(max(1, len(words) - 1), len(words) + 2):
            s, e = max(0, start), min(len(idx.words), start + ln)
            if e > s:
                scored.append((_sim(words, idx.words[s:e]), s, e))
    # Best window per ayah, then rank by (information overlap, character similarity).
    best: dict[int, tuple[float, float, int, int]] = {}
    for sim, s, e in scored:
        if sim < 0.6:
            continue
        a0 = idx.pos[s][0]
        wo = _weighted_overlap(words, idx.words[s:e])
        if a0 not in best or (wo, sim) > best[a0][:2]:
            best[a0] = (wo, sim, s, e)
    ranked = sorted(best.items(), key=lambda kv: kv[1][:2], reverse=True)
    out: list[QuranMatch] = []
    for a0, (wo, sim, s, e) in ranked[:top]:
        ayah = idx.ayahs[a0]
        a1 = idx.pos[e - 1][0]
        last = idx.ayahs[a1] if idx.ayahs[a1].surah == ayah.surah else ayah
        m = QuranMatch(
            printed_text=printed_text,
            surah=ayah.surah,
            ayah_start=ayah.ayah,
            ayah_end=last.ayah,
            canonical_text=" ".join(x.text for x in idx.ayahs[a0 : a1 + 1])
            if last is not ayah
            else ayah.text,
            similarity=round(sim, 4),
            match_type="exact" if sim >= 0.999 else "candidate",
            diff_ops=_diff(words, idx.words[s:e]),
        )
        m.overlap = round(wo, 3)  # type: ignore[attr-defined]
        m.surah_name = ayah.surah_name  # type: ignore[attr-defined]
        m.matched_words = idx.words[s:e]  # type: ignore[attr-defined]
        out.append(m)
    return out


TAFSIR_SOURCE = (
    "التفسير الميسر، مجمع الملك فهد لطباعة المصحف الشريف، عبر موسوعة القرآن الكريم (QuranEnc)"
)


@lru_cache(maxsize=1)
def _tafsir() -> dict[str, str]:
    p = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "reference"
        / "quranenc"
        / "arabic_moyassar.json"
    )
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def tafsir(surah: int, ayah_start: int, ayah_end: int | None = None) -> dict:
    """Meaning of a verse from «التفسير الميسر» (King Fahd Complex) via QuranEnc, an approved
    platform of the scientific package. Never generated. If the file is missing, only a link."""
    ayah_end = ayah_end or ayah_start
    t = _tafsir()
    parts = [t[f"{surah}:{a}"] for a in range(ayah_start, ayah_end + 1) if f"{surah}:{a}" in t]
    return {
        "text": " ".join(parts) or None,
        "source": TAFSIR_SOURCE,
        "url": f"https://quranenc.com/ar/browse/arabic_moyassar/{surah}#{ayah_start}",
    }
