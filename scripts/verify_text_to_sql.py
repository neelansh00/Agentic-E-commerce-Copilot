"""Offline integration checks using recorded reference SQL, never model-generated SQL."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.analytics.baseline import QUERIES, query_sql
from app.analytics.reference import compare_rows
from app.analytics.reporting import write_project_metrics
from app.database.ingest import file_hash
from app.text_to_sql.config import QueryLimits
from app.text_to_sql.contracts import SQLPlan
from app.text_to_sql.pipeline import answer_question
from app.text_to_sql.schema import retrieve_schema, TABLES


class ReferenceReplay:
    name = 'offline-reference-sql-replay-not-an-llm'
    def __init__(self, sql):
        self.sql, self.usage = sql, []

    def generate(self, messages, output_type):
        if output_type is SQLPlan:
            return output_type(action='query', sql=self.sql, message='', assumptions=[])
        # Evidence-only explanation fallback is part of the tested integration.
        return output_type(claims=[], caveats=[])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / 'data/processed/olist.sqlite')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs/generated')
    args = parser.parse_args()
    start = time.perf_counter()
    expected_path = ROOT / 'evaluation/baseline_expected.json'
    expected = json.loads(expected_path.read_text(encoding='utf-8'))
    results = {}
    before = file_hash(args.database)
    for name, spec in QUERIES.items():
        sql = query_sql(name)
        for parameter, value in spec.parameters.items():
            sql = sql.replace(':' + parameter, str(value))  # Trusted integer reference parameters only.
        tables, _ = retrieve_schema(spec.question)
        response = answer_question(spec.question, args.database, ReferenceReplay(sql),
                                   QueryLimits(timeout_seconds=30))
        rows = response.result.rows if response.result else []
        errors = compare_rows(rows, expected['questions'][name]['rows'])
        results[name] = {'status': response.status, 'expected_result_match': not errors and response.status == 'ok',
                         'errors': errors, 'initial_schema_tables': tables,
                         'expected_relevant_tables': list(spec.tables),
                         'retrieval_contains_expected': set(spec.tables) <= set(tables),
                         'result_rows': len(rows), 'elapsed_ms': response.elapsed_ms,
                         'execution_ms': response.result.execution_ms if response.result else None,
                         'trace': response.trace}
        print(f"{name}: {response.status}, result_match={results[name]['expected_result_match']}", flush=True)
    unchanged = before == file_hash(args.database)
    report = {'mode': 'offline reference SQL replay; NOT LLM generation or accuracy',
              'model_api_calls': 0, 'database_sha256': before, 'database_unchanged': unchanged,
              'expected_snapshot_sha256': file_hash(expected_path), 'results': results,
              'all_passed': unchanged and all(r['expected_result_match'] and r['retrieval_contains_expected'] for r in results.values()),
              'elapsed_seconds': round(time.perf_counter() - start, 3),
              'live_model_evaluation': 'not run; user requested offline only'}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'text_to_sql_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    lines = ['# Phase 3 offline integration evidence', '',
             '**This replays Phase 2 reference SQL. It does not measure natural-language SQL generation or model accuracy.**', '',
             f"All checks passed: {report['all_passed']}. Database unchanged: {unchanged}. Model API calls: 0.", '',
             '| Reference | Result matches | Required schema retrieved | Initial tables | Rows |', '|---|---|---|---:|---:|']
    for name, r in results.items():
        lines.append(f"| {name} | {r['expected_result_match']} | {r['retrieval_contains_expected']} | {len(r['initial_schema_tables'])}/{len(TABLES)} | {r['result_rows']} |")
    lines += ['', 'The full JSON records timings, validation/retry traces and source fingerprints. Shared Phase 2 CTEs reference extra tables, so some replays exercise the single bounded schema-expansion path.', '',
              'Validation, SQLite authorization and actual execution are real. The SQL provider is scripted. Semantic SQL correctness for new questions and model explanation quality remain unmeasured.', '',
              'Unit tests separately cover forbidden operations, retry exhaustion, repair, evidence failures, time/output limits, provider errors and schema matching.', '']
    (args.output_dir / 'text_to_sql_report.md').write_text('\n'.join(lines), encoding='utf-8')
    if args.output_dir.resolve() == (ROOT / 'docs/generated').resolve():
        write_project_metrics(ROOT)
    print(f"All passed: {report['all_passed']}; elapsed={report['elapsed_seconds']}s")
    if not report['all_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
