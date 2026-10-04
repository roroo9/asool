# Progress

Deadline: **Tue Oct 6, 2026, 23:59 Riyadh time**. Target submission-ready: **Tue 18:00**.

## Time plan (Riyadh time)
| Phase | Planned window | Status |
|---|---|---|
| 0 Setup | Sun Oct 4, 07:00–09:00 | Done, approved |
| 1 Model bake-off (3 pages) | Sun 09:00–13:00 | Done ~11:00. At GATE 1 |
| 2 Full ingestion (30 pages) + baseline | Sun 13:00–22:00 | Done 11:05. At GATE 2 |
| 3 API | Mon Oct 5, 08:00–14:00 | Done Sun ~19:55. At GATE 3 |
| 4 Frontend + preview deploy | Mon 14:00 – Tue 08:00 | Started Sun ~20:30: API endpoints for Compare/Proof, page images, types, API client, i18n done. Screens not built yet |
| 5 Evaluation & hardening | Tue Oct 6, 08:00–14:00 | |
| 6 Ship | Tue 14:00–18:00 | |
| Buffer | Tue 18:00–23:59 | |

Human tasks in parallel: gold review of 12 more pages (992 phrases, Sun), hadith gradings for ~5 non-Sahihayn hadiths (route pending), verify eval questions (Mon).

## Done
- Phase 0: repo skeleton, `uv` env, FastAPI, Next.js 16 (RTL Arabic), `normalize.py` + tests, public repo https://github.com/roroo9/asool.
- Owner amendments A–C recorded in `CLAUDE.md` §12 (editor_commentary, hadith grading rule, Quran reference, official test cases, Shamela, terminology, consensus gold set).
- Challenge documents read in full (`docs/challenge/`, gitignored). Track 04 success criterion, 12 official test cases, term glossary, judging weights captured in `CLAUDE.md` §12.0.
- Corpus rendered: printed pages 12–41 at 300 DPI (PNG + WebP), gitignored.
- Geometry lane: Tesseract 5.5.3 `ara` with word + line boxes on all 30 pages.
- Quran reference: Quranpedia mushaf 1 (Hafs, King Fahd print), 6236 ayahs. See `data/reference/quran/SOURCE.md`.
- Shamela book 2348 (تحقيق الفحل) pages 10–90 fetched as a review aid (gitignored).
- LLM wrapper with disk cache and usage log; page parser prompt `page_parse.v1` with the editor-commentary, two-column footnote and poetry rules.
- Consensus gold drafting + the Review screen `/review/gold` (disagreements only, line crops, one-key choice, edit, spot-check, structure step, progress bars).

## Decisions and findings
- **Edition:** `rs-mohaqaq.pdf` = 1956 (title page: editor مصطفى محمد عماره, القاهرة, emblem مطبعة دار إحياء الكتب العربية – عيسى البابي الحلبي). Year 1956 comes from the archive.org description, not the scan.
- **Page numbering:** PDF page N = printed page N.
- **Corpus:** printed pp. 12–41. Bake-off pages: 41 (footnotes + editor commentary), 30 (Quran), 20 (dense). Gold pages (15): 12 14 16 18 20 22 24 26 28 30 33 35 37 39 41.
- **archive.org text layer is unusable** (0% Arabic). Baseline and Reader A use our own Tesseract `ara`.
- **dorar.net blocks this machine** (Cloudflare), including the API docs (article/389). Not circumvented. Route pending owner decision.
- **King Fahd Complex developer data (qurancomplex.gov.sa/quran-dev, Hafs v3.0) is the primary Quran reference.** An earlier check wrongly concluded it had no text (the link search missed the developer files). Quranpedia is the fallback.
- **Gemini billing is not possible in Saudi Arabia in time** (reseller CNTXT). Paid model calls go through OpenRouter ($10 limit).
- **Reader C on the 12 remaining gold pages = Surya OCR 2 (local).** Mistral was not possible.

## People
- Gold set reviewer: rawan, team member, native Arabic speaker.

## Phase 1 results (GATE 1)
- Gold review of pages 41, 30, 20 complete: 237 human decisions, 21 spot-checks, 0 errors (after fixing a review-screen bug that recorded unchanged confirmations as "wrong").
- Bake-off: Gemini 3.1 Pro + prompt v2 chosen (strict CER 2.3%, loose 0.4%, footnote-link F1 1.00, block types 100%, $0.139/page). See docs/MODEL_SELECTION.md.
- King Fahd developer data (Hafs v3.0) is now the primary Quran reference; all page-30 verses verify as exact.
- Drafts ready for the 12 remaining gold pages (Surya as Reader C): 992 disputed phrases.
- OpenRouter test: Gemini 3.1 Pro OK, $0.0012. Spend: Anthropic $2.66/$5, OpenRouter $1.62/$10.
- Blocker: dorar.net blocks this machine (Cloudflare), including the API docs page.

## Phase 2 results (GATE 2)
- Index: 30 pages, 535 blocks, 273 footnotes (all linked by exact marker), 17 Quran verses (all exact vs King Fahd text), 45 hadith units (41 in Sahihayn, 3 al-Tirmidhi needing a grading, 1 whose takhrij is on p.42 outside the corpus), 56 chunks (53 matn, 3 editor commentary), 90 baseline chunks, embeddings (Gemini Embedding 2).
- Review queue: 8 block items (4 Quran-mismatch false flags were removed by fixing detection) + 4 page-level completeness flags (2 real Gemini errors: p39 footnote 7, p15 footnote 1).
- Gold disputes for 12 pages after rule v2: 912.

## Phase 3 results (GATE 3)
- Endpoints: /health (with budget), /books, /pages/{id}, /pages/{id}.webp, /passages/{id}, /search (asool|baseline), /answer, /eval/summary, /review (+resolve), /review/gold/*, /review/hadith/*, public /api/v1/search and /api/v1/passages/{id}, OpenAPI at /docs.
- Answer pipeline: cache (versioned) -> level classify -> quoted-verse check -> level D referral -> hybrid retrieval -> support gate -> grounded generation (answer.v2) -> verbatim quote verification -> response. Budget guard: daily cap on serving spend -> fallback model; hard stop -> passages only; per-IP rate limit.
- Live demo (curl): answered with 3/3 verified quotes (conditions of tawbah), abstention (travel prayer, not in corpus), referral (personal marriage case), misquoted verse gently corrected (2/2 verified), nonexistent hadith request refused, consensus question answered with "no consensus reported in the passages".
- Fixed during Phase 3: footnote markers inside passages broke verbatim verification (markers are now ignored on both sides); verse candidates for short misquotes.

## Known issues
- Claude Opus marks two-column footnotes as `column: 0`; order is still correct. Column geometry will come from the fusion step.
