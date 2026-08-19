# Post-migration wiki audit — HOLD

Observed through: 2026-08-15T01:45:05+09:00
Pinned live-vault commit: `f34c0cc8976`
Verdict: HOLD; do not declare the corpus healthy.

## Commit boundary

The cleanup/index lineage through `f16c10f` is preserved. Unsafe R_V commit
`9cdc6027` was reversed by `f34c0cc`. `f16c10f` and `f34c0cc` have the same
tree (`40e900d9b4dd3885bdf674776715c8c6baea44a8`), proving that the reversal
removed only the rejected 21-page patch and its log receipt.

## Remaining recovery residue

The latest backup set contains 1,461 paths and all remain live. Across them:

- 1,461 `orphan-recovery` tags;
- 1,461 `ideation_seeds` and 1,461 `adoption_hooks`;
- 1,457 `epistemic_status: orphan-recovered` markers;
- 1,445 `captured_by: wiki-orphan-upgrade-v1` markers;
- 543 `needs-source-hardening` markers;
- 540 self-provenance markers; and
- 213 detectable double-frontmatter files.

The block-strip migration skipped exactly 11 non-default-scope files: one
concept, seven `inter_agent`, and three `tooling` pages. Six orphan-upgrade
receipts and four external backup directories remain. They are evidence and
must not be bulk-deleted.

## Structural state

- Validator: exit 1; 1,789 checked, 226 files with issues, 1,563 clean.
- Core paths: 1,789 files but 1,788 unique slugs (`bridge-hypothesis` is
  duplicated).
- Backlink blocks: 1,671 balanced; 60 disagree with an independent
  non-generated graph, with 115 false extras.
- Independent link scan: 1,603 broken occurrences, 94 missing targets, at
  least 123 semantic orphans.
- The deleted recovery MOC accounts for 1,463 parsed broken occurrences.
- `index.md` is syntactically reproducible, but its 33-orphan claim is false
  because generated/recovery edges contaminate the metric.

## Semantic state

The R_V family remains stale after the safety reversal: `0.909`, causal-L27,
held-out `38% vs 8%`, and pooled six-of-eight claims remain across multiple
concepts. The exact rejected plan and review are preserved beside this report.

`karpathy-wiki-pattern.md` still describes untracked/absent
`knowledge_compiler` modules, nonexistent `dgc kb` commands, and a phantom
sleep-cycle integration. It should be replaced by the primary-source contract
and the implementation that actually exists, not retained as current fact.

## Safe ordering

1. Keep writers stage-only and preserve the Git baseline plus external
   backups.
2. Make generated backlinks non-semantic and reconcile them in reviewed
   batches of at most 25.
3. Repair authoritative hub claims through `chetana.integration.v2` plans with
   per-operation source and claim bindings.
4. Clean recovery residue by three-way comparison, not metadata heuristics.
5. Regenerate projections and require a truthful nonzero/zero validator gate.
