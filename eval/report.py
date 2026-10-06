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


def gold_stats() -> dict:
    """Gold-set review numbers, computed from the review files (data/gold/draft)."""
    from pipeline.config import BAKEOFF_PAGES
    from pipeline.gold_consensus import DRAFT

    out = {
        "pages": 0,
        "finalized": 0,
        "words": 0,
        "auto_accepted": 0,
        "human_decisions": 0,
        "typed_corrections": 0,
        "auto_equivalent": 0,
        "reviewers": [],
        "spotcheck": {},
    }
    reviewers: set[str] = set()
    for f in sorted(DRAFT.glob("*.json")):
        d = json.loads(f.read_text())
        out["pages"] += 1
        out["finalized"] += (DRAFT.parent / f"{d['page_id']}.json").exists()
        out["words"] += d["total_tokens"]
        out["auto_accepted"] += d["auto_accepted"]
        for it in d["review_items"]:
            if it.get("auto_equivalence"):
                out["auto_equivalent"] += 1
                continue
            out["human_decisions"] += 1
            if it["decision"] not in [c["text"] for c in it["candidates"]]:
                out["typed_corrections"] += 1
            if it.get("reviewer"):
                reviewers.add(it["reviewer"])
        for s in d["spotcheck"]:
            kind = s.get("kind") or "agree"
            k = out["spotcheck"].setdefault(kind, {"checked": 0, "wrong": 0})
            k["checked"] += 1
            k["wrong"] += s["verdict"] == "wrong"
    out["reviewers"] = sorted(reviewers)
    out["bakeoff_pages"] = BAKEOFF_PAGES
    return out


def review_counts() -> dict:
    from api.question_review import REVIEWS, _drafts

    reviews = json.loads(REVIEWS.read_text(encoding="utf-8")) if REVIEWS.exists() else {}
    drafts = _drafts()
    acts = [reviews[q["id"]]["action"] for q in drafts if q["id"] in reviews]
    return {
        "drafted_by": "AI agent",
        "reviewer": sorted({r["reviewer"] for r in reviews.values()}),
        "total": len(drafts),
        "reviewed": len(acts),
        "approved": acts.count("approve"),
        "edited": acts.count("edit"),
        "removed": acts.count("remove"),
        "with_notes": sum(1 for r in reviews.values() if r.get("note")),
    }


def _retrieval_metrics(rows: list[dict]) -> dict:
    m: dict[str, dict] = {}
    if not rows:
        return m
    for key, label in (
        ("recall_at_5", "الاسترجاع: الصفحة الصحيحة ضمن أول ٥ نتائج (Recall@5)"),
        ("mrr", "الاسترجاع: ترتيب أول نتيجة صحيحة (MRR)"),
    ):
        m[label] = {
            "asool": _mean([float(r["asool"][key]) for r in rows]),
            "baseline": _mean([float(r["baseline"][key]) for r in rows]),
            "n": len(rows),
        } | ({"fmt": "decimal"} if key == "mrr" else {})
    fn = [r for r in rows if "context_complete" in r["asool"]]
    if fn:
        m["اكتمال السياق: الحاشية المطلوبة تصل مع النص"] = {
            "asool": _ratio([r["asool"]["context_complete"] for r in fn]),
            "baseline": _ratio([r["baseline"]["context_complete"] for r in fn]),
            "n": len(fn),
        }
    return m


def _answer_metrics(runs: dict, qs: dict, include) -> tuple[dict, list[dict]]:
    m: dict[str, dict] = {}
    run0 = {i: s for i, s in runs.get("0", {}).items() if i in qs and include(qs[i])}

    def rows(pred) -> list[dict]:
        return [s for i, s in run0.items() if pred(qs[i])]

    def add(label: str, rs: list[dict], key: str = "pass") -> None:
        vals = [bool(r.get(key)) for r in rs if key in r]
        if vals:
            m[label] = {"asool": _ratio(vals), "n": len(vals)}

    add("السلوك الصحيح مع كل المتطلبات (كل الأسئلة)", rows(lambda q: True))
    add(
        "الإجابة عن الأسئلة التي في المدونة",
        rows(lambda q: q["source"] != "official_package" and q["expected_behavior"] == "answer"),
    )
    add(
        "الإجابة تستشهد بالمقطع الصحيح",
        rows(lambda q: q["expected_behavior"] == "answer"),
        "cites_gold",
    )
    add("الامتناع حين لا يوجد مصدر كافٍ", rows(lambda q: q["expected_behavior"] == "abstain"))
    add("الإحالة في الحالات الشخصية (المستوى د)", rows(lambda q: q["expected_behavior"] == "refer"))
    add("تصحيح الآيات المحرفة في السؤال", rows(lambda q: q["expected_behavior"] == "correct_verse"))
    add(
        "الأسئلة متعددة الشروط: الاستشهاد بكل الأدلة",
        rows(lambda q: bool(q.get("required_chunk_ids"))),
    )
    req = [s for i, s in run0.items() if qs[i].get("requirements")]
    if req:
        m["متطلبات المراجِعة (حواشٍ وآيات واقتباسات ومصادر معتمدة)"] = {
            "asool": _ratio([not s.get("requirements_failed") for s in req]),
            "n": len(req),
        }
    shown = sum(s["quotes_shown"] for s in run0.values())
    if shown:
        fab = sum(s["fabricated_quotes"] for s in run0.values())
        book = sum(s.get("book_quotes", s["quotes_shown"]) for s in run0.values())
        ext = sum(s.get("external_quotes", 0) for s in run0.values())
        traced = sum(s["quotes_traced"] for s in run0.values())
        m["الاقتباسات المعروضة المتحقق منها حرفيًا"] = {
            "asool": 1 - fab / shown,
            "n": shown,
            "note": f"اقتباسات مختلقة معروضة: {fab}؛ من الكتاب {book}، "
            f"ومن مصادر معتمدة خارجه {ext}",
        }
        if book:
            m["إمكانية التتبع: اقتباس من الكتاب مرتبط بصفحة وموضع على الصورة"] = {
                "asool": traced / book,
                "n": book,
            }
    if len(runs) > 1:
        same, per_run = [], []
        for qid in run0:
            behs = [runs[r][qid]["behaviour"] for r in runs if qid in runs[r]]
            if len(behs) > 1:
                same.append(len(set(behs)) == 1)
        for r in sorted(runs):
            vals = [s["pass"] for i, s in runs[r].items() if i in run0]
            if vals:
                per_run.append(sum(vals) / len(vals))
        if same:
            m["ثبات السلوك عبر التشغيلات المتكررة"] = {
                "asool": _ratio(same),
                "n": len(same),
                "note": "نسبة النجاح لكل تشغيل: " + "، ".join(f"{p:.0%}" for p in per_run),
            }
    failures = [
        {
            "id": i,
            "question": qs[i]["question"],
            "behaviour": BEH_AR.get(s["behaviour"], s["behaviour"]),
            "requirements_failed": s.get("requirements_failed") or [],
        }
        for i, s in run0.items()
        if not s["pass"]
    ]
    return m, failures


def _postfix() -> dict | None:
    p = RESULTS / "postfix_classifier_v3.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = d["results"]
    return {
        "note": d["note"],
        "passed": sum(1 for s in rows.values() if s["pass"]),
        "total": len(rows),
        "failed": sorted(k for k, s in rows.items() if not s["pass"]),
        "fabricated_quotes": sum(s.get("fabricated_quotes", 0) for s in rows.values()),
    }


def build() -> dict:
    qs = {q["id"]: q for q in load_questions()}
    human = lambda q: q["source"] != "agent_natural"  # noqa: E731
    natural = lambda q: q["source"] == "agent_natural"  # noqa: E731
    metrics: dict[str, dict] = {}
    rc = review_counts()
    limits = [
        "مدونة صغيرة: ٣٠ صفحة من كتاب واحد (رياض الصالحين، طبعة ١٩٥٦).",
        f"أسئلة التقييم ({rc['total']}) صاغها الوكيل الآلي وراجعتها مراجِعة بشرية: اعتُمد "
        f"{rc['approved']} وعُدِّل {rc['edited']} وحُذف {rc['removed']}.",
        "أسئلة «الصياغة الطبيعية» صاغها الوكيل الآلي ولم تُراجَع بشريًا، ونتائجها معروضة منفصلة.",
        "الاسترجاع يُقاس بالسؤال الخام للطريقتين، دون إعادة صياغة السؤال بالنموذج.",
        "السلوك ومتطلبات المراجِعة تُحكم آليًا؛ جودة الأسلوب واللطف تحتاج قراءة بشرية.",
    ]
    rp = RESULTS / "retrieval.json"
    rrows = json.loads(rp.read_text())["questions"] if rp.exists() else []
    metrics |= _retrieval_metrics([r for r in rrows if r.get("source") != "agent_natural"])
    official, failures, nat = [], [], None
    ap = RESULTS / "answers.json"
    if ap.exists():
        runs = json.loads(ap.read_text())["runs"]
        am, failures = _answer_metrics(runs, qs, human)
        metrics |= am
        for qid, s in runs.get("0", {}).items():
            q = qs.get(qid)
            if q and q["source"] == "official_package":
                official.append(
                    {
                        "id": qid,
                        "no": q["official_no"],
                        "question": q["question"],
                        "package_case": q.get("package_case"),
                        "expected": q["expected_ar"],
                        "status": BEH_AR.get(s["behaviour"], s["behaviour"]),
                        "pass": s["pass"],
                        "requirements_failed": s.get("requirements_failed") or [],
                        "note": q.get("notes"),
                    }
                )
        official.sort(key=lambda c: c["no"])
        nm, nf = _answer_metrics(runs, qs, natural)
        nat = {
            "label": "drafted by the AI agent, not human-reviewed",
            "label_ar": "صاغها الوكيل الآلي، ولم تُراجَع بشريًا",
            "questions": sum(1 for q in qs.values() if natural(q)),
            "metrics": _retrieval_metrics([r for r in rrows if r.get("source") == "agent_natural"])
            | nm,
            "failures": nf,
        }

    heldout = None
    hp = RESULTS / "heldout.json"
    if hp.exists():
        h = json.loads(hp.read_text())
        for key, label in (
            ("cer_strict", "الاستخراج: خطأ الحروف مع التشكيل، ١٢ صفحة محجوزة (الأقل أفضل)"),
            ("cer_loose", "الاستخراج: خطأ الحروف دون التشكيل، ١٢ صفحة محجوزة (الأقل أفضل)"),
            ("footnote_f1", "الاستخراج: ربط الحواشي بعلاماتها، ١٢ صفحة محجوزة (F1)"),
        ):
            if key in h.get("asool", {}):
                metrics[label] = {
                    "asool": h["asool"][key],
                    "baseline": h.get("baseline", {}).get(key),
                    "n": h["pages"],
                }
        heldout = {
            "pages": h["pages"],
            "rows": [
                {
                    "system": v["label"],
                    "as_output_strict": v["as_output"]["cer_strict"],
                    "as_output_loose": v["as_output"]["cer_loose"],
                    "normalized_strict": v["layout_normalized"]["cer_strict"],
                    "normalized_loose": v["layout_normalized"]["cer_loose"],
                    "footnotes_in_order": v.get("footnotes_in_reading_order"),
                    "bakeoff_normalized_strict": (v.get("bakeoff_layout_normalized") or {}).get(
                        "cer_strict"
                    ),
                }
                for v in h["systems"].values()
            ],
        }
    else:
        limits.append("قياس الاستخراج على ١٢ صفحة محجوزة ينتظر انتهاء مراجعة مجموعة المرجع.")

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "metrics": metrics,
        "official_cases": official,
        "failures": failures,
        "natural_phrasing": nat,
        "question_review": rc,
        "postfix": _postfix(),
        "heldout": heldout,
        "gold": gold_stats(),
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
