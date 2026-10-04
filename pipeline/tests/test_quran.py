"""The five cases required by CLAUDE.md §4.3.7."""

from pipeline.quran import find_unmarked, verify


def test_exact_verse():
    m = verify("وَمَا أُمِرُوا إِلَّا لِيَعْبُدُوا اللَّهَ مُخْلِصِينَ لَهُ الدِّينَ حُنَفَاءَ")
    assert m and (m.surah, m.ayah_start) == (98, 5)
    assert m.match_type == "exact"


def test_one_ocr_corrupted_letter_is_minor_variant():
    # ولنبلونكم -> ولنبلوتكم (one letter), rest of 2:155 intact
    m = verify("وَلَنَبْلُوَتَّكُمْ بِشَيْءٍ مِنَ الْخَوْفِ وَالْجُوعِ وَنَقْصٍ مِنَ الْأَمْوَالِ")
    assert m and (m.surah, m.ayah_start) == (2, 155)
    assert m.match_type == "minor_variant"
    assert m.diff_ops


def test_misquoted_verse_wrong_word_is_flagged():
    # 2:153 "إن الله مع الصابرين" misquoted as "إن الله يحب الصابرين"
    m = verify("يَا أَيُّهَا الَّذِينَ آمَنُوا اسْتَعِينُوا بِالصَّبْرِ وَالصَّلَاةِ إِنَّ اللَّهَ يحب الصَّابِرِينَ")
    assert m and (m.surah, m.ayah_start) == (2, 153)
    assert m.match_type == "mismatch"
    assert any("يحب" in op["printed"] for op in m.diff_ops)


def test_span_across_two_ayahs():
    # end of 3:200 is one ayah; use 2:155 end + 2:156 start
    m = verify("وَبَشِّرِ الصَّابِرِينَ الَّذِينَ إِذَا أَصَابَتْهُمْ مُصِيبَةٌ قَالُوا إِنَّا لِلَّهِ")
    assert m and m.surah == 2 and m.ayah_start == 155 and m.ayah_end == 156
    assert m.match_type == "exact"


def test_non_quran_sentence_with_common_words_does_not_match():
    text = "قال رسول الله صلى الله عليه وسلم إن الله يحب العبد التقي الغني الخفي"
    assert find_unmarked(text) == []


def test_misquote_lists_all_close_verses_owner_case():
    from pipeline.quran import candidates

    got = [(c.surah, c.ayah_start) for c in candidates("إن الله يحب الصابرين", top=4)]
    assert got[0] == (3, 146)  # «والله يحب الصابرين»: most information shared
    assert (2, 153) in got and (8, 46) in got  # «إن الله مع الصابرين»
