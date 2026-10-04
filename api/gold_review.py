"""Gold-set review API (human-in-the-loop). Writes only under data/gold/.

Protected by REVIEW_TOKEN (header `x-review-token`) when the env var is set.
"""

from __future__ import annotations

import io
import json
import threading
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from PIL import Image, ImageDraw
from pydantic import BaseModel

from api.settings import settings
from pipeline.config import GOLD, PAGES
from pipeline.gold_consensus import DRAFT, gold_text

_lock = threading.Lock()


def _auth(
    x_review_token: str | None = Header(default=None), t: str | None = Query(default=None)
) -> None:
    # Header for API calls; `t` query param for <img> crops (browsers can't set headers there).
    if settings.review_token and settings.review_token not in (x_review_token, t):
        raise HTTPException(401, "رمز المراجعة غير صحيح")


router = APIRouter(prefix="/review/gold", tags=["gold review"], dependencies=[Depends(_auth)])


def _load(pid: str) -> dict:
    p = DRAFT / f"{pid}.json"
    if not p.exists():
        raise HTTPException(404, "page not in gold set")
    return json.loads(p.read_text())


def _save(d: dict) -> None:
    (DRAFT / f"{d['page_id']}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))


def _progress(d: dict) -> dict:
    items = d["review_items"]
    spot = d["spotcheck"]
    return {
        "page_id": d["page_id"],
        "printed": d["printed"],
        "items_total": len(items),
        "items_done": sum(it["decision"] is not None for it in items),
        "spot_total": len(spot),
        "spot_done": sum(s["verdict"] is not None for s in spot),
        "structure_reviewed": d["structure_reviewed"],
        "finalized": (GOLD / f"{d['page_id']}.json").exists(),
        "auto_accepted": d["auto_accepted"],
        "total_tokens": d["total_tokens"],
    }


@router.get("/pages")
def pages() -> list[dict]:
    return [_progress(json.loads(p.read_text())) for p in sorted(DRAFT.glob("*.json"))]


@router.get("/{pid}")
def page(pid: str) -> dict:
    d = _load(pid)
    return d | {"progress": _progress(d)}


class Decision(BaseModel):
    text: str  # chosen or edited text; '' deletes the span
    reviewer: str


@router.post("/{pid}/item/{item_id}")
def decide(pid: str, item_id: str, body: Decision) -> dict:
    with _lock:
        d = _load(pid)
        it = next((x for x in d["review_items"] if x["id"] == item_id), None)
        if not it:
            raise HTTPException(404, "item not found")
        it["decision"] = body.text.strip()
        it["reviewer"] = body.reviewer
        it["decided_at"] = datetime.now(UTC).isoformat()
        _save(d)
    return _progress(d)


class Spot(BaseModel):
    verdict: str  # ok | wrong
    fix: str | None = None
    reviewer: str


@router.post("/{pid}/spot/{spot_id}")
def spot(pid: str, spot_id: str, body: Spot) -> dict:
    if body.verdict not in ("ok", "wrong"):
        raise HTTPException(422, "verdict must be ok or wrong")
    with _lock:
        d = _load(pid)
        s = next((x for x in d["spotcheck"] if x["id"] == spot_id), None)
        if not s:
            raise HTTPException(404, "spot item not found")
        verdict = body.verdict
        if verdict == "wrong" and (body.fix or "").strip() == s["text"]:
            verdict = "ok"  # an unchanged "correction" is a confirmation, not an error
        s.update(verdict=verdict, fix=body.fix, reviewer=body.reviewer)
        _save(d)
    return _progress(d)


class BlockType(BaseModel):
    type: str
    reviewer: str


@router.post("/{pid}/block/{order}")
def block_type(pid: str, order: int, body: BlockType) -> dict:
    with _lock:
        d = _load(pid)
        b = next((x for x in d["blocks"] if x["order"] == order), None)
        if not b:
            raise HTTPException(404, "block not found")
        b["type_confirmed"] = body.type
        _save(d)
    return _progress(d)


class Finalize(BaseModel):
    reviewer: str


@router.post("/{pid}/finalize")
def finalize(pid: str, body: Finalize) -> dict:
    with _lock:
        d = _load(pid)
        try:
            gold_text(d)  # validates that every item is decided
        except ValueError as e:
            raise HTTPException(409, str(e)) from e
        for b in d["blocks"]:
            if b["type_confirmed"] is None:
                b["type_confirmed"] = b["type"]
        d["structure_reviewed"] = True
        _save(d)
        spot = d["spotcheck"]
        gold = {
            "page_id": pid,
            "printed": d["printed"],
            "blocks": gold_text(d),
            "provenance": {
                "method": "consensus-assisted (CLAUDE.md §12.C)",
                "readers": d["readers"],
                "rule": d["rule"],
                "auto_accepted_tokens": d["auto_accepted"],
                "total_tokens": d["total_tokens"],
                "human_decisions": len(d["review_items"]),
                "spotcheck": {
                    "checked": sum(s["verdict"] is not None for s in spot),
                    "wrong": sum(s["verdict"] == "wrong" for s in spot),
                },
                "reviewer": body.reviewer,
                "finalized_at": datetime.now(UTC).isoformat(),
            },
        }
        (GOLD / f"{pid}.json").write_text(json.dumps(gold, ensure_ascii=False, indent=1))
    return _progress(d)


HL_FILL = (108, 92, 231, 70)  # insight violet, translucent
HL_LINE = (108, 92, 231, 255)
HINT = (224, 164, 58, 90)  # amber band for "location uncertain"


def _boxes(s: str) -> list[list[int]]:
    return [list(map(int, part.split(","))) for part in s.split(";") if part]


@router.get("/{pid}/crop")
def crop(pid: str, y0: int, y1: int, hl: str = "", x0: int = 0, x1: int = 0) -> Response:
    """The full printed line(s) y0..y1 at full page width; `hl` word boxes drawn in a strong
    color with a thick outline (only the disputed words, never the whole line)."""
    im = Image.open(PAGES / f"{pid}.png").convert("RGB")
    pad_y = 30
    box = (0, max(0, y0 - pad_y), im.width, min(im.height, y1 + pad_y))
    c = im.crop(box)
    dr = ImageDraw.Draw(c, "RGBA")
    for a, b, cc, dd in _boxes(hl):
        dr.rectangle(
            (a - box[0] - 4, b - box[1] - 4, cc - box[0] + 4, dd - box[1] + 4),
            fill=HL_FILL,
            outline=HL_LINE,
            width=5,
        )
    buf = io.BytesIO()
    c.save(buf, "WEBP", quality=85)
    return Response(buf.getvalue(), media_type="image/webp", headers={"Cache-Control": "no-store"})


@router.get("/{pid}/page")
def full_page(pid: str, hl: str = "", hint: str = "") -> Response:
    """Whole page (downscaled) with the disputed words marked, or an amber band when the
    location is uncertain."""
    im = Image.open(PAGES / f"{pid}.png").convert("RGB")
    dr = ImageDraw.Draw(im, "RGBA")
    for a, b, c, d in _boxes(hint):
        dr.rectangle((a, b, c, d), fill=HINT, outline=(224, 164, 58, 255), width=6)
    for a, b, c, d in _boxes(hl):
        dr.rectangle((a - 5, b - 5, c + 5, d + 5), fill=HL_FILL, outline=HL_LINE, width=8)
    w = 1100
    im = im.resize((w, round(im.height * w / im.width)))
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=80)
    return Response(buf.getvalue(), media_type="image/webp", headers={"Cache-Control": "no-store"})
