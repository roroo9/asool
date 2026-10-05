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
import sqlite3
import time
from pathlib import Path

from api.answer import _vnorm, answer, verify_quotes
from api.passages import baseline_passage, passage
from api.question_review import reviewed_questions
from api.search import hybrid
from pipeline.normalize import normalize

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "data" / "eval" / "questions.jsonl"
RESULTS = ROOT / "data" / "eval" / "results"
DB = ROOT / "data" / "asool.db"
K = 5


def load_questions(only: str | None = None) -> list[dict]:
    """Agent drafts with the human reviewer's approvals, edits and removals applied."""
    rows = reviewed_questions()
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


def retrieval() -> dict:
    out = []
    for q in load_questions():
        if not q.get("gold_page_ids") or q["expected_behavior"] not in ("answer",):
            continue
        row = {"id": q["id"], "type": q["type"], "needs_footnote": q["needs_footnote"]}
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
            if q["needs_footnote"]:
                need = normalize(q["footnote_must_contain"], "search")
                # context complete = a top-5 unit from a gold page also carries the footnote
                r["context_complete"] = any(
                    gold & {p["id"] for p in u["pages"]}
                    and need in normalize(_unit_text(u), "search")
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
    # Re-verify every shown quote independently: a fabricated quote is one that is shown
    # but is not in its passage (must be 0; the pipeline removes them before showing).
    kept, removed = verify_quotes(pts, by_tag) if pts else ([], [])
    s["quotes_shown"] = len(pts)
    s["fabricated_quotes"] = len(removed)
    # Traceability: every shown quote resolves to a stored block with a page and a box.
    traced = 0
    for pt in pts:
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
    s["model"] = res.get("model")
    return s


def answers(runs: int, only: str | None, start_run: int = 0) -> dict:
    path = RESULTS / "answers.json"
    old = json.loads(path.read_text()) if path.exists() else {"runs": {}}
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    for run in range(start_run, start_run + runs):
        bucket = old["runs"].setdefault(str(run), {})
        for q in load_questions(only):
            t0 = time.time()
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
    a = ap.parse_args()
    if a.what == "retrieval":
        r = retrieval()
        for m in ("asool", "baseline"):
            qs = r["questions"]
            print(m, "R@5", sum(x[m]["recall_at_5"] for x in qs) / len(qs))
    else:
        answers(a.runs, a.only, a.start_run)
