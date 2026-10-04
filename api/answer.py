"""Grounded answering (CLAUDE.md §4.8) with gates and a deterministic anti-hallucination check.

Pipeline: cache -> level classify -> (quoted verse check) -> level D referral -> retrieve ->
support gate -> generate -> quote verification -> response.

Guarantees:
  - Every quote shown is verified verbatim (after normalization) against the cited passage.
    A failed quote is removed with its point; if more than half are removed -> abstain.
  - Level D (personal ruling) never gets a generated ruling: referral + general passages.
  - Low retrieval support or the model saying "not supported" -> abstention + closest passages.
  - No model available (budget, outage) -> passages only, never an error page.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from api import budget
from api.llm import generate
from api.passages import passage
from api.search import embed_query, hybrid
from api.settings import ROOT, settings
from pipeline import quran
from pipeline.normalize import normalize

PROMPTS = Path(__file__).parent / "prompts"
CACHE = ROOT / "data" / "answers"  # committed: precomputed answers survive redeploys
CLASSIFY_V = "level_classify.v1"
ANSWER_V = "answer.v2"
GLOSSARY = json.loads((ROOT / "data" / "reference" / "glossary.json").read_text())["terms"]

ABSTAIN_AR = "لم أجد في المصادر المتاحة ما يكفي للإجابة عن هذا السؤال."
ABSTAIN_EN = "I could not find enough in the available sources to answer this question."
NO_EVIDENCE_AR = (
    "لم أجد في المصادر المتاحة حديثًا أو نصًا يدل على ذلك. ولا يصح أن يُنسب إلى النبي ﷺ "
    "كلام لم يثبت، فلن أُنشئ حديثًا أو أصوغه. هذه أقرب النصوص الموجودة في الكتاب."
)
NO_EVIDENCE_EN = (
    "I found no hadith or text in the available sources that states this. Words must not be "
    "attributed to the Prophet ﷺ without proof, so I will not compose one. Below are the closest "
    "passages in the book."
)
REFER_AR = (
    "سؤالك يتعلق بحالة شخصية تحتاج إلى فتوى، والفتوى تتطلب معرفة تفاصيل الواقعة وتقديرًا شرعيًا "
    "متخصصًا. هذه الأداة لا تُصدر أحكامًا على الحالات الشخصية. يُرجى سؤال عالم مؤهل أو جهة "
    "إفتاء رسمية في بلدك. وفيما يلي نصوص عامة ذات صلة من الكتاب للاطلاع فقط."
)
REFER_EN = (
    "Your question concerns a personal situation that needs a fatwa, which requires knowing the "
    "details and a qualified scholar's judgment. This tool does not issue rulings on personal "
    "cases. Please ask a qualified scholar or an official fatwa authority in your country. Below "
    "are general passages from the book, for reference only."
)
UNAVAILABLE_AR = "تعذّر توليد إجابة الآن، وهذه أقرب النصوص من الكتاب مع مواضعها في الصفحات الأصلية."

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "level": {"type": "string", "enum": ["A", "B", "C", "D"]},
        "is_personal_case": {"type": "boolean"},
        "is_hostile": {"type": "boolean"},
        "language": {"type": "string"},
        "quoted_verse": {"type": "string"},
        "asks_for_evidence_text": {"type": "boolean"},
        "search_query_ar": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": [
        "level",
        "is_personal_case",
        "is_hostile",
        "language",
        "quoted_verse",
        "asks_for_evidence_text",
        "search_query_ar",
        "reason",
    ],
    "additionalProperties": False,
}
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "source_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "passage": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["text", "passage", "quote"],
                "additionalProperties": False,
            },
        },
        "explanation": {"type": "string"},
        "disagreement_noted": {"type": "boolean"},
        "level": {"type": "string", "enum": ["A", "B", "C"]},
    },
    "required": ["supported", "source_points", "explanation", "disagreement_noted", "level"],
    "additionalProperties": False,
}


CACHE_VERSION = "5"  # bump when the answer pipeline changes, so stale answers are not served


def cache_key(question: str) -> str:
    raw = f"{CACHE_VERSION}|{ANSWER_V}|{normalize(question)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


_MARKERS = re.compile(r"\(\s*[\d٠-٩]{1,3}\s*\)|[¹²³⁴⁵⁶⁷⁸⁹⁰]+")


def _vnorm(s: str) -> str:
    """Normalization for quote verification: footnote markers are not words of the text."""
    return normalize(_MARKERS.sub(" ", s))


def _cached(question: str) -> dict | None:
    p = CACHE / f"{cache_key(question)}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _store(question: str, res: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{cache_key(question)}.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1)
    )


def classify(question: str, model: str) -> dict:
    r = generate(
        stage="classify",
        prompt_version=CLASSIFY_V,
        model=model,
        system=(PROMPTS / f"{CLASSIFY_V}.md").read_text(),
        user=question,
        schema=CLASSIFY_SCHEMA,
        effort="low",
        max_tokens=4000,
    )
    return json.loads(r.text)


def _ar_num(n: int) -> str:
    return str(n).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def _in_corpus(surah: int, ayah: int) -> list[int]:
    """Printed pages of our corpus where this ayah is quoted (empty = outside the corpus)."""
    import sqlite3

    con = sqlite3.connect(ROOT / "data" / "asool.db")
    rows = con.execute(
        "SELECT DISTINCT p.page_number_printed FROM quran_refs q JOIN blocks b ON b.id=q.block_id "
        "JOIN pages p ON p.id=b.page_id WHERE q.surah=? AND ? BETWEEN q.ayah_start AND q.ayah_end",
        (surah, ayah),
    ).fetchall()
    con.close()
    return [r[0] for r in rows]


def check_quoted_verse(question: str, quoted: str) -> dict | None:
    """Official test case 11. Any quoted verse is checked against the FULL King Fahd Mushaf
    text (not only our 30 pages). Exact -> confirmed. Not exact -> every close verse is shown
    (exact Mushaf text + surah:ayah), the correct wording is stated gently, and no single verse
    is chosen silently when several are close."""
    spans = [s for s in [quoted, *quran.bracketed_spans(question)] if s and len(s.split()) >= 3]
    for s in spans:
        m = quran.verify(s)
        if not m:
            continue
        exact = m.match_type == "exact"
        if exact:
            cands = [m]
            m.surah_name = next(  # type: ignore[attr-defined]
                a.surah_name
                for a in quran.load_index().ayahs
                if (a.surah, a.ayah) == (m.surah, m.ayah_start)
            )
        else:
            ranked = quran.candidates(s, top=6)
            if not ranked:
                continue
            best = ranked[0].overlap
            cands = [c for c in ranked if c.overlap >= max(0.6, best - 0.3)][:4] or ranked[:1]
        items = []
        for c in cands:
            pages = _in_corpus(c.surah, c.ayah_start)
            items.append(
                {
                    "surah": c.surah,
                    "surah_name": getattr(c, "surah_name", ""),
                    "ayah_start": c.ayah_start,
                    "ayah_end": c.ayah_end,
                    "canonical_text": c.canonical_text,
                    "similarity": c.similarity,
                    "diff_ops": c.diff_ops,
                    "quranpedia_url": c.quranpedia_url,
                    "in_corpus_pages": pages,
                }
            )
        if exact:
            note = "النص كما ورد في السؤال مطابق لنص المصحف."
        else:
            refs = "، و".join(
                f"﴿{i['canonical_text']}﴾ [{i['surah_name']}: {_ar_num(i['ayah_start'])}]"
                for i in items
            )
            several = len(items) > 1
            note = (
                f"النص كما ورد في السؤال «{s}» لا يطابق لفظ المصحف. "
                + ("وأقرب الآيات إليه: " if several else "وأقرب آية إليه: ")
                + refs
                + ". "
                + (
                    "ولا يمكن الجزم بأيّها المقصود، فيُرجى الرجوع إلى النص الصحيح وعدم البناء على "
                    "الصيغة الواردة في السؤال."
                    if several
                    else "يُرجى الرجوع إلى النص الصحيح وعدم البناء على الصيغة الواردة في السؤال."
                )
            )
            outside = [i for i in items if not i["in_corpus_pages"]]
            if outside:
                note += (
                    " ("
                    + "، ".join(f"{i['surah_name']}: {_ar_num(i['ayah_start'])}" for i in outside)
                    + ": ليست في صفحات الكتاب المفهرسة، ونصها منقول من مصحف مجمع الملك فهد.)"
                )
        return {
            "printed_in_question": s,
            "match_type": m.match_type,
            "exact": exact,
            "candidates": items,
            "reference_source": quran.reference_source(),
            "note_ar": note,
        }
    return None


def verify_quotes(
    points: list[dict], passages_by_tag: dict[str, dict]
) -> tuple[list[dict], list[dict]]:
    """Keep only points whose quote occurs verbatim (normalized) in the cited passage
    (its text or attached footnotes). Returns (kept, removed)."""
    kept, removed = [], []
    for pt in points:
        p = passages_by_tag.get(pt.get("passage", "").strip("[] "))
        q = _vnorm(pt.get("quote", ""))
        if not p or len(q.split()) < 2:
            removed.append(pt | {"why": "no passage" if not p else "quote too short"})
            continue
        hay = _vnorm(
            p["text"]
            + " "
            + " ".join(
                f["text"] + " " + " ".join(f.get("attached_text", [])) for f in p["footnotes"]
            )
        )
        if f" {q} " in f" {hay} ":
            kept.append(pt | {"verified": True, "passage_id": p["id"]})
        else:
            removed.append(pt | {"why": "quote not found verbatim in the cited passage"})
    return kept, removed


_TAG = re.compile(r"\[P(\d+)\]")


def _explanation_ok(expl: str, tags: set[str]) -> str:
    """Drop explanation sentences that cite a passage that was not provided."""
    out = []
    for s in re.split(r"(?<=[.!؟?])\s+", expl.strip()):
        cited = {f"P{n}" for n in _TAG.findall(s)}
        if cited and not cited <= tags:
            continue
        out.append(s)
    return " ".join(out)


def _passages_for(hits, terms) -> list[dict]:
    out = []
    for h in hits:
        p = passage(h.id, terms)
        if p:
            p["retrieval"] = {
                "rrf": round(h.score, 5),
                "bm25_rank": h.bm25_rank,
                "dense_rank": h.dense_rank,
                "dense_sim": h.dense_sim,
            }
            out.append(p)
    return out


def _context(passages: list[dict]) -> str:
    parts = []
    for i, p in enumerate(passages, 1):
        label = "[تعليق المحقق]" if p["kind"] == "editor_commentary" else "[متن الإمام النووي]"
        fn = " | ".join(
            f["text"] + " " + " ".join(f.get("attached_text", [])) for f in p["footnotes"]
        )
        pages = "، ".join(f"ص {x['printed']}" for x in p["pages"])
        parts.append(
            f"P{i} {label} ({' › '.join(p['breadcrumb'])}، {pages})\n{p['text']}"
            + (f"\n[حواشي المحقق] {fn}" if fn else "")
        )
    return "\n\n".join(parts)


def answer(question: str, *, ip: str = "local", use_cache: bool = True) -> dict:
    t0 = time.time()
    question = question.strip()[:1000]
    if use_cache and (c := _cached(question)):
        return c | {"cached": True}
    stages = []
    model = budget.answer_model()
    lang = "ar"
    try:
        cls = classify(question, settings.classifier_model) if model else None
    except Exception as e:  # classifier down: be conservative, still retrieve
        cls = None
        stages.append({"stage": "classify", "error": str(e)[:200]})
    if cls:
        lang = "ar" if cls["language"].startswith("ar") else cls["language"]
        stages.append({"stage": "classify", "level": cls["level"], "reason": cls["reason"]})
    verse = check_quoted_verse(question, cls["quoted_verse"] if cls else "")
    if verse:
        stages.append({"stage": "quoted_verse", "match_type": verse["match_type"]})

    qvec = embed_query(question if not cls else f"{question}\n{cls['search_query_ar']}")
    ret = hybrid(question, extra_query=cls["search_query_ar"] if cls else None, qvec=qvec, k=5)
    passages = _passages_for(ret["hits"], ret["terms"])
    stages.append({"stage": "retrieve", "n": len(passages), "dense": ret["dense_available"]})
    base = {
        "question": question,
        "language": lang,
        "level": cls["level"] if cls else None,
        "classification": cls,
        "quoted_verse_check": verse,
        "passages": passages,
        "ai_notice": "أداة بحث مدعومة بالذكاء الاصطناعي؛ النصوص المقتبسة منقولة حرفيًا من الكتاب "
        "ومتحقق منها، والتوضيح من توليد النموذج.",
        "cached": False,
    }

    def done(res: dict) -> dict:
        res["stages"] = stages
        res["seconds"] = round(time.time() - t0, 2)
        if res["status"] != "unavailable":
            _store(question, res)
        return res

    # Level D: referral, never a ruling.
    if cls and (cls["level"] == "D" or cls["is_personal_case"]):
        return done(
            base | {"status": "referral", "message": REFER_AR if lang == "ar" else REFER_EN}
        )
    if model is None or not budget.allow(ip):
        return base | {"status": "unavailable", "message": UNAVAILABLE_AR, "stages": stages}

    # Support gate: weak retrieval -> abstain without generating.
    best = max((p["retrieval"]["dense_sim"] or 0.0) for p in passages) if passages else 0.0
    stages.append(
        {"stage": "support_gate", "best_sim": round(best, 3), "threshold": settings.support_min_sim}
    )
    if not passages or (ret["dense_available"] and best < settings.support_min_sim):
        return done(
            base | {"status": "abstained", "message": ABSTAIN_AR if lang == "ar" else ABSTAIN_EN}
        )

    gloss = "; ".join(f"{k} = {v}" for k, v in GLOSSARY.items())
    system = (PROMPTS / f"{ANSWER_V}.md").read_text().replace("{glossary}", gloss)
    level = cls["level"] if cls and cls["level"] in "ABC" else "B"
    user = (
        f"language: {lang}\nlevel: {level}\n"
        + (
            "tone: the question is phrased with hostility; stay calm and respectful.\n"
            if cls and cls["is_hostile"]
            else ""
        )
        + (
            "verse_check: the quoted verse does NOT match the Mushaf. A verified correction card "
            "listing the closest verses is shown to the user separately: "
            + "; ".join(f"{c['surah']}:{c['ayah_start']}" for c in verse["candidates"])
            + ". In your explanation, gently say the quoted wording is not the Quranic text and "
            "refer to the verses shown; do NOT choose one of them as the intended verse, and do "
            "not build on the altered wording.\n"
            if verse and not verse["exact"]
            else ""
        )
        + f"question: {question}\n\nPASSAGES:\n{_context(passages)}"
    )
    gen = None
    for m in dict.fromkeys([model, settings.answer_fallback_model]):
        try:
            r = generate(
                stage="answer",
                prompt_version=ANSWER_V,
                model=m,
                system=system,
                user=user,
                schema=ANSWER_SCHEMA,
                effort="medium",
                max_tokens=12000,
            )
            gen = json.loads(r.text) | {"model": m}
            break
        except Exception as e:
            stages.append({"stage": "generate", "model": m, "error": str(e)[:200]})
    if gen is None:
        return base | {"status": "unavailable", "message": UNAVAILABLE_AR, "stages": stages}
    stages.append({"stage": "generate", "model": gen["model"], "supported": gen["supported"]})
    if not gen["supported"] or not gen["source_points"]:
        evidence = bool(cls and cls["asks_for_evidence_text"])
        if evidence:
            msg = NO_EVIDENCE_AR if lang == "ar" else NO_EVIDENCE_EN
        else:
            msg = ABSTAIN_AR if lang == "ar" else ABSTAIN_EN
        return done(
            base
            | {
                "status": "abstained",
                "model": gen["model"],
                "message": msg,
                "abstain_reason": "no_evidence_text" if evidence else "unsupported",
            }
        )

    by_tag = {f"P{i}": p for i, p in enumerate(passages, 1)}
    kept, removed = verify_quotes(gen["source_points"], by_tag)
    stages.append({"stage": "verify_quotes", "kept": len(kept), "removed": len(removed)})
    if not kept or len(removed) > len(gen["source_points"]) / 2:
        return done(
            base
            | {
                "status": "abstained",
                "model": gen["model"],
                "message": ABSTAIN_AR if lang == "ar" else ABSTAIN_EN,
                "verification": {
                    "total": len(gen["source_points"]),
                    "verified": len(kept),
                    "removed": removed,
                },
            }
        )
    cited = {k.get("passage", "").strip("[] ") for k in kept}
    return done(
        base
        | {
            "status": "answered",
            "model": gen["model"],
            "level": gen["level"],
            "answer": {
                "source_points": kept,
                "explanation": _explanation_ok(
                    gen["explanation"], set(by_tag) & (cited | set(by_tag))
                ),
                "disagreement_noted": gen["disagreement_noted"],
            },
            "verification": {
                "total": len(gen["source_points"]),
                "verified": len(kept),
                "removed": removed,
            },
        }
    )
