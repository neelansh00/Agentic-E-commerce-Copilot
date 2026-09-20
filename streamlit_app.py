"""Cloud entry point; the local app/main.py entry point remains available."""
import os
import runpy
from pathlib import Path
import streamlit as st
from app.deployment import ensure_assets

# Streamlit Cloud uses secrets; Railway uses environment variables. Never log either.
try:
    for name in ('OPENAI_API_KEY', 'OPENAI_MODEL', 'ASSET_BUNDLE_URL', 'ASSET_BUNDLE_SHA256'):
        if name in st.secrets:
            os.environ.setdefault(name, str(st.secrets[name]))
except FileNotFoundError:
    pass


@st.cache_resource
def prepare_assets():
    ensure_assets()
    return True


try:
    prepare_assets()
except ValueError as error:
    st.error(str(error))
    st.stop()
runpy.run_path(str(Path(__file__).parent / 'app/main.py'), run_name='__main__')
