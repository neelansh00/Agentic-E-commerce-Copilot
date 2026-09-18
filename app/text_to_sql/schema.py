"""Explainable keyword retrieval plus shortest join paths over the real schema."""
from collections import deque
import re
from app.database.ingest import SOURCES, connect_readonly

TABLES = {spec[0] for spec in SOURCES}
KEYWORDS = {
    'customers': {'customer', 'customers', 'buyer', 'buyers', 'state', 'states', 'region', 'regions', 'city', 'cities'},
    'orders': {'order', 'orders', 'delivery', 'deliveries', 'late', 'lateness', 'cancel', 'canceled', 'cancellation', 'month', 'months', 'monthly', 'trend'},
    'order_items': {'seller', 'sellers', 'category', 'categories', 'product', 'products', 'item', 'items', 'sales', 'freight'},
    'payments': {'revenue', 'payment', 'payments', 'paid', 'aov', 'value', 'installment', 'installments'},
    'products': {'category', 'categories', 'product', 'products', 'weight', 'dimensions'},
    'category_translations': {'category', 'categories', 'translation', 'english'},
    'reviews': {'review', 'reviews', 'rating', 'ratings', 'score', 'scores', 'satisfaction', 'poor'},
    'sellers': {'seller', 'sellers'},
    'geolocation': {'latitude', 'longitude', 'coordinates', 'geolocation', 'map', 'maps'},
}
EDGES = [('customers', 'orders'), ('orders', 'order_items'), ('orders', 'payments'),
         ('orders', 'reviews'), ('order_items', 'products'), ('order_items', 'sellers'),
         ('products', 'category_translations')]
NOTES = {
    'customers': 'customer_id is the join key; customer_unique_id is the repeat-buyer identity. State is customer geography.',
    'orders': 'One row per order. Timestamps are naive ISO text. Successful means delivered. Keep missing delivery dates out of lateness denominators.',
    'payments': 'Many rows per order. Sum payment_value_cents per order before joining other children. Money is integer BRL cents.',
    'order_items': 'Many rows per order; price_cents is item sales, freight_value_cents is separate. Deduplicate order/seller or order/category for ratings/delivery.',
    'reviews': 'review_id is not unique; composite PK(review_id,order_id). Latest eligible review per order; never weight orders by review count.',
    'products': 'Category may be NULL; preserve Unknown. Raw misspellings were corrected to product_name_length/product_description_length.',
    'category_translations': 'Optional LEFT JOIN by product_category_name; missing translations retain raw category.',
    'sellers': 'Seller geography is not customer geography. Order reviews are not direct seller ratings.',
    'geolocation': 'ZIP prefixes are NOT unique. Raw joins inflate counts; no FK to customers/sellers. Aggregate first; outliers exist.',
}


def retrieve_schema(question: str) -> tuple[list[str], dict[str, str]]:
    words = set(re.findall(r'[a-z_]+', question.lower()))
    reasons = {table: 'Matched: ' + ', '.join(sorted(words & terms))
               for table, terms in KEYWORDS.items() if words & terms}
    # Orders is the central grain for analytical questions, not a full-schema fallback.
    reasons.setdefault('orders', 'Central order grain')
    graph = {t: set() for t in TABLES}
    for left, right in EDGES:
        graph[left].add(right)
        graph[right].add(left)
    for target in list(reasons):
        if target == 'geolocation':
            continue
        queue = deque([['orders']])
        seen = {'orders'}
        while queue:
            path = queue.popleft()
            if path[-1] == target:
                for bridge in path:
                    reasons.setdefault(bridge, f'Join bridge to {target}')
                break
            for neighbor in sorted(graph[path[-1]] - seen):
                seen.add(neighbor)
                queue.append(path + [neighbor])
    return sorted(reasons), reasons


def schema_context(database, tables: list[str]) -> str:
    if not set(tables) <= TABLES:
        raise ValueError('Unknown schema table')
    db = connect_readonly(database)
    try:
        blocks = []
        for table in tables:
            columns = db.execute(f'PRAGMA table_info({table})').fetchall()
            if not columns:
                raise ValueError(f'Missing table: {table}; rebuild database first')
            fields = ', '.join(f"{r['name']} {r['type']}" + (' NOT NULL' if r['notnull'] else '') for r in columns)
            pk = ', '.join(r['name'] for r in sorted(columns, key=lambda r: r['pk']) if r['pk'])
            fks = [f"{r['from']} -> {r['table']}.{r['to']}" for r in db.execute(f'PRAGMA foreign_key_list({table})')]
            blocks.append(f"{table}({fields}); PK({pk}); FKs: {', '.join(fks) or 'none'}.\n{NOTES[table]}")
        return '\n\n'.join(blocks)
    finally:
        db.close()
