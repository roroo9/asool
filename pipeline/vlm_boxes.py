"""Second geometry signal: the VLM locates each already-transcribed block (box_2d, 0-1000).

Used by fusion when OCR alignment is weak (ornate Quran type, small footnotes). Cheap: the
output is only coordinates. Results: data/intermediate/boxes/{model_dir}/{page_id}.json
"""

from __future__ import annotations

import json

from api.llm import generate
from api.settings import settings
from pipeline.config import INTER, PAGES, page_id
from pipeline.vlm_parse import model_dir

PROMPT_VERSION = "block_boxes.v1"
SYSTEM = (INTER.parent.parent / "pipeline" / "prompts" / f"{PROMPT_VERSION}.md").read_text()
SCHEMA = {
    "type": "object",
    "properties": {
        "boxes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "order": {"type": "integer"},
                    "box_2d": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["order", "box_2d"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["boxes"],
    "additionalProperties": False,
}


def locate(printed: int, blocks: list[dict], model: str | None = None) -> dict[int, list[int]]:
    model = model or settings.box_model
    out = INTER / "boxes" / model_dir(model) / f"{page_id(printed)}.json"
    if out.exists():
        return {int(k): v for k, v in json.loads(out.read_text()).items()}
    listing = []
    for b in blocks:
        w = b["text"].split()
        head, tail = " ".join(w[:8]), " ".join(w[-5:]) if len(w) > 8 else ""
        listing.append(
            f"{b['order']}. [{b['type']}] «{head}» … «{tail}»"
            if tail
            else f"{b['order']}. [{b['type']}] «{head}»"
        )
    r = generate(
        stage="vlm_boxes",
        prompt_version=PROMPT_VERSION,
        model=model,
        system=SYSTEM,
        user="Blocks on this page:\n" + "\n".join(listing),
        image=PAGES / f"{page_id(printed)}.png",
        schema=SCHEMA,
        effort="medium",
        max_tokens=16000,
    )
    boxes = {b["order"]: b["box_2d"] for b in json.loads(r.text)["boxes"] if len(b["box_2d"]) == 4}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(boxes))
    return boxes
