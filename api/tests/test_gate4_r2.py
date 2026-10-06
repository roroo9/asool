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
    from api.question_review import _block_chunk

    bc = _block_chunk()
    p = passage(bc["riyad1956-p019-b13"])  # Ibn Umar «ما لم يغرغر»
    ids = [x["id"] for x in _neighbors([p], [])]
    assert bc["riyad1956-p019-b10"] in ids and bc["riyad1956-p019-b07"] in ids
    assert bc["riyad1956-p020-b03"] not in ids  # different printed page


def test_glossary_translation_comes_from_the_dictionary():
    from api.answer import glossary_request

    assert glossary_request("ترجم كلمة التوحيد إلى الإنجليزية") == (
        "التوحيد",
        "Tawhid / Oneness of God",
    )
    assert glossary_request("ما معنى التوحيد؟") is None  # not a translation request


def test_editor_commentary_attached_to_the_hadith_it_explains():
    import sqlite3

    con = sqlite3.connect("data/asool.db")
    on = dict(con.execute("SELECT id, commentary_on FROM chunks WHERE kind='editor_commentary'"))
    from api.question_review import _block_chunk

    bc = _block_chunk()
    # p.29: Ka'b ibn Malik, not the next hadith; p.41: Umm Sulaym, not Sulayman ibn Surad
    assert on[bc["riyad1956-p029-b11"]] == bc["riyad1956-p029-b04"]
    assert on[bc["riyad1956-p041-b15"]] == bc["riyad1956-p041-b02"]


def test_no_unit_starts_mid_sentence_across_pages():
    import json
    import sqlite3

    con = sqlite3.connect("data/asool.db")
    for (bids,) in con.execute("SELECT block_ids FROM chunks"):
        first = json.loads(bids)[0]
        (cont,) = con.execute(
            "SELECT continues_from_prev FROM blocks WHERE id=?", (first,)
        ).fetchone()
        assert not cont, first
