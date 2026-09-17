, bounds AS (
    SELECT DATE(MIN(order_purchase_timestamp), 'start of month') AS first_month,
           DATE(MAX(order_purchase_timestamp), 'start of month') AS last_month FROM orders
), months(month_start) AS (
    SELECT first_month FROM bounds WHERE first_month IS NOT NULL
    UNION ALL
    SELECT DATE(month_start, '+1 month') FROM months, bounds WHERE month_start < last_month
)
SELECT SUBSTR(m.month_start, 1, 7) AS purchase_month,
       CASE WHEN m.month_start IN (b.first_month, b.last_month) THEN 1 ELSE 0 END AS boundary_month,
       COUNT(f.order_id) AS total_orders,
       COUNT(CASE WHEN f.order_status = 'delivered' THEN 1 END) AS delivered_orders,
       COUNT(CASE WHEN f.order_status = 'delivered' AND f.payment_rows > 0 THEN 1 END) AS paid_delivered_orders,
       COUNT(CASE WHEN f.order_status = 'delivered' AND f.payment_rows = 0 THEN 1 END) AS delivered_missing_payment,
       SUM(CASE WHEN f.order_status = 'delivered' THEN f.payment_cents END) AS revenue_cents,
       ROUND(AVG(CASE WHEN f.order_status = 'delivered' THEN f.payment_cents END), 6) AS aov_cents
FROM months m CROSS JOIN bounds b LEFT JOIN order_facts f
  ON f.order_purchase_timestamp >= m.month_start
 AND f.order_purchase_timestamp < DATE(m.month_start, '+1 month')
GROUP BY m.month_start, b.first_month, b.last_month ORDER BY purchase_month;
