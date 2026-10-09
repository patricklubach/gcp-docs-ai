# Golden question set

The measurement baseline for retrieval quality (task **T-5.1** in `docs/03-TASKS.md`).
Everything in Phase 4 and later is tuned against this file. If it is wrong, every number
downstream is wrong.

## Status

| | |
|---|---|
| Questions | 30 of the ≥150 target |
| Classes | 8 conceptual / 10 integration / 12 library |
| Expected URLs | 53 |
| **URLs verified** | **No — run `./verify-urls.sh` first** |

The seed was written from knowledge, in an environment that could not reach
`docs.cloud.google.com`. Treat every `expected_url` as a hypothesis until the verifier
passes. **Do not compute or report a metric against this file before then** — an unverified
golden set produces confidently wrong numbers, which is worse than having no numbers.

```bash
./verify-urls.sh          # exits non-zero if any URL fails
```

Re-run it on a schedule. Google moves pages, and a rotted golden set looks exactly like a
retrieval regression.

## Schema

```yaml
- id: integ-001                 # <class-prefix>-NNN, stable forever; never renumber
  class: integration            # conceptual | integration | library
  products: [storage, run]      # expected product filter hints (T-4.1)
  expected_code_lang: go        # library class only; drives the code_lang filter
  question: ...                 # exactly as a user would type it
  expected_urls: [...]          # ANY of these in top-k counts as a hit
  must_mention: [...]           # concepts a correct answer contains (groundedness, not recall)
  notes: >                      # what makes an answer wrong, for the human reviewer
```

`expected_urls` is deliberately *any-of*, not all-of: several pages often answer a question
legitimately. Where a question genuinely requires two sources, say so in `notes` and score it
in the groundedness rubric rather than by overloading recall.

## What the three classes are for

- **conceptual** — prose from Guides, single product. The easy case; a regression here means
  something basic broke.
- **integration** — two or more products. The hardest retrieval problem and the highest user
  value. These are what justify the per-document cap and metadata filtering
  (`docs/01-ARCHITECTURE.md` §7). `integ-001` is the canonical case: without a per-document
  cap, chunks of the Cloud Run overview crowd out Eventarc and the answer is unanswerable.
- **library** — needs working code. These fail hardest when chunking splits a fenced code
  block, so they are the end-to-end check on `docs/00-ANALYSIS.md` §2.5. Several pairs cover
  one topic in two languages (`lib-005`/`lib-012`) specifically to catch a broken `code_lang`
  filter.

## Adding questions

The set grows from **real failures**, not from imagination. Whenever the service answers a
genuine question badly:

1. Add it here with the URLs that *should* have been retrieved.
2. Note what the service got wrong in `notes`.
3. Confirm it fails, fix the cause, confirm it passes.

That is the regression loop. Target distribution at 150: 40 / 50 / 60.

Keep IDs stable — `eval_runs` rows reference them across generations, and renumbering destroys
historical comparability.

## Known weak spots in this seed

- **`lib-009` (Vertex AI / Gemini)** — the fastest-moving surface in the set. Expect it to rot
  first; re-verify each release cycle.
- **`lib-011` (ADC)** — lives under `/docs/authentication`, not under a product. Included on
  purpose to check that product-filter inference degrades gracefully when no product is named.
- **`integ-002` vs `integ-006`** — same data path (Pub/Sub → BigQuery) with and without
  Dataflow. They must not collapse into the same answer; if they do, that is a retrieval bug.
- **No negative cases yet.** The set has no question that *should* be refused. Add ~10
  out-of-scope questions (AWS, unrelated, or not in the corpus) before trusting the refusal
  behaviour required by T-4.4 AC3.
