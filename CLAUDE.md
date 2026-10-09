# CLAUDE.md

## Git conventions

**Never put session data in commits, PR titles or PR bodies.** Specifically, do not add
`Claude-Session:` trailers or `claude.ai/code/session_…` links to anything pushed to this
repository. Session links are transient and meaningless to anyone reading the history later.

Commit trailers are limited to:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

PR bodies describe the change only — no session links, no generation footers.

## Orientation

- `docs/` holds the Go rewrite plan: analysis of the Python prototype, target architecture,
  roadmap, 47 tasks with acceptance criteria, and the skills matrix. Start at `docs/README.md`.
- The Python code at the repo root is the original prototype. It is superseded by the plan in
  `docs/` and is kept only for reference and A/B comparison during the rewrite.
- `docs/01-ARCHITECTURE.md` carries the standing design decisions (Postgres as system of record,
  pluggable `VectorStore` over pgvector/Qdrant). Change those via an ADR, not in passing.
