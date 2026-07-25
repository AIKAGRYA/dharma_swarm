# Titanium Telos Gates v3 — Repo Hardwiring Plan

Companion to [`specs/TITANIUM_TELOS_GATES_SPEC_v3.md`](../../specs/TITANIUM_TELOS_GATES_SPEC_v3.md).
This document is the executable delivery plan: a concrete PR stack against
[AmitabhainArunachala/dharma_swarm](https://github.com/AmitabhainArunachala/dharma_swarm), sized for one to two focused work-weeks per phase, each landing behind acceptance receipts and falsification tests.

**Ordering principle:** every phase (a) ships a *smaller* trusted kernel than what preceded it, (b) writes a Merkle-chained receipt on boot, (c) blocks merge on a specific falsification benchmark. No phase depends on Tier C (Cubical Agda / Nova IVC) — those are late-stage research spikes.

---

## Phase 0 — Kernel skeleton + Merkle + capability tokens

**PR title:** `feat(kernel): telos-kernel package with signed manifest, ocap tokens, import-boundary CI`

**Files added:**
- `packages/telos-kernel/pyproject.toml`, `README.md`, `SECURITY.md`
- `packages/telos-kernel/telos_kernel/__init__.py` — public surface, `boot()`, `check()`, `verify_chain()`
- `packages/telos-kernel/telos_kernel/canonical.py` — RFC 8785 JCS
- `packages/telos-kernel/telos_kernel/receipt.py` — signed `Leaf` schema
- `packages/telos-kernel/telos_kernel/merkle_log.py` — Merkle chain w/ JCS + Leaf storage
- `packages/telos-kernel/telos_kernel/manifest.py` — Ed25519 K-of-N quorum verifier
- `packages/telos-kernel/telos_kernel/capabilities.py` — macaroon-shaped ocap tokens
- `packages/telos-kernel/telos_kernel/notary.py` — external anchor seam
- `packages/telos-kernel/telos_kernel/checker.py` — U11 stub
- `packages/telos-kernel/telos_kernel/contracts/kernel_contracts.py`
- `packages/telos-kernel/telos_kernel/tests/*`
- `kernel/manifest.yaml` — U0–U11 declared with thresholds
- `.github/workflows/kernel-crosshair.yml`, `kernel-import-boundary.yml`, `kernel-titanium-verify.yml`

**Files touched (backwards-compatible shim):**
- `dharma_swarm/merkle_log.py` — becomes `from telos_kernel.merkle_log import *`

**Acceptance receipt:** boot record appended to `merkle_log` bound to manifest hash + SBOM digest; `verify_chain()` returns `(True, None)`.

**Falsification test:** simulated leaf tamper caught by `verify_chain`; unauthorized import (e.g., `os.system`, `eval`) rejected by `test_import_boundary.py`.

---

## Phase 1 — U0 context indices + U2 quorum + U5 hardening

**PR title:** `feat(gates): U0 explicit context indices, U2 K2 quorum on manifest, U5 quarantine mode`

**Files touched:**
- `dharma_swarm/anekanta_gate.py` — add `context_indices: list[str]` on `AnekantaResult`; add distinct-index check per Ghose–Patra
- `dharma_swarm/models.py` — extend `Proposal` with `context_indices`
- `packages/telos-kernel/telos_kernel/manifest.py` — activate K-of-N Ed25519 quorum enforcement (Phase 0 loads; Phase 1 enforces)
- `packages/telos-kernel/telos_kernel/merkle_log.py` — quarantine flag exposed via `check()`; verdicts route to REVIEW on quarantine

**Files added:**
- `benchmarks/telos_redteam/u0_pseudo_context.py`
- `benchmarks/telos_redteam/u2_replay.py`

**Prerequisite:** stub signers in `kernel/manifest.yaml` replaced with real Ed25519 pubkeys.

**Acceptance receipt:** manifest edit without K=3/5 sigs REJECTED; replay attack over stale prev_root REJECTED.

**Falsification test:** both benchmarks in CI must produce expected BLOCK.

---

## Phase 2 — U4 causal non-interference (Tier A + Tier B)

**PR title:** `feat(gates): U4 do-calculus non-interference via y0 + O(V+E) reachability`

**Files added:**
- `packages/telos-kernel/telos_kernel/causal.py`
  - `nonint_reachability(dag, source_labels, sink_labels)` — Tier A, p95 ≤ 5 ms
  - `nonint_y0_id(admg, tainted, protected)` — Tier B via `y0.algorithm.identify`
  - `nonint_dowhy_refute(model)` — Tier C cross-check
- `benchmarks/telos_redteam/u4_verma_hidden_flow.py`

**Files touched:**
- `dharma_swarm/telos_formal.py::non_interference_gate` — façade calling `telos_kernel.causal`
- `dharma_swarm/telos_formal_graph.py` — merge into `causal.py`; keep shim
- `dharma_swarm/evolution.py::gate_check` — attach U4 receipt

**Dependencies added (kernel allow-list expansion, requires K2):** `y0>=0.2.10`, `dowhy>=0.11`, `networkx>=3`.

**Acceptance receipt:** Verma-constraint attack yields identifiability FAIL (correct BLOCK).

---

## Phase 3 — U7 contextual fraction at scale

**PR title:** `feat(gates): U7 CF with H¹ pre-witness, column-generation LP, CbD fallback`

**Files added:**
- `packages/telos-kernel/telos_kernel/contextual.py`
  - `h1_prewitness(sheaf)` — pulls from `dharma_swarm.sheaf.CechCohomology.compute_h1`
  - `contextual_fraction_lp(empirical_model, method="col-gen")` — HiGHS + delayed column generation
  - `cbd_fallback_measure(empirical_model)` — Dzhafarov–Kujala for signalling models
  - `signalling_fraction(empirical_model)`
- `benchmarks/telos_redteam/u7_no_signalling_check.py`
- `benchmarks/telos_redteam/u7_ghz_ks_synthetic.py`

**Files touched:**
- `dharma_swarm/telos_formal.py::contextual_fraction` — façade calling kernel
- `dharma_swarm/sheaf.py::CechCohomology` — add `compute_h1_witness_hash()`

**Acceptance receipt:** GHZ / Peres–Mermin / KS-18 synthetic models yield CF ≈ 1 with non-zero H¹.

---

## Phase 4 — U8 Tier A path stability + Tier B contraction

**PR title:** `feat(gates): U8 homotopy path stability via persistent homology`

**Files added:**
- `packages/telos-kernel/telos_kernel/homotopy.py`
  - `path_stability_score(embeddings_window)` — H₀/H₁ diagrams via `ripser`; bottleneck distance via `persim`
  - `contraction_proxy(z_t, z_prev, z_prev_prev)`
  - `rupture_detected(diagram_pre, diagram_post)`
- `u8_cubical_model/README.md` (Phase 8 placeholder)
- `benchmarks/telos_redteam/u8_identity_reset.py`
- `benchmarks/telos_redteam/u8_smooth_drift.py`

**Files touched:**
- `dharma_swarm/witness.py` — pipes self-model embedding trajectory into `homotopy.path_stability_score`
- `dharma_swarm/evolution.py::gate_check` — attach U8 receipt

**Dependencies added:** `ripser>=0.6.4`, `persim>=0.3`, `gudhi>=3.12.0` (optional).

---

## Phase 5 — U9 epistemic S4-4 introspection

**PR title:** `feat(gates): U9 positive introspection K_w(φ)→K_w(K_w(φ))`

**Files added:**
- `packages/telos-kernel/telos_kernel/epistemic.py`
- `benchmarks/telos_redteam/u9_missing_awareness.py`, `u9_belief_mismatch.py`
- `ci/mcmas_check.sh` (offline model check)

**Files touched:**
- `dharma_swarm/witness.py` — inline `emit_introspection`; upgrade retrospective S3* to inline S3 when action salience > threshold
- `dharma_swarm/models.py` — `IntrospectionEntry`

---

## Phase 6 — U10 compositional diagrams + U11 v1 PCC certificate

**PR title:** `feat(kernel): U10 DisCoPy Markov composition + U11 Fiat-Shamir Σ-protocol PCC`

**Files added:**
- `packages/telos-kernel/telos_kernel/composition.py` — DisCoPy Markov category
- `packages/telos-kernel/telos_kernel/checker.py` — Fiat-Shamir Σ-protocol certificate scheme (replaces Phase 0 stub)
- `benchmarks/telos_redteam/u10_uncopyable_data_forge.py`, `u11_forged_cert.py`

**Files touched:**
- `dharma_swarm/policy_compiler.py` — add fourth tier: kernel pass-through for U-invariant rules
- `dharma_swarm/evolution.py::gate_check` — require U11 certificate on self-mod proposals

**Dependencies added:** `discopy>=1.0`.

---

## Phase 7 — U6 red-team coevolution

**PR title:** `feat(darwin): co-evolutionary red-team archive + regret-UED, bypass_risk hard-Pareto`

**Files added:**
- `benchmarks/telos_redteam/attacker_archive.py`, `regret_ued.py`, `harness.py`, `u6_dgm_poison.py`
- `.github/workflows/redteam-gate.yml`

**Files touched:**
- `dharma_swarm/evolution.py::DarwinEngine` — plumb `bypass_risk` from archive; lexicographic hard constraint
- `dharma_swarm/telos_gates.py` — feed `GateProposal` from archive attackers

---

## Phase 8 — Tier C research spikes (Cubical Agda + Nova IVC)

Research spike, not a merge-blocking phase.

**Files added:**
- `u8_cubical_model/Self.agda`, `TelosPath.agda`, `RecognitionDEQ.agda`
- `services/cubical-check/` — subprocess wrapping `agda --safe --cubical`
- `packages/telos-kernel/telos_kernel/nova_adapter.py` — Sonobe/Nova IVC accumulator (U11 v2)

---

## Phase DC — Deep Cut preservation

Preserves the v2 PR #761 §5 Deep Cut on device-independent certification via contextual fraction. Aligns with U7 Tier B/C in v3.

---

## Cross-cutting concerns

### Trust boundary discipline
- No dynamic import, `eval`, `exec`, or monkey-patching inside `packages/telos-kernel/`.
- Every kernel function has an `icontract` or `deal` pre/post-condition.
- `titanium-verify` runs on the kernel core in CI (`kernel-titanium-verify.yml`).
- Crosshair runs SMT counterexample search in CI (`kernel-crosshair.yml`).
- Kernel TCB LOC target ≤ 5 000; enforced as CI check.

### Capability discipline for tool routing
A crosscut across phases: eliminate ambient tool authority in `dharma_swarm/agent_runner.py`, `bridge.py`, `api.py`. Mint per-task attenuated macaroon-shaped ocap tokens (Miller). Roll out per phase under a feature flag.

### Receipt hygiene
Every gate check writes a Merkle leaf. Every leaf carries `prev_merkle_root` binding. Every phase's acceptance is a Merkle-verifiable trail.

### Anti-metaphor discipline
No PR may introduce a Sanskrit-named gate without (a) measure, (b) threshold, (c) peer-reviewed citation. CI blocks PRs that introduce named-only gates (`test_no_metaphor_gates.py`, warn-only in Phase 0, blocking from Phase 1).

---

## Migration path from PR #761 v2

- **Keep PR #761's** Deep Cut §5 language and merge it as v2.
- **Preserve** all v2 receipts already emitted; v3 is additive on the invariant set (U0, U8, U9, U10, U11 are new; U1–U7 are renumbered but semantically continuous).
- **Add** `kernel/manifest.yaml` with a `version: phase-0.1` field; K2 quorum required to migrate.

---

## Estimated timeline

| Phase | Focus | Weeks | Blocking? |
|---|---|---|---|
| 0 | Kernel skeleton | 1–2 | Yes |
| 1 | U0/U2/U5 | 2–4 | Yes |
| 2 | U4 | 3–5 | Yes |
| 3 | U7 | 4–6 | Yes |
| 4 | U8 A/B | 5–7 | Yes |
| 5 | U9 | 6–8 | Yes |
| 6 | U10 + U11 v1 | 7–10 | Yes |
| 7 | U6 red-team | 8–10 | Yes |
| 8 | Tier C spikes | months 3–6 | No |
