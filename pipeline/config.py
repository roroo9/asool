"""Shared paths and corpus definition."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
PAGES = DATA / "pages"
INTER = DATA / "intermediate"
GOLD = DATA / "gold"
REF = DATA / "reference"

BOOK_ID = "riyad1956"
BOOK = {
    "id": BOOK_ID,
    "title_ar": "رياض الصالحين",
    "title_en": "Riyad al-Salihin",
    "author_ar": "الإمام يحيى بن شرف النووي (ت 676هـ)",
    "edition": "دار إحياء الكتب العربية (عيسى البابي الحلبي)، القاهرة، 1375هـ / 1956م",
    "editor_ar": "مصطفى محمد عمارة",
    "publisher": "دار إحياء الكتب العربية",
    "year": 1956,
    "license": "Matn: public domain. Editor footnotes/commentary: copyright unverified.",
    "source_url": "https://archive.org/details/rsnawwy",
    "source_file": "rs-mohaqaq.pdf",
    "approved_reference_category": "الحديث النبوي (كتب السنة المعتمدة)",
}
PDF_PATH = RAW / BOOK["source_file"]

# Printed page N == PDF page N (1-based), i.e. 0-based index N-1.
CORPUS_PAGES = list(range(12, 42))  # printed pages 12..41 (30 pages)
BAKEOFF_PAGES = [41, 30, 20]
# 15 gold pages: the 3 bake-off pages + 12 spread across the range.
GOLD_PAGES = sorted({41, 30, 20, 12, 14, 16, 18, 22, 24, 26, 28, 33, 35, 37, 39})


def page_id(printed: int) -> str:
    return f"{BOOK_ID}-p{printed:03d}"
