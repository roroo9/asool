# Costs

All numbers are **measured**: OpenRouter reports the cost of each call; Anthropic cost = tokens × the published price (model table dated 2026-09-25: Opus 5.5 $4/$20, Fable 5.1 $10/$50 per 1M input/output tokens); Google AI Studio free tier = $0. Source of truth: the usage log `data/cache/llm_usage.jsonl` and the saved responses. Recompute with `uv run python -m eval.costs` (Phase 5).

## Budgets and spend (as of Sun Oct 4, 11:05 Riyadh)

| Provider | Budget | Spent | Used | Warn at 80% |
|---|---|---|---|---|
| Anthropic (gold readers only, no further use planned) | $5.00 | $2.66 | 53% | $4.00 |
| **OpenRouter** (Asool's models + embeddings) | $10.00 (key limit) | **$7.07** | **71%** | $8.00 |
| Google AI Studio | free tier | $0.00 | n/a | n/a |
| Surya, Tesseract | local | $0.00 | n/a | n/a |

OpenRouter breakdown (logged calls): parsing 30 pages + bake-off with Gemini 3.1 Pro $4.95 (33 calls), block boxes with Gemini 3.8 Flash $0.44 (30 calls), other bake-off candidates $0.79, embeddings $0.01. A further ≈$0.89 was billed for three calls cut off at the output limit before such calls were logged (they are logged now, under `*/truncated`).

## Measured unit costs
| Item | Cost |
|---|---|
| Page parsing, Gemini 3.1 Pro (OpenRouter), prompt v2 | $0.150 / page (30 pages, measured) |
| Block boxes, Gemini 3.8 Flash (OpenRouter) | $0.015 / page |
| Page parsing, Gemini 3.8 Flash (OpenRouter) | $0.090 / page |
| Gold reader B, Claude Opus 5.5 | $0.110 / page |
| Embeddings, Gemini Embedding 2 (OpenRouter) | $0.20 / 1M tokens (2 short texts cost $0.000003) |

## Projection to submission
Ingestion is done. Remaining spend is answers (Phase 3), evaluation runs (Phase 5) and live use during judging (Oct 7–22). With $2.93 left on OpenRouter this is **not enough** for answers with Gemini 3.1 Pro plus 3 evaluation runs. See the GATE 2 decision.

Per-1,000-page ingestion cost (projection from measured unit cost): ≈ $165 with Gemini 3.1 Pro + boxes.

## Update: Mon Oct 5, evening (Riyadh)

| Provider | Budget | Spent | Used | Warn at 80% |
|---|---|---|---|---|
| **OpenRouter** | $25.00 (limit raised at GATE 2) | **$12.15** (OpenRouter's own usage figure) | **49%** | $20.00 |
| Anthropic | $5.00 | $2.66 | 53% | $4.00 |

The new spend since GATE 3 is mostly evaluation:

| Item | Spend |
|---|---|
| Evaluation answer passes, 3 full passes of 66 questions while fixing issues | $4.63 |
| Live and test answers | $0.44 |

**Measured unit costs (online)**

| Item | Cost |
|---|---|
| Answer with Gemini 3.1 Pro (`answer.v3`), including classification | ≈ $0.031 per question |
| Abstention or referral | ≈ $0.001 (classification only, no generation) |
| Answer served from the cache | $0 |

**Remaining plan**
- Two more evaluation runs, needed for consistency: about $4.
- Live use during judging, capped at $3 per day: about $0.03 per new question.

## Update: Tue Oct 6 (after the question review)

| Provider | Budget | Spent | Used |
|---|---|---|---|
| **OpenRouter** | $25.00 | **$22.39** | **89.6%** (past the 80% warning) |

Spend since the last update, about $8.40:

| Item | Spend |
|---|---|
| Three evaluation runs: run 0 on 81 questions, runs 1 and 2 on 66 | about $6.30 |
| A pass stopped early after a chunking regression, 22 questions | about $0.70 |
| Prompt v1 on the 12 held-out pages | about $1.65 |
| Post-fix checks on 16 questions | about $0.55 |
| Development tests of the outside-sources path | about $0.40 |
| Demo precompute | about $0.15 |
| Mushaf verse vectors | $0.04 |

Re-scoring the runs with the fixed scorer cost $0, because every call was served from cache.

**Risk.** The hard stop is at $23, which leaves about $0.60 for new live questions during judging. The 81 evaluation questions and the demo questions are served from cache for free. Above the hard stop, the site shows search passages only, so a page never breaks.

**Recommendation.** Add about $10 of OpenRouter credit before judging (Oct 7). Then raise `OPENROUTER_BUDGET_USD` and `HARD_BUDGET_USD` in the Render settings. About $2.40 of that would fund a clean full re-run of the evaluation on the final pipeline.

## Update: Tue Oct 6, after the clean re-run (owner chose option A)
- OpenRouter key limit $40 (owner added $15). Spent **$24.86**.
- The clean full re-run of 81 questions cost about $2.40.
- Live answers stop at $38, so **about $13.10 remains for judging**. The owner accepted the reserve dipping below $15 to fund the clean re-run.
- All 81 evaluation answers and the demo answers are cached and cost $0 to serve.
