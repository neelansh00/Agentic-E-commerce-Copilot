"""Regression cases for each observed live failure, independent of API access."""
from contextlib import closing
import json
from pathlib import Path
import unittest
import test_analytics as fixtures
from app.database.ingest import connect_readonly
from app.text_to_sql.contracts import Explanation, QueryResult
from app.text_to_sql.executor import execute_sql, QueryExecutionError, authorizer
from app.text_to_sql.metric_validation import validate_metric_grain, validate_metric_result, requires_continuous_months
from app.text_to_sql.pipeline import render_explanation, fallback_observations
from app.text_to_sql.prompts import explanation_messages
from app.text_to_sql.safety import validate_sql, SQLSafetyError
from app.rag.retrieval import Retriever
from app.rag.chunks import chunk_documents
from scripts.run_live_evaluation import make_cases

ROOT = Path(__file__).resolve().parents[1]


def result(rows):
    return QueryResult(sql='SELECT test', tables=['orders'], columns=list(rows[0]) if rows else [],
                       rows=rows, truncated=False, execution_ms=0)


class MetricViewsTests(unittest.TestCase):
    setUp = fixtures.AnalyticsTests.setUp
    rebuild = fixtures.AnalyticsTests.rebuild

    def sql(self, sql):
        return execute_sql(self.path, sql).rows

    def test_month_spine_retains_empty_month_with_null_money(self):
        rows = self.sql('''SELECT m.purchase_month, COUNT(o.order_id) total_orders,
            COALESCE(SUM(o.paid_delivered),0) paid_delivered_orders,
            SUM(o.revenue_cents) revenue_cents, AVG(o.revenue_cents) aov_cents
            FROM metric_months m LEFT JOIN metric_orders o USING(purchase_month)
            GROUP BY m.purchase_month ORDER BY m.purchase_month''')
        self.assertEqual(rows[1], dict(purchase_month='2018-02', total_orders=0,
            paid_delivered_orders=0, revenue_cents=None, aov_cents=None))
        self.assertEqual(len(rows), 3)

    def test_zero_payments_are_observations_missing_payments_are_null(self):
        rows = self.sql("SELECT order_id, revenue_cents, paid_delivered FROM metric_orders WHERE order_id IN ('o4','o5') ORDER BY order_id")
        self.assertEqual(rows, [dict(order_id='o4', revenue_cents=None, paid_delivered=0),
                                dict(order_id='o5', revenue_cents=0, paid_delivered=1)])

    def test_payments_and_reviews_do_not_multiply_order_grain(self):
        row = self.sql('SELECT COUNT(*) n, SUM(revenue_cents) cents, AVG(revenue_cents) aov FROM metric_orders')[0]
        self.assertEqual(row, dict(n=6, cents=15000, aov=3750.0))

    def test_delivery_duration_and_lateness_share_eligible_population(self):
        self.assertEqual(self.sql('SELECT SUM(delivery_eligible) eligible, SUM(is_late) late, AVG(delivery_days) days FROM metric_orders'),
                         [dict(eligible=3, late=2, days=2.5)])
        invalid = self.sql("SELECT delivery_days, is_late FROM metric_orders WHERE order_id='o5'")[0]
        self.assertEqual(invalid, dict(delivery_days=None, is_late=None))

    def test_category_repeated_items_do_not_weight_delivery(self):
        row = self.sql("""SELECT COUNT(*) n, AVG(o.delivery_days) days, SUM(o.is_late) late, SUM(c.item_count) items
            FROM metric_order_categories c JOIN metric_orders o USING(order_id)
            WHERE c.category_key='a' AND o.delivery_eligible=1""")[0]
        self.assertEqual(row, dict(n=2, days=2.25, late=1, items=3))

    def test_seller_order_grain_preserves_item_sales_and_single_review(self):
        rows = self.sql("""SELECT s.order_id, s.item_sales_cents, o.delivered_review_score
            FROM metric_order_sellers s JOIN metric_orders o USING(order_id)
            WHERE s.seller_id='s1' AND s.order_id='o1'""")
        self.assertEqual(rows, [dict(order_id='o1', item_sales_cents=300, delivered_review_score=2)])

    def test_delivery_timestamp_is_not_successful_order_status(self):
        self.data['orders'][2][6] = '2018-01-03 00:00:00'  # canceled but has delivery timestamp
        self.rebuild()
        self.assertEqual(self.sql("SELECT delivered, delivery_eligible, revenue_cents FROM metric_orders WHERE order_id='o3'"),
                         [dict(delivered=0, delivery_eligible=0, revenue_cents=None)])

    def test_review_eligibility_precedes_latest_selection(self):
        self.assertEqual(self.sql("SELECT review_score FROM metric_orders WHERE order_id='o1'"), [{'review_score': 2}])
        self.assertEqual(self.sql("SELECT AVG(delivered_review_score) mean FROM metric_orders"), [{'mean': 10/3}])

    def test_exists_is_valid_readonly_sql_and_executes(self):
        rows = self.sql('SELECT COUNT(*) n FROM orders o WHERE EXISTS (SELECT 1 FROM payments p WHERE p.order_id=o.order_id)')
        self.assertEqual(rows, [{'n': 5}])
        with self.assertRaises(SQLSafetyError):
            validate_sql('SELECT order_id FROM orders WHERE EXISTS (SELECT * FROM sqlite_master)')

    def test_views_survive_executor_setup_and_do_not_modify_database(self):
        before = self.path.read_bytes()
        self.assertEqual(self.sql('SELECT COUNT(*) n FROM metric_orders'), [{'n': 6}])
        self.assertEqual(before, self.path.read_bytes())
        with self.assertRaises(SQLSafetyError):
            execute_sql(self.path, 'DROP VIEW metric_orders')


class SemanticBoundaryTests(unittest.TestCase):
    def test_calendar_gap_rejected_only_for_continuous_series(self):
        response = result([{'purchase_month': '2018-01'}, {'purchase_month': '2018-03'}])
        with self.assertRaisesRegex(SQLSafetyError, 'empty calendar'):
            validate_metric_result(response, True)
        validate_metric_result(response, False)
        self.assertTrue(requires_continuous_months('Revenue by month'))
        self.assertFalse(requires_continuous_months('Which months have the highest revenue?'))

    def test_zero_revenue_without_payment_records_rejected(self):
        with self.assertRaisesRegex(SQLSafetyError, 'Revenue must be NULL'):
            validate_metric_result(result([dict(paid_delivered_orders=0, revenue_cents=0)]))
        validate_metric_result(result([dict(paid_delivered_orders=1, revenue_cents=0)]))

    def test_zero_denominator_aov_rejected(self):
        with self.assertRaisesRegex(SQLSafetyError, 'AOV must be NULL'):
            validate_metric_result(result([dict(paid_delivered_orders=0, aov_cents=0)]))

    def test_inflated_late_numerator_rejected(self):
        with self.assertRaisesRegex(SQLSafetyError, 'subset'):
            validate_metric_result(result([dict(eligible_orders=2, late_orders=3)]))

    def test_raw_child_fanout_and_payment_allocation_rejected(self):
        for sql in [
            'SELECT SUM(m.revenue_cents) FROM metric_orders m JOIN payments p USING(order_id)',
            'SELECT SUM(m.revenue_cents) FROM metric_orders m JOIN metric_order_categories c USING(order_id)',
            'SELECT COUNT(*) FROM metric_order_categories c JOIN metric_order_sellers s USING(order_id)',
        ]:
            with self.subTest(sql=sql), self.assertRaises(SQLSafetyError):
                validate_metric_grain(sql)

    def test_wrong_highest_lowest_labels_never_enter_answer(self):
        response = result([dict(customer_state='SE', total_orders=350, mean_delivery_days=21.5),
                           dict(customer_state='SP', total_orders=41746, mean_delivery_days=8.76)])
        for label, column in [('Highest order volume', 'total_orders'), ('Lowest delivery duration', 'mean_delivery_days')]:
            explanation = Explanation(claims=[dict(label=label, row_index=0, column=column)], caveats=[])
            observations, _ = render_explanation(explanation, response)
            self.assertNotIn(label, observations[0])
            self.assertIn('"customer_state": "SE"', observations[0])
            self.assertNotIn('SP', observations[0])

    def test_mixed_seller_rows_receive_their_own_identity(self):
        response = result([dict(seller_id='seller-A', item_sales_cents=100), dict(seller_id='seller-B', item_sales_cents=90)])
        explanation = Explanation(claims=[dict(label='Top seller sales', row_index=i, column='item_sales_cents') for i in [0,1]], caveats=[])
        observations, _ = render_explanation(explanation, response)
        self.assertIn('seller-A', observations[0])
        self.assertIn('seller-B', observations[1])
        self.assertTrue(all('Top seller' not in o for o in observations))

    def test_explanation_rows_have_explicit_indices(self):
        response = result([dict(customer_state='SP', total_orders=10)])
        payload = json.loads(explanation_messages('Orders by state', response)[1]['content'])
        self.assertEqual(payload['rows'], [{'row_index': 0, 'values': response.rows[0]}])

    def test_previous_invalid_explanations_still_fail_closed(self):
        response = result([dict(purchase_month='2018-01', total_orders=10)])
        for label, index in [('Revenue in 2018',0), ('Orders',30)]:
            with self.assertRaises(ValueError):
                render_explanation(Explanation(claims=[dict(label=label,row_index=index,column='total_orders')],caveats=[]),response)

    def test_rag_includes_transitive_metric_dependencies(self):
        chunks = [c.to_dict() for c in chunk_documents(ROOT / 'knowledge_base')]
        retriever = Retriever.__new__(Retriever)
        retriever.metadata = {'chunks': chunks}
        retriever.retrieve = lambda question: [dict(next(c for c in chunks if c['heading']=='Seller and region screening'),score=.8)]
        hits = retriever.retrieve_for_sql('seller screening')
        self.assertTrue({'Successful orders and revenue','Review score and poor reviews','Delivery eligibility, lateness and duration','Category and seller sales; freight'} <= {h['heading'] for h in hits})
        self.assertEqual(len(hits), len({h['id'] for h in hits}))

    def test_benchmark_questions_are_exactly_unchanged(self):
        previous = json.loads((ROOT / 'docs/generated/live_evaluation.json').read_text(encoding='utf-8'))
        cases, _ = make_cases()
        self.assertEqual(cases, previous['cases'])

    def test_recorded_monthly_failures_rejected_without_using_reference_answers(self):
        previous = json.loads((ROOT / 'docs/generated/live_evaluation.json').read_text(encoding='utf-8'))
        for row in previous['results']:
            if row['id'] == 'monthly_revenue':
                with self.subTest(mode=row['mode']), self.assertRaises(SQLSafetyError):
                    validate_metric_result(QueryResult.model_validate(row['response']['result']), True)

    def test_recorded_explanation_failures_are_rejected_or_neutrally_rendered(self):
        previous = json.loads((ROOT / 'docs/generated/live_evaluation.json').read_text(encoding='utf-8'))
        for row in previous['results']:
            outputs = [o['value'] for o in row['model_outputs'] if o['type']=='Explanation']
            if not outputs or row['response']['result'] is None:
                continue
            response = QueryResult.model_validate(row['response']['result'])
            try:
                observations, _ = render_explanation(Explanation.model_validate(outputs[-1]), response)
            except ValueError:
                observations = fallback_observations(response)
            with self.subTest(question=row['id'],mode=row['mode']):
                self.assertTrue(observations)
                for text in observations:
                    caption = text.split(':',1)[0].lower()
                    self.assertFalse(any(word in caption.split() for word in ['highest','lowest','best','worst','top']))


if __name__ == '__main__':
    unittest.main()
