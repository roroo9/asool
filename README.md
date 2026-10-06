# أصول · Asool

**Verifiable answers from trusted Islamic books, traced to the exact line on the printed page.**

Asool turns scanned pages of a classical Islamic book into structured, searchable knowledge. A researcher, teacher or person presenting Islam asks a question in Arabic or English. Asool answers **only with word-for-word quotations from the book**. Each quotation is linked to its highlighted lines on the original page image, with the editor's footnotes attached, Quranic verses checked against the King Fahd Complex Mushaf, and hadith gradings taken only from approved sources. When the book does not answer, Asool says so. When a question needs a mufti, it refers the user to one.

- **Live demo:** https://asool-tawny.vercel.app
- **API:** https://asool-api-production.up.railway.app (OpenAPI at [`/docs`](https://asool-api-production.up.railway.app/docs))
- **Corpus:** *Riyad al-Salihin* by Imam al-Nawawi, 1956 Cairo edition (Dar Ihya' al-Kutub al-'Arabiyya) with word explanations by Mustafa Muhammad Amara, printed pages 12–41 (chapters on sincerity, repentance and patience)
- **Full evaluation method and every number:** [`docs/EVALUATION.md`](docs/EVALUATION.md)

---

## Contents
1. [Problem and solution](#problem-and-solution)
2. [Competition relevance](#competition-relevance)
3. [Key features](#key-features)
4. [Technology stack and technical decisions](#technology-stack-and-technical-decisions)
5. [How it works](#how-it-works)
6. [Installation and setup](#installation-and-setup)
7. [How to test the project](#how-to-test-the-project)
8. [Project structure](#project-structure)
9. [Results and limitations](#results-and-limitations)
10. [Future improvements](#future-improvements)
11. [Team and contributions](#team-and-contributions)
12. [Acknowledgments and license](#acknowledgments-and-license)

---

## Problem and solution

**The problem.** Classical Islamic books are mostly available as scanned images. Plain OCR turns them into flat text:
- Arabic letters are misread.
- Footnotes are mixed into the main text.
- The editor's commentary is indistinguishable from the author's words.
- Nothing points back to the printed page.

A chatbot built on that text can misquote, attribute an editor's note to the author, repeat a corrupted verse, or invent a hadith. Whoever relies on it cannot easily check where a claim came from.

On this corpus, standard OCR (Tesseract `ara`) gets **27.9% of characters wrong** (with tashkeel) and links **no footnote** to its marker, measured on 12 human-verified pages.

**The solution.** Asool rebuilds the page as structured data before answering anything:
- **Typed blocks:** each page becomes text blocks in reading order: matn, hadith, Quran, footnote, editor commentary, poetry, heading. Each block has a precise box on the page image.
- **Footnotes:** linked to their markers, including two-column footnote areas.
- **Quran:** verses are verified against the King Fahd Complex Mushaf.
- **Hadith:** al-Nawawi's printed takhrij is kept with each hadith, and a grading appears only from approved data.
- **Answers:** made of verified quotations only. Generated explanation is visibly separate, and every quote leads back to the highlighted lines on the page.

**What makes the approach distinctive.**
- **Two reading lanes, fused.** A vision-language model reads and types the blocks; classical OCR supplies word positions. Where the two lanes disagree, the block is flagged rather than trusted.
- **Verification as a hard gate.** Every quotation shown is checked word for word against its source. On the final evaluation run: **0 fabricated quotations out of 172 shown.**
- **Scholarly structure is preserved.** The editor's voice is separated from al-Nawawi's text, footnotes travel with the text they explain, and a sentence never breaks across a page boundary.
- **Honest abstention and referral.** There is a support gate before generation. Level D questions (personal fatwa) always get a referral.

---

## Competition relevance

Built for the **AI Challenge: Serving Islamic Content** (Bathel Foundation, 2026), **Track 04: Knowledge and verification tools for those who present Islam**.

The track's success criterion asks whether a solution *improved the accuracy of reaching knowledge or verifying it, showed the source and the state of the evidence clearly and traceably, and distinguished what the sources support from what needs further verification or referral*. Asool's evidence for each part:

| Criterion | What Asool does | Measured result |
|---|---|---|
| Accuracy of reaching knowledge | Hybrid search over structured units; footnotes travel with their text | Right page in the top 5 for **100%** of 43 reviewed questions (baseline 84%); required footnote present for 8 of 9 (baseline 2 of 9) |
| Accuracy of verifying knowledge | Word-for-word quote verification; Mushaf check of every verse | **0 of 172** displayed quotes not found in their source |
| Source and evidence shown traceably | Every book quote linked to page, block and box; printed takhrij and grading beside each hadith | **151 of 151** book quotes traced to a page and a box |
| Supported vs. needs verification or referral | Abstention when unsupported; referral for personal cases; text from outside the book labeled as such | Abstention 11/11, referral 6/6, misquoted-verse correction 3/3 |

**Judging criteria.** The criteria and weights below are from the participant guide.

| Criterion | Weight | Where to look |
|---|---|---|
| Technical quality and real AI use | 25% | [How it works](#how-it-works); [technical decisions](#technology-stack-and-technical-decisions) |
| Benefit per track success criterion | 20% | [Results](#results-and-limitations), live `/proof` page |
| Reliability and scientific safety | 15% | Quote verification, abstention, referral, hadith grading, human review |
| Innovation and added value | 15% | Two-lane fusion, footnote linking, Mushaf-wide verse check; live `/compare` page |
| User experience and accessibility | 10% | Arabic-first right-to-left interface, phone layout, keyboard navigation, reduced motion |
| Operational realism | 10% | Measured costs, budget guard, fallbacks ([`docs/COSTS.md`](docs/COSTS.md), [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)) |
| Presentation and verifiability | 5% | All numbers produced by `eval/` scripts and shown on `/proof` |

The **12 official test cases** from the challenge's scientific package (p.6) are part of the evaluation. Their expected behaviour is quoted word for word, and **11 of 12 pass** on the final run.

---

## Key features

### Implemented (all live on the demo)
| Feature | Where | What it does |
|---|---|---|
| Grounded answers | `/ask` | An answer in two zones. **«نصوص المصدر»** holds verbatim quotes only, each labeled «متن الإمام النووي», «حاشية المحقق» or «تعليق المحقق», with a page chip. **«إيضاح مولَّد آليًا»** holds a short generated explanation. Hovering a quote draws a line to its highlighted lines on the page image. |
| Answer safety | `/ask` | Content level A–D. Abstention with the closest passages. Referral for personal cases. Refusal to compose a hadith. Correction of misquoted verses with surah and ayah. |
| Approved sources outside the book | `/ask` | For foundational questions the book does not cover (e.g. «هل القرآن من تأليف محمد ﷺ؟»), the answer can add Mushaf verses with their meaning from «التفسير الميسر», and definitions from the Encyclopedia of Translated Islamic Terminology. Both are labeled «من خارج الكتاب المفهرس» and verified like book quotes, with referrals to «بينات» and dorar.net. |
| Source Viewer | `/b/riyad1956/p/12` … `/p/41` | A zoomable page image. **X-ray** mode outlines blocks by type and draws footnote arcs. Each verse shows its Mushaf check and tafsir, and each hadith its printed takhrij and grading. A citation can be copied. |
| Compare | `/compare` | A before/after slider: plain OCR text against Asool's structured blocks on the same page. The same question can be run through both pipelines. |
| Proof | `/proof` | Every metric, computed from the result files: the model bake-off, held-out pages, gold-set review statistics, the 12 official cases and all failures. |
| Human review | `/review` | Gold-set review, hadith grading, question-set review and a queue of low-confidence blocks. Protected by a review code. |
| How it works | `/how` | One real page replayed through the pipeline stages. |
| Public read-only API | `/developers` | `GET /api/v1/search` and `GET /api/v1/passages/{id}`, with citations and page boxes. |
| Interface | all pages | Arabic-first and right to left, with an English toggle, light and dark themes, phone layout, keyboard navigation and reduced-motion support. |

### Not implemented (proposals only)
These are listed in [Future improvements](#future-improvements):
- multi-book ingestion and publisher accounts;
- additional languages beyond the Arabic/English interface;
- persistent storage for review decisions made on the live server.

---

## Technology stack and technical decisions

| Layer | Technology | Role in Asool | Used by |
|---|---|---|---|
| Frontend | **Next.js 16** (App Router), **React 19**, **TypeScript**, **Tailwind CSS 4** | Arabic right-to-left web app; `/api/*` is forwarded to the backend | All screens |
| Frontend | **react-zoom-pan-pinch** | Zoom and pan on the page image, with SVG overlays for highlights, X-ray boxes and footnote arcs | Source Viewer, Ask, Compare |
| Backend | **FastAPI** (Python 3.12+), **uvicorn**, **pydantic-settings** | Search, answer pipeline, page and passage data, review endpoints, public API | Every screen |
| Data | **SQLite** with **FTS5** (BM25), **numpy** vectors | The whole index: 30 pages, 535 blocks, 273 footnote links, 19 verse references, 45 hadith units, 53 search units | Search, answers, Source Viewer |
| AI: page parsing | **Gemini 3.1 Pro** via **OpenRouter**, prompt `page_parse.v2` | Reads each page image into typed blocks in reading order | Offline ingestion |
| AI: geometry | **Tesseract 5 `ara`** (pytesseract), **Gemini 3.8 Flash** for block boxes | Word positions for precise highlights; also the baseline | Offline ingestion, Compare |
| AI: answers | **Gemini 3.1 Pro** (answer), **Gemini 3.8 Flash** (classifier, fallback), **Gemini Embedding 2**, all via OpenRouter | Level classification, grounded generation, query embeddings | Ask |
| Search | Hybrid **BM25 + embeddings** with reciprocal-rank fusion, plus an exact-phrase list and neighbouring units | Retrieval of book units and of Mushaf verses | Ask, `/api/v1/search` |
| Reference data | **King Fahd Complex Hafs v3.0** (developer data), **QuranEnc** «التفسير الميسر», **HadeethEnc API**, **Encyclopedia of Translated Islamic Terminology** | Verse verification and meaning, hadith grades, term definitions | Ask, Source Viewer |
| Gold set (evaluation only) | Tesseract, **Claude Opus 5.5**, **Claude Fable 5.1**, **Surya OCR 2** | Independent readers for the human-verified reference pages | `eval/` |
| Deployment | **Railway** (Docker, always on), **Vercel**, **GitHub Actions** | API container in Amsterdam, website on a global network, uptime check every 30 minutes | Live demo |
| Tooling | **uv**, **pytest** (53 tests), **ruff**, **PyMuPDF**, **rapidfuzz**, **jiwer** | Environment, tests, PDF rendering, fuzzy alignment, CER/WER | Development, ingestion, evaluation |

### Key technical decisions
- **The page parser was chosen by measurement, not reputation.**
  - Ten systems were compared on 3 bake-off pages against the human-verified gold set.
  - Gemini 3.1 Pro with the revised prompt had the lowest character error rate among eligible systems: **2.2%** with tashkeel. Gemini 3.1 Pro with the first prompt scored 4.3% and Gemini 3.8 Flash 4.5%.
  - The choice was re-checked on 12 held-out pages: 3.5% against 5.6% for the first prompt.
  - Claude models scored lower, but they were gold-set readers, so they were not eligible. See [`docs/MODEL_SELECTION.md`](docs/MODEL_SELECTION.md).
  - Trade-off: about **$0.15 per page** to parse.
- **OpenRouter for all model calls.** Direct Gemini billing could not be set up from Saudi Arabia within the challenge window. OpenRouter also keeps the code provider-agnostic: model roles are configuration in `api/settings.py`.
- **Paid embeddings with a keyword fallback.** Query embeddings go through OpenRouter, so judging does not depend on free-tier limits. If the embedding call fails, search continues with BM25 and says so.
- **Two lanes instead of one model.** The vision model reads Arabic well but places text imprecisely; OCR places words precisely but misreads Arabic. Fusing them gives readable text *and* exact highlights, and disagreement becomes a review flag.
- **SQLite and numpy instead of a vector database.** The corpus is small (53 units), so a file-based index keeps the backend simple, fast and dependency-free. Trade-off: a much larger library would need a dedicated search service.
- **Railway for the API, Vercel for the website.** The API needed an always-on server with no idle sleep or cold start, which Railway provides as a Docker container. Vercel hosts the Next.js site and serves the page images only from the deployment, never from GitHub. An idle test showed first requests after 20 minutes of inactivity answered in 0.3–1.4 s.
- **Approved references only.** The Mushaf text, tafsir, hadith grades and term definitions all come from sources named in the challenge's scientific package. A model never generates a verse meaning or a hadith grading.

---

## How it works

**User flow.**
1. **Question:** the user asks a question on `/ask`.
2. **Classification:** a small model assigns a content level from the scientific package: A (stable basics), B (concepts and explanation), C (scholarly disagreement) or D (a ruling on a personal case).
   - **Level D:** the user receives a referral and general passages only, and the flow stops here.
3. **Verse check:** if the question quotes a verse, it is checked against the whole Mushaf. A misquote gets a gentle correction card with the closest verses and their meaning.
4. **Search:** the book is searched (keywords + meaning). Neighbouring hadiths of the same chapter and page are added, so every condition of a ruling is available.
5. **Support gate:** if no passage supports the question well, Asool abstains and shows the closest passages, with no generation.
6. **Generation:** the model writes an answer using only the passages. For foundational questions the book does not cover, it may also use labeled verses and definitions from approved sources.
7. **Verification:** every quotation is checked word for word against its source. Unverified quotes are removed, and if more than half fail, the answer is withdrawn.
8. **Display:** the user sees the verified quotes with their origin labels, the generated explanation, and the page image with the quote highlighted.

**Offline pipeline (run once per book).** `uv run python -m pipeline.run_all`
1. **Rasterize:** pages are rendered at 300 DPI.
2. **Read:** the page parser reads typed blocks; Tesseract and a box model supply positions.
3. **Fuse:** the two lanes are combined into precise boxes.
4. **Structure checks:**
   - Footnotes are linked to their markers and put in reading order.
   - A completeness check makes sure every printed line is covered.
   - The editor's commentary is linked to the hadith it explains.
5. **Annotate:** verses are verified against the Mushaf, and hadith get their takhrij and grading.
6. **Index:** search units that never cut a sentence across pages are embedded and indexed.

Every model call is cached on disk, so a rerun is free and deterministic.

---

## Installation and setup

### What was tested
The steps below were run end to end on **macOS** from a fresh clone of this repository: install, reference downloads, page images, all 53 tests, backend, website, a search and an answer. They were **not** tested on Linux or Windows, although nothing in them is macOS-specific apart from `brew`.

### Prerequisites
| Tool | Version | Needed for |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | recent | Python environment (it installs Python 3.12+ if needed) |
| [Node.js](https://nodejs.org/) | **20.9 or newer** (tested with 25) | Website |
| git, curl | any | Clone and downloads |
| Tesseract 5 with Arabic (`brew install tesseract tesseract-lang`) | 5.x | **Only** for re-ingesting pages; not needed to run the app |

### 1. Clone and install
```bash
git clone https://github.com/roroo9/asool.git
cd asool
uv sync
cp .env.example .env
```

### 2. Environment variables (`.env`)
| Variable | Required? | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | Recommended | Answers, question classification and query embeddings ([get a key](https://openrouter.ai/keys)). **Without it the app still runs:** search uses keywords only, precomputed answers are served, and a new question shows the closest passages instead of a generated answer. |
| `REVIEW_TOKEN` | Optional | Access code for `/review` screens. Empty means the review screens are open, which is fine on your own laptop. |
| `CORS_ORIGINS` | Optional | Browser origins allowed to call the API directly. Default `http://localhost:3000`. |
| `DAILY_BUDGET_USD`, `OPENROUTER_BUDGET_USD`, `HARD_BUDGET_USD`, `ANSWER_RATE_LIMIT_PER_HOUR` | Optional | Spending guard and per-IP rate limit. Defaults are in `.env.example`. |
| `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | Optional | Only for re-running the extraction bake-off and gold-set readers. |

Example `.env` (placeholders only):
```bash
OPENROUTER_API_KEY=your-openrouter-key
REVIEW_TOKEN=choose-a-review-code
```

### 3. Reference data and page images
None of these files are stored in the repository. Each script downloads them from its official source.
```bash
./scripts/fetch_references.sh       # King Fahd Complex Hafs v3.0 + «التفسير الميسر» (QuranEnc)
curl -fsSL -o data/index/quran16.npy   https://github.com/roroo9/asool/releases/download/data-v1/quran16.npy
curl -fsSL -o data/index/quran_ids.json https://github.com/roroo9/asool/releases/download/data-v1/quran_ids.json
./scripts/fetch_page_images.sh      # downloads the 1956 scan from archive.org, renders pages 12–41 locally
```
- The two `curl` lines fetch the Mushaf verse-search vectors from this project's [GitHub release `data-v1`](https://github.com/roroo9/asool/releases/tag/data-v1).
- Without them, verse search falls back to word matching.
- Page images are created locally and stay git-ignored.

### 4. Run
Terminal 1, the backend:
```bash
uv run uvicorn api.main:app --port 8000
```
Terminal 2, the website:
```bash
cd web
npm ci
npm run dev
```
Open http://localhost:3000. The API documentation is at http://localhost:8000/docs. To point the website at a different backend, set `API_URL` before starting it (default `http://localhost:8000`).

### 5. Tests
```bash
uv run pytest
```
The 53 tests cover:
- Arabic normalization, footnote linking and hadith units;
- Quran matching, including unmarked verses;
- quote verification, gold-set rules and chunking across pages;
- the commentary-to-hadith link and the approved-dictionary path.

### Optional: reproduce the evaluation
These steps use the committed results and caches, and some make paid model calls. They were run during development, not in the fresh-clone test.
```bash
uv run python -m eval.run_eval retrieval          # Asool vs. baseline retrieval (free with cached embeddings)
uv run python -m eval.heldout_eval                # extraction accuracy on the 12 held-out gold pages
uv run python -m eval.bakeoff                     # model bake-off on 3 pages
uv run python -m eval.run_eval answers --runs 1   # full answer pipeline, about $0.03 per new question
uv run python -m eval.report                      # writes data/eval/results/summary.json (shown on /proof)
```

### Optional: re-ingest the pages
This needs the PDF from step 3, Tesseract, and an OpenRouter key. Cached model calls are reused.
```bash
uv run python -m pipeline.run_all
```

---

## How to test the project

On the live demo (https://asool-tawny.vercel.app) or locally, in about five minutes:

1. **A complete answer.** Ask «هل يقبل الله التوبة في آخر العمر؟».
   - Expect three hadiths from p.19, each labeled «متن الإمام النووي» with its takhrij and grading. Ibn Umar's hadith shows «حسن · HadeethEnc».
   - Expect the editor's footnote «تصل روحه حلقومه», labeled «حاشية المحقق», with the badge for al-Nisa 4:18.
   - Hover or tap a quote to see its lines highlighted on the page image.
2. **Abstention.** Ask «ما حكم صيام يوم عرفة لغير الحاج؟». The topic is outside the indexed pages, so expect a calm abstention with the closest passages.
3. **Referral.** Ask «حلفت بالطلاق على زوجتي إن خرجت من البيت ثم خرجت، فهل وقع الطلاق؟». This is a personal case, so expect a referral to a qualified scholar, with no ruling.
4. **Misquoted verse.** Ask «قال الله تعالى ﴿إن الله يحب الصابرين﴾، فما معنى هذه الآية؟». Expect a gentle correction showing Āl ʿImrān 146 as the closest verse, plus two others, with their meanings from «التفسير الميسر».
5. **Foundational question.** Ask «هل الإسلام انتشر بالسيف؟». Expect al-Baqara 256 with its tafsir, labeled «من خارج الكتاب المفهرس», a statement that the book does not cover the history, and referrals to «بينات» and dorar.net.
6. **The page itself.** Open `/b/riyad1956/p/41` and switch on **X-ray** to see block types, the two-column footnotes and the footnote arcs.
7. **Compare and Proof.** Drag the slider on `/compare`, then check every number on `/proof`.
8. **Public API.**
   ```bash
   curl "https://asool-api-production.up.railway.app/api/v1/search?q=%D8%B4%D8%B1%D9%88%D8%B7%20%D8%A7%D9%84%D8%AA%D9%88%D8%A8%D8%A9&k=3"
   ```

**Note on speed:** questions 1–5 above are precomputed, so they answer in about a second. A new question takes about 20 seconds, the time the model needs to write a fresh, verified answer.

---

## Project structure

```
asool/
├── api/                    FastAPI backend
│   ├── main.py             endpoints (search, answer, pages, passages, eval, review, public API)
│   ├── answer.py           answer pipeline: classify → verse check → search → gate → generate → verify
│   ├── search.py           hybrid BM25 + embedding search with reciprocal-rank fusion
│   ├── approved.py         approved sources outside the book (Mushaf search, tafsir, terminology)
│   ├── budget.py           spending guard and rate limit
│   ├── prompts/            versioned prompts (answer.v4, level_classify.v3, …)
│   └── tests/
├── pipeline/               offline ingestion
│   ├── run_all.py          the whole pipeline, cached and resumable
│   ├── vlm_parse.py, vlm_boxes.py, ocr_geometry.py, fuse.py    two-lane reading and fusion
│   ├── footnotes.py, structure_checks.py, completeness.py      structure and integrity checks
│   ├── quran.py, quran_search.py, hadith.py                    Quran verification, verse search, hadith
│   ├── gold_consensus.py, gold_locate.py                       gold-set drafting for human review
│   └── prompts/            page_parse.v2, block_boxes.v1
├── web/                    Next.js website (src/app: ask, b/[book]/p/[page], compare, proof, review, how, developers)
├── eval/                   bake-off, held-out, retrieval, answer evaluation and report
├── data/
│   ├── asool.db            the index (SQLite)
│   ├── index/              embedding vectors
│   ├── gold/               human-verified gold pages and review records
│   ├── eval/               questions, reviewer decisions and requirements, results
│   ├── answers/            precomputed answers
│   └── reference/          glossary, terminology entries, Quran source notes
├── scripts/                reference and page-image downloads
├── docs/                   EVALUATION, MODEL_SELECTION, COSTS, DEPLOYMENT, PROGRESS
├── Dockerfile, railway.json    API container (Railway)
└── SOURCES_AND_LICENSES.md
```

---

## Results and limitations

### Results
All figures come from `data/eval/results/` and are shown on the live `/proof` page. The method is in [`docs/EVALUATION.md`](docs/EVALUATION.md).

**Reading the page.** The 12 held-out pages were never used to choose the model or tune the prompt.

| | Asool | Baseline (Tesseract) |
|---|---|---|
| Character error rate with tashkeel | **3.5%** | 27.9% |
| Character error rate, letters only | **0.4%** | 20.8% |
| Footnotes linked to markers (F1) | **0.96** | 0.00 |
| Block types correct | 98.6% | n/a |

**Finding and answering.** 66 questions were drafted by the AI agent and reviewed by a human (58 approved, 8 edited, 20 notes turned into automatic checks). They include the 12 official cases.

| | Result |
|---|---|
| Right page in the top 5 (43 answerable) | **100%** (baseline 84%) |
| Correct behaviour with every reviewer requirement (final clean run) | **63 of 66 (95%)** |
| Official test cases | **11 of 12** |
| Displayed quotes not found in their source | **0 of 172** |
| Book quotes traced to page and box | 151 of 151 |

**Gold set.** 15 pages and 4,483 words, with 964 decisions made by a human reviewer. Spot-checks of auto-accepted words found 0 errors in 82 words where all readers agreed.

**Operations.**

| Item | Cost |
|---|---|
| Parsing a page | about $0.165 |
| A new answer | about $0.03 |
| A cached answer | $0 |

The API answered first requests after 20 minutes of inactivity in under 1.5 s.

### Limitations
- **Scope:** 30 pages of one book in one genre. The gold set has 15 pages and a single reviewer.
- **Three reviewed questions fail on citation completeness.**
  - `hostile-03`: a required hadith is never retrieved for that wording.
  - `official-10`: two of three required texts are not retrieved.
  - `ans-13`: one of two explanatory footnotes is quoted.
- **Colloquial questions:** on a separate set of 15 colloquial questions (drafted by the AI agent, **not** human-reviewed), retrieval alone loses its advantage: 85% against 85% for the baseline. The full pipeline still answers 14 of 15 correctly, because it rewrites the question into the book's vocabulary.
- **Reviewer bias:** gold-set Reader B (Claude) was the reviewer's default option, so Claude's extraction scores are inflated, and Claude was not eligible as the parser.
- **Style:** tone and gentleness are not scored automatically; they need human reading.
- **Review data on the live server:** decisions made on `/review` there are not persisted across redeploys. The reviews in this repository were done locally.
- **External service dependencies.**

  | Service | What depends on it | When unavailable |
  |---|---|---|
  | OpenRouter (Gemini models) | New answers and query embeddings | Keyword search, cached answers and closest passages still work |
  | qurancomplex.gov.sa | King Fahd Mushaf data, at build time | Documented fallback: the Quranpedia Mushaf |
  | QuranEnc | Tafsir text, at build time | The verse card links to quranenc.com instead |
  | archive.org | Page images, only when running locally | n/a |

  The live deployment bundles the reference files, because Railway's network cannot reach qurancomplex.gov.sa.
- **Budget:** live answering stops at a $38 OpenRouter limit, with a $3 daily cap and a cheaper fallback model. Above the limit, the site shows passages only.

---

## Future improvements
These are proposals, not built:
- **Better query expansion** for questions whose required passage is not retrieved (the three remaining failures).
- **More books and editions,** with the same gold-set and review workflow.
- **Persistent storage** for review decisions made on the live server.
- **A larger human-reviewed question set,** including colloquial and non-Arabic questions.
- **More languages** in the interface and answers, using the approved terminology equivalents.

---

## Team and contributions
- **rawan.** Project owner:
  - product and scholarly decisions;
  - review of the 15-page gold set (964 decisions) and the hadith gradings;
  - review of the 66-question evaluation set.

The code, pipeline and evaluation were built with **Claude Code**, an AI coding agent, under rawan's direction, during the challenge window (Oct 4–6, 2026).

---

## Acknowledgments and license

**Sources and tools.** Full details and terms are in [`SOURCES_AND_LICENSES.md`](SOURCES_AND_LICENSES.md).
- **Book:** *Riyad al-Salihin*, Imam al-Nawawi (public domain). Scan from archive.org (item `rsnawwy`). The editor's notes and the 1956 typesetting have unverified copyright status, so the PDF and page images are **not** in this repository.
- **Quran:** King Fahd Glorious Quran Printing Complex, developer data (Hafs v3.0). «التفسير الميسر» is accessed through QuranEnc (Encyclopedia of the Translated Meanings of the Holy Quran).
- **Hadith and terminology:** HadeethEnc (Encyclopedia of Translated Prophetic Hadiths), dorar.net (human entry only), and the Encyclopedia of Translated Islamic Terminology. Referrals point to «بينات: أسئلة وأجوبة عن الإسلام» (dawa.center).
- **Models:** Gemini (Google) via OpenRouter; Claude (Anthropic) and Surya OCR for the gold set; Tesseract OCR.
- **Fonts:** IBM Plex Sans Arabic, Amiri and Amiri Quran (SIL Open Font License).

**License.** No open-source license has been chosen for this project yet, so all rights are reserved by the author. Third-party data and tools keep their own terms, listed in [`SOURCES_AND_LICENSES.md`](SOURCES_AND_LICENSES.md).
