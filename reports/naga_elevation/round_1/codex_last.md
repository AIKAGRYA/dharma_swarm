## Verdict
Revise before elevation. The spec is much safer than the earlier shape, but four requested fixes are still incomplete: assurance-boundary presence, TCB ceiling, PhilPapers replacement, and explicit SAB packet-versus-receipt wording. [confidence: 94/100]

## Fix Status
- FAIL: `core.md` still says `scripts/governance/assurance_boundary.py` is absent, but it exists locally and on `origin/main`. [confidence: 99/100]
- FAIL: `packages/telos-kernel` has no `<= 5000 LOC` trusted-computing-base ceiling. [confidence: 96/100]
- FAIL: the Lambek/Scott citation still uses PhilPapers. [confidence: 95/100]
- PASS: local symbol spelling uses lowercase `bisimilar`. [confidence: 96/100]
- REVISE: SAB export is future-scoped, but it should explicitly say current `sab_client.py` emits `SABContribution` packets, not NĀGA receipts. [confidence: 97/100]

## Redlines
Replace `core.md / Local integration`:

```md
The current checkout contains `dharma_swarm/coalgebra.py`, `scripts/governance/assurance_boundary.py`, and `packages/telos-gatekeeper/`, but it does not currently contain `packages/telos-kernel/`. [confidence: 99/100] `scripts/governance/assurance_boundary.py` emits `assurance_boundary_report.v1`, checks AB-01 through AB-05, and exits with 0 for hold, 1 for violation, and 2 for measurement failure. [confidence: 98/100] Therefore this PR #2 spec may cite the assurance-boundary gate as present integration evidence, while any `packages/telos-kernel` reference remains future-only until a later PR lands matching files and a `<= 5000 LOC` TCB ceiling. [confidence: 97/100]
```

Replace `core.md / Claim classes` citation tail:

```md
[Curry-Howard-Lambek reference: Lambek and Scott, Introduction to Higher Order Categorical Logic, Cambridge University Press](https://www.cambridge.org/9780521356534), [Locally Cartesian Closed Categories and Type Theory](https://www.its.caltech.edu/~matilde/MartinLofCartesianCats.pdf), [Linear Dependent Type Theory](https://www.mscs.dal.ca/~selinger/papers/lindep.pdf)
```

Replace `core.md / Rollout`:

```md
PR #2 lands only the spec triple in `specs/naga_ir/`. [confidence: 93/100] The current `dharma_swarm/connectors/sab_client.py` exports `SABContribution` packets, not NĀGA receipts; SAB receipt export is future PR #4 work. [confidence: 97/100] Later PRs may add NĀGA receipt emission, SAB shadow receipt export, titanium metadata, coalgebraic reconciliation, and arena design, but this core spec must remain compatible with those stages without pretending they already exist in this checkout. [confidence: 94/100]
```

Add under `Non-normative types`:

```md
LCCC references support the dependent-type foundation sketch, but they do not by themselves supply modality transitions, TTL expiry, trust-base reindexing, or challenge invalidation. [confidence: 93/100] Any modality-indexed fibration claim becomes load-bearing only after the draft names its base category, fibers, reindexing maps, substitution laws, and fail-closed authority-transfer rule. [confidence: 94/100] Moltbook material, if cited, is expository only and is not evidence for the NĀGA-IR calculus. [confidence: 96/100]
```

Replace `Non-normative coalgebra` sentence containing `F_A`:

```md
A later reconciler may model receipt state with a local-reference-compatible shape `F_A(S) = S × AuthorityObservation`, where `AuthorityObservation` is a finite record of canonicality status, unresolved challenge set, expiry status, and authority key. [confidence: 91/100] This draft does not claim that the receipt reconciler is implemented, proven, or equivalent to the evolution coalgebra in `dharma_swarm/coalgebra.py`. [confidence: 97/100]
```

## Missing Invariants
Add `canonical_status(receipt, mesh_state, current, t) ∈ {canonical, noncanonical, unknown}` or define `canonical?` as a pure boolean plus a separate failure reason, because `clock_skew_unknown` cannot be represented cleanly by the current predicate alone. [confidence: 92/100]

Add horizon checks: `evidence_within_horizon(receipt.evidence, receipt.challenge_base, t)` and `challenge_snapshot_live(receipt.challenge_base, t)`, otherwise canonization is not fully bounded by evidence horizon, TTL, and trust base. [confidence: 94/100]

In `receipt_wire.md / Example`, state that the example is also non-canonical because `Attested_by` cannot discharge a `deductive` claim. [confidence: 96/100]

## Target Properties
Good PR #2 target-property candidates: canonical-status decidability over finite receipts and finite mesh snapshots, hash stability under JCS, fail-closed trust-base substitution, challenge monotonic blocking, expiry anti-monotonicity, and no silent modality promotion. [confidence: 93/100]

## Wall Sentence
Authority is not authored; it is checked, scoped, fresh, and defeasible. [confidence: 88/100]

## Q1/Q2/Q3
Q1: Not elevation-ready until the redlines above land. [confidence: 94/100]
Q2: No category-theory or dharma isomorphism overclaim remains in the reviewed text, but the coalgebra and fibration sections need the guardrails above. [confidence: 90/100]
Q3: PR #2 should remain a spec-only deliverable; SAB receipts, telos-kernel, and reconciler implementation belong to later PRs with explicit evidence. [confidence: 95/100]
