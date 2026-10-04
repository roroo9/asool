# Costs

All numbers are **measured**: OpenRouter reports the cost of each call; Anthropic cost = tokens × the published price (model table dated 2026-09-25: Opus 5.5 $4/$20, Fable 5.1 $10/$50 per 1M input/output tokens); Google AI Studio free tier = $0. Source of truth: the usage log `data/cache/llm_usage.jsonl` and the saved responses. Recompute with `uv run python -m eval.costs` (Phase 5).

## Budgets and spend (as of Sun Oct 4, ~11:00 Riyadh)

| Provider | Budget | Spent | Used | Warn at 80% |
|---|---|---|---|---|
| Anthropic (gold readers only) | $5.00 | $2.66 | 53% | $4.00 |
| OpenRouter (Asool's models + embeddings) | $10.00 (key limit) | $1.62 | 16% | $8.00 |
| Google AI Studio | free tier | $0.00 | n/a | n/a |
| Surya, Tesseract | local | $0.00 | n/a | n/a |

Anthropic will not be used further unless the owner decides otherwise (Reader C for the remaining gold pages is Surya, local).

## Measured unit costs
| Item | Cost |
|---|---|
| Page parsing, Gemini 3.1 Pro (OpenRouter), prompt v2 | $0.139 / page |
| Page parsing, Gemini 3.8 Flash (OpenRouter) | $0.090 / page |
| Gold reader B, Claude Opus 5.5 | $0.110 / page |
| Embeddings, Gemini Embedding 2 (OpenRouter) | $0.20 / 1M tokens (2 short texts cost $0.000003) |

## Projection to submission
| Item | Estimate |
|---|---|
| Parse the remaining 27 corpus pages with Gemini 3.1 Pro | ≈ $3.75 |
| Embeddings for the whole corpus | < $0.05 |
| Answers + evaluation (≈ 50 questions × 3 runs) | to be measured in Phase 3; capped by `DAILY_BUDGET_USD` |
| **Projected OpenRouter total before answers** | **≈ $5.40 (54%)** |

Per-1,000-page ingestion cost (projection from measured unit cost): ≈ $139 with Gemini 3.1 Pro, ≈ $90 with Gemini 3.8 Flash.
