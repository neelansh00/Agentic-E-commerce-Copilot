"""Small synthetic fixtures exercise failure modes without the Kaggle download."""
import csv
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app.database.ingest import SOURCES, connect_readonly, convert, file_hash, load_database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / 'raw'
        self.raw.mkdir()
        self.database = self.root / 'test.sqlite'
        self.fixture = {
            'customers': [['c1', 'person1', '00123', 'city', 'SP']],
            'sellers': [['s1', '00123', 'city', 'SP']],
            'category_translations': [['category', 'category_en']],
            'products': [['p1', 'category', '10.0', '', '1.0', '100.0', '10.0', '10.0', '10.0']],
            'orders': [['o1', 'c1', 'delivered', '2018-01-01 10:00:00', '', '', '2018-01-05 10:00:00', '2018-01-10 00:00:00']],
            'order_items': [['o1', '1', 'p1', 's1', '2018-01-03 00:00:00', '0.10', '2.99']],
            'payments': [['o1', '1', 'credit_card', '1', '3.09']],
            'reviews': [['r1', 'o1', '5', '', 'Great, thanks!\nSecond line.', '2018-01-06 00:00:00', '2018-01-07 12:00:00']],
            'geolocation': [['00123', '-23.5', '-46.6', 'city', 'SP']] * 2,
        }
        self.write_fixture()

    def write_fixture(self):
        for table, filename, header in SOURCES:
            with (self.raw / filename).open('w', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(header.split())
                writer.writerows(self.fixture[table])

    def test_load_preserves_grain_types_nulls_and_sources(self):
        before = {p.name: file_hash(p) for p in self.raw.glob('*.csv')}
        report = load_database(self.raw, self.database)
        self.assertEqual(report['total_rows'], 10)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT price_cents, freight_value_cents FROM order_items').fetchone(), (10, 299))
            self.assertEqual(db.execute('SELECT customer_zip_code_prefix FROM customers').fetchone()[0], '00123')
            self.assertIsNone(db.execute('SELECT product_description_length FROM products').fetchone()[0])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM geolocation').fetchone()[0], 2)
            self.assertIn('\n', db.execute('SELECT review_comment_message FROM reviews').fetchone()[0])
        self.assertEqual(before, {p.name: file_hash(p) for p in self.raw.glob('*.csv')})

    def test_rebuild_is_idempotent(self):
        first = load_database(self.raw, self.database)
        second = load_database(self.raw, self.database)
        self.assertEqual(first['tables'], second['tables'])
        self.assertEqual(first['total_rows'], second['total_rows'])

    def test_failed_rebuild_preserves_previous_database(self):
        load_database(self.raw, self.database)
        before = self.database.read_bytes()
        self.fixture['order_items'][0][2] = 'missing_product'
        self.write_fixture()
        with self.assertRaises(sqlite3.IntegrityError):
            load_database(self.raw, self.database)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertFalse(list(self.root.glob('olist-build-*')))

    def test_duplicate_composite_key_is_rejected(self):
        self.fixture['payments'] *= 2
        self.write_fixture()
        with self.assertRaises(sqlite3.IntegrityError):
            load_database(self.raw, self.database)
        self.assertFalse(self.database.exists())

    def test_reviews_allow_shared_id_across_orders(self):
        self.fixture['orders'].append(['o2', 'c1', 'created', '2018-01-02 10:00:00', '', '', '', '2018-01-10 00:00:00'])
        self.fixture['reviews'].append(['r1', 'o2', '4', '', '', '2018-01-06 00:00:00', '2018-01-07 12:00:00'])
        self.write_fixture()
        self.assertEqual(load_database(self.raw, self.database)['tables']['reviews']['rows'], 2)

    def test_invalid_review_score_is_rejected(self):
        self.fixture['reviews'][0][2] = '6'
        self.write_fixture()
        with self.assertRaises(sqlite3.IntegrityError):
            load_database(self.raw, self.database)

    def test_header_drift_is_rejected(self):
        path = self.raw / 'olist_customers_dataset.csv'
        path.write_text(path.read_text().replace('customer_id', 'unknown_id', 1))
        with self.assertRaisesRegex(ValueError, 'unexpected CSV header'):
            load_database(self.raw, self.database)

    def test_readonly_connection_supports_select_rejects_write(self):
        load_database(self.raw, self.database)
        db = connect_readonly(self.database)
        self.addCleanup(db.close)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)
        for sql in ['DELETE FROM orders', 'DROP TABLE reviews', 'CREATE TABLE bad(x)', "UPDATE orders SET order_status='canceled'"]:
            with self.subTest(sql=sql), self.assertRaises(sqlite3.OperationalError):
                db.execute(sql)

    def test_conversion_rejects_precision_loss_and_bad_dates(self):
        for column, value in [('price', '1.001'), ('price', 'NaN'), ('review_score', '1.5'),
                              ('geolocation_lat', 'inf'), ('order_approved_at', '2018-02-30 00:00:00')]:
            with self.subTest(column=column, value=value), self.assertRaises(ValueError):
                convert(column, value)

    def test_untranslated_category_is_preserved(self):
        self.fixture['products'][0][1] = 'untranslated'
        self.write_fixture()
        load_database(self.raw, self.database)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT product_category_name FROM products').fetchone()[0], 'untranslated')


if __name__ == '__main__':
    unittest.main()
