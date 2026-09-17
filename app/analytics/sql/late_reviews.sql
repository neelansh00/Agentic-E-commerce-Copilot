SELECT CASE WHEN is_late = 1 THEN 'late' ELSE 'on_time' END AS delivery_group,
       COUNT(*) AS eligible_orders, COUNT(review_score) AS reviewed_orders,
       COUNT(*) - COUNT(review_score) AS missing_eligible_review,
       ROUND(AVG(review_score), 6) AS mean_review_score,
       COUNT(CASE WHEN review_score <= 2 THEN 1 END) AS poor_review_orders,
       ROUND(100.0 * COUNT(CASE WHEN review_score <= 2 THEN 1 END) / NULLIF(COUNT(review_score), 0), 6) AS poor_review_pct
FROM order_facts WHERE delivery_eligible = 1
GROUP BY is_late ORDER BY delivery_group;
