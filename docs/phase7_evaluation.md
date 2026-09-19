# Phase 7 evaluation protocol

The unit of evaluation is a complete request with an explicit expected result or expected abstention. `evaluation/questions.json` contains fifty manually specified development cases: fifteen simple SQL, twelve multi-table SQL, three time-based, eight business definitions, five statistical requests and seven ambiguous/adversarial requests. Eleven SQL cases come from the earlier development benchmark. The other thirty-nine are additional entries in this artifact; some reuse familiar definition/statistical intents or Phase 5 phrasing. The frozen metadata's “newly specified” label does not mean thirty-nine previously unseen questions. This is not held-out evaluation.

## Ground truth and freezing

`scripts/build_benchmark.py` assembles the manually written question catalog and refuses to overwrite the frozen file. All thirty SQL reference queries must first agree with independent raw-CSV calculations. The original eleven also match their unchanged saved reference values. Model prompts receive question/output contracts and schema/definitions; reference SQL and expected values are never passed to the model. Production agent, SQL prompts, routing and metric definitions are not tuned during this run.

SQL questions request explicit column names, cents and NULL semantics. These output contracts make comparison reproducible but are easier than unconstrained end-user phrasing. The comparator checks complete result values, columns and row multiplicity with the existing small float tolerance; grouped rows are aligned by keys. It does not score presentation ordering separately. Top-N membership is checked because the expected result includes exactly the reference subset. Schema expectations are recorded as annotations; a valid metric view need not list every underlying raw table in its output trace.

## Metrics and their limits

- SQL execution rate and SQL exact-result accuracy both use all thirty intended SQL tasks as denominator, including router refusals and generation failures.
- Tool selection compares requested tool sets against manually specified expected sets. Trace entries separately record whether selected tools actually ran.
- Task correctness combines SQL comparison, expected definition-heading retrieval, statistical group counts/means and expected refusal/clarification status. It is heterogeneous and always accompanied by the category metrics.
- RAG retrieval accuracy is expected-heading inclusion for eight definition questions. It does not measure arbitrary knowledge retrieval or prove definition-answer completeness.
- Answer groundedness is reviewed separately against reference correctness, evidence cells, citations and causal/ranking claims. Structural cell references alone are insufficient. Review annotations distinguish factual support from completeness; unsupported answers are not counted as successful quantitative answers.
- Latency is single-run wall time, including tools and model calls but excluding initial embedding-model construction. Tokens come from provider usage; no unverified current rate card is used to invent a cost estimate.

## Controlled comparisons

**A: naive full-schema prompting versus retrieved-schema prompting.** Ten fixed analytical questions use the same model, question, full business contract and SQL instructions. Only the supplied schema differs. Both arms get one generation attempt and the same application validation/execution path. “Naive” here means passing all tables, not omitting business definitions or removing safeguards. Input tokens and schema length are recorded as well as execution and exact results.

**B: no application validation/no retry versus validation with bounded retry.** Both arms reuse exactly the same initial retrieved-schema SQL plan from A. The baseline bypasses AST and metric validation on a disposable database copy, with one attempt. The guarded arm applies the existing validators and up to two diagnostic repairs. Repairs are prompted only by execution/validation errors, never by expected answers. Both arms retain SQLite authorization, read-only/query-only connections, function restrictions, a thirty-second execution limit and bounded output. This measures application checks and repair, not a dangerous unrestricted database configuration. Baseline writes, schema access and extensions are rejected by the engine in tests. The database copy and original file are hash-checked after the run.

**C: model definitions without context versus model plus retrieved definitions.** Eight definition questions receive the same concise explanation instruction and model. Only retrieved project context changes. Unlike the production RAG-only path, both arms generate text, making this a controlled generation experiment. A prewritten lexical rubric records concept-pattern coverage; a separate semantic review examines the actual required facts. Pattern hits are explicitly a proxy: negation, omissions and invented conventions can fool keyword scoring. Honest abstention without context is documented, not labeled fabricated knowledge.

Each arm has one sample per question, fixed order and one model snapshot. Sampling variability, service load and order effects are not controlled. These results cannot establish statistical significance or generalization, and the ten SQL experiment questions overlap prior development work. A/B initial-plan reuse is explicit to avoid counting reused calls as new spending. Additional complexity requires demonstrated value; safety controls also protect the database even if a clean ten-question sample shows no execution gain.

## Reproduce

```powershell
# Offline regression suite (no API calls)
.venv/Scripts/python.exe -m unittest discover -s tests -v

# Live runs are explicit and billable; use fresh output paths to preserve evidence
.venv/Scripts/python.exe scripts/evaluate_phase7.py --live --section benchmark --max-api-calls 150 --output docs/generated/phase7_benchmark_recheck.json
.venv/Scripts/python.exe scripts/evaluate_phase7.py --live --section experiments --max-api-calls 80 --output docs/generated/phase7_experiments_recheck.json
```

The runner checkpoints after each case, records source/data/benchmark hashes, and stops on provider failure or the API budget. Partial reports remain partial; they are never reported as complete fifty-question scores. Do not regenerate the benchmark to make a failed answer pass. Error analysis and future work should reference the frozen question IDs.

After the preserved runs and review files exist, regenerate the report and project metrics without API calls:

```powershell
.venv/Scripts/python.exe scripts/report_phase7.py
```

The report verifies benchmark identity, model identity, review provenance and unchanged database hashes. [Measured results](generated/phase7_report.md) include the three failed main-benchmark requests and additional experiment failures. A separately versioned correction pass can address them; this evaluation does not silently rewrite the benchmark or production behavior.
