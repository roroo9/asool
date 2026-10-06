# أصول · Asool

**Trusted Islamic books, turned into knowledge you can verify, down to the line on the printed page.**

Asool reads scanned pages of a classical Islamic book and turns them into structured, searchable knowledge. Every answer is built only from verified quotations. Each quotation is traced to the exact highlighted spot on the original printed page, with the editor's footnotes attached, Quranic verses checked against the King Fahd Complex Mushaf, and hadith gradings taken only from approved sources. When the sources do not answer a question, Asool says so. When a question needs a mufti, it refers the user to one.

Built for the **AI Challenge: Serving Islamic Content** (Bathel Foundation, 2026), **Track 04: Knowledge & Verification Tools for those who present Islam**.

| | |
|---|---|
| **Live demo** | _added at deployment_ |
| **API** | _added at deployment_ (`/docs` for OpenAPI) |
| **Corpus** | Riyad al-Salihin (Imam al-Nawawi), 1956 Cairo edition with word explanations by Mustafa Muhammad Amara, printed pages 12–41 |
| **Evidence** | Every number below is computed by the scripts in `eval/` and shown on the live `/proof` page. Full method and every disclosed change: [`docs/EVALUATION.md`](docs/EVALUATION.md) |

---

## Results at a glance

All figures are measured on this corpus. Each comparison is against a fair baseline: the same search code, the same embeddings and the same answer model, with only the data preparation changed (plain OCR text in fixed 500-character pieces).

### Reading the printed page (extraction)
Measured against a human-verified gold set of 15 pages. **12 of those pages were held out**, never used to choose the model or tune the prompt.

| 12 held-out pages | Asool | Baseline (Tesseract `ara`) |
|---|---|---|
| Character error rate, **with tashkeel** | **3.5%** | 27.9% |
| Character error rate, letters only | **0.4%** | 20.8% |
| Footnotes linked to their markers (F1) | **0.96** | 0.00 |
| Footnotes in reading order | **100% of pages** | n/a (flat text) |
| Block types correct (matn, hadith, verse, footnote, editor commentary…) | 98.6% | n/a |

### Finding the right source (retrieval)
43 answerable, human-reviewed questions, scored against the gold page.

| | Asool | Baseline |
|---|---|---|
| Right page in the top 5 results | **100%** | 84% |
| Rank of the first correct result (MRR) | **0.93** | 0.77 |
| The footnote the question depends on arrives with the text | **8 of 9** | 2 of 9 |

### Answering safely (full pipeline, final clean run)
66 questions drafted by the AI agent and **reviewed by a human** (58 approved, 8 edited, 20 notes turned into machine-checked requirements). They include the **12 official test cases** of the challenge's scientific package.

| | Result |
|---|---|
| Correct behaviour, with every reviewer requirement met | **63 of 66 (95%)** |
| The 12 official test cases of the scientific package | **11 of 12** |
| Quotations shown to users that are not word for word in their source | **0 of 172** (151 from the book, 21 from approved sources outside it) |
| Book quotations traced to a page and a box on the image | **151 of 151** |
| Abstains when the book has no answer | 11 of 11 |
| Consistency (three earlier runs, before the final fixes) | Same behaviour in 98% of questions; the runs passed 92%, 91% and 89% |
| Refers personal fatwa questions to a scholar | 6 of 6 |
| Corrects misquoted verses, with surah and ayah | 3 of 3 |

The remaining failures, the fixes made after looking at results, and a separate set of 15 **colloquial questions (agent-drafted, not human-reviewed)** are reported in [Limits](#limits-stated-plainly) and in [`docs/EVALUATION.md`](docs/EVALUATION.md). Nothing is hidden.

---

## What a user can do

| Screen | What it does |
|---|---|
| **Ask** (`/ask`) | An answer in two clearly separated zones. **«نصوص المصدر»** holds only verbatim quotations, each labeled with its author: «متن الإمام النووي», «حاشية المحقق» or «تعليق المحقق». **«إيضاح مولَّد آليًا»** holds a short generated explanation. Hovering a quote draws the **Source Thread**, a line from the sentence to the highlighted lines on the original page. |
| **Source Viewer** (`/b/riyad1956/p/19`) | The zoomable page image. **X-ray** mode outlines every block by type and draws arcs from each footnote marker to its footnote. Each verse shows its Mushaf check and its meaning from an approved tafsir. Each hadith shows al-Nawawi's printed takhrij and its grading. |
| **Compare** (`/compare`) | A before/after slider over the same page: flat OCR text against Asool's structured blocks. The same question can also be run through both pipelines side by side. |
| **Proof** (`/proof`) | Every metric in this README, computed from the result files: the model bake-off, the held-out re-measurement, gold-set review statistics, the 12 official cases with the package's exact wording, and all failures. |
| **Review** (`/review`) | Human-in-the-loop work: the gold-set review, hadith gradings, the question-set review, and a queue of low-confidence blocks. |
| **How it works** (`/how`) | One real page replayed through the pipeline stages, using the project's own intermediate data. |
| **Developers** (`/developers`) | A free, read-only public API: `GET /api/v1/search` and `GET /api/v1/passages/{id}`. |

The interface is Arabic-first and right to left, with an English toggle, light and dark themes, keyboard navigation and reduced-motion support.

---

## How it works

```
 OFFLINE (run once)                                                    ONLINE
 ┌─────────────┐  ┌──────────────────────┐  ┌──────────────────────┐   ┌──────────────────────────────┐
 │ 300-DPI page│─▶│ SEMANTIC LANE        │─▶│ FUSION               │   │ classify level A–D           │
 │ image       │  │ Gemini 3.1 Pro reads │  │ blocks ↔ OCR words   │   │ → D: referral, no ruling     │
 └─────────────┘  │ typed blocks         │  │ → precise boxes      │   │ → verse check (whole Mushaf) │
        │         └──────────────────────┘  └──────────┬───────────┘   │ → hybrid search + neighbours │
        │         ┌──────────────────────┐             ▼               │ → support gate (abstain)     │
        └────────▶│ GEOMETRY LANE        │  footnote linking · Quran   │ → grounded generation        │
                  │ Tesseract words +    │  verification · hadith +    │ → word-for-word verification │
                  │ VLM block boxes      │  takhrij + grading ·        │   of every quote             │
                  └──────────────────────┘  completeness check ·      │ → answer with page highlights │
                                            structure-aware units      └──────────────────────────────┘
```

**1. Two lanes, fused.** Vision-language models read Arabic well but place text imprecisely; classical OCR is the reverse. The parser (Gemini 3.1 Pro, prompt `page_parse.v2`) outputs typed blocks in reading order with footnote markers preserved. Each block is aligned to OCR words, so its highlight covers the exact printed lines. When the two lanes disagree, the block is flagged, not trusted.

**2. Structure that matters for scholarship.**
- **Footnotes:** linked to their markers, including two-column footnote areas and footnote groups split around other content.
- **The editor's voice:** commentary («ما نأخذه من هذا الحديث») is kept apart from al-Nawawi's text. It is labeled, chunked separately and linked to the hadith it explains.
- **Units:** follow the book's structure. A unit is a hadith with its narration, takhrij and footnotes, and never cuts a sentence across a page break. Long units are searched in overlapping windows but read as a whole.

**3. Completeness check.** Every printed line found by OCR must be covered by the extracted text. Pages with uncovered lines go to human review and are never indexed silently. This check caught a real parser error on p.39, which was confirmed against the print and corrected.

**4. Quran verification.** Every verse, including verses quoted without ﴿ ﴾ inside the editor's footnotes, is matched word by word against the **King Fahd Complex Mushaf (Hafs v3.0, developer data)**.
- **Exact and near matches:** shown as verified. Differences are highlighted, and the printed text is never altered.
- **Misquoted verses in questions:** checked against the whole Mushaf. The closest correct verses are shown gently, with surah and ayah.
- **Meaning:** a verse's meaning comes only from **«التفسير الميسر» (King Fahd Complex) via the QuranEnc API**, attributed, and never generated.

**5. Hadith: source and grading, never generated.** Al-Nawawi's printed takhrij is always shown. A grading appears only from approved data:
- «في الصحيحين (متفق عليه)», «في صحيح البخاري» or «في صحيح مسلم», taken from the takhrij itself;
- the **HadeethEnc** grade, when narrator and wording match;
- a human entry from **dorar.net**.

Anything else shows «الحكم غير متحقق في البيانات». A search result is never taken on trust: on p.19, the top dorar.net result for «ما لم يغرغر» was a *different*, fabricated hadith.

**6. Grounded answers with hard gates.**
- **Classification:** each question gets a content level (A–D, from the scientific package). Personal-case rulings (level D) always get a referral, never an answer.
- **Search:** hybrid BM25 + embeddings with reciprocal-rank fusion. Neighbouring hadiths of the same chapter and page are added, so every condition of a ruling reaches the model.
- **Support gate:** weak support leads to an abstention, without generation.
- **Verification:** every quotation is checked word for word against its source after normalization. Unverified quotes are removed, and the answer is withdrawn if more than half fail.
- **Foundational questions the book does not cover** (e.g. «هل القرآن من تأليف محمد ﷺ؟»): the package asks for an explanatory answer. Asool may add verses from the Mushaf with their tafsir, and definitions from the **Encyclopedia of Translated Islamic Terminology**. These are labeled «من خارج الكتاب المفهرس», are verified like book quotes, and come with the package's referrals («بينات», dorar.net). Mushaf verses are added only when the book's match is weak.
- **Term translation:** requests are answered from the approved dictionary, not generated.

---

## Evaluation method (summary)

- **Gold set, built without the evaluated model.**
  - Three independent readers per page: Tesseract, Claude Opus 5.5, and Claude Fable 5.1 or Surya OCR. **Gemini, the evaluated parser, is never a reader.**
  - A word is accepted automatically only if all readers agree; everything else is decided by a human reviewer, on a screen that shows the printed line with the disputed words highlighted.
  - **964 human decisions** were made over 4,483 words.
  - Random spot-checks of auto-accepted words found **0 of 82 errors** where all readers agreed, 1 of 48 for tashkeel-abstention words and 1 of 67 for Tesseract-abstention words. Both errors were tashkeel only, and both were corrected.
- **Model choice and honest re-measurement.**
  - Ten systems were compared on 3 bake-off pages. Gemini 3.1 Pro with prompt v2 scored 2.2% strict CER.
  - The choice was then re-measured on 12 held-out pages. The reading-accuracy gain of prompt v2 held: 3.5% against 5.6% for prompt v1.
  - Its two-column footnote ordering did not hold, so footnote order is now fixed deterministically.
- **Question set.**
  - 66 questions drafted by the AI agent and reviewed by a human.
  - The 12 official cases quote the package's expected behaviour word for word.
  - The reviewer's notes became automatic checks: required footnotes, required verses, every condition of a ruling, required referrals.
  - A separate set of 15 colloquial questions, agent-drafted and not reviewed, tests whether copying the book's wording overstates quality. It is never mixed into the reviewed numbers.
- **Independent re-verification.** The evaluator re-checks every displayed quotation against its own source, whether book, Mushaf, tafsir or terminology, and checks that every book quotation resolves to a page and a box.

Reproduce:
```bash
uv run python -m eval.run_eval retrieval            # Asool vs. baseline (cached embeddings, free)
uv run python -m eval.run_eval answers --runs 3     # real answer pipeline, about $0.03 per question per run
uv run python -m eval.heldout_eval                  # extraction on the 12 held-out gold pages
uv run python -m eval.bakeoff                       # model bake-off on 3 pages
uv run python -m eval.report                        # writes data/eval/results/summary.json, shown on /proof
```

---

## Reliability and safety, mapped to the scientific package

| Package principle | How Asool implements it |
|---|---|
| Reliability and attribution | Every quote is verified word for word and linked to book, edition, page, block and box |
| Definitive vs. ijtihad | Disagreement in the passages is shown without picking a winner; consensus is never claimed unless a passage states it |
| No independent fatwa | Level D questions get a referral and general passages only |
| Hallucination resistance | Support gate, word-for-word quote verification, and refusal to compose a hadith that is not in the sources |
| Quran and hadith integrity | Mushaf verification, approved tafsir, approved gradings only, printed takhrij always shown |
| Transparency | Source text and generated explanation are visibly separate; text from outside the book is labeled; AI assistance is stated |
| Translation and localization | Approved equivalents from the package's dictionary sample and the terminology encyclopedia (e.g. "Tawbah (repentance)", never "holy war" for jihad) |
| Privacy | No accounts, no personal data, no tracking |
| Human in the loop | Gold review, hadith grading, question review and a low-confidence block queue, all recorded with reviewer and date |

---

## Operations

**Measured costs** (`docs/COSTS.md`, from logged token counts):

| Item | Cost |
|---|---|
| Ingestion: parsing a page with Gemini 3.1 Pro, plus block boxes | about $0.165 per page, about $165 per 1,000 pages |
| One new answer: classification, generation and embedding | about $0.03 |
| Abstention or referral | about $0.001 |
| Cached answer (official cases, evaluation and demo questions are precomputed) | $0 |

**Budget guard.**
- The OpenRouter key limit is $40.
- Live answers stop at $38, with a $3 daily cap.
- At the daily cap the system falls back to Gemini 3.8 Flash. Above the hard stop, it shows search passages only, so a page never breaks.
- Evaluation and precompute stop at $23, so at least $15 stays for live use during judging (Oct 7–22).
- Answers are rate-limited per IP.

**Dependencies and fallbacks.**
- **Model provider:** OpenRouter, provider-agnostic, with model roles in `api/settings.py`.
- **Embeddings:** if they fail at query time, search continues with keywords only.
- **Quran reference:** the King Fahd developer data and the tafsir are downloaded at build time. If the download fails, the documented fallback is the Quranpedia Mushaf.
- **Hosting:** FastAPI on Render (always-on Starter plan) and Next.js on Vercel.
- **Page images:** served only from the deployment, never from GitHub.

**Maintenance.**
- New pages are ingested with `uv run python -m pipeline.run_all`. Every model call is cached, so reruns are free and deterministic.
- Flagged pages and blocks appear in `/review`.
- 53 automated tests run with `uv run pytest`.

---

## Run locally

Requirements: macOS or Linux, [uv](https://docs.astral.sh/uv/), Node 22+, Tesseract with Arabic (`brew install tesseract tesseract-lang`).

```bash
cp .env.example .env                 # add your own keys (never commit .env)
uv sync && ./scripts/fetch_references.sh   # King Fahd Mushaf data + التفسير الميسر (QuranEnc)
uv run python -m pipeline.quran_search     # Mushaf search vectors (about $0.04, once)
uv run pytest
uv run uvicorn api.main:app --port 8000    # API, http://localhost:8000/docs
cd web && npm install && npm run dev       # web, http://localhost:3000
```

The book PDF and page images are not in this repository (see below). Re-ingestion needs the scan from archive.org (`rsnawwy`, file `rs-mohaqaq.pdf`). The committed index (`data/asool.db`, `data/index/`) is enough to run search and answers.

## Repository layout

| Path | Contents |
|---|---|
| `pipeline/` | Offline ingestion: rasterize, OCR, VLM parse and boxes, fusion, footnotes, Quran, hadith, structure checks, completeness, chunking, index, baseline |
| `api/` | FastAPI: search, answer pipeline, approved sources, budget, review endpoints, public API; prompts are versioned in `api/prompts/` |
| `web/` | Next.js app (Arabic, right to left) |
| `eval/` | Bake-off, held-out, retrieval, answer and report scripts |
| `data/` | Gold set and review records, evaluation questions and results, index, reference metadata |
| `docs/` | Detailed evaluation, model selection, costs, progress log |

## Sources and licenses
Details in [`SOURCES_AND_LICENSES.md`](SOURCES_AND_LICENSES.md).
- **Book:** the matn is in the public domain (al-Nawawi died 676 AH). The editor's notes and the 1956 typesetting have unverified copyright status, so the PDF and page images are **excluded from this repository**. Page images are served only by the live deployment, to show citations.
- **Quran:** King Fahd Glorious Quran Printing Complex developer data (Hafs v3.0), downloaded at build time. «التفسير الميسر» is fetched through the QuranEnc API.
- **Hadith and terminology:** HadeethEnc API, dorar.net (human entry only, no scraping), and the Encyclopedia of Translated Islamic Terminology. All are approved platforms in the challenge's scientific package.
- **Fonts:** IBM Plex Sans Arabic, Amiri and Amiri Quran (SIL OFL).

## Limits stated plainly
- **Small corpus:** 30 pages of one book in one genre. The gold set has 15 pages and one reviewer.
- **Reviewer bias:** gold Reader B (Claude) was the reviewer's default option, so Claude's extraction scores are inflated, and Claude was excluded as the parser.
- **Answer failures in the reviewed set:** three of 66 in the final clean run, all about citation completeness.
  - `hostile-03`: a required hadith (Ibn ʿAbbās, p.16) was never retrieved for this wording.
  - `official-10`: two of three required texts were not retrieved, so only one was cited.
  - `ans-13`: one of two explanatory footnotes was quoted.
  - Passing more passages to the model (10 instead of 5) does not fix the first two; it needs better query expansion.
- **Colloquial wording:** with natural, colloquial phrasing, retrieval alone loses its advantage over the baseline (85% against 85%). The full pipeline still answered 14 of 15 correctly, because the question is rewritten into the book's vocabulary first. The one failure, `nat-05`, cited the right hadith but not its explanatory footnotes. This set was drafted by the AI agent and not human-reviewed.
- **Completeness check:** it cannot detect gaps shorter than one printed line.
- **Style:** behaviour and requirements are scored automatically. Tone and gentleness need human reading.
- **Proposed, not built:** multi-book ingestion, publisher accounts, more languages, and a broader human-reviewed question set.

## Team
Built during the challenge window (Oct 4–6, 2026). Gold-set, hadith-grading and question-set review: **rawan**.
