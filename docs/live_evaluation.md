# Live OpenAI evaluation before Phase 5

The API was configured locally and verified with `gpt-4.1-mini-2025-04-14`. The initial connectivity test generated `SELECT COUNT(*) AS total_orders FROM orders`, returned 99,441 and produced a validated evidence-reference explanation. The key stays in the ignored `.env` file and is not included in reports. Live requests send selected schema, business definitions, questions and bounded SQL results; database execution and embeddings stay local.

## Reproduction and boundaries

```powershell
.venv/Scripts/python.exe scripts/run_live_evaluation.py --live
```

This command makes billable API calls. It refuses to overwrite an existing report; use a new `--output` path for another run. It caps calls at 88, uses the existing maximum of three SQL attempts per question, and stops on provider failures. No unbounded outer retry loop exists. SQL execution uses a 30-second limit for this evaluation; the interactive default remains 15 seconds. API usage and partial results are checkpointed after each case. Offline tests never call this script with live access.

Eleven established reference questions are evaluated once with each of two contexts: the complete metric contract and the Phase 4 top-three retrieved excerpts. This is a preliminary paired comparison of context selection, not the planned no-definitions versus RAG experiment. Both arms have business definitions. Questions are drawn from the development references, not an unseen benchmark.

To make result comparison unambiguous, both arms receive the same explicit output-column names, units and rounding conventions. These specify the requested answer shape without providing SQL or expected values. Those additions also enter normal schema and knowledge retrieval, so these scores are not performance on the original short questions alone. Expected result values and reference SQL stay entirely inside the evaluator.

The result comparator ignores presentation row order, aligns group keys and uses the existing strict reference comparator. It requires all rows, columns, NULL semantics and monetary/count values to agree; floating metrics allow absolute error up to 0.000002. Top-N membership still matters. Complete results and SQL are saved for failure analysis rather than concealing mismatches behind an execution-success metric.

## Interpreting the measurements

- **Question execution rate:** questions that reached successful guarded SQL execution, including repaired attempts, divided by all attempted questions. This is not per-attempt execution rate.
- **Exact result accuracy:** questions whose entire result matches the reference, divided by all attempted questions. Clarifications, failures and truncated results do not pass.
- **Explanation structural acceptance:** answers whose model-selected cell references and labels pass the existing validator. This checks valid references, nonnumeric labels and restricted inferential wording; it does not prove correct label meaning or business usefulness.
- **Semantic answer review:** a separate review of the recorded observations checks label meaning, units, group attribution and whether observations address the question. Copied numbers can be supported by a semantically wrong query. Generic caveats do not repair wrong query results.
- **Latency:** one local end-to-end pipeline duration per question, including API calls, retries and execution. Model/index startup is excluded. No repeated-run performance improvement is claimed.
- **Usage/cost:** API-returned tokens, including cached input where reported. Cost is an estimate using the documented model rate card; it is not a billing statement, and unreported failed-request usage cannot be inferred.

The explanation interface currently generates labels and cell references, with Python inserting values. It does not generate unrestricted narrative analysis. Fallbacks display literal query values and are counted separately from accepted model explanations. Broader narrative quality, causal reasoning, statistical testing and the approximately 50-question unseen agent benchmark remain outside this run.

Official references: [Responses structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [selected model and rate card](https://developers.openai.com/api/docs/models/gpt-4.1-mini). Structured output compliance provides a reliable interface, not semantic correctness.
