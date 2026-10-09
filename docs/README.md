# gcp-docs-ai — Rewrite Plan

Planning documents for taking the Python prototype to a shippable Go service.

| Doc | Contents |
|---|---|
| [00-ANALYSIS.md](00-ANALYSIS.md) | Audit of the current code: what to keep, 17 concrete bugs, the architectural dead ends |
| [01-ARCHITECTURE.md](01-ARCHITECTURE.md) | Target design, the Qdrant-vs-Postgres decision, interfaces, data model, chunking, retrieval pipeline, performance targets |
| [02-ROADMAP.md](02-ROADMAP.md) | Nine phases with demos, exit gates, timeline, risk register |
| [03-TASKS.md](03-TASKS.md) | 47 tasks with verifiable acceptance criteria |
| [04-SKILLS.md](04-SKILLS.md) | Knowledge prerequisites, team shape, two-week pre-flight, reading list |

## The short version

**Database:** Postgres is the system of record no matter what — documents, chunks, jobs, evals.
The *vector index* sits behind a `VectorStore` interface with two implementations. Start on
pgvector (one less service while the hard problems are unsolved), move to Qdrant in production
for metadata filtering and native hybrid search, which is exactly this product's core workload.
One contract test suite runs against both, so "interchangeable" is verified by CI.

**Rewrite:** Go is the right call for the ingestion fan-out and for operability, but it will not
make embedding or inference faster, and the RAG ecosystem is thinner — budget for hand-writing
chunking, fusion and reranking.

**The actual hard part is not the rewrite.** It is that retrieval quality is empirical. Build the
evaluation harness early (Phase 5) and treat every tuning decision as a measurement. The
prototype has two different embedding models configured and no way to tell which one was better —
don't inherit that.

**Start here:** the four-week thin slice at the end of [03-TASKS.md](03-TASKS.md) — one product,
pgvector only, CLI only — judged on a single question: *are the citations right?*
