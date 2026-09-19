# Deterministic analytics baseline — Phase 2

Metric contract version: 1. All checks passed: **True**.
Frozen reference snapshot: **matched**.

Each SQL result is compared with a separate Python calculation over the original CSVs. Counts, cents, strings, NULLs and ordering match exactly; rounded float metrics allow absolute error up to 0.000002.
These results validate manually authored SQL; they do not measure LLM accuracy, statistical significance or causality.

| Query | SQL ran | CSV agreement | Rows | Execution ms |
|---|---|---|---:|---:|
| overview | True | True | 1 | 5056.154 |
| monthly_revenue | True | True | 26 | 6988.726 |
| state_aov | True | True | 27 | 3945.614 |
| state_cancellation | True | True | 27 | 3884.281 |
| category_sales | True | True | 10 | 1274.9 |
| late_delivery | True | True | 1 | 3691.815 |
| late_reviews | True | True | 2 | 3394.936 |
| category_delivery | True | True | 10 | 3361.773 |
| seller_performance | True | True | 20 | 7149.393 |
| seller_lateness | True | True | 20 | 7029.441 |
| regional_delivery | True | True | 27 | 4709.334 |

Full results, executed SQL, parameters, source hashes and errors are in `baseline_report.json`. Only the first five rows per query are shown below. Timing is one local sequential execution per query, including fetching results; it is not a benchmark comparison.

## Observations

- Delivered-order recorded payment revenue: **BRL 15,422,461.77**, across 96,477 orders with payments. 1 delivered orders lack payments.
- Strict timestamp lateness: **8.11%** (7,826/96,470 eligible deliveries); 8 delivered orders excluded.
- Mean selected review score: **2.57 late** (7,661 reviews) versus **4.29 on time** (88,160 reviews).

## Interpretation and limits

Group differences, where present, are descriptive; investigate delivery experience alongside product mix, geography and review-selection effects. These averages do not establish causality or statistical significance. Seller lists identify candidates for review, not evidence of fault. Revenue is the project-defined payment proxy, not net accounting revenue.

## overview

How many orders and buyers are there, and what are delivered-order revenue, AOV and cancellation rate?

Payment revenue includes freight; missing payments are excluded from AOV and shown separately.

| total_orders | unique_buyers | delivered_orders | paid_delivered_orders | delivered_missing_payment | revenue_cents | aov_cents | canceled_orders | cancellation_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 99441 | 96096 | 96478 | 96477 | 1 | 1542246177 | 15985.635716 | 625 | 0.628513 |

## monthly_revenue

How does delivered-order payment revenue vary by purchase month?

Purchase cohorts, not cash-flow months. Boundary and low-coverage cohorts cannot establish a revenue decline cause.

| purchase_month | boundary_month | total_orders | delivered_orders | paid_delivered_orders | delivered_missing_payment | revenue_cents | aov_cents |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2016-09 | 1 | 4 | 1 | 0 | 1 | NULL | NULL |
| 2016-10 | 0 | 324 | 265 | 265 | 0 | 4656671 | 17572.343396 |
| 2016-11 | 0 | 0 | 0 | 0 | 0 | NULL | NULL |
| 2016-12 | 0 | 1 | 1 | 1 | 0 | 1962 | 1962.0 |
| 2017-01 | 0 | 800 | 750 | 750 | 0 | 12754567 | 17006.089333 |

## state_aov

How does delivered-order average payment value vary by customer state?

AOV uses only delivered orders with recorded payments; compare denominators as well as means.

| customer_state | delivered_orders | paid_delivered_orders | delivered_missing_payment | revenue_cents | aov_cents |
| --- | --- | --- | --- | --- | --- |
| PB | 517 | 517 | 0 | 13783465 | 26660.473888 |
| AC | 80 | 80 | 0 | 1958625 | 24482.8125 |
| AP | 67 | 67 | 0 | 1614181 | 24092.253731 |
| AL | 397 | 397 | 0 | 9419579 | 23726.899244 |
| RO | 243 | 243 | 0 | 5697570 | 23446.790123 |

## state_cancellation

Which customer states have the highest cancellation rate?

Canceled divided by all orders; unavailable is not canceled. Small state samples need caution.

| customer_state | total_orders | canceled_orders | cancellation_pct |
| --- | --- | --- | --- |
| RR | 46 | 1 | 2.173913 |
| RO | 253 | 3 | 1.185771 |
| PI | 495 | 4 | 0.808081 |
| SP | 41746 | 327 | 0.783309 |
| RJ | 12852 | 86 | 0.669157 |

## category_sales

What are the top 10 categories by delivered item sales, excluding freight?

Item sales are not allocated payment revenue. Unknown and untranslated categories remain eligible.

| category_key | category_label | item_count | delivered_orders | item_sales_cents | freight_cents |
| --- | --- | --- | --- | --- | --- |
| beleza_saude | health_beauty | 9465 | 8647 | 123313172 | 17895781 |
| relogios_presentes | watches_gifts | 5859 | 5495 | 116617698 | 9815614 |
| cama_mesa_banho | bed_bath_table | 10953 | 9272 | 102343476 | 20177450 |
| esporte_lazer | sports_leisure | 8431 | 7530 | 95485255 | 16340436 |
| informatica_acessorios | computers_accessories | 7644 | 6530 | 88872461 | 14399916 |

## late_delivery

What proportion of eligible delivered orders arrived after the estimated timestamp?

Strict timestamp lateness; calendar-day count is sensitivity context. Missing/invalid deliveries are excluded.

| delivered_orders | eligible_orders | excluded_orders | late_orders | late_pct | mean_delivery_days | calendar_day_late_orders |
| --- | --- | --- | --- | --- | --- | --- |
| 96478 | 96470 | 8 | 7826 | 8.112367 | 12.558217 | 6534 |

## late_reviews

How do review scores and poor-review rates differ between late and on-time deliveries?

Descriptive association only; no test, significance or causality claim. One eligible selected review per order.

| delivery_group | eligible_orders | reviewed_orders | missing_eligible_review | mean_review_score | poor_review_orders | poor_review_pct |
| --- | --- | --- | --- | --- | --- | --- |
| late | 7826 | 7661 | 165 | 2.56507 | 4142 | 54.066049 |
| on_time | 88644 | 88160 | 484 | 4.294192 | 8128 | 9.219601 |

## category_delivery

Which 10 categories have the longest mean delivery time with at least 30 eligible orders?

One observation per order/category; categories on the same order overlap.

| category_key | category_label | eligible_orders | late_orders | late_pct | mean_delivery_days |
| --- | --- | --- | --- | --- | --- |
| moveis_escritorio | office_furniture | 1254 | 115 | 9.170654 | 20.63858 |
| fashion_calcados | fashion_shoes | 235 | 15 | 6.382979 | 15.728033 |
| artigos_de_natal | christmas_supplies | 125 | 12 | 9.6 | 15.374882 |
| moveis_colchao_e_estofado | furniture_mattress_and_upholstery | 37 | 5 | 13.513514 | 14.43297 |
| fashion_underwear_e_moda_praia | fashion_underwear_beach | 117 | 15 | 12.820513 | 14.002583 |

## seller_performance

Which 20 sellers lead item sales among those with at least 20 reviewed delivered orders and below-platform-average scores?

Order scores associated with sellers, not direct seller ratings; multi-seller attribution is shared.

| seller_id | delivered_orders | reviewed_orders | item_sales_cents | mean_review_score | platform_mean_review_score |
| --- | --- | --- | --- | --- | --- |
| 4869f7a5dfa277a7dca6462dcf3b52b2 | 1124 | 1116 | 22698793 | 4.150538 | 4.155976 |
| 4a3ca9315b744ce9f8e9374361493884 | 1772 | 1753 | 19688212 | 3.853394 | 4.155976 |
| 7c67e1448b00f6e969d365cea6b010ab | 973 | 967 | 18657005 | 3.498449 | 4.155976 |
| 1025f0e2d44d7041d6cf58b6550e0bfa | 910 | 902 | 13820856 | 4.006652 | 4.155976 |
| 6560211a19b47992c3666cc44a7e94c0 | 1819 | 1805 | 12070283 | 3.977839 | 4.155976 |

## seller_lateness

Which 20 sellers have the highest above-platform late rates with at least 30 eligible deliveries?

Descriptive above-average screen, not statistical anomaly detection or seller fault.

| seller_id | eligible_orders | late_orders | late_pct | platform_late_pct |
| --- | --- | --- | --- | --- |
| ede0c03645598cdfc63ca8237acbe73d | 43 | 15 | 34.883721 | 8.112367 |
| ad781527c93d00d89a11eecd9dcad7c1 | 38 | 12 | 31.578947 | 8.112367 |
| 835f0f7810c76831d6c7d24c7a646d4d | 42 | 13 | 30.952381 | 8.112367 |
| 54965bbe3e4f07ae045b90b0b8541f52 | 73 | 22 | 30.136986 | 8.112367 |
| 2a1348e9addc1af5aaa619b1a3679d6b | 48 | 13 | 27.083333 | 8.112367 |

## regional_delivery

How do order volume and delivery performance vary across customer states?

All-order volume and eligible-delivery late rates use different denominators; compare both.

| customer_state | total_orders | eligible_orders | late_orders | late_pct | mean_delivery_days |
| --- | --- | --- | --- | --- | --- |
| SP | 41746 | 40494 | 2387 | 5.8947 | 8.761386 |
| RJ | 12852 | 12350 | 1664 | 13.473684 | 15.309438 |
| MG | 11635 | 11354 | 637 | 5.610358 | 12.008666 |
| RS | 5466 | 5344 | 382 | 7.148204 | 15.300276 |
| PR | 5045 | 4923 | 246 | 4.996953 | 11.991582 |
