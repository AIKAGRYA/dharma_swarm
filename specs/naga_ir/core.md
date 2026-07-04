# NĀGA-IR Core

Status: draft

Review target: PR #2 spec core

## Lineage

NĀGA-IR is a dialect-level assurance IR and receipt vocabulary for agentic code work; it is not ETH Nagini and does not compete with Nagini. [confidence: 97/100] Nagini is a Python verifier built on Viper, while Viper is an intermediate verification language with verifier backends and frontends for several source languages, so Nagini output can lift into NĀGA-IR as `Proven_by` evidence rather than becoming NĀGA-IR itself. [confidence: 96/100] A Nagini lift is admissible only when the evidence record names the Nagini version, Viper backend, source fragment, verification result, obligation hash, assumptions, resource limits, and output hash. [confidence: 93/100] MLIR verification citations ground only the dialect-family positioning and reusable semantic-dialect pattern; they do not ground the authority or canonization thesis. [confidence: 91/100] [Nagini](https://www.pm.inf.ethz.ch/research/nagini.html), [Viper](https://www.pm.inf.ethz.ch/research/viper.html), [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf), [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Verif Dialect](https://circt.llvm.org/docs/Dialects/Verif/)

## Thesis

A code change is not authoritative because it exists, or because an agent produced it, or because CI passed. It is authoritative only when its claim is inhabited by admissible evidence, under a known trust base, inside a live context, without unresolved challenge. [confidence: 93/100] The measured object is `(receipt, mesh_state, current, t)` and the threshold is `canonical?`, defined normatively in this file and called by [witness_mesh.md](witness_mesh.md); this is a proof-carrying authorization pattern, not a theorem supplied by MLIR verif, and the cross-file invariant is that `witness_mesh.md` calls but never redefines `canonical?`, so there is exactly one normative definition. [confidence: 96/100] [A logical reconstruction of SPKI](https://arxiv.org/abs/cs/0208028)

## Scope

NĀGA-IR specifies receipt structure, judgment forms, evidence modalities, authority transfer, and bounded canonization for agentic code assurance. [confidence: 91/100] It does not specify a verifier, scheduler, source language, model policy, token economy, or final SAB governance process. [confidence: 94/100]

## Non-goals

NĀGA-IR does not assert that CI success proves correctness, that LLM review is proof, that agent provenance is authority, or that canonization is permanent truth. [confidence: 94/100] Each non-goal is enforced by requiring every receipt to name its modality, trust base, fragment, TTL, and challenge base before authority can be transferred. [confidence: 92/100]

## Design commitments

Cursor owns the acceleration of authorship. Dharma owns the conservation of authority. [confidence: 90/100] This sentence is a non-normative framing slogan; the operationalized claim is the boundary rule below. [confidence: 92/100] In NĀGA-IR this is operationalized as a boundary rule: `causal_origin` records who or what produced an artifact, while `epistemic_origin` records which trust base and fragment checked the claim; authority transfer requires exact trust-base match or a checked refinement receipt. [confidence: 94/100]

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

Claims are typed propositions over program fragments, with Curry-Howard-Lambek kept as foundation intent until a checked calculus exists. [confidence: 95/100] Claims are stratified by `claim_class` and `claim_strength`; the threshold for accepting a claim is that its receipt names both fields, fragment id, admissible modalities, checker assumptions, and any quantitative bound required by the strength profile. [confidence: 94/100] Resource-linearity enters core only as a placeholder claim class; [Linear Dependent Type Theory](https://www.mscs.dal.ca/~selinger/papers/lindep.pdf) supports the shape of a future linear-dependent profile but not NĀGA-IR software resource rules, so a `resource-linearity` claim is non-canonical until a later profile names syntax, operational resource semantics, checker obligations, and admissible proof rules. [confidence: 94/100]

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

The five explicit modalities stay in the core spec as surface constructors, while the wire schema may store them in a uniform envelope of `Evidence[modality, method, body](C)`, where `body` contains modality-specific parameters. [confidence: 94/100] The threshold for changing the surface language to only the uniform form is two independent implementations, meaning distinct codebases by different maintainers with no shared dispatch table, each demonstrating that malformed, unknown, or cross-modality evidence fails closed before claim-class admissibility is evaluated, as scoped in the Q1 decision below. [confidence: 92/100]

## Open decisions

Q1 is resolved by keeping five explicit evidence modalities as surface constructors while using the uniform wire envelope only as storage shape; collapse to uniform-only requires two independent implementations, meaning distinct codebases by different maintainers with no shared dispatch table, each demonstrating that malformed, unknown, or cross-modality evidence fails closed before claim-class admissibility is evaluated. [confidence: 94/100] Q2 is resolved by keeping the proof agenda in this file as target properties, not proven theorems, until a companion proof artifact names the calculus, assumptions, checker, and checked fragment. [confidence: 95/100] Q3 is resolved by retaining `resource-linearity` as a claim class and deferring proof rules to a later linear profile, so PR #2 adds no linear verifier logic to the TCB. [confidence: 92/100]

## Evidence ordering

NĀGA-IR defines a partial, claim-class-specific admissibility relation over evidence records: `Proven_by` may discharge deductive safety claims only when verifier result equals `pass` for the exact fragment and trust base, `Tested_by` may discharge only empirical claims whose declared coverage and mutation thresholds are met, `Witnessed_by` and `Attested_by` expire at TTL, and no modality may be promoted to another modality without a new `Proven_by` receipt for the coercion rule; verifier-family citations ground only verifier output shape, while the no-promotion rule is a local authorization rule. [confidence: 93/100] [A logical reconstruction of SPKI](https://arxiv.org/abs/cs/0208028), [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)

## Trust base

Authority is the pair `(trust_base_id, fragment_id)` under which a modality was checked. [confidence: 94/100] A receipt is transferable to a new trust base only by re-checking the claim or by carrying a `Proven_by` refinement receipt that names the source trust base, target trust base, translated claim set, checker, and pass result; otherwise transfer fails closed. [confidence: 93/100]

## Current context

`current` is the finite authority context at observation time `t`. [confidence: 91/100] It contains `trust_base_id`, `fragment_id`, `fragment_version`, the finite trust-base key snapshot, signer revocation status, fragment-narrowing relation, and checked-refinement lookup used by `signatures_valid`, `admissible_evidence`, and `authority_matches`; absent or unresolved entries make the diagnostic status `unknown` and therefore non-canonical for authority transfer. [confidence: 91/100]

## Canonization

A claim is canonical only when the shared predicate below holds over the receipt, the named mesh state, and observation time `t`. [confidence: 95/100]

```text
canonical?(receipt, mesh_state, current, t) =
  schema_valid(receipt)
  and signatures_valid(receipt, current, t)
  and authority_key(receipt) == receipt.challenge_base.authority_key
  and admissible_evidence(receipt, current, t) >= 1
  and ttl_live(receipt.ttl, receipt.evidence, t)
  and clock_within_skew(receipt.clock, t)
  and authority_matches(receipt.authority, receipt.epistemic_origin, receipt.evidence, current)
  and no_unresolved_challenge(mesh_state, receipt.challenge_base.authority_key, receipt.challenge_base, t)
```

`claim_hash(receipt)` is defined as the SHA-256 hash URI of the JCS claim object covering `claim_id`, `claim_class`, `claim_strength`, normalized statement, scope, fragment id, and obligation hash when present. [confidence: 95/100] `authority_key(receipt)` is the SHA-256 hash URI of the JCS object `{subject_id, claim_hash, trust_base_id, fragment_id, fragment_version}`. [confidence: 95/100] `admissible_evidence(receipt, current, t)` filters out evidence whose modality, result, body threshold, trust base, or fragment does not match the receipt authority or a named checked-refinement receipt. [confidence: 94/100] `authority_matches` requires agreement among `authority.trust_base_id`, `authority.fragment_id`, `authority.fragment_version`, `epistemic_origin.trust_base_id`, admissible evidence trust bases, `current.trust_base_id`, `current.fragment_id`, and `current.fragment_version`, except when a checked refinement receipt is named. [confidence: 94/100] `clock_within_skew` returns false when `abs(t - receipt.clock.observed_at) > receipt.clock.max_clock_skew_ms` or clock uncertainty exceeds the declared maximum skew; TTL expiry is handled by `ttl_live`. [confidence: 92/100] `no_unresolved_challenge` is a query over the named mesh or event base; a receipt's `challenge_state` is only a cached summary and cannot prove absence by itself. [confidence: 95/100] Implementations may expose `canonical_status ∈ {canonical, noncanonical, unknown}` for diagnostics, but authority transfer uses the fail-closed boolean predicate where `unknown` is non-canonical. [confidence: 91/100] Canonization is therefore bounded by horizon, TTL, and trust base; it is not a claim that no morphism to bottom exists. [confidence: 96/100]

## Wire reference

The wire object is `dharma.naga_receipt.v1`, a signed JSON receipt carrying `schema_version`, `receipt_id`, `subject`, `claim`, `claim_hash`, `evidence[]`, `authority`, `causal_origin`, `epistemic_origin`, `ttl`, `challenge_base`, `challenge_state`, `clock`, `prev_receipt_hash`, and `signatures`. [confidence: 94/100] The normative field-level contract is in [receipt_wire.md](receipt_wire.md). [confidence: 95/100]

## Mesh reference

Runtime witnesses compose into a witness mesh whose measured object is `ORMap[AuthorityKey, EventSet]`; the threshold for convergence is deterministic equality of `canonical_mesh_projection?` after replicas receive the same content-addressed event set, with challenge add-wins, derived TTL expiry, resolver-authorized challenge resolution, and prev-hash supersession rules defined in [witness_mesh.md](witness_mesh.md). [confidence: 93/100] Any CRDT-like claim in that file is scoped to convergence of receipt state, not to semantic correctness of the underlying program. [confidence: 93/100] [Conflict-free Replicated Data Types](https://arxiv.org/abs/1805.06358)

## Local integration

The origin/main baseline contains `dharma_swarm/coalgebra.py`, `docs/telos-engine/01_SATTVA_VISION.md`, `scripts/governance/assurance_boundary.py`, and `packages/telos-gatekeeper/`, but it does not currently contain `packages/telos-kernel/`. [confidence: 99/100] `scripts/governance/assurance_boundary.py` exists at 430 lines, performs AST-static checks via the stdlib `ast` module without executing targets, emits `assurance_boundary_report.v1`, checks AB-01, AB-02, AB-03, AB-04, and AB-05, and exits with 0 for hold, 1 for violation, and 2 for measurement failure. [confidence: 98/100] `packages/telos-kernel/` remains future-only and is constrained to <= 5000 LOC for TCB verifier logic. [confidence: 98/100] `scripts/governance/a2a_reconcile_embedded_receipts.py` exists on origin/main as a present receipt reconciler relevant to later PR #6 work, distinct from the absent `dharma_swarm/reconciler.py`. [confidence: 98/100]

## Non-normative coalgebra

The coalgebraic section is design intent for PR #6, not a normative proof obligation in PR #2. [confidence: 96/100] A later reconciler should model mesh evolution as a labelled transition coalgebra `c : MeshState -> AuthorityObservation × P_fin(Event × MeshState)`, where `AuthorityObservation = (canonical_status, unresolved_challenge_ids, expiry_status, authority_key)` and each transition label is an admissible mesh event whose target is `join(state, singleton(event))`; the weaker `F_A(S) = S × AuthorityObservation` is only a projection shape, not enough for bisimulation. [confidence: 94/100] [Bisimulation of Labelled State-to-Function Transition Systems Coalgebraically](https://arxiv.org/abs/1511.05866), [Conflict-free Replicated Data Types](https://arxiv.org/abs/1805.06358) This draft claims only that [dharma_swarm/coalgebra.py](../../dharma_swarm/coalgebra.py), including its lowercase `bisimilar(...)` function, is a compatible local reference point for coalgebraic shape; it does not claim the receipt reconciler is implemented, proven, or the same functor as the evolution coalgebra. [confidence: 97/100]

## Non-normative types

The type-theory section is a foundation sketch, not a proven calculus for PR #2. [confidence: 96/100] A later proof note may model the intuitionistic dependent fragment with a category with families or an LCCC only for extensional Π, Σ, and identity types; modality-indexed evidence should be modeled as fibered modal structure, such as dependent right adjoints over context reindexing, and any linear profile should use a symmetric monoidal fibration over the non-linear base rather than treating LCCC alone as sufficient. [confidence: 94/100] [The biequivalence of locally cartesian closed categories and Martin-Löf type theories](https://www.cambridge.org/core/journals/mathematical-structures-in-computer-science/article/abs/biequivalence-of-locally-cartesian-closed-categories-and-martinlof-type-theories/6ECB295B1246A85D5DD92E5F38428D99), [Modal Dependent Type Theory and Dependent Right Adjoints](https://arxiv.org/abs/1804.05236), [Linear Dependent Type Theory](https://www.mscs.dal.ca/~selinger/papers/lindep.pdf)

## Target theorems

Five target properties define the proof agenda; the measured object for every property is `(receipt, mesh_state, current, t)` plus the finite trust-base snapshot and fragment relation named by the receipt, and the threshold for claiming any property as proven is a companion proof artifact that names the calculus, assumptions, checker, and checked fragment. [confidence: 96/100] [A logical reconstruction of SPKI](https://arxiv.org/abs/cs/0208028), [Conflict-free Replicated Data Types](https://arxiv.org/abs/1805.06358)

Target property, modality-indexed validity: for any receipt `r`, current authority context `c`, and time `t`, `admissible_evidence(r, c, t)` may count an evidence record `e` only when `e.modality in Allowed(r.claim.claim_class, r.claim.claim_strength)`, `e.result` and modality body meet the modality threshold, and `e.trust_base_id` and `e.fragment_id` match the receipt authority or a named checked-refinement receipt; if `e.modality` is not in `Allowed(r.claim.claim_class, r.claim.claim_strength)`, then `e` contributes zero admissible evidence unless a separate `Proven_by` receipt proves the coercion rule under the same trust base and fragment. [confidence: 94/100] [Modal Dependent Type Theory and Dependent Right Adjoints](https://arxiv.org/abs/1804.05236), [A logical reconstruction of SPKI](https://arxiv.org/abs/cs/0208028)

Target property, canonicality decidability: for any finite JCS receipt `r`, finite mesh state `S`, finite current authority record `c`, finite trust-base snapshot `K`, and RFC 3339 observation time `t`, `canonical?(r, S, c, t)` terminates with `true` or `false`, with unresolved external lookup, missing key status, malformed time, unsupported signature algorithm, unknown modality, or non-terminating verifier replay represented as `unknown` at the diagnostic layer and therefore `false` for authority transfer. [confidence: 93/100] [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785), [A logical reconstruction of SPKI](https://arxiv.org/abs/cs/0208028)

Target property, monotonicity under fragment narrowing: for any canonical receipt `r` over fragment `F`, sub-fragment `F'`, mesh state `S`, current authority `c`, and time `t`, if the trust base declares `F'` is a sub-fragment of `F`, the claim restriction `restrict(r.claim, F')` is defined, every admissible evidence obligation for `F` entails the restricted obligation for `F'`, all authority, claim hash, challenge-base, current, and signature inputs are coherently recomputed for `F'`, the restricted receipt has `signatures_valid(restrict(r, F'), restrict(c, F'), t) = true` or names a checked refinement receipt authorizing the restriction, and no new unresolved challenge exists for the narrowed authority key inside the evidence horizon, then `canonical?(restrict(r, F'), S, restrict(c, F'), t) = true`. [confidence: 92/100] [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)

Target property, non-monotonicity under widening or trust-base substitution: there exists a receipt `r`, mesh state `S`, current authority `c`, time `t`, super-fragment `F+`, and trust base `T+` such that `canonical?(r, S, c, t) = true`, but replacing `F` by `F+` without new admissible evidence makes `admissible_evidence = 0` or exposes an unresolved challenge, and replacing `T` by `T+` without checked refinement makes `signatures_valid` or `authority_matches` false. [confidence: 94/100] [A logical reconstruction of SPKI](https://arxiv.org/abs/cs/0208028)

Target property, bounded challenge completeness: for any receipt `r`, mesh state `S`, current authority `c`, and observation time `t`, if there exists a valid `challenge_opened` event `e` in `S[authority_key(r)]` with `e.observed_at` inside `r.challenge_base` horizon and no valid authorized `challenge_resolved` event for `e` with `observed_at <= t`, then `canonical?(r, S, c, t) = false`; conversely, if every such challenge has an authorized resolution before `t` and all other `canonical?` conjuncts hold, the challenge predicate alone does not block canonization. [confidence: 94/100] [Conflict-free Replicated Data Types](https://arxiv.org/abs/1805.06358), [A logical reconstruction of SPKI](https://arxiv.org/abs/cs/0208028)

## Threat model

Adversarial agents may forge causal origin, replay stale witnesses, substitute trust bases, hide counterexamples, inflate test evidence, or convert human attestation into false proof. [confidence: 94/100] NĀGA-IR counters those threats with signed receipts, TTLs, prev-hash chains, explicit epistemic origin, modality-specific thresholds, and challenge records that block canonization while unresolved. [confidence: 91/100]

## Non-normative Dharma boundary

NĀGA-IR does not claim an isomorphism between category theory, Madhyamaka, Kyoto School thought, or any dharmic tradition. [confidence: 98/100] The phrase "formal convergence" is non-normative and refers only to this measured pattern in the receipt calculus: context-dependent standing, typed transformation, invariant preservation, witnessable equivalence, and defeasible authority. [confidence: 93/100] Śūnyatā is not modeled as a terminal object; the technical rendering is that no claim has authority by svabhāva, only through context, witness, trust base, freshness, and unresolved-challenge status. [confidence: 92/100]

## Rollout

PR #2 lands only the spec triple in `specs/naga_ir/`. [confidence: 93/100] Current `dharma_swarm/connectors/sab_client.py` exports `SABContribution` packets, not NĀGA receipts; full SAB receipt export is future PR #4 work. [confidence: 97/100] Later PRs may add NĀGA receipt emission, SAB shadow receipt export, titanium metadata, coalgebraic reconciliation, and arena design, but this core spec must remain compatible with those stages without pretending they already exist in this checkout. [confidence: 94/100]

## Appendix B Related work

This appendix is non-normative survey material: [First-Class Verification Dialects for MLIR](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Verif Dialect](https://circt.llvm.org/docs/Dialects/Verif/), and [SMT Dialect](https://mlir.llvm.org/docs/Dialects/SMT/) ground the dialect-level verifier-IR family resemblance but not authority transfer; [Viper](https://www.pm.inf.ethz.ch/research/viper.html), [Nagini](https://www.pm.inf.ethz.ch/research/nagini.html), and [Fifteen Years of Viper](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf) ground verifier output as liftable `Proven_by` evidence but not NĀGA-IR canonization; [Cursor Origin](https://cursor.com/origin) and [Agent Trace](https://axiomstudio.ai/blog/cursor-agent-trace-explainer) ground `causal_origin` and attribution-trace inputs but not `epistemic_origin` or proof; [EcoLANG](https://arxiv.org/abs/2505.06904) grounds communication-compression motivation for replay and adversarial testing, while PACT, UCCP, and BabelTele remain uncited until public sources are supplied. [confidence: 91/100]
