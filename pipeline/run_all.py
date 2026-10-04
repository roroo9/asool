"""Idempotent ingestion: parse -> geometry -> fuse -> completeness -> footnotes -> Quran ->
hadith -> confidence -> chunk -> embed -> index (+ baseline). Every LLM call is cached, so
re-running is free; only missing pieces are computed.

    uv run python -m pipeline.run_all            # full corpus
    uv run python -m pipeline.run_all --no-embed # skip embeddings (offline)
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import UTC, datetime

import numpy as np

from api.settings import settings
from pipeline import (
    baseline,
    completeness,
    footnotes,
    hadith,
    ocr_geometry,
    quran,
    structure_checks,
)
from pipeline.config import BOOK, BOOK_ID, CORPUS_PAGES, DATA, INTER, PAGES, page_id
from pipeline.fuse import fuse_two_lanes
from pipeline.normalize import normalize
from pipeline.rasterize import rasterize
from pipeline.vlm_boxes import locate
from pipeline.vlm_parse import model_dir, parse_page

DB = DATA / "asool.db"
INDEX_DIR = DATA / "index"
PARSER_PROMPT = "page_parse.v2"
REVIEW_THRESHOLD = 0.75
AR = re.compile(r"[ء-ي]")

SCHEMA = """
CREATE TABLE books(id TEXT PRIMARY KEY, title_ar, title_en, author_ar, edition, editor_ar,
  publisher, year, license, source_url, approved_reference_category);
CREATE TABLE pages(id TEXT PRIMARY KEY, book_id, page_number_printed INT, page_index INT,
  image_path, width INT, height INT, status, coverage REAL, uncovered_regions JSON);
CREATE TABLE blocks(id TEXT PRIMARY KEY, page_id, ord INT, type, author_role, col INT,
  text_raw, text_norm, bbox JSON, rects JSON, bbox_source, lanes_agree INT, align_score REAL,
  footnote_marker, continues_from_prev INT, continues_to_next INT, vlm_confidence REAL,
  confidence REAL, flags JSON, attached_to, reviewed INT DEFAULT 0);
CREATE TABLE footnote_links(id INTEGER PRIMARY KEY, page_id, marker, anchor_block_id,
  anchor_char_offset INT, footnote_block_id, confidence REAL, method);
CREATE TABLE quran_refs(id INTEGER PRIMARY KEY, block_id, surah INT, ayah_start INT,
  ayah_end INT, match_type, similarity REAL, canonical_text, printed_text, diff_ops JSON,
  detection, reference_source);
CREATE TABLE hadith_marks(id TEXT PRIMARY KEY, block_ids JSON, wording, narrator,
  takhrij_text, takhrij_kind, grading_status, grading, grading_source, grading_source_url,
  graded_by, dorar_search_url, hadeethenc JSON, hadeethenc_check JSON, dorar_entry JSON);
CREATE TABLE chunks(id TEXT PRIMARY KEY, book_id, kind, author_role, breadcrumb JSON, text,
  text_norm, text_for_embedding, block_ids JSON, page_ids JSON, footnote_ids JSON,
  quran_ref_ids JSON, hadith_ids JSON, commentary_on, token_count INT, min_confidence REAL);
CREATE VIRTUAL TABLE chunks_fts USING fts5(id UNINDEXED, text_norm, tokenize='unicode61');
CREATE TABLE baseline_chunks(id TEXT PRIMARY KEY, page_id, text, text_norm, char_start INT);
CREATE VIRTUAL TABLE baseline_fts USING fts5(id UNINDEXED, text_norm, tokenize='unicode61');
CREATE TABLE review_items(id INTEGER PRIMARY KEY, block_id, page_id, reason, confidence REAL,
  created_at, resolved INT DEFAULT 0, resolved_by, resolved_at);
CREATE TABLE meta(key PRIMARY KEY, value);
"""


def _arabic_ratio(t: str) -> float:
    letters = [c for c in t if c.isalpha()]
    return len(AR.findall(t)) / len(letters) if letters else 1.0


def build(embed: bool = True) -> None:
    meta = {p["printed"]: p for p in rasterize()}
    ocr_geometry.run()
    model = settings.page_parser_model
    pages, all_blocks, links, flags, qrefs, page_flags = [], [], [], [], [], []
    for p in CORPUS_PAGES:
        pid = page_id(p)
        try:
            parsed = parse_page(p, model, prompt=PARSER_PROMPT)
        except Exception as e:  # fall back to the configured fallback parser, flagged
            print(f"parser failed on p{p}: {e}; using fallback")
            parsed = parse_page(p, settings.page_parser_fallback_model, prompt=PARSER_PROMPT)
            page_flags.append((pid, f"primary parser failed: {str(e)[:120]}"))
        ocr = json.loads((INTER / "ocr" / f"{pid}.json").read_text())
        blocks = parsed["blocks"]
        for b in blocks:
            b["id"] = f"{pid}-b{b['order']:02d}"
            b["page_id"] = pid
        boxes = locate(p, blocks)
        blocks = fuse_two_lanes(blocks, ocr, boxes)
        blocks = footnotes.split_merged_footnotes(blocks)
        for b in blocks:
            if b.get("split_from"):
                b["id"] = f"{b['split_from']}-{b['sub']}"
        blocks = structure_checks.tighten_boxes(blocks, ocr)
        blocks = structure_checks.attach_colon_continuations(blocks)
        flags += structure_checks.duplicate_runs(blocks)
        comp = completeness.check(p, blocks)
        if not comp["complete"]:
            page_flags.append(
                (
                    pid,
                    f"completeness: {comp['uncovered_lines']} printed line(s) not covered by "
                    f"extracted text",
                )
            )
        pl, pf = footnotes.link_page(blocks, pid)
        links += pl
        flags += pf
        for b in blocks:
            spans = []
            if b["type"] == "quran":
                spans = [(b["text"], "typed_quran")]
            elif b.get("author_role") != "editor" and b["type"] in ("body", "hadith"):
                spans = [(s, "brackets") for s in quran.bracketed_spans(b["text"])]
                spans += [
                    (m.printed_text, "unmarked_3gram") for m in quran.find_unmarked(b["text"])
                ]
            for s, how in spans:
                m = quran.verify(s)
                if m:
                    qrefs.append((b["id"], m, how))
        pages.append(
            {
                "id": pid,
                "printed": p,
                "w": meta[p]["width"],
                "h": meta[p]["height"],
                "coverage": comp["coverage"],
                "regions": comp["regions"],
            }
        )
        all_blocks += blocks

    # Confidence (CLAUDE.md §4.5)
    bflags: dict[str, list[str]] = {}
    for f in flags:
        bflags.setdefault(f["block_id"], []).append(f["reason"])
    for bid, m, _ in qrefs:
        if m.match_type == "mismatch":
            bflags.setdefault(bid, []).append(
                f"Quran text differs from the reference ({m.surah}:{m.ayah_start})"
            )
    for b in all_blocks:
        fl = bflags.setdefault(b["id"], [])
        c = float(b.get("confidence", 0.8))
        if "[؟]" in b["text"]:
            c = min(c, 0.5)
            fl.append("unreadable word marked [؟]")
        if b["bbox_source"] == "none":
            c = min(c, 0.5)
            fl.append("no position on the page found")
        elif not b.get("lanes_agree"):
            c = min(c, 0.85)
            fl.append("position from the vision model only (OCR could not confirm)")
        if any("footnote" in x for x in fl):
            c = min(c, 0.7)
        if any("Quran text differs" in x for x in fl):
            c = min(c, 0.5)
        if b["type"] not in ("page_number", "page_header") and _arabic_ratio(b["text"]) < 0.7:
            c = min(c, 0.6)
            fl.append("low share of Arabic letters")
        b["final_confidence"] = round(c, 3)
        b["vlm_confidence"] = b.get("confidence")

    # Hadith units over the whole corpus in reading order
    def _he_match(wording: str) -> list[dict]:
        try:
            from pipeline import hadeethenc

            return hadeethenc.match(wording)
        except Exception as e:  # HadeethEnc is optional; never block ingestion
            print("hadeethenc unavailable:", e)
            return []

    hunits = hadith.units(all_blocks, match_fn=_he_match)

    chunks = _chunks(all_blocks, links, qrefs, hunits)
    _write_db(pages, all_blocks, links, qrefs, hunits, chunks, bflags, page_flags)
    base = baseline.build()
    if embed:
        _embed(chunks, base)
    print(
        f"pages={len(pages)} blocks={len(all_blocks)} footnote_links={len(links)} "
        f"quran_refs={len(qrefs)} hadith_units={len(hunits)} chunks={len(chunks)} "
        f"baseline_chunks={len(base)}"
    )


def _chunks(blocks, links, qrefs, hunits) -> list[dict]:
    """Structure-aware chunks: one per hadith unit / Quran-introduction run within a chapter;
    editor commentary as separate, labeled chunks; footnotes attached; never split a block."""
    fn_by_anchor: dict[str, list[str]] = {}
    for ln in links:
        if ln["anchor_block_id"]:
            fn_by_anchor.setdefault(ln["anchor_block_id"], []).append(ln["footnote_block_id"])
    byid = {b["id"]: b for b in blocks}
    q_by_block: dict[str, list[int]] = {}
    for i, (bid, _, _) in enumerate(qrefs):
        q_by_block.setdefault(bid, []).append(i + 1)
    h_by_block = {bid: u["id"] for u in hunits for bid in u["block_ids"]}
    chapter = ""
    chunks: list[dict] = []
    cur: dict | None = None
    last_matn: str | None = None

    def close():
        nonlocal cur
        if cur and cur["block_ids"]:
            chunks.append(cur)
        cur = None

    for b in blocks:
        t = b["type"]
        if t in ("page_number", "page_header", "footnote") or b.get("attached_to"):
            continue
        if t == "heading":
            close()
            if "باب" in b["text"] or not chapter:
                chapter = re.sub(r"\s+", " ", b["text"]).strip()
            continue
        if b.get("author_role") == "editor" or t == "editor_commentary":
            if not (cur and cur["kind"] == "editor_commentary"):
                close()
                cur = {
                    "kind": "editor_commentary",
                    "author_role": "editor",
                    "block_ids": [],
                    "chapter": chapter,
                    "commentary_on": last_matn,
                }
            cur["block_ids"].append(b["id"])
            continue
        starts_unit = t == "body" and hadith.START_RE.match(b["text"])
        too_big = cur and sum(len(byid[x]["text"]) for x in cur["block_ids"]) > 2200
        if (
            cur is None
            or cur["kind"] != "matn"
            or (starts_unit and not b.get("continues_from_prev"))
            or too_big
        ):
            close()
            cur = {
                "kind": "matn",
                "author_role": "matn",
                "block_ids": [],
                "chapter": chapter,
                "commentary_on": None,
            }
            n = len(chunks)
            last_matn = f"{BOOK_ID}-c{n:03d}"
        cur["block_ids"].append(b["id"])
    close()

    out = []
    for n, c in enumerate(chunks):
        cid = f"{BOOK_ID}-c{n:03d}"
        bl = [byid[x] for x in c["block_ids"]]
        text = "\n".join(x["text"] for x in bl)
        fns = [f for x in c["block_ids"] for f in fn_by_anchor.get(x, [])]
        attached: dict[str, list[str]] = {}
        for x in blocks:
            if x.get("attached_to"):
                attached.setdefault(x["attached_to"], []).append(x["text"])
        fn_text = " ".join(
            " ".join([byid[f]["text"], *attached.get(f, [])]) for f in fns if f in byid
        )
        crumb = [BOOK["title_ar"], c["chapter"]] if c["chapter"] else [BOOK["title_ar"]]
        label = (
            "تعليق المحقق مصطفى محمد عمارة"
            if c["kind"] == "editor_commentary"
            else "متن الإمام النووي"
        )
        tfe = f"{' › '.join(crumb)} › {label}\n{text}" + (f"\n[حواشي] {fn_text}" if fn_text else "")
        out.append(
            {
                "id": cid,
                "kind": c["kind"],
                "author_role": c["author_role"],
                "breadcrumb": crumb,
                "text": text,
                "text_norm": normalize(text + " " + fn_text),
                "text_for_embedding": tfe,
                "block_ids": c["block_ids"],
                "page_ids": sorted({x["page_id"] for x in bl}),
                "footnote_ids": fns,
                "quran_ref_ids": [q for x in c["block_ids"] for q in q_by_block.get(x, [])],
                "hadith_ids": sorted({h_by_block[x] for x in c["block_ids"] if x in h_by_block}),
                "commentary_on": (c["commentary_on"] if c["kind"] == "editor_commentary" else None),
                "token_count": len(text.split()),
                "min_confidence": min(x["final_confidence"] for x in bl),
            }
        )
    # commentary_on was recorded as the id the matn chunk would get; fix it to the real id
    ids = {x["id"] for x in out}
    for c in out:
        if c["commentary_on"] and c["commentary_on"] not in ids:
            c["commentary_on"] = None
    return out


def _write_db(pages, blocks, links, qrefs, hunits, chunks, bflags, page_flags) -> None:
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    j = json.dumps
    con.execute(
        "INSERT INTO books VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            BOOK_ID,
            BOOK["title_ar"],
            BOOK["title_en"],
            BOOK["author_ar"],
            BOOK["edition"],
            BOOK["editor_ar"],
            BOOK["publisher"],
            BOOK["year"],
            BOOK["license"],
            BOOK["source_url"],
            BOOK["approved_reference_category"],
        ),
    )
    for p in pages:
        con.execute(
            "INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                p["id"],
                BOOK_ID,
                p["printed"],
                p["printed"] - 1,
                f"pages/{p['id']}.webp",
                p["w"],
                p["h"],
                "indexed",
                p["coverage"],
                j(p["regions"]),
            ),
        )
    for b in blocks:
        con.execute(
            "INSERT INTO blocks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
            (
                b["id"],
                b["page_id"],
                b["order"],
                b["type"],
                b.get("author_role"),
                b.get("column"),
                b["text"],
                normalize(b["text"]),
                j(b.get("bbox")),
                j(b.get("rects")),
                b["bbox_source"],
                int(bool(b.get("lanes_agree"))),
                b.get("align_score"),
                b.get("footnote_marker"),
                int(b.get("continues_from_prev", False)),
                int(b.get("continues_to_next", False)),
                b.get("vlm_confidence"),
                b["final_confidence"],
                j(sorted(set(bflags.get(b["id"], []))), ensure_ascii=False),
                b.get("attached_to"),
            ),
        )
    for ln in links:
        con.execute(
            "INSERT INTO footnote_links(page_id,marker,anchor_block_id,anchor_char_offset,"
            "footnote_block_id,confidence,method) VALUES (?,?,?,?,?,?,?)",
            (
                ln["page_id"],
                ln["marker"],
                ln["anchor_block_id"],
                ln["anchor_char_offset"],
                ln["footnote_block_id"],
                ln["confidence"],
                ln["method"],
            ),
        )
    for bid, m, how in qrefs:
        con.execute(
            "INSERT INTO quran_refs(block_id,surah,ayah_start,ayah_end,match_type,"
            "similarity,canonical_text,printed_text,diff_ops,detection,reference_source) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                bid,
                m.surah,
                m.ayah_start,
                m.ayah_end,
                m.match_type,
                m.similarity,
                m.canonical_text,
                m.printed_text,
                j(m.diff_ops, ensure_ascii=False),
                how,
                quran.reference_source(),
            ),
        )
    for u in hunits:
        con.execute(
            "INSERT INTO hadith_marks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                u["id"],
                j(u["block_ids"]),
                u["wording"],
                u["narrator"],
                u["takhrij_text"],
                u["takhrij_kind"],
                u["grading_status"],
                u["grading"],
                u["grading_source"],
                u["grading_source_url"],
                u["graded_by"],
                u["dorar_search_url"],
                j(u.get("hadeethenc", []), ensure_ascii=False),
                j(u.get("hadeethenc_check"), ensure_ascii=False),
                j(u.get("dorar_entry"), ensure_ascii=False),
            ),
        )
    for c in chunks:
        con.execute(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                c["id"],
                BOOK_ID,
                c["kind"],
                c["author_role"],
                j(c["breadcrumb"], ensure_ascii=False),
                c["text"],
                c["text_norm"],
                c["text_for_embedding"],
                j(c["block_ids"]),
                j(c["page_ids"]),
                j(c["footnote_ids"]),
                j(c["quran_ref_ids"]),
                j(c["hadith_ids"]),
                c["commentary_on"],
                c["token_count"],
                c["min_confidence"],
            ),
        )
        con.execute("INSERT INTO chunks_fts VALUES (?,?)", (c["id"], c["text_norm"]))
    now = datetime.now(UTC).isoformat()
    for b in blocks:
        if b["final_confidence"] < REVIEW_THRESHOLD:
            con.execute(
                "INSERT INTO review_items(block_id,page_id,reason,confidence,created_at) "
                "VALUES (?,?,?,?,?)",
                (
                    b["id"],
                    b["page_id"],
                    "; ".join(sorted(set(bflags.get(b["id"], [])))) or "low model confidence",
                    b["final_confidence"],
                    now,
                ),
            )
    for pid, reason in page_flags:
        con.execute(
            "INSERT INTO review_items(block_id,page_id,reason,confidence,created_at) "
            "VALUES (NULL,?,?,NULL,?)",
            (pid, reason, now),
        )
    # Re-apply human review resolutions (versioned file) so a rebuild never loses them.
    res_file = DATA / "review_resolutions.json"
    if res_file.exists():
        for key, r in json.loads(res_file.read_text()).items():
            pid, bid = key.split("|")
            con.execute(
                "UPDATE review_items SET resolved=1, resolved_by=?, resolved_at=? "
                "WHERE page_id=? AND coalesce(block_id,'PAGE')=?",
                (f"{r['by']}: {r.get('note', '')}", r.get("at"), pid, bid),
            )
    con.execute("INSERT INTO meta VALUES ('built_at', ?)", (now,))
    con.execute(
        "INSERT INTO meta VALUES ('page_parser', ?)",
        (f"{settings.page_parser_model} {PARSER_PROMPT}",),
    )
    con.execute("INSERT INTO meta VALUES ('quran_reference', ?)", (quran.reference_source(),))
    con.commit()
    con.close()


def _embed(chunks: list[dict], base: list[dict]) -> None:
    from api.llm import embed

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    for name, rows, field in (("chunks", chunks, "text_for_embedding"), ("baseline", base, "text")):
        vecs = np.array(embed([r[field] for r in rows], stage=f"embed/{name}"), dtype=np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        np.save(INDEX_DIR / f"{name}.npy", vecs)
        (INDEX_DIR / f"{name}_ids.json").write_text(json.dumps([r["id"] for r in rows]))
    (INDEX_DIR / "model.txt").write_text(settings.embed_model)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-embed", action="store_true")
    a = ap.parse_args()
    _ = model_dir, PAGES  # re-exported for scripts
    build(embed=not a.no_embed)
