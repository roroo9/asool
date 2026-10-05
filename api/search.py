"""Hybrid retrieval (CLAUDE.md §4.7): BM25 (SQLite FTS5 on normalized text) + dense cosine
(Gemini Embedding 2) -> Reciprocal Rank Fusion (k=60). The same code serves Asool's
structure-aware chunks and the baseline's fixed chunks, so only data preparation differs.

If the embedding call fails (network, budget), search degrades to BM25 only and says so.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from api.settings import ROOT
from pipeline.normalize import normalize

DB = ROOT / "data" / "asool.db"
INDEX = ROOT / "data" / "index"
RRF_K = 60
_lock = threading.Lock()

# Arabic proclitics to strip for keyword matching (light stemming, both sides normalized).
_PREFIXES = ("وال", "بال", "فال", "كال", "لل", "ال", "و", "ف", "ب")


def _variants(tok: str) -> set[str]:
    out = {tok}
    for p in _PREFIXES:
        if tok.startswith(p) and len(tok) - len(p) >= 3:
            out.add(tok[len(p) :])
    return out


def query_terms(q: str) -> list[str]:
    toks = [t for t in normalize(q).split() if len(t) >= 2]
    terms: set[str] = set()
    for t in toks:
        terms |= _variants(t)
    return sorted(terms)


@lru_cache(maxsize=1)
def _vectors(name: str) -> tuple[np.ndarray, list[str]]:
    return np.load(INDEX / f"{name}.npy"), json.loads((INDEX / f"{name}_ids.json").read_text())


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


@dataclass
class Hit:
    id: str
    score: float  # RRF score
    bm25_rank: int | None
    dense_rank: int | None
    dense_sim: float | None


def _bm25(con: sqlite3.Connection, table: str, terms: list[str], n: int) -> list[str]:
    if not terms:
        return []
    # Each term may match a prefix-stripped form too (e.g. «التوبة» ~ «توبة»).
    expr = " OR ".join(f'"{t}"*' if len(t) >= 4 else f'"{t}"' for t in terms)
    try:
        rows = con.execute(
            f"SELECT id FROM {table} WHERE {table} MATCH ? ORDER BY bm25({table}) LIMIT ?",
            (expr, n),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [r[0] for r in rows]


_QUOTED = re.compile(r"[«\"“]([^»\"”]{4,200})[»\"”]")


def _phrase_hits(table: str, q: str, n: int = 10) -> list[str]:
    """Ids of units whose normalized text contains a phrase quoted in the question."""
    phrases = [normalize(m.group(1)) for m in _QUOTED.finditer(q)]
    phrases = [p for p in phrases if len(p.split()) >= 2]
    if not phrases:
        return []
    con = db()
    try:
        rows = con.execute(f"SELECT id, text_norm FROM {table}").fetchall()
    finally:
        con.close()
    out: list[str] = []
    for cid, text in rows:  # footnote markers are digits in text_norm: not words of the text
        hay = " " + " ".join(re.sub(r"\b\d+\b", " ", text or "").split()) + " "
        if any(f" {p} " in hay for p in phrases):
            out.append(cid)
    return out[:n]


def _dense(name: str, qvec: np.ndarray | None, n: int) -> list[tuple[str, float]]:
    if qvec is None:
        return []
    mat, ids = _vectors(name)
    sims = mat @ qvec
    top = np.argsort(-sims)[:n]
    return [(ids[i], float(sims[i])) for i in top]


def embed_query(q: str) -> np.ndarray | None:
    from api.llm import embed

    try:
        v = np.array(embed([q], stage="embed/query")[0], dtype=np.float32)
        return v / np.linalg.norm(v)
    except Exception:
        return None


def hybrid(
    q: str,
    *,
    mode: str = "asool",
    k: int = 5,
    n: int = 30,
    qvec: np.ndarray | None = None,
    extra_query: str | None = None,
) -> dict:
    """Returns {"hits": [Hit], "dense_available": bool, "terms": [...]}."""
    table, vname = ("chunks_fts", "chunks") if mode == "asool" else ("baseline_fts", "baseline")
    terms = query_terms(q + " " + (extra_query or ""))
    if qvec is None:
        qvec = embed_query(q if not extra_query else f"{q}\n{extra_query}")
    con = db()
    with _lock:
        bm = _bm25(con, table, terms, n)
    con.close()
    dn = _dense(vname, qvec, n)
    ph = _phrase_hits(table.replace("_fts", "_chunks" if mode != "asool" else ""), q)
    scores: dict[str, Hit] = {}
    # Third ranked list: units that contain a phrase the user quoted from the book («…»).
    # A verbatim quotation is strong evidence even when the unit is long and its embedding
    # is dominated by other content (found on eval question ans-16, «لا أغبق قبلهما»).
    for r, cid in enumerate(ph):
        h = scores.setdefault(cid, Hit(cid, 0.0, None, None, None))
        h.score += 1 / (RRF_K + r + 1)
    for r, cid in enumerate(bm):
        h = scores.setdefault(cid, Hit(cid, 0.0, None, None, None))
        h.score += 1 / (RRF_K + r + 1)
        h.bm25_rank = r + 1
    for r, (cid, sim) in enumerate(dn):
        h = scores.setdefault(cid, Hit(cid, 0.0, None, None, None))
        h.score += 1 / (RRF_K + r + 1)
        h.dense_rank = r + 1
        h.dense_sim = sim
    hits = sorted(scores.values(), key=lambda h: -h.score)[:k]
    # dense similarity for hits that only came from BM25 (used by the support gate)
    if qvec is not None:
        mat, ids = _vectors(vname)
        pos = {cid: i for i, cid in enumerate(ids)}
        for h in hits:
            if h.dense_sim is None and h.id in pos:
                h.dense_sim = float(mat[pos[h.id]] @ qvec)
    return {"hits": hits, "dense_available": qvec is not None, "terms": terms}


def highlight_spans(text: str, terms: list[str]) -> list[list[int]]:
    """Character spans in the RAW text whose normalized word matches a query term."""
    spans = []
    for m in re.finditer(r"\S+", text):
        w = normalize(m.group(0))
        if w and any(w == t or w.endswith(t) and len(t) >= 3 for t in terms):
            spans.append([m.start(), m.end()])
    return spans
