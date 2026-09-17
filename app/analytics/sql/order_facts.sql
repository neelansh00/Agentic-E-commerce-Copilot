-- Shared, read-only CTEs. Each reference query is this prefix plus its SQL body.
-- Grain: exactly one row per order. Never join raw items to raw payments/reviews.
WITH RECURSIVE
payment_totals AS (
    SELECT order_id, SUM(payment_value_cents) AS payment_cents, COUNT(*) AS payment_rows
    FROM payments GROUP BY order_id
),
ranked_reviews AS (
    SELECT r.order_id, r.review_score,
           ROW_NUMBER() OVER (PARTITION BY r.order_id ORDER BY
               r.review_answer_timestamp DESC, r.review_creation_date DESC, r.review_id DESC) AS position
    FROM reviews r JOIN orders o ON o.order_id = r.order_id
    WHERE r.review_creation_date >= o.order_purchase_timestamp
      AND r.review_answer_timestamp >= r.review_creation_date
),
order_facts AS (
    SELECT o.*, c.customer_state, c.customer_unique_id,
           p.payment_cents, COALESCE(p.payment_rows, 0) AS payment_rows,
           r.review_score,
           CASE WHEN o.order_status = 'delivered'
                  AND o.order_delivered_customer_date IS NOT NULL
                  AND o.order_estimated_delivery_date IS NOT NULL
                  AND o.order_delivered_customer_date >= o.order_purchase_timestamp
                THEN 1 ELSE 0 END AS delivery_eligible,
           CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date
                THEN 1 ELSE 0 END AS is_late,
           (JULIANDAY(o.order_delivered_customer_date) - JULIANDAY(o.order_purchase_timestamp)) AS delivery_days
    FROM orders o JOIN customers c ON c.customer_id = o.customer_id
    LEFT JOIN payment_totals p ON p.order_id = o.order_id
    LEFT JOIN ranked_reviews r ON r.order_id = o.order_id AND r.position = 1
)
