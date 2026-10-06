"""Fetch definitions from the Encyclopedia of Translated Islamic Terminology (terminologyenc.com,
an approved platform in the challenge's scientific package, p.9) for the concepts Asool may need
to define when a foundational question is not covered by the indexed book.

Writes data/reference/terminologyenc/terms.json: {term: {id, url, ar: {...}, en: {...}}}.
Only the entries below are stored, each with its source URL. Polite: sequential, cached.
Usage: uv run python scripts/fetch_terminology.py
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from pipeline.normalize import normalize

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reference" / "terminologyenc"
API = "https://terminologyenc.com/api/v1"
WANTED = [
    "التوحيد", "الاجتهاد", "الإخلاص", "الجهاد", "التوبة", "الصبر", "النية", "الوحي",
    "القبلة", "العبادة", "الإسلام", "القرآن", "الخلاف", "الإجماع", "الفتوى", "السنة",
    "الكعبة", "الشريعة", "الابتلاء", "الطهور", "الهجرة",
]


def get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "Asool research tool"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def index() -> list[dict]:
    p = OUT / "index.json"
    if p.exists():
        return json.loads(p.read_text())
    cats = get(f"{API}/categories/list?language=ar")
    terms: dict[str, dict] = {}
    for c in cats:
        page = 1
        while True:
            d = get(f"{API}/terms/list?language=ar&category_id={c['id']}&page={page}&per_page=100")
            rows = d.get("data", []) if isinstance(d, dict) else []
            for t in rows:
                terms[t["id"]] = {"id": t["id"], "term": t["term"], "category": c["title"]}
            if len(rows) < 100:
                break
            page += 1
            time.sleep(0.2)
    OUT.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(list(terms.values()), ensure_ascii=False))
    return list(terms.values())


def _key(s: str) -> str:
    k = normalize(s).strip(" .")
    return k[2:] if k.startswith("ال") else k


def main() -> None:
    idx = index()
    by = {}
    for t in idx:
        by.setdefault(_key(t["term"]), []).append(t)
    out = {}
    for w in WANTED:
        cands = by.get(_key(w), [])
        if not cands:
            print("not found:", w)
            continue
        t = cands[0]
        ar = get(f"{API}/terms/one?id={t['id']}&language=ar")
        en = get(f"{API}/terms/one?id={t['id']}&language=en")
        out[w] = {
            "id": t["id"],
            "term": t["term"],
            "category": t["category"],
            "url": f"https://terminologyenc.com/ar/browse/term/{t['id']}",
            "ar": ar if isinstance(ar, dict) else None,
            "en": en if isinstance(en, dict) and en.get("term") else None,
        }
        print("ok:", w, t["id"])
        time.sleep(0.3)
    (OUT / "terms.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(len(out), "terms saved")


if __name__ == "__main__":
    main()
