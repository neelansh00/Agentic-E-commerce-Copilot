# Interview notes — Phase 1

Only decisions actually implemented in Phase 1 are described as completed. Agent, RAG, embedding, cosine-similarity, UI and model-evaluation decisions remain for later phases.

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

## Questions to settle in Phase 2

Define successful orders, payment-based revenue, AOV denominator, cancellation denominator, late-delivery eligibility and timestamp policy; choose how to handle multiple reviews and multi-seller attribution. Then build manually verified reference queries. The 20 Phase 1 checks are data-engineering checks, not SQL-generation accuracy or groundedness measurements.

## Planned later decisions (not yet implemented or evaluated)

The requested direction is one primary agent with clearly defined SQL, business-definition retrieval and restricted Python tools. A small, inspectable native routing loop is the starting candidate; a framework must earn its complexity. RAG would retrieve changeable definitions with citations, while fine-tuning would not supply transactional facts. Schema matching, embedding model/dimension, cosine similarity, chunking, top-k, routing and retries must be justified by their later evaluations. No claims of improved accuracy are available yet.
