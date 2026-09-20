# Exact Windows local-run guide

## Already configured on this PC

Your existing `.env`, `.venv`, raw files, SQLite database and embeddings do not need rebuilding. Double-click **`run_local.bat`** in the project folder. It changes to its own directory and runs the virtual environment's Python. Open **http://127.0.0.1:8501** (equivalently http://localhost:8501). Stop with Ctrl+C in its terminal.

Manual equivalent from the project folder:

```powershell
.venv\Scripts\python.exe -m streamlit run app/main.py
```

The remaining instructions are for a **fresh clone**, not a request to overwrite your working configuration.

## Prerequisites

- Python **3.12**, 64-bit, with `venv` and pip. This project is verified on Windows with Python 3.12.2.
- Git for cloning; internet access for installing dependencies and downloading the pinned embedding model.
- The original Olist ZIP described below. No Docker, PostgreSQL server, Node.js or cloud account is required.
- An OpenAI API key/model with access to Responses structured outputs only if using **Live SQL**. Offline tests, scripted SQL and local definition/statistical tools do not need an API key.

## 1. Clone and create the environment

Open PowerShell in the parent folder where you want the project:

```powershell
git clone https://github.com/neelansh00/Agentic-E-commerce-Copilot.git
cd Agentic-E-commerce-Copilot
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
```

If PowerShell blocks activation, no policy change is necessary: use `.venv\Scripts\python.exe` instead of `python` for every command below. If the `py` launcher is absent, use a verified Python 3.12 executable for `python -m venv .venv`. Check `python --version` after activation; a fresh machine must install Python first.

## 2. Optional live API configuration

Create `.env` in the **repository root**, beside `README.md`, only if it does not already exist:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Set the two existing variables locally:

```dotenv
OPENAI_API_KEY=<your-own-api-key>
OPENAI_MODEL=<a-model-you-have-access-to>
```

The preserved live evaluation used `gpt-4.1-mini-2025-04-14`; availability depends on your account. Another model may produce different results and is not covered by those measured results. Replace placeholders; do not include angle brackets in real values. Do not put the file inside `app/`, paste the real key into chat, or commit it. `.env` and Streamlit's real `secrets.toml` are ignored. Asset-bundle environment variables are for hosted deployment and are unnecessary for local use.

## 3. Obtain and extract the dataset

Raw data, the ZIP and SQLite files are **not included in GitHub**. Download **Brazilian E-Commerce Public Dataset by Olist** from [the original Kaggle dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), using Kaggle's Download option. Kaggle may require an account.

Place the downloaded ZIP in the **repository root**, next to `README.md`. Leave it zipped; the audit script extracts it. If it is the only ZIP in that folder:

```powershell
python scripts/inspect_dataset.py
```

With multiple ZIPs, explicitly name the supplied archive (replace the example filename with the actual one):

```powershell
python scripts/inspect_dataset.py --archive "archive (1).zip"
```

This extracts the nine supplied CSVs into `data/raw/` and writes reproducible audit reports. Do not manually edit CSVs. Ground-truth numbers apply to the supplied historical snapshot; a different dataset version may intentionally fail reference checks.

## 4. Initialize the database and local knowledge retrieval

```powershell
python scripts/load_database.py
python scripts/verify_database.py
python scripts/download_embedding_model.py
python scripts/build_knowledge_index.py
```

The database is **not initialized automatically** by the local UI. Ingestion creates `data/processed/olist.sqlite`. Re-running it replaces the generated database after validation; it does not append records. Close database viewers before rebuilding on Windows.

The model-download step requires network access once and uses the pinned public ONNX model. The index builder creates `data/processed/knowledge_index/` from `knowledge_base/`. Subsequent RAG inference is local and does not use the OpenAI API. Rebuild the index if knowledge documents change. Setup commands regenerate their setup/audit reports; they do not rerun or replace the preserved Phase 7 live evaluation.

## 5. Start the app

**Easiest Windows method:** double-click `run_local.bat` after completing setup. Activation is not needed for the batch launcher.

**Manual terminal method:**

```powershell
.venv\Scripts\python.exe -m streamlit run app/main.py
```

Open **http://127.0.0.1:8501**. `.streamlit/config.toml` binds the local app to `127.0.0.1`; Streamlit's default port is 8501. Headless mode may require you to open the address manually. Hosted `streamlit_app.py` and Railway settings are separate; they are not needed here.

## 6. Five representative questions

| Question | Mode | Expected tool path / behavior |
|---|---|---|
| How many orders are there? | Live SQL (or Scripted demo for a no-API check) | SQL; supplied snapshot has 99,441 orders. Scripted demo is fixed playback, not generation. |
| Which states generated the most revenue? Return customer_state and revenue_cents. | Live SQL | RAG + SQL; combines customer geography with order/payment metrics through the shared metric views. Inspect cents and the query's ordering. |
| What does late delivery mean? | Local tools | RAG only; cited delivery eligibility and lateness definition. |
| Are late deliveries associated with lower ratings? | Local tools | SQL + Python; descriptive late/on-time review comparison, no causal or significance claim. |
| Delete all orders. | Local tools | Safe read-only refusal; no SQL/RAG/Python tool is executed. |

Live generation varies and incurs API charges. Selecting Local tools for an arbitrary SQL request produces a mode/configuration message, not live SQL. Each question is independent: explicitly state scope rather than using follow-ups like “those sellers.”

## 7. Manual acceptance checklist

- [ ] Streamlit starts and shows the chat without a missing-database warning.
- [ ] Scripted count returns 99,441 for the supplied snapshot.
- [ ] A Live SQL count request succeeds using your configured API account.
- [ ] The live natural-language request has generated SQL and a visible result table.
- [ ] The definition request returns sources with document/line citations.
- [ ] The statistical request returns SQL evidence, group means and the descriptive comparison.
- [ ] The destructive request refuses without running a query.
- [ ] SQL Used, Data Preview, Sources / Business Definitions, Tool Trace and Execution Information expanders work.
- [ ] API errors or SQL failures are shown explicitly rather than as invented numbers.

## 8. Run tests yourself

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected verified result: **146 tests passed**. These tests are offline and use controlled fixtures; they do not need your dataset or API key. Full real-data UI verification requires the preparation above:

```powershell
.venv\Scripts\python.exe scripts/verify_ui.py --output docs/generated/my_local_check.json
```

That runs the suite plus three real-data UI flows without API calls. Choose a fresh output filename; existing evidence is intentionally not overwritten. To test the hosted entry point locally, first export assets with `scripts/export_runtime_assets.py`, then run `scripts/verify_hosting.py --output docs/generated/my_hosting_check.json`.

## 9. Project-specific troubleshooting

| Problem | Fix |
|---|---|
| Missing API key/model or setup failure in Live SQL | Put both settings in root `.env`, verify model access, restart the app. Local tools still work without an API key. Errors are sanitized; never print credentials. |
| `.env` appears correct but is ignored | Ensure it is named `.env`, not `.env.txt`, beside `README.md`; existing process environment variables take precedence over dotenv. |
| Dataset missing / multiple ZIPs | Place the Kaggle ZIP in the root and use `--archive` when necessary. |
| Database missing | Run inspection, ingestion and database verification in that order. The local UI does not load CSVs automatically. |
| Missing model, manifest or stale knowledge index | Run the download script, then the index builder. Do not disable integrity checks. |
| Wrong Python/environment or package import error | Use `.venv\Scripts\python.exe`, reinstall `-r requirements.txt`, then run `-m pip check`. Use Python 3.12. |
| Port 8501 occupied | Stop the previous Streamlit terminal with Ctrl+C, or run `.venv\Scripts\python.exe -m streamlit run app/main.py --server.port=8502` and open `http://127.0.0.1:8502`. |
| Seller request refused or category payment revenue changes metric | These are documented Phase 7 limitations. Check trace/metric wording; do not treat substituted item sales as payment revenue. |

The frozen development benchmark remains **47/50 task correctness**, **28/30 SQL execution/result matches** and **48/50 tool-selection matches**, not held-out or production accuracy. See [Phase 7 results](generated/phase7_report.md). Cloud deployment has not been performed; optional instructions are in [deployment.md](deployment.md).
