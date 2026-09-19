"""Run with: python -m streamlit run app/main.py"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import streamlit as st
from app.agent.runner import AgentResult
from app.ui.service import submit_question, MODES, COUNT_QUESTION, DATABASE
from app.ui.presentation import chart_options, chart_spec, summary_metrics
from app.text_to_sql.evidence import CAPTIONS

st.set_page_config(page_title='E-Commerce Analytics Copilot', page_icon='◈', layout='centered')


@st.cache_resource(scope='session')
def get_retriever():
    from app.rag.embeddings import LocalEmbedder
    from app.rag.retrieval import Retriever
    return Retriever(LocalEmbedder())


def render_response(response, key):
    st.caption(' · '.join(response.route.tools).upper() or 'REQUEST CHECK')
    if response.status != 'ok':
        (st.error if response.status == 'failed' else st.info)(response.answer)
    else:
        st.markdown('**Observations**' if response.result else '**Business definition**')
        # Treat generated text as plain text, never HTML or executable markup.
        st.text(response.answer)
        metrics = summary_metrics(response)
        if metrics:
            for column, (label, value) in zip(st.columns(len(metrics)), metrics):
                column.metric(label, value)
        if response.analysis:
            st.bar_chart({'Delivery group': ['Late', 'On time'],
                          'Mean review score': [response.analysis['late_mean'], response.analysis['on_time_mean']]},
                         x='Delivery group', y='Mean review score', color='#146B59')
            st.caption('Mean scores describe reviewed eligible orders. The complete input histogram is in Data Preview.')
        else:
            dimension, measures = chart_options(response.result)
            if measures:
                measure = st.selectbox('Chart measure', measures, format_func=lambda c: CAPTIONS[c], key=f'measure_{key}')
                st.vega_lite_chart(chart_spec(response.result, measure), width='stretch')
                st.caption('Chart uses returned groups only. Currency is displayed in BRL; missing values are not zero. Gaps break the monthly line.')
    if response.caveats:
        with st.expander('Interpretation / limitations'):
            for caveat in response.caveats:
                st.text(caveat)
    with st.expander('SQL Used'):
        attempts = [t for t in response.trace if t.get('sql')]
        if not attempts:
            st.caption('No SQL was executed for this request.')
        for i, attempt in enumerate(attempts, 1):
            st.caption(f"Attempt {i} · {attempt.get('status', 'recorded')}")
            st.code(attempt['sql'], language='sql')
        if response.result:
            st.caption('Tables / views: ' + ', '.join(response.result.tables))
    with st.expander('Data Preview'):
        if response.result:
            if response.result.truncated:
                st.warning('This result is truncated. It is a preview, not the complete population. Charts and summary cards are disabled.')
            st.caption(f'{len(response.result.rows)} returned rows. Raw monetary columns ending in _cents are BRL cents. Blank cells are NULL.')
            if response.result.rows:
                st.dataframe(response.result.rows, width='stretch', hide_index=True)
            else:
                st.info('The query returned no rows.')
        else:
            st.caption('No query result for this request.')
        if response.analysis:
            st.json(response.analysis)
    with st.expander('Sources / Business Definitions'):
        if not response.sources:
            st.caption('No vector retrieval was used. Query conventions are documented in knowledge_base/metrics.md.')
        for source in response.sources:
            st.text(f"{source['source']}:{source['start_line']}-{source['end_line']} | {source['heading']}")
            st.text(source['text'])
    with st.expander('Tool Trace'):
        st.json(response.trace)
    with st.expander('Execution Information'):
        st.json(dict(status=response.status, model=response.model, elapsed_ms=response.elapsed_ms,
                     sql_execution_ms=response.result.execution_ms if response.result else None,
                     selected_schema=response.schema_tables, model_usage=response.usage,
                     explanation_fallback=any(t.get('status')=='deterministic_fallback' for t in response.trace)))


def main():
    st.session_state.setdefault('conversation', [])
    st.session_state.setdefault('next_turn', 0)
    example = None
    with st.sidebar:
        st.markdown('### ◈ ANALYTICS COPILOT')
        st.caption('Olist · Brazilian e-commerce')
        mode = st.radio('Execution mode', MODES, key='execution_mode')
        st.caption({'Local tools': 'Definitions and delivery/review comparisons. No model API calls.',
                    'Live SQL': 'Generate SQL with your configured model. API usage may incur charges.',
                    'Scripted demo': 'Fixed order-count SQL; clearly labeled, not model-generated.'}[mode])
        st.divider()
        st.markdown('**Try a question**')
        examples = [('Define late delivery', 'What does late delivery mean?'),
                    ('Delivery & reviews', 'Are late deliveries associated with lower ratings?')]
        if mode == 'Scripted demo':
            examples = [('Count orders', COUNT_QUESTION)]
        elif mode == 'Live SQL':
            examples += [('Revenue by state', 'Which states generated the most revenue? Return customer_state and revenue_cents.'),
                         ('Monthly revenue', 'How does revenue vary by purchase month? Return a continuous monthly series with purchase_month and revenue_cents.')]
        for label, question in examples:
            if st.button(label, width='stretch'):
                example = question
        st.divider()
        if st.button('Clear conversation', width='stretch'):
            st.session_state.conversation = []
        st.caption('Session-only history · latest 10 answers')
        st.caption('Each question is independent. Include the metric, population and period.')
    st.caption('AGENTIC E-COMMERCE ANALYTICS COPILOT')
    st.title('Ask your commerce data.')
    st.write('Explore sales, delivery and customer experience—with the evidence behind every answer.')
    if not DATABASE.exists():
        st.warning('Database not found. Run scripts/load_database.py before asking transactional questions.')
    if not st.session_state.conversation:
        st.info('Start with a suggested question or write your own below. Expand any answer to inspect its SQL, data and sources.')
    for turn in st.session_state.conversation:
        with st.chat_message('user'):
            st.text(turn['question'])
        with st.chat_message('assistant'):
            render_response(AgentResult.model_validate(turn['response']), turn['id'])
    question = st.chat_input('Ask a complete business question', max_chars=4000) or example
    if question:
        with st.chat_message('user'):
            st.text(question)
        with st.chat_message('assistant'):
            with st.spinner('Checking the question and gathering evidence…'):
                response = submit_question(question, mode, get_retriever)
            turn_id = st.session_state.next_turn
            st.session_state.next_turn += 1
            st.session_state.conversation.append(dict(id=turn_id, question=question, response=response.model_dump()))
            st.session_state.conversation = st.session_state.conversation[-10:]
            render_response(response, turn_id)


main()
