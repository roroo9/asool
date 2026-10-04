import pytest

from pipeline.normalize import normalize, normalize_marker, strip_diacritics


def test_strips_tashkeel_and_tatweel():
    assert strip_diacritics("إِنَّمَا الأعْمَالُ") == "إنما الأعمال"
    assert normalize("الحـــمد") == "الحمد"


def test_unifies_letter_forms():
    assert normalize("أإآٱ") == "اااا"
    assert normalize("مصطفى") == "مصطفي"
    assert normalize("رحمة") == "رحمه"
    assert normalize("مؤمن") == "مومن"
    assert normalize("رئيس") == "رييس"


def test_digits_and_punctuation():
    assert normalize("صفحة ١٢") == "صفحه 12"
    assert normalize("﴿ وَمَا أُمِرُوا ﴾ «الأعمال» (١)") == "وما امروا الاعمال 1"


def test_quranic_marks_removed():
    # small high meem / waqf signs U+06D6..U+06ED
    assert normalize("الْحَمْدُ ۛ لِلَّهِ ۚ") == "الحمد لله"
    assert normalize("وَٱلصَّٰبِرِينَ", "quran") == "والصبرين"


def test_whitespace_collapse_and_empty():
    assert normalize("  قال \n\t  تعالى  ") == "قال تعالي"
    assert normalize("") == ""


def test_cer_loose_keeps_punctuation():
    assert normalize("قالَ: «نعم»", "cer_loose") == "قال: «نعم»"


def test_raw_text_is_not_mutated():
    raw = "إِنَّمَا"
    normalize(raw)
    assert raw == "إِنَّمَا"


def test_unknown_level():
    with pytest.raises(ValueError):
        normalize("x", "bogus")


@pytest.mark.parametrize(
    "marker,expected",
    [
        ("(١)", "1"),
        ("( 12 )", "12"),
        ("¹", "1"),
        ("(٣)", "3"),
        ("*", "*"),
        ("", None),
        ("()", None),
    ],
)
def test_normalize_marker(marker, expected):
    assert normalize_marker(marker) == expected
