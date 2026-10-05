"""Human review of the evaluation question set (owner request, Oct 5).

The questions in data/eval/questions.jsonl were drafted by the AI agent. The reviewer approves,
edits or removes each one here. Decisions are stored separately
(data/eval/question_reviews.json) and applied on top of the drafts by `reviewed_questions()`,
so the original draft stays visible and every change is attributable.
Agent suggestions that need the reviewer's approval live in data/eval/question_proposals.json.

Protected by the same review code as the gold review.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.gold_review import _auth

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "data" / "eval"
QUESTIONS = EVAL / "questions.jsonl"
REVIEWS = EVAL / "question_reviews.json"
PROPOSALS = EVAL / "question_proposals.json"
DB = ROOT / "data" / "asool.db"
EDITABLE = ("question", "expected_behavior", "gold_chunk_ids", "required_chunk_ids")
BEHAVIOURS = ("answer", "abstain", "refer", "correct_verse")

_lock = threading.Lock()
router = APIRouter(
    prefix="/review/questions", tags=["question review"], dependencies=[Depends(_auth)]
)


def _drafts() -> list[dict]:
    return [json.loads(x) for x in QUESTIONS.read_text(encoding="utf-8").splitlines() if x]


def _json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def reviewed_questions(include_removed: bool = False) -> list[dict]:
    """Drafts with the reviewer's decisions applied (used by the evaluation)."""
    reviews = _json(REVIEWS)
    out = []
    for q in _drafts():
        r = reviews.get(q["id"])
        if r:
            if r["action"] == "remove" and not include_removed:
                continue
            q = (
                q
                | r.get("edit", {})
                | {
                    "human_verified": r["action"] in ("approve", "edit"),
                    "reviewed_by": r["reviewer"],
                    "review_action": r["action"],
                }
            )
        out.append(q)
    return out


def _chunks() -> dict[str, dict]:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    pages = {r["id"]: r["page_number_printed"] for r in con.execute("SELECT * FROM pages")}
    out = {}
    for r in con.execute("SELECT id, kind, text, page_ids FROM chunks ORDER BY id"):
        out[r["id"]] = {
            "id": r["id"],
            "kind": r["kind"],
            "pages": [pages.get(p) for p in json.loads(r["page_ids"])],
            "excerpt": _excerpt(r["text"]),
        }
    con.close()
    return out


def _excerpt(text: str, n: int = 40) -> str:
    """Start of the narration, then the quoted wording itself (the part a reviewer judges)."""
    words = text.split()
    i = text.find("«")
    if i <= 0 or len(text[:i].split()) <= 12:
        return " ".join(words[:n])
    return " ".join(text[:i].split()[:6]) + " … " + " ".join(text[i:].split()[:n])


def _citations(q: dict, chunks: dict) -> list[dict]:
    req = set(q.get("required_chunk_ids") or [])
    ids = list(dict.fromkeys([*(q.get("gold_chunk_ids") or []), *req]))
    return [chunks[i] | {"required": i in req} for i in ids if i in chunks]


@router.get("")
def listing() -> dict:
    chunks = _chunks()
    reviews, proposals = _json(REVIEWS), _json(PROPOSALS)
    items = []
    for q in _drafts():
        p = proposals.get(q["id"])
        items.append(
            {
                "id": q["id"],
                "official_no": q.get("official_no"),
                "draft": {
                    k: q.get(k)
                    for k in (*EDITABLE, "type", "allowed_behaviors", "notes", "expected_verses")
                }
                | {"expected_ar": q.get("expected_ar")},
                "citations": _citations(q, chunks),
                "proposal": p
                and p
                | {"citations": _citations({k: p.get(k, q.get(k)) for k in EDITABLE}, chunks)},
                "review": reviews.get(q["id"]),
            }
        )
    done = sum(1 for i in items if i["review"])
    return {
        "items": items,
        "chunks": list(chunks.values()),
        "progress": {"done": done, "total": len(items)},
    }


class Review(BaseModel):
    action: Literal["approve", "edit", "remove"]
    reviewer: str
    note: str = ""
    edit: dict | None = None


@router.post("/{qid}")
def decide(qid: str, body: Review) -> dict:
    drafts = {q["id"]: q for q in _drafts()}
    if qid not in drafts:
        raise HTTPException(404, "السؤال غير موجود")
    edit = {}
    if body.action == "edit":
        edit = {k: v for k, v in (body.edit or {}).items() if k in EDITABLE}
        if not edit:
            raise HTTPException(422, "لا توجد تعديلات")
        if "expected_behavior" in edit and edit["expected_behavior"] not in BEHAVIOURS:
            raise HTTPException(422, "سلوك غير معروف")
        chunks = _chunks()
        for k in ("gold_chunk_ids", "required_chunk_ids"):
            if k in edit and any(c not in chunks for c in edit[k]):
                raise HTTPException(422, "مقطع غير موجود")
        if "gold_chunk_ids" in edit:  # pages follow the chosen citations
            pages = sorted({p for c in edit["gold_chunk_ids"] for p in _page_ids(c)})
            edit["gold_page_ids"] = pages
    with _lock:
        reviews = _json(REVIEWS)
        reviews[qid] = {
            "action": body.action,
            "reviewer": body.reviewer.strip() or "rawan",
            "note": body.note.strip(),
            "edit": edit,
            "decided_at": datetime.now(UTC).isoformat(),
        }
        REVIEWS.write_text(json.dumps(reviews, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "done": len(reviews), "total": len(drafts)}


@router.delete("/{qid}")
def undo(qid: str) -> dict:
    with _lock:
        reviews = _json(REVIEWS)
        reviews.pop(qid, None)
        REVIEWS.write_text(json.dumps(reviews, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True}


def _page_ids(cid: str) -> list[str]:
    con = sqlite3.connect(DB)
    r = con.execute("SELECT page_ids FROM chunks WHERE id=?", (cid,)).fetchone()
    con.close()
    return json.loads(r[0]) if r else []
