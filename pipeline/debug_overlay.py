"""GATE 2 debug view: draw indexed blocks over the page image (gitignored output).

    uv run python -m pipeline.debug_overlay 20 28 30 35 41
Colors: body blue, hadith magenta, quran green, footnote orange, editor commentary brown,
heading red, poetry teal. Dashed = position from the vision model only (OCR did not
confirm). Grey lines = footnote links (marker -> footnote). Red frame = review flag.
"""

from __future__ import annotations

import json
import sqlite3
import sys

from PIL import Image, ImageDraw

from pipeline.config import DATA, PAGES, page_id

COL = {
    "body": (40, 90, 220),
    "hadith": (190, 40, 190),
    "quran": (20, 150, 60),
    "footnote": (240, 130, 0),
    "editor_commentary": (140, 80, 30),
    "heading": (220, 30, 30),
    "poetry": (0, 150, 150),
}
OUT = DATA / "debug"


def draw(printed: int) -> str:
    pid = page_id(printed)
    con = sqlite3.connect(DATA / "asool.db")
    con.row_factory = sqlite3.Row
    blocks = list(con.execute("SELECT * FROM blocks WHERE page_id=? ORDER BY ord", (pid,)))
    links = list(con.execute("SELECT * FROM footnote_links WHERE page_id=?", (pid,)))
    flagged = {
        r[0] for r in con.execute("SELECT block_id FROM review_items WHERE page_id=?", (pid,))
    }
    im = Image.open(PAGES / f"{pid}.png").convert("RGB")
    d = ImageDraw.Draw(im, "RGBA")
    centers = {}
    for b in blocks:
        rects = json.loads(b["rects"] or "[]")
        c = COL.get(b["type"], (120, 120, 120))
        for r in rects:
            d.rectangle(r, outline=c + (255,), width=4 if b["lanes_agree"] else 2, fill=c + (28,))
        if rects:
            bb = json.loads(b["bbox"])
            centers[b["id"]] = ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
            d.text((bb[2] + 6, bb[1]), str(b["ord"]), fill=c + (255,))
            if b["id"] in flagged:
                d.rectangle(
                    [bb[0] - 8, bb[1] - 8, bb[2] + 8, bb[3] + 8], outline=(220, 0, 0, 255), width=3
                )
    for ln in links:
        a, f = centers.get(ln["anchor_block_id"]), centers.get(ln["footnote_block_id"])
        if a and f:
            d.line([a, f], fill=(90, 90, 90, 160), width=3)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{pid}.png"
    im.resize((im.width // 2, im.height // 2)).save(p)
    return str(p)


if __name__ == "__main__":
    for a in sys.argv[1:]:
        print(draw(int(a)))
