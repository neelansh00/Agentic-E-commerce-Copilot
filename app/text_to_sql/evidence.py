"""Display captions and group identities come from evidence, never model prose."""
import json
import re

DIMENSIONS = ('purchase_month', 'customer_state', 'seller_id', 'category_label', 'category_key',
              'delivery_group', 'order_id', 'product_id')
CAPTIONS = {
    'total_orders': 'Total orders', 'unique_buyers': 'Unique buyers', 'delivered_orders': 'Delivered orders',
    'paid_delivered_orders': 'Delivered orders with payments', 'delivered_missing_payment': 'Delivered orders missing payment',
    'revenue_cents': 'Delivered payment revenue (BRL cents)', 'aov_cents': 'Average delivered payment value (BRL cents)',
    'canceled_orders': 'Canceled orders', 'cancellation_pct': 'Cancellation rate (%)',
    'item_sales_cents': 'Delivered item sales (BRL cents)', 'freight_cents': 'Item freight (BRL cents)',
    'item_count': 'Item count', 'eligible_orders': 'Eligible delivery orders', 'excluded_orders': 'Excluded delivered orders',
    'late_orders': 'Late eligible orders', 'late_pct': 'Eligible delivery late rate (%)',
    'mean_delivery_days': 'Mean eligible delivery duration (days)', 'calendar_day_late_orders': 'Calendar-day late orders',
    'reviewed_orders': 'Orders with selected eligible reviews', 'missing_eligible_review': 'Orders missing eligible reviews',
    'mean_review_score': 'Mean selected review score', 'poor_review_orders': 'Orders with poor selected reviews',
    'poor_review_pct': 'Poor-review rate among reviewed orders (%)', 'platform_mean_review_score': 'Platform delivered-order mean review score',
    'platform_late_pct': 'Platform eligible delivery late rate (%)', 'boundary_month': 'Dataset boundary month flag',
    'payment_rows': 'Payment rows',
}


def render_cell(result, row_index, column, fallback=False):
    row = result.rows[row_index]
    # Keep fallback captions literal for compatibility and clearly identify them.
    caption = column if fallback else CAPTIONS.get(column, 'Observed value')
    # Unknown SQL aliases can themselves contain an unsupported interpretation.
    if re.search(r'\b(highest|lowest|best|worst|top|maximum|minimum|cause|causal)\b', caption.replace('_', ' '), re.I):
        caption = 'Observed value'
    group = {name: row[name] for name in DIMENSIONS if name in row and name != column}
    context = ' | group=' + json.dumps(group, ensure_ascii=False) if group else ''
    return f'{caption}: {json.dumps(row[column], ensure_ascii=False)} [row {row_index}, {column}]{context}'
