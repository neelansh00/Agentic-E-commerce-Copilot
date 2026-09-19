"""Full offline suite plus real-data Streamlit AppTest flows; optional one live question."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from streamlit.testing.v1 import AppTest
from app.database.ingest import file_hash
from app.analytics.reporting import write_project_metrics


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='One order-count question through the UI using the configured model (at most four model calls)')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/generated/phase6_verification.json')
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Choose a fresh output path; preserved evidence is not overwritten.')
    tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True)
    count=re.search(r'Ran (\d+) tests',tests.stderr)
    before=file_hash(ROOT/'data/processed/olist.sqlite')
    reference=json.loads((ROOT/'evaluation/baseline_expected.json').read_text(encoding='utf-8'))['questions']
    flows=[]
    for mode, question in [('Scripted demo','How many orders are there?'),('Local tools','What does late delivery mean?'),('Local tools','Are late deliveries associated with lower ratings?')] + ([('Live SQL','How many orders are there? Return one column named total_orders.')] if args.live else []):
        at=AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=180).run()
        at.radio[0].set_value(mode).run()
        at.chat_input[0].set_value(question).run()
        result=at.session_state['conversation'][-1]['response'] if at.session_state['conversation'] else None
        errors=[e.message for e in at.exception]
        passed=not errors and result is not None and result['status']=='ok'
        if result and 'orders are there' in question:
            passed=passed and result['result']['rows']==[dict(total_orders=reference['overview']['rows'][0]['total_orders'])]
        elif result and 'associated' in question:
            groups={r['delivery_group']:r for r in reference['late_reviews']['rows']}
            for group in ['late','on_time']:
                passed=passed and result['analysis'][group+'_orders']==groups[group]['reviewed_orders'] and abs(result['analysis'][group+'_mean']-groups[group]['mean_review_score'])<.000002
        elif result:
            passed=passed and any(s['heading']=='Delivery eligibility, lateness and duration' for s in result['sources'])
        at.run()
        preserved=result==at.session_state['conversation'][-1]['response'] if result else False
        flows.append(dict(mode=mode,question=question,response=result,exceptions=errors,rerun_preserves_answer=preserved,passed=bool(passed and preserved)))
    report=dict(offline_tests=int(count.group(1)) if count else None,tests_passed=tests.returncode==0,test_output=tests.stdout+tests.stderr,
                flows=flows,database_unchanged=before==file_hash(ROOT/'data/processed/olist.sqlite'),
                method='Streamlit AppTest using the real local database and embeddings. Scripted demo is not model-generated SQL. Optional single live flow is an integration smoke, not an accuracy benchmark.',
                source_hashes={str(p.relative_to(ROOT)):file_hash(p) for p in [ROOT/'app/main.py',*(ROOT/'app/ui').glob('*.py')]})
    report['all_passed']=report['tests_passed'] and report['database_unchanged'] and all(f['passed'] for f in flows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    write_project_metrics(ROOT)
    print(json.dumps({k:v for k,v in report.items() if k not in ['flows','test_output','source_hashes']},indent=2))
    if not report['all_passed']:
        print(tests.stderr[-2000:])
        raise SystemExit(1)


if __name__=='__main__':
    main()
