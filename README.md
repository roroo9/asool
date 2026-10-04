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
