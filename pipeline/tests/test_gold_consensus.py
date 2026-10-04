from eval.extraction_eval import cer_wer, footnote_links, prf
from pipeline.gold_consensus import _key, _map, gold_text


def test_map_equal_and_replace():
    m = _map(["a", "b", "c"], ["a", "x", "c"])
    assert m == {0: (0, 1), 1: (1, 2), 2: (2, 3)}


def test_map_unequal_span():
    m = _map(["a", "b", "c", "d"], ["a", "bc", "d"])
    assert m[0] == (0, 1) and m[3] == (2, 3)
    assert m[1] == m[2] == (1, 2)


def test_key_ignores_diacritics_keeps_punctuation():
    assert _key("الحَمْدُ") == _key("الحمد")
    assert _key("«") == "«"


def _draft():
    return {
        "blocks": [
            {
                "order": 1,
                "type": "body",
                "author_role": "matn",
                "footnote_marker": "",
                "type_confirmed": None,
            },
            {
                "order": 2,
                "type": "footnote",
                "author_role": "editor",
                "footnote_marker": "(١)",
                "type_confirmed": "footnote",
            },
        ],
        "tokens": [
            {"block": 0, "raw": "قال"},
            {"block": 0, "raw": "رسولُ"},
            {"block": 0, "raw": "الله"},
            {"block": 1, "raw": "(١)"},
            {"block": 1, "raw": "المدينه"},
        ],
        "review_items": [
            {"tok_from": 1, "tok_to": 2, "decision": "رسولُ", "id": "r0"},
            {"tok_from": 4, "tok_to": 5, "decision": "المدينة", "id": "r1"},
        ],
        "spotcheck": [{"tok": 0, "verdict": "ok", "fix": None}],
    }


def test_gold_text_applies_decisions():
    blocks = gold_text(_draft())
    assert blocks[0]["text"] == "قال رسولُ الله"
    assert blocks[1]["text"] == "(١) المدينة"


def test_gold_text_refuses_unreviewed():
    d = _draft()
    d["review_items"][0]["decision"] = None
    try:
        gold_text(d)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_cer_strict_vs_loose():
    r = cer_wer("الحَمْدُ لله", "الحمد لله", "strict")
    assert r["cer"] > 0
    assert cer_wer("الحَمْدُ لله", "الحمد لله", "loose")["cer"] == 0


def test_footnote_links_and_prf():
    blocks = [
        {"type": "body", "text": "قال (١) ثم (٢)"},
        {"type": "footnote", "footnote_marker": "(١)", "text": "(١) المدينة المنورة"},
        {"type": "footnote", "footnote_marker": "(2)", "text": "(2) من ألم"},
    ]
    links = footnote_links(blocks)
    assert {m for m, _ in links} == {"1", "2"}
    assert prf(links, links)["f1"] == 1.0
