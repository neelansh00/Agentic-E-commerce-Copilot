# Publication audit and local verification

Audited on 20 September 2026. This record covers preparation; successful GitHub publication and remote HEAD agreement must be confirmed separately after authentication/push.

## Security and repository contents

- Scanned all 248 reachable historical blobs across the 13 pre-publication commits, plus tracked/untracked publishing files, using provider-token/private-key/credential-URL/literal-secret rules and exact comparison with configured local secret values. Also inspected ignored first-party text and the three UI screenshots. Dependency installations, source datasets and binary runtime assets are excluded from text scanning and from publication.
- **No actual credential found in Git history or publishing files.** The single candidate at `docs/deployment.md:40` is the explicit placeholder `your-key`, not a secret. A configured OpenAI credential exists in the ignored local `.env`; only its location, never its value, appears in the audit.
- `.env.example` has empty live settings and commented hosted placeholders. Application/deployment code reads environment variables or platform secrets. No `.env`, real Streamlit secrets, private key, local database, raw data, model cache, virtual environment or runtime ZIP is tracked. Git history contains no `.env`/`secrets.toml` file entries.
- Ignore rules cover these assets, Python caches, local logs, common IDE directories and private-key files. No Git LFS is necessary: the largest historical blob is 424,495 bytes, and the existing Git object store measured about 1.08 MiB before publication changes.
- Existing generated reports are intentional evidence, not API credential caches. They retain questions, SQL, results, token counts and sanitized failures. Phase 7 reports and the frozen benchmark were checked unchanged. A harmless historical traceback contains a local Windows path in `phase5_attempt2.json`; it is preserved as evidence and is not executable configuration.
- All README/docs local links were checked: no missing relative targets or absolute local filesystem links. Application paths are derived from the repository location. Three screenshots show analytics/evidence only, with no credentials.
- The original Kaggle ZIP, nine CSVs, SQLite database, weights and asset bundle stay local/ignored. Fresh users obtain the [original Kaggle dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) and run the documented audit/ingestion scripts. No dataset architecture changed.

Raw location-only audit evidence: [publication_security_audit.json](generated/publication_security_audit.json). The audit is a pattern/exact-match inspection with manual candidate review, not proof that every possible unknown credential format can be detected.

## Final local checks

| Check | Result |
|---|---|
| Full offline suite | 146 passed |
| Real-data local UI flows | 3/3 passed |
| Fresh staged hosted-entry flows | 3/3 passed |
| SQLite hash after both integration checks | Unchanged |
| `python -m pip check` | No broken requirements |
| `compileall` for app/scripts/tests/hosted entry | Passed |
| Local HTTP startup health | 200 / `ok`, tested on spare port 8503; documented default remains 8501 |
| Five manual-guide routes | Verified against current router |
| Existing configured lint/type tooling | None found; no new lint/type framework introduced |
| Model API calls in this verification | Zero |

Evidence: [local suite/UI report](generated/publication_local_verification.json), [hosted-entry report](generated/publication_hosting_verification.json), [HTTP startup report](generated/publication_startup_verification.json).

The test server was stopped after verification. The Windows launcher's pre-existing extra blank line is preserved. No product behavior, architecture or historical evaluation result was changed.

## Publishing and reproduction boundaries

The original branch was `master`, with no remotes. It was renamed to `main` without rewriting history, and the user-specified GitHub repository was configured as `origin`. Initial remote access rejected the saved GitHub credential; publication requires successful account authentication. No force push, squash, history deletion or repository reinitialization is authorized or needed.

The exact [local run guide](local_run_guide.md) covers fresh cloning, Python 3.12 environment creation/activation, dependency installation, `.env`, Kaggle ZIP placement, database/model/index preparation, batch/manual startup, representative tool paths, tests and troubleshooting.

The live development result remains **47/50 tasks correct**, **28/30 SQL execution/result matches**, and **48/50 tool-selection matches**. Two seller-routing false positives, metric substitution and incomplete explanation coverage remain known limits. No cloud deployment or new live evaluation has been performed.
