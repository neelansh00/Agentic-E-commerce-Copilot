"""Read-only publication audit. Reports locations, never matching secret values."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'provider_token': re.compile(rb'(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{16,})'),
    'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'credential_url': re.compile(rb'(?i)(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|https?)://[^\s/:]+:[^\s/@]+@'),
    'literal_secret_assignment': re.compile(rb'''(?im)^\s*["']?(?:OPENAI_API_KEY|api_key|password|access_token|client_secret)["']?\s*[:=]\s*["'][^"'\r\n]{8,}["']'''),
}
TEXT = {'.py','.json','.yaml','.yml','.toml','.bat','.md','.txt','.log','.ipynb','.sql','.ini','.cfg','.sh','.ps1'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Choose a fresh output path.')
    # Compare against local configured secrets without displaying their values or hashes.
    known=[]
    for env in ROOT.glob('.env*'):
        if env.name == '.env.example': continue
        for key,value in dotenv_values(env).items():
            if value and len(value)>=8 and re.search('KEY|TOKEN|PASSWORD|SECRET',key,re.I):
                known.append(value.encode())
    def findings(data):
        result=[]
        for label,pattern in PATTERNS.items():
            for match in pattern.finditer(data):
                result.append(dict(rule=label,line=data[:match.start()].count(b'\n')+1))
        for secret in known:
            position=data.find(secret)
            if position>=0: result.append(dict(rule='exact_local_secret',line=data[:position].count(b'\n')+1))
        return result
    objects=git('rev-list','--objects','--all').decode().splitlines()
    history=[]; sizes=[]; blob_count=0
    process=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    for row in objects:
        oid,_,path=row.partition(' ')
        process.stdin.write((oid+'\n').encode()); process.stdin.flush()
        header=process.stdout.readline().decode().split()
        size=int(header[2]); data=process.stdout.read(size); process.stdout.read(1)
        if header[1]!='blob': continue
        blob_count+=1; sizes.append(dict(path=path,bytes=size))
        for hit in findings(data): history.append(dict(object=oid,path=path,**hit))
    process.stdin.close(); process.wait()
    working=[]; local_paths=[]
    tracked=git('ls-files','-z').decode().split('\0')[:-1]
    untracked=git('ls-files','--others','--exclude-standard','-z').decode().split('\0')[:-1]
    for path in sorted(set(tracked+untracked)):
        target=ROOT/path
        if not target.is_file(): continue
        data=target.read_bytes()
        for hit in findings(data): working.append(dict(path=path,**hit))
        if target.suffix.lower() in TEXT:
            for match in re.finditer(rb'[A-Za-z]:[\\/]+(?:Users|[^\s"\r\n]*Desktop)[\\/]',data):
                local_paths.append(dict(path=path,line=data[:match.start()].count(b'\n')+1))
    excluded=[]
    for name in ['.env','.streamlit/secrets.toml','.venv/placeholder','data/raw/placeholder.csv',
                 'data/processed/olist.sqlite','data/models/placeholder','dist/runtime-assets.zip']:
        result=subprocess.run(['git','check-ignore','--quiet',name],cwd=ROOT)
        excluded.append(dict(path=name,ignored=result.returncode==0))
    forbidden=[p for p in tracked if p=='.env' or p.endswith('secrets.toml') or p.startswith(('.venv/','data/raw/','data/processed/','data/models/','dist/')) or p.endswith(('.sqlite','.zip','.pyc'))]
    # Inspect ignored first-party text too, while excluding third-party installations,
    # source data, model binaries and generated asset/clone directories.
    ignored_findings=[]
    for directory,children,files in os.walk(ROOT):
        children[:]=[n for n in children if n not in {'.git','.venv','venv','env','data','dist','__pycache__'}]
        for name in files:
            path=Path(directory)/name
            relative=path.relative_to(ROOT).as_posix()
            if relative in tracked or relative in untracked: continue
            if path.suffix.lower() not in TEXT and not name.startswith('.env'): continue
            for hit in findings(path.read_bytes()): ignored_findings.append(dict(path=relative,**hit))
    report=dict(head=git('rev-parse','HEAD').decode().strip(),commits=int(git('rev-list','--count','--all')),
                history_blobs=blob_count,history_candidates=history,working_candidates=working,
                local_path_locations=local_paths,tracked_files=len(tracked),tracked_forbidden_files=forbidden,
                largest_history_blobs=sorted(sizes,key=lambda x:x['bytes'],reverse=True)[:10],
                exclusions=excluded,ignored_local_candidates=ignored_findings,
                method='All reachable Git blobs and tracked/untracked publishing files scanned with token/credential patterns plus exact local .env secret comparison. Ignored first-party text scanned separately; dependencies, original data, binary assets and dist excluded. Candidate matches require review; no secret values emitted. Not a proof of absence of every possible credential.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
