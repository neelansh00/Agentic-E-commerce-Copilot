"""Single request orchestrator composing existing guarded tools."""
import time
from pydantic import Field
from app.agent.routing import Route, route_question
from app.text_to_sql.contracts import PipelineResult
from app.text_to_sql.pipeline import answer_question
from app.text_to_sql.executor import execute_sql, QueryExecutionError
from app.text_to_sql.safety import SQLSafetyError
from app.tools.python_analysis import compare_review_histograms, describe_comparison

# Generic input contract for the only current Python operation. No result constants.
REVIEW_HISTOGRAM_SQL = '''SELECT is_late, delivered_review_score AS review_score, COUNT(*) AS n
FROM metric_orders WHERE delivery_eligible = 1 AND delivered_review_score IS NOT NULL
GROUP BY is_late, delivered_review_score ORDER BY is_late, review_score'''


class AgentResult(PipelineResult):
    route: Route
    analysis: dict = Field(default_factory=dict)


def run_agent(question, database, model=None, retriever=None, limits=None):
    start = time.perf_counter()
    route = route_question(question)
    trace = [dict(tool='router', selected_tools=route.tools, operation=route.operation, reason=route.reason)]
    sources = []
    def finish(status, answer, **kwargs):
        return AgentResult(status=status, answer=answer, route=route, trace=trace, sources=sources,
                           model=getattr(model, 'name', 'deterministic-tools'),
                           elapsed_ms=round(1000*(time.perf_counter()-start), 3), **kwargs)
    if route.operation in ('clarify', 'unsupported'):
        return finish('clarification' if route.operation == 'clarify' else 'unsupported', route.reason)
    if 'rag' in route.tools and retriever is None:
        return finish('failed', 'This request requires the business knowledge index. Configure a retriever.')
    if route.operation == 'query':
        if model is None:
            return finish('failed', 'SQL generation requires a configured model; offline demos only replay explicit responses.')
        response = answer_question(question, database, model, limits, retriever if 'rag' in route.tools else None)
        payload = response.model_dump()
        payload['trace'] = trace + payload['trace']
        payload['elapsed_ms'] = round(1000*(time.perf_counter()-start), 3)
        return AgentResult(**payload, route=route)
    try:
        if 'rag' in route.tools:
            sources = (retriever.retrieve_for_sql(question) if route.operation == 'late_reviews' else retriever.retrieve(question))
            trace.append(dict(tool='business_knowledge', returned_chunks=len(sources)))
            if not sources:
                return finish('clarification', 'No relevant business definition was retrieved. Clarify the metric.')
        if route.operation == 'definition':
            from app.rag.retrieval import context_for
            return finish('ok', context_for(sources))
        trace.append(dict(tool='sql', sql=REVIEW_HISTOGRAM_SQL))
        result = execute_sql(database, REVIEW_HISTOGRAM_SQL, ['metric_orders'], limits)
        trace[-1].update(status='executed', returned_rows=len(result.rows), execution_ms=result.execution_ms)
        trace.append(dict(tool='python', operation='compare_review_histograms', status='started'))
        analysis = compare_review_histograms(result)
        trace[-1]['status'] = 'completed'
        observations = describe_comparison(analysis)
        caveats = ['Descriptive association only; no causal effect or statistical significance is established.',
                   'Reviews are ordinal. Mean scores assume equally spaced score points; pairwise comparisons preserve ordering.',
                   'Population: delivered orders with valid delivery dates and an eligible selected review. Missing reviews are excluded; this can introduce selection bias.',
                   'Repeated customers and shared sellers can create dependence. No independent-observation hypothesis test is performed.']
        return finish('ok', '\n'.join(observations), result=result, analysis=analysis, observations=observations, caveats=caveats)
    except (ValueError, OSError, RuntimeError, QueryExecutionError, SQLSafetyError) as exc:
        trace.append(dict(stage='tool_failure', error=str(exc)[:300]))
        return finish('failed', 'A required tool failed. No statistical conclusion was produced; inspect the trace.')
