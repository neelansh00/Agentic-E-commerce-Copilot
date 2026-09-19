-- Connection-local semantic primitives, never complete benchmark answers.
-- No physical tables or source records are modified.
CREATE TEMP VIEW metric_orders AS
WITH payment_totals AS (
    SELECT order_id, SUM(payment_value_cents) AS payment_cents, COUNT(*) AS payment_rows
    FROM main.payments GROUP BY order_id
), ranked_reviews AS (
    SELECT r.order_id, r.review_score,
           ROW_NUMBER() OVER (PARTITION BY r.order_id ORDER BY
             r.review_answer_timestamp DESC, r.review_creation_date DESC, r.review_id DESC) AS position
    FROM main.reviews r JOIN main.orders o ON o.order_id = r.order_id
    WHERE r.review_creation_date >= o.order_purchase_timestamp
      AND r.review_answer_timestamp >= r.review_creation_date
), base AS (
    SELECT o.*, c.customer_state, c.customer_unique_id,
           p.payment_cents, COALESCE(p.payment_rows, 0) AS payment_rows, r.review_score,
           CASE WHEN o.order_status = 'delivered' THEN 1 ELSE 0 END AS delivered,
           CASE WHEN o.order_status = 'canceled' THEN 1 ELSE 0 END AS canceled,
           CASE WHEN o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
             AND o.order_estimated_delivery_date IS NOT NULL
             AND o.order_delivered_customer_date >= o.order_purchase_timestamp THEN 1 ELSE 0 END AS delivery_eligible
    FROM main.orders o JOIN main.customers c ON c.customer_id = o.customer_id
    LEFT JOIN payment_totals p ON p.order_id = o.order_id
    LEFT JOIN ranked_reviews r ON r.order_id = o.order_id AND r.position = 1
)
SELECT base.*, SUBSTR(order_purchase_timestamp, 1, 7) AS purchase_month,
       CASE WHEN delivered = 1 AND payment_rows > 0 THEN 1 ELSE 0 END AS paid_delivered,
       CASE WHEN delivered = 1 AND payment_rows = 0 THEN 1 ELSE 0 END AS delivered_missing_payment,
       CASE WHEN delivered = 1 THEN payment_cents END AS revenue_cents,
       CASE WHEN delivered = 1 THEN review_score END AS delivered_review_score,
       CASE WHEN delivery_eligible = 1 THEN
         CASE WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 1 ELSE 0 END END AS is_late,
       CASE WHEN delivery_eligible = 1 THEN
         CASE WHEN DATE(order_delivered_customer_date) > DATE(order_estimated_delivery_date) THEN 1 ELSE 0 END END AS calendar_day_late,
       CASE WHEN delivery_eligible = 1 THEN
         JULIANDAY(order_delivered_customer_date) - JULIANDAY(order_purchase_timestamp) END AS delivery_days
FROM base;

CREATE TEMP VIEW metric_order_categories AS
SELECT i.order_id, p.product_category_name AS category_key,
       COALESCE(t.product_category_name_english, p.product_category_name, 'Unknown') AS category_label,
       COUNT(*) AS item_count, SUM(i.price_cents) AS item_sales_cents,
       SUM(i.freight_value_cents) AS freight_cents
FROM main.order_items i JOIN main.products p ON p.product_id = i.product_id
LEFT JOIN main.category_translations t ON t.product_category_name = p.product_category_name
GROUP BY i.order_id, p.product_category_name, t.product_category_name_english;

CREATE TEMP VIEW metric_order_sellers AS
SELECT order_id, seller_id, COUNT(*) AS item_count,
       SUM(price_cents) AS item_sales_cents, SUM(freight_value_cents) AS freight_cents
FROM main.order_items GROUP BY order_id, seller_id;

CREATE TEMP VIEW metric_months AS
WITH RECURSIVE bounds AS (
    SELECT DATE(MIN(order_purchase_timestamp), 'start of month') AS first_month,
           DATE(MAX(order_purchase_timestamp), 'start of month') AS last_month FROM main.orders
), months(month_start) AS (
    SELECT first_month FROM bounds WHERE first_month IS NOT NULL
    UNION ALL
    SELECT DATE(month_start, '+1 month') FROM months, bounds WHERE month_start < last_month
)
SELECT SUBSTR(month_start, 1, 7) AS purchase_month, month_start,
       DATE(month_start, '+1 month') AS next_month_start,
       CASE WHEN month_start = first_month OR month_start = last_month THEN 1 ELSE 0 END AS boundary_month
FROM months CROSS JOIN bounds;
