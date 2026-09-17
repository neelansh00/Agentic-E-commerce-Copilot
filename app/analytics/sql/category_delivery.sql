, category_orders AS (
    SELECT DISTINCT i.order_id, p.product_category_name AS category_key
    FROM order_items i JOIN products p ON p.product_id = i.product_id
)
SELECT c.category_key, COALESCE(t.product_category_name_english, c.category_key, 'Unknown') AS category_label,
       COUNT(*) AS eligible_orders, SUM(f.is_late) AS late_orders,
       ROUND(100.0 * SUM(f.is_late) / COUNT(*), 6) AS late_pct,
       ROUND(AVG(f.delivery_days), 6) AS mean_delivery_days
FROM category_orders c JOIN order_facts f ON f.order_id = c.order_id
LEFT JOIN category_translations t ON t.product_category_name = c.category_key
WHERE f.delivery_eligible = 1
GROUP BY c.category_key, t.product_category_name_english HAVING COUNT(*) >= :min_orders
ORDER BY mean_delivery_days DESC, c.category_key LIMIT :top_n;
