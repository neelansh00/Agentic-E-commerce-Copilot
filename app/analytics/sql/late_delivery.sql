SELECT COUNT(*) AS delivered_orders,
       COUNT(CASE WHEN delivery_eligible = 1 THEN 1 END) AS eligible_orders,
       COUNT(CASE WHEN delivery_eligible = 0 THEN 1 END) AS excluded_orders,
       COUNT(CASE WHEN delivery_eligible = 1 AND is_late = 1 THEN 1 END) AS late_orders,
       ROUND(100.0 * SUM(CASE WHEN delivery_eligible = 1 THEN is_late ELSE 0 END)
           / NULLIF(SUM(delivery_eligible), 0), 6) AS late_pct,
       ROUND(AVG(CASE WHEN delivery_eligible = 1 THEN delivery_days END), 6) AS mean_delivery_days,
       COUNT(CASE WHEN delivery_eligible = 1 AND DATE(order_delivered_customer_date) > DATE(order_estimated_delivery_date) THEN 1 END) AS calendar_day_late_orders
FROM order_facts WHERE order_status = 'delivered';
