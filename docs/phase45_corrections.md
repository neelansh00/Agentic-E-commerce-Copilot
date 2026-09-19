# Phase 4.5 correction pass

This pass corrects the initial live failures before Phase 5. It does not introduce an agent, Python analysis tool or UI. The original live report is preserved. All eleven question strings, output contracts and group keys are unchanged; an automated regression asserts equality with the archived run. The model remains the same configured snapshot, and both context modes run once after the fixes.

## Root causes and selected layers

| Failure family | Category | Root cause | Smallest shared correction |
|---|---|---|---|
| Monthly cohorts, both modes | Missing date/calendar rows; NULL handling | DISTINCT observed months omit gaps; ELSE 0/COALESCE invents revenue when payments are absent | Reusable calendar view, NULL-preserving order revenue, explicit SQL instructions and result invariants |
| Category delivery, full definitions | Wrong join/grain; incorrect aggregation | COUNT DISTINCT repairs only the denominator while AVG and SUM still see repeated item rows | One order/category aggregate view joined to one order-metric row |
| Overall delivery, RAG | Incorrect denominator/eligibility | Counts are filtered but duration AVG includes ineligible rows | Delivery duration and late indicators are NULL outside the shared eligible population |
| Seller performance, full definitions | SQL syntax/execution at validation boundary | SQLGlot classifies EXISTS as a Func; a safe SQL predicate was rejected repeatedly | Allow the EXISTS AST construct; retain physical-table/function/SQLite authorizer restrictions |
| Seller performance, RAG | Incorrect denominator/eligibility; explanation-layer error | Non-null delivery date substitutes for delivered status; missing prerequisite definitions; latest-review filtering before ranking is not enforced; seller labels mix rows | Order flags and eligible-review selection in a shared view, transitive definition retrieval, exact row identities in rendered evidence |
| State, category, month, seller and regional explanations | Explanation-layer error | Model counts list positions incorrectly, embeds numbers/dates in labels or adds unsupported superlatives | Explicit indexed rows in explanation input; canonical captions and copied group identities in output; invalid selections still fail closed |

The definitions themselves were already unambiguous. `knowledge_base/metrics.md` and the frozen reference are unchanged. Wrong base-table selection and incorrect SQL ranking were not primary causes in the original recorded failures; unsupported ranking prose is an explanation-layer error. The per-case report records the exact affected context and regression test rather than merging execution failures with incorrect numerical answers.

## Reusable grains, not question-specific SQL

`app/database/metric_views.sql` installs four temporary views on each read-only connection before enabling query-only mode. SQLite reads the original database in `mode=ro`; the views change connection state only. They contain no top-N answers, benchmark IDs, thresholds or reference values. The model still writes the projection, filters, grouping, aggregation and ordering.

- `metric_orders`: one row per order. Payments are aggregated first; reviews are filtered for timestamp eligibility before deterministic latest-review ranking. It exposes successful/canceled flags, nullable delivered payment revenue, payment coverage, selected review score and eligible delivery measures.
- `metric_order_categories`: one row per order/raw-category, with summed item counts, prices and freight. Repeated items no longer weight delivery averages. Unknown and untranslated categories remain intact.
- `metric_order_sellers`: one row per order/seller, preserving item totals while counting each associated order review once. Multi-seller orders still contribute to several sellers by the documented policy.
- `metric_months`: a recursive calendar from first through last observed purchase month. Monthly reports left-join the order grain and retain empty months. Counts can be zero; undefined revenue and AOV remain NULL.

The supplied schema context exposes relevant views with grain and NULL/denominator notes. Views are registered in the SQL allowlist; SQLite authorization permits their named raw dependencies and internal CTE read contexts. Database writes, external tables/functions and arbitrary schema access remain forbidden. The TEMP storage setting must be configured before creating views because changing it discards existing TEMP objects; regression tests cover actual guarded execution, not just SQL parsing.

These views are a small explicit semantic layer. Alternatives were longer prompts alone or question-specific SQL templates. Prompts alone had failed live; complete answer templates would defeat the text-to-SQL test. At production scale the same grains could be versioned database views or tested transformations. No such infrastructure is introduced here.

## Delivery and one-to-many protections

Eligible delivery requires delivered status, present delivered/estimated timestamps and delivery at or after purchase. `delivery_days`, `is_late` and `calendar_day_late` are NULL otherwise; averaging or summing those measures cannot accidentally include an invalid observation from the view. The eligible count is `SUM(delivery_eligible)`, and late rate uses that denominator. Successful-order sales/reviews use the delivered flag, which requires status exactly delivered.

Platform averages come from the order grain independently of seller/category joins. Item sales use the aggregated child grains; order payment revenue is not allocated across them. Additional semantic validation rejects joining raw items/payments/reviews into `metric_orders`, combining seller and category grains without an allocation policy, or aggregating payment revenue over these child grains. These are conservative boundaries, not a universal SQL equivalence checker.

Result invariants reject revenue/AOV zero when the paid-order denominator is zero, late counts exceeding eligible counts and interior calendar gaps for continuous-month intent. Ranked or explicitly selected month questions do not require a continuous spine. The calendar check does not prove that arbitrary user filters are semantically correct; it complements the view and prompt rules. All rejections feed the existing bounded SQL correction loop.

## RAG prerequisite definitions

The original semantic top-three search is unchanged for definition lookup. SQL context retrieval additionally follows a small explicit graph of definition dependencies. For example, seller screening needs selected reviews, eligible delivery and item-sales conventions, all of which depend on the successful-order definition. Added chunks retain source citations and a dependency reason; no similarity score is fabricated for them. Unrelated definitions are not automatically dumped into every request.

## Explanation boundary

The model selects useful cells from explicitly indexed rows. Its free-form labels are untrusted and are no longer rendered. Captions come from a metric-column glossary; group identity comes directly from that selected row, including seller ID, state, category and month. Thus selecting row two cannot silently attach row zero's seller identity.

The renderer makes no highest/lowest/best/worst/top claims. This is deliberately conservative even where the returned table is ordered: correctly verifying a superlative also requires scope, ties, truncation and limiting semantics. Unknown column captions are neutral. Digit-bearing or inferential labels and invalid row/column references still trigger the documented literal fallback for compatibility. Numeric values are always copied from query results.

This is constrained evidence presentation, not a claim of improved unrestricted narrative generation. A correct table may still receive an incomplete summary; the current five-cell limit and fallback selection are stated limitations. Canonical captions depend on the metric-column contract; an arbitrary semantically wrong SQL alias is not made correct by formatting. Exact result comparison and a review of the actual rendered answers remain required.

## Regression and reproduction

`tests/test_phase45.py` covers the original missing-month/NULL failures, repeated items, invalid delivery populations, successful status versus timestamps, eligible-review ordering, EXISTS safety, view execution without database mutation, payment allocation guards, original bad explanation outputs and immutable benchmark questions. Existing ingestion, SQL safety and baseline tests remain in place.

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe scripts/verify_metric_views.py
.venv/Scripts/python.exe scripts/run_live_evaluation.py --live --output docs/generated/phase45_live_evaluation.json
```

The live command makes billable API requests and refuses to overwrite an existing report. No reference SQL/values enter model prompts. The new view-definition source hashes are recorded alongside prompt, schema and RAG code hashes. The calendar/order/category/seller SQL here is generic domain logic; evaluation-specific comparison code stays outside the application.

See the [updated comparison](generated/phase45_report.md) for measured results, every affected case, answer review and the explicit readiness decision. Passing this development benchmark would justify proceeding with Phase 5 work, not deploying a production analyst or claiming unseen-question accuracy. Phase 5 is not started by this pass.
