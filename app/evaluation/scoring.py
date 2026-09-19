"""Explicit denominators; proxies are never mislabeled as human answer quality."""
import re
import statistics
from app.evaluation.live import compare_unordered


def ratio(numerator, denominator):
    return dict(numerator=numerator,denominator=denominator,rate=numerator/denominator if denominator else None)


def score_case(case, response):
    executed=response.result is not None
    correct=False; errors=[]
    retrieval=None
    if case['kind']=='sql':
        errors=compare_unordered(response.result.rows if executed else [],case['expected_rows'],case['group_keys'])
        correct=executed and not response.result.truncated and not errors
    elif case['kind']=='definition':
        headings={s['heading'] for s in response.sources}
        retrieval=set(case['expected_headings'])<=headings
        correct=response.status=='ok' and retrieval
    elif case['expected_status']=='ok' and case['kind']=='statistical':
        correct=response.status=='ok' and all(isinstance(response.analysis.get(k),(int,float)) and abs(response.analysis[k]-v)<=.000002 for k,v in case['expected_analysis'].items())
    else:
        correct=response.status==case['expected_status'] and response.result is None
    return dict(executed=executed,result_correct=bool(correct),comparison_errors=errors[:10],
                tools_correct=set(response.route.tools)==set(case['expected_tools']),
                status_correct=response.status==case['expected_status'],retrieval_hit=retrieval,
                fallback=any(t.get('status')=='deterministic_fallback' for t in response.trace))


def summarize_benchmark(rows):
    sql=[r for r in rows if r['category'] in ('simple_sql','multi_table_sql','time_based')]
    defs=[r for r in rows if r['category']=='business_definition']
    usage=[u for r in rows for u in r['response']['usage']]
    latencies=[r['response']['elapsed_ms'] for r in rows]
    return dict(
      sql_execution=ratio(sum(r['score']['executed'] for r in sql),len(sql)),
      sql_result_accuracy=ratio(sum(r['score']['result_correct'] for r in sql),len(sql)),
      task_correctness=ratio(sum(r['score']['result_correct'] for r in rows),len(rows)),
      tool_selection=ratio(sum(r['score']['tools_correct'] for r in rows),len(rows)),
      status_accuracy=ratio(sum(r['score']['status_correct'] for r in rows),len(rows)),
      rag_heading_hit=ratio(sum(r['score']['retrieval_hit'] for r in defs),len(defs)),
      explanation_fallbacks=sum(r['score']['fallback'] for r in rows),
      median_latency_ms=statistics.median(latencies) if latencies else None,
      input_tokens=sum(u.get('input_tokens',0) for u in usage),output_tokens=sum(u.get('output_tokens',0) for u in usage),
      cost_usd=None,cost_note='No current price lookup applied; token counts are measured, not an invoice.')


def rubric_score(text, patterns):
    hits=[bool(re.search(p,text,re.I|re.S)) for p in patterns]
    return dict(fact_pattern_hits=hits,all_patterns_present=all(hits),note='Lexical rubric proxy; negation and full semantic correctness require manual review.')
