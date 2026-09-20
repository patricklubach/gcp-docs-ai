# 02 — Roadmap

Nine phases. Each has a **demo** (what you can show at the end) and an **exit gate** (what must
be objectively true to move on). Do not skip gates; the prototype's problems all come from
skipped gates.

Sequencing principle: **make the corpus correct before making retrieval clever, and make
retrieval measurable before making it clever.** The prototype's real failure was tuning a
pipeline whose inputs were already corrupt.

---

### Phase 0 — Foundations (1 week)
Repo scaffold, config, CI, containers, ADRs. No product behaviour.

- **Demo:** `make up` starts Postgres + Qdrant + Ollama; `gcpdocs doctor` reports all green.
- **Exit gate:** CI runs build + vet + lint + race tests on every PR and is red on failure;
  ADR-001..004 merged; zero hardcoded hosts/models/paths anywhere in the tree.

### Phase 1 — Ingestion that is correct (2 weeks)
Crawler and extractor. The thing the prototype got closest to, done properly.

- **Demo:** `gcpdocs crawl --product storage` fills `documents` with canonical URLs, clean
  Markdown, ETags and hashes; re-running it fetches almost nothing.
- **Exit gate:** golden-file tests over ≥20 real devsite pages; ≥99% extraction success on a
  full product; zero empty documents; re-crawl of an unchanged product does ≥90% 304s; run
  survives injected 429/500/timeout without losing a page.

### Phase 2 — Storage and the swappable index (2 weeks)
Postgres schema + `VectorStore` with both backends and a shared contract suite.

- **Demo:** the identical ingest run indexed into pgvector, then into Qdrant, by changing one
  config value; both answer the same search identically.
- **Exit gate:** contract test suite passes against **both** backends in CI (testcontainers);
  `depguard` blocks driver imports outside their package; idempotency proven — running ingest
  twice yields the same chunk count.

### Phase 3 — Chunking and embedding (1.5 weeks)
AST-based, code-safe chunking. Batched embedding with generations.

- **Demo:** a page with 12 code blocks chunks with every block intact and `code_lang` set.
- **Exit gate:** property test — *no chunk ever splits a fenced code block or a table*;
  chunk IDs stable across reruns; ≥200 chunks/s embedding throughput; generation + alias swap
  working end to end.

### Phase 4 — Retrieval and answering (2 weeks)
Hybrid search, RRF, rerank, MMR, citations, streaming.

- **Demo:** `gcpdocs ask "how do I trigger Cloud Run from a GCS upload"` streams a cited answer
  drawing on **both** products.
- **Exit gate:** every answer carries ≥1 resolvable citation; per-document cap enforced;
  retrieval p95 <150 ms; refuses to answer rather than guessing when retrieval returns nothing.

### Phase 5 — Evaluation harness (1 week) — *do not defer this*
Golden set, metrics, regression gate in CI.

- **Demo:** `gcpdocs eval` prints recall@10, MRR, citation accuracy, groundedness; a deliberately
  bad chunking change makes CI fail.
- **Exit gate:** ≥150 golden questions across all three answer classes (§1 of Architecture);
  eval runs in CI on every retrieval-touching PR; promotion of a new generation is blocked on it.

> This phase is placed here deliberately. Every later tuning decision — reranker on/off, chunk
> size, hybrid weights, model swap — is unfalsifiable without it. Building it after the tuning
> means redoing the tuning.

### Phase 6 — Service surface (1.5 weeks)
HTTP API, streaming, auth, rate limits, a thin web UI.

- **Demo:** a customer opens the UI, asks a question, gets a streamed answer with clickable
  source links and can rate it.
- **Exit gate:** OpenAPI spec published and matching the implementation; authn + per-key rate
  limiting; graceful shutdown; `/readyz` reflects real dependency health.

### Phase 7 — Coverage: references, samples, integrations (2 weeks)
Client-library reference docs, git-ingested sample repos, service-relationship index.

- **Demo:** "Show me Go code to publish to Pub/Sub with an ordering key" returns real, compiling
  sample code with a link to the sample repo at a pinned commit.
- **Exit gate:** ≥3 languages of reference docs indexed; sample ingestion from git with licence
  metadata; library-class golden questions ≥0.80 recall@10.

### Phase 8 — Operations and hardening (1.5 weeks)
Observability, backups, runbooks, load test, security review.

- **Demo:** a Grafana board showing crawl, index and query health; a restore-from-backup drill.
- **Exit gate:** OTel traces span crawl→answer; alerts on stale corpus, failed runs, error rate,
  latency; documented and *rehearsed* backup/restore for Postgres **and** Qdrant; load test at
  3× expected peak; dependency and secrets scanning clean.

### Phase 9 — Documentation and launch (1 week)
README that works on a cold clone, architecture docs, runbooks, `NOTICE`, ADR index.

- **Exit gate:** a person who has never seen the repo goes from clone to answered question in
  <30 minutes following only the README, on a machine you do not control. Test this with a real
  human — it is the only honest measure.

---

## Timeline

~15–16 weeks for one experienced engineer; ~9–10 weeks for two working in parallel
(natural split: ingestion/storage vs retrieval/serving, converging at Phase 4).

**Recommended first milestone — "thin slice", ~4 weeks:** Phases 0–2 plus minimal 3 and 4 for a
*single product* (Cloud Storage), pgvector only, CLI only. It proves the whole pipeline end to
end and will teach you more about the real problems than any amount of further planning. Qdrant,
the API, samples and the web UI all come after that slice answers its first correctly-cited
question.

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Google changes devsite HTML structure | High | Ingestion silently degrades | Golden fixtures + extraction-success alarm; fail the run below 95% |
| Crawl gets rate-limited or IP-blocked | Medium | Total ingestion outage | Politeness limits, `robots.txt`, backoff, contactable User-Agent; keep `documents.markdown` so you can rebuild without re-crawling |
| Retrieval quality plateaus below usefulness | Medium | Product is not shippable | Phase 5 first; tune against numbers, not vibes |
| Embedding model swap invalidates index | Certain, eventually | Downtime if unplanned | Generations + alias swap (Architecture §6) — designed in from the start |
| Go RAG ecosystem gaps cost time | Medium | Schedule slip | Keep rerank/embed behind HTTP interfaces; use proven sidecars rather than reimplementing |
| CC BY attribution missed before customer launch | Low | Legal exposure | Phase 9 gate + `NOTICE` + per-answer `sources[].license` |
| Two-DB complexity slows the team | Medium | Schedule slip | Start pgvector-only; Qdrant is Phase 2 and optional to promote |
