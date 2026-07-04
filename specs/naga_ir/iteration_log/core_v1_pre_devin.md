# NĀGA-IR Core (Outline — pre-prose, for review)

Status: DRAFT OUTLINE. Headers + one-sentence bodies + citations placed. Full prose blocked pending review.

Lineage note: NĀGA-IR is a dialect-level assurance IR in the [MLIR verif family](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf) sense; it is not a rename of, and does not compete with, ETH's [Nagini](https://www.pm.inf.ethz.ch/research/nagini.html). Nagini is a Python verifier in the [Viper](https://www.pm.inf.ethz.ch/research/viper.html) lineage ([Eilers et al. 2025, "15 Years of Viper"](https://pm.inf.ethz.ch/publications/EilersSchwerhoffSummersMueller25.pdf)). NĀGA-IR is the receipt/witness IR that a Nagini-style verifier's output can be lifted into as `Proven_by` evidence.

---

## 0. One-line thesis

A code change is authoritative only when its claim is inhabited by admissible evidence, under a known trust base, inside a live context, without unresolved challenge.

## 1. Scope and non-goals

NĀGA-IR specifies the receipt schema, judgment forms, and canonization rule for authority-conservation in an agentic codebase; it does not specify a verifier, a scheduler, or a token economy.

## 2. Design commitments

Cursor owns the acceleration of authorship; NĀGA-IR owns the conservation of authority — the two are orthogonal and composable ([cursor.com/origin](https://cursor.com/origin), [agent-trace spec](https://axiomstudio.ai/blog/cursor-agent-trace-explainer)).

## 3. The five universes

A NĀGA-IR receipt binds five typed universes: Subject, Claim, Evidence, Authority, Origin — where Origin splits into `causal_origin` (who/what produced the artifact, absorbing agent-trace as input) and `epistemic_origin` (which trust base / fragment the claim is checked under).

## 4. Claim types

Claims are propositions-as-types over program fragments in the [Curry–Howard–Lambek](https://en.wikipedia.org/wiki/Curry%E2%80%93Howard_correspondence) sense ([Lambek & Scott 1986](https://philpapers.org/rec/LAMITH-2)), stratified into safety, purity, effect-boundary, contract, and behavioral-equivalence claims.

## 5. Evidence modalities

Evidence is not a scalar; it comes in five typed modalities, each with an explicit method, parameters, and trust base.

### 5.1 Proven_by

`Γ ⊢ w : Proven_by(verifier, trust_base, fragment)(C)` — deductive evidence from a sound verifier over a bounded fragment, e.g. titanium-verify over `packages/telos-kernel/` under `telos-kernel-tcb-v1` ([MLIR verif dialects, PLDI 2025](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [CIRCT verif RFC](https://discourse.llvm.org/t/rfc-upstreaming-circts-verif-and-smt-dialects/85299)).

### 5.2 Tested_by

`Γ ⊢ t : Tested_by(harness, coverage, seed, mutation_score)(C)` — statistical evidence with declared coverage and mutation adequacy, never conflated with proof.

### 5.3 Witnessed_by

`Γ ⊢ r : Witnessed_by(runtime, identity, ttl)(C)` — runtime observation bound to an identity and a freshness window, expiring when TTL lapses.

### 5.4 Challenged_by

`Γ ⊢ k : Challenged_by(counterexample, adversary)(C)` — a live counterclaim carrying its own receipt, resolvable only by refutation or by narrowing the claim.

### 5.5 Attested_by

`Γ ⊢ a : Attested_by(principal, role, jurisdiction, ttl)(C)` — human or authority sign-off with an explicit role and expiration; strictly weaker than Proven_by and never sufficient alone for safety claims (confidence 88/100 that this fifth modality earns its keep; open to Codex's `Evidence[modality, method, params]` uniform-form alternative at 86/100).

## 6. Authority and trust base

Authority is not a property of an agent or of CI; it is the pair `(trust_base_id, fragment_id)` under which a modality was checked, so authority is transferable only by re-checking under a new trust base.

## 7. Bounded canonization

A claim is canonical iff (i) it carries at least one admissible modality, (ii) no unresolved `Challenged_by` exists within the declared evidence horizon, (iii) all TTLs are live, and (iv) the trust base matches the current fragment — canonization is bounded, not absolute.

## 8. Receipt wire format

Each receipt is a signed JSON object `dharma.naga_receipt.v1` carrying `{subject, claim, evidence[], authority, causal_origin, epistemic_origin, ttl, prev_receipt_hash}`; the full schema lives in [receipt_wire.md](./receipt_wire.md).

## 9. Compatibility with assurance_boundary_report.v1

`scripts/governance/assurance_boundary.py` today emits `assurance_boundary_report.v1` with contracts AB-01..AB-05 and exit codes {0,1,2}; PR #3 will emit a `dharma.naga_receipt.v1` alongside — same verdict, richer typing — with AB-01..AB-05 lifted into `Proven_by(assurance_boundary, telos-kernel-tcb-v1, ...)` evidence entries.

## 10. Witness mesh (forward reference)

Multi-agent runtime witnesses (identity, TTL, replay hash) compose into a mesh whose CRDT-like merge and challenge-propagation semantics are specified in [witness_mesh.md](./witness_mesh.md).

## 11. Coalgebraic semantics

NĀGA-IR's dynamic semantics are an F-coalgebra with observation functor `F(S) = Claim × Modality-set × ChallengeSet × TrustBase × S`, whose bisimulation gives the intended equivalence-of-authority relation; this reuses `dharma_swarm/coalgebra.py` (Lambek's theorem already cited in-file) and is the substrate for PR #6's `reconciler.py`.

## 12. Type-theoretic foundation

The judgment forms are interpreted in a locally cartesian closed category with a modality-indexed fibration of evidence over claims, following [Seely 1984](https://www.its.caltech.edu/~matilde/MartinLofCartesianCats.pdf) for the LCCC ↔ Martin-Löf correspondence and [Fu, Kishida, Selinger 2020](https://www.mscs.dal.ca/~selinger/papers/lindep.pdf) for the linear-dependent fibration pattern; [HoTT](https://homotopytypetheory.org/book/) gives the identity-type reading of "same claim under different receipts."

## 13. Formal properties (target theorems)

We target four properties for the v1 spec: soundness (admissible receipt implies claim held under its trust base), monotonicity-under-narrowing (narrower fragment preserves receipts), non-monotonicity-under-widening (widening requires re-check), and challenge-completeness (every canonical claim admits a well-formed `Challenged_by` slot) — proofs deferred to a companion note, not this PR.

## 14. Threat model

We assume adversarial agents may forge causal_origin, replay stale witnesses, or attempt trust-base substitution; TTLs, signed prev_receipt_hash chains, and explicit `epistemic_origin` are the three defenses (this is where the [Moltbook / OpenClaw 1.6M-agent](https://www.bitrue.com/blog/what-is-ai-agent-moltbook-and-how-it-works) covert-channel work motivates the design, without depending on it).

## 15. Non-claims

NĀGA-IR does not claim isomorphism between category theory, Madhyamaka, and Kyoto School thought; it claims formal convergence on one pattern — context-dependent entities, typed transformations, invariant preservation, witnessable equivalence — and nothing more.

## 16. Rollout arc

PR #2 lands this spec triple; PR #3 wires `assurance_boundary.py` to emit receipts; PR #4 shadow-exports via `sab_client.py`; PR #5 adds `naga:{...}` metadata to titanium-verify without renaming; PR #6 lands `reconciler.py` on the coalgebra; PR #7 opens the Molt Arena design doc last, not first.

---

## Appendix A. Philosophical convergence (non-load-bearing)

The five-universe structure resonates with — but is not proven by — the Madhyamaka reading of śūnyatā as absence of svabhāva (no claim carries authority by its own nature) and with the Kyoto School's basho / place-logic (authority is relational, contextual, revocable); see `docs/telos-engine/01_SATTVA_VISION.md` and `docs/vision_maps/2026-05-07_attractor_closure/03_omega_state.md` for the internal lineage. Śūnyatā is NOT the terminal object; the correct rendering is: no claim has authority by svabhāva, only through context, witness, trust base, freshness, and unresolved-challenge status.

## Appendix B. Related work

MLIR verif/smt dialects and `verif.contract` as first-class Hoare-triple IR ([Fehr et al. PLDI 2025](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf), [Verif Dialect docs](https://circt.llvm.org/docs/Dialects/Verif/), [K-CIRCT arXiv:2404.18756](https://arxiv.org/abs/2404.18756)); the [Viper](https://www.pm.inf.ethz.ch/research/viper.html) family (Nagini/Prusti/Gobra) as the reference verifier lineage; Cursor Origin and agent-trace as the causal_origin substrate; the emergent-compression line (PACT, UCCP, EcoLANG, BabelTele) as motivation for the challenge-modality's adversarial replay tests.
