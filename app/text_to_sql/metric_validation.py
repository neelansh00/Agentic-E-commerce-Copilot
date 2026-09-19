"""Small semantic invariants; safety validation alone cannot check metric meaning."""
from datetime import date
import sqlglot
import re
from sqlglot import exp
from app.text_to_sql.safety import SQLSafetyError, validate_sql


def validate_metric_grain(sql):
    tables = set(validate_sql(sql).tables)
    if 'metric_orders' in tables and tables & {'payments', 'reviews', 'order_items'}:
        raise SQLSafetyError('Do not join raw child tables to metric_orders; use the order/category or order/seller aggregate view')
    if {'metric_order_categories', 'metric_order_sellers'} <= tables:
        raise SQLSafetyError('Do not combine category and seller grains in one metric query; a shared allocation policy is required')
    if 'metric_orders' in tables and tables & {'metric_order_categories', 'metric_order_sellers'}:
        tree = sqlglot.parse_one(sql, read='sqlite')
        for aggregate in tree.find_all(exp.AggFunc):
            if any(c.name.lower() in {'payment_cents', 'revenue_cents'} for c in aggregate.find_all(exp.Column)):
                raise SQLSafetyError('Payment revenue cannot be aggregated across category/seller rows without an allocation policy; use item_sales_cents')


def requires_continuous_months(question):
    intent = question.split('\n', 1)[0].lower()
    return bool(re.search(r'month|monthly', intent)) and not re.search(r'\b(top|highest|lowest|only|selected|exclude|excluding|nonempty)\b', intent)


def validate_metric_result(result, continuous_months=False):
    for row in result.rows:
        if row.get('paid_delivered_orders') == 0:
            if 'revenue_cents' in row and row['revenue_cents'] is not None:
                raise SQLSafetyError('Revenue must be NULL when no eligible payment records exist; do not COALESCE money to zero')
            if 'aov_cents' in row and row['aov_cents'] is not None:
                raise SQLSafetyError('AOV must be NULL for a zero paid-order denominator')
        if {'eligible_orders', 'late_orders'} <= row.keys() and row['eligible_orders'] is not None and row['late_orders'] is not None:
            if not 0 <= row['late_orders'] <= row['eligible_orders']:
                raise SQLSafetyError('Late orders must be a subset of the eligible delivery population; check join grain')
    if continuous_months and not result.truncated and 'purchase_month' in result.columns and len(result.rows) > 1:
        months = sorted({r['purchase_month'] for r in result.rows})
        try:
            values = [date.fromisoformat(m + '-01') for m in months]
        except (TypeError, ValueError):
            raise SQLSafetyError('Monthly purchase cohorts must use YYYY-MM') from None
        indices = [d.year * 12 + d.month for d in values]
        if len(indices) != indices[-1] - indices[0] + 1:
            raise SQLSafetyError('Monthly cohort results must include empty calendar months; drive the query from metric_months LEFT JOIN metric_orders')
