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
- Baseline run wall time: 93.153 seconds (single local run, includes reference verification; not an improvement claim).
- LLM execution accuracy, answer accuracy, retrieval accuracy, latency improvement and cost: not measured.
- The approximately 50-question agent evaluation and controlled experiments remain for later phases.

Evidence: [database verification](generated/verification_report.md), [baseline report](generated/baseline_report.md).
