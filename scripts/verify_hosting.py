"""Replay hosted entry point from a clean checkout with an exported bundle; no API calls."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.deployment import digest, install_bundle

SMOKE = '''
import json
from streamlit.testing.v1 import AppTest
flows=[]
for mode,question in [('Scripted demo','How many orders are there?'),('Local tools','What does late delivery mean?'),('Local tools','Are late deliveries associated with lower ratings?')]:
    at=AppTest.from_file('streamlit_app.py',default_timeout=180).run()
    assert not at.exception, [e.message for e in at.exception]
    at.radio[0].set_value(mode).run()
    at.chat_input[0].set_value(question).run()
    result=at.session_state['conversation'][-1]['response']
    assert not at.exception and result['status']=='ok', result['answer']
    if mode=='Scripted demo': assert result['result']['rows']==[{'total_orders':99441}]
    if 'associated' in question: assert result['analysis']['late_orders']>0 and result['analysis']['on_time_orders']>0
    if 'mean?' in question: assert any(s['heading']=='Delivery eligibility, lateness and duration' for s in result['sources'])
    flows.append(dict(mode=mode,question=question,status=result['status']))
print(json.dumps(flows))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'dist/runtime-assets.zip')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/generated/hosting_verification.json')
    args=parser.parse_args()
    if args.output.exists(): parser.error('Choose a fresh output report.')
    with tempfile.TemporaryDirectory(prefix='hosted-smoke-') as temporary:
        staging=Path(temporary)
        for directory in ['app','knowledge_base']:
            shutil.copytree(ROOT/directory,staging/directory,ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT/'streamlit_app.py',staging/'streamlit_app.py')
        checksum=digest(args.bundle)
        install_bundle(args.bundle,checksum,staging)
        before=digest(staging/'data/processed/olist.sqlite')
        completed=subprocess.run([sys.executable,'-c',SMOKE],cwd=staging,capture_output=True,text=True)
        report=dict(bundle_sha256=checksum,bundle_bytes=args.bundle.stat().st_size,
                    passed=completed.returncode==0,stdout=completed.stdout,stderr=completed.stderr,
                    database_unchanged=before==digest(staging/'data/processed/olist.sqlite'),
                    model_api_calls=0,scope='Clean temporary checkout, real bundle and hosted Streamlit entry point on local Windows; not a deployed cloud/Linux test.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    if not report['passed'] or not report['database_unchanged']: raise SystemExit(1)


if __name__=='__main__': main()
