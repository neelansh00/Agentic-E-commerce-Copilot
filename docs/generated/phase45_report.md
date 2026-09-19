# Phase 4.5 correction results

**Ready for Phase 5 development: True. Phase 5 has not started.**

Model: `gpt-4.1-mini-2025-04-14`. Exactly the same eleven questions, output contracts, group keys and reference values: **True**. No complete benchmark SQL was added to the application. Original results are preserved.

| Context | Previous execution | Corrected execution | Previous exact results | Corrected exact results |
|---|---:|---:|---:|---:|
| static | 10/11 | 11/11 | 8/11 (72.7%) | 11/11 (100.0%) |
| rag | 11/11 | 11/11 | 8/11 (72.7%) | 11/11 (100.0%) |

Offline regressions: **99 run; all passed: True** (original 76 plus 23 new tests). Full-data metric checks: **16/16**. Existing guarded reference replays all passed: **True**. Database unchanged: **True**.

## Explanation review

Coding assistant inspection of all 22 rendered answers, their result cells, group identities, metric units and reference outputs; not an independent human evaluation.

All 22 rendered outputs were reviewed against their cells and correct query results. No misleading interpretation was found. Free-form model labels are no longer displayed: captions are deterministic and each selected state/category/seller/month identity is copied from the same row. The renderer makes no ranking assertions.

| Context | Model cell selections accepted | Literal fallbacks | Misleading rendered interpretations found |
|---|---:|---:|---:|
| static | 10/11 | 1/11 | 0/11 |
| rag | 7/11 | 4/11 | 0/11 |

Five answers still use explicit literal fallbacks because model labels contain digits. Safe output is not the same as a useful or complete generated summary: monthly fallbacks show first-row coverage, and category/seller summaries sometimes omit the central metric. Full correct results are retained. This pass does not claim unrestricted narrative-generation quality or an independent human groundedness score.

## Each previously failed case

Result status below refers to the full returned table. Explanation fallbacks are shown separately rather than counted as misleading prose.

### monthly_revenue / static

- Categories: missing date/calendar rows, NULL handling, explanation-layer error.
- Previous: executed=True, exact result=False, fallback=True.
- Corrected: executed=True, exact result=True, fallback=True; rendered answer reviewed as non-misleading.
- Root cause: Observed-month grouping omits an empty cohort; CASE ELSE 0/COALESCE turns unknown payments into zero. Model dates embedded in labels fail validation.
- Fix: metric_months calendar spine; nullable metric_orders revenue; NULL/calendar result checks and repair feedback; indexed evidence and safe fallback.
- Regression tests in `tests/test_phase45.py`: `test_month_spine_retains_empty_month_with_null_money`, `test_zero_payments_are_observations_missing_payments_are_null`, `test_calendar_gap_rejected_only_for_continuous_series`, `test_recorded_monthly_failures_rejected_without_using_reference_answers`, `test_previous_invalid_explanations_still_fail_closed`.

### monthly_revenue / rag

- Categories: missing date/calendar rows, NULL handling, explanation-layer error.
- Previous: executed=True, exact result=False, fallback=True.
- Corrected: executed=True, exact result=True, fallback=True; rendered answer reviewed as non-misleading.
- Root cause: Observed-month grouping omits an empty cohort; CASE ELSE 0/COALESCE turns unknown payments into zero. Model dates embedded in labels fail validation.
- Fix: metric_months calendar spine; nullable metric_orders revenue; NULL/calendar result checks and repair feedback; indexed evidence and safe fallback.
- Regression tests in `tests/test_phase45.py`: `test_month_spine_retains_empty_month_with_null_money`, `test_zero_payments_are_observations_missing_payments_are_null`, `test_calendar_gap_rejected_only_for_continuous_series`, `test_recorded_monthly_failures_rejected_without_using_reference_answers`, `test_previous_invalid_explanations_still_fail_closed`.

### state_aov / static

- Categories: explanation-layer error.
- Previous: executed=True, exact result=True, fallback=True.
- Corrected: executed=True, exact result=True, fallback=False; rendered answer reviewed as non-misleading.
- Root cause: Model references row 30 in a 27-row table and embeds numerical values in labels.
- Fix: Explicit row_index for each input row; canonical captions and exact copied state identity; out-of-range references remain rejected.
- Regression tests in `tests/test_phase45.py`: `test_explanation_rows_have_explicit_indices`, `test_previous_invalid_explanations_still_fail_closed`, `test_recorded_explanation_failures_are_rejected_or_neutrally_rendered`.

### state_aov / rag

- Categories: explanation-layer error.
- Previous: executed=True, exact result=True, fallback=True.
- Corrected: executed=True, exact result=True, fallback=False; rendered answer reviewed as non-misleading.
- Root cause: Model references row 30 in a 27-row table and embeds numerical values in labels.
- Fix: Explicit row_index for each input row; canonical captions and exact copied state identity; out-of-range references remain rejected.
- Regression tests in `tests/test_phase45.py`: `test_explanation_rows_have_explicit_indices`, `test_previous_invalid_explanations_still_fail_closed`, `test_recorded_explanation_failures_are_rejected_or_neutrally_rendered`.

### state_cancellation / static

- Categories: explanation-layer error.
- Previous: executed=True, exact result=True, fallback=True.
- Corrected: executed=True, exact result=True, fallback=False; rendered answer reviewed as non-misleading.
- Root cause: Model embeds percentages inside labels.
- Fix: Prompt separates selected value from caption; no model label is rendered; invalid labels still use a safe fallback.
- Regression tests in `tests/test_phase45.py`: `test_previous_invalid_explanations_still_fail_closed`, `test_recorded_explanation_failures_are_rejected_or_neutrally_rendered`.

### category_sales / rag

- Categories: explanation-layer error.
- Previous: executed=True, exact result=True, fallback=True.
- Corrected: executed=True, exact result=True, fallback=False; rendered answer reviewed as non-misleading.
- Root cause: Labels contain top10 plus unverified superlatives; the digit-bearing label triggers fallback despite correct SQL.
- Fix: Indexed selection and deterministic captions; no unsupported ranking text is displayed.
- Regression tests in `tests/test_phase45.py`: `test_recorded_explanation_failures_are_rejected_or_neutrally_rendered`.

### late_delivery / rag

- Categories: incorrect denominator/eligibility, incorrect aggregation.
- Previous: executed=True, exact result=False, fallback=False.
- Corrected: executed=True, exact result=True, fallback=False; rendered answer reviewed as non-misleading.
- Root cause: Late counts filter eligibility, but mean delivery duration does not.
- Fix: metric_orders makes duration and late flags NULL for every ineligible row; one canonical delivery population and explicit aggregation instructions.
- Regression tests in `tests/test_phase45.py`: `test_delivery_duration_and_lateness_share_eligible_population`, `test_inflated_late_numerator_rejected`.

### category_delivery / static

- Categories: wrong join/grain, incorrect aggregation.
- Previous: executed=True, exact result=False, fallback=False.
- Corrected: executed=True, exact result=True, fallback=False; rendered answer reviewed as non-misleading.
- Root cause: COUNT DISTINCT corrects the denominator only; repeated category items still weight duration averages and late sums.
- Fix: metric_order_categories stores one row per order/category; sum item quantities separately and average order duration at that grain.
- Regression tests in `tests/test_phase45.py`: `test_category_repeated_items_do_not_weight_delivery`, `test_raw_child_fanout_and_payment_allocation_rejected`, `test_payments_and_reviews_do_not_multiply_order_grain`.

### seller_performance / static

- Categories: SQL syntax/execution.
- Previous: executed=False, exact result=False, fallback=False.
- Corrected: executed=True, exact result=True, fallback=False; rendered answer reviewed as non-misleading.
- Root cause: Safe EXISTS predicate is misclassified under the function allowlist; all three attempts repeat it.
- Fix: Permit the EXISTS AST node without granting external functions/tables; shared eligible-review view also removes fragile hand-written latest-review subqueries.
- Regression tests in `tests/test_phase45.py`: `test_exists_is_valid_readonly_sql_and_executes`, `test_review_eligibility_precedes_latest_selection`.

### seller_performance / rag

- Categories: incorrect denominator/eligibility, explanation-layer error.
- Previous: executed=True, exact result=False, fallback=False.
- Corrected: executed=True, exact result=True, fallback=True; rendered answer reviewed as non-misleading.
- Root cause: Non-null delivery date substitutes for delivered status; prerequisite definitions are absent from top-three context. Top seller captions mix several rows.
- Fix: Status-derived flags and eligible-first review selection; RAG dependency expansion; deterministic seller identity per observation.
- Regression tests in `tests/test_phase45.py`: `test_delivery_timestamp_is_not_successful_order_status`, `test_review_eligibility_precedes_latest_selection`, `test_rag_includes_transitive_metric_dependencies`, `test_mixed_seller_rows_receive_their_own_identity`.

### seller_lateness / static

- Categories: explanation-layer error.
- Previous: executed=True, exact result=True, fallback=True.
- Corrected: executed=True, exact result=True, fallback=False; rendered answer reviewed as non-misleading.
- Root cause: The model copies numeric rates and counts into labels (including 34.883721%), violating the evidence-only label contract.
- Fix: Copy seller identity as structured row context, never model prose.
- Regression tests in `tests/test_phase45.py`: `test_mixed_seller_rows_receive_their_own_identity`, `test_recorded_explanation_failures_are_rejected_or_neutrally_rendered`.

### regional_delivery / static

- Categories: explanation-layer error.
- Previous: executed=True, exact result=True, fallback=True.
- Corrected: executed=True, exact result=True, fallback=False; rendered answer reviewed as non-misleading.
- Root cause: The model uses row 29 for SP in a 27-row result and miscounts other positions; the nonexistent reference triggers fallback.
- Fix: Explicit row indices and copied state context; labels remain untrusted.
- Regression tests in `tests/test_phase45.py`: `test_explanation_rows_have_explicit_indices`, `test_recorded_explanation_failures_are_rejected_or_neutrally_rendered`.

### regional_delivery / rag

- Categories: explanation-layer error.
- Previous: executed=True, exact result=True, fallback=False.
- Corrected: executed=True, exact result=True, fallback=True; rendered answer reviewed as non-misleading.
- Root cause: Valid SE cells are falsely labeled highest order volume and lowest delivery duration; selected cells do not support those extrema.
- Fix: Renderer discards free-form labels and makes no ranking assertions; states and metric captions come from selected evidence.
- Regression tests in `tests/test_phase45.py`: `test_wrong_highest_lowest_labels_never_enter_answer`, `test_recorded_explanation_failures_are_rejected_or_neutrally_rendered`.

## Live rerun usage and interpretation

46 API calls; 100,307 input tokens and 10,958 output tokens. Estimated cost: USD 0.056504 using the recorded rate card, not an invoice.

This is one development rerun per context after fixes motivated by the observed failures. It is not an unseen benchmark, a model comparison, or a statistically established RAG improvement. Several layers changed, so no isolated causal attribution of the improvement is claimed. Both modes now match all eleven complete reference results.

The readiness decision meets the requested gates for continuing development: all regressions pass, execution is complete, exact results exceed 10/11 in both modes and none of the reviewed rendered answers is factually misleading. This does not authorize or start Phase 5.

Evidence: [implementation and trade-offs](../phase45_corrections.md), [raw corrected run](phase45_live_evaluation.json), [original run](live_evaluation.json), [answer review](../../evaluation/phase45_answer_review.json), [failure classifications](../../evaluation/phase45_failure_analysis.json), [test output](phase45_tests.json), [metric checks](phase45_metric_checks.json), [readiness gates](phase45_readiness.json).
