# Offline end-to-end project check

All passed: **True**.

Rebuilt the database from the supplied archive and ran existing phases together. This does not verify live model behavior or prove the absence of all possible bugs.

| Command | Exit code | Seconds |
|---|---:|---:|
| `-m pip check` | 0 | 3.203 |
| `-m compileall -q app scripts tests` | 0 | 0.268 |
| `scripts/inspect_dataset.py` | 0 | 40.403 |
| `scripts/load_database.py` | 0 | 102.349 |
| `scripts/verify_database.py` | 0 | 19.95 |
| `scripts/run_baseline.py` | 0 | 57.882 |
| `scripts/verify_text_to_sql.py` | 0 | 37.689 |
| `scripts/ask.py --demo count --json` | 0 | 0.754 |
| `scripts/ask.py --demo cancellation --json` | 0 | 0.891 |
| `scripts/build_knowledge_index.py` | 0 | 3.565 |
| `scripts/verify_rag.py` | 0 | 2.274 |
| `scripts/ask.py --define What does late delivery mean? --json` | 0 | 2.252 |
| `scripts/ask.py --demo cancellation --rag --json` | 0 | 2.529 |
| `-m unittest discover -s tests -v` | 0 | 10.158 |
