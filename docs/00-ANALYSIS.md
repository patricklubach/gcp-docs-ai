# 00 — Current State Analysis

Audit of `gcp-docs-ai` @ `1cc857d` (14 commits, 2026-03-19 → 2026-04-15, ~750 LOC Python).

## 1. What exists today

| File | Role | Verdict |
|---|---|---|
| `scraper.py` | Entry point; crawls devsite nav, fetches pages async | Keep the *idea*, rewrite |
| `documentation.py` | `DocumentationPage`: HTML → Markdown → file | Keep the *idea*, rewrite |
| `markdown_doc.py` | Regex heading splitter + broken table parser | Delete |
| `md_parser.py` | Second regex Markdown parser (tables, code, lists, links) | Delete |
| `check.py` | Third copy of the heading splitter, as a top-level script | Delete |
| `database.py` | Chroma + `mxbai-embed-large`, indexes one hardcoded file | Delete |
| `rag.py` | LlamaIndex + Ollama `qwen3:4b`, separate index in `./storage` | Delete |
| `main.py` | LangChain REPL against Chroma retriever | Delete |
| `manifest.py` | MD5 manifest of `./data/*.md`, prints a diff | Concept survives, code does not |
| `logger.py` | Coloured stdlib logger | Delete (structured logging instead) |
| `test_md_parser.py` | One test, for a deleted module | Delete |

The repo is a **working prototype with three half-finished pipelines stacked on top of each
other**, not a service. There is no server, no API, no config, no CI, no container, no
persistence contract. That is fine for what it is — but it is also why "bring it into a
shippable state" means rewrite, not refactor. Roughly 60% of the current LOC is duplicated or
dead and will not be ported at all.

## 2. Architectural problems

### 2.1 Three competing RAG stacks, none of them wired together
- `database.py` + `main.py`: LangChain + Chroma, embeddings `mxbai-embed-large`, reads `./data`.
- `rag.py`: LlamaIndex + Ollama, embeddings `qwen3-embedding`, reads `./docs`, persists `./storage`.
- `scraper.py` writes to `./data`.

Two different embedding models, three different directories, two different index formats. Nothing
guarantees the index reflects what the scraper produced. Any answer quality measurement today is
measuring an accident.

### 2.2 No incremental update path — the core design flaw
`database.py:12` — `add_documents = not os.path.exists(db_location)`. Once `./chroma_langchain_db`
exists, **the index is never updated again**. New scraped pages are invisible. The only way to
pick up changes is `rm -rf` the database and re-embed the whole corpus.

`manifest.py` was clearly written to fix this, but `check_for_changes()` only *prints* `Added:` /
`Modified:` and then overwrites the manifest. Nothing consumes the diff. `main.py:8` calls it for
side effects that do not exist. On the first run it `return`s before comparing anything.

This is the single most important thing the rewrite has to solve: Google Cloud docs change
constantly, and a docs assistant that serves a stale snapshot is worse than no assistant.

### 2.3 Import-time side effects
`database.py` does the entire embed-and-index run at module import. `main.py:6` does
`from database import retriever`, so importing the module embeds the corpus. Nothing can be
unit-tested, and the REPL blocks on startup with no progress output.

### 2.4 Retrieval design is a stub
- Chunks are `item.title + " " + section` where section = "text between two blank lines"
  (`markdown_doc.py:24`). No token budget, no overlap, no minimum size. A one-line paragraph and a
  40-line `gcloud` snippet are both "a chunk".
- Metadata is `{"title", "path"}` — **there is no source URL**, so answers cannot link to docs.
  Meanwhile `main.py:26` instructs the model "always provide the source for your answers". The
  prompt promises something the data cannot deliver; the model will invent URLs.
- Fixed `k=5`, dense-only, no hybrid/lexical search, no reranking, no deduplication. Five chunks
  from the same page crowd out the one relevant page.

### 2.5 Regex Markdown parsing corrupts the corpus
All three parsers use `^(#+)\s+(.*)` with `re.MULTILINE`. Google Cloud docs are full of shell
snippets:

````
```bash
# Create a bucket
gcloud storage buckets create gs://my-bucket
```
````

`# Create a bucket` is matched as an H1 heading. Code blocks get shredded into fake sections, and
the fake section titles get embedded as if they were topics. `md_parser.py:60` compounds this:
`cb.strip('```')` is `strip` with a *character set*, so it strips any leading/trailing backtick,
space or newline — it will eat the language tag and mangle code ending in a backtick.

## 3. Concrete bugs

| # | Location | Bug | Impact |
|---|---|---|---|
| B1 | `scraper.py:76`, `scraper.py:105` | `extract_mobile_nav_links()` and `convert_article_to_md()` reference a global `url` defined only in the `__main__` block | `NameError` on any import or reuse; only works by accident as a script |
| B2 | `scraper.py:30` | `fetch()` catches everything and implicitly returns `None` | `run()` then calls `page.write()` → `AttributeError: 'NoneType'`, killing the whole batch after the fetches are done |
| B3 | `scraper.py:45` | Docstring says "using a semaphore to limit workers"; there is no semaphore | Unbounded concurrent tasks — a 400-page product opens 400 simultaneous connections to Google. Expect 429s and an IP block |
| B4 | `scraper.py` | No timeouts, no retries, no backoff, no `User-Agent`, no `robots.txt` | One slow page hangs the run forever; transient 5xx loses a page silently |
| B5 | `documentation.py:24` | `write()` opens the file *before* checking `self.md` | Zero-byte `.md` files for every page whose body was not found, polluting the corpus and the manifest |
| B6 | `documentation.py:38` | `convert_article_to_md()` returns `None` on missing `devsite-article-body`, logged as ERROR but the page is still "processed" | Silent data loss, no failure signal, no exit code |
| B7 | `documentation.py:18` | Slug is `"-".join(urlpath.split('/')[1:])` | `?hl=de`, trailing slashes, and `/docs/` vs `/docs` produce different files for the same page → duplicates in the index |
| B8 | `markdown_doc.py:44` | `add_table_from_str(self, text)` immediately overwrites `text` with a hardcoded Dark Souls table | Function is inert; the `pandas>=3.0.1` dependency exists solely for it |
| B9 | `markdown_doc.py:53` | Table regex `\| ([\w\s]+) \|` rejects any cell containing `.`, `-`, `/`, `(` | Fails on essentially every real GCP docs table |
| B10 | `logger.py:16-17` | Formatter mutates `record.levelname` and `record.msg` in place | Corrupts the record for every other handler; ANSI codes end up in log files; double-colouring on re-format |
| B11 | `main.py:18` | `OllamaLLM(base_url="http://127.0.0.1:1234")` — port 1234 is LM Studio, which speaks the **OpenAI** API, not Ollama's | Wrong protocol against that port; model id `qwen3.5-4b@q4_k_s` is LM Studio syntax |
| B12 | `main.py:22-24` | Prompt reads "Here are some relevant **reviews**: {reviews}" | Copy-paste residue from the tutorial in the header comment (a product-review demo). The model is told it is grading reviews while answering cloud questions |
| B13 | `manifest.py:26` | Returns before diffing on first run | First run after a scrape always reports nothing |
| B14 | `manifest.py:11` | `f.read()` whole file into memory; MD5 | Fine at current scale, wrong at corpus scale; MD5 should be SHA-256 |
| B15 | `check.py:47` | Top-level code reads a hardcoded `data/md_document.md` at import | Crashes on import; default content literal is `"benis"` |
| B16 | `test_md_parser.py:6` | Opens `md_document.md`, which is not in the repo (`data/` is gitignored) | The only test cannot pass on a fresh clone |
| B17 | `database.py:9` | Hardcoded `./data/buckets.md` | Indexes exactly one file out of the whole scrape |

## 4. Repo hygiene

- `.DS_Store` is committed.
- `pyproject.toml` description is still `"Add your description here"`; no `[project.scripts]`.
- `requests` (sync) and `aiohttp` (async) are both imported in `scraper.py`.
- `pandas`, `markdownify` and `html-to-markdown` are all declared; `markdownify` is unused,
  `pandas` serves only the dead B8 function.
- Both LangChain **and** LlamaIndex **and** ChromaDB are dependencies — three frameworks for one
  job, ~400MB of transitive deps.
- No CI, no linter, no formatter, no type checking, no `Dockerfile`, no `compose.yaml`.
- No configuration layer: every host, port, path, model name and `k` is a literal in source.
- No licence/attribution handling. Google Cloud docs are **CC BY 4.0** and code samples are
  Apache 2.0 — a service that serves this content to a customer must attribute and link back.
  This is a shipping blocker, not a nice-to-have. See `docs/01-ARCHITECTURE.md` §9.

## 5. What is actually good here — and worth keeping

Do not throw away the insight, only the code:

1. **Targeting `div.devsite-article-body`** is the right extraction anchor for Google devsite.
2. **Harvesting the nav tree** (`ul[menu="_book"]` inside `.devsite-mobile-nav-bottom`) is a
   genuinely clever way to enumerate a product's page set without a sitemap — the mobile nav is
   server-rendered, so it survives a plain HTTP GET. Port this technique directly.
3. **HTML → Markdown before chunking** is correct: it preserves headings, code fences and tables
   as structure that the chunker can respect, and it is far cheaper to store and re-chunk than HTML.
4. **A content manifest for change detection** is the right instinct — it just needs to drive an
   incremental pipeline instead of `print()`.
5. **Local-first inference** (Ollama/LM Studio) keeps cost and data-residency simple.

## 6. Headline conclusion

Ship-blocking gaps, in priority order:

1. No incremental indexing (§2.2) — the corpus is frozen at first index.
2. No source URLs in metadata (§2.4) — citations are impossible, so answers are unverifiable.
3. Chunking destroys code blocks (§2.5) — and code is what users actually need from GCP docs.
4. No concurrency control or politeness in the crawler (B3, B4) — will get the IP blocked.
5. No retrieval quality measurement at all — no golden set, no metrics, no regression gate.
6. No service surface — it is a REPL, not something a customer can query.

The rewrite plan addresses these in that order.
