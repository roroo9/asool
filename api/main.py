"""Asool API.

Internal endpoints (used by the web app) + a public read-only API under /api/v1.
OpenAPI docs: /docs
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api import budget, gold_review, hadith_review
from api import passages as P
from api.answer import answer as run_answer
from api.search import hybrid
from api.settings import ROOT, settings

app = FastAPI(
    title="Asool API",
    version="1.0.0",
    description=(
        "أصول: بحث وأجوبة موثقة من صفحات الكتب المطبوعة الأصلية. أداة مدعومة بالذكاء الاصطناعي. "
        "Every passage links to book -> edition -> page -> block -> bounding box."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
app.include_router(gold_review.router)
app.include_router(hadith_review.router)

PAGES_DIR = ROOT / "data" / "pages"
EVAL = ROOT / "data" / "eval" / "results" / "summary.json"


def _ip(req: Request) -> str:
    fwd = req.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (req.client.host if req.client else "unknown")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "asool-api",
        "version": app.version,
        "budget": budget.status(),
    }


@app.get("/books")
def books() -> list[dict]:
    return [P.book()]


@app.get("/pages/{page_id}.webp", include_in_schema=False)
def page_image(page_id: str) -> FileResponse:
    f = PAGES_DIR / f"{page_id}.webp"
    if "/" in page_id or not f.exists():
        raise HTTPException(404, "image not found")
    return FileResponse(
        f, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"}
    )


@app.get("/pages/{page_id}")
def page(page_id: str) -> dict:
    p = P.page(page_id)
    if not p:
        raise HTTPException(404, "page not found")
    return p


@app.get("/pages/{page_id}/naive")
def page_naive(page_id: str) -> dict:
    """What a typical pipeline gets from this page: Tesseract text in OCR line order, with
    footnotes mixed into the body and no structure (the baseline's data preparation)."""
    f = ROOT / "data" / "intermediate" / "ocr" / f"{page_id}.json"
    if "/" in page_id or not f.exists():
        raise HTTPException(404, "page not found")
    o = json.loads(f.read_text())
    return {
        "page_id": page_id,
        "engine": o["engine"],
        "lines": [{"text": ln["text"], "bbox": ln["bbox"]} for ln in o["lines"]],
    }


@app.get("/eval/bakeoff")
def eval_bakeoff() -> dict:
    f = ROOT / "data" / "eval" / "results" / "bakeoff.json"
    if not f.exists():
        return {"available": False}
    d = json.loads(f.read_text())
    return {"available": True, "pages": d["pages"], "rows": d["rows"]}


@app.get("/eval/known-errors")
def eval_known_errors() -> dict:
    f = ROOT / "data" / "eval" / "known_extraction_errors.json"
    return json.loads(f.read_text()) if f.exists() else {"errors": []}


@app.get("/passages/{passage_id}")
def get_passage(passage_id: str) -> dict:
    p = P.baseline_passage(passage_id) if passage_id.startswith("base-") else P.passage(passage_id)
    if not p:
        raise HTTPException(404, "passage not found")
    return p


@app.get("/search")
def search(
    q: str = Query(..., min_length=2, max_length=300),
    k: int = Query(5, ge=1, le=20),
    mode: str = Query("asool", pattern="^(asool|baseline)$"),
) -> dict:
    r = hybrid(q, mode=mode, k=k)
    if mode == "baseline":
        items = [P.baseline_passage(h.id) | {"retrieval": h.__dict__} for h in r["hits"]]
    else:
        items = [P.passage(h.id, r["terms"]) | {"retrieval": h.__dict__} for h in r["hits"]]
    return {"query": q, "mode": mode, "dense_available": r["dense_available"], "results": items}


class AskBody(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)


@app.post("/answer")
def ask(body: AskBody, req: Request) -> dict:
    try:
        return run_answer(body.question, ip=_ip(req))
    except Exception as e:  # never a broken page: fall back to passages only
        r = hybrid(body.question, k=5)
        return {
            "question": body.question,
            "status": "unavailable",
            "message": "تعذّر توليد إجابة حاليًا، وفيما يلي أقرب النصوص من الكتاب.",
            "passages": [P.passage(h.id, r["terms"]) for h in r["hits"]],
            "error": type(e).__name__,
        }


@app.get("/eval/summary")
def eval_summary() -> dict:
    if not EVAL.exists():
        return {"available": False}
    return json.loads(EVAL.read_text()) | {"available": True}


# ---- Review queue (list is public; resolving needs the review code) ----


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(ROOT / "data" / "asool.db")
    con.row_factory = sqlite3.Row
    return con


@app.get("/review")
def review_queue(include_resolved: bool = False) -> list[dict]:
    con = _con()
    q = (
        "SELECT r.*, b.type, b.text_raw, b.bbox FROM review_items r "
        "LEFT JOIN blocks b ON b.id=r.block_id"
    )
    if not include_resolved:
        q += " WHERE r.resolved=0"
    rows = []
    for r in con.execute(q + " ORDER BY r.page_id"):
        d = dict(r)
        d["bbox"] = json.loads(d["bbox"]) if d["bbox"] else None
        if d["block_id"] is None:
            p = con.execute(
                "SELECT uncovered_regions FROM pages WHERE id=?", (d["page_id"],)
            ).fetchone()
            d["regions"] = json.loads(p[0] or "[]") if p else []
        rows.append(d)
    con.close()
    return rows


class Resolve(BaseModel):
    reviewer: str
    note: str = ""


@app.post("/review/{item_id}/resolve", dependencies=[Depends(gold_review._auth)])
def resolve(item_id: int, body: Resolve) -> dict:
    con = _con()
    now = datetime.now(UTC).isoformat()
    row = con.execute(
        "SELECT page_id, block_id FROM review_items WHERE id=?", (item_id,)
    ).fetchone()
    if not row:
        con.close()
        raise HTTPException(404, "review item not found")
    con.execute(
        "UPDATE review_items SET resolved=1, resolved_by=?, resolved_at=? WHERE id=?",
        (f"{body.reviewer}: {body.note}".strip(": "), now, item_id),
    )
    con.commit()
    con.close()
    f = ROOT / "data" / "review_resolutions.json"
    res = json.loads(f.read_text()) if f.exists() else {}
    res[f"{row['page_id']}|{row['block_id'] or 'PAGE'}"] = {
        "by": body.reviewer,
        "note": body.note,
        "at": now,
    }
    f.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return {"ok": True}


# ---- Public read-only API ----


@app.get("/api/v1/search", tags=["public api"])
def v1_search(
    q: str = Query(..., min_length=2, max_length=300), k: int = Query(5, ge=1, le=20)
) -> dict:
    """Hybrid search over the indexed book. Each result carries its page citation and the
    bounding boxes of its blocks on the original page image."""
    return search(q=q, k=k, mode="asool") | {
        "attribution": "Asool (أصول) — رياض الصالحين، طبعة 1956. Cite the printed page.",
    }


@app.get("/api/v1/passages/{passage_id}", tags=["public api"])
def v1_passage(passage_id: str) -> dict:
    return get_passage(passage_id)
