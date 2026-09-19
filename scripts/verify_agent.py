"""Reproduce Phase 5 tests, routing and complete-data tool integration; optional live smoke."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.agent.routing import route_question
from app.agent.runner import run_agent
from app.database.ingest import file_hash
from app.rag.embeddings import LocalEmbedder
from app.rag.retrieval import Retriever
from app.text_to_sql.config import ModelConfig
from app.text_to_sql.model import OpenAIModel, ScriptedModel
from app.analytics.reporting import write_project_metrics


def csv_histogram():
    """Independent raw-CSV population/selection, not SQL-view reuse."""
    def rows(name):
        with (ROOT/'data/raw'/name).open(encoding='utf-8', newline='') as stream:
            yield from csv.DictReader(stream)
    orders = {r['order_id']: r for r in rows('olist_orders_dataset.csv')}
    chosen = {}
    for r in rows('olist_order_reviews_dataset.csv'):
        order = orders[r['order_id']]
        if r['review_creation_date'] < order['order_purchase_timestamp'] or r['review_answer_timestamp'] < r['review_creation_date']:
            continue
        key = (r['review_answer_timestamp'], r['review_creation_date'], r['review_id'])
        if r['order_id'] not in chosen or key > chosen[r['order_id']][0]:
            chosen[r['order_id']] = (key, int(r['review_score']))
    counts = Counter()
    for oid, r in orders.items():
        actual, estimated = r['order_delivered_customer_date'], r['order_estimated_delivery_date']
        if r['order_status'] == 'delivered' and actual and estimated and actual >= r['order_purchase_timestamp'] and oid in chosen:
            counts[(int(actual > estimated), chosen[oid][1])] += 1
    return [dict(is_late=g, review_score=s, n=n) for (g,s),n in sorted(counts.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Two bounded live SQL smoke questions (up to eight API calls)')
    parser.add_argument('--live-report', type=Path, help='Attach preserved live smoke evidence instead of making new API calls; provenance is recorded')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/generated/phase5_verification.json')
    args = parser.parse_args()
    if args.live_report:
        args.live_report = args.live_report.resolve()
    if args.live and args.live_report:
        parser.error('Choose new live calls or preserved evidence, not both.')
    if args.output.exists():
        parser.error('Preserve prior evidence: choose a fresh --output path.')
    started = time.perf_counter()
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=ROOT, capture_output=True, text=True)
    cases = json.loads((ROOT/'evaluation/phase5_routing.json').read_text(encoding='utf-8'))
    routing = [dict(case=c, actual=route_question(c['question']).model_dump(), passed=route_question(c['question']).tools==c['tools'] and route_question(c['question']).operation==c['operation']) for c in cases]
    database = ROOT/'data/processed/olist.sqlite'
    before = file_hash(database)
    retriever = Retriever(LocalEmbedder())
    results = []
    for question in ['What does late delivery mean?', 'Are late deliveries associated with lower ratings?', 'Using business definitions, are late deliveries associated with lower ratings?']:
        response = run_agent(question, database, retriever=retriever)
        results.append(dict(question=question, response=response.model_dump()))
    oracle = csv_histogram()
    histogram_match = all(r['response']['result'] and r['response']['result']['rows']==oracle for r in results[1:])
    model = ScriptedModel([dict(action='query',sql='SELECT COUNT(*) AS total_orders FROM orders',message='',assumptions=[]),dict(claims=[dict(label='Orders',row_index=0,column='total_orders')],caveats=[])])
    scripted = run_agent('How many orders are there?', database, model)
    live = []
    if args.live_report:
        live = json.loads(args.live_report.read_text(encoding='utf-8'))['live_smoke']
        if len(live) != 2:
            parser.error('Expected two preserved live smoke cases.')
    if args.live:
        model = OpenAIModel(ModelConfig.from_env())
        expected = json.loads((ROOT/'evaluation/baseline_expected.json').read_text(encoding='utf-8'))['questions']['overview']['rows'][0]
        for question, column in [('How many orders are there? Return one column named total_orders.', 'total_orders'), ('What is total revenue in integer cents? Return one column named revenue_cents.', 'revenue_cents')]:
            response = run_agent(question, database, model, retriever)
            match = bool(response.result and response.result.rows == [{column: expected[column]}] and not response.result.truncated)
            live.append(dict(question=question, response=response.model_dump(), reference_match=match))
    report = dict(tests_passed=tests.returncode==0, test_output=tests.stdout+tests.stderr, routing=routing,
                  tool_results=results, histogram_matches_independent_csv=histogram_match,
                  scripted_sql=scripted.model_dump(), live_smoke=live, database_unchanged=file_hash(database)==before,
                  elapsed_seconds=round(time.perf_counter()-started,3),
                  method='Same-author development routing cases; deterministic arithmetic and local RAG integration; scripted SQL is not model accuracy. Optional two-question live smoke is not the full benchmark.')
    report['live_evidence_origin'] = dict(path=str(args.live_report.relative_to(ROOT)), sha256=file_hash(args.live_report)) if args.live_report else ('new calls' if args.live else 'none')
    report['source_hashes'] = {str(p.relative_to(ROOT)): file_hash(p) for folder in ['app/agent', 'app/tools'] for p in (ROOT/folder).glob('*.py')}
    report['all_passed'] = (report['tests_passed'] and all(r['passed'] for r in routing) and histogram_match and
        all(r['response']['status']=='ok' for r in results) and scripted.status=='ok' and report['database_unchanged'] and all(r['reference_match'] for r in live))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    write_project_metrics(ROOT)
    print(json.dumps({k:v for k,v in report.items() if k not in ['test_output','routing','tool_results','scripted_sql','live_smoke']},indent=2))
    if not report['all_passed']:
        print(tests.stderr[-2000:])
        print(json.dumps([r for r in routing if not r['passed']],indent=2))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
