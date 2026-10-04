"""HadeethEnc (hadeethenc.com, «موسوعة الأحاديث النبوية») as a second hadith reference.

Approved platform in the challenge's scientific package (p.9). Public API, no key.
We download the Arabic title index once (≈45 requests, 1 req/s), match a printed hadith
against titles with fuzzy matching, and fetch full details only for the best candidates.
The match is a *reference* shown beside the hadith; it never overrides the book's text and
never produces a grading by itself. Low-similarity matches are not shown.
"""

from __future__ import annotations

import json
import time

import httpx
from rapidfuzz import fuzz

from pipeline.config import REF
from pipeline.normalize import normalize

API = "https://hadeethenc.com/api/v1"
DIR = REF / "hadeethenc"
INDEX = DIR / "index_ar.json"
UA = {"User-Agent": "Asool research tool (github.com/roroo9/asool)"}
MIN_SCORE = 80  # partial_ratio of the normalized title inside the printed hadith


def build_index() -> list[dict]:
    if INDEX.exists():
        return json.loads(INDEX.read_text())
    DIR.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    with httpx.Client(timeout=30, headers=UA) as c:
        roots = c.get(f"{API}/categories/roots/", params={"language": "ar"}).json()
        for cat in roots:
            page = 1
            while True:
                d = c.get(
                    f"{API}/hadeeths/list/",
                    params={
                        "language": "ar",
                        "category_id": cat["id"],
                        "page": page,
                        "per_page": 100,
                    },
                ).json()
                for h in d["data"]:
                    seen[h["id"]] = {"id": h["id"], "title": h["title"]}
                time.sleep(1)
                if page >= int(d["meta"]["last_page"]):
                    break
                page += 1
    rows = list(seen.values())
    INDEX.write_text(json.dumps(rows, ensure_ascii=False))
    return rows


def details(hid: str) -> dict:
    p = DIR / f"{hid}.json"
    if p.exists():
        return json.loads(p.read_text())
    r = httpx.get(
        f"{API}/hadeeths/one/", params={"language": "ar", "id": hid}, headers=UA, timeout=30
    )
    d = r.json()
    keep = {k: d.get(k) for k in ("id", "title", "hadeeth", "attribution", "grade")}
    keep["url"] = f"https://hadeethenc.com/ar/browse/hadith/{hid}"
    p.write_text(json.dumps(keep, ensure_ascii=False))
    time.sleep(1)
    return keep


def match(hadith_text: str, top: int = 3) -> list[dict]:
    """Best HadeethEnc entries for a printed hadith (verified against the full hadith text)."""
    idx = build_index()
    q = normalize(hadith_text)
    if len(q) < 15:
        return []
    scored = []
    for h in idx:
        t = normalize(h["title"])
        if len(t) < 10:
            continue
        s = fuzz.partial_ratio(t, q)
        if s >= MIN_SCORE:
            scored.append((s, h["id"]))
    out = []
    for s, hid in sorted(scored, reverse=True)[:top]:
        d = details(hid)
        full = fuzz.partial_ratio(normalize(d.get("hadeeth") or ""), q)
        # Confirm with the full text: the printed hadith and HadeethEnc's wording must overlap.
        both = fuzz.token_set_ratio(normalize(d.get("hadeeth") or ""), q)
        if max(full, both) >= 70:
            out.append(d | {"title_score": s, "text_score": round(max(full, both), 1)})
    return out


if __name__ == "__main__":
    print(len(build_index()), "titles")
    print(match("إنما الأعمال بالنيات، وإنما لكل امرئ ما نوى")[:1])
