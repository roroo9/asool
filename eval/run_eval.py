"""Retrieval, context completeness, answer behaviour and safety on data/eval/questions.jsonl.

Asool vs. the baseline (Tesseract text, fixed 500-character pieces) with the SAME embeddings,
the SAME hybrid search code and the SAME k; only the data preparation differs (CLAUDE.md §5.1).
Retrieval uses the raw question for both systems (no classifier rewrite), so the comparison is
about the index, not the query.

Answers go through the real /answer pipeline in offline mode (api.answer.answer, offline_run):
run 0 also fills the precomputed answer cache that the live site serves; runs 1..n are fresh
repeated calls used for consistency (mean ± spread). Every LLM call is logged with its cost.

Usage:
  uv run python -m eval.run_eval retrieval            # free (embeddings are cached)
  uv run python -m eval.run_eval answers --runs 1     # ~$0.03 per question per run
  uv run python -m eval.run_eval answers --runs 3 --only official
Results: data/eval/results/{retrieval,answers}.json  ->  eval.report builds summary.json
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from pathlib import Path

from api.answer import _vnorm, answer, verify_quotes
from api.approved import verify_external
from api.passages import baseline_passage, passage
from api.question_review import reviewed_questions
from api.search import hybrid
from pipeline.normalize import normalize

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "eval" / "questions.jsonl"
RESULTS = ROOT / "data" / "eval" / "results"
DB = ROOT / "data" / "asool.db"
K = 5


REQUIREMENTS = ROOT / "data" / "eval" / "question_requirements.json"
NATURAL = ROOT / "data" / "eval" / "questions_natural.jsonl"


def _pages_of(blocks: list[str]) -> list[str]:
    return sorted({b.rsplit("-b", 1)[0] for b in blocks})


def load_questions(only: str | None = None, natural: bool = True) -> list[dict]:
    """The 66 human-reviewed questions (agent drafts + reviewer decisions + the reviewer's notes
    as structured requirements), then the agent-drafted natural-phrasing set (not reviewed)."""
    from api.question_review import resolve

    reqs = json.loads(REQUIREMENTS.read_text(encoding="utf-8")) if REQUIREMENTS.exists() else {}
    rows = []
    for q in reviewed_questions():
        r = reqs.get(q["id"])
        if r:
            r = dict(r)
            if "required_anchor_blocks" in r:
                q = resolve(q | {"required_anchor_blocks": r.pop("required_anchor_blocks")})
            q = q | {"requirements": r}
        rows.append(q)
    if natural and NATURAL.exists():
        for x in NATURAL.read_text(encoding="utf-8").splitlines():
            if x:
                q = resolve(json.loads(x))
                q.setdefault("gold_page_ids", _pages_of(q.get("gold_anchor_blocks", [])))
                rows.append(q)
    if only:
        rows = [r for r in rows if r["id"].startswith(only) or r["type"] == only]
    return rows


# ---------------------------------------------------------------- retrieval + context


def _unit_text(p: dict) -> str:
    """Everything a returned unit gives the reader: its text and its attached footnotes."""
    fns = " ".join(
        f["text"] + " " + " ".join(f.get("attached_text", [])) for f in p.get("footnotes", [])
    )
    return f"{p['text']} {fns}"


def _footnote_needs(q: dict) -> list[str]:
    """Footnote text(s) a question depends on (any one suffices)."""
    if q.get("footnote_must_contain"):
        return [normalize(q["footnote_must_contain"], "search")]
    req = q.get("requirements") or {}
    ids = req.get("footnotes_all") or req.get("footnotes_any") or []
    if not ids:
        return []
    con = sqlite3.connect(DB)
    out = []
    for b in ids:
        r = con.execute("SELECT text_raw FROM blocks WHERE id=?", (b,)).fetchone()
        if r:
            out.append(normalize(re.sub(r"^\s*\(\s*[\d٠-٩]+\s*\)", "", r[0]), "search"))
    con.close()
    return out


def retrieval() -> dict:
    out = []
    for q in load_questions():
        if not q.get("gold_page_ids") or q["expected_behavior"] not in ("answer",):
            continue
        row = {
            "id": q["id"],
            "type": q["type"],
            "source": q["source"],
            "needs_footnote": q["needs_footnote"],
        }
        for mode in ("asool", "baseline"):
            hits = hybrid(q["question"], mode=mode, k=K)["hits"]
            units = [passage(h.id) if mode == "asool" else baseline_passage(h.id) for h in hits]
            units = [u for u in units if u]
            gold = set(q["gold_page_ids"])
            rank = next(
                (i + 1 for i, u in enumerate(units) if gold & {p["id"] for p in u["pages"]}),
                None,
            )
            r = {"ids": [u["id"] for u in units], "first_gold_rank": rank}
            r["recall_at_5"] = rank is not None
            r["mrr"] = 1 / rank if rank else 0.0
            if mode == "asool" and q.get("gold_chunk_ids"):
                r["chunk_hit"] = bool(set(q["gold_chunk_ids"]) & set(r["ids"]))
            needs = _footnote_needs(q)
            if needs:
                # context complete = a top-5 unit from a gold page also carries the footnote
                r["context_complete"] = any(
                    gold & {p["id"] for p in u["pages"]}
                    and any(n in normalize(_unit_text(u), "search") for n in needs)
                    for u in units
                )
            row[mode] = r
        out.append(row)
    res = {"k": K, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "questions": out}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "retrieval.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


# ---------------------------------------------------------------- answers + safety


def _block_page(con: sqlite3.Connection, bid: str) -> str | None:
    r = con.execute("SELECT page_id FROM blocks WHERE id=?", (bid,)).fetchone()
    return r[0] if r else None


def _behaviour(res: dict) -> str:
    st = res.get("status")
    if st == "referral":
        return "refer"
    if st == "abstained":
        return "abstain"
    if st in ("answered", "glossary"):
        return "answer"
    return st or "error"


def _verse_ok(res: dict, expected: list[str]) -> bool:
    v = res.get("quoted_verse_check") or {}
    if not v or v.get("exact"):
        return False
    got = set()
    for c in v.get("candidates", []):
        for a in range(c["ayah_start"], c["ayah_end"] + 1):
            got.add(f"{c['surah']}:{a}")
    return all(e in got for e in expected)


def score(q: dict, res: dict, con: sqlite3.Connection) -> dict:
    beh = _behaviour(res)
    allowed = q.get("allowed_behaviors") or [q["expected_behavior"]]
    s: dict = {"behaviour": beh, "allowed": allowed}
    if q["expected_behavior"] == "correct_verse":
        s["verse_corrected"] = _verse_ok(res, q.get("expected_verses", []))
        s["pass"] = s["verse_corrected"]
    else:
        s["pass"] = beh in allowed
    ans = res.get("answer") or {}
    pts = ans.get("source_points", [])
    passages = res.get("passages", [])
    by_tag = {f"P{i}": p for i, p in enumerate(passages, 1)}
    # Re-verify every shown quote independently against ITS OWN source (book passage, or the
    # Mushaf/tafsir/terminology item it cites). A fabricated quote is one that is shown but is
    # not in that source (must be 0; the pipeline removes them before showing).
    items = (res.get("external") or {}).get("items", {})
    book = [pt for pt in pts if not pt.get("external")]
    ext = [pt for pt in pts if pt.get("external")]
    _, removed = verify_quotes(book, by_tag) if book else ([], [])
    ext_bad = [
        pt
        for pt in ext
        if not (pt["passage"] in items and verify_external(pt["quote"], items[pt["passage"]]))
    ]
    s["quotes_shown"] = len(pts)
    s["book_quotes"] = len(book)
    s["external_quotes"] = len(ext)
    s["fabricated_quotes"] = len(removed) + len(ext_bad)
    # Traceability (book quotes): each resolves to a stored block with a page and a box.
    traced = 0
    for pt in book:
        p = by_tag.get(pt["passage"])
        if not p:
            continue
        blocks = p.get("blocks", []) + p.get("footnotes", [])
        qn = _vnorm(pt["quote"])
        hit = [b for b in blocks if qn and qn in _vnorm(b["text"])]
        if not hit:  # quote spanning blocks: the blocks sharing >= 2 of its words
            words = set(qn.split())
            hit = [b for b in blocks if len(words & set(_vnorm(b["text"]).split())) >= 2]
        if hit and all(b.get("bbox") and _block_page(con, b["id"]) for b in hit):
            traced += 1
    s["quotes_traced"] = traced
    cited = {by_tag[pt["passage"]]["id"] for pt in pts if pt["passage"] in by_tag}
    s["cited_chunks"] = sorted(cited)
    if q.get("gold_chunk_ids") and res.get("status") == "answered":
        s["cites_gold"] = bool(cited & set(q["gold_chunk_ids"]))
    if q.get("required_chunk_ids") and beh == "answer":
        need = set(q["required_chunk_ids"])
        s["required_cited"] = len(need & cited) / len(need)
        s["pass"] = s["pass"] and need <= cited
    if q.get("must_contain_any") and beh == "answer":
        txt = json.dumps([ans, res.get("glossary")], ensure_ascii=False).lower()
        s["term_ok"] = any(t.lower() in txt for t in q["must_contain_any"])
        s["pass"] = s["pass"] and s["term_ok"]
    fails = _requirements(q.get("requirements") or {}, res, con)
    if q.get("requirements"):
        s["requirements_failed"] = fails
        s["pass"] = s["pass"] and not fails
    s["model"] = res.get("model")
    return s


def _shown_verses(res: dict) -> set[str]:
    """Verses the reader sees: the verse-check card, cited Mushaf items, and the verse badges
    next to quoted book text."""
    out: set[str] = set()
    for c in (res.get("quoted_verse_check") or {}).get("candidates", []):
        out |= {f"{c['surah']}:{a}" for a in range(c["ayah_start"], c["ayah_end"] + 1)}
    items = (res.get("external") or {}).get("items", {})
    pts = (res.get("answer") or {}).get("source_points", [])
    for pt in pts:
        it = items.get(pt.get("passage")) if pt.get("external") == "quran" else None
        if it:
            out.add(f"{it['surah']}:{it['ayah']}")
    by_tag = {f"P{i}": p for i, p in enumerate(res.get("passages", []), 1)}
    for pt in pts:
        p = by_tag.get(pt.get("passage"))
        if not p:
            continue
        qn = _vnorm(pt["quote"])
        quoted = {
            b["id"]
            for b in p.get("blocks", []) + p.get("footnotes", [])
            if qn and (qn in _vnorm(b["text"]) or _vnorm(b["text"]) in qn)
        }
        for v in p.get("quran", []):
            if v["block_id"] in quoted:
                out |= {f"{v['surah']}:{a}" for a in range(v["ayah_start"], v["ayah_end"] + 1)}
    return out


def _requirements(req: dict, res: dict, con: sqlite3.Connection) -> list[str]:
    """Reviewer notes as checks. Returns the list of unmet requirements (empty = all met)."""
    if not req:
        return []
    ans = res.get("answer") or {}
    pts = ans.get("source_points", [])
    quotes = [_vnorm(p["quote"]) for p in pts]
    fails = []

    def fn_text(bid: str) -> str:
        r = con.execute("SELECT text_raw FROM blocks WHERE id=?", (bid,)).fetchone()
        return _vnorm(r[0]) if r else ""

    def fn_quoted(bid: str) -> bool:
        f = fn_text(bid)
        return bool(f) and any(q and (q in f or f in q) for q in quotes)

    for b in req.get("footnotes_all", []):
        if not fn_quoted(b):
            fails.append(f"footnote not quoted: {b}")
    if req.get("footnotes_any") and not any(fn_quoted(b) for b in req["footnotes_any"]):
        fails.append(f"none of the footnotes quoted: {req['footnotes_any']}")
    for ph in req.get("quotes_all", []):
        if not any(_vnorm(ph) in q for q in quotes):
            fails.append(f"missing quote: {ph}")
    shown = _shown_verses(res)
    for v in req.get("verses_shown_all", []):
        if v not in shown:
            fails.append(f"verse not shown: {v}")
    if req.get("closest_verse"):
        c = [
            f"{x['surah']}:{x['ayah_start']}"
            for x in (res.get("quoted_verse_check") or {}).get("candidates", [])
            if x.get("closest")
        ]
        if c != [req["closest_verse"]]:
            fails.append(f"closest verse not marked: {req['closest_verse']} (got {c})")
    items = (res.get("external") or {}).get("items", {})
    if req.get("external_quran") and not any(p.get("external") == "quran" for p in pts):
        fails.append("no verse from the Mushaf cited")
    for term in req.get("terms_cited_all", []):
        if not any(
            p.get("external") == "term" and items.get(p["passage"], {}).get("term") == term
            for p in pts
        ):
            fails.append(f"term definition not cited: {term}")
    used_ext = any(p.get("external") for p in pts)
    urls = {r["url"] for r in (res.get("external") or {}).get("referrals", [])}
    for u in req.get("referrals_all", []):
        if not (used_ext and u in urls):
            fails.append(f"referral not shown: {u}")
    if req.get("language") == "en":
        txt = ans.get("explanation", "")
        latin = sum(c.isascii() and c.isalpha() for c in txt)
        if latin < 0.5 * max(1, sum(c.isalpha() for c in txt)):
            fails.append("explanation not in English")
    blob = json.dumps(ans, ensure_ascii=False).lower()
    for term in req.get("terms_en_all", []):
        if term.lower() not in blob:
            fails.append(f"English term missing: {term}")
    if req.get("glossary_explanation") and not (res.get("glossary") or {}).get("explanation"):
        fails.append("no brief explanation from the approved dictionary")
    return fails


def answers(runs: int, only: str | None, start_run: int = 0, human_only: bool = False) -> dict:
    path = RESULTS / "answers.json"
    old = json.loads(path.read_text()) if path.exists() else {"runs": {}}
    old.setdefault("primary", str(start_run))  # the first run written to a fresh file
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    for run in range(start_run, start_run + runs):
        bucket = old["runs"].setdefault(str(run), {})
        for q in load_questions(only, natural=not human_only):
            t0 = time.time()
            from api import budget

            if budget.status()["eval_stop"]:
                print("STOP: evaluation budget reached; the live reserve is kept", flush=True)
                return old
            res = answer(q["question"], use_cache=False, offline_run=run)
            s = score(q, res, con)
            s["seconds"] = round(time.time() - t0, 1)
            s["status"] = res.get("status")
            bucket[q["id"]] = s
            print(run, q["id"], s["behaviour"], "PASS" if s["pass"] else "FAIL", flush=True)
            RESULTS.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(old, ensure_ascii=False, indent=1))
    return old


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["retrieval", "answers"])
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--start-run", type=int, default=0)
    ap.add_argument("--only", default=None, help="id prefix or question type")
    ap.add_argument("--human-only", action="store_true", help="skip the natural-phrasing set")
    a = ap.parse_args()
    if a.what == "retrieval":
        r = retrieval()
        for m in ("asool", "baseline"):
            qs = r["questions"]
            print(m, "R@5", sum(x[m]["recall_at_5"] for x in qs) / len(qs))
    else:
        answers(a.runs, a.only, a.start_run, a.human_only)
