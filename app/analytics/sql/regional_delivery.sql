SELECT customer_state, COUNT(*) AS total_orders,
       SUM(delivery_eligible) AS eligible_orders,
       SUM(CASE WHEN delivery_eligible = 1 THEN is_late ELSE 0 END) AS late_orders,
       ROUND(100.0 * SUM(CASE WHEN delivery_eligible = 1 THEN is_late ELSE 0 END)
           / NULLIF(SUM(delivery_eligible), 0), 6) AS late_pct,
       ROUND(AVG(CASE WHEN delivery_eligible = 1 THEN delivery_days END), 6) AS mean_delivery_days
FROM order_facts GROUP BY customer_state ORDER BY total_orders DESC, customer_state;
