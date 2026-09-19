# Order lifecycle and analytical boundaries

## Order lifecycle

The supplied orders file contains these observed status labels: `created`, `approved`, `invoiced`, `processing`, `shipped`, `delivered`, `canceled`, and `unavailable`. They describe the snapshot's recorded status. The file does not provide a complete sequence of status-change events, so do not infer exact transition paths or time spent in each state.

Purchase, approval, carrier handoff, customer delivery and estimated delivery are separate timestamps. Some are missing or inconsistent. Do not fill missing timestamps with purchase dates or infer successful delivery from an estimate. The project's successful-order definition is exactly status `delivered`; delivery-duration metrics additionally need eligible observed timestamps.

## Payments, installments and item value

Each order can have multiple payment sequences, payment types and installments. A payment row is not another order, and installment count is not a multiplier for `payment_value_cents`. Aggregate the recorded payment values per order once. Zero-value recorded payments differ from absent payment records.

Item prices and item freight are separate measures. Do not assume item prices equal recorded payments or infer refunds, discounts, settlement times or margin from their difference. The source does not contain a refund ledger, marketing spend or product cost data.

## Unanswerable operational questions

The knowledge base defines metrics; it does not contain current sales totals, forecasts, external market facts, personal contact details, a return-policy window or a causal explanation of a revenue decline. Transactional totals must come from SQL over the supplied snapshot. A missing business policy should be reported as unavailable rather than invented.
