"""Hand-calculated edge cases, plus independent CSV/SQL parity for every query."""
from contextlib import closing
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from app.analytics.baseline import QUERIES, run_query
from app.analytics.reference import CsvReference, compare_rows
from app.database.ingest import SOURCES, connect_readonly, load_database


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.raw = self.root / 'raw'
        self.raw.mkdir()
        self.path = self.root / 'test.sqlite'
        jan = '2018-01-01 00:00:00'
        estimate = '2018-01-03 00:00:00'
        self.data = {
            'customers': [['c1', 'person', '00123', 'city', 'SP'], ['c2', 'person', '00124', 'city', 'RJ']],
            'sellers': [['s1', '00123', 'city', 'SP'], ['s2', '00123', 'city', 'SP']],
            'category_translations': [['a', 'Alpha']],
            'products': [[pid, cat, '', '', '', '', '', '', ''] for pid, cat in [('p1', 'a'), ('p2', 'untranslated'), ('p3', '')]],
            'orders': [
                ['o1', 'c1', 'delivered', jan, '', '', '2018-01-03 12:00:00', estimate],
                ['o2', 'c2', 'delivered', jan, '', '', estimate, estimate],
                ['o3', 'c1', 'canceled', jan, '', '', '', estimate],
                ['o4', 'c1', 'delivered', jan, '', '', '', estimate],
                ['o5', 'c1', 'delivered', jan, '', '', '2017-12-31 00:00:00', estimate],
                ['o6', 'c2', 'delivered', '2018-03-01 00:00:00', '', '', '2018-03-04 00:00:00', '2018-03-03 00:00:00'],
            ],
            'payments': [['o1', '1', 'card', '1', '10.00'], ['o1', '2', 'voucher', '1', '20.00'],
                         ['o2', '1', 'card', '1', '70.00'], ['o3', '1', 'card', '1', '90.00'],
                         ['o5', '1', 'voucher', '1', '0.00'], ['o6', '1', 'card', '1', '50.00']],
            'order_items': [
                ['o1', '1', 'p1', 's1', estimate, '1.00', '0.10'],
                ['o1', '2', 'p1', 's1', estimate, '2.00', '0.20'],
                ['o1', '3', 'p2', 's2', estimate, '3.00', '0.30'],
                ['o2', '1', 'p1', 's2', estimate, '40.00', '4.00'],
                ['o3', '1', 'p2', 's1', estimate, '999.00', '0.00'],
                ['o4', '1', 'p2', 's1', estimate, '20.00', '2.00'],
                ['o5', '1', 'p2', 's1', estimate, '30.00', '3.00'],
                ['o6', '1', 'p3', 's1', estimate, '50.00', '5.00'],
            ],
            'reviews': [
                ['a', 'o1', '5', '', '', '2018-01-04 00:00:00', '2018-01-05 00:00:00'],
                ['b', 'o1', '1', '', '', '2018-01-05 00:00:00', '2018-01-06 00:00:00'],
                ['z', 'o1', '2', '', '', '2018-01-05 00:00:00', '2018-01-06 00:00:00'],
                ['bad_creation', 'o1', '1', '', '', '2017-12-31 00:00:00', '2018-01-10 00:00:00'],
                ['bad_answer', 'o1', '1', '', '', '2018-01-20 00:00:00', '2018-01-19 00:00:00'],
                ['good', 'o2', '5', '', '', '2018-01-04 00:00:00', '2018-01-05 00:00:00'],
                ['invalid_delivery_but_valid_review', 'o5', '3', '', '', '2018-01-04 00:00:00', '2018-01-05 00:00:00'],
                ['bad', 'o6', '1', '', '', '2018-02-01 00:00:00', '2018-03-05 00:00:00'],
            ],
            'geolocation': [['00123', '-23.5', '-46.6', 'city', 'SP']],
        }
        self.rebuild()

    def rebuild(self):
        for table, filename, header in SOURCES:
            with (self.raw / filename).open('w', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(header.split())
                writer.writerows(self.data[table])
        load_database(self.raw, self.path)

    def query(self, name, **params):
        with closing(connect_readonly(self.path)) as db:
            return run_query(db, name, params)['rows']

    def test_hand_calculated_revenue_aov_and_cancellations(self):
        self.assertEqual(self.query('overview'), [dict(total_orders=6, unique_buyers=1,
            delivered_orders=5, paid_delivered_orders=4, delivered_missing_payment=1,
            revenue_cents=15000, aov_cents=3750.0, canceled_orders=1, cancellation_pct=16.666667)])

    def test_strict_timestamp_lateness_and_invalid_dates(self):
        self.assertEqual(self.query('late_delivery'), [dict(delivered_orders=5, eligible_orders=3,
            excluded_orders=2, late_orders=2, late_pct=66.666667, mean_delivery_days=2.5, calendar_day_late_orders=1)])

    def test_latest_valid_review_tiebreak_and_missing_coverage(self):
        self.assertEqual(self.query('late_reviews'), [
            dict(delivery_group='late', eligible_orders=2, reviewed_orders=1, missing_eligible_review=1,
                 mean_review_score=2.0, poor_review_orders=1, poor_review_pct=100.0),
            dict(delivery_group='on_time', eligible_orders=1, reviewed_orders=1, missing_eligible_review=0,
                 mean_review_score=5.0, poor_review_orders=0, poor_review_pct=0.0)])

    def test_repeated_category_items_do_not_weight_delivery(self):
        rows = self.query('category_delivery', min_orders=1, top_n=20)
        alpha = next(r for r in rows if r['category_key'] == 'a')
        self.assertEqual(alpha['eligible_orders'], 2)
        self.assertEqual(alpha['mean_delivery_days'], 2.25)
        self.assertEqual(alpha['late_pct'], 50.0)

    def test_category_sales_retains_unknown_and_untranslated(self):
        rows = self.query('category_sales')
        self.assertEqual([r['category_key'] for r in rows], ['untranslated', None, 'a'])
        self.assertEqual([r['item_sales_cents'] for r in rows], [5300, 5000, 4300])
        self.assertEqual(rows[0]['category_label'], 'untranslated')
        self.assertEqual(rows[1]['category_label'], 'Unknown')

    def test_seller_deduplication_and_thresholds(self):
        rows = self.query('seller_performance', min_reviewed_orders=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['seller_id'], 's1')
        self.assertEqual(rows[0]['reviewed_orders'], 2)
        self.assertEqual(rows[0]['mean_review_score'], 2.5)
        self.assertEqual(rows[0]['item_sales_cents'], 10300)
        self.assertEqual(self.query('seller_performance'), [])
        late = self.query('seller_lateness', min_orders=1)
        self.assertEqual([(r['seller_id'], r['eligible_orders'], r['late_pct']) for r in late], [('s1', 2, 100.0)])

    def test_month_spine_keeps_empty_period_and_boundaries(self):
        rows = self.query('monthly_revenue')
        self.assertEqual([r['purchase_month'] for r in rows], ['2018-01', '2018-02', '2018-03'])
        self.assertEqual([r['boundary_month'] for r in rows], [1, 0, 1])
        self.assertEqual(rows[1]['total_orders'], 0)
        self.assertIsNone(rows[1]['revenue_cents'])
        self.assertEqual(rows[0]['revenue_cents'], 10000)

    def test_no_deliveries_produces_undefined_rates_not_zero(self):
        for row in self.data['orders']:
            row[2] = 'canceled'
        self.rebuild()
        result = self.query('late_delivery')[0]
        self.assertEqual(result['eligible_orders'], 0)
        self.assertEqual(result['late_orders'], 0)
        self.assertIsNone(result['late_pct'])
        self.assertIsNone(self.query('overview')[0]['aov_cents'])
        self.assertIsNone(self.query('overview')[0]['revenue_cents'])

    def test_each_sql_query_matches_independent_fixture_reference(self):
        oracle = CsvReference(self.raw)
        for name, spec in QUERIES.items():
            params = {k: 1 if k.startswith('min_') else v for k, v in spec.parameters.items()}
            with self.subTest(name=name):
                self.assertEqual(compare_rows(self.query(name, **params), oracle.result(name, params)), [])

    def test_query_names_and_parameters_are_fixed(self):
        for name, parameters in [('unknown', {}), ('category_sales', {'top_n': -1}),
                                 ('category_sales', {'top_n': True}), ('overview', {'inject': 1})]:
            with self.subTest(name=name, parameters=parameters), self.assertRaises(ValueError):
                self.query(name, **parameters)

    def test_comparator_detects_wrong_values_order_and_nulls(self):
        self.assertTrue(compare_rows([{'cents': 100}], [{'cents': 101}]))
        self.assertTrue(compare_rows([{'mean': 0.0}], [{'mean': None}]))
        self.assertTrue(compare_rows([{'id': 'a'}, {'id': 'b'}], [{'id': 'b'}, {'id': 'a'}]))
        self.assertEqual(compare_rows([{'days': 2.250001}], [{'days': 2.25}]), [])

    def test_cli_frozen_snapshot_detects_regression_without_overwriting(self):
        project = Path(__file__).resolve().parents[1]
        snapshot = self.root / 'expected.json'
        output = self.root / 'reports'
        command = [sys.executable, str(project / 'scripts/run_baseline.py'),
                   '--database', str(self.path), '--raw-dir', str(self.raw),
                   '--snapshot', str(snapshot), '--output-dir', str(output)]
        first = subprocess.run(command + ['--freeze'], capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        frozen_bytes = snapshot.read_bytes()
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(snapshot.read_bytes(), frozen_bytes)
        saved = json.loads(snapshot.read_text(encoding='utf-8'))
        saved['questions']['overview']['rows'][0]['revenue_cents'] += 1
        snapshot.write_text(json.dumps(saved), encoding='utf-8')
        changed_bytes = snapshot.read_bytes()
        failed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertEqual(snapshot.read_bytes(), changed_bytes)
        report = json.loads((output / 'baseline_report.json').read_text(encoding='utf-8'))
        self.assertFalse(report['all_passed'])
        self.assertEqual(report['snapshot_status'], 'mismatch')


if __name__ == '__main__':
    unittest.main()
