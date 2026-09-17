SELECT p.product_category_name AS category_key,
       COALESCE(t.product_category_name_english, p.product_category_name, 'Unknown') AS category_label,
       COUNT(*) AS item_count, COUNT(DISTINCT i.order_id) AS delivered_orders,
       SUM(i.price_cents) AS item_sales_cents, SUM(i.freight_value_cents) AS freight_cents
FROM order_items i JOIN orders o ON o.order_id = i.order_id
JOIN products p ON p.product_id = i.product_id
LEFT JOIN category_translations t ON t.product_category_name = p.product_category_name
WHERE o.order_status = 'delivered'
GROUP BY p.product_category_name, t.product_category_name_english
ORDER BY item_sales_cents DESC, category_key LIMIT :top_n;
