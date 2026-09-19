# Offline end-to-end project check

All passed: **True**.

Rebuilt the database from the supplied archive and ran existing phases together. This does not verify live model behavior or prove the absence of all possible bugs.

| Command | Exit code | Seconds |
|---|---:|---:|
| `-m pip check` | 0 | 3.625 |
| `-m compileall -q app scripts tests` | 0 | 0.436 |
| `scripts/inspect_dataset.py` | 0 | 31.988 |
| `scripts/load_database.py` | 0 | 88.826 |
| `scripts/verify_database.py` | 0 | 74.723 |
| `scripts/run_baseline.py` | 0 | 240.643 |
| `scripts/verify_text_to_sql.py` | 0 | 204.854 |
| `scripts/ask.py --demo count --json` | 0 | 0.998 |
| `scripts/ask.py --demo cancellation --json` | 0 | 1.157 |
| `-m unittest discover -s tests -v` | 0 | 14.01 |
