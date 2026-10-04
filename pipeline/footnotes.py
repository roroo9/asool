"""Footnote linking (CLAUDE.md §4.2): deterministic first, no LLM needed on this book.

1. Normalize markers ((١) / (1) / ¹ -> "1").
2. Exact: body marker <-> footnote with the same marker on the same page -> marker_exact (1.0).
3. A footnote block with no marker at the top of the footnote area that continues from the
   previous page -> attached to the previous page's last footnote (flagged).
4. Leftovers: k-th unmatched marker <-> k-th unmatched footnote -> marker_fuzzy (0.6, flagged).
5. Anything still unmatched is flagged for review.
anchor_char_offset = index of the marker inside the anchor block's text (for the UI arc).
"""

from __future__ import annotations

import re

from pipeline.normalize import normalize_marker

MARKER_RE = re.compile(r"\(\s*[\d٠-٩]{1,2}\s*\)|[¹²³⁴⁵⁶⁷⁸⁹]")
LEAD_RE = re.compile(r"^\s*(\(\s*[\d٠-٩]{1,2}\s*\)|[¹²³⁴⁵⁶⁷⁸⁹])")

ANCHOR_TYPES = {"body", "hadith", "quran", "heading", "poetry", "editor_commentary"}


def footnote_marker(block: dict) -> str | None:
    m = block.get("footnote_marker") or ""
    if not m:
        lead = LEAD_RE.match(block["text"])
        m = lead.group(1) if lead else ""
    return normalize_marker(m)


def link_page(blocks: list[dict], page_id: str) -> tuple[list[dict], list[dict]]:
    """Returns (links, flags). Blocks must carry 'id'."""
    anchors = []  # (marker, block, offset, raw)
    for b in blocks:
        if b["type"] in ANCHOR_TYPES:
            for m in MARKER_RE.finditer(b["text"]):
                anchors.append((normalize_marker(m.group(0)), b, m.start(), m.group(0)))
    notes = [b for b in blocks if b["type"] == "footnote"]
    by_marker: dict[str, dict] = {}
    unmarked = []
    for n in notes:
        k = footnote_marker(n)
        if k and k not in by_marker:
            by_marker[k] = n
        else:
            unmarked.append(n)
    links, flags = [], []
    used_notes: set[str] = set()
    left_anchors = []
    for k, b, off, raw in anchors:
        n = by_marker.get(k)
        if n and n["id"] not in used_notes:
            links.append(_link(page_id, raw, b, off, n, 1.0, "marker_exact"))
            used_notes.add(n["id"])
        else:
            left_anchors.append((k, b, off, raw))
    left_notes = [n for n in notes if n["id"] not in used_notes and footnote_marker(n)]
    for (_k, b, off, raw), n in zip(left_anchors, left_notes, strict=False):
        links.append(_link(page_id, raw, b, off, n, 0.6, "marker_fuzzy"))
        used_notes.add(n["id"])
        flags.append(
            {"block_id": n["id"], "reason": f"footnote linked by order, not marker ({raw})"}
        )
    for _k, b, _off, raw in left_anchors[len(left_notes) :]:
        flags.append({"block_id": b["id"], "reason": f"footnote marker {raw} has no footnote"})
    for n in notes:
        if n["id"] in used_notes:
            continue
        if not footnote_marker(n) and n.get("continues_from_prev"):
            links.append(
                {
                    "page_id": page_id,
                    "marker": "",
                    "anchor_block_id": None,
                    "anchor_char_offset": None,
                    "footnote_block_id": n["id"],
                    "confidence": 0.7,
                    "method": "continuation",
                }
            )
            flags.append({"block_id": n["id"], "reason": "footnote continues from previous page"})
        else:
            flags.append({"block_id": n["id"], "reason": "footnote without a marker in the text"})
    return links, flags


def _link(page_id, raw, b, off, n, conf, method) -> dict:
    return {
        "page_id": page_id,
        "marker": raw,
        "anchor_block_id": b["id"],
        "anchor_char_offset": off,
        "footnote_block_id": n["id"],
        "confidence": conf,
        "method": method,
    }


SPLIT_MARKERS = re.compile(r"(?=\(\s*[\d٠-٩]{1,2}\s*\))")


def split_merged_footnotes(blocks: list[dict]) -> list[dict]:
    """A parser sometimes returns several numbered footnotes as one block (e.g. «(١) … (٢) …»).
    Split them deterministically so each footnote can be linked to its marker. The split pieces
    share the parent's geometry and are marked `split_from` for transparency."""
    out = []
    for b in blocks:
        if b["type"] != "footnote":
            out.append(b)
            continue
        parts = [p.strip() for p in SPLIT_MARKERS.split(b["text"]) if p.strip()]
        if len(parts) <= 1 or not all(LEAD_RE.match(p) for p in parts[1:]):
            out.append(b)
            continue
        for k, part in enumerate(parts):
            nb = dict(b)
            nb["text"] = part
            lead = LEAD_RE.match(part)
            nb["footnote_marker"] = lead.group(1) if lead else ""
            nb["split_from"] = b.get("id")
            nb["sub"] = k
            out.append(nb)
    return out
