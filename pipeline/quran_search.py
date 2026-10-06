"""Search the FULL King Fahd Mushaf by meaning (owner request, Oct 5).

Used only when a foundational question (level A/B) is not covered by the indexed book: the
answer may then quote verses from the approved Mushaf, labeled as outside the book. Verses are
found by hybrid search (dense embeddings of each ayah + word overlap, fused with RRF) and their
text always comes from the reference file, never from a model.

Vectors: data/index/quran.npy (+ quran_ids.json), built once by `build()` (~$0.04).
"""

from __future__ import annotations

import json
import math
from collections import Counter
from functools import lru_cache

import numpy as np

from pipeline.config import DATA
from pipeline.normalize import normalize
from pipeline.quran import load_index, reference_source

INDEX = DATA / "index"
RRF_K = 60


def _doc(a) -> str:
    return f"سورة {a.surah_name} آية {a.ayah}: {' '.join(a.words)}"


def build() -> int:
    from api.llm import embed

    idx = load_index()
    vecs = np.array(embed([_doc(a) for a in idx.ayahs], stage="embed/quran"), dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    INDEX.mkdir(parents=True, exist_ok=True)
    np.save(INDEX / "quran.npy", vecs)
    (INDEX / "quran_ids.json").write_text(json.dumps([[a.surah, a.ayah] for a in idx.ayahs]))
    return len(idx.ayahs)


@lru_cache(maxsize=1)
def _vectors() -> tuple[np.ndarray, list[tuple[int, int]]] | None:
    p = INDEX / "quran.npy"
    if not p.exists():
        return None
    ids = [tuple(x) for x in json.loads((INDEX / "quran_ids.json").read_text())]
    return np.load(p), ids


@lru_cache(maxsize=1)
def _idf() -> dict[str, float]:
    ayahs = load_index().ayahs
    df = Counter(w for a in ayahs for w in set(a.words))
    n = len(ayahs)
    return {w: math.log(n / c) for w, c in df.items()}


def search(query: str, qvec: np.ndarray | None, k: int = 5) -> list[dict]:
    """Top-k ayahs: {surah, ayah, surah_name, text, score, ref, quranpedia_url}."""
    idx = load_index()
    pos = {(a.surah, a.ayah): i for i, a in enumerate(idx.ayahs)}
    scores: dict[int, float] = {}
    # word overlap (IDF-weighted), on the imla'i spelling used for matching
    qw = set(normalize(query, "quran").split())
    idf = _idf()
    lex = sorted(
        ((sum(idf.get(w, 0) for w in qw & set(a.words)), i) for i, a in enumerate(idx.ayahs)),
        reverse=True,
    )[:30]
    for r, (s, i) in enumerate(lex):
        if s > 0:
            scores[i] = scores.get(i, 0) + 1 / (RRF_K + r + 1)
    v = _vectors()
    if v is not None and qvec is not None:
        mat, ids = v
        sims = mat @ qvec
        for r, j in enumerate(np.argsort(-sims)[:30]):
            i = pos[ids[j]]
            scores[i] = scores.get(i, 0) + 1 / (RRF_K + r + 1)
    out = []
    for i, s in sorted(scores.items(), key=lambda x: -x[1])[:k]:
        a = idx.ayahs[i]
        out.append(
            {
                "surah": a.surah,
                "ayah": a.ayah,
                "surah_name": a.surah_name,
                "text": a.text,
                "score": round(s, 5),
                "reference_source": reference_source(),
                "quranpedia_url": f"https://quranpedia.net/surah/{a.surah}/{a.ayah}",
            }
        )
    return out


if __name__ == "__main__":
    print(build(), "ayahs embedded")
