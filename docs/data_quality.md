# Phase 1 data-quality interpretation

Exact missing-value percentages for **all columns** are in the [audit](generated/dataset_audit.md); executable SQL and counts are in the [verification report](generated/verification_report.md) and its JSON companion.

## Missing values that matter

| Column | Missing | Percentage | Analysis implication |
|---|---:|---:|---|
| Review title | 87,658 | 88.3435% | Text analysis is not representative of all reviews. |
| Review message | 58,274 | 58.7297% | A missing comment is not a missing score; score has 0% missing. |
| Customer delivery timestamp | 2,965 | 2.9817% | Late-delivery denominator must require an observed delivery timestamp. |
| Carrier delivery timestamp | 1,783 | 1.7930% | Carrier-to-customer duration cannot be computed for these rows. |
| Order approval timestamp | 160 | 0.1609% | Approval duration needs a completeness filter. |
| Product category / name length / description length / photos | 610 each | 1.8512% each | Keep an explicit unknown group in category comparisons. |
| Product weight / length / height / width | 2 each | 0.0061% each | Exclude or flag missing physical measurements. |

All source ID columns are nonempty, including PK components and enforced FK fields. Missing child records are a separate issue from null cells: 775 orders have no items, one has no payment and 768 have no review. Inner joins can silently exclude these orders.

## Duplicates and ambiguous grain

- Geolocation has 261,831 exact duplicate excess rows. They remain in storage for faithful reproduction. ZIP prefix is neither unique nor a safe direct dimension key.
- Reviews have no exact duplicate full rows, but repeated review IDs and multiple reviews per order. Preserve them; decide later whether order-level analysis uses a latest-review rule or a documented summary. Averaging all raw reviews would give some orders extra weight.
- There are 2,961 orders with multiple payment rows and 1,278 with multiple sellers. Joins need aggregation or allocation appropriate to the question.
- There are 2,997 customer identities with multiple customer records. Count distinct `customer_unique_id` for unique buyers, not `customer_id`.

## Coverage and consistency

- Categories `pc_gamer` (3 products) and `portateis_cozinha_e_preparadores_de_alimentos` (10 products) are absent from the translation CSV. Do not drop these products through an inner join.
- Eight delivered orders lack the customer delivery timestamp; six non-delivered-status orders have one. Delivery status and timestamp should both be considered when defining eligible orders.
- 166 orders have a carrier timestamp earlier than purchase; 23 have customer delivery earlier than carrier handoff. Flag affected duration calculations instead of replacing dates.
- 74 review creation timestamps precede purchase. The file alone does not establish why; review timing analysis needs exclusion flags.
- Nine payment rows have zero value, two have zero installments, and four products have zero weight. These are preserved observations, not automatically corrected errors.
- 31 coordinate rows fall outside a broad Brazil bounding box (latitude −34 to 6; longitude −74 to −28). This is a heuristic screening flag, not a definitive geographical validation.
- City labels vary within ZIP prefixes; eight prefixes map to multiple states. No arbitrary city/state deduplication is performed.

Orders span 2016-09-04 to 2018-10-17. Boundary months may be incomplete, and delivery/review availability is affected by the snapshot. A future answer about revenue decline must check time coverage, order status, denominator and attribution; this dataset alone cannot establish the cause of a business change.

The estimated-delivery field is a timestamp, often at midnight. Phase 2 must explicitly distinguish the requested strict timestamp rule (`delivered > estimated`) from a calendar-day definition, since delivery later on the estimated calendar date can qualify under the former. No late-rate metric is implemented in Phase 1.

## What the loader rejects versus preserves

The loader rejects missing required IDs, duplicate selected keys, orphan enforced FKs, malformed CSV headers/records, invalid timestamp syntax, fractional integer attributes, sub-cent money, negative monetary values, invalid review scores and globally invalid coordinates. It preserves plausible but inconsistent source facts (missing optional values, temporal anomalies, untranslated categories, duplicate coordinate records). A failed load leaves the previous database untouched.

The audit reads all rows, not a sample. Uniqueness/missingness checks and selected date/relationship checks are comprehensive for their defined rules; this is not proof that every source value is correct. Full-table row counts and monetary reconciliation do not independently prove every transformed cell. Small fixture tests cover conversion behavior and failure handling.
