"""Regenerate live evaluation tables and semantic-review summaries without API calls."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.ingest import file_hash
from app.analytics.reporting import write_project_metrics

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'docs/generated/live_evaluation.json'
    report = json.loads(source.read_text(encoding='utf-8'))
    review = json.loads((ROOT / 'evaluation/live_answer_review.json').read_text(encoding='utf-8'))
    if review['evaluation_sha256'] != file_hash(source):
        raise ValueError('Semantic review belongs to another evaluation; review the new outputs first')
    lines = ['# Live SQL generation and constrained answer evaluation', '',
        f"Model: `{report['model']}`. Completed: {report['complete']}. Database unchanged: {report['database_unchanged']}.", '',
        'Eleven development questions, each with an explicit output contract, sampled once per context. Static means the full metric document; RAG means retrieved excerpts. Neither mode is a no-definitions baseline. These are live-generated SQL results, not scripted replay.', '',
        '| Context | Questions executed | Exact results | Accepted explanation format | Literal fallbacks | Median latency | API calls |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for mode, s in report['summaries'].items():
        n = s['questions']
        lines.append(f"| {mode} | {s['executed']}/{n} ({s['executed']/n:.1%}) | {s['exact_results']}/{n} ({s['exact_results']/n:.1%}) | {s['structurally_valid_explanations']}/{n} | {s['explanation_fallbacks']} | {s['median_latency_ms']/1000:.3f}s | {s['api_calls']} |")
    total = sum(s['api_calls'] for s in report['summaries'].values())
    inputs = sum(s['input_tokens'] for s in report['summaries'].values())
    outputs = sum(s['output_tokens'] for s in report['summaries'].values())
    lines += ['', f"This benchmark made {total} API calls, with {inputs:,} input tokens and {outputs:,} output tokens. Estimated cost: USD {report.get('estimated_cost_usd', 'unavailable')} using the recorded rate card; not an invoice. Connectivity smoke calls are excluded (see JSON).", '',
        'Full numerical result accuracy is distinct from explanation quality. A query may execute and an explanation may reference real cells while both are semantically misleading.', '',
        '## Semantic explanation review', '', review['reviewer']+'.', '', review['rubric'], '',
        '| Context | Accepted explanations | Labels faithful to returned result | Faithful labels and exact query result |', '|---|---:|---:|---:|']
    scores = {}
    for mode in report['modes']:
        accepted = [r for r in review['results'] if r['mode'] == mode and r['labels_faithful_to_returned_result'] is not None]
        faithful = [r for r in accepted if r['labels_faithful_to_returned_result']]
        exact = {(r['id'], r['mode']) for r in report['results'] if r['result_match']}
        combined = sum((r['id'], r['mode']) in exact for r in faithful)
        scores[mode] = dict(accepted=len(accepted), faithful=len(faithful), faithful_and_exact=combined)
        lines.append(f"| {mode} | {len(accepted)} | {len(faithful)}/{len(accepted)} | {combined}/{len(accepted)} |")
    lines += ['', 'These conditional review counts are not unrestricted generative-answer accuracy. Literal fallbacks are excluded; useful question coverage is assessed separately below. All explanations currently use model-selected labels/cells with values inserted by Python.', '',
        '## Per-question evidence', '', '| Question | Context | Exact result | Explanation |', '|---|---|---|---|']
    for row in report['results']:
        state = 'accepted' if row['explanation_validated'] else 'literal fallback' if row['explanation_fallback'] else 'unavailable'
        lines.append(f"| {row['id']} | {row['mode']} | {row['result_match']} | {state} |")
    lines += ['', '## Reviewed answer limitations', '']
    for r in review['results']:
        lines.append(f"- **{r['id']} / {r['mode']}** ({r['question_coverage']}): {r['note']}")
    lines += ['', '## SQL failure analysis', '',
        '- Monthly revenue, both contexts: returns 25 observed months instead of the 26-month calendar spine; converts missing eligible payment sums to zero instead of NULL.',
        '- Category delivery, static: counts distinct orders but averages and sums over item rows, so repeated order/category items change delivery metrics.',
        '- Overall delivery, RAG: mean delivery duration is averaged without the eligibility filter, although late counts use it.',
        '- Seller performance, static: SQLGlot classifies EXISTS under its function hierarchy and the current allowlist rejects it; the model repeats the rejected construct through all three attempts. This is an overly restrictive validator path, not an unsafe statement.',
        '- Seller performance, RAG: delivered population uses non-null delivered timestamps instead of delivered status; latest-review candidate filtering also differs from the reference. Platform mean is 4.155812 versus reference 4.155976.', '',
        '## Before Phase 5', '',
        'API access works, but this run does not establish reliable analytical answers. Address metric-grain/NULL/calendar semantics, the EXISTS validator false positive, explicit row/group references and verified extrema before expanding the agent. Preserve this initial run, add regression tests and evaluate fixes on separate paraphrases; do not replace failed results with successful reruns.', '',
        'No statistically justified RAG improvement is claimed: both contexts match 8/11 complete results, with different failures and one sample each. The model and questions were not tuned during this run. See [methodology](../live_evaluation.md), the JSON traces and [semantic review annotations](../../evaluation/live_answer_review.json).', '']
    (ROOT / 'docs/generated/live_evaluation.md').write_text('\n'.join(lines), encoding='utf-8')
    write_project_metrics(ROOT)
    print(json.dumps(scores, indent=2))


if __name__ == '__main__':
    main()
