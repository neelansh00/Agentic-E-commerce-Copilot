"""Routing, restricted arithmetic and end-to-end synthetic tool composition."""
from pathlib import Path
import unittest
from unittest.mock import patch
import test_analytics as fixtures
from app.agent.routing import route_question
from app.agent.runner import run_agent
from app.text_to_sql.contracts import QueryResult, ModelError
from app.text_to_sql.model import ScriptedModel
from app.text_to_sql.config import QueryLimits
from app.tools.python_analysis import compare_review_histograms


class Knowledge:
    def retrieve(self, question):
        return [dict(source='metrics.md', start_line=1, end_line=2, heading='Definition', text='Test definition')]
    retrieve_for_sql = retrieve


class RoutingTests(unittest.TestCase):
    def test_all_five_combinations(self):
        for question, expected in [
            ('How many orders are there?', ['sql']),
            ('What does late delivery mean?', ['rag']),
            ('Which state generated the highest revenue?', ['rag', 'sql']),
            ('Are late deliveries associated with lower ratings?', ['sql', 'python']),
            ('Using business definitions, are late deliveries associated with lower ratings?', ['rag', 'sql', 'python']),
            ('Which sellers violate our definition of poor delivery performance?', ['rag', 'sql']),
            ('What is revenue?', ['rag'])]:
            with self.subTest(question=question):
                self.assertEqual(route_question(question).tools, expected)

    def test_filtered_statistical_request_not_silently_global(self):
        for suffix in [' in SP', ' in 2018', ' for seller abc', ' and explain causes']:
            self.assertIn(route_question('Are late deliveries associated with lower ratings' + suffix).operation, ['unsupported', 'clarify'])

    def test_no_python_for_sql_aggregation(self):
        self.assertNotIn('python', route_question('Average order value by state').tools)

    def test_business_drop_and_explain_are_not_commands_or_definitions(self):
        for question in ['Show the revenue drop by month', 'Explain revenue by state']:
            self.assertEqual(route_question(question).operation, 'query')

    def test_causal_writes_followups_and_limits(self):
        for question in ['', 'x'*4001, 'Why did revenue fall?', 'What about those sellers?']:
            self.assertEqual(route_question(question).operation, 'clarify')
        self.assertEqual(route_question('DROP TABLE orders').operation, 'unsupported')
        self.assertEqual(route_question('Test statistical significance of delivery times').operation, 'unsupported')


class PythonTests(unittest.TestCase):
    def result(self, rows, truncated=False):
        return QueryResult(sql='', tables=[], columns=['is_late','review_score','n'], rows=rows, truncated=truncated, execution_ms=0)

    def test_hand_calculated_distribution(self):
        result = self.result([dict(is_late=1,review_score=1,n=2), dict(is_late=1,review_score=3,n=2), dict(is_late=0,review_score=3,n=1), dict(is_late=0,review_score=5,n=3)])
        values = compare_review_histograms(result)
        self.assertEqual(values['late_mean'], 2)
        self.assertEqual(values['on_time_mean'], 4.5)
        self.assertEqual(values['mean_difference_late_minus_on_time'], -2.5)
        self.assertEqual(values['probability_late_score_lower'], .875)
        self.assertEqual(values['probability_equal_score'], .125)

    def test_incomplete_empty_invalid_and_duplicate_inputs(self):
        row = dict(is_late=0,review_score=3,n=1)
        for result in [self.result([], True), self.result([]), self.result([row]), self.result([row,row]), self.result([dict(row,n=-1)]), self.result([dict(row,review_score=None)]), self.result([dict(row,n=1.5)])]:
            with self.subTest(result=result):
                with self.assertRaises(ValueError):
                    compare_review_histograms(result)


class AgentTests(unittest.TestCase):
    setUp = fixtures.AnalyticsTests.setUp
    rebuild = fixtures.AnalyticsTests.rebuild

    def test_statistics_complete_sql_to_python(self):
        result = run_agent('Are late deliveries associated with lower ratings?', self.path)
        self.assertEqual(result.status, 'ok')
        self.assertEqual(result.analysis['late_orders'], 1)
        self.assertEqual(result.analysis['late_mean'], 2)
        self.assertEqual(result.analysis['on_time_mean'], 5)
        self.assertEqual(result.analysis['probability_late_score_lower'], 1)
        self.assertEqual([t['tool'] for t in result.trace], ['router','sql','python'])
        self.assertFalse(result.usage)

    def test_statistics_with_knowledge(self):
        result = run_agent('Using business definitions, are late deliveries associated with lower ratings?', self.path, retriever=Knowledge())
        self.assertEqual(result.status, 'ok')
        self.assertTrue(result.sources)
        self.assertEqual([t['tool'] for t in result.trace], ['router','business_knowledge','sql','python'])

    def test_definition_needs_no_database_or_model(self):
        result = run_agent('What does late delivery mean?', Path('missing.sqlite'), retriever=Knowledge())
        self.assertEqual(result.status, 'ok')
        self.assertIn('metrics.md:1-2', result.answer)
        self.assertIsNone(result.result)

    def test_sql_only_and_sql_rag(self):
        for question, retriever in [('How many orders are there?', None), ('Calculate the cancellation rate', Knowledge())]:
            model = ScriptedModel([dict(action='query', sql='SELECT COUNT(*) AS n FROM orders', message='', assumptions=[]), dict(claims=[dict(label='Count',row_index=0,column='n')], caveats=[])])
            result = run_agent(question, self.path, model, retriever)
            self.assertEqual(result.status, 'ok')
            self.assertEqual(result.result.rows[0]['n'], 6)
            self.assertEqual(len(model.calls), 2)

    def test_missing_tools_and_provider_failure(self):
        self.assertEqual(run_agent('How many orders?', self.path).status, 'failed')
        self.assertEqual(run_agent('What is revenue?', self.path).status, 'failed')
        result = run_agent('How many orders?', self.path, ScriptedModel([ModelError('Unavailable')]))
        self.assertEqual(result.status, 'failed')
        self.assertIsNone(result.result)

    def test_rag_failure_and_empty_hits(self):
        with patch.object(Knowledge, 'retrieve', side_effect=ValueError('Stale index')):
            self.assertEqual(run_agent('What is revenue?', self.path, retriever=Knowledge()).status, 'failed')
        with patch.object(Knowledge, 'retrieve', return_value=[]):
            self.assertEqual(run_agent('What is revenue?', self.path, retriever=Knowledge()).status, 'clarification')

    def test_truncated_statistics_and_database_failure(self):
        q = 'Are late deliveries associated with lower ratings?'
        self.assertEqual(run_agent(q, self.path, limits=QueryLimits(max_rows=1)).status, 'failed')
        self.assertEqual(run_agent(q, self.root/'missing.sqlite').status, 'failed')

    def test_rejected_query_retry_limit_propagates(self):
        bad = dict(action='query', sql='DELETE FROM orders', message='', assumptions=[])
        model = ScriptedModel([bad]*3)
        result = run_agent('How many orders?', self.path, model)
        self.assertEqual(result.status, 'failed')
        self.assertEqual(len(model.calls), 3)
        self.assertIsNone(result.result)
