"""A bounded plan/validate/execute/explain loop, with inspectable failures."""
import json
import re
import sqlite3
import time
from pydantic import ValidationError
from app.text_to_sql.config import QueryLimits
from app.text_to_sql.contracts import SQLPlan, Explanation, PipelineResult, ModelError
from app.text_to_sql.executor import execute_sql, QueryExecutionError
from app.text_to_sql.prompts import planning_messages, explanation_messages
from app.text_to_sql.safety import SQLSafetyError, SchemaMismatch
from app.text_to_sql.schema import retrieve_schema, schema_context

CAVEATS = {
    'descriptive_only': 'Observations are descriptive; they do not establish causality or statistical significance.',
    'missing_coverage': 'Check the displayed coverage counts; missing data is not zero.',
    'truncated': 'Only a bounded preview is shown; it is not the complete result.',
    'small_groups': 'Rates for small groups may be unstable; inspect denominators.',
    'revenue_proxy': 'Revenue is the delivered-order recorded-payment proxy, not net accounting revenue.',
}


def render_explanation(explanation, result):
    observations = []
    for claim in explanation.claims[:5]:
        if not 0 <= claim.row_index < len(result.rows) or claim.column not in result.columns:
            raise ValueError('Explanation referenced a nonexistent result cell')
        if not claim.label.strip() or len(claim.label) > 160 or re.search(r'\d', claim.label):
            raise ValueError('Explanation labels must be short and nonnumeric')
        if re.search(r'caus|significan|prove|due to', claim.label, re.I):
            raise ValueError('Unsupported inferential label')
        value = result.rows[claim.row_index][claim.column]
        # Values are copied from evidence, including NULL; no invented numeric prose.
        observations.append(f"{claim.label}: {json.dumps(value, ensure_ascii=False)} [row {claim.row_index}, {claim.column}]")
    if not observations:
        raise ValueError('No evidence claims')
    codes = set(explanation.caveats) | {'descriptive_only'}
    if not codes <= CAVEATS.keys():
        raise ValueError('Unknown caveat')
    if result.truncated:
        codes.add('truncated')
    return observations, [CAVEATS[c] for c in sorted(codes)]


def fallback_observations(result):
    if not result.rows:
        if result.truncated:
            return ['Rows exist, but none fit the output preview budget. Narrow the selected columns.']
        return ['The query returned no rows; no numerical conclusion is available.']
    return [f'{column}: {json.dumps(value, ensure_ascii=False)} [row 0, {column}]'
            for column, value in list(result.rows[0].items())[:5]]


def answer_question(question, database, model, limits=None):
    limits = limits or QueryLimits()
    start = time.perf_counter()
    trace, usage_start = [], len(model.usage)
    tables, reasons = retrieve_schema(question)
    def finish(status, answer, result=None, observations=None, caveats=None):
        return PipelineResult(status=status, answer=answer, result=result,
            observations=observations or [], caveats=caveats or [], schema_tables=tables,
            schema_reasons=reasons, trace=trace, usage=model.usage[usage_start:],
            elapsed_ms=round((time.perf_counter()-start)*1000, 3), model=model.name)
    if not question.strip() or len(question) > 4000:
        return finish('clarification', 'Provide a nonempty analytics question of at most 4000 characters.')
    trace.append({'tool': 'schema_retrieval', 'tables': list(tables), 'reasons': dict(reasons)})
    feedback, expanded = '', False
    for attempt in range(1, limits.max_attempts + 1):
        try:
            context = schema_context(database, tables)
            plan = SQLPlan.model_validate(model.generate(planning_messages(question, context, feedback), SQLPlan))
        except (ModelError, ValidationError, ValueError, OSError, sqlite3.Error) as exc:
            trace.append({'stage': 'model_or_schema', 'attempt': attempt, 'error': str(exc)[:500]})
            return finish('failed', 'Unable to generate a validated SQL plan. No numerical answer was produced.')
        if plan.action != 'query':
            trace.append({'stage': 'planning', 'attempt': attempt, 'action': plan.action, 'message': plan.message})
            return finish('clarification' if plan.action == 'clarify' else 'unsupported', plan.message)
        entry = {'tool': 'sql', 'attempt': attempt, 'sql': plan.sql, 'assumptions': plan.assumptions}
        trace.append(entry)
        try:
            if not plan.sql:
                raise SQLSafetyError('Query action requires SQL')
            result = execute_sql(database, plan.sql, tables, limits)
            entry.update(status='executed', tables=result.tables, execution_ms=result.execution_ms,
                         returned_rows=len(result.rows), truncated=result.truncated)
        except SchemaMismatch as exc:
            entry.update(status='rejected', error=str(exc))
            if not expanded:
                tables[:] = sorted(set(tables) | set(exc.missing))
                reasons.update({t: 'One bounded repair expansion to a known table' for t in exc.missing})
                expanded = True
                trace.append({'tool': 'schema_expansion', 'tables': list(exc.missing)})
            feedback = f'Previous SQL: {plan.sql}\n{exc}'
            continue
        except (SQLSafetyError, QueryExecutionError) as exc:
            entry.update(status='rejected_or_failed', error=str(exc))
            feedback = f'Previous SQL: {plan.sql}\n{exc}'
            continue
        if not result.rows:
            observations = fallback_observations(result)
            caveats = [CAVEATS['descriptive_only']]
            if result.truncated:
                caveats.append(CAVEATS['truncated'])
            return finish('ok', observations[0], result, observations, caveats)
        try:
            explanation = Explanation.model_validate(model.generate(explanation_messages(question, result), Explanation))
            observations, caveats = render_explanation(explanation, result)
            trace.append({'stage': 'explanation', 'status': 'evidence_references_validated'})
        except (ModelError, ValidationError, ValueError) as exc:
            observations = fallback_observations(result)
            caveats = [CAVEATS['descriptive_only'], 'Model explanation unavailable or invalid; showing literal query values.']
            if result.truncated:
                caveats.append(CAVEATS['truncated'])
            trace.append({'stage': 'explanation', 'status': 'deterministic_fallback', 'error': str(exc)[:300]})
        return finish('ok', '\n'.join(observations), result, observations, caveats)
    return finish('failed', f'SQL did not pass validation and execute within {limits.max_attempts} attempts. No numerical answer was produced.')
