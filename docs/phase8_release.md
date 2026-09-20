# Phase 8: packaging, verification and portfolio handoff

Phase 8 adds a Dockerfile, Compose configuration, an allowlisted image build context, an integrated setup/demo/troubleshooting guide, grounded resume examples and interview explanations of packaging choices. It updates automatic project metrics from the new local verification artifact. No routing, metric, SQL generation, RAG or answer behavior changed.

## Verification

| Check | Observed result |
|---|---|
| Installed dependency consistency (`pip check`) | Passed; no broken requirements |
| Complete offline suite | 137/137 passed |
| Real-data Streamlit integration | 3/3 passed: scripted count, local definition, delivery/review comparison |
| Database hash before/after integration | Unchanged |
| Compose syntax (`docker compose config --quiet`) | Passed |
| Python source compilation (`compileall`) | Passed for app, scripts and tests |
| Linux image build and container runtime | Blocked: Docker Desktop Linux engine unavailable; not verified |
| New model API requests | None |

The [raw local verification](generated/phase8_local_verification.json) records test output, exact responses, evidence and UI source hashes. It was produced with:

```powershell
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe scripts/verify_ui.py --output docs/generated/phase8_local_verification.json
docker compose config --quiet
```

Choose a new report filename when reproducing; the verifier refuses to overwrite prior evidence. Offline tests use controlled fixtures; three additional UI flows use the supplied database and actual local embeddings. None measures new live generation quality. The automatic metrics writer reads this artifact, preserving earlier phase results separately.

Docker CLI 28.3.0 was installed, but `docker version` could not reach `dockerDesktopLinuxEngine`. Starting Docker Desktop (including `docker desktop start`) did not produce a running engine; `docker desktop status` reported that status could not be retrieved. An explicitly permitted `docker build -t olist-copilot:phase8 .` failed because the engine pipe was absent. This is an environment blocker, not a successful build. Once the engine is working, run the Docker guide, confirm a healthy service, and repeat the three local UI flows before marking container verification complete.

## Packaging scope

The image uses Python 3.12 slim and pinned direct dependencies. It copies only runtime code, definitions and Streamlit configuration. Compose binds the UI to localhost, passes the two optional model settings and mounts prepared data read-only. The application runs as UID 10001. HTTP health checking is provided. Downloading weights and ingesting CSVs remain explicit local preparation steps.

The base image and transitive dependencies are not digest/hash locked. Cross-platform installation and bind-mount behavior require a successful container smoke test before claiming container portability. No authentication, cloud deployment, migration service or production monitoring was added.

## Known accuracy limitations retained

The frozen Phase 7 live result remains **47/50 tasks correct**, **28/30 SQL result matches** and **48/50 tool selections correct**. Broad follow-up keywords falsely reject two seller questions. A category payment-revenue question can silently become item sales during repair; item sales is not a valid substitute without user agreement. Explanation coverage can be incomplete. These are substantive defects, not packaging warnings. See [failure analysis and controlled experiments](generated/phase7_report.md).

This phase does not declare the application universally reliable or production-ready. A follow-up correctness pass should preserve requested metric intent, narrow follow-up detection, add general regression cases and rerun the frozen benchmark plus held-out paraphrases. Do not reuse the earlier eleven-question 11/11 result as if it described the broader fifty-question run.

## Reviewer path

1. [Setup and five-minute demo](demo_guide.md).
2. [Data model](data_model.md) and [business contract](../knowledge_base/metrics.md).
3. [Agent workflow](phase5_agent.md) and [UI/screenshot evidence](phase6_ui.md).
4. [Evaluation methodology](phase7_evaluation.md) and preserved results.
5. [Interview notes](interview_notes.md) and [measured metrics](project_metrics.md).
