"""Execute fixed analytics SQL, cross-check raw CSVs, and optionally freeze ground truth."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.analytics.baseline import METRIC_VERSION, QUERIES, run_query
from app.analytics.reference import CsvReference, compare_rows
from app.analytics.reporting import markdown_report, write_project_metrics
from app.database.ingest import SOURCES, connect_readonly, file_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / 'data/processed/olist.sqlite')
    parser.add_argument('--raw-dir', type=Path, default=ROOT / 'data/raw')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs/generated')
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'evaluation/baseline_expected.json')
    parser.add_argument('--freeze', action='store_true', help='Explicitly create/replace expected results after every independent comparison passes.')
    args = parser.parse_args()
    start = time.perf_counter()
    source_hashes = {filename: file_hash(args.raw_dir / filename) for _, filename, _ in SOURCES}
    # Normalize text newlines so Git's CRLF/LF checkout settings do not invalidate the contract.
    metric_text = (ROOT / 'knowledge_base/metrics.md').read_text(encoding='utf-8')
    metric_hash = hashlib.sha256(metric_text.encode('utf-8')).hexdigest()
    reference = CsvReference(args.raw_dir)
    db = connect_readonly(args.database)
    results, expected = {}, {}
    try:
        for name, spec in QUERIES.items():
            truth = reference.result(name, spec.parameters)
            expected[name] = {'question': spec.question, 'expected_relevant_tables': list(spec.tables),
                              'expected_tools': ['sql'], 'expected_interpretation': spec.interpretation,
                              'parameters': spec.parameters, 'reference_sql': f'app/analytics/sql/{name}.sql',
                              'sql_prefix': 'app/analytics/sql/order_facts.sql', 'rows': truth}
            result = {'question': spec.question, 'interpretation': spec.interpretation,
                      'metric_relevant_tables': list(spec.tables)}
            try:
                result.update(run_query(db, name))
                errors = compare_rows(result['rows'], truth)
                result.update(execution_ok=True, reference_match=not errors, errors=errors)
                expected[name]['assembled_sql_sha256'] = hashlib.sha256(result['sql'].encode()).hexdigest()
            except sqlite3.Error as exc:
                result.update(execution_ok=False, reference_match=False, errors=[str(exc)])
            results[name] = result
            print(f"{name}: execution={result['execution_ok']}, CSV agreement={result['reference_match']}", flush=True)
    finally:
        db.close()
    independent_pass = all(r['reference_match'] for r in results.values())
    candidate = {'metric_version': METRIC_VERSION, 'metric_contract_sha256': metric_hash,
                 'source_sha256': source_hashes, 'questions': expected}
    snapshot_errors = []
    # Do not freeze evidence if the source changed during independent verification.
    sources_stable = all(file_hash(args.raw_dir / filename) == digest for filename, digest in source_hashes.items())
    if not sources_stable:
        snapshot_errors.append('Source CSV changed during verification')
    if args.freeze and independent_pass and sources_stable:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        snapshot_status = 'created/refreshed explicitly'
    elif args.snapshot.exists():
        frozen = json.loads(args.snapshot.read_text(encoding='utf-8'))
        for key in ('metric_version', 'metric_contract_sha256', 'source_sha256'):
            if candidate[key] != frozen.get(key):
                snapshot_errors.append(f'{key} changed; review definitions/data before an explicit --freeze')
        if expected.keys() != frozen.get('questions', {}).keys():
            snapshot_errors.append('Question IDs changed')
        for name in expected.keys() & frozen.get('questions', {}).keys():
            saved = frozen['questions'][name]
            if {k: v for k, v in expected[name].items() if k != 'rows'} != {k: v for k, v in saved.items() if k != 'rows'}:
                snapshot_errors.append(f'{name}: reference SQL or question metadata changed')
            snapshot_errors += [f'{name}: {error}' for error in compare_rows(expected[name]['rows'], saved['rows'])]
        snapshot_status = 'matched' if not snapshot_errors else 'mismatch'
    else:
        snapshot_status = 'missing; use --freeze after reviewing results'
        snapshot_errors.append('No frozen ground truth')
    report = {'metric_version': METRIC_VERSION, 'metric_contract_sha256': metric_hash,
              'source_sha256': source_hashes, 'database_sha256': file_hash(args.database),
              'generated_at_utc': datetime.now(timezone.utc).isoformat(),
              'queries': results, 'snapshot_status': snapshot_status, 'snapshot_errors': snapshot_errors,
              'all_passed': independent_pass and not snapshot_errors,
              'elapsed_seconds': round(time.perf_counter() - start, 3)}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'baseline_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (args.output_dir / 'baseline_report.md').write_text(markdown_report(report), encoding='utf-8')
    if args.output_dir.resolve() == (ROOT / 'docs/generated').resolve():
        write_project_metrics(ROOT)
    print(f"All passed: {report['all_passed']}; snapshot: {snapshot_status}; elapsed: {report['elapsed_seconds']}s")
    if not report['all_passed']:
        print(json.dumps(snapshot_errors))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
