# NĀGA-IR Core

Status: draft

Review target: PR #2 spec core

## Lineage

NĀGA-IR is a dialect-level assurance IR and receipt vocabulary for agentic code work; it is not ETH Nagini and does not compete with Nagini. [confidence: 97/100] Nagini is a Python verifier built on Viper, while Viper is an intermediate verification language with verifier backends and frontends for several source languages, so Nagini output can lift into NĀGA-IR as `Proven_by` evidence rather than becoming NĀGA-IR itself. [confidence: 96/100] A Nagini lift is admissible only when the evidence record names the Nagini version, Viper backend, source fragment, verification result, obligation hash, assumptions, resource limits, and output hash. [confidence: 93/100] [Nagini](https://www.pm.inf.ethz.ch/research/nagini.html), [Viper](https://www.pm.inf.ethz.ch/research/viper.html), [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)

## Thesis

A code change is authoritative only when its claim is inhabited by admissible evidence, under a known trust base, inside a live context, without unresolved challenge. [confidence: 92/100] The measured object is the pair `(receipt, mesh_state)` at observation time `t`; the threshold is the shared `canonical?` predicate in this file and [witness_mesh.md](witness_mesh.md), not a receipt's self-reported challenge count. [confidence: 93/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Verif Dialect](https://circt.llvm.org/docs/Dialects/Verif/)

## Scope

NĀGA-IR specifies receipt structure, judgment forms, evidence modalities, authority transfer, and bounded canonization for agentic code assurance. [confidence: 91/100] It does not specify a verifier, scheduler, source language, model policy, token economy, or final SAB governance process. [confidence: 94/100]

## Non-goals

NĀGA-IR does not assert that CI success proves correctness, that LLM review is proof, that agent provenance is authority, or that canonization is permanent truth. [confidence: 94/100] Each non-goal is enforced by requiring every receipt to name its modality, trust base, fragment, TTL, and challenge base before authority can be transferred. [confidence: 92/100]

## Design commitments

Cursor owns the acceleration of authorship. Dharma owns the conservation of authority. [confidence: 90/100] In NĀGA-IR this is operationalized as a boundary rule: `causal_origin` records who or what produced an artifact, while `epistemic_origin` records which trust base and fragment checked the claim; authority transfer requires exact trust-base match or a checked refinement receipt. [confidence: 94/100]

## Universes

A NĀGA-IR receipt binds five typed universes: `Subject`, `Claim`, `Evidence`, `Authority`, and `Origin`. [confidence: 93/100] `Origin` splits into `causal_origin` for production trace and `epistemic_origin` for trust-base context; this split prevents agent identity from being mistaken for proof. [confidence: 95/100]

| Universe | Measured object | Admission threshold | Confidence |
|---|---|---:|---:|
| `Subject` | artifact hash, path, symbol, or packet id | stable content address or source-located selector | 93/100 |
| `Claim` | proposition over a fragment | typed claim id plus fragment id | 92/100 |
| `Evidence` | evidence record array | at least one admissible record for canonization | 91/100 |
| `Authority` | trust base and fragment pair | exact trust-base match or explicit re-check | 94/100 |
| `Origin` | causal and epistemic origin records | both fields present, neither substituted for the other | 95/100 |

## Claim classes

Claims are typed propositions over program fragments, with Curry-Howard-Lambek kept as foundation intent until a checked calculus exists. [confidence: 95/100] Claims are stratified by `claim_class` and `claim_strength`; the threshold for accepting a claim is that its receipt names both fields, fragment id, admissible modalities, checker assumptions, and any quantitative bound required by the strength profile. [confidence: 94/100] Resource-linearity enters core only as a claim class, with proof rules deferred to a later linear profile so PR #2 does not move linear-verifier logic into the TCB. [confidence: 90/100] [Introduction to Higher Order Categorical Logic](https://philpapers.org/rec/LAMITH-2), [Locally Cartesian Closed Categories and Type Theory](https://www.its.caltech.edu/~matilde/MartinLofCartesianCats.pdf), [Linear Dependent Type Theory](https://www.mscs.dal.ca/~selinger/papers/lindep.pdf)

## Admissibility matrix

The measured object is `(claim_class, claim_strength, modality, evidence_body)`. [confidence: 95/100] `claim_class` names the domain of the proposition; `claim_strength` names the authority profile. [confidence: 94/100] `Tested_by` may be canonical only for empirical or differential claim strengths and never for deductive safety. [confidence: 95/100]

| Claim strength | Meaning | Canonical modalities | Rejected alone | Confidence |
|---|---|---|---|---:|
| `deductive` | verifier claims the proposition holds under formal assumptions | `Proven_by` | `Tested_by`, `Witnessed_by`, `Attested_by` | 95/100 |
| `empirical` | harness claims behavior over measured executions | thresholded `Tested_by`, replayable `Witnessed_by` | unthresholded `Tested_by`, `Attested_by` | 93/100 |
| `differential` | harness claims two fragments behave equivalently over measured executions | thresholded differential `Tested_by`, `Proven_by` | non-differential `Tested_by`, `Attested_by` | 92/100 |
| `observational` | runtime claims a concrete event or state was observed | replayable `Witnessed_by` | non-replayable witness for safety | 93/100 |
| `attested` | authorized principal signs a governance fact | `Attested_by` | unsigned origin trace | 92/100 |

| Claim class | Allowed strengths | Non-canonical support | Confidence |
|---|---|---|---|---:|
| safety | `deductive` | `Tested_by`, `Witnessed_by`, `Attested_by` | 94/100 |
| purity | `deductive` | `Tested_by`, `Witnessed_by` | 92/100 |
| effect-boundary | `deductive`, `observational` | `Tested_by`, `Attested_by` | 91/100 |
| contract | `deductive`, `empirical` | `Witnessed_by`, `Attested_by` | 91/100 |
| behavioral-equivalence | `deductive`, `differential` | `Witnessed_by` | 91/100 |
| provenance | `observational`, `attested` | `Tested_by` | 91/100 |
| runtime-observation | `observational` | `Attested_by` | 92/100 |
| resource-linearity | `deductive` under a later linear profile | `Witnessed_by` | 89/100 |

## Evidence modalities

Evidence is not a scalar score; it is a typed modality with method, parameters, trust base, and freshness rules. [confidence: 94/100] A receipt may carry multiple modalities, but canonization is computed by a claim-class-specific admissibility predicate rather than by a total strength ranking. [confidence: 92/100]

| Modality | Judgment form | Required fields | Minimum threshold | Confidence |
|---|---|---|---|---:|
| `Proven_by` | `Γ ⊢ w : Proven_by(verifier, trust_base, fragment)(C)` | verifier, version, trust base, fragment, obligations, result | verifier result passed for the named fragment under the named trust base | 94/100 |
| `Tested_by` | `Γ ⊢ t : Tested_by(harness, coverage, seed, mutation_score)(C)` | harness, seed, coverage metric, mutation score, result | declared threshold met; never upgraded to proof | 93/100 |
| `Witnessed_by` | `Γ ⊢ r : Witnessed_by(runtime, identity, ttl)(C)` | runtime id, identity, observed value, replay hash, TTL | observation is replayable or independently checkable within TTL | 91/100 |
| `Challenged_by` | `Γ ⊢ k : Challenged_by(counterexample, adversary)(C)` | counterexample, adversary id, challenge receipt, horizon | unresolved challenge blocks canonization | 95/100 |
| `Attested_by` | `Γ ⊢ a : Attested_by(principal, role, jurisdiction, ttl)(C)` | principal, role, jurisdiction, TTL, signature | never sufficient alone for safety claims | 94/100 |

The five explicit modalities stay in the core spec as surface constructors, while the wire schema may store them in a uniform envelope of `Evidence[modality, method, params](C)`. [confidence: 93/100] The threshold for changing the surface language to only the uniform form is two independent implementers showing that modality-specific fail-closed behavior is preserved without hidden dynamic dispatch. [confidence: 89/100]

## Evidence ordering

NĀGA-IR defines a partial, claim-class-specific admissibility relation over evidence records: `Proven_by` may discharge deductive safety claims only when verifier result equals `pass` for the exact fragment and trust base, `Tested_by` may discharge only empirical claims whose declared coverage and mutation thresholds are met, `Witnessed_by` and `Attested_by` expire at TTL, and no modality may be promoted to another modality without a new `Proven_by` receipt for the coercion rule. [confidence: 93/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Nagini](https://www.pm.inf.ethz.ch/research/nagini.html), [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)

## Trust base

Authority is the pair `(trust_base_id, fragment_id)` under which a modality was checked. [confidence: 94/100] A receipt is transferable to a new trust base only by re-checking the claim or by carrying a `Proven_by` refinement receipt that names the source trust base, target trust base, translated claim set, checker, and pass result; otherwise transfer fails closed. [confidence: 93/100]

## Canonization

A claim is canonical only when the shared predicate below holds over the receipt, the named mesh state, and observation time `t`. [confidence: 95/100]

```text
canonical?(receipt, mesh_state, current, t) =
  schema_valid(receipt)
  and signatures_valid(receipt)
  and authority_key(receipt) == receipt.challenge_base.authority_key
  and admissible_evidence(receipt.claim.claim_class, receipt.claim.claim_strength, receipt.evidence, t) >= 1
  and ttl_live(receipt.ttl, receipt.evidence, t)
  and clock_within_skew(receipt.clock, t)
  and authority_matches(receipt.authority, receipt.epistemic_origin, receipt.evidence, current)
  and no_unresolved_challenge(mesh_state, receipt.challenge_base.authority_key, receipt.challenge_base, t)
```

`claim_hash(receipt)` is the SHA-256 hash URI of the JCS claim object covering `claim_id`, `claim_class`, `claim_strength`, normalized statement, scope, fragment id, and obligation hash when present. [confidence: 95/100] `authority_key(receipt)` is the SHA-256 hash URI of the JCS object `{subject_id, claim_hash, trust_base_id, fragment_id, fragment_version}`. [confidence: 95/100] `admissible_evidence` filters out evidence whose trust base or fragment does not match the receipt authority or a named checked-refinement receipt. [confidence: 94/100] `authority_matches` requires agreement among `authority.trust_base_id`, `authority.fragment_id`, `authority.fragment_version`, `epistemic_origin.trust_base_id`, admissible evidence trust bases, `current.trust_base_id`, `current.fragment_id`, and `current.fragment_version`, except when a checked refinement receipt is named. [confidence: 94/100] `clock_within_skew` returns false when observation time exceeds TTL or clock uncertainty exceeds the declared maximum skew. [confidence: 92/100] `no_unresolved_challenge` is a query over the named mesh or event base; a receipt's `challenge_state` is only a cached summary and cannot prove absence by itself. [confidence: 95/100] Canonization is therefore bounded by horizon, TTL, and trust base; it is not a claim that no morphism to bottom exists. [confidence: 96/100]

## Wire reference

The wire object is `dharma.naga_receipt.v1`, a signed JSON receipt carrying `subject`, `claim`, `claim_hash`, `evidence[]`, `authority`, `causal_origin`, `epistemic_origin`, `ttl`, `challenge_base`, `challenge_state`, `clock`, `prev_receipt_hash`, and `signatures`. [confidence: 94/100] The normative field-level contract is in [receipt_wire.md](receipt_wire.md). [confidence: 95/100]

## Mesh reference

Runtime witnesses compose into a witness mesh by merging claim, evidence, challenge, and expiration events with deterministic conflict rules. [confidence: 88/100] The mesh contract is in [witness_mesh.md](witness_mesh.md), and any CRDT-like claim in that file is scoped to convergence of receipt state, not to semantic correctness of the underlying program. [confidence: 93/100] [Conflict-free Replicated Data Types](https://arxiv.org/abs/1805.06358)

## Local integration

The current checkout contains `dharma_swarm/coalgebra.py` and `docs/telos-engine/01_SATTVA_VISION.md`, but it does not currently contain `scripts/governance/assurance_boundary.py` or `packages/telos-kernel/`. [confidence: 99/100] Therefore this PR #2 spec may name those absent paths only as planned or prior-context integration targets until a later PR lands matching files in this checkout. [confidence: 97/100]

## Non-normative coalgebra

The coalgebraic section is design intent for PR #6, not a normative proof obligation in PR #2. [confidence: 96/100] A later reconciler may model receipt state with `F_A(S) = AuthorityObservation × S`, but this draft claims only that [dharma_swarm/coalgebra.py](../../dharma_swarm/coalgebra.py) is a compatible local reference point, not that the mapping is implemented or proven. [confidence: 97/100]

## Non-normative types

The type-theory section is a foundation sketch, not a proven calculus for PR #2. [confidence: 96/100] A later proof note may interpret claims as types and evidence as inhabitants under a modality-indexed fibration, but the threshold for making that load-bearing is a checked calculus with syntax, typing rules, assumptions, and proof obligations. [confidence: 96/100] [Locally Cartesian Closed Categories and Type Theory](https://www.its.caltech.edu/~matilde/MartinLofCartesianCats.pdf), [The Biequivalence of Locally Cartesian Closed Categories and Martin-Löf Type Theories](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/6ECB295B1246A85D5DD92E5F38428D99/S0960129513000881a.pdf/the-biequivalence-of-locally-cartesian-closed-categories-and-martin-lof-type-theories.pdf), [Linear Dependent Type Theory](https://www.mscs.dal.ca/~selinger/papers/lindep.pdf)

## Target theorems

Five target properties define the proof agenda: modality-indexed validity, canonicality decidability, monotonicity under fragment narrowing, non-monotonicity under fragment widening or trust-base substitution, and challenge completeness with no silent modality promotion. [confidence: 92/100] The threshold for claiming any property as proven is a companion proof artifact that names the calculus, assumptions, checker, and checked fragment; until then these are target properties only, not theorems of PR #2. [confidence: 96/100]

## Threat model

Adversarial agents may forge causal origin, replay stale witnesses, substitute trust bases, hide counterexamples, inflate test evidence, or convert human attestation into false proof. [confidence: 94/100] NĀGA-IR counters those threats with signed receipts, TTLs, prev-hash chains, explicit epistemic origin, modality-specific thresholds, and challenge records that block canonization while unresolved. [confidence: 91/100]

## Dharma boundary

NĀGA-IR does not claim an isomorphism between category theory, Madhyamaka, Kyoto School thought, or any dharmic tradition. [confidence: 98/100] The phrase "formal convergence" is non-normative and refers only to this measured pattern in the receipt calculus: context-dependent standing, typed transformation, invariant preservation, witnessable equivalence, and defeasible authority. [confidence: 93/100] Śūnyatā is not modeled as a terminal object; the technical rendering is that no claim has authority by svabhāva, only through context, witness, trust base, freshness, and unresolved-challenge status. [confidence: 92/100]

## Rollout

PR #2 lands only the spec triple in `specs/naga_ir/`. [confidence: 93/100] Later PRs may add receipt emission, SAB shadow export, titanium metadata, coalgebraic reconciliation, and arena design, but this core spec must remain compatible with those stages without pretending they already exist in this checkout. [confidence: 94/100]
