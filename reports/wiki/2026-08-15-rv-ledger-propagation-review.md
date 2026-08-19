# R_V propagation plan review — HOLD

Date: 2026-08-15 (Asia/Tokyo)

Plan: `2026-08-15-rv-ledger-propagation.json`
Plan schema: `chetana.integration.v1` (retired after this review)
Reviewed scope: 21 pages, 54 operations, 61 exact replacements

## Verdict

Do not apply this plan. Its original dry run satisfied the v1 source hash,
target hashes, and exact replacement counts, but it did not satisfy the
semantic proof obligations needed for promotion.

## Blocking findings

- The plan binds only `02_CONTRADICTIONS_REGISTER.md` while introducing values
  from `00_MASTER_LEDGER.md`, including M024, M046, and M093/C26.
- It conflates the historical whole-residual behavioral intervention described
  by `causal-validation.md` with the locked L27 `v_projection` metric
  intervention. These must remain separate experiment lineages.
- `three-stage-relay-architecture.md` would remain internally contradictory.
  Canonical M043/M044 falsify relay specificity, while several old relay claims
  would survive the patch.
- C29's architecture rows remain disputed/non-poolable. The plan incorrectly
  uses stronger words such as "retracted" and leaves stale tables and counts in
  place.
- Bare `0.909` to `0.904` substitutions preserve host claims that overgeneralize
  M015. The canonical result is threshold-free, Mistral `hook_v`, within-corpus,
  and `n=196`; it is not a universal detector result.
- The plan leaves other known stale quantities, including `g=-1.47`,
  `d=-1.85`, `754 prompts`, disputed dual-layer ablations, and `-4.51`.

## Required replacement

The compiler schema was advanced to `chetana.integration.v2`. Every operation
must now bind its exact evidence source IDs and claim IDs. A replacement plan
must bind both ledgers, replace complete scoped evidence blocks rather than
isolated numerals, preserve experiment identity, and pass an independent
semantic review after rebasing onto current page hashes.

## Live-vault incident and recovery

Another concurrent process applied the rejected v1 plan as live-vault commit
`9cdc6027`. A reverse-patch check passed for exactly its 21 concept pages and
`log.md`; no successor commit existed and the vault was clean. The unsafe
commit was then reversed by recoverable commit `f34c0cc`, preserving the prior
cleanup, backlink, and index commits unchanged.
