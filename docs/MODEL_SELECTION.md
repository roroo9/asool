# Model selection (Phase 1 bake-off)

**Decision:** Asool's page parser is **Gemini 3.1 Pro (preview) via OpenRouter, prompt `page_parse.v2`**.
Fallback on failure: Gemini 3.8 Flash (OpenRouter), then Gemini 3.5 Flash (Google AI Studio).
Configured in `api/settings.py` (`page_parser_model`, `page_parser_fallback_model`), switchable by env.

## Task and data
- Task: transcribe a scanned page of رياض الصالحين (1956 Cairo print) into typed blocks in reading order, with footnote markers and editor commentary separated.
- Pages: printed pp. **41** (8 footnotes in two columns, split around the editor's commentary, a poetry line), **30** (start of باب الصبر, 6 Quran verses), **20** (densest page, 7 footnotes).
- Gold: human-reviewed, consensus-assisted (see README "Gold set"). Reviewer: rawan. 237 disputed phrases decided by the reviewer, 21 spot-checks.
- Run: `uv run python -m eval.bakeoff` → `data/eval/results/bakeoff.json`.

## Metrics
- **CER strict:** character error rate with diacritics kept (combining marks in canonical NFC order).
- **CER loose:** after `normalize(level="cer_loose")` (no tashkeel, unified letter forms).
- **Footnote-link F1:** body marker ↔ footnote with the same marker on the page.
- **Block-type accuracy:** share of gold characters whose best-matching predicted block has the right type.
- **USD/page:** measured from provider-reported cost (OpenRouter) or tokens × published price (Anthropic, table dated 2026-09-25). Google AI Studio free tier = 0.

## Results (mean of 3 pages)

| System | Role | CER strict | CER loose | WER loose | Footnote F1 | Block types | USD/page |
|---|---|---|---|---|---|---|---|
| Claude Opus 5.5 | Gold Reader B (not eligible) | 1.0% | 0.2% | 1.6% | 0.96 | 100% | 0.110 |
| Claude Fable 5.1 | Gold Reader C here (not eligible) | 1.7% | 0.9% | 7.2% | 1.00 | 90% | 0.335 |
| **Gemini 3.1 Pro + prompt v2** | **chosen** | **2.3%** | **0.4%** | 3.3% | **1.00** | **100%** | 0.139 |
| Gemini 3.1 Pro + prompt v1 | candidate | 4.3% | 0.4% | 3.0% | 1.00 | 100% | 0.138 |
| Gemini 3.8 Flash + v1 | candidate | 4.5% | 0.5% | 3.9% | 1.00 | 100% | 0.090 |
| Gemini 3.5 Flash + v1 | candidate | 7.8% | 1.6% | 4.6% | 0.96 | 93% | 0 (free tier) |
| Surya OCR 2 (local) | Gold Reader C, other pages (not eligible) | 10.8% | 2.9% | 12.4% | 0.60 | 33% | 0 |
| GPT-5.6 Terra + v1 | candidate | 16.3% | 6.2% | 15.3% | 0.79 | 76% | 0.116 |
| Qwen3-VL 32B + v1 | candidate | 24.7% | 8.1% | 21.3% | 0.14 | 23% | 0.001 |
| Tesseract 5 `ara` | Gold Reader A / baseline | 29.9% | 23.9% | 58.4% | 0.00 | n/a | 0 |

Per page, strict CER of the chosen system: p41 1.4%, p30 2.8%, p20 2.8%.

## Why this choice
1. **Independence rule** (CLAUDE.md §12.C): the gold set's readers are Tesseract, Claude, Surya. The page parser must come from another family, so Claude and Surya are not eligible even though Claude scored lowest.
2. Among eligible candidates, Gemini 3.1 Pro with prompt v2 has the lowest strict CER, perfect footnote linking and block typing on all 3 pages.
3. Prompt v2 adds one rule naming the main error we measured (Gemini dropped printed tashkeel such as «وانطلقَ» → «وانطلق»). It halved strict CER (4.3% → 2.3%) without changing loose CER.
4. Quality is the top priority; Pro costs about $0.05/page more than 3.8 Flash. For 30 pages that is about $1.50.

## Limits and bias (read before quoting these numbers)
- **3 pages only.** The prompt v2 tweak was chosen on the same 3 pages, so its gain is an in-sample estimate. It will be re-measured on the **12 held-out gold pages** in Phase 5.
- **Claude's scores are inflated** and not comparable: the gold drafts used Claude Opus as the pivot reading, auto-accepted words required Claude Opus and Claude Fable to agree on diacritics, and the reviewer saw Claude's reading as the first option. This is exactly why Claude is excluded from selection.
- **Diacritic style bias:** for the same reason, the gold set may lean toward Claude's diacritic conventions. The human reviewer checked every disputed word against the page image, and the 5% spot-check of auto-accepted words found 0 errors in 21 words.
- OpenRouter routes to Google's own endpoint for Gemini (`provider: Google` in the test response); results may differ slightly from Google AI Studio.
