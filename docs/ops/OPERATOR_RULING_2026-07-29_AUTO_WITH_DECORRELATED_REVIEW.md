# Operator Ruling — 2026-07-29 — DOOR = AUTO_WITH_DECORRELATED_REVIEW

**Status:** ratified operator ruling, recorded verbatim. Tier 2 surface —
operator hand-merge forever; no automation may amend this record.
**Provenance:** delivered by the operator in the walking-mode execution
prompt of 2026-07-29 (session of record: the graph-of-loops implementation
session; design doc `docs/plans/GRAPH_OF_LOOPS_DESIGN_2026-07-29.md`,
PR #1156). Supersedes the TWO_TIER framing of the earlier ruling-amendment
draft, per its own §0.
**Implementation:** `scripts/governance/automerge_tier_policy.json` (frozen
policy), `scripts/governance/check_automerge_tier_policy.py` (required
guard), token rename in `scripts/runtime/pr_merge_control.py`.

---

## §0 as ratified (verbatim)

> **DOOR = AUTO_WITH_DECORRELATED_REVIEW.** The operator authorizes
> AI-executed merges to main for Tiers 0–1 (defined in §5), conditional on
> the review architecture in §§5–9. Merge Master Mike is the sole merge
> executor, bound by policy + structured review verdicts. Tier 2 (the
> referee layer) is operator hand-merge forever.
>
> **TOKEN VERDICT:** the CI-synthesized `merge-pr-<N>` confirmation
> (pr_merge_control.py, ~line 1801) currently claims operator consent it
> never received. Rename it `automerge-policy-pass-<N>`, emitted only when
> policy + review verdicts pass. Under this ruling the token becomes
> honest: it asserts machine policy and decorrelated verdicts, and claims
> nothing about the operator.

## Tier table as ratified (§5, condensed to the binding facts)

- **Tier 0** — docs, test additions, formatting-only, config comments. One
  decorrelated review. Diff ≤ 300 lines.
- **Tier 1** — source code, refactors, dependency bumps, lane outputs. Two
  decorrelated reviews (different model families from the author, and from
  each other where routing allows). Full CI green on required contexts,
  coverage non-regression, no test deletion without reviewer sign-off
  naming each deleted test. Diff ≤ 600 lines; larger → split or escalate.
- **Tier 2** — referee layer, operator hand-merge FOREVER. The binding
  path list lives in `scripts/governance/automerge_tier_policy.json`
  (`tiers.tier2.paths`) — that file is the policy of record; this prose is
  a pointer, not a second copy.
- Rate limit: max 20 automerges/day initially, tunable only via Tier-2
  change (operator hand-merge).

## Decorrelation, disagreement, post-merge anchors, canaries (§§6-9)

Ratified as specified in the execution prompt: reviewer family ≠ author
family; context isolation (diff + tests + receipts + CI run IDs only —
never the author's narrative); machine-checkable verdicts (re-run or
mechanically verify CI run IDs; prose-only approval = no approval); fresh
context per review. Tier-0 disagreement → third-model tiebreak, logged;
Tier-1 disagreement → convert to draft + escalate with both verdicts.
Merge queue, nightly full suite on main with auto-KILLSWITCH + revert PR
on regression, every automerge in the daily brief with one-tap revert,
red nightly freezes automerging. Weekly seeded canary PRs; a reviewer that
passes a canary is dropped from rotation until fixed (fixes are Tier 2).

## v1 implementation gaps (honest, dated 2026-07-29)

1. Decorrelated review v1 counts native APPROVED reviews from the
   policy's reviewer families on the head SHA — an API-verifiable
   execution artifact, but not yet the full §6.3 structured verdict
   (checked-items list + re-run receipts). Deepening the verdict schema is
   a named next step, Tier 2 when it lands.
2. Tier-0 third-model tiebreak and automatic draft-conversion on Tier-1
   disagreement are not yet automated; the guard fails red instead, which
   is the fail-closed superset of both. Watcher automation lands with the
   PR-F workstream.
3. Merge queue and the nightly auto-KILLSWITCH + revert-PR anchor are not
   yet wired; the nightly-main status renders in the daily brief (PR-C)
   and a red nightly is an operator EMERGENCY STOP away from freezing the
   lanes. Automating that edge is a named next step.
