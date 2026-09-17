SELECT customer_state, COUNT(*) AS delivered_orders,
       COUNT(payment_cents) AS paid_delivered_orders,
       COUNT(*) - COUNT(payment_cents) AS delivered_missing_payment,
       SUM(payment_cents) AS revenue_cents, ROUND(AVG(payment_cents), 6) AS aov_cents
FROM order_facts WHERE order_status = 'delivered'
GROUP BY customer_state ORDER BY aov_cents DESC, customer_state;
