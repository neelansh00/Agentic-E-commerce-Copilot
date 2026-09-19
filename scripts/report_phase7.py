"""Render measured Phase 7 results from preserved runs and explicit review notes."""
from collections import Counter
import json
from pathlib import Path
import statistics
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.database.ingest import file_hash
from app.evaluation.scoring import ratio
from app.analytics.reporting import write_project_metrics


def main():
    def read(name): return json.loads((ROOT/name).read_text(encoding='utf-8'))
    benchmark=read('docs/generated/phase7_benchmark.json')
    experiments=read('docs/generated/phase7_experiments.json')
    notes=read('evaluation/phase7_review_notes.json')
    c_review=read('evaluation/phase7_definition_review.json')
    tests=read('docs/generated/phase7_tests.json')
    questions=read('evaluation/questions.json')['questions']
    assert benchmark['complete'] and experiments['complete']
    assert benchmark['benchmark_sha256']==experiments['benchmark_sha256']==file_hash(ROOT/'evaluation/questions.json')
    assert c_review['experiment_sha256']==file_hash(ROOT/'docs/generated/phase7_experiments.json')
    assert benchmark['model']==experiments['model']
    assert benchmark['database_unchanged'] and experiments['database_unchanged'] and experiments['isolated_copy_unchanged']
    assert len(c_review['cases'])==16 and len({(r['id'],r['mode']) for r in c_review['cases']})==16
    assert all(r['all_required_facts']==all(r['facts_supported']) for r in c_review['cases'])
    substantive=[r for r in benchmark['results'] if r['response']['status']=='ok']
    grounded=[r for r in substantive if r['id'] not in notes['unsupported_answer_ids']]
    review=[]
    for r in benchmark['results']:
        review.append(dict(id=r['id'],status=r['response']['status'],substantive_answer=r in substantive,
            supported_for_requested_metric=(r['id'] not in notes['unsupported_answer_ids']) if r in substantive else None,
            partial_summary=r['id'] in notes['partial_summary_ids'],note=notes['summary_notes'].get(r['id'],'')))
    (ROOT/'evaluation/phase7_answer_review.json').write_text(json.dumps(dict(benchmark_sha256=file_hash(ROOT/'docs/generated/phase7_benchmark.json'),method=notes['groundedness_method'],reviewer=notes['reviewer'],cases=review),indent=2)+'\n',encoding='utf-8')
    summary=dict(benchmark=benchmark['summary'],offline_tests=tests,groundedness_review=ratio(len(grounded),len(substantive)),
                 categories={},experiments={},total_api_calls=benchmark['api_calls']+experiments['api_calls'])
    for category in sorted({r['category'] for r in benchmark['results']}):
        rows=[r for r in benchmark['results'] if r['category']==category]
        summary['categories'][category]=ratio(sum(r['score']['result_correct'] for r in rows),len(rows))
    for experiment in ['A','B']:
        rows=[r for r in experiments['experiments'] if r['experiment']==experiment]
        modes={}
        for mode in sorted({r['mode'] for r in rows}):
            selected=[r for r in rows if r['mode']==mode]
            modes[mode]=dict(execution=ratio(sum(r['executed'] for r in selected),len(selected)),accuracy=ratio(sum(r['correct'] for r in selected),len(selected)))
            if experiment=='A':
                modes[mode]['input_tokens']=sum(u['input_tokens'] for r in selected for u in r['usage'])
                modes[mode]['median_latency_ms']=statistics.median(r['latency_ms'] for r in selected)
        summary['experiments'][experiment]=modes
    for mode in ['without_definitions','with_rag']:
        rows=[r for r in c_review['cases'] if r['mode']==mode]
        automatic=[r for r in experiments['experiments'] if r['experiment']=='C' and r['mode']==mode]
        summary['experiments'].setdefault('C',{})[mode]=dict(semantic_contract_coverage=ratio(sum(r['all_required_facts'] for r in rows),len(rows)),lexical_proxy=ratio(sum(r['rubric']['all_patterns_present'] for r in automatic),len(automatic)))
    full_tokens=summary['experiments']['A']['full_schema']['input_tokens']
    retrieved_tokens=summary['experiments']['A']['retrieved_schema']['input_tokens']
    summary['schema_input_token_reduction_pct']=100*(full_tokens-retrieved_tokens)/full_tokens
    all_usage=benchmark['usage']+experiments['usage']
    summary['tokens']=dict(input=sum(u['input_tokens'] for u in all_usage),output=sum(u['output_tokens'] for u in all_usage))
    summary['database_unchanged']=True
    (ROOT/'docs/generated/phase7_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    def fmt(metric): return f"{metric['numerator']}/{metric['denominator']} ({100*metric['rate']:.1f}%)" if metric['rate'] is not None else 'Not measured'
    lines=['# Phase 7 measured evaluation', '',f"Model: `{benchmark['model']}`. Fifty frozen development questions; production code unchanged during evaluation. All {tests['tests_run']} offline tests pass.",'',
           '| Metric | Result |','|---|---:|']
    for key in ['sql_execution','sql_result_accuracy','task_correctness','tool_selection','status_accuracy','rag_heading_hit']:
        lines.append(f"| {key.replace('_',' ')} | {fmt(benchmark['summary'][key])} |")
    lines += [f"| Reviewed support for requested metric among substantive answers | {fmt(summary['groundedness_review'])} |",'',
              'Groundedness is coding-assistant review against evidence, not independent human annotation. Ten abstentions are outside its denominator; incorrect abstentions still fail task correctness. Definition heading hits are retrieval scores, not generated-prose accuracy.',
              f"Median end-to-end case latency: {benchmark['summary']['median_latency_ms']:.1f} ms. This mixes cheap deterministic requests and model SQL, not a SQL-only latency estimate. Literal explanation fallbacks: {benchmark['summary']['explanation_fallbacks']}.",'',
              '| Category | Correct tasks |','|---|---:|']
    for category,metric in summary['categories'].items(): lines.append(f'| {category} | {fmt(metric)} |')
    lines += ['', 'The five statistical cases contain three paraphrases of the supported global comparison and two expected refusals. This is not five distinct statistical tools. Correct refusals contribute to task correctness, not SQL result accuracy.', '', '## Failures and answer usefulness','']
    for identifier,failure in notes['benchmark_semantic_failures'].items():
        lines += [f"- **{identifier}: {failure['category']}.** {failure['root_cause']} Next correction: {failure['next_fix']}"]
    lines += ['', 'Correct SQL tables can still have weak explanations. Monthly/status/state fallbacks show only the first row; seller-state/payment-type captions miss dimension or unit labels; several summaries select scattered cells. These are coverage issues, not additional exact-SQL failures. The allocation case is an intent-level correctness failure and is also excluded from grounded answers.', '',
              '## Controlled comparisons', '', '| Experiment / mode | Executed | Exact results |', '|---|---:|---:|']
    for experiment in ['A','B']:
        for mode,metric in summary['experiments'][experiment].items():
            lines.append(f"| {experiment}: {mode} | {fmt(metric['execution'])} | {fmt(metric['accuracy'])} |")
    lines += ['', '| C: definition context | All required facts supported (assistant review) |','|---|---:|']
    for mode,metric in summary['experiments']['C'].items(): lines.append(f"| {mode} | {fmt(metric['semantic_contract_coverage'])} |")
    lines += ['', 'A changes only full versus retrieved schema, with one attempt in each arm. B reuses the same initial SQL in both arms and retains engine safety on an isolated read-only copy. C compares generated definitions with/without retrieved context, separately from the production verbatim-RAG path. See the protocol for exact controls and limitations.', '',
              '### Schema context cost and latency','']
    for mode,metric in summary['experiments']['A'].items():
        lines.append(f"- {mode}: {metric['input_tokens']:,} input tokens; median {metric['median_latency_ms']:.1f} ms.")
    lines += [f"- Retrieved-schema input tokens were {summary['schema_input_token_reduction_pct']:.2f}% lower in this sample. Accuracy was lower, not improved; median latency differences are not statistically established.", '',
              '### Experiment failure analysis', '',
              '- A: both schema arms generated `customer_state` directly from `orders` for state cancellation. The field belongs to the customer dimension (or joined metric view). Execution failed in both arms. B repaired the same initial retrieved-schema query by selecting from `metric_orders`; this was the single successful repair.',
              '- A/B: retrieved-schema monthly SQL retained the empty calendar month but left SUMs of count flags NULL instead of zero. Monetary NULL values were appropriate; coverage counts were wrong. The query executed, so the current validator did not trigger a retry. The schema included the required fields; this is a generated aggregation/NULL-semantics error, not evidence of a missing table in retrieval.',
              '- C: without context, the monthly answer substituted customer-acquisition cohorts for order-purchase cohorts, while other answers were generic or explicitly uncertain. With RAG, six answers expressed all required facts. The lateness answer did not explicitly exclude unknown dates from the denominator; the cohort answer covered NULL for empty months but omitted nonempty cohorts with no eligible payments. Both passed the lexical rubric, demonstrating why 8/8 pattern hits are not 8/8 complete semantic answers.',
              '- Suggested follow-up regressions: count flags after a calendar LEFT JOIN, raw-versus-joined state columns, and definition completeness for unknown dates and missing payments. Preserve this run as the pre-correction evidence.', '']
    lines += ['', '### Engineering interpretation','',
              'Keep the small existing architecture. The comparisons do not justify adding another agent, an embedding schema router or a new framework. B supports bounded diagnostic retry with one repaired query; engine and application safety remain essential beyond that sample. The simple schema retriever has a measured token saving but no measured accuracy gain here: retain the full-schema evaluation alternative and test a broader held-out set before choosing a default on accuracy grounds. RAG supplies project policy, but retrieval hits and lexical coverage cannot replace semantic review.', '',
              'This is one sample per arm on development questions in fixed order. No significance, held-out generalization, causal performance improvement or production readiness is claimed. Do not compare the 50-question agent score directly with the earlier 11-question text-to-SQL score: routing and refusal behavior are now part of the measured system.', '',
              '## Usage and reproducibility','',
              f"Actual API requests: {summary['total_api_calls']} ({benchmark['api_calls']} benchmark + {experiments['api_calls']} experiments). Input tokens: {summary['tokens']['input']:,}; output tokens: {summary['tokens']['output']:,}. Reused B plans are not charged twice in this count. No current-price cost estimate is claimed.",
              'The original database and isolated experiment copy are unchanged. Questions and prior phase reports are preserved. Phase 8 has not started.', '',
              'Evidence: [protocol](../phase7_evaluation.md), [frozen questions](../../evaluation/questions.json), [benchmark outputs](phase7_benchmark.json), [experiments](phase7_experiments.json), [answer review](../../evaluation/phase7_answer_review.json), [definition review](../../evaluation/phase7_definition_review.json), [offline checks](phase7_tests.json).', '']
    (ROOT/'docs/generated/phase7_report.md').write_text('\n'.join(lines),encoding='utf-8')
    write_project_metrics(ROOT)
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
