# Local use and managed deployment — no Docker required

## Run on your PC

After [initial setup](demo_guide.md), double-click `run_local.bat` on Windows, or run:

```powershell
.venv/Scripts/python.exe -m streamlit run app/main.py
```

Open http://127.0.0.1:8501. Your existing `.env`, database and local RAG index are used without rebuilding or downloading. Stop with Ctrl+C. Docker Desktop is unnecessary; the earlier Docker files have been removed.

## Prepare cloud assets once

Git excludes the database and embedding files. A fresh cloud checkout needs a separate runtime artifact:

```powershell
.venv/Scripts/python.exe scripts/export_runtime_assets.py
```

This creates `dist/runtime-assets.zip` and prints its SHA-256. The measured bundle is **140,602,729 bytes**, containing ten files: the database, model files/manifest and current index. It excludes `.env`, raw CSVs, caches and code. The exporter verifies model/index integrity and rejects source changes during packaging. It refuses to overwrite; use `--output dist/runtime-assets-v2.zip` for another version.

Upload the bundle to an HTTPS file host you control, such as a release asset or object-storage download endpoint. **This upload has not been performed.** Ensure you have the right to distribute the Olist/model artifacts to the intended audience. Use a direct file URL, not a preview page. Private storage can use a signed URL that must remain valid when the service restarts. Store the URL in platform secrets and keep the SHA-256 printed by export.

The hosted entry point, `streamlit_app.py`, downloads only from an owner-configured URL, verifies the complete bundle hash, rejects unsafe paths/links and oversized archives, and atomically publishes a fresh `data/` directory. Existing local data is never replaced. The RAG tool still validates its model/index/source hashes.

The analytics snapshot is disposable: a fresh instance can download it again, so no volume or hosted database is required for this demo. Cold starts include download time; restarting loses session-only chat history. Changing the bundle hash requires a fresh deployment filesystem, not replacing files beneath active queries. Rebuild the bundle after changing knowledge/model assets. Linux dependencies and resource limits must still be checked on the selected host.

## Streamlit Community Cloud

1. Push code to GitHub; leave ignored assets and credentials out of Git.
2. Host the exported bundle and retain its direct URL/hash.
3. Create an app from the repository/branch. Select **`streamlit_app.py`** as the main file and **Python 3.12** in Advanced settings.
4. Add root-level TOML in the app's Secrets settings:

```toml
ASSET_BUNDLE_URL = "https://your-host.example/runtime-assets.zip"
ASSET_BUNDLE_SHA256 = "the-64-character-hash-printed-by-export"
# Optional: omit these two for a local-tools-only hosted demo.
OPENAI_API_KEY = "your-key"
OPENAI_MODEL = "your-configured-model"
```

5. Deploy. `requirements.txt` provides dependencies. First app execution prepares the bundle; subsequent sessions reuse it.
6. Run the acceptance flows below before sharing the link.

See official [deployment settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) and [secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management). `.streamlit/secrets.toml` is ignored and must not be committed.

## Railway

1. Create a service from your GitHub repository. `railway.json` selects **Railpack**; `.python-version` selects Python 3.12. No project Dockerfile or local Docker installation is needed.
2. Set `ASSET_BUNDLE_URL` and `ASSET_BUNDLE_SHA256` as service variables. Optionally add `OPENAI_API_KEY` and `OPENAI_MODEL`.
3. Deploy. The configured start command, **`python scripts/start_hosted.py`**, prepares assets before launching Streamlit on `0.0.0.0` and Railway's `PORT`.
4. Generate a domain in the service's networking settings and run the acceptance flows.

The configured health path is `/_stcore/health`, with a 300-second startup timeout. HTTP health checks server availability, not analytics accuracy. Inspect download speed if preparation times out. Railway manages its own build/runtime infrastructure: see [configuration reference](https://docs.railway.com/config-as-code/reference) and [start commands](https://docs.railway.com/deployments/start-command). No Railway deployment or billing change was made here.

## Acceptance and verification

- Scripted demo: “How many orders are there?” returns **99,441** for the supplied snapshot.
- Local tools: “What does late delivery mean?” returns cited definitions.
- Local tools: “Are late deliveries associated with lower ratings?” returns the descriptive comparison with SQL evidence.
- Optional Live SQL: run one count query and inspect usage/evidence. This is billable and excluded from deployment smoke tests.

The app has no authentication or global spending controls. Enabling Live SQL on a public app lets visitors consume its configured API account. Omit API credentials for an unrestricted public demo, or restrict access through the hosting platform.

```powershell
.venv/Scripts/python.exe scripts/verify_ui.py --output docs/generated/my_local_release.json
.venv/Scripts/python.exe scripts/verify_hosting.py --output docs/generated/my_hosting_smoke.json
```

Use fresh output paths. Current results: **146 offline tests passed**, **3/3 local real-data UI flows passed**, and **3/3 hosted-entry flows passed after bundle restoration into a clean temporary checkout**. Database hashes were unchanged; no model API calls were made. Evidence: [local verification](generated/local_release_verification.json) and [hosting smoke](generated/hosting_verification.json).

The hosting test ran on this Windows PC. No actual cloud/Linux deployment is claimed. Provider deployment is still required to verify Linux wheels, download access, available memory and public endpoint behavior. Phase 7's three known correctness failures remain documented; deployment packaging does not improve model accuracy.

The Railway launcher was also run locally with `PORT=8502`; its health endpoint returned HTTP 200 / `ok`. A Windows process-launch quoting issue found during that check was fixed, and the test server was stopped afterward. See [launcher evidence](generated/hosted_launcher_verification.json).
