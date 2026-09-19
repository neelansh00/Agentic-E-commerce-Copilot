# Measured project metrics

Regenerated from saved reports by the verification and baseline scripts. These are deterministic checks, not model accuracy.

- Source CSVs / database tables: 9 / 9.
- Source and loaded records: 1,550,922 (includes original duplicates).
- Database checks passed: 20/20.
- Six join/cardinality checks; three exact monetary reconciliations against CSV Decimal sums.
- Deterministic reference questions: 11.
- Reference SQL executions completed: 11/11.
- SQL results matching independent CSV calculations: 11/11.
- Reference result rows checked: 171.
- Frozen ground-truth comparison: matched.
- Baseline run wall time: 57.298 seconds (single local run, includes reference verification; not an improvement claim).
- Phase 3 offline reference replays matching ground truth: 11/11 (not model-generated SQL).
- Keyword schema retrieval contains required tables: 11/11 reference questions (development set).
- Database unchanged after guarded execution: True.
- Phase 3 model API calls: 0 (offline by user request).
- Phase 4 retrieval benchmark: 24 manually authored cases; real local embeddings, zero LLM API calls.
- RAG dev: 8 supported / 4 unknown questions; Hit@3 100.0%, Top-1 100.0%, MRR@3 1.000, unknown abstention 100.0%; median query 31.61 ms (startup excluded).
- RAG test: 10 supported / 2 unknown questions; Hit@3 100.0%, Top-1 90.0%, MRR@3 0.950, unknown abstention 100.0%; median query 41.007 ms (startup excluded).
- Retrieval scores measure expected-heading matches on a small same-author benchmark, not generated-answer accuracy. See [retrieval evidence](generated/rag_report.md).
- LLM execution accuracy, generated-answer accuracy, latency improvement and API cost: not measured.
- The approximately 50-question agent evaluation and controlled experiments remain for later phases.

Evidence: [database verification](generated/verification_report.md), [baseline report](generated/baseline_report.md), [offline text-to-SQL integration](generated/text_to_sql_report.md).
