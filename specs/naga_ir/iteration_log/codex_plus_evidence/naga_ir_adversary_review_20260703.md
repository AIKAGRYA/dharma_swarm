# NĀGA-IR Adversarial Review

Generated at: 2026-07-03T15:51Z

Reviewer: native subagent `019f28ac-144c-7d61-9372-63164335a5c2`

Score: 76/100

Verdict: block 90 confidence

## Blockers

1. Wire schema contradicted itself on signatures and hashes. The review cited placeholder `sha256:...` strings while the threshold said lowercase SHA-256 hex, and the canonicality predicate required signature verification while the example used `signatures: []`.
2. Canonization depended on self-reported challenge state. The required change was to make canonicality a query over a named challenge or event base for `(subject, claim, trust_base, fragment, horizon, t)`.
3. Authority matching was inconsistent across core and wire. The required change was one normative predicate requiring evidence, authority, epistemic origin, current trust base, current fragment, TTLs, signatures, and checked-refinement exception to agree.
4. Load-bearing thresholds were underdefined. The required change was a claim-class-to-admissible-modality matrix, quantitative tested-evidence thresholds, and no `not_claimed` threshold for canonical tested claims.
5. CRDT and witness mesh claims were not formal enough. The required change was either a join-semilattice merge definition or downgrading CRDT and bisimulation language to non-normative design intent.
6. Coalgebra and type-theory sections were formal-looking but not formal. The required change was either moving them to target or non-normative status or defining the calculus, mapping, assumptions, and proof obligations.

## Required changes

- Keep the explicit absence statement for `scripts/governance/assurance_boundary.py` and `packages/telos-kernel/`.
- Add a normative canonicality predicate shared by `core.md`, `receipt_wire.md`, and `witness_mesh.md`.
- Define challenge-base completeness and resolver authorization, including trust-base refinement rules.
- Define clock-skew fields.
- Keep Nagini as external verifier evidence only and add a Nagini-to-`Proven_by` adapter threshold.
- Move dharma/category-theory convergence language to a clearly non-load-bearing appendix or mark it explicitly non-normative.

## Patch response

The follow-up patch addressed these objections by adding `challenge_base`, clock skew, exact hash grammar, signature object shape, a shared `canonical?` predicate, a claim-class admissibility matrix, join-semilattice mesh state, non-authoritative `challenge_state`, and non-normative coalgebra/type-theory sections.
