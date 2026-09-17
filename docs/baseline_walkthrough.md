# Phase 2 — deterministic analytics baseline

The baseline establishes what correct answers mean before adding text-to-SQL. It consists of 11 fixed, human-authored SQL queries, one versioned [business metric contract](../knowledge_base/metrics.md), an independent CSV calculator and frozen reference results. There is no model, agent routing, RAG index or arbitrary Python execution.

## Run and inspect

```powershell
python scripts/run_baseline.py
python -m unittest discover -s tests -v
```

The first command executes all reference SQL against the read-only local database, independently recalculates the outputs from raw CSVs, compares the frozen snapshot and produces [a readable report](generated/baseline_report.md). Its JSON companion contains every row, assembled SQL, parameters, execution time and source/database checksums. Failures produce a nonzero process exit code and are recorded; nothing is silently repaired.

`evaluation/baseline_expected.json` holds the questions, expected relevant tables/tools, interpretations, named parameters, SQL file references, SQL hashes and independently computed expected results. It is the seed for later evaluation, not the final approximately 50-question benchmark.

Only after deliberately reviewing a data/definition/query change should the frozen ground truth be regenerated:

```powershell
python scripts/run_baseline.py --freeze
```

That flag creates/replaces the snapshot only when all SQL/CSV comparisons pass and source hashes remain stable. Ordinary runs never refresh expected answers. A changed metric contract, source archive contents, question metadata or SQL hash causes a snapshot mismatch until reviewed. Independent agreement alone cannot establish that a chosen business policy is appropriate; the contract must also be reviewed.

## Reference query catalogue

| ID | Output grain | Business question |
|---|---|---|
| `overview` | Entire dataset | Orders, distinct buyer identities, delivered revenue, AOV, cancellations |
| `monthly_revenue` | Purchase month | Delivered payment revenue with cohort coverage and boundary flags |
| `state_aov` | Customer state | AOV with observed-payment denominator and missing-payment counts |
| `state_cancellation` | Customer state | Canceled / all orders, sorted by rate |
| `category_sales` | Category, top 10 | Delivered item sales and separately reported freight |
| `late_delivery` | Eligible delivered orders | Strict timestamp late rate and calendar-day sensitivity count |
| `late_reviews` | Late/on-time group | Selected review means, poor-score percentages and review coverage |
| `category_delivery` | Order/category, top 10 | Longest mean delivery times, minimum 30 eligible orders |
| `seller_performance` | Order/seller, top 20 | Highest item sales among below-average scores, minimum 20 reviewed orders |
| `seller_lateness` | Order/seller, top 20 | Above-platform late rates, minimum 30 eligible orders |
| `regional_delivery` | Customer state | All-order volume plus eligible delivery performance |

All reference questions are answerable descriptively using SQL. `late_reviews` does not request a hypothesis test, so its expected tool is SQL only. A later inferential question would need a separately justified statistical workflow. Seller IDs are already on `order_items`; queries do not join `sellers` unnecessarily unless seller attributes are required.

## How to read the SQL

`app/analytics/sql/order_facts.sql` defines reusable CTEs (temporary named results within a query, not persisted tables):

1. `payment_totals` sums payment sequences to one row per order.
2. `ranked_reviews` filters impossible review chronology and assigns `ROW_NUMBER` within each order, with deterministic tie-breaking.
3. `order_facts` joins the customer record and at most one payment summary/selected review, then exposes delivery eligibility and duration.

Each query body is appended to this prefix. The report includes the **entire assembled SQL**, so it can be inspected or executed with the listed named parameters. The shared prefix references customers, payments and reviews even when a query does not need all those fields; `expected_relevant_tables` identifies semantic requirements, not a claim about every textual reference in the assembled SQL. This simple reference implementation is not the future schema-retrieval mechanism or a performance-optimized semantic layer.

For item sales, the query uses order items directly and never joins payment rows. For delivery by category or reviews by seller, it first reduces to distinct order/category or order/seller pairs. Counts across overlapping categories/sellers are therefore not additive.

## Hand-calculated adversarial fixture

The test fixture has six orders: five delivered and one canceled. Four delivered orders have payment totals of 3,000, 7,000, 0 and 5,000 cents; the fifth lacks payment data. The canceled order has 9,000 cents and must be excluded.

- Revenue = 3,000 + 7,000 + 0 + 5,000 = **15,000 cents**.
- AOV = 15,000 / 4 = **3,750 cents**, not 15,000 / 5.
- Cancellation = 1 / 6 = **16.666667%**.
- Three deliveries are eligible. One occurs at noon on its estimated date, one equals its estimated timestamp, and one occurs the day after. Strict late rate = 2 / 3; calendar-day late count = 1.
- Duplicate items in the same category/order must not weight the delivery average twice.
- Conflicting reviews test latest-answer selection, ID tie-breaking and invalid chronology. Missing eligible reviews remain missing.

Additional tests cover empty month gaps, unknown/untranslated categories, zero eligible deliveries, named-parameter validation, exact comparison failures and independent SQL/CSV agreement for every query.

## Measured observations and business interpretation

The [generated report](generated/baseline_report.md) is the source of truth for measured values. On the supplied snapshot, recorded delivered-order payments total BRL 15,422,461.77 across 96,477 orders with payment records; one delivered order lacks payments. AOV is approximately BRL 159.86 under this denominator.

The strict timestamp late rate is 7,826 / 96,470 = 8.112367%; eight delivered orders are ineligible because of missing delivery timestamps. The mean selected review score is 2.565070 for 7,661 reviewed late orders and 4.294192 for 88,160 reviewed on-time orders. Missing review coverage differs between groups. These descriptive results motivate investigation; product, geography, carrier and selection effects remain possible explanations.

RR has the highest observed state cancellation percentage, but that is one canceled order out of just 46. A ranked percentage without its sample size would be misleading. Category rankings use item sales, whereas overall revenue uses payment value; they must not be compared as identical totals.

## Verification boundaries

Every output row and column is checked, not only the first five rows displayed in Markdown. Integers, currency cents, NULL values, labels and deterministic order are compared exactly. Rounded fractional metrics use an absolute tolerance of 0.000002 to accommodate SQLite Julian-day arithmetic and Python datetime arithmetic. There is no relative tolerance that could hide large monetary differences.

The CSV reference reads original columns with `csv`, parses currency with `Decimal`, calculates elapsed time with `datetime`, and uses Python dictionaries/sets for grouping. It does not query the database or reuse the SQL transformations. Both implementations still share the same written business contract; independent code and hand-calculated cases reduce implementation risk, not policy risk.

SQL timings are recorded once per query, including fetching results. Warm/cold cache and local hardware are not controlled. No latency improvement, agent accuracy or statistical significance is claimed. Source data is a historical snapshot with missing records, not a complete modern e-commerce ledger.
