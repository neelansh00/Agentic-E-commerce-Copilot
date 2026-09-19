"""Evidence reports for the deterministic baseline."""
import json
import re
from pathlib import Path


def write_project_metrics(root: Path):
    lines = ['# Measured project metrics', '',
             'Regenerated from saved reports. Deterministic checks, retrieval metrics and live development results are labeled separately.', '']
    verification_path = root / 'docs/generated/verification_report.json'
    if verification_path.exists():
        report = json.loads(verification_path.read_text(encoding='utf-8'))
        lines += [f"- Source CSVs / database tables: {len(report['source_files'])} / {len(report['source_files'])}.",
                  f"- Source and loaded records: {sum(t['rows'] for t in report['source_files'].values()):,} (includes original duplicates).",
                  f"- Database checks passed: {sum(c['passed'] for c in report['checks'])}/{len(report['checks'])}.",
                  '- Six join/cardinality checks; three exact monetary reconciliations against CSV Decimal sums.']
    baseline_path = root / 'docs/generated/baseline_report.json'
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
        queries = baseline['queries']
        lines += [f"- Deterministic reference questions: {len(queries)}.",
                  f"- Reference SQL executions completed: {sum(q['execution_ok'] for q in queries.values())}/{len(queries)}.",
                  f"- SQL results matching independent CSV calculations: {sum(q['reference_match'] for q in queries.values())}/{len(queries)}.",
                  f"- Reference result rows checked: {sum(len(q.get('rows', [])) for q in queries.values())}.",
                  f"- Frozen ground-truth comparison: {baseline['snapshot_status']}.",
                  f"- Baseline run wall time: {baseline['elapsed_seconds']} seconds (single local run, includes reference verification; not an improvement claim)."]
    text_sql_path = root / 'docs/generated/text_to_sql_report.json'
    if text_sql_path.exists():
        text_sql = json.loads(text_sql_path.read_text(encoding='utf-8'))
        results = text_sql['results']
        lines += [f"- Phase 3 offline reference replays matching ground truth: {sum(r['expected_result_match'] for r in results.values())}/{len(results)} (not model-generated SQL).",
                  f"- Keyword schema retrieval contains required tables: {sum(r['retrieval_contains_expected'] for r in results.values())}/{len(results)} reference questions (development set).",
                  f"- Database unchanged after guarded execution: {text_sql['database_unchanged']}.",
                  f"- Phase 3 model API calls: {text_sql['model_api_calls']} (offline by user request)."]
    rag_path = root / 'docs/generated/rag_report.json'
    if rag_path.exists():
        rag = json.loads(rag_path.read_text(encoding='utf-8'))
        lines += [f"- Phase 4 retrieval benchmark: {len(rag['results'])} manually authored cases; real local embeddings, zero LLM API calls."]
        for split, metrics in rag['groups'].items():
            lines += [f"- RAG {split}: {metrics['supported']} supported / {metrics['unknown']} unknown questions; Hit@3 {metrics['hit_at_3']:.1%}, Top-1 {metrics['top1_accuracy']:.1%}, MRR@3 {metrics['mrr_at_3']:.3f}, unknown abstention {metrics['abstention_accuracy']:.1%}; median query {metrics['median_query_ms']} ms (startup excluded)."]
        lines += ['- Retrieval scores measure expected-heading matches on a small same-author benchmark, not generated-answer accuracy. See [retrieval evidence](generated/rag_report.md).']
    live_path = root / 'docs/generated/live_evaluation.json'
    if live_path.exists():
        live = json.loads(live_path.read_text(encoding='utf-8'))
        lines += [f"- Original live model evaluation: `{live['model']}`; preliminary development evaluation, one sample per question/context."]
        for mode, summary in live['summaries'].items():
            if not summary:
                continue
            count = summary['questions']
            lines += [f"- Live {mode}: {summary['executed']}/{count} questions executed; {summary['exact_results']}/{count} complete results match reference; {summary['structurally_valid_explanations']}/{count} explanations pass structural validation (not semantic quality); median {summary['median_latency_ms']} ms."]
        lines += [f"- Live benchmark API calls: {sum(s.get('api_calls', 0) for s in live['summaries'].values())}; estimated USD cost {live.get('estimated_cost_usd', 'unavailable')} (not invoice; smoke tests excluded).",
                  '- Semantic label review found wrong group/extrema claims despite valid cell references. See [live evaluation and answer review](generated/live_evaluation.md).']
    else:
        lines += ['- Live SQL generation and model answer quality: not measured.']
    corrected_path = root / 'docs/generated/phase45_live_evaluation.json'
    readiness_path = root / 'docs/generated/phase45_readiness.json'
    if corrected_path.exists() and readiness_path.exists():
        corrected = json.loads(corrected_path.read_text(encoding='utf-8'))
        readiness = json.loads(readiness_path.read_text(encoding='utf-8'))
        lines += ['', '- Phase 4.5: same eleven questions, output contracts, reference and model; observed development failures corrected, not an unseen test.']
        for mode, summary in corrected['summaries'].items():
            lines += [f"- Corrected {mode}: {summary['executed']}/{summary['questions']} executions and {summary['exact_results']}/{summary['questions']} exact results; {summary['explanation_fallbacks']} explicitly marked literal fallbacks."]
        lines += [f"- Phase 4.5 offline tests: {readiness['offline_tests']}; all passed: {readiness['offline_tests_passed']}.",
                  f"- All {readiness['reviewed_answers']} final rendered answers reviewed as non-misleading: {readiness['no_misleading_rendered_interpretations']} (assistant review, not independent human annotation).",
                  f"- At the end of Phase 4.5: readiness gates met: {readiness['ready_for_phase5']}; Phase 5 started: {readiness['phase5_started']}.",
                  '- Evidence: [correction report](generated/phase45_report.md). Safe captions and correct tables do not prove complete narrative quality or production readiness.']
    phase5_path = root / 'docs/generated/phase5_final_verification.json'
    if phase5_path.exists():
        phase5 = json.loads(phase5_path.read_text(encoding='utf-8'))
        routing = phase5['routing']
        live = phase5['live_smoke']
        test_count = re.search(r'Ran (\d+) tests', phase5['test_output'])
        lines += ['', f"- Phase 5 verification passed: {phase5['all_passed']}; offline tests passed: {phase5['tests_passed']}.",
                  f"- Phase 5 offline tests executed: {test_count.group(1) if test_count else 'not recorded'}.",
                  f"- Deterministic routing development cases: {sum(r['passed'] for r in routing)}/{len(routing)} (not held-out language coverage).",
                  f"- Complete delivery/review histogram agrees with independent raw CSV calculation: {phase5['histogram_matches_independent_csv']}.",
                  f"- Phase 5 live smoke exact matches: {sum(r['reference_match'] for r in live)}/{len(live)}; two-question smoke, not a new full benchmark.",
                  '- One restricted Python operation; all five SQL/RAG/Python tool combinations exercised. See [Phase 5](phase5_agent.md).']
    phase6_path = root / 'docs/generated/phase6_verification.json'
    if phase6_path.exists():
        phase6 = json.loads(phase6_path.read_text(encoding='utf-8'))
        flows = phase6['flows']
        lines += ['', f"- Phase 6 offline tests: {phase6['offline_tests']}; passed: {phase6['tests_passed']}.",
                  f"- Real-data Streamlit flows passed: {sum(f['passed'] for f in flows)}/{len(flows)}; includes explicitly labeled scripted/local/live modes.",
                  f"- Database unchanged during UI verification: {phase6['database_unchanged']}.",
                  '- Streamlit rerender and session-isolation checks are functional tests, not a usability study or production load test.',
                  '- Evidence: [Phase 6 UI](phase6_ui.md) and [raw verification](generated/phase6_verification.json).']
    phase7_path = root / 'docs/generated/phase7_summary.json'
    if phase7_path.exists():
        phase7 = json.loads(phase7_path.read_text(encoding='utf-8'))
        lines += ['', '- Phase 7: fifty frozen development questions; includes eleven previously used SQL questions. Not held out.']
        for label in ['sql_execution','sql_result_accuracy','task_correctness','tool_selection','rag_heading_hit']:
            metric = phase7['benchmark'][label]
            lines += [f"- Phase 7 {label}: {metric['numerator']}/{metric['denominator']} ({100*metric['rate']:.1f}%)."]
        lines += [f"- Phase 7 offline tests: {phase7['offline_tests']['tests_run']}; passed: {phase7['offline_tests']['passed']}.",
                  f"- Paired schema experiment input-token reduction: {phase7['schema_input_token_reduction_pct']:.2f}%; retrieved schema did not improve accuracy in this sample (8/10 vs 9/10).",
                  '- Validation/retry experiment: execution 9/10 to 10/10; exact results 8/10 to 9/10, one shared initial-plan repair.',
                  '- Definition experiment: all required facts covered 0/8 without context vs 6/8 with RAG, coding-assistant semantic review.',
                  f"- Phase 7 actual model API calls: {phase7['total_api_calls']}; tokens: {phase7['tokens']['input']:,} input / {phase7['tokens']['output']:,} output. No current-price cost estimate.",
                  '- Evidence and unresolved errors: [Phase 7 report](generated/phase7_report.md). Do not present this as 100% reliable or independent human evaluation.']
    else:
        lines += ['- The approximately 50-question agent evaluation and controlled experiments remain for later phases.']
    lines += ['- Unrestricted narrative-answer accuracy, statistically established improvements and business impact: not measured.', '',
              'Evidence: [database verification](generated/verification_report.md), [baseline report](generated/baseline_report.md), [offline text-to-SQL integration](generated/text_to_sql_report.md).', '']
    (root / 'docs/project_metrics.md').write_text('\n'.join(lines), encoding='utf-8')


def markdown_report(report):
    lines = ['# Deterministic analytics baseline — Phase 2', '',
             f"Metric contract version: {report['metric_version']}. All checks passed: **{report['all_passed']}**.",
             f"Frozen reference snapshot: **{report['snapshot_status']}**.", '',
             'Each SQL result is compared with a separate Python calculation over the original CSVs. Counts, cents, strings, NULLs and ordering match exactly; rounded float metrics allow absolute error up to 0.000002.',
             'These results validate manually authored SQL; they do not measure LLM accuracy, statistical significance or causality.', '',
             '| Query | SQL ran | CSV agreement | Rows | Execution ms |', '|---|---|---|---:|---:|']
    for name, result in report['queries'].items():
        lines.append(f"| {name} | {result['execution_ok']} | {result['reference_match']} | {len(result.get('rows', []))} | {result.get('execution_ms', '—')} |")
    lines += ['', 'Full results, executed SQL, parameters, source hashes and errors are in `baseline_report.json`. Only the first five rows per query are shown below. Timing is one local sequential execution per query, including fetching results; it is not a benchmark comparison.', '']
    if report.get('snapshot_errors'):
        lines += ['Snapshot errors: ' + '; '.join(report['snapshot_errors']), '']
    if report['all_passed']:
        overview = report['queries']['overview']['rows'][0]
        delivery = report['queries']['late_delivery']['rows'][0]
        review_groups = {r['delivery_group']: r for r in report['queries']['late_reviews']['rows']}
        lines += ['## Observations', '']
        if overview['revenue_cents'] is not None:
            lines.append(f"- Delivered-order recorded payment revenue: **BRL {overview['revenue_cents']/100:,.2f}**, across {overview['paid_delivered_orders']:,} orders with payments. {overview['delivered_missing_payment']:,} delivered orders lack payments.")
        if delivery['late_pct'] is not None:
            lines.append(f"- Strict timestamp lateness: **{delivery['late_pct']:.2f}%** ({delivery['late_orders']:,}/{delivery['eligible_orders']:,} eligible deliveries); {delivery['excluded_orders']:,} delivered orders excluded.")
        if all(key in review_groups and review_groups[key]['mean_review_score'] is not None for key in ('late', 'on_time')):
            late, on_time = review_groups['late'], review_groups['on_time']
            lines.append(f"- Mean selected review score: **{late['mean_review_score']:.2f} late** ({late['reviewed_orders']:,} reviews) versus **{on_time['mean_review_score']:.2f} on time** ({on_time['reviewed_orders']:,} reviews).")
        lines += ['', '## Interpretation and limits', '',
                  'Group differences, where present, are descriptive; investigate delivery experience alongside product mix, geography and review-selection effects. These averages do not establish causality or statistical significance. Seller lists identify candidates for review, not evidence of fault. Revenue is the project-defined payment proxy, not net accounting revenue.', '']
    for name, result in report['queries'].items():
        lines += [f'## {name}', '', result['question'], '', result['interpretation'], '']
        if result.get('errors'):
            lines += [f"Errors: {result['errors']}", '']
        if result.get('rows'):
            columns = result['columns']
            lines += ['| ' + ' | '.join(columns) + ' |', '| ' + ' | '.join('---' for _ in columns) + ' |']
            for row in result['rows'][:5]:
                lines.append('| ' + ' | '.join('NULL' if row[c] is None else str(row[c]).replace('|', '\\|') for c in columns) + ' |')
            lines.append('')
        else:
            lines += ['No result rows.', '']
    return '\n'.join(lines)
