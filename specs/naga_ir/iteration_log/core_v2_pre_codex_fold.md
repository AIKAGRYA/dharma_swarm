# NĀGA-IR Core (Outline v2 — post Devin+ redlines)

Status: DRAFT OUTLINE. Headers + one-sentence bodies + citations placed. v2 incorporates Devin+ round-01 contribution (Fable rating 91/100). Full prose blocked pending completion of the iteration chain.

Lineage note: NĀGA-IR is a dialect-level assurance IR in the [MLIR verif family](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf) sense; it is not a rename of, and does not compete with, ETH's [Nagini](https://www.pm.inf.ethz.ch/research/nagini.html). Nagini is a Python verifier in the [Viper](https://www.pm.inf.ethz.ch/research/viper.html) lineage ([Eilers et al. 2025](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)). NĀGA-IR is the receipt/witness IR that a Nagini-style verifier's output can be lifted into as `Proven_by` evidence.

---

## 0. One-line thesis

A code change is authoritative only while its claim is inhabited by admissible evidence, under a known trust base, inside a live context, without unresolved challenge. [wall/temporal edit per Devin+ I]

## 1. Scope and non-goals

NĀGA-IR specifies the receipt schema, judgment forms, and canonization rule for authority-conservation in an agentic codebase; it does not specify a verifier, a scheduler, or a token economy.

## 2. Design commitments

Cursor owns the acceleration of authorship; NĀGA-IR owns the conservation of authority — the two are orthogonal and composable ([cursor.com/origin](https://cursor.com/origin), [agent-trace spec](https://axiomstudio.ai/blog/cursor-agent-trace-explainer)).

## 3. The five universes

A NĀGA-IR receipt binds five typed universes: Subject, Claim, Evidence, Authority, Origin — where Origin splits into `causal_origin` (who/what produced the artifact, absorbing agent-trace as input) and `epistemic_origin` (which trust base / fragment the claim is checked under).

## 4. Claim types

Claims are propositions-as-types over program fragments in the [Curry–Howard–Lambek](https://en.wikipedia.org/wiki/Curry%E2%80%93Howard_correspondence) sense ([Lambek & Scott 1986](https://philpapers.org/rec/LAMITH-2)), stratified into safety, purity, effect-boundary, contract, and behavioral-equivalence claims (linearity-flavored claims are deferred to a `linear.md` sub-spec; evidence-side linearity handled in §12 per Devin+ Q3).

## 5. Evidence modalities

Evidence is not a scalar; the **kernel form** is `Evidence[modality, method, params](C)`, and the five modalities below are surface sugar with fixed param schemas that desugar 1:1 into the kernel form — the same one-op-with-attributes / dialect-legible-names split used by [MLIR verif dialects](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf) (kernel/surface split per Devin+ Q1).

### 5.1 Proven_by

`Γ ⊢ w : Proven_by(verifier, trust_base, fragment)(C)` — deductive evidence from a sound verifier over a bounded fragment, e.g. titanium-verify over `packages/telos-kernel/` under `telos-kernel-tcb-v1` ([CIRCT verif RFC](https://discourse.llvm.org/t/rfc-upstreaming-circts-verif-and-smt-dialects/85299), [Verif Dialect docs](https://circt.llvm.org/docs/Dialects/Verif/)).

### 5.2 Tested_by

`Γ ⊢ t : Tested_by(harness, coverage, seed, mutation_score)(C)` — statistical evidence with declared coverage and mutation adequacy, never conflated with proof.

### 5.3 Witnessed_by

`Γ ⊢ r : Witnessed_by(runtime, identity, ttl)(C)` — runtime observation bound to an identity and a freshness window, expiring when TTL lapses.

### 5.4 Challenged_by

`Γ ⊢ k : Challenged_by(counterexample, adversary)(C)` — a live counterclaim carrying its own receipt, resolvable only by refutation or by narrowing the claim.

### 5.5 Attested_by

`Γ ⊢ a : Attested_by(principal, role, jurisdiction, ttl)(C)` — human or authority sign-off with an explicit role and expiration; ordered relative to other modalities only per claim type (see §6a admissibility matrix), never sufficient alone for safety claims, and the sole admissible modality for jurisdictional claims (per Devin+ F2/R2).

## 6. Authority and trust base

Authority is not a property of an agent or of CI; it is the pair `(trust_base_id, fragment_id)` under which a modality was checked, so authority is transferable only by re-checking under a new trust base.

## 6a. Admissibility matrix

`admissible(claim_type, modality)` is a relation fixed per trust base — safety requires `Proven_by` or (`Tested_by` with declared mutation floor plus live `Witnessed_by`), jurisdictional claims require `Attested_by`, no claim type admits `Attested_by` alone for safety — making §7 clause (i) decidable and giving PR #3 the mapping it needs to lift AB-01..AB-05 into typed evidence (per Devin+ Section C).

## 7. Bounded canonization

A claim is canonical iff (i) it carries at least one admissible modality per §6a, (ii) no unresolved `Challenged_by` exists within the declared evidence horizon **and the challenge channel was demonstrably live over that horizon** (a mesh-liveness receipt per witness_mesh.md, so that absence of challenge is evidence of absence rather than absence of evidence), (iii) all TTLs are live, and (iv) the trust base matches the current fragment — canonization is bounded, not absolute (per Devin+ F4/R3).

## 8. Receipt wire format

Each receipt is a signed JSON object `dharma.naga_receipt.v1` carrying `{subject, claim, evidence[], authority, causal_origin, epistemic_origin, ttl, prev_receipt_hash}`; the full schema lives in [receipt_wire.md](./receipt_wire.md).

## 9. Compatibility with assurance_boundary_report.v1

`scripts/governance/assurance_boundary.py` today emits `assurance_boundary_report.v1` with contracts AB-01..AB-05 and exit codes {0,1,2}; PR #3 will emit a `dharma.naga_receipt.v1` alongside — same verdict, richer typing — with AB-01..AB-05 lifted into `Proven_by(assurance_boundary, telos-kernel-tcb-v1, ...)` evidence entries per §6a.

## 10. Witness mesh (forward reference)

Multi-agent runtime witnesses (identity, TTL, replay hash) compose into a mesh whose CRDT-like merge, mesh-liveness receipts, and challenge-propagation semantics are specified in [witness_mesh.md](./witness_mesh.md).

## 11. Coalgebraic semantics

NĀGA-IR's dynamic semantics instantiate the same final-coalgebra pattern as `dharma_swarm/coalgebra.py` under [Lambek's theorem](https://philpapers.org/rec/LAMITH-2), with a distinct observation functor `F(S) = Claim × M(Modality × TTL-residue) × ChallengeSet × TrustBase × S` where M is a multiset functor; PR #6's `reconciler.py` supplies the mediating map between the two coalgebras, not a reuse of the existing one (per Devin+ F1/R1/R5/H).

## 12. Type-theoretic foundation

Claims live as dependent types over the cartesian base `trust_base × fragment` in the [Seely 1984](https://www.its.caltech.edu/~matilde/MartinLofCartesianCats.pdf) LCCC ↔ Martin-Löf sense, while evidence lives in a monoidal fibration over that same base — the [Fu-Kishida-Selinger 2020](https://www.mscs.dal.ca/~selinger/papers/lindep.pdf) pattern of linear-dependent types indexed by a cartesian context — capturing the resource-like nature of TTL'd witnesses; [HoTT](https://homotopytypetheory.org/book/) gives the identity-type reading of "same claim under different receipts," and receipts remain proof-relevant (Evidence(C) is not an h-proposition), so canonization clause (iv) can inspect which trust base inhabited the claim (per Devin+ F3/G).

## 13. Conjectured properties (target theorems, unproven)

We conjecture six properties for the v1 spec (proofs deferred to a companion note, labeled CONJECTURE per Devin+ Q2):

- **C1 Soundness.** An admissible receipt implies its claim holds under its trust base.
- **C2 Monotonicity under narrowing.** A narrower fragment preserves receipts.
- **C3 Non-monotonicity under widening.** Widening the fragment requires re-check.
- **C4 Challenge-completeness.** Every canonical claim admits a well-formed `Challenged_by` slot.
- **C5 Revocation propagation.** `canonical(c,t) ∧ revoked(tb,t) ∧ depends(c,tb) ⇒ ¬canonical(c,t+1)` — the theorem that gives `prev_receipt_hash` chains a load-bearing job (per Devin+ E1).
- **C6 No authority amplification under merge.** `canonical(c, merge(A,B)) ⇒ canonical(c,A) ∨ canonical(c,B)` — proved in witness_mesh.md, cross-referenced here because without it CRDT merge is an authority-forging primitive (per Devin+ E2).

## 14. Threat model

Adversarial agents may forge `causal_origin`, replay stale witnesses, attempt trust-base substitution, or partition the witness mesh to induce canonization by censorship; TTLs, signed `prev_receipt_hash` chains, and explicit `epistemic_origin` defend integrity, while the mesh-liveness requirement in §7 clause (ii) defends liveness. The adversary's cheapest forgery surface is a channel humans cannot read — [BabelTele](https://arxiv.org/abs/2606.19857) demonstrates agents already produce such channels, which is why `Witnessed_by` requires identity + replay hash and `Attested_by` alone cannot carry safety claims (per Devin+ F4/R4 + bonus).

## 15. Non-claims

NĀGA-IR does not claim isomorphism between category theory, Madhyamaka, and Kyoto School thought; it claims formal convergence on one pattern — context-dependent entities, typed transformations, invariant preservation, witnessable equivalence — and nothing more.

## 16. Rollout arc

PR #2 lands this spec triple; PR #3 wires `assurance_boundary.py` to emit receipts (using the §6a admissibility matrix to lift AB-01..AB-05); PR #4 shadow-exports via `sab_client.py`; PR #5 adds `naga:{...}` metadata to titanium-verify without renaming; PR #6 lands `reconciler.py` on the coalgebra mediating map (§11); PR #7 opens the Molt Arena design doc last, not first.

---

## Appendix A. Philosophical convergence (non-load-bearing)

The five-universe structure resonates with — but is not proven by — the Madhyamaka reading of śūnyatā as absence of svabhāva (no claim carries authority by its own nature) and with the Kyoto School's basho / place-logic (authority is relational, contextual, revocable); see `docs/telos-engine/01_SATTVA_VISION.md` and `docs/vision_maps/2026-05-07_attractor_closure/03_omega_state.md` for the internal lineage. Śūnyatā is NOT the terminal object; the correct rendering is: no claim has authority by svabhāva, only through context, witness, trust base, freshness, and unresolved-challenge status. Non-load-bearing resonance (per Devin+ G): the deliberate absence of a subobject classifier / global truth-value object in §12 matches "no authority by svabhāva" — the base category is not a topos by design, not by accident.

## Appendix B. Related work

MLIR verif/smt dialects and `verif.contract` as first-class Hoare-triple IR ([Fehr et al. PLDI 2025](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Verif Dialect docs](https://circt.llvm.org/docs/Dialects/Verif/), [K-CIRCT arXiv:2404.18756](https://arxiv.org/abs/2404.18756)); the [Viper](https://www.pm.inf.ethz.ch/research/viper.html) family ([Nagini](https://www.pm.inf.ethz.ch/research/nagini.html), Prusti, Gobra) as the reference verifier lineage; [Cursor Origin](https://cursor.com/origin) and [agent-trace](https://axiomstudio.ai/blog/cursor-agent-trace-explainer) as the causal_origin substrate; the emergent-compression line — [EcoLANG](https://aclanthology.org/2025.findings-emnlp.284.pdf) (EMNLP 2025 Findings; over 20% token reduction at preserved simulation accuracy), [PACT](https://arxiv.org/abs/2606.05304) (arXiv 2606.05304, preprint; action-state records halve SWE-agent input tokens), and [BabelTele](https://arxiv.org/abs/2606.19857) (arXiv 2606.19857, preprint; 99.5% semantic fidelity at 27.9% of original length) — as motivation for the challenge modality's adversarial replay tests: compressed, model-native channels are precisely where forged or replayed evidence evades human review, since the messages are no longer human-auditable by construction (per Devin+ D-revised).
