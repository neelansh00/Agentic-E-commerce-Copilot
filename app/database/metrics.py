"""Trusted view definitions and their raw-table dependencies, independent of questions."""
from pathlib import Path

VIEW_SQL = Path(__file__).with_name('metric_views.sql').read_text(encoding='utf-8')
VIEW_DEPENDENCIES = {
    'metric_orders': {'orders', 'customers', 'payments', 'reviews'},
    'metric_order_categories': {'order_items', 'products', 'category_translations'},
    'metric_order_sellers': {'order_items'},
    'metric_months': {'orders'},
}
VIEW_CONTEXTS = {
    'metric_orders': {'metric_orders', 'payment_totals', 'ranked_reviews', 'base'},
    'metric_months': {'metric_months', 'bounds', 'months'},
    'metric_order_categories': {'metric_order_categories'},
    'metric_order_sellers': {'metric_order_sellers'},
}
VIEW_NOTES = {
    'metric_orders': 'Exactly one row per order. delivered/canceled/paid_delivered/delivered_missing_payment are 0/1. SUM(revenue_cents) is delivered payment revenue; AVG(revenue_cents) is AOV. Unknown revenue is NULL, recorded zero remains zero. review_score selects the latest eligible review; delivered_review_score additionally excludes non-delivered orders. delivery_eligible is 0/1. is_late, calendar_day_late and delivery_days are NULL for ineligible orders. AVG(delivery_days) automatically excludes them. SUM(is_late) / SUM(delivery_eligible) uses the eligible denominator. No raw-child joins are needed.',
    'metric_order_categories': 'Exactly one row per (order_id, category_key), including NULL category. Join metric_orders by order_id. SUM(item_count/item_sales_cents/freight_cents) preserves item sales; COUNT(*)/AVG(delivery_days) after delivery eligibility filter counts each order/category once. Multi-category counts are not additive. Never sum order payment revenue across this one-to-many join.',
    'metric_order_sellers': 'Exactly one row per (order_id, seller_id). Join metric_orders by order_id. Filter delivered=1 for seller sales/reviews; delivery_eligible=1 for lateness. One order score per seller/order. Platform review mean and late rate must come from metric_orders independently, not this seller join.',
    'metric_months': 'Complete purchase-month spine from first to last observed order, including empty months. Start monthly time-series FROM metric_months LEFT JOIN metric_orders USING(purchase_month). COUNT(order_id) counts zero in empty months; COALESCE only count sums, never revenue/AOV. Do not put right-side filters in WHERE, which drops empty months.',
}


def available_views(tables):
    tables = set(tables)
    result = set(tables) & VIEW_DEPENDENCIES.keys()
    if 'orders' in tables:
        result |= {'metric_orders', 'metric_months'}
    if 'products' in tables:
        result.add('metric_order_categories')
    if 'order_items' in tables:
        result.add('metric_order_sellers')
    return result
