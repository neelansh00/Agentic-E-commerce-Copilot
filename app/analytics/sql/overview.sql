SELECT COUNT(*) AS total_orders,
       COUNT(DISTINCT customer_unique_id) AS unique_buyers,
       COUNT(CASE WHEN order_status = 'delivered' THEN 1 END) AS delivered_orders,
       COUNT(CASE WHEN order_status = 'delivered' AND payment_rows > 0 THEN 1 END) AS paid_delivered_orders,
       COUNT(CASE WHEN order_status = 'delivered' AND payment_rows = 0 THEN 1 END) AS delivered_missing_payment,
       SUM(CASE WHEN order_status = 'delivered' THEN payment_cents END) AS revenue_cents,
       ROUND(AVG(CASE WHEN order_status = 'delivered' THEN payment_cents END), 6) AS aov_cents,
       COUNT(CASE WHEN order_status = 'canceled' THEN 1 END) AS canceled_orders,
       ROUND(100.0 * COUNT(CASE WHEN order_status = 'canceled' THEN 1 END) / NULLIF(COUNT(*), 0), 6) AS cancellation_pct
FROM order_facts;
