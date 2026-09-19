# Live SQL generation and constrained answer evaluation

Model: `gpt-4.1-mini-2025-04-14`. Completed: True. Database unchanged: True.

Eleven development questions, each with an explicit output contract, sampled once per context. Static means the full metric document; RAG means retrieved excerpts. Neither mode is a no-definitions baseline. These are live-generated SQL results, not scripted replay.

| Context | Questions executed | Exact results | Accepted explanation format | Literal fallbacks | Median latency | API calls |
|---|---:|---:|---:|---:|---:|---:|
| static | 10/11 (90.9%) | 8/11 (72.7%) | 5/11 | 5 | 10.581s | 25 |
| rag | 11/11 (100.0%) | 8/11 (72.7%) | 8/11 | 3 | 9.118s | 23 |

This benchmark made 48 API calls, with 84,479 input tokens and 19,031 output tokens. Estimated cost: USD 0.063627 using the recorded rate card; not an invoice. Connectivity smoke calls are excluded (see JSON).

Full numerical result accuracy is distinct from explanation quality. A query may execute and an explanation may reference real cells while both are semantically misleading.

## Semantic explanation review

Coding assistant semantic review; not independent human annotation or a second paid LLM judge.

Inspect every accepted rendered observation against its referenced row and column; verify group attribution, units and any ranking claim against the complete returned table. Record query accuracy separately. Coverage describes whether observations address the core metric, not whether every result row is verbalized.

| Context | Accepted explanations | Labels faithful to returned result | Faithful labels and exact query result |
|---|---:|---:|---:|
| static | 5 | 5/5 | 4/5 |
| rag | 8 | 6/8 | 5/8 |

These conditional review counts are not unrestricted generative-answer accuracy. Literal fallbacks are excluded; useful question coverage is assessed separately below. All explanations currently use model-selected labels/cells with values inserted by Python.

## Per-question evidence

| Question | Context | Exact result | Explanation |
|---|---|---|---|
| overview | static | True | accepted |
| overview | rag | True | accepted |
| monthly_revenue | static | False | literal fallback |
| monthly_revenue | rag | False | literal fallback |
| state_aov | static | True | literal fallback |
| state_aov | rag | True | literal fallback |
| state_cancellation | static | True | literal fallback |
| state_cancellation | rag | True | accepted |
| category_sales | static | True | accepted |
| category_sales | rag | True | literal fallback |
| late_delivery | static | True | accepted |
| late_delivery | rag | False | accepted |
| late_reviews | static | True | accepted |
| late_reviews | rag | True | accepted |
| category_delivery | static | False | accepted |
| category_delivery | rag | True | accepted |
| seller_performance | static | False | unavailable |
| seller_performance | rag | False | accepted |
| seller_lateness | static | True | literal fallback |
| seller_lateness | rag | True | accepted |
| regional_delivery | static | True | literal fallback |
| regional_delivery | rag | True | accepted |

## Reviewed answer limitations

- **overview / static** (partial): Correct labels and values, but the five-observation cap omits requested AOV.
- **overview / rag** (partial): Accurate counts; omits revenue, AOV and cancellation rate from the explanation.
- **monthly_revenue / static** (not_generated): No accepted model explanation. Literal fallback: Explanation labels must be short and nonnumeric
- **monthly_revenue / rag** (not_generated): No accepted model explanation. Literal fallback: Explanation labels must be short and nonnumeric
- **state_aov / static** (not_generated): No accepted model explanation. Literal fallback: Explanation referenced a nonexistent result cell
- **state_aov / rag** (not_generated): No accepted model explanation. Literal fallback: Explanation referenced a nonexistent result cell
- **state_cancellation / static** (not_generated): No accepted model explanation. Literal fallback: Explanation labels must be short and nonnumeric
- **state_cancellation / rag** (addresses_core): Highest/lowest rates and state-specific denominators agree with the returned table; small-group caveat would improve interpretation.
- **category_sales / static** (partial): Labels refer to the right categories, but mixes freight/counts/category key instead of summarizing the sales ranking.
- **category_sales / rag** (not_generated): No accepted model explanation. Literal fallback: Explanation labels must be short and nonnumeric
- **late_delivery / static** (addresses_core): Correct eligible denominator, excluded count, late count and percentage.
- **late_delivery / rag** (addresses_core): Displayed late counts and rate match reference; complete SQL result fails because mean delivery duration uses an ineligible population. On-time analysis is imprecise wording for the eligible delivery population.
- **late_reviews / static** (addresses_core): Both groups have the correct mean score and poor-review percentage, with a descriptive-only caveat.
- **late_reviews / rag** (partial): Selected cells are correct, but omits late mean score and on-time poor-review percentage, weakening the requested group comparison.
- **category_delivery / static** (partial): Labels are faithful to the returned cells, but SQL overweights repeated category items; returned delivery metrics are wrong.
- **category_delivery / rag** (addresses_core): Names several categories and their correct mean delivery durations; shows one eligibility denominator.
- **seller_performance / static** (not_generated): No accepted model explanation. SQL exhausted its three attempts; no numerical answer was produced.
- **seller_performance / rag** (partial): Repeated Top seller labels mix rows zero, one and two without seller identity. Platform reference also differs because SQL substitutes non-null delivery date for delivered status.
- **seller_lateness / static** (not_generated): No accepted model explanation. Literal fallback: Explanation labels must be short and nonnumeric
- **seller_lateness / rag** (addresses_core): Correct top seller identifier, denominator, late count, late rate and platform comparison. Only the leading seller is discussed; the complete ranking is in the result table.
- **regional_delivery / static** (not_generated): No accepted model explanation. Literal fallback: Explanation referenced a nonexistent result cell
- **regional_delivery / rag** (partial): Highest order volume references SE with 350, although SP has 41746. Lowest delivery duration references SE with 21.519788 days, although SP has 8.761386. Valid cell references do not validate superlatives.

## SQL failure analysis

- Monthly revenue, both contexts: returns 25 observed months instead of the 26-month calendar spine; converts missing eligible payment sums to zero instead of NULL.
- Category delivery, static: counts distinct orders but averages and sums over item rows, so repeated order/category items change delivery metrics.
- Overall delivery, RAG: mean delivery duration is averaged without the eligibility filter, although late counts use it.
- Seller performance, static: SQLGlot classifies EXISTS under its function hierarchy and the current allowlist rejects it; the model repeats the rejected construct through all three attempts. This is an overly restrictive validator path, not an unsafe statement.
- Seller performance, RAG: delivered population uses non-null delivered timestamps instead of delivered status; latest-review candidate filtering also differs from the reference. Platform mean is 4.155812 versus reference 4.155976.

## Before Phase 5

API access works, but this run does not establish reliable analytical answers. Address metric-grain/NULL/calendar semantics, the EXISTS validator false positive, explicit row/group references and verified extrema before expanding the agent. Preserve this initial run, add regression tests and evaluate fixes on separate paraphrases; do not replace failed results with successful reruns.

No statistically justified RAG improvement is claimed: both contexts match 8/11 complete results, with different failures and one sample each. The model and questions were not tuned during this run. See [methodology](../live_evaluation.md), the JSON traces and [semantic review annotations](../../evaluation/live_answer_review.json).
