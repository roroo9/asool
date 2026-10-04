"""Render corpus pages: 300-DPI PNG master (OCR/VLM input) + WebP for the web.

Idempotent: skips pages that already exist.
"""

from __future__ import annotations

import json

import pymupdf
from PIL import Image

from pipeline.config import CORPUS_PAGES, PAGES, PDF_PATH, page_id

DPI = 300
WEB_WIDTH = 1400


def rasterize(pages: list[int] = CORPUS_PAGES) -> list[dict]:
    PAGES.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(PDF_PATH)
    meta = []
    for printed in pages:
        pid = page_id(printed)
        png = PAGES / f"{pid}.png"
        webp = PAGES / f"{pid}.webp"
        if not png.exists():
            pix = doc[printed - 1].get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
            pix.save(png)
        im = Image.open(png)
        if not webp.exists():
            w = min(WEB_WIDTH, im.width)
            im.resize((w, round(im.height * w / im.width))).save(webp, "WEBP", quality=80)
        meta.append({"id": pid, "printed": printed, "width": im.width, "height": im.height})
    (PAGES / "pages.json").write_text(json.dumps(meta, indent=1))
    return meta


if __name__ == "__main__":
    print(len(rasterize()), "pages")
