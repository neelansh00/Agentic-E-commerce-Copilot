"""Evidence reports for the deterministic baseline."""
import json
from pathlib import Path


def write_project_metrics(root: Path):
    lines = ['# Measured project metrics', '',
             'Regenerated from saved reports by the verification and baseline scripts. These are deterministic checks, not model accuracy.', '']
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
    lines += ['- LLM execution accuracy, answer accuracy, RAG retrieval accuracy, latency improvement and cost: not measured.',
              '- The approximately 50-question agent evaluation and controlled experiments remain for later phases.', '',
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
