# Business metric contract — version 1

These are explicit project conventions over the supplied Olist snapshot, not claims about Olist's accounting policies. Phase 2 uses this document directly; embedding-based retrieval is not implemented yet.

Total orders counts every order regardless of status. Unique buyers counts distinct `customer_unique_id` across those orders, including buyers with canceled orders. It is not a count of buyers with completed purchases.

## Successful orders and revenue

A successful order has `order_status = 'delivered'`. Revenue means the sum of recorded `payment_value_cents` for these orders. Aggregate all payment sequences per order first. The result includes any freight contained in the recorded payments. It is a gross payment-based proxy, not profit, net revenue, cash-flow timing or accounting revenue: refund, cost and settlement data are unavailable. Canceled, unavailable and all other non-delivered statuses are excluded.

Orders without payment rows have unknown payment value, not zero. Always report delivered orders, delivered orders with payments, and missing-payment coverage separately. Zero-valued recorded payments are legitimate observed values for this calculation. A sum over no eligible payments is NULL, not invented zero revenue.

Currency is BRL; storage and reference totals use integer cents. Divide by 100 for presentation. Do not sum payments after a raw join to items or reviews.

## Average order value

AOV = recorded payment revenue / number of delivered orders with at least one payment row. AOV excludes delivered orders with missing payments and reports their count. Multiple payment installments/sequences do not increase the order denominator. A zero denominator yields NULL. State means customer state, not seller state.

## Category and seller sales; freight

Item sales = sum of `price_cents` on delivered orders. Freight = separate sum of `freight_value_cents`. These measures exclude non-delivered orders and do not use payment value. An item is a source line item; repeated products on an order are still separate item rows.

Category/seller rankings explicitly say **item sales**, not payment revenue. Payment-based revenue cannot be uniquely assigned across categories/sellers without an allocation policy. The baseline intentionally does not invent one. Missing categories form an explicit NULL/Unknown group; untranslated categories keep the Portuguese label. Group on the raw category key, not the display label, to avoid label collisions.

## Cancellation rate

Cancellation rate = orders with status exactly `canceled` / all orders in the selected purchase cohort. `unavailable` is a distinct status, not automatically a cancellation. Count orders even if no item/payment/review exists. Report numerator, denominator and percentage (0–100); all statuses in this snapshot represent the observed state, not complete lifecycle history.

## Delivery eligibility, lateness and duration

Eligible delivery = status `delivered`, non-null delivered and estimated timestamps, and delivered timestamp >= purchase timestamp. Excluded delivered orders are counted. This is a purchase-to-customer metric and does not require a carrier timestamp.

Late means `order_delivered_customer_date > order_estimated_delivery_date` using the full timestamp. Equality is on time. Arrival later on the estimated calendar date counts late under this strict rule; this is deliberate and must be disclosed. A calendar-day sensitivity count is also reported, but does not replace the strict definition. NULL dates are unknown, never on time.

Late rate = late eligible orders / all eligible delivery orders. Delivery days = elapsed purchase-to-customer seconds / 86,400, not rounded calendar days or business days. A category contributes at most once per order to category delivery analysis, even if an order has several items in that category. A multi-category order can appear in several category groups, so group order counts are not additive.

## Review score and poor reviews

Scores range from 1 to 5; poor means 1 or 2. First retain reviews with creation >= order purchase and answer timestamp >= review creation. Among those, select the latest answer timestamp per order; break ties by latest creation timestamp, then lexicographically largest review ID. This is deterministic and avoids weighting orders by their number of reviews. It is a snapshot policy, not evidence that the selected review was a revision of another one.

Missing eligible reviews are excluded from score averages and reported separately. For late-versus-on-time comparison, restrict to eligible deliveries and show review coverage, mean score, poor-review count and rate by group. Differences describe association only. No statistical test, significance claim or causal attribution is performed in Phase 2.

Seller ratings are **order-level review scores associated with the seller**, not direct seller ratings. Count each order/seller pair once, even for repeated items. Multi-seller orders contribute their order score to each associated seller; comparisons are therefore not independent seller-level experiments.

## Seller and region screening

Seller sales/rating screen: require at least 20 reviewed delivered orders, retain sellers whose mean selected order score is below the platform's order-weighted mean across reviewed delivered orders, and rank by delivered item sales (top 20). This is a candidate review list; high sales means relative ranking, not a statistical threshold.

Seller late-delivery screen: require at least 30 eligible delivered orders and a late rate above the platform eligible-order late rate; rank by rate, then sample size, then seller ID (top 20). This is an above-average descriptive screen, not an anomaly test or proof of seller fault. Thresholds are configurable named SQL parameters.

Category delivery ranking requires at least 30 eligible order/category pairs. Regional delivery reports show all customer states with order counts, eligible deliveries, late counts/rates and mean delivery days; no arbitrary high-volume or poor-performance cutoff is implied. Carrier, route and geography may confound seller comparisons.

## Time cohorts and missing periods

Assign revenue to purchase month of the eventually delivered order, not payment or delivery month. Calendar months between first and last purchase are included, including months without orders. Empty-month observed revenue and AOV are NULL; counts are zero. An observed cohort with payment records totaling zero has revenue zero.

Flag the first and last observed purchase months as dataset-boundary months. Also report delivered/payment coverage. Interior months are not guaranteed complete; recent cohorts can be immature at the snapshot. Do not interpret apparent decline as causal evidence or compare incomplete cohorts without qualification. A revenue-change explanation would require explicit period selection, coverage checks and descriptive decomposition in later work.

## Limitations shared by all metrics

No source timezone is supplied; timestamps are treated as timezone-naive and unshifted. Return NULL for undefined means/rates, expose relevant denominators, retain unknown categories and avoid geolocation joins for state aggregates. These definitions are versioned so future reference-answer changes can be explained.
