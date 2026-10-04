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
