"""Arabic normalization: the single source of truth for search, matching and CER.

Never apply this to stored ``text_raw``. Use it only to build comparison keys.

Levels
------
- ``search``    : strip tashkeel/Quranic marks/tatweel, unify letter forms, digits to
                  ASCII, drop punctuation and ornate brackets, collapse whitespace.
- ``quran``     : same as ``search`` (Tanzil simple-clean is compared on the same key);
                  kept as a separate name so the two can diverge without touching callers.
- ``cer_loose`` : strip tashkeel/tatweel and unify letter forms, but KEEP punctuation and
                  digits (as ASCII) so loose CER still reflects layout-level errors.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["normalize", "strip_diacritics", "to_ascii_digits", "normalize_marker"]

# Tashkeel + Quranic annotation marks + superscript alef.
_DIACRITICS_RE = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ࣓-ࣿ]")
_TATWEEL = "ـ"

_LETTER_MAP = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ٲ": "ا",
        "ٳ": "ا",
        "ى": "ي",
        "ی": "ي",  # Persian yeh
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
        "ک": "ك",  # Persian keheh
    }
)

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# Anything that is not a letter/number/space is dropped at the search level.
# This removes ﴿ ﴾ « » ( ) [ ] ، ؛ ؟ . : etc. (The ﷺ ligature is expanded to words by
# NFKC first, so it survives as text.)
_NON_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_HAMZA_ALONE = "ء"


def strip_diacritics(text: str) -> str:
    """Remove tashkeel, Quranic annotation marks and tatweel."""
    return _DIACRITICS_RE.sub("", text).replace(_TATWEEL, "")


def to_ascii_digits(text: str) -> str:
    return text.translate(_DIGITS)


def normalize(text: str, level: str = "search") -> str:
    if level not in {"search", "quran", "cer_loose"}:
        raise ValueError(f"unknown normalization level: {level}")
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    # NFKC expands some presentation forms (e.g. ﷺ -> long phrase). That is fine for
    # matching since both sides go through the same function.
    t = strip_diacritics(t)
    t = t.translate(_LETTER_MAP)
    t = to_ascii_digits(t)
    if level in {"search", "quran"}:
        t = t.replace("_", " ")
        t = _NON_WORD_RE.sub(" ", t)
        t = t.replace(_HAMZA_ALONE, "")
    t = _WS_RE.sub(" ", t).strip()
    return t


_MARKER_RE = re.compile(r"\d+|\*+")
_SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def normalize_marker(marker: str | None) -> str | None:
    """Normalize a footnote marker like '(١)', '¹', '( 1 )', '*' to a bare key ('1', '*')."""
    if not marker:
        return None
    t = to_ascii_digits(marker).translate(_SUPERSCRIPTS)
    m = _MARKER_RE.search(t)
    if not m:
        return None
    return m.group(0).lstrip("0") or "0"
