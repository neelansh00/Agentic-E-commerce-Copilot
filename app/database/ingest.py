"""Strict CSV ingestion with atomic replacement and no third-party dependencies."""
from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import math
from pathlib import Path
import sqlite3
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = Path(__file__).with_name('schema.sql')

# Mapping is explicit so source schema changes fail loudly instead of shifting columns.
# (database table, CSV filename, space-separated source columns)
SOURCES = [
    ('customers', 'olist_customers_dataset.csv', 'customer_id customer_unique_id customer_zip_code_prefix customer_city customer_state'),
    ('sellers', 'olist_sellers_dataset.csv', 'seller_id seller_zip_code_prefix seller_city seller_state'),
    ('category_translations', 'product_category_name_translation.csv', 'product_category_name product_category_name_english'),
    ('products', 'olist_products_dataset.csv', 'product_id product_category_name product_name_lenght product_description_lenght product_photos_qty product_weight_g product_length_cm product_height_cm product_width_cm'),
    ('orders', 'olist_orders_dataset.csv', 'order_id customer_id order_status order_purchase_timestamp order_approved_at order_delivered_carrier_date order_delivered_customer_date order_estimated_delivery_date'),
    ('order_items', 'olist_order_items_dataset.csv', 'order_id order_item_id product_id seller_id shipping_limit_date price freight_value'),
    ('payments', 'olist_order_payments_dataset.csv', 'order_id payment_sequential payment_type payment_installments payment_value'),
    ('reviews', 'olist_order_reviews_dataset.csv', 'review_id order_id review_score review_comment_title review_comment_message review_creation_date review_answer_timestamp'),
    ('geolocation', 'olist_geolocation_dataset.csv', 'geolocation_zip_code_prefix geolocation_lat geolocation_lng geolocation_city geolocation_state'),
]
RENAMES = {'product_name_lenght': 'product_name_length', 'product_description_lenght': 'product_description_length',
           'price': 'price_cents', 'freight_value': 'freight_value_cents', 'payment_value': 'payment_value_cents'}
MONEY = {'price', 'freight_value', 'payment_value'}
INTEGERS = {'order_item_id', 'payment_sequential', 'payment_installments', 'review_score',
            'product_name_lenght', 'product_description_lenght', 'product_photos_qty',
            'product_weight_g', 'product_length_cm', 'product_height_cm', 'product_width_cm'}
DATES = {'shipping_limit_date', 'order_purchase_timestamp', 'order_approved_at',
         'order_delivered_carrier_date', 'order_delivered_customer_date', 'order_estimated_delivery_date',
         'review_creation_date', 'review_answer_timestamp'}


def file_hash(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def convert(column: str, value: str):
    if not value.strip():
        return None
    if column in MONEY | INTEGERS:
        number = Decimal(value) * (100 if column in MONEY else 1)
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError(f'Non-integral value after conversion: {column}={value}')
        return int(number)
    if column in DATES:
        parsed = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        if parsed.strftime('%Y-%m-%d %H:%M:%S') != value:
            raise ValueError(f'Noncanonical timestamp: {value}')
    if column in {'geolocation_lat', 'geolocation_lng'}:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f'Nonfinite coordinate: {value}')
        return number
    # Identifiers, ZIP prefixes, city names and free text remain source strings.
    return value


def load_table(connection: sqlite3.Connection, raw_dir: Path, spec: tuple) -> dict:
    table, filename, source_columns = spec
    columns = source_columns.split()
    database_columns = [RENAMES.get(c, c) for c in columns]
    if table == 'geolocation':
        database_columns.insert(0, 'geolocation_row_id')
    sql = f"INSERT INTO {table} ({', '.join(database_columns)}) VALUES ({', '.join('?' for _ in database_columns)})"
    path = raw_dir / filename
    source_hash = file_hash(path)
    count = 0
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != columns:
            raise ValueError(f'{filename}: unexpected CSV header: {reader.fieldnames}')
        batch = []
        for count, row in enumerate(reader, start=1):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'{filename}: malformed data record {count}')
            try:
                values = [convert(c, row[c]) for c in columns]
            except (ValueError, ArithmeticError) as exc:
                raise ValueError(f'{filename}: data record {count}: {exc}') from exc
            if table == 'geolocation':
                values.insert(0, count)
            batch.append(values)
            if len(batch) == 5000:
                connection.executemany(sql, batch)
                batch.clear()
        if batch:
            connection.executemany(sql, batch)
    if file_hash(path) != source_hash:
        raise ValueError(f'Source changed during ingestion: {filename}')
    actual = connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    if actual != count:
        raise ValueError(f'Row-count mismatch: {table}: source={count}, loaded={actual}')
    return {'file': filename, 'rows': count, 'sha256': source_hash}


def load_database(raw_dir: Path, database: Path) -> dict:
    """Build a separate DB, validate it, then atomically replace the requested target.

    A rejected source row leaves the previous database intact. No INSERT OR IGNORE,
    implicit deduplication, or source CSV mutation is permitted.
    """
    start = time.perf_counter()
    raw_dir, database = Path(raw_dir), Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='olist-build-', suffix='.sqlite', dir=database.parent, delete=False) as temp:
        temporary = Path(temp.name)
    connection = None
    try:
        connection = sqlite3.connect(temporary)
        connection.execute('PRAGMA foreign_keys = ON')
        # Create secondary indexes after bulk ingestion for faster loading.
        schema = SCHEMA.read_text(encoding='utf-8')
        tables, indexes = schema.split('CREATE INDEX', 1)
        connection.executescript(tables)
        manifest = {}
        with connection:
            for spec in SOURCES:
                manifest[spec[0]] = load_table(connection, raw_dir, spec)
        connection.executescript('CREATE INDEX' + indexes)
        fk_errors = connection.execute('PRAGMA foreign_key_check').fetchall()
        integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
        if fk_errors or integrity != 'ok':
            raise ValueError(f'Integrity failure: {integrity}; foreign keys: {fk_errors[:5]}')
        connection.execute('ANALYZE')
        connection.commit()
        connection.close()
        connection = None
        temporary.replace(database)
        return {'database': database.name, 'schema_sha256': file_hash(SCHEMA),
                'tables': manifest, 'total_rows': sum(t['rows'] for t in manifest.values()),
                'foreign_key_violations': len(fk_errors), 'integrity_check': integrity,
                'elapsed_seconds': round(time.perf_counter() - start, 3)}
    finally:
        if connection is not None:
            connection.close()
        temporary.unlink(missing_ok=True)


def connect_readonly(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
    # The order/customer/review joins repeatedly revisit pages. A bounded 64 MiB
    # cache avoids the tiny default cache becoming an I/O bottleneck on this data.
    connection.execute('PRAGMA cache_size = -65536')
    connection.execute('PRAGMA foreign_keys = ON')
    connection.execute('PRAGMA temp_store = MEMORY')
    from app.database.metrics import VIEW_SQL
    connection.executescript(VIEW_SQL)
    connection.execute('PRAGMA query_only = ON')
    connection.row_factory = sqlite3.Row
    return connection
