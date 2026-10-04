"""Quote verification and level-D routing (CLAUDE.md §6 Phase 3 tests). No network: the LLM,
embeddings and retrieval are replaced with fakes."""

import json

import pytest

from api import answer as A
from api.answer import _explanation_ok, verify_quotes

PASSAGE = {
    "id": "c1",
    "kind": "matn",
    "text": "قال العلماء : التوبةُ(١) واجبةٌ منْ كلِّ ذنبٍ ، أحدها أنْ يُقلعَ (٢) عن المعصيةِ",
    "footnotes": [{"text": "(١) الرجوع إلى الله", "attached_text": []}],
    "pages": [{"printed": 18}],
    "breadcrumb": ["رياض الصالحين", "باب التوبة"],
}


def test_verbatim_quote_kept_despite_markers_and_tashkeel():
    pts = [{"text": "x", "passage": "P1", "quote": "أن يقلع عن المعصية"}]
    kept, removed = verify_quotes(pts, {"P1": PASSAGE})
    assert len(kept) == 1 and not removed


def test_altered_quote_removed():
    pts = [{"text": "x", "passage": "P1", "quote": "أن يترك المعصية فورا"}]
    kept, removed = verify_quotes(pts, {"P1": PASSAGE})
    assert not kept and removed[0]["why"].startswith("quote not found")


def test_quote_cited_to_wrong_passage_removed():
    other = PASSAGE | {"id": "c2", "text": "باب الصبر", "footnotes": []}
    pts = [{"text": "x", "passage": "P2", "quote": "أن يقلع عن المعصية"}]
    kept, removed = verify_quotes(pts, {"P1": PASSAGE, "P2": other})
    assert not kept


def test_quote_from_footnote_allowed():
    pts = [{"text": "x", "passage": "P1", "quote": "الرجوع إلى الله"}]
    kept, _ = verify_quotes(pts, {"P1": PASSAGE})
    assert kept


def test_explanation_drops_sentences_citing_unknown_passages():
    out = _explanation_ok("التوبة واجبة [P1]. وقيل غير ذلك [P9].", {"P1"})
    assert "[P9]" not in out and "[P1]" in out


@pytest.fixture
def fake_pipeline(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "CACHE", tmp_path)
    monkeypatch.setattr(A, "embed_query", lambda q: None)

    class H:
        id, score, bm25_rank, dense_rank, dense_sim = "c1", 0.03, 1, None, None

    monkeypatch.setattr(
        A, "hybrid", lambda *a, **k: {"hits": [H()], "terms": [], "dense_available": False}
    )
    monkeypatch.setattr(A, "passage", lambda cid, terms=None: dict(PASSAGE))
    monkeypatch.setattr(A.budget, "answer_model", lambda: "openrouter:fake")
    monkeypatch.setattr(A.budget, "allow", lambda ip: True)
    calls = {"answer": 0}

    def fake_generate(**kw):
        class R:
            pass

        r = R()
        if kw["stage"] == "classify":
            personal = "يجوز لي" in kw["user"]
            r.text = json.dumps(
                {
                    "level": "D" if personal else "A",
                    "is_personal_case": personal,
                    "is_hostile": False,
                    "language": "ar",
                    "quoted_verse": "",
                    "asks_for_evidence_text": False,
                    "search_query_ar": "التوبة",
                    "reason": "t",
                }
            )
        else:
            calls["answer"] += 1
            r.text = json.dumps(
                {
                    "supported": True,
                    "disagreement_noted": False,
                    "level": "A",
                    "explanation": "التوبة واجبة [P1].",
                    "source_points": [
                        {"text": "الإقلاع شرط", "passage": "P1", "quote": "أن يقلع عن المعصية"}
                    ],
                }
            )
        return r

    monkeypatch.setattr(A, "generate", fake_generate)
    return calls


def test_level_d_gets_referral_and_no_generated_answer(fake_pipeline):
    res = A.answer("أنا في بلد كذا، هل يجوز لي تأخير المهر؟", use_cache=False)
    assert res["status"] == "referral"
    assert "answer" not in res
    assert fake_pipeline["answer"] == 0  # the answer model was never called


def test_normal_question_answered_with_verified_quote(fake_pipeline):
    res = A.answer("ما شروط التوبة؟", use_cache=False)
    assert res["status"] == "answered"
    assert res["verification"] == {"total": 1, "verified": 1, "removed": []}
