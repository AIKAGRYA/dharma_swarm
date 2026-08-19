# Chetana integrative-compiler implementation audit

Observed: 2026-08-15T03:05:00+09:00

Repository: `AIKAGRYA/dharma_swarm`

Candidate branch: `fix/karpathy-wiki-metabolism-20260815`, based on
`a5a61b73c8848b86664f9d5bbcf21986df43c02c`. The implementation was not merged
when this audit was written, so branch behavior is not evidence of a deployed
recurring metabolism loop.

Audited implementation hashes:

- `wiki_compiler.py`:
  `a4036e04f8480b494e8da43bd329549b46f41950e09f3d58cd16a3c1822d0e0f`
- `backlinks.py`:
  `199a46ae037a98729012d407d7733cf4232645663bae80c7f4cc8222bc0dcab9`
- `backlink_markdown.py`:
  `9a77d1ec946695f06a17dd07a23a864c55b03c0c97abb69d2d38cc6399ed07bc`
- `safe_write.py`:
  `98429749e5977eb82299ffb930cdc3e27774a21f65dfde905a23a51cb4e1bbdc`
- `cross_update.py`:
  `40e947adddf7a71761cb2103f6bb0034bef869cd9cb5793b25b30773b9958f14`
- `wiki_log.py`:
  `6a79ce63c70db6bd05a652367725395f6ed8bdee637efa09236a932f2e545985`
- `cli.py`:
  `a31b3dc9676fd5ad8e6c7eb1973e15c5d78953d5e1d2d52fe7b68b16cf601d21`
- `promote.py`:
  `f16d67bd90d1905c04ab6bb502c64d6f2c4a4a048e9647acd336f1549c1d6a96`

Operational-file hashes:

- `/Users/dhyana/.dharma/scripts/wiki_lib.py`:
  `474c38b25da4217a3d91e7e8a16384690a53c67a6baabb893c60ab19c0d521cf`
- `/Users/dhyana/.hermes/scripts/wiki_distill.py`:
  `026f191041419a5ecc904f554394c4ff6e16c5fad3893e043d8f8aeb4adcd829`
- Hermes job `af871fdb8c42` (`wiki-knowledge-distill`) normalized prompt:
  `eea9a69b5b574f5283e2b256cb18a744a5d1065b9deac6f03562d433667f30f1`
  (`jobs.json` has runtime counters and timestamps, so its whole-file hash is
  intentionally not treated as a stable implementation identity.)
- `/Users/dhyana/chambers/wiki_graph.html`:
  `aba6a0713d6ed00af93c3d0e185cdf9df1e9e76f25778375ac1aac70af82f119`

Verification at the audited revision:

```text
pytest dharma_swarm/chetana/tests -q
165 passed in 4.83s

pytest tests/test_chetana_markitdown_document_ingest.py \
  tests/test_chetana_staging_boundary.py \
  tests/test_chetana_verify_production.py \
  tests/test_wiki_trust_manifest.py \
  tests/test_wiki_vector_live_gate.py -q
79 passed, 4 dependency warnings in 2.83s
```

## Audited claims

- **IMPL01 — Capture remains separate from integration.** Existing `ingest`
  creates a new staged derivative. It does not provide hashed immutable
  raw-source custody and does not discover or revise affected current pages.
  The new integration seam begins with an explicitly enumerated
  `chetana.integration.v2` plan (`wiki_compiler.py:48-50,227-234,366-405`).

- **IMPL02 — Canonical write scope is bounded and dry-run-first.** A plan names
  at most 50 markdown pages under `concepts`, `connections`, `mocs`, `research`,
  or `tooling`; target and source hashes, exact replacement counts, path and
  symlink bounds, and a nonempty reviewer-name field are checked before apply.
  Plan and evidence bytes are checked again at final transaction validation.
  The reviewer string is recorded but not authenticated
  (`wiki_compiler.py:49-51,199-224,227-234,366-405,409-659,818-878`).

- **IMPL03 — Evidence binding is evaluator structure, not entailment proof.**
  Every operation carries explicit evidence/claim bindings. Each claim token
  must occur inside one unique locator in the hashed UTF-8 evidence bytes.
  Canonical writes require evidence declared as `audited-source` or
  `canonical-ledger` and confined beneath an operator-configured root. These are
  syntactic and filesystem-capability checks; they do not prove that the cited
  language entails the replacement (`wiki_compiler.py:61,73-106,158-195,
  236-283,685-796`).

- **IMPL04 — Edit modes have executable shape constraints.** `extend` and
  `qualify` preserve the old bytes and append; `retract` preserves claim
  genealogy and marks status; canceling operation sequences are rejected.
  Evidence declared as agent inference, operator input, primary source, or
  verified runtime cannot directly rewrite a canonical article in any mode
  (`wiki_compiler.py:165-195,236-283,871-873`).

- **IMPL05 — Apply is descriptor-confined and rollback-capable, not
  crash-atomic.** The writer opens path components without following symlinks,
  binds the transaction to a caller-captured directory identity, stages every
  output, checks the full expected corpus and membership, rechecks mappings and
  bytes after replacements, and rolls back only transaction-owned outputs.
  Compiler pages and their typed log receipt share that batch. Active or
  concurrently appearing trust manifests fail closed. A machine crash between
  file renames is not claimed to be a filesystem-wide atomic transaction
  (`safe_write.py:64-335`; `wiki_compiler.py:450-659`).

- **IMPL06 — Backlinks are derived projections.** Semantic edges come from
  authored body wikilinks and explicit `related:` metadata. Fenced/inline code,
  marker-generated backlink blocks, and `related:` fields explicitly marked or
  tagged `orphan-recovered` are excluded. Planning is read-only; apply pins the
  full scanned corpus, refuses batches above 25 pages, refuses signed pages
  outside the signature-preserving cross-update path, and fails on unresolved
  manifest governance (`backlinks.py:162-280,281-388`;
  `backlink_markdown.py:43-120`).

- **IMPL07 — Approval and its projections commit together.** `approve_atom`
  prepares the human-reviewed v2-signed bytes, then one wiki-root transaction
  creates or replaces the trusted concept, removes the exact pending source,
  updates the affected backlink closure and exact generated index row, and
  appends one receipt. Every changed approved page is re-signed after its
  generated backlink block changes. A failure returns `INTEGRATION_BLOCKED`
  and rolls those writes back. Curated index prose is not treated as a generated
  row. Active signed manifests still fail closed because page-plus-manifest
  signing is not implemented (`promote.py:219-440`;
  `cross_update.py:54-368,371-435`).

- **IMPL08 — Lint and no-input health are truthful but currently red.**
  `wiki_lib.py` now returns nonzero when validation finds defects
  (`wiki_lib.py:227-253`). The distiller writes candidates only to staging,
  records `live_writes: 0`, and returns nonzero when its non-cron input freshness
  SLA is violated (`wiki_distill.py:231-252,275-380`). This does not connect a
  genuine input source to the compiler or prove recurring integration.

- **IMPL09 — The reader is useful but is a static compiled view.** The audited
  HTML embeds article bodies, renders escaped Markdown and live wikilink
  navigation, exposes node/table search, and does not synthesize cited answers
  (`wiki_graph.html:526-596,646-705`). Its embedded extraction timestamp is
  2026-08-13, so reader availability is not evidence that the wiki is current.

- **IMPL10 — The live acceptance state remains unhealthy.** The post-migration
  audit records 226 schema-invalid core files, recovery residue, broken and
  disputed links, no trusted concepts manifest, and no genuine current input
  seam. The rejected R_V v1 batch was briefly applied by a concurrent process
  and reverted; neither incident is claimed as compiler success. See
  `reports/wiki/2026-08-15-post-migration-audit.md` and
  `reports/wiki/2026-08-15-rv-ledger-propagation-review.md`.

## Explicit non-claims

This audit does not claim immutable raw custody, affected-page discovery,
natural-language entailment checking, authenticated reviewer identity,
page-plus-signed-manifest transactions, automatic index refresh from arbitrary
compiler plans, cited-answer synthesis, crash-atomic multi-file writes, a live
source input seam, or a scheduled end-to-end integration loop. Those remain
acceptance work rather than documentation gaps.
