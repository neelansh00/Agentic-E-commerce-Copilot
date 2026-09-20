# Setup, demo and troubleshooting

## Fresh local setup

Use Python 3.12 (the verified minor version), a terminal in the repository root and the supplied Olist ZIP. Installation and the one-time model download require internet access. No API key is needed for local tools or tests.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe scripts/inspect_dataset.py
.venv/Scripts/python.exe scripts/load_database.py
.venv/Scripts/python.exe scripts/verify_database.py
.venv/Scripts/python.exe scripts/download_embedding_model.py
.venv/Scripts/python.exe scripts/build_knowledge_index.py
.venv/Scripts/python.exe -m streamlit run app/main.py
```

If several ZIPs exist, pass `--archive "your-file.zip"` to the inspection script. On macOS/Linux replace `.venv/Scripts/python.exe` with `.venv/bin/python`. Raw CSVs are never manually edited. Loading again replaces the generated database; indexing again rebuilds the generated index. Do not run either while investigating a historical benchmark. Setup audit/loading reports are regenerated; preserved Phase 7 live evidence is not.

Open http://127.0.0.1:8501. Stop with Ctrl+C. The default Local tools mode does not generate arbitrary SQL; it supports cited definitions and the global late-delivery/review comparison. Scripted demo replays a fixed count query and is explicitly labeled.

## Optional live SQL

1. Copy `.env.example` to `.env` **only if `.env` does not already exist**.
2. Edit `.env` locally and set `OPENAI_API_KEY` and `OPENAI_MODEL` to your own authorized key and a Responses structured-output-capable model. Do not paste or commit the key. The measured model snapshot is recorded in the evaluation artifacts; choosing another model requires a new evaluation.
3. Start the application and choose Live SQL in the sidebar. Live questions incur provider usage; the other modes remain local.
4. Ask “How many orders are there? Return one column named total_orders.” Inspect SQL Used and Data Preview; the supplied snapshot has 99,441 orders.
5. If the provider fails, inspect the sanitized error/trace and model configuration. Do not interpret a failed response as a zero value.

Never print `docker compose config` or the container environment when credentials are configured: interpolation can reveal them. Docker daemon administrators can inspect runtime environment variables; this is a local demo deployment, not secret management for a shared service.

## Five-minute interview demo

1. Explain the business problem: define the metric, query at the right grain, show evidence.
2. In Local tools, ask “What does late delivery mean?” Expand Sources / Business Definitions. Explain heading chunks, pinned local embeddings, cosine similarity and definition dependencies.
3. Ask “Are late deliveries associated with lower ratings?” Show the chart, SQL and two-by-five review histogram. Explain eligible deliveries, selected reviews and descriptive association, not causation or significance.
4. If configured, switch to Live SQL and ask “Which states generated the most revenue?” Show selected schema, SQL attempts, query output and constrained evidence captions. Model output can vary; check the result rather than promising a particular answer.
5. Show the Phase 7 report: 47/50 tasks correct, two false refusals and one silent metric substitution. Explain why execution, result correctness and explanation fidelity are different metrics.

Use the checked-in [screenshots](phase6_ui.md) if a presentation machine lacks data/model assets. Do not present scripted playback as live generation.

## Docker

First prepare `data/processed/olist.sqlite`, `data/models/bge-small-en-v1.5/` and `data/processed/knowledge_index/` using local setup above. Docker Desktop must have its Linux engine running. The image installs pinned direct dependencies and copies runtime source/definitions only; it excludes data, credentials, historical results and tests. The Python base tag and transitive dependencies are not fully locked, so this is a repeatable recipe, not a bit-identical build.

```powershell
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 30 copilot
```

Open http://127.0.0.1:8501. Stop any locally running Streamlit on that port first, or change the host side of the mapping to `127.0.0.1:8502:8501`. Compose reads the two optional settings from the host `.env`; it never copies that file into the image. With neither setting, local tools still work. Data is a read-only bind mount and the process runs as a non-root user. The health check tests HTTP availability; it does not prove model accuracy or asset readiness. Keep this unauthenticated demo bound to localhost.

```powershell
docker compose down
```

This stops/removes the service; it does not delete your host data. Rebuild the image after code/knowledge changes and rebuild the index after knowledge changes. Linux file permissions must allow UID 10001 to read mounted assets.

## Verification and common failures

```powershell
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe scripts/verify_ui.py --output docs/generated/my_local_verification.json
```

The last command runs the suite plus three real-data UI flows, requires prepared data/models, makes no model API calls and refuses to overwrite its output. A live evaluation is a separate, billable operation: follow [Phase 7 reproduction](phase7_evaluation.md), choose fresh output paths and preserve the frozen questions.

| Symptom | Action |
|---|---|
| Missing database | Run ingestion after extracting the supplied archive. |
| Missing weights/manifest | Run the explicit model-download script, then build the index. |
| Stale index or hash mismatch | Check whether knowledge/model files changed; rebuild from the intended version. Do not disable integrity checks. |
| Docker engine unavailable | Start Docker Desktop's Linux engine and check `docker version`. |
| Port already in use | Stop the previous app or choose another localhost host port. |
| SQL failure after repair limit | Read the trace, restate scope/metric, and retain the failure for evaluation. |
| Seller request unexpectedly refused | Known Phase 7 follow-up keyword false positive; report it rather than claiming arbitrary language support. |
| Payment revenue by category | No allocation policy exists. Do not accept substituted item sales as the requested metric. |

## Resume wording backed by evidence

- Built a single-agent e-commerce analytics copilot over 1.55 million source records across nine relational tables, with guarded SQL, local definition retrieval and inspectable evidence.
- Evaluated fifty development questions with independent CSV-backed SQL references: 28/30 SQL result matches and 48/50 tool-selection matches; documented routing and metric-substitution failures.
- Reduced input tokens by 17.54% in a ten-question schema-context comparison; retrieved-schema accuracy was 8/10 versus 9/10 with full schema, so no accuracy gain is claimed.

Choose two bullets, explain the denominators and use [generated project metrics](project_metrics.md) as the source. These are development results, not held-out accuracy, measured business impact or production reliability.
