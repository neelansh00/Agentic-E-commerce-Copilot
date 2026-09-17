"""Reproducible relational checks and descriptive data-quality findings."""
import csv
from decimal import Decimal
from pathlib import Path

from app.database.ingest import SOURCES, connect_readonly, file_hash


def verify_database(database: Path, raw_dir: Path) -> dict:
    connection = connect_readonly(database)
    def scalar(sql):
        return connection.execute(sql).fetchone()[0]
    def rows(sql):
        return [dict(row) for row in connection.execute(sql)]
    try:
        checks = []
        def check(name, actual, expected, sql=None):
            checks.append({'name': name, 'actual': actual, 'expected': expected,
                           'passed': actual == expected, 'sql': sql})

        sources = {}
        for table, filename, _ in SOURCES:
            path = raw_dir / filename
            with path.open(encoding='utf-8-sig', newline='') as stream:
                reader = csv.DictReader(stream)
                total = sum(1 for _ in reader)
            sources[table] = {'rows': total, 'sha256': file_hash(path)}
            sql = f'SELECT COUNT(*) FROM {table}'
            check(f'{table}: CSV row count preserved', scalar(sql), total, sql)
        check('SQLite integrity', scalar('PRAGMA integrity_check'), 'ok')
        check('Enforced foreign keys', len(rows('PRAGMA foreign_key_check')), 0)

        joins = [
            ('orders -> customers', 'SELECT COUNT(*) FROM orders o JOIN customers c ON c.customer_id=o.customer_id', sources['orders']['rows']),
            ('items -> orders/products/sellers', '''SELECT COUNT(*) FROM order_items i
                JOIN orders o ON o.order_id=i.order_id
                JOIN products p ON p.product_id=i.product_id
                JOIN sellers s ON s.seller_id=i.seller_id''', sources['order_items']['rows']),
            ('payments -> orders', 'SELECT COUNT(*) FROM payments p JOIN orders o ON o.order_id=p.order_id', sources['payments']['rows']),
            ('reviews -> orders', 'SELECT COUNT(*) FROM reviews r JOIN orders o ON o.order_id=r.order_id', sources['reviews']['rows']),
            ('products -> optional translations', '''SELECT COUNT(*) FROM products p LEFT JOIN category_translations t
                ON p.product_category_name=t.product_category_name''', sources['products']['rows']),
            ('orders -> preaggregated child tables', '''WITH i AS (SELECT order_id, COUNT(*) n FROM order_items GROUP BY order_id),
                p AS (SELECT order_id, SUM(payment_value_cents) paid FROM payments GROUP BY order_id),
                r AS (SELECT order_id, COUNT(*) n FROM reviews GROUP BY order_id)
                SELECT COUNT(*) FROM orders o LEFT JOIN i ON i.order_id=o.order_id
                LEFT JOIN p ON p.order_id=o.order_id LEFT JOIN r ON r.order_id=o.order_id''', sources['orders']['rows']),
        ]
        for name, sql, expected in joins:
            check(name, scalar(sql), expected, sql)

        for table, filename, columns in [
            ('order_items', 'olist_order_items_dataset.csv', [('price', 'price_cents'), ('freight_value', 'freight_value_cents')]),
            ('payments', 'olist_order_payments_dataset.csv', [('payment_value', 'payment_value_cents')]),
        ]:
            with (raw_dir / filename).open(encoding='utf-8-sig', newline='') as stream:
                totals = {source: Decimal(0) for source, _ in columns}
                for row in csv.DictReader(stream):
                    for source in totals:
                        totals[source] += Decimal(row[source])
            for source, dest in columns:
                sql = f'SELECT SUM({dest}) FROM {table}'
                check(f'Exact source monetary reconciliation: {dest}', scalar(sql), int(totals[source] * 100), sql)

        quality_sql = {
            'orders_without_items': 'SELECT COUNT(*) FROM orders o WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id=o.order_id)',
            'orders_without_payments': 'SELECT COUNT(*) FROM orders o WHERE NOT EXISTS (SELECT 1 FROM payments p WHERE p.order_id=o.order_id)',
            'orders_without_reviews': 'SELECT COUNT(*) FROM orders o WHERE NOT EXISTS (SELECT 1 FROM reviews r WHERE r.order_id=o.order_id)',
            'orders_with_multiple_reviews': 'SELECT COUNT(*) FROM (SELECT order_id FROM reviews GROUP BY order_id HAVING COUNT(*)>1)',
            'review_ids_shared_by_orders': 'SELECT COUNT(*) FROM (SELECT review_id FROM reviews GROUP BY review_id HAVING COUNT(*)>1)',
            'orders_with_multiple_payments': 'SELECT COUNT(*) FROM (SELECT order_id FROM payments GROUP BY order_id HAVING COUNT(*)>1)',
            'orders_with_multiple_sellers': 'SELECT COUNT(*) FROM (SELECT order_id FROM order_items GROUP BY order_id HAVING COUNT(DISTINCT seller_id)>1)',
            'customers_with_repeat_identity': 'SELECT COUNT(*) FROM (SELECT customer_unique_id FROM customers GROUP BY customer_unique_id HAVING COUNT(*)>1)',
            'products_missing_category': 'SELECT COUNT(*) FROM products WHERE product_category_name IS NULL',
            'products_with_untranslated_category': '''SELECT COUNT(*) FROM products p WHERE product_category_name IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM category_translations t WHERE t.product_category_name=p.product_category_name)''',
            'geolocation_exact_duplicate_excess': '''SELECT SUM(n-1) FROM (SELECT COUNT(*) n FROM geolocation
                GROUP BY geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state)''',
            'zip_prefixes_with_multiple_city_labels': 'SELECT COUNT(*) FROM (SELECT geolocation_zip_code_prefix FROM geolocation GROUP BY geolocation_zip_code_prefix HAVING COUNT(DISTINCT geolocation_city)>1)',
            'zip_prefixes_with_multiple_states': 'SELECT COUNT(*) FROM (SELECT geolocation_zip_code_prefix FROM geolocation GROUP BY geolocation_zip_code_prefix HAVING COUNT(DISTINCT geolocation_state)>1)',
            'customers_without_geolocation': '''SELECT COUNT(*) FROM customers c WHERE NOT EXISTS
                (SELECT 1 FROM geolocation g WHERE g.geolocation_zip_code_prefix=c.customer_zip_code_prefix)''',
            'sellers_without_geolocation': '''SELECT COUNT(*) FROM sellers s WHERE NOT EXISTS
                (SELECT 1 FROM geolocation g WHERE g.geolocation_zip_code_prefix=s.seller_zip_code_prefix)''',
            'coordinates_outside_broad_brazil_box': '''SELECT COUNT(*) FROM geolocation WHERE
                geolocation_lat NOT BETWEEN -34 AND 6 OR geolocation_lng NOT BETWEEN -74 AND -28''',
            'delivered_orders_missing_delivery_timestamp': "SELECT COUNT(*) FROM orders WHERE order_status='delivered' AND order_delivered_customer_date IS NULL",
            'nondelivered_orders_with_delivery_timestamp': "SELECT COUNT(*) FROM orders WHERE order_status<>'delivered' AND order_delivered_customer_date IS NOT NULL",
            'approval_before_purchase': 'SELECT COUNT(*) FROM orders WHERE order_approved_at < order_purchase_timestamp',
            'carrier_before_purchase': 'SELECT COUNT(*) FROM orders WHERE order_delivered_carrier_date < order_purchase_timestamp',
            'delivery_before_purchase': 'SELECT COUNT(*) FROM orders WHERE order_delivered_customer_date < order_purchase_timestamp',
            'delivery_before_carrier': 'SELECT COUNT(*) FROM orders WHERE order_delivered_customer_date < order_delivered_carrier_date',
            'review_created_before_purchase': 'SELECT COUNT(*) FROM reviews r JOIN orders o ON o.order_id=r.order_id WHERE r.review_creation_date < o.order_purchase_timestamp',
            'zero_payment_rows': 'SELECT COUNT(*) FROM payments WHERE payment_value_cents=0',
            'zero_installment_rows': 'SELECT COUNT(*) FROM payments WHERE payment_installments=0',
            'zero_weight_products': 'SELECT COUNT(*) FROM products WHERE product_weight_g=0',
        }
        quality = {name: {'value': scalar(sql), 'sql': sql} for name, sql in quality_sql.items()}
        report = {
            'source_files': sources, 'checks': checks, 'all_checks_passed': all(c['passed'] for c in checks),
            'quality_findings': quality,
            'order_status_counts': rows('SELECT order_status, COUNT(*) AS orders FROM orders GROUP BY order_status ORDER BY orders DESC'),
            'purchase_range': rows('SELECT MIN(order_purchase_timestamp) AS earliest, MAX(order_purchase_timestamp) AS latest FROM orders')[0],
            'untranslated_categories': rows('''SELECT p.product_category_name, COUNT(*) AS products FROM products p
                LEFT JOIN category_translations t ON t.product_category_name=p.product_category_name
                WHERE p.product_category_name IS NOT NULL AND t.product_category_name IS NULL GROUP BY p.product_category_name'''),
            'join_fanout_example': rows('''SELECT
                (SELECT SUM(payment_value_cents) FROM payments) AS source_payment_cents,
                (SELECT SUM(p.payment_value_cents) FROM payments p JOIN order_items i ON i.order_id=p.order_id) AS naive_item_join_payment_cents''')[0],
        }
        return report
    finally:
        connection.close()


def verification_markdown(report: dict) -> str:
    lines = ['# Database verification and quality findings', '',
             'Generated by `python scripts/verify_database.py`. SQL and source checksums are in `verification_report.json`.', '',
             f"All {len(report['checks'])} reconciliation/integrity/join checks passed: **{report['all_checks_passed']}**.", '',
             '| Check | Actual | Expected | Passed |', '|---|---:|---:|---|']
    for c in report['checks']:
        lines.append(f"| {c['name']} | {c['actual']} | {c['expected']} | {c['passed']} |")
    lines += ['', '## Quality observations (preserved, not silently corrected)', '',
              'Counts are records unless the finding explicitly refers to orders, IDs, or ZIP prefixes.',
              'The broad Brazil bounding box is only an outlier flag, not proof of an invalid coordinate.', '',
              '| Finding | Count |', '|---|---:|']
    for name, value in report['quality_findings'].items():
        lines.append(f"| {name.replace('_', ' ')} | {value['value']:,} |")
    lines += ['', '## Order statuses', '', '| Status | Orders |', '|---|---:|']
    for row in report['order_status_counts']:
        lines.append(f"| {row['order_status']} | {row['orders']:,} |")
    lines += ['', f"Purchase range: {report['purchase_range']['earliest']} to {report['purchase_range']['latest']}.", '',
              '## Fanout warning', '',
              f"All payment rows total {report['join_fanout_example']['source_payment_cents']:,} cents. "
              f"A naive join to items produces {report['join_fanout_example']['naive_item_join_payment_cents']:,} cents.",
              'These are reconciliation totals across all statuses, not a definition of business revenue.',
              'Aggregate each child table to the intended grain before combining them.', '']
    return '\n'.join(lines)
