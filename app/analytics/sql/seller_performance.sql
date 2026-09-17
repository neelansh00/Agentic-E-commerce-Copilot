, seller_orders AS (
    SELECT seller_id, order_id, SUM(price_cents) AS item_sales_cents FROM order_items GROUP BY seller_id, order_id
), platform AS (
    SELECT AVG(review_score) AS mean_score FROM order_facts WHERE order_status = 'delivered'
)
SELECT s.seller_id, COUNT(*) AS delivered_orders, COUNT(f.review_score) AS reviewed_orders,
       SUM(s.item_sales_cents) AS item_sales_cents,
       ROUND(AVG(f.review_score), 6) AS mean_review_score,
       ROUND(p.mean_score, 6) AS platform_mean_review_score
FROM seller_orders s JOIN order_facts f ON f.order_id = s.order_id CROSS JOIN platform p
WHERE f.order_status = 'delivered'
GROUP BY s.seller_id, p.mean_score
HAVING COUNT(f.review_score) >= :min_reviewed_orders AND AVG(f.review_score) < p.mean_score
ORDER BY item_sales_cents DESC, s.seller_id LIMIT :top_n;
