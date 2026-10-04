# أصول · Asool

Asool turns scanned pages of trusted Islamic books into structured, verifiable knowledge.
Every search result and answer links back to the exact highlighted spot on the original printed page,
with footnotes attached, Quranic verses verified, and uncertain extractions flagged.

Built for the AI Challenge: Serving Islamic Content (Bathel Foundation, 2026), Track 04.

> Status: under construction. See `docs/PROGRESS.md`.

## Corpus
رياض الصالحين للإمام النووي, 1956 edition (دار إحياء الكتاب العربي), printed pages 12–41.
See `SOURCES_AND_LICENSES.md`. Book files are not in this repo.

## Run locally
Requirements: macOS/Linux, [uv](https://docs.astral.sh/uv/), Node 22+, Tesseract with Arabic (`brew install tesseract tesseract-lang`).

```bash
cp .env.example .env          # then fill in the keys
uv sync                       # Python deps
uv run pytest                 # tests
uv run uvicorn api.main:app --reload --port 8000   # API at http://localhost:8000/docs
cd web && npm install && npm run dev               # web at http://localhost:3000
```

## Repository layout
- `pipeline/` offline ingestion (page image → blocks → footnotes → Quran check → chunks → index)
- `api/` FastAPI backend
- `web/` Next.js frontend (Arabic, right-to-left)
- `eval/` evaluation scripts
- `data/` reference data, gold set, eval questions, index
- `docs/` progress, model selection, costs, limits

## Gold set: method, bias controls, spot-check
The gold set is the human-verified reference used to measure extraction quality. It covers 15 of the 30 corpus pages (printed pp. 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 33, 35, 37, 39, 41).

**Method (consensus-assisted human review).**
1. Each gold page is read by three independent readers:
   - Reader A: Tesseract 5 `ara` (classical OCR, run locally).
   - Reader B: Claude Opus 5.5 (vision-language model).
   - Reader C: Claude Fable 5.1 on the 3 bake-off pages; **Surya OCR 2** (open-source, run locally) on the other 12 pages.
2. A word is **auto-accepted only if all three readers agree** on its letters, and Readers B and C also agree on it exactly, diacritics included (Tesseract votes on letters only, because it does not read tashkeel reliably). Everything else goes to a human.
3. The human reviewer sees only the disputed phrases, each with the printed line cropped from the original page and the disputed words highlighted, and chooses a reading or types a correction (`/review/gold`).
4. A random 5% of auto-accepted words (weighted toward words with tashkeel) is shown to the reviewer as a spot-check.
5. The reviewer confirms the block types (body, hadith, Quran, footnote, editor commentary…) before the page is finalized.

**Bias controls.**
- **Asool's own page parser (Gemini) is never one of the gold readers**, so the gold set does not come from the model it evaluates.
- The review screen shows how many readers support a candidate, not which model produced it.
- Readers A and C are classical/open OCR engines with weaker tashkeel than the vision-language models, so **more disagreements reach human review**; auto-accept still requires all three readers to agree.
- Known limitation: Reader B (Claude) was the pivot reading and the reviewer's default option, so Claude scores are inflated against this gold set and Claude is not eligible as Asool's parser. Diacritic conventions may lean toward Claude's style.

**Spot-check results (bake-off pages).** 21 auto-accepted words checked, **0 wrong** (error rate 0%). A review-screen bug recorded these 21 confirmations as "wrong" although the reviewer left every word unchanged. The bug is fixed and the 21 records are reclassified with a note in the data (`correction_note`).

| Pages | Words | Auto-accepted | Human decisions | Spot-checked | Spot-check errors |
|---|---|---|---|---|---|
| 41, 30, 20 (bake-off) | 942 | 425 | 237 | 21 | 0 |
| 12 other pages | 3,541 | 1,221 | 992 (pending) | 61 (pending) | pending |

Shamela (book 2348, a different edition) is available to the reviewer as an independent text cross-check; page numbers differ, so it is never used as gold directly.
