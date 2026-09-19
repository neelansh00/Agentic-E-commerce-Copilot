"""UI contract checks use Streamlit AppTest, synthetic responses and no API calls."""
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from streamlit.testing.v1 import AppTest
from app.agent.runner import AgentResult
from app.agent.routing import route_question
from app.text_to_sql.contracts import QueryResult
from app.ui.presentation import chart_options, chart_spec, summary_metrics
from app.ui.service import submit_question, COUNT_QUESTION

ROOT = Path(__file__).resolve().parents[1]


def response(rows=None, truncated=False, status='ok'):
    rows = rows if rows is not None else [dict(customer_state='SP',revenue_cents=100),dict(customer_state='RJ',revenue_cents=None)]
    result = QueryResult(sql='SELECT example',columns=list(rows[0]) if rows else [],rows=rows,
                         tables=['orders'],truncated=truncated,execution_ms=1)
    return AgentResult(status=status,answer='Evidence answer',model='test',route=route_question('Revenue by state'),
                       result=result,trace=[dict(tool='sql',sql=result.sql,status='executed')],
                       sources=[dict(source='metrics.md',start_line=1,end_line=2,heading='Revenue',text='Verified definition')])


class PresentationTests(unittest.TestCase):
    def test_cents_converted_once_and_null_not_zero(self):
        result = response().result
        spec = chart_spec(result,'revenue_cents')
        self.assertEqual([p['value'] for p in spec['data']['values']], [1.0,None])
        self.assertEqual(result.rows[0]['revenue_cents'],100)
        self.assertIn('(BRL)',spec['encoding']['y']['title'])

    def test_monthly_gaps_break_line_and_sort(self):
        r=response([dict(purchase_month='2018-05',revenue_cents=500),dict(purchase_month='2018-01',revenue_cents=100),dict(purchase_month='2018-02',revenue_cents=None),dict(purchase_month='2018-03',revenue_cents=300)]).result
        points=chart_spec(r,'revenue_cents')['data']['values']
        self.assertEqual([p['group'] for p in points],['2018-01','2018-02','2018-03','2018-05'])
        self.assertEqual(len({p['segment'] for p in points}),4)

    def test_no_chart_for_truncation_duplicate_groups_or_unknown_metrics(self):
        for r in [response(truncated=True).result,response([dict(customer_state='SP',revenue_cents=2)]*2).result,response([dict(customer_state='SP',mystery=2),dict(customer_state='RJ',mystery=3)]).result]:
            self.assertFalse(chart_options(r)[1])
            with self.assertRaises(ValueError):
                chart_spec(r,'revenue_cents')

    def test_summary_preserves_unknown_and_omits_truncated(self):
        self.assertEqual(summary_metrics(response([dict(revenue_cents=None)]))[0][1],'Unknown')
        self.assertEqual(summary_metrics(response([dict(revenue_cents=1)],truncated=True)),[])


class ServiceTests(unittest.TestCase):
    def test_local_mode_never_creates_model_for_query(self):
        with patch('app.ui.service.OpenAIModel') as model:
            result=submit_question('Revenue by state','Local tools',Mock())
            self.assertEqual(result.status,'failed')
            model.assert_not_called()

    def test_local_definitions_need_no_model(self):
        retriever=Mock()
        retriever.retrieve.return_value=response().sources
        with patch('app.ui.service.OpenAIModel') as model:
            result=submit_question('What is revenue?','Live SQL',lambda:retriever)
            self.assertEqual(result.status,'ok')
            model.assert_not_called()

    def test_demo_does_not_accept_arbitrary_queries(self):
        result=submit_question('Revenue by state','Scripted demo',Mock())
        self.assertEqual(result.status,'failed')
        self.assertIn('does not generate SQL',result.answer)

    def test_live_boundary_uses_new_provider_and_sanitizes_setup_error(self):
        with patch('app.ui.service.ModelConfig.from_env',side_effect=ValueError('SECRET_VALUE')):
            result=submit_question(COUNT_QUESTION,'Live SQL',Mock())
            self.assertEqual(result.status,'failed')
            self.assertNotIn('SECRET_VALUE',result.model_dump_json())
        with patch('app.ui.service.ModelConfig.from_env'),patch('app.ui.service.OpenAIModel') as factory,patch('app.ui.service.run_agent',return_value=response()):
            submit_question(COUNT_QUESTION,'Live SQL',Mock())
            submit_question(COUNT_QUESTION,'Live SQL',Mock())
            self.assertEqual(factory.call_count,2)


class StreamlitTests(unittest.TestCase):
    def app(self):
        return AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=30).run()

    def test_startup_local_default_no_execution(self):
        with patch('app.ui.service.submit_question') as submit:
            at=self.app()
            self.assertFalse(at.exception)
            self.assertEqual(at.radio[0].value,'Local tools')
            submit.assert_not_called()

    def test_all_evidence_panels_and_reruns_do_not_repeat_execution(self):
        with patch('app.ui.service.submit_question',return_value=response()) as submit:
            at=self.app()
            at.chat_input[0].set_value('Revenue by state').run()
            self.assertFalse(at.exception)
            self.assertEqual({e.label for e in at.expander},{'SQL Used','Data Preview','Sources / Business Definitions','Tool Trace','Execution Information'})
            self.assertEqual(len(at.dataframe),1)
            at.run()
            self.assertEqual(submit.call_count,1)
            self.assertEqual(len(at.session_state['conversation']),1)

    def test_clear_and_independent_sessions(self):
        with patch('app.ui.service.submit_question',return_value=response()):
            at=self.app()
            at.chat_input[0].set_value('Revenue by state').run()
            other=self.app()
            self.assertEqual(len(other.session_state['conversation']),0)
            next(b for b in at.button if b.label=='Clear conversation').click().run()
            self.assertEqual(len(at.session_state['conversation']),0)
            self.assertFalse(at.exception)

    def test_failed_and_truncated_results_visible(self):
        for result in [response(status='failed'),response(truncated=True)]:
            with patch('app.ui.service.submit_question',return_value=result):
                at=self.app()
                at.chat_input[0].set_value('Revenue by state').run()
                self.assertFalse(at.exception)
                self.assertTrue(at.error if result.status=='failed' else at.warning)
                self.assertFalse(at.selectbox)

    def test_example_click_runs_once(self):
        with patch('app.ui.service.submit_question',return_value=response()) as submit:
            at=self.app()
            next(b for b in at.button if b.label=='Delivery & reviews').click().run()
            at.run()
            self.assertEqual(submit.call_count,1)

    def test_history_is_bounded(self):
        at=self.app()
        with patch('app.ui.service.submit_question',return_value=response()):
            for i in range(11):
                at.chat_input[0].set_value(f'Question {i}').run()
            self.assertFalse(at.exception)
            self.assertEqual(len(at.session_state['conversation']),10)
            self.assertEqual(at.session_state['conversation'][0]['question'],'Question 1')
