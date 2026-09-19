"""Run the offline project end to end, stopping on the first failed command."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-name', default='integration_report')
    parser.add_argument('--rag-only', action='store_true', help='Recheck RAG and all unit tests against the existing verified database')
    args = parser.parse_args()
    if not args.report_name.replace('_', '').isalnum():
        parser.error('Use an alphanumeric report name with optional underscores')
    commands = [
        ['-m', 'pip', 'check'],
        ['-m', 'compileall', '-q', 'app', 'scripts', 'tests'],
        ['scripts/inspect_dataset.py'],
        ['scripts/load_database.py'],
        ['scripts/verify_database.py'],
        ['scripts/run_baseline.py'],
        ['scripts/verify_text_to_sql.py'],
        ['scripts/ask.py', '--demo', 'count', '--json'],
        ['scripts/ask.py', '--demo', 'cancellation', '--json'],
        ['scripts/build_knowledge_index.py'],
        ['scripts/verify_rag.py'],
        ['scripts/ask.py', '--define', 'What does late delivery mean?', '--json'],
        ['scripts/ask.py', '--demo', 'cancellation', '--rag', '--json'],
        ['-m', 'unittest', 'discover', '-s', 'tests', '-v'],
    ]
    if args.rag_only:
        commands = commands[:2] + commands[9:]
    report = {'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'rag and all unit tests' if args.rag_only else 'all implemented phases',
              'mode': 'offline only; no model API calls', 'steps': [], 'all_passed': False}
    output = ROOT / 'docs/generated'
    output.mkdir(parents=True, exist_ok=True)
    for command in commands:
        print('RUN ' + ' '.join(command), flush=True)
        start = time.perf_counter()
        try:
            process = subprocess.run([sys.executable, *command], cwd=ROOT,
                                     capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
            result = {'command': command, 'exit_code': process.returncode,
                      'elapsed_seconds': round(time.perf_counter()-start, 3),
                      'stdout_tail': process.stdout[-2500:], 'stderr_tail': process.stderr[-2500:]}
        except subprocess.TimeoutExpired:
            result = {'command': command, 'exit_code': -1, 'error': '600-second integration step timeout'}
        report['steps'].append(result)
        print(f"{'PASS' if result['exit_code'] == 0 else 'FAIL'} {' '.join(command)}", flush=True)
        if result['exit_code'] != 0:
            break
    report['all_passed'] = len(report['steps']) == len(commands) and all(s['exit_code'] == 0 for s in report['steps'])
    report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    (output / f'{args.report_name}.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    lines = ['# Offline end-to-end project check', '', f"All passed: **{report['all_passed']}**.", '',
             ('Rechecked RAG and all unit tests against the existing verified database.' if args.rag_only else 'Rebuilt the database from the supplied archive and ran existing phases together.') + ' This does not verify live model behavior or prove the absence of all possible bugs.', '',
             '| Command | Exit code | Seconds |', '|---|---:|---:|']
    lines += [f"| `{' '.join(s['command'])}` | {s['exit_code']} | {s.get('elapsed_seconds', 'timeout')} |" for s in report['steps']]
    (output / f'{args.report_name}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"All passed: {report['all_passed']}", flush=True)
    if not report['all_passed']:
        print(json.dumps(report['steps'][-1], indent=2))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
