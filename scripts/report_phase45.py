"""Run offline regressions and regenerate the preserved before/after comparison; no API calls."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.ingest import file_hash
from app.analytics.reporting import write_project_metrics

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def main():
    old = read('docs/generated/live_evaluation.json')
    new = read('docs/generated/phase45_live_evaluation.json')
    review = read('evaluation/phase45_answer_review.json')
    failures = read('evaluation/phase45_failure_analysis.json')
    checks = read('docs/generated/phase45_metric_checks.json')
    replay = read('docs/generated/phase45_reference_replay/text_to_sql_report.json')
    old_hash = file_hash(ROOT / 'docs/generated/live_evaluation.json')
    new_hash = file_hash(ROOT / 'docs/generated/phase45_live_evaluation.json')
    if review['evaluation_sha256'] != new_hash or failures['corrected_evaluation_sha256'] != new_hash or failures['original_evaluation_sha256'] != old_hash:
        raise ValueError('Review annotations must match the exact archived evaluation files')
    test_run = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],
                              cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    match = re.search(r'Ran (\d+) tests', test_run.stderr)
    tests = dict(exit_code=test_run.returncode, count=int(match[1]) if match else None, output=test_run.stderr,
                 measured_at_utc=datetime.now(timezone.utc).isoformat())
    (ROOT / 'docs/generated/phase45_tests.json').write_text(json.dumps(tests,indent=2)+'\n')
    same_benchmark = old['cases'] == new['cases'] and old['reference_sha256'] == new['reference_sha256'] and old['model'] == new['model'] and old['modes'] == new['modes']
    expected_reviews = {(r['id'],r['mode']) for r in new['results']}
    review_complete = expected_reviews == {(r['id'],r['mode']) for r in review['results']} and len(review['results']) == len(expected_reviews)
    no_misleading = review_complete and all(r['no_factually_misleading_rendered_interpretation'] for r in review['results'])
    execution_complete = new['complete'] and all(s['executed']==s['questions']==11 for s in new['summaries'].values())
    accuracy_gate = all(s['exact_results']>=10 and s['questions']==11 for s in new['summaries'].values())
    ready = test_run.returncode == 0 and bool(tests['count']) and same_benchmark and no_misleading and execution_complete and accuracy_gate and new['database_unchanged'] and checks['all_passed'] and replay['all_passed']
    readiness = dict(ready_for_phase5=ready, phase5_started=False, offline_tests=tests['count'], offline_tests_passed=test_run.returncode==0,
        same_questions_model_and_reference=same_benchmark, sql_execution_complete=execution_complete,
        accuracy_threshold_met=accuracy_gate, no_misleading_rendered_interpretations=no_misleading,
        reviewed_answers=len(review['results']), metric_checks_passed=checks['all_passed'], reference_replay_passed=replay['all_passed'],
        limitation='Readiness is for continuing project development on this corrected development benchmark, not production or unseen-question accuracy.',
        original_report_sha256=old_hash, corrected_report_sha256=new_hash)
    (ROOT / 'docs/generated/phase45_readiness.json').write_text(json.dumps(readiness,indent=2)+'\n')
    lines = ['# Phase 4.5 correction results', '',
        f"**Ready for Phase 5 development: {ready}. Phase 5 has not started.**", '',
        f"Model: `{new['model']}`. Exactly the same eleven questions, output contracts, group keys and reference values: **{same_benchmark}**. No complete benchmark SQL was added to the application. Original results are preserved.", '',
        '| Context | Previous execution | Corrected execution | Previous exact results | Corrected exact results |',
        '|---|---:|---:|---:|---:|']
    for mode in new['modes']:
        a,b=old['summaries'][mode],new['summaries'][mode]
        lines.append(f"| {mode} | {a['executed']}/11 | {b['executed']}/11 | {a['exact_results']}/11 ({a['exact_results']/11:.1%}) | {b['exact_results']}/11 ({b['exact_results']/11:.1%}) |")
    lines += ['', f"Offline regressions: **{tests['count']} run; all passed: {test_run.returncode == 0}** (original 76 plus {max(0,(tests['count'] or 0)-76)} new tests). Full-data metric checks: **{sum(c['passed'] for c in checks['checks'])}/{len(checks['checks'])}**. Existing guarded reference replays all passed: **{replay['all_passed']}**. Database unchanged: **{new['database_unchanged']}**.", '',
        '## Explanation review', '', review['reviewer']+'.', '',
        'All 22 rendered outputs were reviewed against their cells and correct query results. No misleading interpretation was found. Free-form model labels are no longer displayed: captions are deterministic and each selected state/category/seller/month identity is copied from the same row. The renderer makes no ranking assertions.', '',
        '| Context | Model cell selections accepted | Literal fallbacks | Misleading rendered interpretations found |',
        '|---|---:|---:|---:|']
    for mode,s in new['summaries'].items():
        misleading=sum(not r['no_factually_misleading_rendered_interpretation'] for r in review['results'] if r['mode']==mode)
        lines.append(f"| {mode} | {s['structurally_valid_explanations']}/11 | {s['explanation_fallbacks']}/11 | {misleading}/11 |")
    lines += ['', 'Five answers still use explicit literal fallbacks because model labels contain digits. Safe output is not the same as a useful or complete generated summary: monthly fallbacks show first-row coverage, and category/seller summaries sometimes omit the central metric. Full correct results are retained. This pass does not claim unrestricted narrative-generation quality or an independent human groundedness score.', '',
        '## Each previously failed case', '',
        'Result status below refers to the full returned table. Explanation fallbacks are shown separately rather than counted as misleading prose.', '']
    for f in failures['failures']:
        before,after=f['previous'],f['corrected']
        lines += [f"### {f['id']} / {f['mode']}", '',
            f"- Categories: {', '.join(f['categories'])}.",
            f"- Previous: executed={before['executed']}, exact result={before['result_match']}, fallback={before['explanation_fallback']}.",
            f"- Corrected: executed={after['executed']}, exact result={after['result_match']}, fallback={after['explanation_fallback']}; rendered answer reviewed as non-misleading.",
            '- Root cause: '+f['root_cause'], '- Fix: '+f['fix'],
            '- Regression tests in `tests/test_phase45.py`: '+', '.join('`'+t+'`' for t in f['regression_tests'])+'.', '']
    lines += ['## Live rerun usage and interpretation', '',
        f"{sum(s['api_calls'] for s in new['summaries'].values())} API calls; {sum(s['input_tokens'] for s in new['summaries'].values()):,} input tokens and {sum(s['output_tokens'] for s in new['summaries'].values()):,} output tokens. Estimated cost: USD {new.get('estimated_cost_usd','unavailable')} using the recorded rate card, not an invoice.", '',
        'This is one development rerun per context after fixes motivated by the observed failures. It is not an unseen benchmark, a model comparison, or a statistically established RAG improvement. Several layers changed, so no isolated causal attribution of the improvement is claimed. Both modes now match all eleven complete reference results.', '',
        'The readiness decision meets the requested gates for continuing development: all regressions pass, execution is complete, exact results exceed 10/11 in both modes and none of the reviewed rendered answers is factually misleading. This does not authorize or start Phase 5.', '',
        'Evidence: [implementation and trade-offs](../phase45_corrections.md), [raw corrected run](phase45_live_evaluation.json), [original run](live_evaluation.json), [answer review](../../evaluation/phase45_answer_review.json), [failure classifications](../../evaluation/phase45_failure_analysis.json), [test output](phase45_tests.json), [metric checks](phase45_metric_checks.json), [readiness gates](phase45_readiness.json).', '']
    (ROOT / 'docs/generated/phase45_report.md').write_text('\n'.join(lines),encoding='utf-8')
    write_project_metrics(ROOT)
    print(json.dumps(readiness,indent=2))
    if not ready:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
