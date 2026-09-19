from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.database.ingest import SCHEMA
from app.text_to_sql.config import ModelConfig, QueryLimits
from app.text_to_sql.contracts import ModelError, SQLPlan
from app.text_to_sql.executor import execute_sql, authorizer, QueryExecutionError
from app.text_to_sql.model import OpenAIModel, ScriptedModel
from app.text_to_sql.pipeline import answer_question
from app.text_to_sql.safety import SQLSafetyError, SchemaMismatch, validate_sql
from app.text_to_sql.schema import retrieve_schema, schema_context


def plan(sql):
    return dict(action='query', sql=sql, message='', assumptions=[])


def explanation(column='total_orders', row=0, label='Total orders'):
    return dict(claims=[dict(label=label, row_index=row, column=column)], caveats=['descriptive_only'])


class SQLSafetyTests(unittest.TestCase):
    def test_forbidden_sql_corpus(self):
        attacks = ['INSERT INTO orders(order_id) VALUES (\'x\')', 'UPDATE orders SET order_status=\'x\'',
            'DELETE FROM orders', 'DROP TABLE orders', 'ALTER TABLE orders ADD x TEXT',
            'CREATE TABLE x(a)', 'TRUNCATE TABLE orders', 'VACUUM', 'PRAGMA query_only=OFF',
            "ATTACH DATABASE 'other.sqlite' AS extra", 'DETACH DATABASE extra',
            "SELECT load_extension('evil') FROM orders", "SELECT readfile('/etc/passwd') FROM orders",
            'SELECT randomblob(100000000) FROM orders', 'SELECT * FROM sqlite_master',
            "SELECT * FROM pragma_table_info('orders')", 'SELECT * FROM main.orders',
            'SELECT * FROM orders; DELETE FROM orders', 'SELECT * INTO stolen FROM orders',
            'WITH stolen AS (DELETE FROM orders RETURNING *) SELECT * FROM stolen',
            'SELECT 999 AS invented_revenue', "SELECT * FROM orders UNION SELECT * FROM sqlite_schema"]
        for sql in attacks:
            with self.subTest(sql=sql), self.assertRaises(SQLSafetyError):
                validate_sql(sql)

    def test_comments_strings_ctes_unions_and_alias_shadowing(self):
        for sql in ["-- DROP is a comment\nSELECT COUNT(*) n FROM orders WHERE order_status <> 'DELETE'",
                    'WITH o AS (SELECT order_id FROM orders) SELECT COUNT(*) FROM o',
                    'SELECT order_id FROM orders UNION SELECT order_id FROM reviews',
                    'WITH orders AS (SELECT order_id FROM payments) SELECT * FROM orders']:
            self.assertTrue(validate_sql(sql).tables)
        self.assertEqual(validate_sql('WITH orders AS (SELECT order_id FROM payments) SELECT * FROM orders').tables, ('payments',))

    def test_unknown_table_and_schema_scope(self):
        with self.assertRaises(SQLSafetyError):
            validate_sql('SELECT * FROM secret_users')
        with self.assertRaises(SchemaMismatch) as error:
            validate_sql('SELECT * FROM payments', ['orders'])
        self.assertEqual(error.exception.missing, ['payments'])

    def test_empty_oversized_malformed_sql(self):
        for sql in ['', 'SELECT\x00 * FROM orders', 'SELECT ((( FROM orders']:
            with self.assertRaises(SQLSafetyError):
                validate_sql(sql)
        with self.assertRaises(SQLSafetyError):
            validate_sql('SELECT * FROM orders', max_chars=5)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'test.sqlite'
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript(SCHEMA.read_text(encoding='utf-8'))
            db.execute("INSERT INTO customers VALUES ('c','person','123','city','SP')")
            db.executemany('INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)', [
                (f'o{i}', 'c', 'delivered', '2018-01-01 00:00:00', None, None,
                 '2018-01-03 00:00:00', '2018-01-02 00:00:00') for i in range(4)])
            db.execute("INSERT INTO payments VALUES ('o0',1,'card',1,100)")
            db.commit()

    def test_valid_select_and_result_transparency(self):
        model = ScriptedModel([plan('SELECT COUNT(*) total_orders FROM orders'), explanation()])
        response = answer_question('How many orders?', self.path, model)
        self.assertEqual(response.status, 'ok')
        self.assertEqual(response.result.rows, [{'total_orders': 4}])
        self.assertIn('Total orders: 4', response.answer)
        self.assertEqual(response.result.tables, ['orders'])
        self.assertEqual(response.schema_tables, ['orders'])

    def test_invalid_column_then_bounded_correction(self):
        model = ScriptedModel([plan('SELECT SUM(nonexistent) total_orders FROM orders'),
                               plan('SELECT COUNT(*) total_orders FROM orders'), explanation()])
        response = answer_question('Total orders?', self.path, model)
        self.assertEqual(response.status, 'ok')
        self.assertIn('no such column', model.calls[1][-1]['content'])
        self.assertEqual(len([x for x in response.trace if x.get('tool') == 'sql']), 2)

    def test_invalid_aggregation_then_repair(self):
        model = ScriptedModel([plan('SELECT SUM(COUNT(*)) total_orders FROM orders'),
                               plan('SELECT COUNT(*) total_orders FROM orders'), explanation()])
        self.assertEqual(answer_question('Total orders?', self.path, model).status, 'ok')
        self.assertIn('misuse', model.calls[1][-1]['content'])

    def test_syntax_and_wrong_table_repaired_within_three_attempts(self):
        model = ScriptedModel([plan('SELECT ((( FROM orders'),
                               plan('SELECT COUNT(*) total_orders FROM ordres'),
                               plan('SELECT COUNT(*) total_orders FROM orders'), explanation()])
        response = answer_question('Total orders?', self.path, model)
        self.assertEqual(response.status, 'ok')
        self.assertEqual(len([t for t in response.trace if t.get('tool') == 'sql']), 3)

    def test_retry_exhaustion_has_no_fabricated_result(self):
        model = ScriptedModel([plan('SELECT missing FROM orders')] * 3)
        response = answer_question('Total orders?', self.path, model)
        self.assertEqual(response.status, 'failed')
        self.assertIsNone(response.result)
        self.assertEqual(len(model.calls), 3)
        self.assertIn('No numerical answer', response.answer)

    def test_write_attempt_never_changes_database(self):
        before = self.path.read_bytes()
        response = answer_question('Delete all orders', self.path, ScriptedModel([plan('DELETE FROM orders')] * 3))
        self.assertEqual(response.status, 'failed')
        self.assertEqual(before, self.path.read_bytes())

    def test_schema_expansion_is_traceable_and_bounded(self):
        sql = 'SELECT COUNT(*) payment_rows FROM payments'
        response = answer_question('Total orders?', self.path,
            ScriptedModel([plan(sql), plan(sql), explanation('payment_rows', label='Payment rows')]))
        self.assertEqual(response.status, 'ok')
        self.assertIn('payments', response.schema_tables)
        self.assertEqual(len([t for t in response.trace if t.get('tool') == 'schema_expansion']), 1)

    def test_model_failure_is_explicit(self):
        response = answer_question('Total orders?', self.path, ScriptedModel([ModelError('offline provider unavailable')]))
        self.assertEqual(response.status, 'failed')
        self.assertIsNone(response.result)

    def test_malformed_model_output_fails_closed(self):
        response = answer_question('Total orders?', self.path, ScriptedModel([{'sql': 'SELECT * FROM orders'}]))
        self.assertEqual(response.status, 'failed')

    def test_missing_database_is_handled(self):
        response = answer_question('Total orders?', self.path.with_name('absent.sqlite'), ScriptedModel([]))
        self.assertEqual(response.status, 'failed')

    def test_executor_connection_failure_uses_standard_error_boundary(self):
        with self.assertRaises(QueryExecutionError):
            execute_sql(self.path.with_name('missing.sqlite'), 'SELECT COUNT(*) FROM orders')

    def test_clarification_and_unsupported_skip_sql(self):
        for action in ('clarify', 'unsupported'):
            response = answer_question('Why did profit fall?', self.path, ScriptedModel([
                dict(action=action, sql=None, message='Costs are unavailable; specify a measurable sales question.', assumptions=[])]))
            self.assertIsNone(response.result)
            self.assertFalse(any(t.get('tool') == 'sql' for t in response.trace))

    def test_invalid_evidence_uses_literal_fallback(self):
        for output in [explanation(row=99), explanation(column='fake'), explanation(label='Revenue 999'),
                       explanation(label='Proven cause'), dict(claims=[], caveats=[])]:
            with self.subTest(output=output):
                result = answer_question('Total orders?', self.path, ScriptedModel([
                    plan('SELECT COUNT(*) total_orders FROM orders'), output]))
                self.assertEqual(result.status, 'ok')
                self.assertEqual(result.trace[-1]['status'], 'deterministic_fallback')
                self.assertIn('total_orders: 4', result.answer)

    def test_no_rows_not_a_zero_business_answer(self):
        model = ScriptedModel([plan("SELECT order_id FROM orders WHERE order_status='never'")])
        response = answer_question('Find orders?', self.path, model)
        self.assertEqual(response.result.rows, [])
        self.assertIn('no rows', response.answer)
        self.assertEqual(len(model.calls), 1)

    def test_row_limit_marks_truncation(self):
        result = execute_sql(self.path, 'SELECT order_id FROM orders ORDER BY order_id', limits=QueryLimits(max_rows=2))
        self.assertEqual(len(result.rows), 2)
        self.assertTrue(result.truncated)

    def test_byte_limit_does_not_claim_zero_rows(self):
        response = answer_question('Total orders?', self.path,
            ScriptedModel([plan('SELECT order_id FROM orders')]), limits=QueryLimits(max_result_bytes=10))
        # The SQLite cell fits, but its encoded row exceeds the preview byte budget.
        self.assertEqual(response.status, 'ok')
        self.assertTrue(response.result.truncated)
        self.assertEqual(response.result.rows, [])
        self.assertIn('Rows exist', response.answer)

    def test_nonfinite_output_rejected(self):
        with self.assertRaisesRegex(QueryExecutionError, 'nonfinite'):
            execute_sql(self.path, 'SELECT 1e999 AS value FROM orders')

    def test_duplicate_column_alias_rejected(self):
        with self.assertRaises(QueryExecutionError):
            execute_sql(self.path, 'SELECT order_id, order_id FROM orders')

    def test_expensive_query_times_out(self):
        sql = 'WITH RECURSIVE n(x) AS (SELECT 1 FROM orders UNION ALL SELECT x+1 FROM n WHERE x<100000000) SELECT SUM(x) FROM n'
        with self.assertRaisesRegex(QueryExecutionError, 'time budget'):
            execute_sql(self.path, sql, limits=QueryLimits(timeout_seconds=0.001))

    def test_sqlite_authorizer_blocks_mutations_even_without_parser(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.set_authorizer(authorizer({'orders'}))
            for sql in ["DELETE FROM orders", "PRAGMA user_version=3", 'SELECT * FROM sqlite_master',
                        'SELECT randomblob(10) FROM orders']:
                with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                    db.execute(sql)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 4)

    def test_schema_retrieval_avoids_unrelated_tables(self):
        tables, reasons = retrieve_schema('Which sellers have the worst ratings?')
        self.assertEqual(set(tables), {'sellers', 'order_items', 'orders', 'reviews'})
        context = schema_context(self.path, tables)
        self.assertIn('review_score', context)
        self.assertNotIn('payment_value_cents', context)
        self.assertNotIn('geolocation_lat', context)


class ProviderTests(unittest.TestCase):
    def test_adapter_uses_structured_output_and_no_storage(self):
        captured = {}
        def parse(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(status='completed', output_parsed=SQLPlan(**plan('SELECT COUNT(*) FROM orders')), usage=None)
        model = OpenAIModel(ModelConfig('secret', 'configured-model'), client=SimpleNamespace(responses=SimpleNamespace(parse=parse)))
        model.generate([{'role': 'user', 'content': 'question'}], SQLPlan)
        self.assertFalse(captured['store'])
        self.assertIs(captured['text_format'], SQLPlan)
        self.assertNotIn('secret', repr(model.config))

    def test_adapter_does_not_expose_provider_secrets(self):
        def parse(**kwargs):
            raise RuntimeError('api key secret leaked in provider text')
        model = OpenAIModel(ModelConfig('secret', 'model'), client=SimpleNamespace(responses=SimpleNamespace(parse=parse)))
        with self.assertRaises(ModelError) as error:
            model.generate([], SQLPlan)
        self.assertNotIn('secret', str(error.exception))

    def test_refusal_or_incomplete_response_is_explicit(self):
        for status in ('completed', 'incomplete'):
            client = SimpleNamespace(responses=SimpleNamespace(parse=lambda **kwargs:
                SimpleNamespace(status=status, output_parsed=None, usage=None)))
            with self.subTest(status=status), self.assertRaisesRegex(ModelError, 'refused'):
                OpenAIModel(ModelConfig('secret', 'model'), client).generate([], SQLPlan)

    def test_missing_credentials_no_network_fallback(self):
        with patch.dict('os.environ', {}, clear=True), tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'No live model'):
                ModelConfig.from_env(Path(temp) / '.env')


if __name__ == '__main__':
    unittest.main()
