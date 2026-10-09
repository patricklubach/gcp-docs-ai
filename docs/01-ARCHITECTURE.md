# 01 — Target Architecture

## 1. Product definition

> A service that answers questions about Google Cloud: what a service does, how to use two or
> more services together, and how to use their client libraries — with citations to the exact
> documentation page and section the answer came from.

Three answer classes, each with different retrieval needs. Design for all three from day one:

| Class | Example question | What retrieval must do |
|---|---|---|
| **Conceptual** | "What consistency guarantees does Cloud Storage give me?" | Find prose in *Guides*; one product |
| **Integration** | "How do I trigger a Cloud Run job when an object lands in a bucket?" | Retrieve across **two or more** products and rank the pages that mention both |
| **Library / code** | "Show me the Go code to publish to Pub/Sub with an ordering key" | Retrieve *code*, from reference docs and sample repos, filtered by language |

The integration and library classes are the ones the current prototype cannot serve at all, and
they are the ones with the most user value. They drive several decisions below (§4.3, §5.3, §10).

## 2. Why Go — and where Go will not help

Good reasons, and they hold:
- **Ingestion is I/O-bound fan-out.** Goroutines + `errgroup` + a bounded semaphore express
  "crawl 500 pages, 8 at a time, 2 req/s per host, cancel everything on shutdown" far more
  legibly than the current `asyncio.gather` over unbounded tasks.
- **A single static binary** with no venv, no `uv.lock`, no CUDA-adjacent Python deps is a
  dramatically simpler operational story for a service a customer depends on.
- **Streaming + backpressure**: channels give bounded queues for free. Memory stays flat on a
  1M-chunk reindex instead of growing with the corpus.
- **Real types.** `Chunk`, `VectorStore`, `Embedder` as interfaces make the "swap the database"
  goal a compile-time guarantee rather than a hope.

Be honest about the limits:
- **Go will not make embedding or LLM inference faster.** Those are network calls to Ollama /
  Vertex / TEI. Wall-clock time for indexing is dominated by the embedding service, not by the
  orchestration language. Expect the win to come from *correct batching and concurrency*, which
  you could also have gotten in Python.
- **The RAG ecosystem is thinner in Go.** No LangChain/LlamaIndex equivalent with the same
  breadth. You will hand-write chunking, hybrid fusion and reranking. That is a feature for this
  project — the prototype's problems came *from* framework defaults — but it is real work, and
  it is why the roadmap has an explicit retrieval-quality phase.
- **Tokenizers and rerankers are Python-shaped.** Plan to call a small Python sidecar (HF
  `text-embeddings-inference`, or Ollama) over HTTP rather than reimplementing them. Keep the
  boundary at a well-defined interface.

## 3. The database question: Qdrant or Postgres?

**Answer: both, with different jobs. This is not a fence-sit — they solve different problems.**

### 3.1 You need Postgres regardless of the vector store

The system has a large amount of state that is not vectors and must be transactional:

- crawl runs, per-URL fetch status, ETag / Last-Modified, content hashes, tombstones
- documents and their chunks (the canonical text, so you can re-chunk and re-embed without
  re-crawling Google — this alone justifies it)
- the job queue (ingest → extract → chunk → embed → index), with retries and a dead-letter table
- query logs, user feedback, evaluation runs and their scores
- index generation metadata and the active-alias pointer (§6)

Trying to keep that in a vector database's payloads is how you end up with an unrecoverable
corpus. **Postgres is the system of record. Non-negotiable.**

### 3.2 Then, for the vector index specifically

| Dimension | pgvector | Qdrant |
|---|---|---|
| Extra infrastructure | None — already have Postgres | A second stateful service to run, back up, monitor |
| Scale comfort zone | Excellent to ~5–10M vectors with HNSW | Designed well past that |
| Metadata filtering | Degrades: filtered HNSW breaks index locality; heap scans add real latency | In-graph filtering with payload indexes; ~1–2 ms overhead |
| Hybrid (dense + lexical) | Hand-rolled: `tsvector` + `ts_rank`, RRF in SQL | Native — sparse vectors + prefetch + `NewQueryRRF` fusion in the Go client |
| Transactional consistency with your metadata | Free (same transaction) | Eventual; needs reconciliation |
| Zero-downtime reindex | Manual (table + view swap) | Native collection aliases |
| Quantization / memory tuning | Limited | Scalar, product, binary quantization |
| Operational learning cost | Low, if you know Postgres | New system: shards, replicas, snapshots, payload indexes |

**Why this project leans Qdrant in production:** the highest-value query class (§1, "integration")
is *exactly* a selective metadata filter over a large collection — `product IN ('run','storage')`,
`doc_type = 'reference'`, `lang = 'go'`. That is the one workload where the two genuinely diverge,
and it is your core workload, not an edge case. Native hybrid search matters too: GCP docs are
dense with exact identifiers (`roles/storage.objectAdmin`, `--ordering-key`) that embeddings
handle poorly and BM25 nails. Getting that in pgvector means maintaining hand-written fusion SQL.

**Why you should still start on pgvector:** at a realistic starting corpus — say 30 GCP products,
~15k pages, ~150k–400k chunks — pgvector with HNSW is comfortably fast, and you get to ship the
whole pipeline against *one* piece of infrastructure while the hard problems (chunking quality,
citation accuracy, eval harness) are still unsolved. Adding Qdrant on day one means debugging two
systems while you do not yet know whether your chunks are any good.

### 3.3 The decision

```
Postgres  = system of record, always.           (documents, chunks, jobs, evals, feedback)
VectorStore = a Go interface with two impls.    (pgvector | qdrant)
  - default in dev/CI:  pgvector   (one container, fast tests)
  - default in prod:    qdrant     (filtering + native hybrid at scale)
```

Switching is a config value. The contract test suite (T-2.5) runs identically against both, so
"interchangeable" is verified by CI, not asserted in a README. Revisit the prod default with data
from the benchmark harness (T-2.6) — if pgvector holds p95 targets on your real corpus with your
real filters, staying single-service is a legitimate outcome, and the abstraction costs you
nothing either way.

> **ADR-001** through **ADR-004** in `docs/adr/` should record this, plus the embedding model
> choice, the chunking strategy and the Go/Python boundary.

## 4. Component architecture

```
                      ┌─────────────────────────────────────────┐
                      │  cmd/gcpdocs-api    (HTTP, SSE stream)   │
                      └───────────────┬─────────────────────────┘
                                      │
        ┌─────────────────────────────┴──────────────────────────┐
        │  answer/   query rewrite → retrieve → rerank → prompt   │
        │            → stream → cite → log                        │
        └──────┬───────────────────────────────┬─────────────────┘
               │                               │
        ┌──────┴────────┐              ┌───────┴────────┐
        │  retrieve/    │              │  llm/          │
        │  hybrid+RRF   │              │  Chat iface    │
        │  MMR, dedupe  │              │  ollama|openai │
        └──────┬────────┘              │  |vertex       │
               │                       └────────────────┘
        ┌──────┴──────────────────────────────┐
        │  index/  VectorStore interface       │
        │    ├── qdrant                        │
        │    └── pgvector                      │
        └──────┬──────────────────────────────┘
               │
        ┌──────┴───────────────────────────────────────────────┐
        │  store/  Postgres: documents, chunks, runs, jobs,     │
        │          feedback, evals, index_generations           │
        └──────┬───────────────────────────────────────────────┘
               │
  ┌────────────┴─────────────────────────────────────────────────┐
  │  cmd/gcpdocs-worker   (River job queue, Postgres-backed)      │
  │                                                                │
  │   crawl/  ──▶  extract/  ──▶  chunk/  ──▶  embed/  ──▶ index/  │
  │   politeness   devsite       goldmark     batching             │
  │   robots.txt   → Markdown    AST-aware    Embedder iface       │
  │   ETag/304     canonical     code-safe    ollama|tei|vertex    │
  │   backoff      URLs          breadcrumbs                       │
  └────────────────────────────────────────────────────────────────┘
```

### 4.1 Package layout

```
cmd/
  gcpdocs-api/      HTTP API + streaming chat
  gcpdocs-worker/   River workers for the ingest pipeline
  gcpdocs/          admin CLI: crawl, reindex, eval, promote, doctor
internal/
  config/           env + file config, validated at startup, no literals in code
  crawl/            fetcher, robots, rate limit, nav discovery, conditional GET
  extract/          devsite HTML → Markdown + front-matter (URL, product, doc_type)
  chunk/            goldmark AST → heading-aware, code-safe chunks
  embed/            Embedder interface + ollama/tei/vertex impls, batching, retry
  index/            VectorStore interface + qdrant/pgvector impls + contract tests
  store/            pgx + sqlc; migrations; repositories
  retrieve/         hybrid search, RRF, MMR, dedupe, context assembly
  llm/              Chat interface, prompt templates, token budgeting
  answer/           orchestration, citation binding, groundedness guard
  eval/             golden set runner, metrics, regression gate
  telemetry/        OTel traces/metrics, slog handlers
pkg/api/            public request/response types (stable, versioned)
deploy/             Dockerfile, compose.yaml, k8s manifests
docs/               this plan, ADRs, runbooks, API reference
testdata/           golden HTML fixtures + expected Markdown + expected chunks
```

### 4.2 The three interfaces that make the DB interchangeable

```go
// internal/index/store.go
type VectorStore interface {
    EnsureCollection(ctx context.Context, spec CollectionSpec) error
    Upsert(ctx context.Context, collection string, points []Point) error
    Delete(ctx context.Context, collection string, ids []string) error
    Search(ctx context.Context, collection string, q Query) ([]Hit, error)
    // Alias lets the pgvector impl emulate Qdrant's native aliasing.
    SwapAlias(ctx context.Context, alias, collection string) error
    Stats(ctx context.Context, collection string) (Stats, error)
    Close() error
}

type Query struct {
    Dense     []float32
    Sparse    *SparseVector   // nil ⇒ dense-only; impls that lack sparse fall back to lexical SQL
    Filter    Filter          // product, doc_type, lang, version — engine-neutral AST
    Limit     int
    Fusion    FusionMode      // RRF | DBSF | None
    MinScore  float32
}
```

```go
// internal/embed/embedder.go
type Embedder interface {
    Embed(ctx context.Context, texts []string, kind Kind) ([][]float32, error) // Kind: Document|Query
    Dimensions() int
    ModelID() string   // recorded on every chunk; a change forces a new generation
    MaxBatch() int
}
```

```go
// internal/llm/chat.go
type Chat interface {
    Stream(ctx context.Context, req Request) (iter.Seq2[Delta, error], error)
    ModelID() string
    ContextWindow() int
}
```

**Rule:** nothing outside `internal/index/qdrant` and `internal/index/pgvector` may import a
driver package. Enforce it in CI with `go-arch-lint` or a `depguard` linter rule (T-0.6) — this is
what actually keeps the abstraction honest over time.

### 4.3 Filter AST, not SQL strings

`Filter` must be an engine-neutral tree (`And`/`Or`/`Not`/`Eq`/`In`/`Range`) that each backend
compiles — to a Qdrant `Filter` protobuf, or to a parameterised `WHERE` clause. Do not let raw
predicates leak across the interface; that is how "swappable" quietly stops being true.

## 5. Data model

### 5.1 Postgres (system of record)

```sql
crawl_runs(id, started_at, finished_at, status, product, pages_seen, pages_changed, error)
documents(
  id uuid pk,                    -- uuidv5(canonical_url)
  canonical_url text unique,     -- normalized: no ?hl=, no trailing slash, no fragment
  product text,                  -- 'storage', 'run', 'pubsub'
  doc_type text,                 -- guide | reference | tutorial | sample | release-note
  title text, breadcrumb text[],
  lang text,                     -- natural language of the page
  etag text, last_modified text,
  content_hash bytea,            -- sha256 of extracted markdown
  markdown text,                 -- canonical extracted text; re-chunk without re-crawling
  fetched_at, indexed_at, deleted_at
)
chunks(
  id uuid pk,                    -- uuidv5(canonical_url + heading_path + ordinal)  ⇒ idempotent
  document_id uuid fk,
  ordinal int, heading_path text[], anchor text,
  content text, content_hash bytea,
  token_count int,
  code_lang text,                -- set when the chunk is predominantly a code block
  embedding_model text, generation int
)
index_generations(id, name, embedding_model, dims, chunk_count, status, promoted_at)
river_job(...)                   -- River's own tables
query_logs(id, question, filters, hit_ids, latency_ms, model, created_at)
feedback(id, query_log_id, rating, comment)
eval_runs(id, generation, suite, recall_at_k, mrr, groundedness, citation_accuracy, created_at)
```

`documents.markdown` is the highest-leverage column in the schema: it means changing the chunking
strategy or the embedding model is an **offline reindex**, not a re-crawl of Google.

### 5.2 Vector payload (both backends carry the same fields)

`chunk_id, document_id, canonical_url, anchor, product, doc_type, code_lang, heading_path,
title, generation, token_count`

Payload indexes on `product`, `doc_type`, `code_lang`, `generation` (Qdrant) / btree + GIN
(Postgres).

### 5.3 Chunking strategy

Parse with **`goldmark`** into an AST — never regex (this is analysis §2.5). Then:

1. Split at headings H1–H4; each section inherits the full breadcrumb
   (`Cloud Storage > Buckets > Create a bucket`).
2. Target **~700 tokens**, hard max ~1024, **~15% overlap** between adjacent prose chunks.
3. **Never split inside a fenced code block or a table.** If a code block alone exceeds the
   budget, emit it as its own chunk, prefixed with the breadcrumb and the immediately preceding
   paragraph so it retains context.
4. Tag code chunks with `code_lang` from the fence info string. This is what makes
   "show me the Go code for X" work (§1, library class).
5. Drop boilerplate: "Was this helpful?", feedback widgets, "Try it for yourself" footers.
6. **Embed** `breadcrumb + "\n\n" + content`; **store and display** `content` alone. Contextual
   prefixing measurably improves retrieval on documentation corpora and costs nothing.
7. Chunk IDs are `uuidv5(canonical_url + heading_path + ordinal)` ⇒ re-running the pipeline
   upserts in place instead of duplicating. This is what makes ingestion idempotent.

## 6. Reindexing and zero downtime

Embedding models change; chunking strategies improve. Both invalidate the whole index, so make
that a routine operation instead of an outage:

1. New generation `n+1` → write to collection `docs_v{n+1}` (Qdrant) or a new partition (pgvector).
2. Backfill from `documents.markdown` — **no crawling**.
3. Run the eval suite (§7) against `docs_v{n+1}`.
4. **Gate:** promote only if metrics are within regression tolerance of the live generation.
5. `SwapAlias("docs_live", "docs_v{n+1}")` — atomic.
6. Keep generation `n` for one cycle for instant rollback.

The API only ever reads through the alias `docs_live`. It never knows a generation number.

## 7. Retrieval pipeline

```
question
  → normalize + optional query rewrite (expand acronyms: GCS→Cloud Storage, IAM roles, etc.)
  → extract filter hints  (products mentioned, language mentioned → code_lang)
  → parallel:  dense search (k=50)   +   lexical/sparse search (k=50)
  → RRF fusion
  → cross-encoder rerank (top 50 → top 12)            [bge-reranker via TEI/Ollama sidecar]
  → MMR + per-document cap (max 2 chunks per URL)     [prevents one page crowding the context]
  → token-budgeted context assembly with [1][2][3] markers
  → LLM stream
  → citation binding + groundedness check
```

Two details that matter more than they look:

- **Per-document cap.** Without it, five chunks from one long page fill the whole context and the
  integration questions (§1) become unanswerable, because the second product never appears.
- **Lexical leg is not optional.** `roles/storage.objectAdmin`, `--ordering-key`,
  `google-cloud-pubsub` — exact identifiers are where dense retrieval is weakest and where users
  are most precise. This is the strongest argument for hybrid search in this domain.

## 8. Reliability design

| Concern | Mechanism |
|---|---|
| Crawler politeness | `golang.org/x/time/rate` per host, configurable (default 2 req/s), `robots.txt` honoured, real `User-Agent` with a contact URL |
| Transient failures | Exponential backoff + full jitter, capped retries, per-host circuit breaker |
| Partial failure | Per-URL status in `crawl_runs`; one bad page never aborts a run (fixes B2) |
| Unbounded work | Bounded channels + `semaphore.Weighted`; worker count from config |
| Poison jobs | River retries with backoff → dead-letter table → alert |
| Shutdown | `context` cancellation on SIGTERM, drain in-flight ≤30 s, then hard stop |
| Memory | Stream HTML parse; batch embeds; never load the corpus into a slice |
| Index corruption | Generations + alias swap + eval gate (§6) |
| Observability | OTel traces span crawl→extract→chunk→embed→index; RED metrics per stage; `slog` JSON |
| Health | `/healthz` (process), `/readyz` (Postgres + vector store + embedder reachable) |

## 9. Legal and attribution — a shipping blocker

Google Cloud documentation is **CC BY 4.0**; code samples are **Apache 2.0**. If a customer uses
this service, you must:

- attribute Google and **link back to the source page** on every answer (this is also the single
  best trust feature the product has — the citation requirement and the legal requirement are the
  same requirement);
- not imply Google endorsement, and keep Google trademarks/branding out of the product identity;
- preserve Apache 2.0 notices where code samples are reproduced;
- respect `robots.txt` and the site Terms of Service for the crawl itself.

Put this in `NOTICE`, in the API response envelope (`sources[].license`), and in the UI footer.
Get it reviewed before any external customer touches it.

## 10. Beyond prose docs — making the "libraries" promise real

The user-facing goal includes *"how to use their libraries"*. Guides alone will not carry that.
Phase 7 adds two more source types behind the same `documents` table:

- **Client library reference** (`cloud.google.com/{product}/docs/reference/{lang}/...`) — method
  signatures, parameters, types. Crawled the same way, `doc_type='reference'`, `code_lang` set.
- **Official sample repos** (`GoogleCloudPlatform/golang-samples`, `python-docs-samples`, …) —
  ingested from **git**, not HTTP: clone, walk, chunk each sample file whole with its region tags
  and README context, `doc_type='sample'`. Git gives you exact versions, licences and change
  detection for free, which is a much better deal than scraping.

Cross-service questions additionally benefit from a **service-relationship index**: a small table
of `(product_a, product_b, relationship, source_url)` mined from "Integrate with", "Triggers" and
architecture-centre pages. It is cheap to build and turns a hard retrieval problem into a filter.

## 11. Performance & stability targets (the definition of "shippable")

| Metric | Target |
|---|---|
| Crawl throughput | 500-page product in <3 min at 2 req/s/host, 8 workers |
| Incremental re-crawl | ≥90% of unchanged pages short-circuit on ETag/304 |
| Embedding throughput | ≥200 chunks/s sustained against the configured embedder |
| Full reindex, 500k chunks | <60 min, memory <1 GB RSS per worker |
| Retrieval p95 (no LLM) | <150 ms |
| Time to first token | <1.5 s p95 |
| Answer citation accuracy | ≥95% of cited URLs actually contain the claim (eval-measured) |
| Recall@10 on golden set | ≥0.85 |
| API availability | 99.5% monthly |
| Crawl run success | ≥99% of pages fetched; run fails loudly if <95% |
