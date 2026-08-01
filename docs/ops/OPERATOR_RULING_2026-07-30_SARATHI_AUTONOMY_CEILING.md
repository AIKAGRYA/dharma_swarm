# Operator Ruling — 2026-07-30 — SARATHI AUTONOMY CEILING (tier-2 repeal)

**Status:** ratified operator ruling, recorded as a witness record. This file
is itself a tier-2 referee surface (`tiers.tier2.paths` in the policy JSON).
**Provenance:** delivered by the operator in the Sarathi autonomy build
mission of 2026-07-30 (`docs/prompts/SARATHI_AUTONOMY_BUILD_2026-07-30.md`,
session of record: the sarathi-autonomy-build session, PR #1167). Amends the
2026-07-29 ruling (`docs/ops/OPERATOR_RULING_2026-07-29_AUTO_WITH_DECORRELATED_REVIEW.md`)
in exactly one place: the tier-2 clause. That record stays untouched as
history; this record supersedes its tier-2 section only.
**Implementation:** `scripts/governance/automerge_tier_policy.json` (schema
v2), `scripts/governance/check_automerge_tier_policy.py` (door update),
`dharma_swarm/risk_patterns.py` (stdlib-only shared vocabulary),
`dharma_swarm/operator_core/reversibility_gate.py` (stdlib-only import chain),
`dharma_swarm/operator_core/autonomy_dial.py` (the dial).
**Resolution note:** the binding enforcement lives in the policy JSON +
evaluator + branch protection; agents resolve conflicts against those enforced
files, never against this prose.

---

## §0 as ratified (condensed to the binding facts)

> The prior "operator hand-merge FOREVER" tier-2 rule is **repealed** by
> operator decision 2026-07-30: replace it with a *decorrelated-review +
> reversibility* gate that Sarathi can clear autonomously. Nothing is
> off-limits except what is genuinely irreversible or genuinely illegal.
> The `_never_auto_match` denylist stays as the hard legal/irreversible
> floor — that boundary does not move.

## The autonomy ceiling (binding formula)

A PR is admissible to the unattended merge lane iff, for its tier:

```
AUTONOMOUS_IF (decorrelated_reviews >= N_tier)
          AND (reversibility_gate == AUTO)
          AND (not _never_auto_match)
```

Mechanical definitions (the evaluator is the arbiter of these):

- `N_tier`: tier0 = 1, tier1 = 2, tier2 = 2 — counted exactly as the
  2026-07-29 ruling counts them (trusted `<app>[bot]` logins, family ≠
  author family, head-SHA-pinned APPROVED reviews).
- `reversibility_gate == AUTO` for a merge intent:
  `classify_action(pr_title, operator_reachable=False).action_class` is not
  `OPERATOR_ONLY`. With the operator unreachable, the gate classifies
  OPERATOR_ONLY exactly when a NEVER_AUTO denylist pattern or CRITICAL-risk
  vocabulary matches — that is the "genuinely irreversible or genuinely
  illegal" boundary. Milder classes (NEEDS_LEASE, IRREVERSIBLE-by-risk-HIGH)
  are admitted because a reviewed git merge is single-revert reversible and
  the decorrelated quorum stands in for the execution lease.
- `not _never_auto_match` (tier2 additionally): every hit referee path must
  be clear of NEVER_AUTO substrings; a referee surface sitting on the floor
  (credentials, launchd, production, ...) stays operator hand-merge.

## Tier-2 as amended

- Tier 2 keeps the same referee path list (extended with this record and the
  floor's own implementation modules: `dharma_swarm/risk_patterns.py`,
  `dharma_swarm/operator_core/reversibility_gate.py`,
  `dharma_swarm/operator_core/autonomy_dial.py` — a tier-1 PR must not be
  able to rewrite the denylist the tier-2 door trusts).
- Tier 2 door: 2 decorrelated reviews, diff ≤ 400 lines, test-deletion
  named sign-off, reversibility floor as above.
- The policy is still loaded from the DEFAULT branch by the workflow: a PR
  editing the policy cannot loosen its own admission, and this repeal binds
  only after the operator lands it — the landing IS the ratifying act.

## The autonomy dial

`DGC_SARATHI_AUTONOMY` ∈ {`shadow`, `propose`, `dispatch`, `full`};
first-boot default `propose`; invalid values fail closed to `shadow`.
Semantics live in `dharma_swarm/operator_core/autonomy_dial.py`: the dial
bounds what Sarathi's delegation organ may execute (shadow = log only;
propose = write proposals, hold dispatch; dispatch = execute gate-admissible
delegations; full = also arm automerge-label intents into Merge Master
Mike's lane). The dial never widens the reversibility gate: gate = floor,
dial = ceiling, an action must clear both. Target per the mission:
`propose` during the 14-cycle unattended proof, then `dispatch`, then
`full` after one clean week.

## What does not move

- The NEVER_AUTO denylist (`reversibility_gate.NEVER_AUTO_PATTERNS`) — the
  hard legal/irreversible floor.
- Merge Master Mike as the sole merge executor; Sarathi produces PR/label
  intents only ("merge pr" and "git push" are themselves NEVER_AUTO).
- The rate limit (20/day), the honest confirmation token
  (`automerge-policy-pass-<N>`), the canary-sandbox structural block, and
  every 2026-07-29 mechanism not named here.

## v1 implementation gaps (honest, dated 2026-07-30)

1. The reversibility floor classifies the PR TITLE (the declared intent) —
   a benign-titled PR whose diff hides floor-grade content is caught only by
   the decorrelated reviewers and the tier2 path floor, not by the title
   gate. Deepening to diff-aware classification is a named next step.
2. `N_tier2 = 2` equals the total reviewer-family count today (openai,
   github-copilot); adding a third family raises real decorrelation and is a
   named next step.
3. The dial exists but nothing reads it until the Sarathi delegation organ
   lands (PR-S1 of the same mission); until then it constrains nothing.
4. Substring matching is deliberately coarse and fail-closed: titles
   containing e.g. "token" or "delete" route to the operator lane even when
   benign. Retitle or hand-merge; do not widen the vocabulary to taste.
