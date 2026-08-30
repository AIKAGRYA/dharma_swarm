---
title: "Karpathy Wiki Pattern — local conformance"
confidence: 0.90
sources:
  - https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
  - https://github.com/AIKAGRYA/dharma_swarm/blob/3b0f0bacafe2adb4ccecc8111851d12a5ebcb35f/reports/wiki/sources/2026-08-15-chetana-compiler-audit.md
stale_after: "2026-09-15"
related:
  - karpathy-llm-wiki
  - hybrid-retriever
  - semantic-digester
status: draft
para: resource
domain: computational
---

# Karpathy Wiki Pattern

This is dharma_swarm's local conformance report for Karpathy's LLM-wiki
pattern, not a restatement of the upstream source. The source contract is in
[[karpathy-llm-wiki]]. The local test is whether new evidence can safely revise
existing knowledge and whether readers actually use the maintained result.

## Conformance map — 2026-08-15

| Upstream capability | Local mechanism | Honest status |
|---|---|---|
| Immutable raw sources | Chetana `ingest` creates a staged derivative and records a source path | **Missing:** no hashed immutable raw-source custody |
| Integrative ingest | `chetana compile` evaluates an explicitly enumerated multi-page plan | **Bounded prototype:** no affected-page discovery or scheduled integration |
| Mutable current wiki | Content-hashed exact replacements in five allowed article layers | **Implemented on the fix branch** for reviewed legacy-vault batches |
| Evidence-aware correction | Operation → claim → evidence → exact-locator bindings plus operator-configured evidence roots | **Partial:** the filesystem capability is bounded, but entailment and the reviewer are not authenticated |
| Cross-references | Marker-bounded backlinks derived from authored, non-code wikilinks and explicit `related:` metadata | **Implemented on the fix branch;** dry-run by default |
| Index and log | Existing index plus append-only typed receipts | **Partial:** approval refreshes both atomically; arbitrary compiler batches need an explicit projection step |
| Periodic lint | Validator and stage-only distill monitor return nonzero on violated invariants | **Implemented but red** on the current corpus/input seam |
| Query with citations | Reader and search return pages/hits with provenance | **Partial:** no cited answer synthesis or automatic query-to-compile loop |

The branch implementation and this status page are not proof of a living loop.
They define a safer integration seam that still has to be merged, connected to
genuine input, and exercised end to end.

## The bounded compiler prototype

The current transition is:

```text
external source (not yet held in immutable raw custody)
  -> staged derivative
  -> explicitly enumerated integration plan
  -> dry-run diff
  -> recorded reviewer-name attestation
  -> descriptor-anchored staged batch
  -> pages and operation receipt committed or rolled back together
```

`ingest` does not overwrite a current article. A v2 plan may name up to 50
pages. Before apply, the evaluator checks:

- the plan hash and every local evidence-file hash;
- a unique evidence locator containing the exact claim token;
- an explicit operation/claim/evidence binding;
- an audited-source or canonical-ledger capability minted from an
  operator-configured evidence root for every canonical write;
- each target hash, bounded path, and symlink boundary;
- exact old-text occurrence counts and mode-specific edit shape; and
- a nonempty reviewer name.

Plan and evidence bytes are revalidated at the transaction's final validation
point; evidence drift rolls the pages and receipt back together.

`observed_at` is checked only as a zoned, non-future plan field; it is not bound
to file modification time. A reviewer name is recorded, not authenticated.
Authority labels are declared by the plan, but they authorize a write only when
the evidence path is also confined to an operator-configured audited-source or
canonical-ledger root. That is a bounded filesystem capability, not proof that
the cited text entails the replacement. This is therefore a locator-bound,
reviewer-attested evaluator prototype—not yet a semantic authority typechecker.

The mode distinction is nevertheless real evaluator behavior. Evidence declared
as `agent-inference`, `operator`, `primary-source`, or `verified-runtime` cannot
write a canonical article in any mode. For an allowed audited or ledger source,
`extend` and `qualify` must preserve the old text and append; `retract` must
preserve claim genealogy and mark the claim retracted, superseded, or withdrawn.
The receipt retains evidence observation times and exact locators, page
before/after hashes, and each operation's mode, claim bindings, replacement
hashes, and expected count. Pages and the receipt share the same staged,
rollback-capable batch. If a signed trust manifest exists, standalone compiler
and backlink writes fail closed until page and manifest changes can be
transacted together.

## Links are projections, not evidence

Authored prose wikilinks and explicit `related:` metadata create semantic edges.
Wikilinks inside fenced code, inline code, generated backlink markers, or
frontmatter marked `epistemic_status: orphan-recovered` (or tagged
`orphan-recovered`) do not. A generated backlink block therefore cannot
manufacture graph connectivity or become evidence for itself.

Planning is read-only. Apply rechecks the configured corpus snapshot, preserves
file modes, serializes cooperative writers, and confines traversal and swaps to
held directory descriptors without following symlinks. It also avoids
overwriting a non-cooperative concurrent edit during rollback. Each file swap is
atomic, but the batch is not crash-atomic across the filesystem; rollback is the
bounded recovery mechanism. Both scoped and unscoped CLI migrations stop above
25 changed pages.

## Runtime health is not activity

The scheduled distill process is now stage-only. It reports zero live writes
and returns `attention_needed` when non-cron input is older than the freshness
SLA. A scheduler invocation that sees no eligible sessions is not evidence that
integration occurred. The validator likewise returns nonzero when schema
defects exist.

The live system is still unhealthy:

- no genuine source currently enters the integration seam;
- immutable raw custody and affected-page discovery are absent;
- legacy schema, broken-link, and recovery-residue defects remain;
- the trusted concepts manifest is absent;
- query produces search results, not a synthesized cited answer; and
- the wiki's write-heavy/read-light demand-side gap remains: durable knowledge
  has little value if agents do not consult it during work.

The first broad R_V plan was rejected by semantic human review because its prose
outran its evidence. It was then mistakenly applied by a concurrent process and
reverted. The compiler did not reject that v1 plan, and the unsafe prose was
briefly live. That incident is a regression fixture for the v2 binding model,
not a success claim.

## What this pattern does not mean

- It is not anti-search or anti-retrieval over the compiled corpus.
- More pages, backlinks, density, or a lower orphan count do not establish
  knowledge quality.
- A scheduler firing is not proof that integration happened.
- An answer, model consensus, or agent confidence is not authority by itself.
- Obsidian, a provider, a command namespace, and a page-count target are local
  choices rather than Karpathy requirements.

## Acceptance target for a living wiki

For a new authoritative correction, a complete future loop should discover all
dependent current claims, produce a reviewable evidence-bound plan, preserve
raw custody, apply only after real review, refresh derived projections, and
finish with lint and query checks. A zero-input cycle must be red once its input
freshness SLA is exceeded; independent lint failures remain red on their own.
None of affected-page discovery, raw custody,
automatic projection refresh for arbitrary compiler plans, cited-answer
synthesis, or idempotent recurring integration is claimed as implemented today.

## Backlinks
