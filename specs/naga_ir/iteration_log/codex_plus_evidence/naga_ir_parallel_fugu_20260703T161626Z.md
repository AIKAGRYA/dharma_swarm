# NĀGA-IR Parallel Core

Status: parallel review draft
Author lane: fugu-ultra
Created: 2026-07-03T16:16:26Z
Target: pasteable PR #2 review material for `specs/naga_ir/core.md`
Overall confidence: 91/100

## Review verdict

I disagree with any reading that treats the outline as already above 90/100 merely because the prose is coherent: the measured object is the PR #2 spec triple, and the threshold for 90/100 is that canonicality, admissibility, challenge absence, authority transfer, and non-normative formal sections all have explicit predicates rather than persuasive vocabulary. [confidence: 91/100] This threshold follows the verification-dialect pattern that claims must become first-class IR objects with explicit contracts or obligations, not unstated English entailments. [confidence: 90/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Verif Dialect](https://circt.llvm.org/docs/Dialects/Verif/)

## Q1 answer

Keep the five explicit modalities as core surface constructors and use `Evidence[modality, method, params](C)` only as the wire-envelope shape. [confidence: 93/100] The measured object is one evidence record; the threshold is that the parser validates exactly one closed modality tag from `{Proven_by, Tested_by, Witnessed_by, Challenged_by, Attested_by}` and dispatches to modality-specific admissibility rules before any receipt can become canonical. [confidence: 92/100] A uniform envelope is safe for serialization only if it does not erase constructor-specific failure behavior. [confidence: 91/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)

## Q2 answer

Keep the property list in `core.md`, but rename it from target theorems to target properties and require a later `properties.md` or proof artifact before any property is called proven. [confidence: 94/100] The measured object is each property sentence; the threshold is that it names the claim, assumptions, checker or proof calculus, checked fragment, and failure mode, otherwise it remains a roadmap item. [confidence: 93/100] This avoids turning proof obligations into marketing claims. [confidence: 91/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf)

## Q3 answer

Add `resource-linearity` as a claim class in core, but defer its typing and proof rules to a later linear profile. [confidence: 91/100] The measured object is a claim whose authority or resource cannot be copied or weakened; the threshold is that the receipt names the linear resource, admissible structural rules, fragment, and checker, and PR #2 does not move linear-verifier logic into `packages/telos-kernel/`. [confidence: 90/100] This captures the slice motivated by linear dependent type theory without prematurely expanding the TCB. [confidence: 91/100] [Linear Dependent Type Theory](https://www.mscs.dal.ca/~selinger/papers/lindep.pdf)

## Redline thesis

Current: `A code change is authoritative only when its claim is inhabited by admissible evidence, under a known trust base, inside a live context, without unresolved challenge.`

Replacement: `A code change is not authoritative because it exists, because an agent produced it, or because CI passed; it is authoritative only when a normalized claim over a named fragment has admissible evidence, a matching trust base, live TTL, valid signatures, and no unresolved challenge in the named challenge base.` [confidence: 92/100]

Reason: the measured object is `(receipt, mesh_state, current_context, observation_time)`; the threshold is the shared `canonical?` predicate, not the receipt text alone. [confidence: 94/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf)

## Redline modalities

Current: `Evidence is not a scalar; it comes in five typed modalities, each with an explicit method, parameters, and trust base.`

Replacement: `Evidence is not a scalar or a total order; it is a closed sum of typed modalities, and each modality is admissible only relative to a claim class, method, parameters, trust base, freshness window, and challenge state.` [confidence: 93/100]

Reason: the measured object is `(claim_class, modality, evidence_body)`; the threshold is a class-specific admissibility relation that prevents `Tested_by` or `Attested_by` from being promoted into `Proven_by`. [confidence: 94/100] [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf), [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf)

## Redline authority

Current: `Authority is not a property of an agent or of CI; it is the pair (trust_base_id, fragment_id) under which a modality was checked, so authority is transferable only by re-checking under a new trust base.`

Replacement: `Authority is the checked relation among evidence trust bases, authority.trust_base_id, authority.fragment_id, epistemic_origin.trust_base_id, current trust base, current fragment, and any named refinement receipt; if any required edge is absent, authority transfer fails closed.` [confidence: 93/100]

Reason: the measured object is `authority_matches(receipt, current)`; the threshold is exact agreement or a `Proven_by` refinement receipt naming source trust base, target trust base, translated claim set, checker, and pass result. [confidence: 93/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf)

## Shared canonicality

Add this section after trust base. [confidence: 95/100]

`A claim is canonical at observation time t iff canonical?(receipt, mesh_state, current, t) holds: schema and signatures validate, at least one evidence record is admissible for the claim class, all required TTLs and clock-skew bounds are live, authority_matches(receipt, current) holds, and no unresolved challenge exists in challenge_base for the authority key within the evidence horizon.` [confidence: 95/100]

Justification: without a shared predicate, `core.md`, `receipt_wire.md`, and `witness_mesh.md` can each satisfy themselves while disagreeing on the measured object of authority. [confidence: 94/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf)

## Challenge base

Add this section near canonization. [confidence: 94/100]

`Absence of challenge is measured by querying a named challenge base, not by trusting a receipt's cached challenge summary; the threshold is a key `(subject_id, claim_id, trust_base_id, fragment_id, fragment_version)`, an evidence horizon, a mesh or event-base id, and a snapshot hash or replayable query receipt.` [confidence: 95/100]

Justification: a self-reported `unresolved_count == 0` is not evidence of absence and would let the artifact under review declare itself unchallenged. [confidence: 96/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf)

## Admissibility matrix

Add this section before evidence modalities. [confidence: 93/100]

`The core spec must define a claim-class-to-modality admissibility matrix; the threshold is that each row names which modalities can canonicalize the class, which modalities are supporting only, and which modalities are rejected alone.` [confidence: 93/100]

Justification: without this matrix, the phrase `at least one admissible modality` hides the most important policy decision in the system. [confidence: 95/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)

## Tested thresholds

Add this sentence to `Tested_by`. [confidence: 92/100]

`A `Tested_by` record is canonical only for claim classes that admit empirical evidence and only when `coverage_metric`, `coverage_threshold`, `coverage_observed`, `mutation_threshold` when claimed, `mutation_score` when claimed, seed policy, and explicit bounds are present and satisfied.` [confidence: 92/100]

Justification: `not_measured` and `not_claimed` are acceptable historical metadata values, but they cannot support canonical empirical authority. [confidence: 94/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf)

## Nagini adapter

Add this sentence to lineage or `Proven_by`. [confidence: 93/100]

`A Nagini result lifts into NĀGA-IR only as `Proven_by` evidence when the receipt records Nagini version, Viper backend, source fragment, obligations, assumptions, resource limits, verification result, and output hash; the verifier remains external to NĀGA-IR.` [confidence: 94/100]

Justification: this preserves the non-rename distinction and prevents NĀGA-IR from pretending to be a Python verifier. [confidence: 96/100] [Nagini](https://www.pm.inf.ethz.ch/research/nagini.html), [Viper](https://www.pm.inf.ethz.ch/research/viper.html), [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)

## Coalgebra check

I disagree with the sentence that bisimulation over `F(S) = Claim × Modality-set × ChallengeSet × TrustBase × S` directly gives equivalence-of-authority. [confidence: 94/100] The measured object of bisimulation is an observation stream, and the threshold for authority equivalence is equality of canonicality result and unresolved-challenge set for every authority key over a declared horizon; without a projection containing time, TTL, fragment version, signatures, and canonicality status, the functor is too weak. [confidence: 93/100] [Introduction to Higher Order Categorical Logic](https://philpapers.org/rec/LAMITH-2)

Replacement: `Coalgebraic semantics are non-normative in PR #2; a later reconciler may define an authority observation functor whose observations include claim, admissible modality set, challenge set, trust base, fragment version, TTL status, signature status, canonicality status, and successor state, but this draft does not claim that such bisimulation is implemented or proven.` [confidence: 94/100]

## Type check

The LCCC direction is acceptable as a base for dependent claim contexts, but the current formulation should not imply that a topos or HoTT model is required. [confidence: 90/100] The measured object is the judgment form `Γ ⊢ evidence : Modality(C)`; the threshold is a comprehension-category or LCCC base for contexts and dependent claims, plus a modality-indexed fibration for evidence over claim classes. [confidence: 90/100] Linear/resource evidence should live in a symmetric-monoidal or linear-dependent fiber rather than relying on ordinary cartesian weakening. [confidence: 91/100] [Locally Cartesian Closed Categories and Type Theory](https://www.its.caltech.edu/~matilde/MartinLofCartesianCats.pdf), [The Biequivalence of Locally Cartesian Closed Categories and Martin-Löf Type Theories](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/6ECB295B1246A85D5DD92E5F38428D99/S0960129513000881a.pdf/the-biequivalence-of-locally-cartesian-closed-categories-and-martin-lof-type-theories.pdf), [Linear Dependent Type Theory](https://www.mscs.dal.ca/~selinger/papers/lindep.pdf)

## Formal properties

Add these properties to the target list. [confidence: 92/100]

1. No silent strengthening: if evidence record `e` has modality `m`, claim class `k`, and trust base `b`, then `e` cannot discharge a claim requiring modality `m'` unless there is a `Proven_by` coercion receipt from `(m, k, b)` to `(m', k, b)`. [confidence: 94/100]
2. Challenge-base completeness: if `canonical?(r, mesh, current, t)` holds, then the challenge query over `r.challenge_base` has enumerated every open challenge event for the authority key within the declared horizon or returned `unknown`. [confidence: 93/100]
3. Trust-base non-substitution: if `current.trust_base_id` differs from `receipt.authority.trust_base_id`, then canonicality is false unless a checked refinement receipt is named and validates. [confidence: 94/100]
4. Canonicality decidability: for a finite receipt, finite mesh snapshot, finite trust-base registry, and bounded clock uncertainty, `canonical?` returns exactly one of `canonical`, `noncanonical`, or `unknown`. [confidence: 91/100]

Justification: these properties target the concrete ways an agentic codebase can launder weak evidence into authority. [confidence: 94/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)

## Category errors

The phrase `sound verifier` is too strong unless the receipt names the verifier fragment, assumptions, and trusted kernel. [confidence: 92/100] Replace it with `named verifier pass over a bounded fragment under declared assumptions`. [confidence: 93/100] [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)

The phrase `strictly weaker than Proven_by` implies a total evidence order that the spec has not defined. [confidence: 91/100] Replace it with `inadmissible alone for safety and effect-boundary claims unless a claim-class profile explicitly permits it`. [confidence: 93/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf)

The HoTT identity-type sentence is premature. [confidence: 91/100] Different receipts for the same English sentence are distinct records unless a later proof note defines normalized claim equality and receipt equivalence. [confidence: 92/100] [Homotopy Type Theory Book](https://homotopytypetheory.org/book/)

The emergent-compression examples in related work should not be load-bearing unless each named protocol is verified. [confidence: 90/100] Move that load to the threat model as `opaque or compact agent communication can bypass auditability unless round-trip integrity is witnessed`. [confidence: 92/100]

## Dharma boundary

Keep all dharmic and Kyoto-language material non-normative. [confidence: 96/100] The measured object of the technical spec is a receipt calculus; the threshold for any load-bearing claim is an explicit predicate over evidence, trust base, context, TTL, and challenge status, not a metaphysical analogy. [confidence: 96/100] Śūnyatā is not a terminal object in this spec; the safe technical rendering is that no claim has authority by svabhāva, only through context, witness, trust base, freshness, and unresolved-challenge status. [confidence: 96/100]

## Wall sentences

Do not replace the two wall sentences. [confidence: 91/100]

`Cursor owns the acceleration of authorship. Dharma owns the conservation of authority.` [confidence: 90/100]

`A code change is not authoritative because it exists, or because an agent produced it, or because CI passed. It is authoritative only when its claim is inhabited by admissible evidence, under a known trust base, inside a live context, without unresolved challenge.` [confidence: 92/100]

The superior move is not wording replacement, but operationalization: define `canonical?`, `authority_matches`, `admissible_evidence`, `challenge_base`, and `no_silent_strengthening` immediately after the wall sentences. [confidence: 94/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf)
