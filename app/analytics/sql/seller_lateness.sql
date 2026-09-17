, seller_orders AS (SELECT DISTINCT seller_id, order_id FROM order_items),
platform AS (SELECT AVG(1.0 * is_late) AS late_rate FROM order_facts WHERE delivery_eligible = 1)
SELECT s.seller_id, COUNT(*) AS eligible_orders, SUM(f.is_late) AS late_orders,
       ROUND(100.0 * AVG(f.is_late), 6) AS late_pct,
       ROUND(100.0 * p.late_rate, 6) AS platform_late_pct
FROM seller_orders s JOIN order_facts f ON f.order_id = s.order_id CROSS JOIN platform p
WHERE f.delivery_eligible = 1
GROUP BY s.seller_id, p.late_rate
HAVING COUNT(*) >= :min_orders AND AVG(1.0 * f.is_late) > p.late_rate
ORDER BY late_pct DESC, eligible_orders DESC, s.seller_id LIMIT :top_n;
