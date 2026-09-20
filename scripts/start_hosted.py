"""Railway launcher: prepare assets before starting the HTTP health endpoint."""
import os
from pathlib import Path
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.deployment import ensure_assets

if __name__ == '__main__':
    try:
        ensure_assets()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    port = int(os.environ.get('PORT', '8501'))
    if not 1 <= port <= 65535:
        raise SystemExit('PORT must be between 1 and 65535.')
    os.chdir(ROOT)
    command = [sys.executable, '-m', 'streamlit', 'run', 'streamlit_app.py',
               '--server.address=0.0.0.0', f'--server.port={port}']
    if os.name == 'nt':
        # Windows execv does not quote an executable path containing spaces.
        raise SystemExit(subprocess.call(command))
    os.execv(sys.executable, command)
