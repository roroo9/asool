"""Geometry lane + Reader A: Tesseract 5 `ara` with word and line boxes.

Output per page: data/intermediate/ocr/{page_id}.json
{
  "engine": "tesseract <version> ara psm4",
  "width", "height",
  "lines": [{"id", "bbox": [x0,y0,x1,y1], "text", "conf", "words": [{"text","bbox","conf"}]}],
  "text": full page text (lines joined with newlines, Tesseract order)
}
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytesseract
from PIL import Image

from pipeline.config import CORPUS_PAGES, INTER, PAGES, page_id

OUT = INTER / "ocr"
PSM = 4  # single column of variable-size text; best on these pages in a quick check


def ocr_page(printed: int, force: bool = False) -> dict:
    pid = page_id(printed)
    out = OUT / f"{pid}.json"
    if out.exists() and not force:
        return json.loads(out.read_text())
    im = Image.open(PAGES / f"{pid}.png")
    d = pytesseract.image_to_data(
        im, lang="ara", config=f"--psm {PSM}", output_type=pytesseract.Output.DICT
    )
    lines: dict[tuple, dict] = {}
    for i, word in enumerate(d["text"]):
        if not word.strip():
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
        ln = lines.setdefault(key, {"words": []})
        ln["words"].append(
            {"text": word, "bbox": [x, y, x + w, y + h], "conf": float(d["conf"][i])}
        )
    out_lines = []
    for n, (_, ln) in enumerate(sorted(lines.items())):
        ws = ln["words"]
        bbox = [
            min(w["bbox"][0] for w in ws),
            min(w["bbox"][1] for w in ws),
            max(w["bbox"][2] for w in ws),
            max(w["bbox"][3] for w in ws),
        ]
        # Tesseract emits Arabic words in logical (reading) order already.
        out_lines.append(
            {
                "id": f"L{n}",
                "bbox": bbox,
                "text": " ".join(w["text"] for w in ws),
                "conf": sum(w["conf"] for w in ws) / len(ws),
                "words": ws,
            }
        )
    res = {
        "engine": f"tesseract {pytesseract.get_tesseract_version()} ara psm{PSM}",
        "width": im.width,
        "height": im.height,
        "lines": out_lines,
        "text": "\n".join(ln["text"] for ln in out_lines),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def run(pages: list[int] = CORPUS_PAGES) -> None:
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(ocr_page, pages))


if __name__ == "__main__":
    run()
    print("ok")
