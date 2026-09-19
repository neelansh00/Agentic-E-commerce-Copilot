"""UI execution boundary; models are request-local, never globally cached."""
from pathlib import Path
from app.agent.routing import route_question
from app.agent.runner import AgentResult, run_agent
from app.text_to_sql.config import ModelConfig
from app.text_to_sql.model import OpenAIModel, ScriptedModel

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / 'data/processed/olist.sqlite'
COUNT_QUESTION = 'How many orders are there?'
MODES = ('Local tools', 'Live SQL', 'Scripted demo')


def submit_question(question, mode, retriever_factory, database=DATABASE):
    route = route_question(question)
    def failure(message):
        return AgentResult(status='failed', answer=message, route=route, model='not-invoked',
                           trace=[dict(tool='ui_setup', status='failed')])
    if mode not in MODES:
        return failure('Choose a supported execution mode.')
    try:
        model = None
        if route.operation == 'query':
            if mode == 'Local tools':
                return failure('This question needs SQL generation. Select Live SQL, or try a definition or the delivery/review comparison in Local tools.')
            if mode == 'Scripted demo':
                if question != COUNT_QUESTION:
                    return failure('The scripted demo supports only: How many orders are there? It does not generate SQL.')
                model = ScriptedModel([
                    dict(action='query', sql='SELECT COUNT(*) AS total_orders FROM orders', message='', assumptions=[]),
                    dict(claims=[dict(label='Order count', row_index=0, column='total_orders')], caveats=['descriptive_only'])])
            else:
                model = OpenAIModel(ModelConfig.from_env())
        retriever = retriever_factory() if 'rag' in route.tools else None
        return run_agent(question, database, model=model, retriever=retriever)
    except Exception:
        # Do not expose secrets or arbitrary exception text in the browser.
        return failure('Setup failed. Check the local database, knowledge index and (for Live SQL) OPENAI_API_KEY / OPENAI_MODEL in .env. See the local setup guide.')
