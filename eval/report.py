"""Build data/eval/results/summary.json (read by /eval/summary and the /proof page).

Every number is computed from the result files written by eval.run_eval (and, when the
gold review is finished, eval.heldout_eval). Nothing is typed by hand.
Usage: uv run python -m eval.report
"""

from __future__ import annotations

import json
import statistics as st
import time

from eval.run_eval import RESULTS, load_questions

BEH_AR = {
    "answer": "إجابة موثقة",
    "abstain": "امتناع مع أقرب النصوص",
    "refer": "إحالة إلى أهل العلم",
    "correct_verse": "تصحيح نص الآية",
    "unavailable": "تعذّر التوليد",
    "error": "خطأ",
}


def _mean(xs: list[float]) -> float | None:
    return st.mean(xs) if xs else None


def _ratio(xs: list[bool]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def build() -> dict:
    qs = {q["id"]: q for q in load_questions()}
    metrics: dict[str, dict] = {}
    limits = [
        "مدونة صغيرة: ٣٠ صفحة من كتاب واحد (رياض الصالحين، طبعة ١٩٥٦).",
        "أسئلة التقييم صاغها الوكيل وتنتظر مراجعة بشرية (human_verified=false) إلا ما ذُكر.",
        "الاسترجاع يُقاس بالسؤال الخام للطريقتين، دون إعادة صياغة السؤال بالنموذج.",
        "السلوك المتوقع يُحكم آليًا (إجابة/امتناع/إحالة/تصحيح آية)؛ جودة الأسلوب تحتاج مراجعة بشرية.",
    ]

    rp = RESULTS / "retrieval.json"
    if rp.exists():
        rows = json.loads(rp.read_text())["questions"]
        n = len(rows)
        for key, label in (
            ("recall_at_5", "الاسترجاع: الصفحة الصحيحة ضمن أول ٥ نتائج (Recall@5)"),
            ("mrr", "الاسترجاع: ترتيب أول نتيجة صحيحة (MRR)"),
        ):
            metrics[label] = {
                "asool": _mean([float(r["asool"][key]) for r in rows]),
                "baseline": _mean([float(r["baseline"][key]) for r in rows]),
                "n": n,
            } | ({"fmt": "decimal"} if key == "mrr" else {})
        fn = [r for r in rows if r["needs_footnote"]]
        if fn:
            metrics["اكتمال السياق: الحاشية المطلوبة تصل مع النص"] = {
                "asool": _ratio([r["asool"]["context_complete"] for r in fn]),
                "baseline": _ratio([r["baseline"]["context_complete"] for r in fn]),
                "n": len(fn),
            }

    official = []
    ap = RESULTS / "answers.json"
    if ap.exists():
        runs = json.loads(ap.read_text())["runs"]
        run0 = runs.get("0", {})

        def per_type(pred) -> list[dict]:
            return [s | {"q": qs[i]} for i, s in run0.items() if i in qs and pred(qs[i])]

        def add(label: str, rows: list[dict], key: str = "pass") -> None:
            vals = [bool(r.get(key)) for r in rows if key in r]
            if vals:
                metrics[label] = {"asool": _ratio(vals), "n": len(vals)}

        add("السلوك الصحيح في كل الأسئلة", per_type(lambda q: True))
        add(
            "الإجابة عن الأسئلة التي في المدونة",
            per_type(
                lambda q: q["source"] != "official_package" and q["expected_behavior"] == "answer"
            ),
        )
        add(
            "الإجابة تستشهد بالمقطع الصحيح",
            per_type(lambda q: q["expected_behavior"] == "answer"),
            "cites_gold",
        )
        add("الامتناع حين لا يوجد مصدر كافٍ", per_type(lambda q: q["type"] == "unanswerable"))
        add(
            "الإحالة في الحالات الشخصية (المستوى د)",
            per_type(lambda q: q["type"] == "personal_case"),
        )
        add("تصحيح الآيات المحرفة في السؤال", per_type(lambda q: q["type"] == "misquoted_verse"))
        add(
            "الأسئلة متعددة الشروط: الاستشهاد بكل الأدلة",
            per_type(lambda q: bool(q.get("required_chunk_ids"))),
        )
        shown = sum(s["quotes_shown"] for s in run0.values())
        if shown:
            fab = sum(s["fabricated_quotes"] for s in run0.values())
            traced = sum(s["quotes_traced"] for s in run0.values())
            metrics["الاقتباسات المعروضة المتحقق منها حرفيًا"] = {
                "asool": 1 - fab / shown,
                "n": shown,
                "note": f"اقتباسات مختلقة معروضة: {fab}",
            }
            metrics["إمكانية التتبع: اقتباس مرتبط بصفحة وموضع على الصورة"] = {
                "asool": traced / shown,
                "n": shown,
            }
        if len(runs) > 1:
            same = []
            for qid in run0:
                behs = [runs[r][qid]["behaviour"] for r in runs if qid in runs[r]]
                if len(behs) > 1:
                    same.append(len(set(behs)) == 1)
            passes = [
                _ratio([s["pass"] for s in runs[r].values()]) for r in sorted(runs) if runs[r]
            ]
            metrics["ثبات السلوك عبر التشغيلات المتكررة"] = {
                "asool": _ratio(same),
                "n": len(same),
                "note": f"نسبة النجاح لكل تشغيل: {', '.join(f'{p:.0%}' for p in passes)}",
            }
        for qid, s in run0.items():
            q = qs.get(qid)
            if q and q["source"] == "official_package":
                official.append(
                    {
                        "id": qid,
                        "no": q["official_no"],
                        "question": q["question"],
                        "expected": q["expected_ar"],
                        "status": BEH_AR.get(s["behaviour"], s["behaviour"]),
                        "pass": s["pass"],
                        "note": q.get("notes"),
                    }
                )
        official.sort(key=lambda c: c["no"])

    hp = RESULTS / "heldout.json"
    if hp.exists():
        h = json.loads(hp.read_text())
        for key, label in (
            ("cer_strict", "خطأ الحروف مع التشكيل على الصفحات المحجوزة (الأقل أفضل)"),
            ("footnote_f1", "ربط الحواشي على الصفحات المحجوزة (F1)"),
        ):
            if key in h.get("asool", {}):
                metrics[label] = {
                    "asool": h["asool"][key],
                    "baseline": h.get("baseline", {}).get(key),
                    "n": h["pages"],
                }
    else:
        limits.append("قياس الاستخراج على ١٢ صفحة محجوزة ينتظر انتهاء مراجعة مجموعة المرجع.")

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "metrics": metrics,
        "official_cases": official,
        "limits": limits,
        "command": "uv run python -m eval.run_eval retrieval && "
        "uv run python -m eval.run_eval answers --runs 3 && uv run python -m eval.report",
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    return summary


if __name__ == "__main__":
    s = build()
    for k, v in s["metrics"].items():
        print(f"{k}: {v}")
    for c in s["official_cases"]:
        print("✓" if c["pass"] else "✗", c["no"], c["status"])
