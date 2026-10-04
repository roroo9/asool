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
        s.update(verdict=body.verdict, fix=body.fix, reviewer=body.reviewer)
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


@router.get("/{pid}/crop")
def crop(pid: str, x0: int, y0: int, x1: int, y1: int, hl: str = "") -> Response:
    """Line crop (with margin) of the 300-DPI page; `hl` = 'x0,y0,x1,y1;...' boxes to mark."""
    im = Image.open(PAGES / f"{pid}.png").convert("RGB")
    pad_y = 28
    # Full page width gives the reviewer the whole printed line as context.
    box = (0, max(0, y0 - pad_y), im.width, min(im.height, y1 + pad_y))
    c = im.crop(box)
    if hl:
        dr = ImageDraw.Draw(c, "RGBA")
        for part in hl.split(";"):
            a, b, cc, dd = map(int, part.split(","))
            dr.rectangle(
                (a - box[0] - 3, b - box[1] - 3, cc - box[0] + 3, dd - box[1] + 3),
                fill=(47, 212, 181, 50),
                outline=(47, 212, 181, 255),
                width=3,
            )
    buf = io.BytesIO()
    c.save(buf, "WEBP", quality=85)
    return Response(
        buf.getvalue(), media_type="image/webp", headers={"Cache-Control": "private, max-age=3600"}
    )
