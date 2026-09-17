"""Run a fixed, reviewed reference query. This is not arbitrary SQL execution."""
from dataclasses import dataclass, field
from pathlib import Path
import time

SQL_DIR = Path(__file__).with_name('sql')
METRIC_VERSION = '1'


@dataclass(frozen=True)
class ReferenceQuery:
    question: str
    tables: tuple[str, ...]
    interpretation: str
    parameters: dict = field(default_factory=dict)


QUERIES = {
    'overview': ReferenceQuery('How many orders and buyers are there, and what are delivered-order revenue, AOV and cancellation rate?',
        ('orders', 'customers', 'payments'), 'Payment revenue includes freight; missing payments are excluded from AOV and shown separately.'),
    'monthly_revenue': ReferenceQuery('How does delivered-order payment revenue vary by purchase month?',
        ('orders', 'payments'), 'Purchase cohorts, not cash-flow months. Boundary and low-coverage cohorts cannot establish a revenue decline cause.'),
    'state_aov': ReferenceQuery('How does delivered-order average payment value vary by customer state?',
        ('orders', 'customers', 'payments'), 'AOV uses only delivered orders with recorded payments; compare denominators as well as means.'),
    'state_cancellation': ReferenceQuery('Which customer states have the highest cancellation rate?',
        ('orders', 'customers'), 'Canceled divided by all orders; unavailable is not canceled. Small state samples need caution.'),
    'category_sales': ReferenceQuery('What are the top 10 categories by delivered item sales, excluding freight?',
        ('orders', 'order_items', 'products', 'category_translations'), 'Item sales are not allocated payment revenue. Unknown and untranslated categories remain eligible.', {'top_n': 10}),
    'late_delivery': ReferenceQuery('What proportion of eligible delivered orders arrived after the estimated timestamp?',
        ('orders',), 'Strict timestamp lateness; calendar-day count is sensitivity context. Missing/invalid deliveries are excluded.'),
    'late_reviews': ReferenceQuery('How do review scores and poor-review rates differ between late and on-time deliveries?',
        ('orders', 'reviews'), 'Descriptive association only; no test, significance or causality claim. One eligible selected review per order.'),
    'category_delivery': ReferenceQuery('Which 10 categories have the longest mean delivery time with at least 30 eligible orders?',
        ('orders', 'order_items', 'products', 'category_translations'), 'One observation per order/category; categories on the same order overlap.', {'min_orders': 30, 'top_n': 10}),
    'seller_performance': ReferenceQuery('Which 20 sellers lead item sales among those with at least 20 reviewed delivered orders and below-platform-average scores?',
        ('orders', 'order_items', 'reviews'), 'Order scores associated with sellers, not direct seller ratings; multi-seller attribution is shared.', {'min_reviewed_orders': 20, 'top_n': 20}),
    'seller_lateness': ReferenceQuery('Which 20 sellers have the highest above-platform late rates with at least 30 eligible deliveries?',
        ('orders', 'order_items'), 'Descriptive above-average screen, not statistical anomaly detection or seller fault.', {'min_orders': 30, 'top_n': 20}),
    'regional_delivery': ReferenceQuery('How do order volume and delivery performance vary across customer states?',
        ('orders', 'customers'), 'All-order volume and eligible-delivery late rates use different denominators; compare both.'),
}


def query_sql(name: str) -> str:
    if name not in QUERIES:
        raise ValueError(f'Unknown reference query: {name}')
    return (SQL_DIR / 'order_facts.sql').read_text(encoding='utf-8') + '\n' + (SQL_DIR / f'{name}.sql').read_text(encoding='utf-8')


def run_query(connection, name: str, parameters: dict | None = None) -> dict:
    sql = query_sql(name)
    defaults = QUERIES[name].parameters
    supplied = parameters or {}
    if set(supplied) - set(defaults):
        raise ValueError('Unknown query parameter')
    params = {**defaults, **supplied}
    if any(type(v) is not int or v < 1 for v in params.values()):
        raise ValueError('Thresholds and limits must be positive integers')
    start = time.perf_counter()
    cursor = connection.execute(sql, params)
    columns = [c[0] for c in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return {'sql': sql, 'parameters': params, 'columns': columns, 'rows': rows,
            'execution_ms': round(1000 * (time.perf_counter() - start), 3)}
