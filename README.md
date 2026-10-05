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

**Reviewer:** rawan (team member, native Arabic speaker).

**Method (consensus-assisted human review).**
1. Each gold page is read by three independent readers:
   - Reader A: Tesseract 5 `ara` (classical OCR, run locally).
   - Reader B: Claude Opus 5.5 (vision-language model).
   - Reader C: Claude Fable 5.1 on the 3 bake-off pages; **Surya OCR 2** (open-source, run locally) on the other 12 pages.
2. A word is **auto-accepted only if all three readers agree** on its letters, and Readers B and C also agree on its tashkeel. Tesseract votes on letters only, because it does not read tashkeel reliably. Two abstention rules (owner decisions, Oct 4):
   - **Tashkeel abstention:** a reader that outputs **no tashkeel at all** on a word whose letters match the others abstains on tashkeel only; the remaining reader decides the tashkeel.
   - **Tesseract abstention:** when Tesseract reads a word with **less than 60% confidence** (or not at all), it abstains, and the remaining independent readers B and C must then agree **exactly**, tashkeel included.
   Words accepted under either abstention rule are spot-checked at **10%** (twice the normal rate). Everything else goes to a human.
3. The human reviewer sees only the disputed phrases, each with the full printed line from the original page and **only the disputed words** highlighted, and chooses a reading or types a correction (`/review/gold`). If the words cannot be located reliably, the screen says «الموقع غير مؤكد» and shows the full page with the likely area marked; a «عرض الصفحة كاملة» button is always available.
4. A random 5% of fully agreed words (weighted toward words with tashkeel) and 10% of words accepted by abstention are shown to the reviewer as a spot-check.
5. **Equivalent readings are not disputes (owner rule, Oct 5).** Readings that differ only in Unicode (combining-mark order such as shadda + fatha, fixed by NFC) or in whitespace just inside brackets, around footnote markers or before punctuation («الرحيم )» = «الرحيم)», «﴿ قُلْ» = «﴿قُلْ», «شهدا (٨)» = «شهدا(٨)») are the same printed text. Such a dispute is auto-accepted when Readers B and C are identical after this canonicalization and Tesseract agrees on the letters or gave no reading. Spaces *between words* («يارسول» / «يا رسول») are a real difference in the print and stay with the human. Strict CER applies the same canonicalization to both sides. This removed **28** of 792 open disputes; **764** remain (522 tashkeel differences between B and C, 120 letter differences, 108 where Tesseract confidently reads other letters, 13 word-spacing differences, 1 with no Reader C).
6. The reviewer confirms the block types (body, hadith, Quran, footnote, editor commentary…) before the page is finalized.

**Bias controls.**
- **Asool's own page parser (Gemini) is never one of the gold readers**, so the gold set does not come from the model it evaluates.
- The review screen shows how many readers support a candidate, not which model produced it.
- Readers A and C are classical/open OCR engines with weaker tashkeel than the vision-language models, so **more disagreements reach human review**; auto-accept still requires all three readers to agree.
- Known limitation: Reader B (Claude) was the pivot reading and the reviewer's default option, so Claude scores are inflated against this gold set and Claude is not eligible as Asool's parser. Diacritic conventions may lean toward Claude's style.

**Spot-check results (bake-off pages).** 21 auto-accepted words checked, **0 wrong** (error rate 0%). A review-screen bug recorded these 21 confirmations as "wrong" although the reviewer left every word unchanged. The bug is fixed and the 21 records are reclassified with a note in the data (`correction_note`).

| Pages | Words | Auto-accepted | Human decisions | Spot-checked | Spot-check errors |
|---|---|---|---|---|---|
| 41, 30, 20 (bake-off) | 942 | 425 + 11 equivalent readings | 237 (26 re-queued still open) | 21 | 0 |
| 12 other pages (rule v3) | 3,541 | 2,375 (476 tashkeel abstention, 678 Tesseract abstention) + 17 equivalent readings | 738 (pending) | 176 (pending) | pending |

**Review-screen bug and audit (Oct 4).** The first version of the review screen could show a neighbouring line when a disputed phrase was not found by OCR, highlighted whole lines instead of the disputed words, and could keep the previous image visible while the next one loaded. Fixed: word-level location with honest "uncertain" labels, one image per dispute, full-page view. All decisions made with the old screen were audited against the new locator: **37 of 237 bake-off decisions** (and both decisions made on page 12) were put back in the review queue because their crop did not show the disputed words. No spot-check answer was affected. Audit file: `data/gold/audit_2026-10-04_crops.json`.

Shamela (book 2348, a different edition) is available to the reviewer as an independent text cross-check; page numbers differ, so it is never used as gold directly.

## Hadith grading rule
No hadith is shown without its source and a grading from approved data; a grading is **never generated by a model**.
1. Al-Nawawi's printed takhrij names al-Bukhari and/or Muslim («متفق عليه»، «رواه البخاري»، «رواه مسلم») → the exact source as printed: «متفق عليه» → **«في الصحيحين (متفق عليه)»**, «رواه البخاري» → **«في صحيح البخاري»**, «رواه مسلم» → **«في صحيح مسلم»** (owner decision, GATE 4: «في الصحيحين» alone would wrongly imply both books).
2. Otherwise, if the hadith is found in **HadeethEnc** (موسوعة الأحاديث النبوية, an approved platform in the challenge's scientific package, reviewed by scholars) with the **same narrator and core wording**, its grade (الدرجة) and link are used automatically. If the match is uncertain, the project owner confirms or rejects it in `/review/hadith`.
3. Otherwise the owner enters the result from **dorar.net** by hand: grading, muhaddith, source, number and link. The screen warns when the entered narrator differs from the book's narrator.
4. Nothing verified → **«الحكم غير متحقق في البيانات»**.
Al-Nawawi's printed takhrij is always shown beside the grading.

In the 30-page corpus: 41 hadiths are in the Sahihayn by al-Nawawi's takhrij (24 «متفق عليه», 8 al-Bukhari, 8 Muslim, 1 «رواه إماما المحدثين» naming both), and 4 are graded from HadeethEnc (3 automatically, 1 confirmed by the owner). None needs manual dorar entry.

**Why search results are never used for grading automatically (dorar lesson, Oct 4).** For the hadith «إن الله يقبل توبة العبد ما لم يغرغر» (p.19), the first dorar.net result for «ما لم يغرغر» was a *different*, fabricated hadith graded «كذب». Taking the top search result would have attached a "fabricated" verdict to an authentic hadith. That is why the grading is taken only after checking narrator and wording, or confirmed by a person. The prefilled dorar search uses a short distinctive phrase with footnote markers and tashkeel removed and joined words split («مالم» → «ما لم»).

## Evaluation (Phase 5)
Everything on `/proof` is computed by these scripts; nothing is typed by hand.

```bash
uv run python -m eval.run_eval retrieval          # Asool vs. baseline, free (cached embeddings)
uv run python -m eval.run_eval answers --runs 3   # real /answer pipeline, ~$0.03 per question per run
uv run python -m eval.heldout_eval                # extraction on the 12 held-out gold pages
uv run python -m eval.report                      # -> data/eval/results/summary.json -> /proof
```

**Question set** (`data/eval/questions.jsonl`, 66 questions, drafted by the agent, each marked `human_verified` until the owner checks it): 33 answerable questions (direct, needs-footnote, cross-page, multi-condition, Quran, editor commentary, English), 1 owner case (`completeness-01`), 10 unanswerable from this corpus, 5 personal cases needing a fatwa (level D), 3 hostile phrasings, 2 misquoted verses, and the **12 official test cases** of the scientific package (p.6) adapted to this corpus. Questions outside the 30 pages are expected to end in abstention or referral, never in an answer from general knowledge.

**Fair baseline.** Same embeddings, same hybrid search code (BM25 + dense + RRF), same k=5 and same answer model; only the data preparation differs (Tesseract plain text in fixed 500-character pieces). Retrieval is measured with the raw question for both systems.

**Metrics.** Recall@5 and MRR by gold page; context completeness (a top-5 unit from the gold page also carries the footnote the question depends on); behaviour (answer / abstain / refer / correct the verse); quotes re-verified independently (fabricated quotes shown must be 0); traceability (every shown quote resolves to a stored block with a page and a box); multi-condition answers must cite every required unit; consistency across 3 repeated runs.

**Changes made after looking at evaluation results (disclosed).**
- `completeness-01` (owner, GATE 4): answers now add same-chapter, same-page neighbouring units and prompt `answer.v3` requires every condition/limit to be cited.
- `ans-16`: a quotation from the book inside «…» in the question is now a third ranked list in the fusion (exact phrase match, footnote markers ignored), applied identically to the baseline. Before: Asool Recall@5 95.3%; after: 97.7% (baseline unchanged, 81.4%).
- `ans-21`: editor commentary printed among the footnotes was linked to the *next* hadith (p.29, p.41). It is now linked to the hadith whose footnote is printed just before it, and its search text names that hadith's opening. Asool Recall@5: 97.7% → 100%.
- `official-08`: a request to translate a term from the approved glossary is now answered from the dictionary itself (status `glossary`), never generated; terms outside the package's sample are labeled as not yet verified against Jamhara.
- `official-11` / `official-12`: prompt rules: the explanation never writes surah/ayah numbers itself (the verified verse card does), and loaded terms are explained in the passages' own context without adopting the asker's framing.
