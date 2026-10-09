# 04 — Skills and Knowledge Prerequisites

What you need to know before starting, honestly rated. The rewrite is not hard because Go is
hard; it is hard because **retrieval quality is an empirical discipline** and most of the work is
measurement, not code.

Levels: **1** aware · **2** can follow a tutorial · **3** can build unaided · **4** can debug it
under pressure at 3am.

---

## A. Go — target level 3, level 4 for concurrency

| Topic | Target | Why this project needs it |
|---|---|---|
| Idiomatic Go, project layout, error wrapping (`%w`, `errors.Is/As`) | 3 | Errors cross five pipeline stages; you need to know *which* URL failed and why |
| `context` propagation and cancellation | **4** | Ctrl-C, SIGTERM drain, client disconnect and per-request timeouts all ride on it. Getting this wrong is the #1 source of goroutine leaks |
| Goroutines, channels, `select`, bounded queues | **4** | The whole ingestion design is backpressure |
| `errgroup`, `semaphore.Weighted`, `x/time/rate` | **4** | Directly fixes B3 (unbounded concurrency) |
| Interfaces and dependency injection | 3 | The DB-interchangeability goal lives or dies here |
| Table-driven tests, golden files, fuzz/property tests | 3 | T-1.4 and T-3.1 acceptance criteria are golden and property tests |
| `testcontainers-go` | 3 | Running one contract suite against two real databases (T-2.5) |
| `pprof`, `-race`, `runtime/trace` | 3 | The 24h soak (T-8.3) requires reading a heap profile, not guessing |
| `log/slog`, OpenTelemetry Go SDK | 2→3 | Phase 0 |
| Generics | 2 | Useful in the filter AST; do not overuse |

**Gap to close first:** if concurrency is not already at 4, spend a focused week on
*Concurrency in Go* (Cox-Buday) plus the `context` and `sync` package sources before Phase 1.
Everything downstream inherits mistakes made here.

## B. Retrieval / RAG — the real difficulty, target level 3

| Topic | Target | Notes |
|---|---|---|
| Chunking strategies for technical docs | **4** | Highest-leverage variable in the entire system. Structure-aware > fixed-size, always, for documentation |
| Embedding models: dimensions, context limits, doc-vs-query asymmetry | 3 | Many models need distinct prefixes for documents and queries; getting this wrong silently halves recall |
| HNSW: `m`, `ef_construct`, `ef_search`, recall/latency tradeoff | 3 | You will tune these in both backends |
| BM25 / sparse retrieval, SPLADE, miniCOIL | 3 | The lexical leg is non-optional for GCP identifiers (Architecture §7) |
| Reciprocal Rank Fusion and alternatives | 3 | T-4.2 |
| Cross-encoder reranking | 2→3 | Large quality win per unit effort; keep it behind a switch and *measure* it |
| MMR / diversification | 3 | Why one page cannot monopolise the context |
| Query rewriting, HyDE, acronym expansion | 2→3 | T-4.1 |
| Evaluation: recall@k, MRR, nDCG, groundedness, citation accuracy | **4** | Without this you are guessing. Read the RAGAS and BEIR literature |
| Context assembly and token budgeting | 3 | T-4.4 |
| Grounded prompting and refusal behaviour | 3 | "I don't know" is a feature, not a failure (T-4.4 AC3) |
| Prompt injection via retrieved content | 3 | You are ingesting third-party HTML and serving it to an LLM (T-6.2 AC3) |

**Gap to close first:** build the eval harness (Phase 5) *before* tuning anything. If you learn
one thing from this document, make it that. Every hour spent tuning retrieval without
measurement is an hour spent guessing, and the prototype is direct evidence — it has two
different embedding models configured and no way to tell which was better.

## C. Databases — target level 3

### Postgres (required)
`pgx` v5 (pools, batching, `CopyFrom`), migrations, `EXPLAIN ANALYZE`, btree/GIN/partial
indexes, transaction isolation, `tsvector`/`ts_rank`, `LISTEN/NOTIFY`, connection-pool sizing,
backup/PITR.

### pgvector (required for the default backend)
`vector` type, HNSW vs IVFFlat, `vector_cosine_ops`, filtered-search behaviour and *why* it
degrades (heap-scan locality — Architecture §3.2), `maintenance_work_mem` during index build,
dimension limits.

### Qdrant (required for the production backend)
Collections, named dense + sparse vectors, payload indexes, the Query API (prefetch + RRF
fusion), aliases, scalar/product/binary quantization, snapshots, memmap vs in-RAM, sharding and
replication, `wait` semantics on upsert.

**Gap to close first:** Qdrant's payload indexes and quantization are where the operational
surprises live. Do a throwaway spike — load 1M synthetic vectors, tune quantization and
`ef_search`, measure — before T-2.4. A day here saves a week later.

## D. Web crawling and HTML extraction — target level 3

`robots.txt` semantics, politeness and backoff, conditional GET (ETag / `If-Modified-Since`),
URL canonicalization, `goquery`/`net/html`, `goldmark` AST (and writing a custom renderer),
HTML→Markdown fidelity for code and tables, detecting structural drift in a site you do not
control.

**Gap to close first:** `goldmark`'s AST and extension model. The chunker is the heart of the
system and it is a `goldmark` program. Budget two days to read its AST walker properly — regex
is what broke the prototype (Analysis §2.5) and the temptation to reach for it will return.

## E. LLM operations — target level 3

Serving (Ollama, vLLM, HF TGI/TEI), the difference between Ollama's API and OpenAI-compatible
endpoints (**directly relevant — this is bug B11**), streaming and SSE, token counting and
budgeting, sampling parameters, GPU/VRAM sizing, quantization tradeoffs, structured outputs,
latency profile (TTFT vs throughput), and the cost model if you ever move to a hosted API.

## F. Operations — target level 3

Docker multi-stage builds for Go, Compose for local dev, Kubernetes basics if deploying there,
OpenTelemetry (traces/metrics/logs), Prometheus + Grafana, SLOs and error budgets, GitHub Actions,
migration safety in CI/CD, secret management, backup/restore drills, load testing (k6/vegeta).

## G. Domain knowledge — target level 3

You cannot evaluate a Google Cloud assistant without knowing Google Cloud. Specifically:

- The main service families and what they are actually for — enough to judge whether an answer
  is *right*, not just plausible.
- **How services compose**: Eventarc, Pub/Sub, Cloud Run triggers, Workflows, IAM service
  accounts and Workload Identity. This is the integration answer class and the hardest to eval.
- IAM roles and permission naming conventions (`roles/storage.objectAdmin`) — the exact strings
  that make the lexical retrieval leg matter.
- Client-library idioms in at least Go and Python, including auth (ADC), retries and pagination.
- How the docs themselves are organised: Guides vs Reference vs Tutorials vs Release Notes,
  and the devsite URL structure. Your `doc_type` taxonomy depends on it.

**This is the most underrated item on the list.** Writing 150 good golden questions (T-5.1)
requires real product knowledge, and the quality of that set caps the quality of everything
measured against it.

## H. Legal and compliance — target level 2

CC BY 4.0 attribution obligations, Apache 2.0 notice requirements, Google's site ToS and
trademark limits, GDPR basics if you log customer questions (you will), data residency if
customers ask (a real reason to keep inference local).

---

## Team shape

**One engineer** can do this in ~15–16 weeks if they are already level 3 in Go and level 2+ in
RAG. The long pole is Phase 5 + Phase 7, not the rewrite itself.

**Two engineers** is the sweet spot and gets you to ~9–10 weeks:
- **Engineer A — pipeline:** Phases 1, 2, 3, 7. Needs Go concurrency 4, databases 3, crawling 3.
- **Engineer B — retrieval & serving:** Phases 4, 5, 6. Needs RAG 3–4, domain 3, API design 3.
- Both share Phases 0, 8, 9. They converge at Phase 4, so agree the `Chunk` and `VectorStore`
  contracts (T-2.2, T-3.1) *first* — those are the interface between the two workstreams.

Adding a third engineer before Phase 4 will not speed things up; the work is not that parallel
until the contracts are fixed.

---

## Two-week pre-flight

Do this before T-0.1. It is cheap and it will change the plan in useful ways.

| Day | Activity | Output |
|---|---|---|
| 1–2 | Go concurrency refresher: worker pool + rate limiter + context cancellation from scratch | A throwaway crawler that respects 2 req/s and cancels cleanly |
| 3–4 | `goldmark` spike: parse a real GCP page, walk the AST, emit heading-aware chunks | Proof the code-block problem is solvable; a feel for T-3.1 |
| 5 | pgvector spike: 100k vectors, HNSW, filtered query, `EXPLAIN ANALYZE` | Measured filtered-vs-unfiltered latency on your hardware |
| 6–7 | Qdrant spike: 1M synthetic vectors, payload indexes, hybrid Query API, quantization | Your own numbers for ADR-002 instead of someone else's blog post |
| 8 | Embedding model bake-off: 3 candidates on 20 real GCP passages | A model choice with evidence, and ADR-003 |
| 9–10 | Write 30 golden questions by hand across all three answer classes | The seed of T-5.1 — and a brutal reality check on how hard your own product is |

Day 9–10 is the most valuable pair of days in the whole schedule. Writing the questions forces
you to confront what "answering correctly" actually means here, and it will probably change your
chunking and filtering design before you have written a line of it.

---

## Reading list, ranked by return on time

1. *Concurrency in Go* — Cox-Buday. Chapters 4–5. Directly applicable to Phase 1.
2. Qdrant docs: Hybrid Queries, Payload Indexing, Quantization, Optimizer.
3. pgvector README + the "filtered search" discussion threads — understand *why* it degrades.
4. `goldmark` source: `ast/` and `renderer/`. Short, and you will be living in it.
5. RAGAS paper + BEIR benchmark methodology — how to measure retrieval honestly.
6. Anthropic's "Contextual Retrieval" write-up — the breadcrumb-prefix technique in §5.3.
7. Google Cloud architecture centre — for the integration questions in the golden set.
8. `river` docs — the job queue you will build the pipeline on.
9. OpenTelemetry Go SDK docs — Phase 0 and Phase 8.
