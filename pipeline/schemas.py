"""Pydantic models + JSON schema for VLM page parsing (prompt page_parse.v1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BlockType = Literal[
    "heading",
    "body",
    "footnote",
    "editor_commentary",
    "quran",
    "hadith",
    "poetry",
    "page_header",
    "page_number",
    "marginalia",
    "other",
]
AuthorRole = Literal["matn", "editor", "unknown"]


class ParsedBlock(BaseModel):
    order: int
    type: BlockType
    author_role: AuthorRole
    column: int = Field(description="0 = full width; 1 = rightmost column; 2 = next to its left")
    text: str
    footnote_markers_in_text: list[str]
    footnote_marker: str = Field(description="marker at the start of a footnote, else ''")
    continues_from_prev: bool
    continues_to_next: bool
    confidence: float
    issues: list[str]


class ParsedPage(BaseModel):
    page_number_printed: str = Field(description="as printed, '' if none")
    running_header: str = Field(description="'' if none")
    blocks: list[ParsedBlock]
    page_level_issues: list[str]


def _strict(schema: dict) -> dict:
    """Make a pydantic JSON schema acceptable to both providers' structured output:
    inline $defs, every property required, additionalProperties false."""
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(dict(defs[node["$ref"].split("/")[-1]]))
            node = {k: walk(v) for k, v in node.items() if k not in ("title", "default")}
            if node.get("type") == "object":
                node["required"] = list(node.get("properties", {}).keys())
                node["additionalProperties"] = False
            return node
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(schema)


PAGE_SCHEMA = _strict(ParsedPage.model_json_schema())
