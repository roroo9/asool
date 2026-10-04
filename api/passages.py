"""Read models for passages (chunks), pages and books, with full provenance:
book -> edition -> page -> block -> bounding box, footnotes attached, Quran checks, hadith
grading. Used by /search, /answer, /passages, /pages and the public /api/v1.
"""

from __future__ import annotations

import json
import sqlite3

from api.search import db, highlight_spans
from pipeline.config import BOOK
from pipeline.hadith import UNVERIFIED_AR

J = json.loads


def _citation(page_printed: int) -> str:
    author = BOOK["author_ar"].split(" (")[0]
    return f"{BOOK['title_ar']}، {author}، {BOOK['edition']}، ص {page_printed}"


def _block_rows(con: sqlite3.Connection, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    q = f"SELECT * FROM blocks WHERE id IN ({','.join('?' * len(ids))})"
    rows = {r["id"]: dict(r) for r in con.execute(q, ids)}
    out = []
    for i in ids:
        r = rows.get(i)
        if not r:
            continue
        out.append(
            {
                "id": r["id"],
                "page_id": r["page_id"],
                "type": r["type"],
                "author_role": r["author_role"],
                "text": r["text_raw"],
                "bbox": J(r["bbox"]) if r["bbox"] else None,
                "rects": J(r["rects"]) if r["rects"] else [],
                "bbox_source": r["bbox_source"],
                "confidence": r["confidence"],
                "flags": J(r["flags"] or "[]"),
                "footnote_marker": r["footnote_marker"],
                "attached_to": r["attached_to"],
            }
        )
    return out


def hadith_view(r: dict) -> dict:
    return {
        "id": r["id"],
        "narrator": r["narrator"],
        "takhrij_printed": r["takhrij_text"],
        "grading_status": r["grading_status"],
        "grading": r["grading"] or UNVERIFIED_AR,
        "grading_source": r["grading_source"],
        "grading_source_url": r["grading_source_url"],
        "dorar_search_url": r["dorar_search_url"],
        "block_ids": json.loads(r["block_ids"])
        if isinstance(r["block_ids"], str)
        else r["block_ids"],
    }


def passage(
    cid: str, terms: list[str] | None = None, con: sqlite3.Connection | None = None
) -> dict | None:
    own = con is None
    con = con or db()
    c = con.execute("SELECT * FROM chunks WHERE id=?", (cid,)).fetchone()
    if not c:
        return None
    c = dict(c)
    block_ids, page_ids = J(c["block_ids"]), J(c["page_ids"])
    blocks = _block_rows(con, block_ids)
    fn_ids = J(c["footnote_ids"])
    fns = _block_rows(con, fn_ids)
    attached = {}
    if fn_ids:
        q = f"SELECT * FROM blocks WHERE attached_to IN ({','.join('?' * len(fn_ids))})"
        for r in con.execute(q, fn_ids):
            attached.setdefault(r["attached_to"], []).append(r["text_raw"])
    links = []
    if block_ids:
        q = (
            f"SELECT * FROM footnote_links WHERE anchor_block_id IN "
            f"({','.join('?' * len(block_ids))})"
        )
        links = [dict(r) for r in con.execute(q, block_ids)]
    qrefs = []
    if block_ids:
        q = f"SELECT * FROM quran_refs WHERE block_id IN ({','.join('?' * len(block_ids))})"
        for r in con.execute(q, block_ids):
            qrefs.append(
                {
                    "block_id": r["block_id"],
                    "surah": r["surah"],
                    "ayah_start": r["ayah_start"],
                    "ayah_end": r["ayah_end"],
                    "match_type": r["match_type"],
                    "similarity": r["similarity"],
                    "printed_text": r["printed_text"],
                    "canonical_text": r["canonical_text"],
                    "diff_ops": J(r["diff_ops"] or "[]"),
                    "reference_source": r["reference_source"],
                    "quranpedia_url": f"https://quranpedia.net/surah/{r['surah']}/{r['ayah_start']}",
                }
            )
    hadiths = []
    for hid in J(c["hadith_ids"]):
        r = con.execute("SELECT * FROM hadith_marks WHERE id=?", (hid,)).fetchone()
        if r:
            hadiths.append(hadith_view(dict(r)))
    pages = {
        r["id"]: r["page_number_printed"]
        for r in con.execute(
            "SELECT id, page_number_printed FROM pages WHERE id IN "
            f"({','.join('?' * len(page_ids))})",
            page_ids,
        )
    }
    commentary_on = c["commentary_on"]
    if own:
        con.close()
    text = c["text"]
    return {
        "id": c["id"],
        "kind": c["kind"],
        "author_role": c["author_role"],
        "author_label": "تعليق المحقق مصطفى محمد عمارة"
        if c["kind"] == "editor_commentary"
        else "متن الإمام النووي",
        "breadcrumb": J(c["breadcrumb"]),
        "text": text,
        "highlights": highlight_spans(text, terms or []),
        "pages": [
            {"id": p, "printed": pages[p], "citation": _citation(pages[p])}
            for p in page_ids
            if p in pages
        ],
        "blocks": blocks,
        "footnotes": [
            f
            | {
                "attached_text": attached.get(f["id"], []),
                "marker_links": [ln for ln in links if ln["footnote_block_id"] == f["id"]],
            }
            for f in fns
        ],
        "quran": qrefs,
        "hadith": hadiths,
        "commentary_on": commentary_on,
        "min_confidence": c["min_confidence"],
    }


def baseline_passage(bid: str, con: sqlite3.Connection | None = None) -> dict | None:
    own = con is None
    con = con or db()
    r = con.execute("SELECT * FROM baseline_chunks WHERE id=?", (bid,)).fetchone()
    p = (
        con.execute("SELECT page_number_printed FROM pages WHERE id=?", (r["page_id"],)).fetchone()
        if r
        else None
    )
    if own:
        con.close()
    if not r:
        return None
    return {
        "id": r["id"],
        "kind": "baseline",
        "text": r["text"],
        "pages": [{"id": r["page_id"], "printed": p[0] if p else None}],
        "note": "baseline: Tesseract text cut into fixed 500-character pieces",
    }


def page(pid: str) -> dict | None:
    con = db()
    p = con.execute("SELECT * FROM pages WHERE id=?", (pid,)).fetchone()
    if not p:
        con.close()
        return None
    p = dict(p)
    ids = [
        r[0] for r in con.execute("SELECT id FROM blocks WHERE page_id=? ORDER BY ord, id", (pid,))
    ]
    blocks = _block_rows(con, ids)
    links = [dict(r) for r in con.execute("SELECT * FROM footnote_links WHERE page_id=?", (pid,))]
    qrefs = [
        dict(r) | {"diff_ops": J(r["diff_ops"] or "[]")}
        for r in con.execute(
            f"SELECT * FROM quran_refs WHERE block_id IN ({','.join('?' * len(ids))})", ids
        )
    ]
    had = [
        hadith_view(dict(r)) | {"block_ids": J(r["block_ids"])}
        for r in con.execute("SELECT * FROM hadith_marks")
        if set(J(r["block_ids"])) & set(ids)
    ]
    neighbours = [
        r[0]
        for r in con.execute(
            "SELECT id FROM pages WHERE page_number_printed IN (?, ?) ORDER BY page_number_printed",
            (p["page_number_printed"] - 1, p["page_number_printed"] + 1),
        )
    ]
    con.close()
    return {
        "id": pid,
        "printed": p["page_number_printed"],
        "width": p["width"],
        "height": p["height"],
        "image": f"/pages/{pid}.webp",
        "citation": _citation(p["page_number_printed"]),
        "coverage": p["coverage"],
        "uncovered_regions": J(p["uncovered_regions"] or "[]"),
        "blocks": blocks,
        "footnote_links": links,
        "quran": qrefs,
        "hadith": had,
        "prev": next((n for n in neighbours if n < pid), None),
        "next": next((n for n in neighbours if n > pid), None),
    }


def book() -> dict:
    con = db()
    b = dict(con.execute("SELECT * FROM books").fetchone())
    n = con.execute("SELECT count(*) FROM pages").fetchone()[0]
    pages = [r[0] for r in con.execute("SELECT id FROM pages ORDER BY page_number_printed")]
    meta = {r[0]: r[1] for r in con.execute("SELECT key, value FROM meta")}
    con.close()
    return b | {"page_count": n, "page_ids": pages, "index_meta": meta}
