"""Precompute answers for demo questions so the judges get instant, stable answers
(CLAUDE.md §12.F4). Answers are stored in data/answers/ (committed) and served from there.

All evaluation questions are precomputed by `eval.run_eval answers` (run 0). This adds the
questions the interface itself suggests (home page examples, Compare default) and the video
script questions. Already cached questions cost nothing.

Usage: uv run python -m eval.precompute
"""

from __future__ import annotations

from api.answer import _cached, answer

DEMO = [
    # home page example questions (web/src/components/SearchBox.tsx)
    "ما فضل الصبر عند المصيبة؟",
    "ما معنى «إنما الأعمال بالنيات»؟",
    "هل يقبل الله التوبة في آخر العمر؟",
    "ما المقصود بالإخلاص في العمل؟",
    # Compare page default question
    "ما شروط التوبة؟",
    # video script (CLAUDE.md §9.1)
    "ما حكم صيام يوم عرفة لغير الحاج؟",
    "حلفت بالطلاق على زوجتي إن خرجت من البيت ثم خرجت، فهل وقع الطلاق؟",
    "قال الله تعالى ﴿إن الله يحب الصابرين﴾، فما معنى هذه الآية؟",
    "What does tawbah mean and what are its conditions?",
]


def main() -> None:
    for q in DEMO:
        had = _cached(q) is not None
        r = answer(q, offline_run=0)
        print("cached" if had else "new   ", r["status"], q)


if __name__ == "__main__":
    main()
