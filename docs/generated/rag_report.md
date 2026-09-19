# Phase 4 local retrieval evaluation

Real local embeddings; no LLM/API calls.

13 chunks, top-k 3, cosine threshold 0.6. Startup 2.049s; query latency excludes startup.

| Split | Supported / unknown | Hit@3 | Top-1 | MRR@3 | Unknown abstention | Median ms |
|---|---:|---:|---:|---:|---:|---:|
| dev | 8 / 4 | 100.0% | 100.0% | 1.000 | 100.0% | 31.61 |
| test | 10 / 2 | 100.0% | 90.0% | 0.950 | 100.0% | 41.007 |

Cases were manually written before running retrieval. Threshold 0.60 was chosen before development evaluation; test cases were not used to tune it. This small same-author benchmark is not an independent production test. Hit@3 measures whether the expected heading is returned, not completeness of all required definitions or answer correctness. Similarity is not a probability. Unknown cases are easy unrelated topics; business-adjacent unsupported requests can still retrieve related excerpts.

Definition responses copy source text; SQL planning with retrieved context is tested using scripted responses only. No generative RAG improvement, causal claim or LLM accuracy is established.

## Failures

None on this run.

## Ranking misses

- rag_13: expected Successful orders and revenue at rank 2; first result was ['Category and seller sales; freight'].
