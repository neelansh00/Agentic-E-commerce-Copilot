"""Evaluation failures must not turn into inflated success metrics."""
import json
from pathlib import Path
import unittest
import test_analytics as fixtures
from app.agent.runner import AgentResult
from app.agent.routing import route_question
from app.evaluation.scoring import score_case,summarize_benchmark,ratio,rubric_score
from app.evaluation.sandbox import engine_only
from app.text_to_sql.executor import QueryExecutionError
from app.text_to_sql.contracts import QueryResult


class ScoringTests(unittest.TestCase):
    def case_response(self,rows,truncated=False,status='ok'):
        case=dict(kind='sql',expected_rows=[dict(total_orders=6)],group_keys=[],expected_tools=['sql'],expected_status='ok')
        result=QueryResult(sql='SELECT COUNT(*) total_orders FROM orders',tables=['orders'],columns=['total_orders'],rows=rows,truncated=truncated,execution_ms=0)
        response=AgentResult(status=status,answer='Count',route=route_question('How many orders?'),model='test',result=result)
        return case,response

    def test_execution_is_not_accuracy(self):
        case,response=self.case_response([dict(total_orders=7)])
        score=score_case(case,response)
        self.assertTrue(score['executed']); self.assertFalse(score['result_correct'])

    def test_empty_truncated_wrong_alias_and_duplicate_rows_fail(self):
        for rows,truncated in [([],False),([dict(total_orders=6)],True),([dict(count=6)],False),([dict(total_orders=6)]*2,False)]:
            case,response=self.case_response(rows,truncated)
            self.assertFalse(score_case(case,response)['result_correct'])

    def test_missing_results_count_in_denominator(self):
        case,response=self.case_response([dict(total_orders=6)])
        rows=[dict(category='simple_sql',score=score_case(case,response),response=response.model_dump())]
        response.result=None; response.status='failed'
        rows.append(dict(category='simple_sql',score=score_case(case,response),response=response.model_dump()))
        summary=summarize_benchmark(rows)
        self.assertEqual(summary['sql_execution'],dict(numerator=1,denominator=2,rate=.5))
        self.assertEqual(summary['sql_result_accuracy']['rate'],.5)

    def test_wrong_tool_not_hidden_by_correct_result(self):
        case,response=self.case_response([dict(total_orders=6)])
        case['expected_tools']=['rag','sql']
        score=score_case(case,response)
        self.assertTrue(score['result_correct']); self.assertFalse(score['tools_correct'])

    def test_zero_denominator_and_rubric_label(self):
        self.assertIsNone(ratio(0,0)['rate'])
        self.assertFalse(rubric_score('delivered payment', ['delivered','missing'])['all_patterns_present'])
        self.assertIn('proxy',rubric_score('yes',['yes'])['note'])

    def test_frozen_benchmark_shape_and_categories(self):
        path=Path(__file__).resolve().parents[1]/'evaluation/questions.json'
        cases=json.loads(path.read_text(encoding='utf-8'))['questions']
        self.assertEqual(len(cases),50)
        self.assertEqual(len({c['id'] for c in cases}),50)
        self.assertEqual(sum(c['kind']=='sql' for c in cases),30)
        self.assertEqual({c['category'] for c in cases},{'simple_sql','multi_table_sql','time_based','business_definition','statistical','ambiguous_adversarial'})
        for c in cases:
            self.assertTrue(c['interpretation'])
            if c['kind']=='sql': self.assertTrue(c['reference_sql']); self.assertTrue(c['expected_rows'])


class EngineBaselineTests(unittest.TestCase):
    setUp=fixtures.AnalyticsTests.setUp
    rebuild=fixtures.AnalyticsTests.rebuild

    def test_select_and_metric_views_work(self):
        self.assertEqual(engine_only(self.path,'SELECT COUNT(*) AS n FROM metric_orders').rows,[dict(n=6)])

    def test_engine_still_denies_mutations_and_external_reads(self):
        before=self.path.read_bytes()
        for sql in ['DELETE FROM orders','DROP TABLE orders','PRAGMA table_info(orders)',"ATTACH DATABASE ':memory:' AS evil",'SELECT * FROM sqlite_master',"SELECT load_extension('evil')"]:
            with self.subTest(sql=sql):
                with self.assertRaises(QueryExecutionError): engine_only(self.path,sql)
        self.assertEqual(self.path.read_bytes(),before)

    def test_expensive_query_bounded(self):
        with self.assertRaises(QueryExecutionError):
            engine_only(self.path,'WITH RECURSIVE numbers(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM numbers) SELECT SUM(n) FROM numbers',timeout=.01)
