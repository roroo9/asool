"""GATE 4 round 2 rules: exact Sahihayn source, equivalent gold readings, unmarked verses,
neighbouring units for multi-condition answers."""

from api.answer import _neighbors
from api.passages import passage
from pipeline import quran
from pipeline.gold_consensus import auto_resolve_equivalent, canon
from pipeline.hadith import sahihayn_label


def test_sahihayn_label_is_exact():
    assert sahihayn_label("متفق عليه") == "في الصحيحين (متفق عليه)"
    assert sahihayn_label("رواه البخارى") == "في صحيح البخاري"
    assert sahihayn_label("رواه مسلمٌ") == "في صحيح مسلم"
    assert sahihayn_label("رواه البخاري ومسلم") == "في الصحيحين (رواه البخاري ومسلم)"


def test_canon_ignores_only_non_real_differences():
    assert canon("الرحيم )") == canon("الرحيم)")
    assert canon("﴿ قُلْ") == canon("﴿قُلْ")
    assert canon("شهدا (٨)") == canon("شهدا(٨)")
    assert canon("بَّ") == canon("بَّ")  # shadda+fatha order
    assert canon("يارسول") != canon("يا رسول")  # a real spacing difference in the print


def _item(b, c, a=None, decision=None):
    cands = [{"text": b, "readers": ["B"]}, {"text": c, "readers": ["C"]}]
    if a:
        cands.append({"text": a, "readers": ["A"]})
    return {"candidates": cands, "decision": decision}


def test_auto_resolve_keeps_real_disputes_and_human_decisions():
    d = {
        "review_items": [
            _item("الرحيم )", "الرحيم)", "الرحيم)"),
            _item("اللَّهَ", "اللَّهِ"),  # tashkeel differs: real
            _item("اللَّهَ", "اللَّهَ", "أنه"),  # Tesseract reads other letters: rule v3
            _item("﴿ قُلْ", "﴿قُلْ", decision="human"),
        ]
    }
    assert auto_resolve_equivalent(d) == 1
    assert d["review_items"][0]["decision"] == "الرحيم)"
    assert d["review_items"][3]["decision"] == "human"


def test_unmarked_verse_in_editor_footnote():
    t = (
        "(٧) تصل روحه حلقومه قال تعالى: وليست التوبة للذين يعملون السيئات "
        "حتى إذا حضر أحدهم الموت قال إنى تبت الآن"
    )
    m = quran.find_unmarked(t)
    assert [(x.surah, x.ayah_start, x.match_type) for x in m] == [(4, 18, "exact")]


def test_neighbors_add_same_page_units():
    p = passage("riyad1956-c019")
    ids = [x["id"] for x in _neighbors([p], [])]
    assert "riyad1956-c018" in ids and "riyad1956-c017" in ids
    assert "riyad1956-c020" not in ids  # different printed page
