from pipeline.footnotes import footnote_marker, link_page
from pipeline.hadith import classify_takhrij, dorar_search_url, units


def _b(i, typ, text, marker="", role="matn", cont=False):
    return {
        "id": f"b{i}",
        "type": typ,
        "text": text,
        "footnote_marker": marker,
        "author_role": role,
        "continues_from_prev": cont,
    }


def test_exact_links_and_offsets():
    blocks = [
        _b(1, "body", "قال (١) ثم قال (٢)"),
        _b(2, "footnote", "(١) المدينة", "(١)", "editor"),
        _b(3, "footnote", "(٢) من ألم", "(٢)", "editor"),
    ]
    links, flags = link_page(blocks, "p1")
    assert {(ln["marker"], ln["footnote_block_id"], ln["method"]) for ln in links} == {
        ("(١)", "b2", "marker_exact"),
        ("(٢)", "b3", "marker_exact"),
    }
    assert links[0]["anchor_char_offset"] == blocks[0]["text"].index("(١)")
    assert flags == []


def test_split_footnote_groups_like_page_41():
    # (1)-(2) before the editor's commentary, (3) after it: all must link.
    blocks = [
        _b(1, "body", "أ (١) ب (٢) ج (٣)"),
        _b(2, "footnote", "(١) x", "(١)", "editor"),
        _b(3, "footnote", "(٢) y", "(٢)", "editor"),
        _b(4, "editor_commentary", "ما نأخذه من هذا الحديث ...", role="editor"),
        _b(5, "footnote", "(٣) z", "(٣)", "editor"),
    ]
    links, _ = link_page(blocks, "p41")
    assert sorted(ln["footnote_block_id"] for ln in links) == ["b2", "b3", "b5"]


def test_ordinal_fallback_is_flagged():
    blocks = [_b(1, "body", "نص (٤)"), _b(2, "footnote", "(5) شرح", "(5)", "editor")]
    links, flags = link_page(blocks, "p")
    assert links[0]["method"] == "marker_fuzzy" and links[0]["confidence"] == 0.6
    assert any("by order" in f["reason"] for f in flags)


def test_continuation_from_previous_page():
    blocks = [_b(1, "footnote", "تتمة الشرح من الصفحة السابقة", "", "editor", cont=True)]
    links, flags = link_page(blocks, "p")
    assert links[0]["method"] == "continuation"
    assert flags


def test_marker_parsing():
    assert footnote_marker({"footnote_marker": "", "text": "(١٢) كلام"}) == "12"


def test_takhrij_classification():
    assert classify_takhrij("متفق عليه") == "in_sahihayn"
    assert classify_takhrij("رواه مسلم") == "in_sahihayn"
    assert classify_takhrij("رواه البخارى") == "in_sahihayn"
    assert classify_takhrij("رواه إماما المحدثين") == "in_sahihayn"
    assert classify_takhrij("رواه الترمذى وقال حديث حسن") == "other"
    assert classify_takhrij(None) == "unknown"


def test_hadith_units_and_unverified_default():
    blocks = [
        _b(1, "heading", "باب الصبر"),
        _b(2, "body", "وعن أبى هريرة رضى الله عنه قال : قال رسول الله صلى الله عليه وسلم :"),
        _b(3, "hadith", "« ليس الشديد بالصرعة »"),
        _b(4, "body", "رواه الترمذى وقال : حديث حسن ."),
        _b(5, "body", "وعن أنس قال : قال رسول الله صلى الله عليه وسلم :"),
        _b(6, "hadith", "« إنما الصبر عند الصدمة الأولى »"),
        _b(7, "body", "متفق عليه ."),
    ]
    us = units(blocks)
    assert [u["takhrij_kind"] for u in us] == ["other", "in_sahihayn"]
    assert us[0]["grading_status"] in ("unverified", "verified")
    assert us[1]["grading_status"] == "in_sahihayn"
    assert us[0]["dorar_search_url"].startswith("https://dorar.net/hadith/search?q=")


def test_dorar_url_is_normalized_words():
    assert "%D9%84%D9%8A%D8%B3" in dorar_search_url("«لَيْسَ الشديد»")
