SELECT customer_state, COUNT(*) AS total_orders,
       COUNT(CASE WHEN order_status = 'canceled' THEN 1 END) AS canceled_orders,
       ROUND(100.0 * COUNT(CASE WHEN order_status = 'canceled' THEN 1 END) / COUNT(*), 6) AS cancellation_pct
FROM order_facts GROUP BY customer_state
ORDER BY cancellation_pct DESC, total_orders DESC, customer_state;
