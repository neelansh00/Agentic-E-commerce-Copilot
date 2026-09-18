# Phase 3 offline integration evidence

**This replays Phase 2 reference SQL. It does not measure natural-language SQL generation or model accuracy.**

All checks passed: True. Database unchanged: True. Model API calls: 0.

| Reference | Result matches | Required schema retrieved | Initial tables | Rows |
|---|---|---|---:|---:|
| overview | True | True | 3/9 | 1 |
| monthly_revenue | True | True | 2/9 | 26 |
| state_aov | True | True | 3/9 | 27 |
| state_cancellation | True | True | 2/9 | 27 |
| category_sales | True | True | 4/9 | 10 |
| late_delivery | True | True | 1/9 | 1 |
| late_reviews | True | True | 2/9 | 2 |
| category_delivery | True | True | 4/9 | 10 |
| seller_performance | True | True | 4/9 | 20 |
| seller_lateness | True | True | 3/9 | 20 |
| regional_delivery | True | True | 2/9 | 27 |

The full JSON records timings, validation/retry traces and source fingerprints. Shared Phase 2 CTEs reference extra tables, so some replays exercise the single bounded schema-expansion path.

Validation, SQLite authorization and actual execution are real. The SQL provider is scripted. Semantic SQL correctness for new questions and model explanation quality remain unmeasured.

Unit tests separately cover forbidden operations, retry exhaustion, repair, evidence failures, time/output limits, provider errors and schema matching.
