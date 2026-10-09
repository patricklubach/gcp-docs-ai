# 03 — Task List with Acceptance Criteria

Every task has an **ID**, a size (S ≤1d, M 2–3d, L 4–5d), dependencies, and acceptance criteria
written so that someone other than the author can verify them. "AC" bullets are checkable
statements, not aspirations.

Global definition of done, applied to every task: code compiles with `go vet` clean; `golangci-lint`
clean; tests pass with `-race`; exported symbols documented; no new hardcoded configuration;
public behaviour change reflected in `docs/`.

---

## Phase 0 — Foundations

### T-0.1 · Archive the prototype · S
Move the Python tree to `legacy/` with a README explaining what it was and which ideas were
carried forward (Analysis §5). Delete `.DS_Store`, add it to `.gitignore`.
- **AC1** `legacy/README.md` names the three techniques kept: devsite article-body targeting, nav-tree harvesting, HTML→Markdown-before-chunking.
- **AC2** `git ls-files | grep -c DS_Store` returns 0.
- **AC3** The Python code is still runnable from `legacy/` for A/B comparison during Phase 1.

### T-0.2 · Go module and repo scaffold · S
Create the layout from Architecture §4.1. Go 1.25+.
- **AC1** `go build ./...` succeeds on a clean clone with no network beyond module download.
- **AC2** Every `cmd/` binary responds to `--version` with build info from `runtime/debug.BuildInfo`.
- **AC3** `Makefile` provides `build test lint up down migrate eval` and each works.

### T-0.3 · Configuration layer · M
Typed config from file + env (`GCPDOCS_*`), validated at startup, precedence documented.
- **AC1** Starting with an invalid config fails within 1s with a message naming the offending field and why.
- **AC2** `gcpdocs config dump` prints the effective config with secrets redacted.
- **AC3** A grep for hardcoded `http://`, `localhost`, model names or `k=` outside `internal/config` and tests returns nothing.

### T-0.4 · Structured logging and telemetry · M
`log/slog` JSON handler; OpenTelemetry traces and metrics; request/run IDs propagated by context.
- **AC1** Every log line carries `trace_id`, `run_id` (ingest) or `request_id` (API).
- **AC2** No handler mutates a `slog.Record` (the B10 defect must not reappear); a test asserts two handlers receive identical records.
- **AC3** Traces from a crawl run appear in the local Jaeger/OTel collector with spans per pipeline stage.

### T-0.5 · Local dev environment · M
`compose.yaml` with Postgres+pgvector, Qdrant, Ollama, and an OTel collector.
- **AC1** `make up` on a clean machine reaches all-healthy in <3 min.
- **AC2** `gcpdocs doctor` checks every dependency and prints a green/red table with actionable remediation text per failure.
- **AC3** `make down` removes containers; `make down VOLUMES=1` also removes data.

### T-0.6 · CI pipeline and architecture enforcement · M
GitHub Actions: build, `go vet`, `golangci-lint`, `go test -race -cover`, `govulncheck`, container build.
- **AC1** A PR that fails any check cannot be merged (branch protection on).
- **AC2** `depguard` (or `go-arch-lint`) fails the build if `internal/index/qdrant` or `pgx` is imported outside its own package — verified by a deliberately bad commit in the PR that introduces the rule.
- **AC3** Coverage reported per package; the build fails if total drops more than 2 points.

### T-0.7 · ADRs · S
`docs/adr/`: 001 Go rewrite, 002 Postgres as system of record + pluggable vector store, 003 embedding model + generation strategy, 004 chunking strategy, 005 Go/Python sidecar boundary.
- **AC1** Each ADR states context, options considered, decision, consequences, and a revisit trigger.
- **AC2** ADR-002 records the pgvector-first / Qdrant-in-prod decision and names the benchmark (T-2.6) that would overturn it.

---

## Phase 1 — Ingestion

### T-1.1 · Polite HTTP fetcher · M
Shared client: timeouts, per-host `rate.Limiter`, `robots.txt` cache, identifying `User-Agent`, exponential backoff with full jitter, per-host circuit breaker, conditional GET (`If-None-Match` / `If-Modified-Since`).
- **AC1** Against a test server, 20 concurrent requests to one host never exceed the configured rate, measured over the run.
- **AC2** `robots.txt` `Disallow` is honoured; a disallowed URL is skipped and recorded with reason, not fetched.
- **AC3** Injected 429 with `Retry-After` is obeyed; injected 500s retry with growing, jittered delays up to the cap and then fail *that URL only*.
- **AC4** A 304 response returns a `NotModified` result without a body read.
- **AC5** Fetching is cancellable: `ctx` cancel aborts in-flight requests within 100 ms.

### T-1.2 · URL canonicalization · S
Normalize: strip fragments, `?hl=`, tracking params, trailing slash; lowercase host; resolve relative.
- **AC1** Table-driven test with ≥25 real devsite URL variants; all variants of one page map to one canonical URL (fixes B7).
- **AC2** `documents.canonical_url` has a unique constraint and ingestion never violates it.

### T-1.3 · Page discovery · M
Port the nav-tree technique (Analysis §5.2) plus sitemap support and a bounded same-product link crawl as fallback.
- **AC1** Given a product landing URL, returns the full deduplicated page set; for Cloud Storage guides that is within 5% of the human-counted nav entries.
- **AC2** Discovery never leaves the configured product path prefix or host.
- **AC3** If the nav selector matches nothing, discovery fails **loudly** with a distinct error — it does not silently return an empty list (fixes the prototype's silent-empty failure mode).

### T-1.4 · devsite extractor · L
`div.devsite-article-body` → Markdown, preserving heading levels, fenced code with language, tables, and links rewritten to absolute canonical URLs. Strip nav, feedback widgets, "Was this helpful", promos.
- **AC1** Golden-file tests over ≥20 checked-in real HTML fixtures spanning guides, references, tutorials and release notes; byte-exact expected Markdown.
- **AC2** Code fences retain their language tag; a fixture with 10+ snippets round-trips all of them.
- **AC3** Relative links become absolute canonical URLs.
- **AC4** Missing article body returns a typed error and writes **no** document (fixes B5/B6).
- **AC5** Extraction is pure: `Extract(html, url) (Document, error)` touches no filesystem or network.

### T-1.5 · Ingest orchestration and change detection · L
Worker pool over discovered URLs; store documents with hash/ETag; tombstone pages that disappeared; per-run statistics. Replaces `manifest.py` entirely.
- **AC1** A second run over an unchanged product re-embeds nothing and logs ≥90% short-circuits.
- **AC2** A page whose content changed is detected by content hash even when ETag is absent.
- **AC3** A page removed from the nav is marked `deleted_at` and its chunks are deleted from the vector store in the same run.
- **AC4** One failing page does not abort the run (fixes B2); the run summary lists per-URL failures, and the run exits non-zero if success is below the configured threshold.
- **AC5** Concurrency is bounded by config; a 500-page product completes in <3 min at 2 req/s/host with 8 workers.
- **AC6** `SIGTERM` mid-run drains and leaves the database consistent; a resumed run picks up where it stopped.

---

## Phase 2 — Storage and interchangeable index

### T-2.1 · Postgres schema and migrations · M
Schema from Architecture §5.1 via `golang-migrate` (or `goose`); `sqlc` for type-safe queries.
- **AC1** `make migrate` is idempotent; every migration has a tested `down`.
- **AC2** Migrations run automatically in CI against a fresh Postgres and against a populated one.
- **AC3** `documents.markdown` is populated for every document, enabling re-chunk without re-crawl.

### T-2.2 · `VectorStore` interface and filter AST · M
Interface and engine-neutral `Filter` tree from Architecture §4.2/§4.3.
- **AC1** The interface compiles with zero driver imports in `internal/index` root.
- **AC2** `Filter` supports And/Or/Not/Eq/In/Range over string and int payload fields.
- **AC3** Godoc on every method states idempotency and error semantics.

### T-2.3 · pgvector backend · L
HNSW index; dense search; lexical leg via `tsvector` + `ts_rank`; RRF fusion in SQL; alias emulated by a generation pointer table.
- **AC1** Passes the full contract suite (T-2.5).
- **AC2** `EXPLAIN ANALYZE` on the hot search path shows the HNSW index in use, not a seq scan — asserted by a test.
- **AC3** `SwapAlias` is atomic: concurrent readers see either the old or the new generation, never a mix.

### T-2.4 · Qdrant backend · L
Collections with named dense + sparse vectors; payload indexes; prefetch + `NewQueryRRF` native hybrid; native aliases; batched upserts.
- **AC1** Passes the identical contract suite (T-2.5).
- **AC2** Payload indexes exist on `product`, `doc_type`, `code_lang`, `generation`; verified by querying collection info in a test.
- **AC3** Batched upsert of 10k points completes without exceeding the configured memory ceiling.
- **AC4** Connection loss mid-upsert retries and does not duplicate points (stable IDs make this checkable).

### T-2.5 · Backend contract test suite · L
**The task that makes "interchangeable" a fact rather than a claim.** One suite, run twice via testcontainers.
- **AC1** The same test file runs against both backends with no backend-specific branches.
- **AC2** Covers: ensure/idempotent-create, upsert, re-upsert same ID (no duplicates), delete, dense search ordering, filtered search, hybrid search, alias swap, stats, empty-result, and error cases.
- **AC3** Both backends return the same top-5 IDs for a fixed corpus and fixed query vector.
- **AC4** The suite runs in CI on every PR in under 5 minutes.
- **AC5** Adding a third backend requires touching zero test files — proven by a stub in-memory backend that also passes.

### T-2.6 · Benchmark harness · M
Reproducible benchmark on the **real** corpus with **real** filters.
- **AC1** Reports p50/p95/p99 latency and recall@10 for both backends at 100k and 500k chunks, unfiltered and with a two-product filter.
- **AC2** Results committed to `docs/benchmarks/` with the hardware and corpus size stated.
- **AC3** The output is sufficient to confirm or overturn ADR-002; the ADR is updated with the outcome either way.

### T-2.7 · Job queue · M
River (Postgres-backed) for crawl/extract/chunk/embed/index jobs.
- **AC1** Jobs are idempotent: replaying any job produces no duplicate data.
- **AC2** Failures retry with backoff and land in a dead-letter table after the cap, with the error preserved.
- **AC3** `gcpdocs jobs status` shows queue depth, in-flight, failed; a metric is exported for each.
- **AC4** Worker shutdown finishes the current job or returns it to the queue — it never loses one.

---

## Phase 3 — Chunking and embedding

### T-3.1 · AST-based chunker · L
`goldmark` AST → heading-aware, code-safe chunks per Architecture §5.3.
- **AC1** **Property test:** across all fixture documents plus generated Markdown, no output chunk contains an unbalanced code fence and no fenced block or table is ever split. This is the single most important test in the project — it is the direct fix for the corpus corruption in Analysis §2.5.
- **AC2** Chunk IDs are stable: chunking the same document twice yields identical IDs; inserting a paragraph changes only affected chunks' ordinals downstream, not every ID.
- **AC3** Token counts respect target/max; overlap is present between adjacent prose chunks and absent around code chunks.
- **AC4** `code_lang` is set from the fence info string for code-dominant chunks.
- **AC5** Breadcrumbs are complete and correct on every chunk; a nested H4 carries its H1–H3 ancestors.
- **AC6** Boilerplate ("Was this helpful?", feedback widgets) appears in zero chunks across all fixtures.

### T-3.2 · `Embedder` interface and backends · M
Ollama, HF text-embeddings-inference, Vertex AI. Batching, retry, concurrency limit.
- **AC1** Batch size and concurrency come from config; a slow embedder applies backpressure rather than queueing unboundedly.
- **AC2** `ModelID()` and `Dimensions()` are recorded on every chunk and on the generation.
- **AC3** A dimension mismatch against the target collection is detected **before** any write, with a clear error.
- **AC4** Sustained throughput ≥200 chunks/s against the reference local embedder, reported by a benchmark.

### T-3.3 · Generations and alias promotion · M
Implements Architecture §6.
- **AC1** `gcpdocs reindex --generation n+1` builds from `documents.markdown` with zero network calls to Google.
- **AC2** `gcpdocs promote` refuses to swap when the eval gate (T-5.3) fails, and says which metric regressed.
- **AC3** Rollback to the previous generation completes in <10 s.
- **AC4** API traffic during a swap sees no errors and no mixed-generation results — asserted by a test that swaps under concurrent load.

---

## Phase 4 — Retrieval and answering

### T-4.1 · Query understanding · M
Normalization, acronym/alias expansion (GCS→Cloud Storage, GKE→Kubernetes Engine, …), product and language detection to populate filters.
- **AC1** A maintained alias table covers the top 50 GCP products and their common abbreviations.
- **AC2** "Show me the **Go** code for Pub/Sub" sets `code_lang=go` and `product=pubsub` filters.
- **AC3** Expansion never *removes* the original terms from the lexical leg.

### T-4.2 · Hybrid retrieval, fusion and diversification · L
Parallel dense + lexical, RRF, MMR, per-document cap.
- **AC1** Dense and lexical legs run concurrently; total latency ≈ max of the two, not the sum.
- **AC2** An exact-identifier query (`roles/storage.objectAdmin`) ranks the defining page in the top 3 — a case where dense-only measurably fails, documented in the test.
- **AC3** No more than 2 chunks from the same `canonical_url` reach the context.
- **AC4** Retrieval p95 <150 ms at 500k chunks, excluding LLM time.
- **AC5** A cross-product question returns chunks from **both** products; asserted on ≥10 golden integration questions.

### T-4.3 · Reranking · M
Cross-encoder rerank of top-50 → top-12 via a configurable sidecar, with a clean on/off switch.
- **AC1** Reranking can be disabled by config and the system degrades gracefully.
- **AC2** Measured recall@10 improvement on the golden set is reported; if it does not improve, the ADR records that and it stays off.
- **AC3** Sidecar unavailability falls back to fusion-only ranking with a warning metric — it never fails the request.

### T-4.4 · Context assembly and prompting · M
Token-budgeted assembly with numbered source markers; a grounded system prompt written for *this* product.
- **AC1** The prompt contains no residue from any tutorial (direct fix for B12); it is reviewed and versioned in `internal/llm/prompts/`.
- **AC2** Assembly never exceeds the model context window; it drops lowest-ranked chunks first and logs what it dropped.
- **AC3** When retrieval returns nothing above `MinScore`, the system answers "I don't have documentation covering that" and does **not** call the LLM for a free-form answer.
- **AC4** Prompts are versioned; a prompt change is visible in `query_logs` for attribution.

### T-4.5 · Citations and groundedness · L
Bind `[n]` markers to real sources; validate before returning.
- **AC1** Every returned answer includes a `sources[]` array with `url`, `title`, `anchor`, `product`, `license`.
- **AC2** Every `[n]` marker in the answer text resolves to an entry in `sources[]`; unresolvable markers are stripped and counted in a metric.
- **AC3** Citation accuracy ≥95% on the golden set (T-5.1), measured, not assumed.
- **AC4** Anchors deep-link to the correct heading on the live page — spot-checked by an automated test that fetches the anchor.

### T-4.6 · Chat and CLI surface · M
`Chat` interface with Ollama/OpenAI-compatible/Vertex backends; `gcpdocs ask` with streaming.
- **AC1** Correct protocol per backend — an OpenAI-compatible endpoint (e.g. LM Studio on :1234) is addressed with the OpenAI client, not the Ollama one (fixes B11).
- **AC2** `gcpdocs ask "..."` streams tokens and prints sources at the end.
- **AC3** `Ctrl-C` cancels the in-flight LLM request immediately.

---

## Phase 5 — Evaluation

### T-5.1 · Golden question set · L
≥150 questions with expected source URLs, spanning conceptual / integration / library classes.
- **AC1** Stored as version-controlled YAML: question, expected URLs, class, products, optional expected `code_lang`.
- **AC2** Class distribution is at least 40 / 50 / 60 across conceptual / integration / library.
- **AC3** Each entry names its author and date; a documented process exists for adding a question whenever a real user question is answered badly.

### T-5.2 · Metrics runner · M
recall@k, MRR, nDCG, citation accuracy, groundedness, answer latency.
- **AC1** `gcpdocs eval --suite golden` writes a JSON report and a human-readable summary table.
- **AC2** Results are persisted to `eval_runs` and comparable across generations.
- **AC3** `gcpdocs eval --compare gen7 gen8` prints a per-metric diff with per-question regressions listed.

### T-5.3 · Regression gate · M
- **AC1** CI runs the eval suite on any PR touching `chunk/`, `embed/`, `retrieve/`, `answer/` or prompts.
- **AC2** A drop >3 points in recall@10 or citation accuracy fails the build.
- **AC3** `gcpdocs promote` consults the same gate (T-3.3 AC2), so CI and promotion cannot disagree.
- **AC4** Demonstrated: a deliberate bad-chunking commit turns CI red, and reverting turns it green.

---

## Phase 6 — Service surface

### T-6.1 · HTTP API · L
`POST /v1/ask` (SSE streaming), `POST /v1/search`, `GET /v1/products`, `POST /v1/feedback`, `/healthz`, `/readyz`, `/metrics`.
- **AC1** An OpenAPI 3.1 spec is published and verified against the implementation in CI (contract test, not a hand-written doc).
- **AC2** SSE streams first token in <1.5 s p95 and terminates cleanly on client disconnect (server cancels the LLM call).
- **AC3** Structured errors with stable codes; no internal detail or stack traces leak to clients.
- **AC4** `/readyz` returns 503 when Postgres, the vector store or the embedder is unreachable — verified by killing each dependency in a test.

### T-6.2 · Auth, quotas and abuse protection · M
API keys, per-key rate limits, request size caps, prompt-injection hardening on retrieved content.
- **AC1** Unauthenticated requests get 401; over-quota gets 429 with `Retry-After`.
- **AC2** Keys are stored hashed; rotation is documented and tested.
- **AC3** Retrieved document text cannot alter system instructions — verified by a test using a fixture page containing injected instructions.

### T-6.3 · Web UI · M
Minimal chat UI: streaming answer, clickable sources, product filter, feedback buttons.
- **AC1** Sources are visible and clickable next to every answer.
- **AC2** Feedback posts to `/v1/feedback` and lands in the `feedback` table joined to the query log.
- **AC3** Attribution and licence notice are present in the footer (Architecture §9).

### T-6.4 · Graceful lifecycle · S
- **AC1** `SIGTERM` stops accepting new requests, drains in-flight ≤30 s, then exits 0.
- **AC2** In-flight SSE streams are closed with a terminal event, not dropped.

---

## Phase 7 — Coverage: references, samples, integrations

### T-7.1 · Client-library reference ingestion · L
- **AC1** Reference pages for ≥3 languages (Go, Python, Java) are ingested with `doc_type='reference'` and `code_lang` set.
- **AC2** Method signatures survive extraction intact — golden-file tested.
- **AC3** A signature lookup ("what arguments does `Bucket.Create` take in Go") returns the correct reference chunk in the top 3.

### T-7.2 · Sample-repo ingestion from git · L
Clone `GoogleCloudPlatform/golang-samples`, `python-docs-samples`, etc.; chunk each sample whole.
- **AC1** Ingestion is from git at a pinned commit, not HTTP scraping; the commit SHA is stored per document.
- **AC2** Region tags and the sample's README context are preserved with the code.
- **AC3** A sample file is never split mid-function.
- **AC4** Apache-2.0 licence metadata is recorded per sample and surfaced in `sources[].license`.
- **AC5** Re-running against a newer commit updates only changed files.

### T-7.3 · Service-relationship index · M
Mine "Integrate with" / "Triggers" / architecture-centre pages into `(product_a, product_b, relationship, source_url)`.
- **AC1** ≥200 relationships extracted across the indexed products.
- **AC2** Integration-class queries use it to seed product filters, and the eval suite shows measurable improvement on that class.
- **AC3** Relationships link to a source URL; none are model-invented.

### T-7.4 · Corpus freshness automation · M
- **AC1** Scheduled incremental crawls per product; cadence configurable.
- **AC2** A `corpus_staleness_seconds` metric per product, with an alert above threshold.
- **AC3** `GET /v1/products` reports each product's last-indexed timestamp so users can see how fresh an answer is.

---

## Phase 8 — Operations and hardening

### T-8.1 · Dashboards and alerts · M
- **AC1** Grafana board: crawl success rate, extraction success rate, queue depth, embed throughput, retrieval p95, TTFT, error rate, corpus staleness.
- **AC2** Alerts on: crawl run failed, extraction success <95%, dead-letter growth, `/readyz` failing, retrieval p95 breach, corpus stale.
- **AC3** Every alert links to a runbook section that says what to actually do.

### T-8.2 · Backup and restore · M
- **AC1** Automated Postgres backups with documented retention; Qdrant snapshots scheduled.
- **AC2** A restore drill is **performed and documented with timings** — not merely scripted.
- **AC3** Documented recovery path for total vector-store loss: rebuild from `documents.markdown`, with a measured duration.

### T-8.3 · Load and soak testing · M
- **AC1** Load test at 3× expected peak QPS sustains p95 targets.
- **AC2** A 24-hour soak shows flat memory and no goroutine leaks (`pprof` before/after attached to the report).
- **AC3** Behaviour under embedder/LLM outage is graceful degradation with clear errors, not cascading failure.

### T-8.4 · Security review · M
- **AC1** `govulncheck` and dependency scanning clean, running on a schedule.
- **AC2** Secrets come only from the environment or a secret manager; a repo scan for committed secrets is clean and enforced in CI.
- **AC3** Container runs as non-root with a read-only root filesystem.
- **AC4** Prompt-injection and PII handling reviewed and documented.

---

## Phase 9 — Documentation

### T-9.1 · README that works cold · M
- **AC1** A person who has never seen the repo goes clone → answered question in <30 min following only the README, **on a machine you do not control**. Verified with a real person; record who and when.
- **AC2** Prerequisites, hardware expectations and model sizes stated up front.
- **AC3** Every command in the README is executed by a CI smoke job, so it cannot rot.

### T-9.2 · Architecture and operations docs · M
- **AC1** `docs/` covers architecture, data model, the retrieval pipeline, and how to add a new vector backend (with the contract suite as the checklist).
- **AC2** Runbooks for: crawl failure, stale corpus, bad generation rollback, vector store down, embedder down.
- **AC3** ADR index is current; superseded ADRs are marked, not deleted.

### T-9.3 · API documentation · S
- **AC1** OpenAPI spec published with examples for every endpoint.
- **AC2** A copy-pasteable quickstart for `curl` and one Go client example.
- **AC3** Rate limits, error codes and the licence/attribution obligation are documented for API consumers.

### T-9.4 · Licence and attribution · S
- **AC1** `NOTICE` covers Google CC BY 4.0 documentation and Apache 2.0 code samples.
- **AC2** Every API answer and UI view carries attribution and a source link.
- **AC3** Reviewed before any external customer access (Architecture §9).

---

## Suggested execution order for the thin slice (first ~4 weeks)

```
T-0.1 → T-0.2 → T-0.3 → T-0.5 → T-0.6          foundations
      → T-1.1 → T-1.2 → T-1.3 → T-1.4 → T-1.5  ingestion, Cloud Storage only
      → T-2.1 → T-2.2 → T-2.3                  Postgres + pgvector only
      → T-3.1 → T-3.2                          chunking + embedding
      → T-4.2 → T-4.4 → T-4.5 → T-4.6          minimal retrieve + ask + cite
      → T-5.1 (30 questions) → T-5.2           enough eval to know if it works
```

Defer until after the slice answers its first correctly-cited question: T-2.4 (Qdrant),
T-2.5/T-2.6, T-4.3 (rerank), all of Phase 6, 7 and 8. Judge the slice on one question — *are the
citations right?* If they are, everything after this is tuning and scaling. If they are not, the
problem is upstream in chunking or extraction, and no amount of Phase 4 work will rescue it.
