# Offline end-to-end project check

All passed: **True**.

Rechecked RAG and all unit tests against the existing verified database. This does not verify live model behavior or prove the absence of all possible bugs.

| Command | Exit code | Seconds |
|---|---:|---:|
| `-m pip check` | 0 | 1.932 |
| `-m compileall -q app scripts tests` | 0 | 0.261 |
| `scripts/build_knowledge_index.py` | 0 | 8.178 |
| `scripts/verify_rag.py` | 0 | 4.607 |
| `scripts/ask.py --define What does late delivery mean? --json` | 0 | 3.361 |
| `scripts/ask.py --demo cancellation --rag --json` | 0 | 3.092 |
| `-m unittest discover -s tests -v` | 0 | 16.772 |
