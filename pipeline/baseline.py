"""Baseline data preparation (CLAUDE.md §5.1), for a fair comparison with Asool.

The 1956 PDF's own text layer is unusable (0% Arabic), so the baseline is what a typical
pipeline does without Asool: Tesseract `ara` plain text of each page, concatenated in page
order, cut into fixed 500-character chunks with 50 characters of overlap. Same embeddings,
same retrieval code and same LLM are used downstream; only data preparation differs.
"""

from __future__ import annotations

import json
import sqlite3

from pipeline.config import CORPUS_PAGES, DATA, INTER, page_id
from pipeline.normalize import normalize

SIZE, OVERLAP = 500, 50


def build() -> list[dict]:
    text, starts = "", []  # starts: (char offset, page id)
    for p in CORPUS_PAGES:
        pid = page_id(p)
        ocr = json.loads((INTER / "ocr" / f"{pid}.json").read_text())
        starts.append((len(text), pid))
        text += ocr["text"].replace("\n", " ") + " "
    rows = []
    pos, n = 0, 0
    while pos < len(text):
        chunk = text[pos : pos + SIZE]
        pid = [s for s in starts if s[0] <= pos][-1][1]
        rows.append(
            {
                "id": f"base-{n:04d}",
                "page_id": pid,
                "text": chunk,
                "text_norm": normalize(chunk),
                "char_start": pos,
            }
        )
        n += 1
        pos += SIZE - OVERLAP
    con = sqlite3.connect(DATA / "asool.db")
    for r in rows:
        con.execute(
            "INSERT INTO baseline_chunks VALUES (?,?,?,?,?)",
            (r["id"], r["page_id"], r["text"], r["text_norm"], r["char_start"]),
        )
        con.execute("INSERT INTO baseline_fts VALUES (?,?)", (r["id"], r["text_norm"]))
    con.commit()
    con.close()
    return rows
