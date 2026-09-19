"""Explicitly opt-in, bounded live evaluation. References never enter model prompts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.analytics.baseline import QUERIES
from app.database.ingest import file_hash
from app.evaluation.live import RecordingModel, compare_unordered, summarize
from app.text_to_sql.config import ROOT, ModelConfig, QueryLimits
from app.text_to_sql.model import OpenAIModel
from app.text_to_sql.pipeline import answer_question

KEYS = {'overview': [], 'monthly_revenue': ['purchase_month'], 'state_aov': ['customer_state'],
        'state_cancellation': ['customer_state'], 'category_sales': ['category_key'], 'late_delivery': [],
        'late_reviews': ['delivery_group'], 'category_delivery': ['category_key'],
        'seller_performance': ['seller_id'], 'seller_lateness': ['seller_id'], 'regional_delivery': ['customer_state']}


def make_cases():
    snapshot = json.loads((ROOT / 'evaluation/baseline_expected.json').read_text(encoding='utf-8'))
    cases = []
    for name, spec in QUERIES.items():
        columns = list(snapshot['questions'][name]['rows'][0])
        question = spec.question + '\nReturn exactly these output columns: ' + ', '.join(columns) + '.'
        question += '\nRound noninteger metrics to six decimals. Percentages use 0–100; monetary values remain cents. Use NULL for undefined values. Return all groups unless a top-N was requested; break ranking ties by group key ascending.'
        if name == 'monthly_revenue':
            question += ' Format purchase_month as YYYY-MM; boundary_month is integer zero or one.'
        if name == 'late_reviews':
            question += ' Use delivery_group labels late and on_time.'
        cases.append(dict(id=name, question=question, group_keys=KEYS[name], output_columns=columns))
    return cases, snapshot


def save(report, output):
    report['summaries'] = {mode: summarize([r for r in report['results'] if r['mode'] == mode]) for mode in report['modes']}
    # Rate card verified 2026-09-19; estimate, not an invoice. Unknown models have no cost estimate.
    if report['model'] == 'gpt-4.1-mini-2025-04-14':
        report['estimated_cost_usd'] = round(sum((s.get('input_tokens', 0)-s.get('cached_input_tokens', 0))*.4 + s.get('cached_input_tokens', 0)*.1 + s.get('output_tokens', 0)*1.6 for s in report['summaries'].values())/1e6, 6)
        report['pricing_source'] = 'https://developers.openai.com/api/docs/models/gpt-4.1-mini'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Required: authorize real billable API calls')
    parser.add_argument('--mode', choices=['static', 'rag', 'both'], default='both')
    parser.add_argument('--max-api-calls', type=int, default=88)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/generated/live_evaluation.json')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required; this script makes billable API calls')
    if not 1 <= args.max_api_calls <= 88:
        parser.error('API call limit must be 1–88')
    if args.output.exists():
        parser.error('Output exists; choose another --output to preserve previous evidence')
    cases, snapshot = make_cases()
    database = ROOT / 'data/processed/olist.sqlite'
    model = RecordingModel(OpenAIModel(ModelConfig.from_env()), args.max_api_calls)
    modes = ['static', 'rag'] if args.mode == 'both' else [args.mode]
    retriever = None
    if 'rag' in modes:
        from app.rag.embeddings import LocalEmbedder
        from app.rag.retrieval import Retriever
        retriever = Retriever(LocalEmbedder())
    report = dict(started_at_utc=datetime.now(timezone.utc).isoformat(), model=model.name, modes=modes,
        max_api_calls=args.max_api_calls, complete=False, results=[], cases=cases,
        database_sha256=file_hash(database), reference_sha256=file_hash(ROOT / 'evaluation/baseline_expected.json'),
        method='11 development reference questions with explicit output contracts, two contexts, one sample each; not held-out accuracy. No reference SQL or values sent to model.',
        source_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['app/text_to_sql', 'app/rag', 'knowledge_base'] for p in (ROOT / folder).glob('*') if p.is_file()},
        sql_timeout_seconds=30, explanation_review='Pending separate semantic review; structural validity is not answer quality',
        excluded_calls='Connectivity smoke tests and other requests made outside this runner are not included.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save(report, args.output)
    stop = False
    try:
        for case in cases:
            for mode in modes:
                if model.calls >= args.max_api_calls:
                    stop = True
                    break
                before, output_start = model.calls, len(model.outputs)
                response = answer_question(case['question'], database, model, QueryLimits(timeout_seconds=30), retriever=retriever if mode == 'rag' else None)
                executed = response.result is not None
                actual = response.result.rows if executed else []
                errors = compare_unordered(actual, snapshot['questions'][case['id']]['rows'], case['group_keys'])
                row = dict(id=case['id'], mode=mode, executed=executed,
                    result_match=executed and not response.result.truncated and not errors,
                    comparison_errors=errors[:30], api_calls=model.calls-before,
                    explanation_validated=any(t.get('status') == 'evidence_references_validated' for t in response.trace),
                    explanation_fallback=any(t.get('status') == 'deterministic_fallback' for t in response.trace),
                    response=response.model_dump(), model_outputs=model.outputs[output_start:])
                report['results'].append(row)
                save(report, args.output)
                print(f"{case['id']} {mode}: status={response.status}, exact_match={row['result_match']}, explanation_validated={row['explanation_validated']}, calls={row['api_calls']}", flush=True)
                if any('Model request failed' in t.get('error', '') for t in response.trace):
                    report['stop_reason'] = 'Provider failure; stopped rather than repeatedly spending/retrying'
                    stop = True
                    break
            if stop:
                break
    finally:
        report['complete'] = len(report['results']) == len(cases)*len(modes)
        report['database_unchanged'] = file_hash(database) == report['database_sha256']
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(report, args.output)
    print(json.dumps(report['summaries'], indent=2))
    if not report['complete'] or not report['database_unchanged']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
