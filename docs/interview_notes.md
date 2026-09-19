# Interview notes — Phases 1–3

Only decisions actually implemented in Phases 1–3 are described as completed. Phase 3 was tested offline at the user's request, not with live LLM calls. Agent routing, RAG, embeddings, cosine similarity, UI and model evaluation remain for later phases.

## How to explain this phase in one minute

“I started with the supplied archive rather than assuming an online schema. My script audited every row in nine CSVs. I then loaded 1,550,922 records into SQLite with validated composite keys, six foreign-key relationships and indexes. I retained source anomalies and documented them, rather than silently cleaning away difficult cases. Twenty checks reconcile counts, joins and currency totals. The main lesson was grain: joining items, payments and reviews directly can multiply rows and inflate revenue.”

## Why SQLite rather than PostgreSQL?

- **Chosen:** SQLite through Python's standard driver for the local, single-user phase.
- **Why:** Works without server installation or credentials, and handles the measured 1.55-million-record snapshot. The majority is reference geolocation data.
- **Alternative:** PostgreSQL with SQLAlchemy Core, or DuckDB for analytical workloads.
- **Advantages:** One reproducible file, actual relational constraints, easy test fixtures, no dependency downloads.
- **Disadvantages:** Limited write concurrency; SQLite typing and SQL/date functions differ from PostgreSQL. Not a multi-user production database architecture.
- **At scale:** PostgreSQL for concurrent service access, COPY ingestion, appropriate resource limits, managed credentials and measured query plans. Use BIGINT cents, not 32-bit aggregate assumptions.

## Why SQL instead of supplying all data to an LLM?

- **Chosen now:** Relational storage and deterministic reconciliation queries. No LLM is implemented yet.
- **Why:** Exact grouping/joins over millions of rows belong in a query engine. The future LLM should propose constrained analytical operations, not remember transactional facts.
- **Alternative:** Pandas-only analysis or sending sampled tables in prompts.
- **Advantages:** Explicit grain, efficient filtering, reproducible results, inspectable calculations.
- **Disadvantages:** Bad joins can produce plausible but incorrect answers; successful execution does not imply correctness.
- **At scale:** Curated metric definitions, query budgets, read replicas and evaluation against reference results.

## Why integer cents?

- **Chosen:** Convert currency strings with `Decimal` to integer cents; reject extra decimal precision.
- **Why:** Binary floating point is unsuitable for exact financial reconciliation.
- **Alternative:** PostgreSQL NUMERIC/DECIMAL; floating point with rounding.
- **Advantages:** Exact sums in SQLite; easy source-to-database verification.
- **Disadvantages:** Every displayed value needs the correct unit conversion; money column names explicitly end in `_cents`.
- **At scale:** NUMERIC or BIGINT with explicit currency and rounding policies. Distinguish payment receipts, item value, freight and recognized revenue.

## Why composite keys and a geolocation surrogate?

- **Chosen:** (`order_id`, `order_item_id`), (`order_id`, `payment_sequential`), (`review_id`, `order_id`); CSV record ordinal for geolocation.
- **Why:** These match actual supplied uniqueness. Review ID alone fails; ZIP prefix is highly nonunique.
- **Alternative:** Use generated IDs everywhere, or deduplicate automatically.
- **Advantages:** Exposes business grain and prevents silent overwrites. Geolocation duplicates remain auditable.
- **Disadvantages:** Review/order uniqueness is specific to this observed file, and record ordinals change if a source file is reordered.
- **At scale:** Persistent ingestion provenance, source event identifiers and explicit merge/versioning rules.

## Why not enforce every apparent relationship as an FK?

- **Chosen:** Enforce six valid parent relationships. Keep category translation and ZIP lookups optional.
- **Why:** Two categories lack translations and ZIPs lack uniqueness/complete coverage. An FK must reference a real unique, complete parent domain.
- **Alternative:** Invent missing translations, delete unmatched records, or add separately curated category/ZIP dimensions.
- **Advantages:** No fabricated data, honest coverage, complete source preservation.
- **Disadvantages:** Later query authors must use LEFT JOIN and unknown-category handling.
- **At scale:** Curated dimensions with explicit unknown members and coverage monitoring; never silently map a missing category to an unrelated one.

## Why preserve anomalies?

- **Chosen:** Separate storage validity from analytical eligibility. Keep odd but structurally valid facts and record quality findings.
- **Why:** Missing dates or zero values can reflect a business state rather than a data error. Deleting them changes denominators.
- **Alternative:** Drop/impute data during ingestion.
- **Advantages:** Reproducible lineage; later analysis can justify filters.
- **Disadvantages:** Analysts must apply documented eligibility rules.
- **At scale:** Quality flags, quarantines for structural failures, versioned transformations and source-owner review.

## Why build into a temporary database?

- **Chosen:** Build and validate a separate database beside the target, close it, then atomically replace the target.
- **Why:** A failed import must not destroy a working database or leave half-loaded tables.
- **Alternative:** Drop/recreate tables in place or append with `INSERT OR IGNORE`.
- **Advantages:** Failure recovery, repeatable rebuilds, explicit failure on conflicts.
- **Disadvantages:** Temporarily needs space for both copies. Close applications using the DB before rebuilding; Windows may prevent replacement of an open file.
- **At scale:** Transactional staging and publish, migrations and coordinated readers. Filesystem atomic replace is not a full backup/durability strategy.

## Why these checks and indexes?

- **Chosen:** Source row-count checks, FK/integrity checks, six cardinality checks and exact monetary reconciliation. Index PK/FK, time/status and likely geography/category filters.
- **Why:** Detect lost rows, broken relationships and obvious join inflation before a model can produce answers.
- **Alternative:** Only test whether a SELECT executes; index every column.
- **Advantages:** Correctness evidence tied to known failure modes. Sensible starting indexes keep future joins accessible.
- **Disadvantages:** These checks do not prove future natural-language SQL correctness or demonstrate index speedup. No latency improvement is claimed.
- **At scale:** EXPLAIN plans and measured workloads guide indexes; add semantic query benchmarks and resource-limit tests.

## Why standard-library scripts and tests?

- **Chosen:** `csv`, `zipfile`, `sqlite3`, `Decimal`, `unittest`; no application dependency yet.
- **Why:** All Phase 1 requirements can be reproduced offline with Python 3.11+.
- **Alternative:** Pandas, SQLAlchemy and pytest immediately.
- **Advantages:** Minimal setup and visible internal behavior; fixture tests need no dataset or API credentials.
- **Disadvantages:** More explicit parsing code; the exact distinct-value audit holds sets in memory and is not a big-data profiler.
- **At scale:** Streaming/database profiling or approximate cardinality sketches; use the appropriate library when it simplifies a real requirement. The unittest tests can later run under pytest.

## Business policy decisions completed in Phase 2

The [metric contract](../knowledge_base/metrics.md) now defines success as delivered, revenue as recorded successful-order payments, AOV over delivered orders with payments, cancellation over all orders, strict timestamp lateness and valid-review selection. Eleven SQL queries are checked against independent raw-CSV calculations and frozen reference results. The 20 Phase 1 checks remain data-engineering checks, not SQL-generation accuracy or groundedness measurements.

## Why a deterministic baseline before an agent?

- **Chosen:** Fixed SQL plus independently calculated expected results before generation.
- **Why:** Without ground truth, executable but wrong SQL can look successful. A baseline also makes a later model's mistakes inspectable.
- **Alternative:** Start with prompts and judge a handful of answers manually.
- **Advantages:** Business policy is explicit, reproducible and testable. Hand-calculated cases expose fanout and denominator mistakes.
- **Disadvantages:** Eleven references are narrow and not the promised full benchmark. They cannot establish general natural-language capability.
- **At scale:** Version metric contracts, broaden benchmark populations and keep unseen questions separate from development examples. An agent earns its role by composing operations for questions outside the fixed catalogue.

## Why distinguish payment revenue from category/seller item sales?

- **Chosen:** Delivered payment values for global/state/month revenue; item price sums for category/seller rankings.
- **Why:** One payment may cover multiple items, categories, sellers and freight. The data does not supply a unique seller-level allocation.
- **Alternative:** Proportionally allocate payment value across item values, or call all item sales revenue.
- **Advantages:** No invented attribution; exact source values and clear units.
- **Disadvantages:** Category totals do not reconcile to payment revenue; the label must remain explicit. Payment revenue is still a project proxy, not accounting truth.
- **At scale:** Work with finance/product stakeholders on recognition, refunds, discounts and allocation. Keep additive metrics at their natural grain.

## Why this AOV denominator and NULL policy?

- **Chosen:** Use delivered orders with observed payment rows, including recorded zero payments. Report missing coverage; undefined rates/means are NULL.
- **Why:** Missing is not zero, and multiple payments are not multiple orders.
- **Alternative:** Divide by every delivered order or impute missing payments as zero.
- **Advantages:** Numerator and denominator refer to the same observed population.
- **Disadvantages:** Observed-payment AOV may be biased if missingness is systematic; it is not an estimate for unobserved payments.
- **At scale:** Track coverage by cohort and reconcile against the payment system; only impute under a justified model.

## Why latest eligible review rather than averaging every review row?

- **Chosen:** Valid chronology first, then latest answer, latest creation, largest review ID per order.
- **Why:** Avoid overweighting orders with multiple reviews and make tie outcomes reproducible.
- **Alternative:** Earliest review, mean per order, or all review rows.
- **Advantages:** One score per order and explicit missing-review coverage.
- **Disadvantages:** The source does not prove reviews are edits; selection is an assumption, and chronology filtering changes the population.
- **At scale:** Determine review event semantics and evaluate sensitivity to competing selection rules. Order-level scores shared across sellers are not independent direct seller ratings.

## Why descriptive screens rather than significance or anomaly claims?

- **Chosen:** Compare means/rates and show sample sizes; use explicit minimum sample thresholds for seller/category rankings.
- **Why:** This phase establishes reference aggregates, not statistical inference. Late delivery may correlate with geography, product mix and other factors.
- **Alternative:** Run many tests and rank p-values, or label every above-average seller anomalous.
- **Advantages:** Easy to explain, no unjustified causal/significance claims.
- **Disadvantages:** Thresholds of 20/30 are transparent screening conventions, not validated precision guarantees. Rankings may be unstable for small groups.
- **At scale:** Define hypotheses and units of independence, consider confidence intervals, multiple comparisons, confounding and repeated buyers/orders before choosing tests.

## Why independent CSV calculations and frozen snapshots?

- **Chosen:** SQL outputs compared to Python dictionaries/sets, Decimal sums and datetime differences over original CSVs; commit expected results with source/contract/SQL hashes.
- **Why:** Re-running the same SQL twice is not independent verification, and silently regenerating expected values hides regressions.
- **Alternative:** Use only execution success or hardcode one aggregate total.
- **Advantages:** Every output cell and its ordering is checked. Hand-calculated adversarial fixtures complement full-data agreement.
- **Disadvantages:** Two implementations need maintenance and can still share a mistaken written policy. Floating-point duration averages require a small absolute tolerance.
- **At scale:** Automated lineage, curated gold data, peer review, holdout questions and explicit versioned benchmark updates. Do not use these development questions to claim unseen-model accuracy.

## Planned later decisions (not yet implemented or evaluated)

The requested direction is one primary agent with clearly defined SQL, business-definition retrieval and restricted Python tools. Phase 3 now implements the SQL loop; multi-tool routing remains later work. RAG would retrieve changeable definitions with citations, while fine-tuning would not supply transactional facts. Embedding model/dimension, cosine similarity, chunking and top-k are pending. Schema matching and retry policies are implemented but their effect on live-model accuracy has not been evaluated. No claims of improved accuracy are available yet.

## Why keyword schema retrieval with join paths?

- **Chosen:** Match question words to tables, add shortest paths through the relational model, and inspect actual metadata only for selected tables.
- **Why:** Small known schema; this policy can be drawn and debugged. Initial selections/reasons and one optional targeted expansion are logged.
- **Alternative:** Full-schema prompts or embedding-based schema retrieval.
- **Advantages:** Lower irrelevant context and no embedding service; bridge tables are retained for joins.
- **Disadvantages:** Synonyms and ambiguous phrases may be missed. Development-reference recall does not prove unseen-question accuracy or token/latency improvements.
- **At scale:** Evaluate paraphrases and larger schemas; adopt semantic retrieval only if it improves measured result accuracy.

## Why both SQLGlot and SQLite authorization?

- **Chosen:** Parse SELECT/CTE structure and allowlists, then independently restrict database operations and functions at preparation time with SQLite's authorizer on a read-only connection.
- **Why:** Keyword blocking confuses comments/strings and misses SQL structure; relying on a model's promise is insufficient. Independent layers cover parser mistakes and unexpected SQL.
- **Alternative:** Regex-only validation, only `mode=ro`, or unrestricted execution in a writable connection.
- **Advantages:** Reject mutations, attachments, PRAGMAs, system reads and extension/file functions. Tests exercise the authorizer without the parser as well.
- **Disadvantages:** Conservative allowlists reject some useful queries. A SELECT can still have a wrong join or expensive intermediate computation; this is not semantic proof or an OS sandbox.
- **At scale:** A least-privilege DB role, read replica, server statement/resource budgets and isolated workers; maintain query-level correctness evaluation.

## Why at most three SQL attempts?

- **Chosen:** Initial generation plus up to two repairs, feeding back validation/SQLite diagnostics and previous SQL. Provider SDK retries are disabled.
- **Why:** Fixable syntax/schema/aggregate mistakes should not immediately abort, but loops need bounded cost and latency.
- **Alternative:** No repair, unlimited retries or framework-managed hidden retries.
- **Advantages:** Visible trace, bounded SQL attempt count and clear terminal failure. Missing data cannot turn into fabricated results after retries.
- **Disadvantages:** Repairs can change intended semantics; timeout per query is not a whole-request deadline. Three attempts are a configured engineering bound, not an experimentally proven optimum.
- **At scale:** Evaluate correction success/cost and error classes, enforce end-to-end budgets and stop early on nonrepairable errors.

## Why typed model outputs and evidence-cell explanations?

- **Chosen:** Pydantic SQL plans and explanation references. The model chooses a result cell; Python inserts its actual value. Bad references fall back to literal results.
- **Why:** Structured output separates query/clarify/unsupported outcomes; numbers should originate in executed data.
- **Alternative:** Markdown SQL extraction and unconstrained narrative answers.
- **Advantages:** Inspectable schema, deterministic failure handling, no model-authored numeric value field. Fixed caveats prohibit unrestricted statistical claims.
- **Disadvantages:** A valid reference may still have a misleading label, and SQL itself may be semantically incorrect. This is not complete automatic groundedness certification.
- **At scale:** Semantic claim review, better evidence granularity and human-labelled groundedness evaluation. Don't claim a score without measuring it.

## Why a native pipeline and offline provider tests?

- **Chosen:** Ordinary Python loop plus a small model protocol. OpenAI structured-output adapter is available but live calls were deliberately not used; ScriptedModel is visibly named as offline.
- **Why:** Phase 3 has one sequential task and clear boundaries, so a graph/multi-agent framework would add little. Offline tests exercise failures cheaply and reproducibly.
- **Alternative:** LangGraph/LangChain orchestration, network-dependent tests or reporting reference replay as a successful model benchmark.
- **Advantages:** Understandable control flow; testable refusal/error/repair behavior; replace provider without rewriting database logic.
- **Disadvantages:** Mock responses do not test actual model quality, availability, token costs or provider behavior. SDK boundary tests are contract tests, not live integration proof.
- **At scale:** Enable explicitly configured live evaluations, store model/prompt versions, add usage budgets and compare against the held-out benchmark. Add a framework only when orchestration complexity warrants it.


## Phase 4 decisions: local business-definition RAG

**Why RAG instead of fine-tuning?** Definitions are explicit project conventions that must be inspectable and editable. Retrieval supplies their current text and citations without retraining. Fine-tuning might change model behavior but does not reliably store an auditable, current metric contract. RAG adds retrieval errors and context-selection decisions; at production scale version definitions, evaluate retrieval drift and enforce approved metric calculations independently of prose.

**Why BGE-small through FastEmbed?** A compact English encoder with local ONNX CPU inference gives real semantic retrieval without credentials or a heavyweight training stack. The pinned public model revision and asset hashes make rebuilding explainable. TF-IDF/BM25 would be simpler and a worthwhile later baseline; hosted embeddings trade local setup for network dependency and cost. We did not compare encoders and cannot claim this one is optimal. Production model choice would use domain-specific, multilingual and adversarial benchmarks.

**Why cosine similarity and FAISS?** Normalization removes vector magnitude, and the dot product of normalized vectors equals cosine similarity. FAISS IndexFlatIP checks every chunk exactly. Thirteen chunks do not justify approximate indexes, a server or orchestration framework. A plain NumPy matrix could also do this job; FAISS provides a standard index interface at the cost of another binary dependency. Larger corpora could require filtering, hybrid retrieval or approximate search, justified by measured recall and latency.

**Why heading chunks and top three?** Metric sections are understandable citation units. We preserve line references and bound chunk size; token checks prevent silent model truncation. Top three balances context size and coverage, while a fixed similarity threshold drops very weak matches. The threshold is not a probability or a proof that a question is answerable. Compound SQL questions can need several related definitions, so retrieval completeness must be evaluated separately. Future work could retrieve explicit definition dependencies or use a reranker only if controlled tests justify it.

**Why return excerpts offline?** The user requested offline model development. Real local semantic search works without an LLM; verbatim excerpts keep definitions grounded and visible. SQL-context integration is verified with scripted responses. This does not establish generated-answer accuracy, nor does it validate whether a live model will follow definitions. Production answers need citation entailment and semantic query checks, beyond valid JSON and safe SQL.

**Why optional RAG rather than replacing the existing path?** Static contract prompting is an existing working baseline. An explicit --rag flag lets us inspect the new path and later compare it under controlled conditions. One retriever feeding one planner is easy to draw; no agent swarm is needed. Phase 5 will add tool routing, not duplicate agents around each function.

**Why these metrics?** Hit@3 asks whether the needed section is present in retrieved context, Top-1 measures first-result usefulness and MRR rewards high placement. Unknown-topic abstention measures one failure mode; latency separates model startup from per-query cost. Ten supported reserved questions are too few to generalize. The freight question ranks the wrong section first, demonstrating why Hit@3 alone can hide a practical weakness. LLM answer groundedness and no-RAG versus RAG comparisons remain unmeasured.

**How does source freshness work?** Store source/model checksums alongside the index and refuse stale or incompatible artifacts. Atomic metadata replacement prevents half-published builds. Hashes detect accidental changes, not malicious replacement of all local files. At production scale use controlled artifact publication, authorization, audit logs and safe index lifecycle management.


## What changed when we tested a real model?

The first live evaluation used the configured GPT-4.1 mini snapshot on 11 reference questions in two context modes. Both matched 8/11 complete results, even though SQL executed in 10/11 static and 11/11 RAG runs. This is a development set with explicit output shapes, not evidence of generalization. We preserved all initial failures and did not tune the prompts during the run.

The strongest interview lesson is that three checks answer different questions. SQL safety asks whether a query may run. Result comparison asks whether the calculations follow the metric contract. Explanation review asks whether prose faithfully describes the evidence. A query can pass safety while averaging repeated item rows, and a model can point to a real state count while calling it the highest when it is not.

Offline scripted tests demonstrated plumbing, not model behavior. Live generation revealed missing calendar months, NULL-to-zero errors, wrong delivery eligibility, an overly restrictive EXISTS check and repeated invalid explanation references. Two accepted explanations still had misleading group/extrema labels. These are documented weaknesses, not hidden behind an execution-rate score. Next improvements should have regression cases and separate paraphrases; rerunning the same examples until they pass would inflate the reported result.

The answer interface is constrained generation: the model picks labels/cells and Python supplies values. We measured structural acceptance and reviewed label meaning and coverage. We have not measured unrestricted narrative quality. See the [live report](generated/live_evaluation.md) for exact counts, usage and review limitations.
