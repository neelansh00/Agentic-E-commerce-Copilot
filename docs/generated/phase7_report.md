# Phase 7 measured evaluation

Model: `gpt-4.1-mini-2025-04-14`. Fifty frozen development questions; production code unchanged during evaluation. All 137 offline tests pass.

| Metric | Result |
|---|---:|
| sql execution | 28/30 (93.3%) |
| sql result accuracy | 28/30 (93.3%) |
| task correctness | 47/50 (94.0%) |
| tool selection | 48/50 (96.0%) |
| status accuracy | 47/50 (94.0%) |
| rag heading hit | 8/8 (100.0%) |
| Reviewed support for requested metric among substantive answers | 39/40 (97.5%) |

Groundedness is coding-assistant review against evidence, not independent human annotation. Ten abstentions are outside its denominator; incorrect abstentions still fail task correctness. Definition heading hits are retrieval scores, not generated-prose accuracy.
Median end-to-end case latency: 2137.9 ms. This mixes cheap deterministic requests and model SQL, not a SQL-only latency estimate. Literal explanation fallbacks: 4.

| Category | Correct tasks |
|---|---:|
| ambiguous_adversarial | 6/7 (85.7%) |
| business_definition | 8/8 (100.0%) |
| multi_table_sql | 10/12 (83.3%) |
| simple_sql | 15/15 (100.0%) |
| statistical | 5/5 (100.0%) |
| time_based | 3/3 (100.0%) |

The five statistical cases contain three paraphrases of the supported global comparison and two expected refusals. This is not five distinct statistical tools. Correct refusals contribute to task correctness, not SQL result accuracy.

## Failures and answer usefulness

- **seller_performance: routing false positive.** The word those in a self-contained seller screen triggers the router's blanket follow-up detector. Next correction: Recognize actual unresolved references instead of rejecting any question containing those; add complete-sentence and genuine-follow-up regressions.
- **seller_lateness: routing false positive.** Above-platform is a comparison, but the standalone above token triggers the follow-up detector. Next correction: Distinguish comparison language from references to earlier answers; test both intents.
- **allocation: repair changes the requested metric.** Validation correctly blocks summing order payment revenue across category rows, but its use-item-sales feedback leads repair to substitute a different metric. The final answer does not disclose the substitution or request an allocation policy. Next correction: Treat missing allocation policy as clarification, preserve requested metric intent across repair, and surface any explicitly approved change of metric.

Correct SQL tables can still have weak explanations. Monthly/status/state fallbacks show only the first row; seller-state/payment-type captions miss dimension or unit labels; several summaries select scattered cells. These are coverage issues, not additional exact-SQL failures. The allocation case is an intent-level correctness failure and is also excluded from grounded answers.

## Controlled comparisons

| Experiment / mode | Executed | Exact results |
|---|---:|---:|
| A: full_schema | 9/10 (90.0%) | 9/10 (90.0%) |
| A: retrieved_schema | 9/10 (90.0%) | 8/10 (80.0%) |
| B: no_application_validation_no_retry | 9/10 (90.0%) | 8/10 (80.0%) |
| B: validation_and_retry | 10/10 (100.0%) | 9/10 (90.0%) |

| C: definition context | All required facts supported (assistant review) |
|---|---:|
| without_definitions | 0/8 (0.0%) |
| with_rag | 6/8 (75.0%) |

A changes only full versus retrieved schema, with one attempt in each arm. B reuses the same initial SQL in both arms and retains engine safety on an isolated read-only copy. C compares generated definitions with/without retrieved context, separately from the production verbatim-RAG path. See the protocol for exact controls and limitations.

### Schema context cost and latency

- full_schema: 34,741 input tokens; median 5514.4 ms.
- retrieved_schema: 28,647 input tokens; median 5337.6 ms.
- Retrieved-schema input tokens were 17.54% lower in this sample. Accuracy was lower, not improved; median latency differences are not statistically established.

### Experiment failure analysis

- A: both schema arms generated `customer_state` directly from `orders` for state cancellation. The field belongs to the customer dimension (or joined metric view). Execution failed in both arms. B repaired the same initial retrieved-schema query by selecting from `metric_orders`; this was the single successful repair.
- A/B: retrieved-schema monthly SQL retained the empty calendar month but left SUMs of count flags NULL instead of zero. Monetary NULL values were appropriate; coverage counts were wrong. The query executed, so the current validator did not trigger a retry. The schema included the required fields; this is a generated aggregation/NULL-semantics error, not evidence of a missing table in retrieval.
- C: without context, the monthly answer substituted customer-acquisition cohorts for order-purchase cohorts, while other answers were generic or explicitly uncertain. With RAG, six answers expressed all required facts. The lateness answer did not explicitly exclude unknown dates from the denominator; the cohort answer covered NULL for empty months but omitted nonempty cohorts with no eligible payments. Both passed the lexical rubric, demonstrating why 8/8 pattern hits are not 8/8 complete semantic answers.
- Suggested follow-up regressions: count flags after a calendar LEFT JOIN, raw-versus-joined state columns, and definition completeness for unknown dates and missing payments. Preserve this run as the pre-correction evidence.


### Engineering interpretation

Keep the small existing architecture. The comparisons do not justify adding another agent, an embedding schema router or a new framework. B supports bounded diagnostic retry with one repaired query; engine and application safety remain essential beyond that sample. The simple schema retriever has a measured token saving but no measured accuracy gain here: retain the full-schema evaluation alternative and test a broader held-out set before choosing a default on accuracy grounds. RAG supplies project policy, but retrieval hits and lexical coverage cannot replace semantic review.

This is one sample per arm on development questions in fixed order. No significance, held-out generalization, causal performance improvement or production readiness is claimed. Do not compare the 50-question agent score directly with the earlier 11-question text-to-SQL score: routing and refusal behavior are now part of the measured system.

## Usage and reproducibility

Actual API requests: 98 (61 benchmark + 37 experiments). Input tokens: 181,184; output tokens: 14,716. Reused B plans are not charged twice in this count. No current-price cost estimate is claimed.
The original database and isolated experiment copy are unchanged. Questions and prior phase reports are preserved. Phase 8 has not started.

Evidence: [protocol](../phase7_evaluation.md), [frozen questions](../../evaluation/questions.json), [benchmark outputs](phase7_benchmark.json), [experiments](phase7_experiments.json), [answer review](../../evaluation/phase7_answer_review.json), [definition review](../../evaluation/phase7_definition_review.json), [offline checks](phase7_tests.json).
