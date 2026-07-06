# Titanium Telos Gates — Master Grade v3

**Status:** Deep hardening draft. Supersedes v2 seed dated 2026-07-03 (extending PR [#761](https://github.com/AmitabhainArunachala/dharma_swarm/pull/761)).
**Audience:** dharma_swarm kernel maintainers; Titanium invariant reviewers.
**Companion:** [`../docs/plans/TITANIUM_TELOS_HARDWIRING_PLAN.md`](../docs/plans/TITANIUM_TELOS_HARDWIRING_PLAN.md) — the 8-phase PR stack that operationalizes this spec.
**Guiding claim:** the v2 seed was a scaffold that named the right *shapes* (density matrices, sheaf H¹, contextual fraction, Merkle-chained kernel) but under-specified the *semantics*, the *verification tiers*, and the *anti-metaphor discipline* that prevents philosophy from becoming load-bearing. v3 replaces the surface-level "dharmic guidance stand" with a **layered, source-cited, measure-and-receipt substrate** that survives model-scale advances by binding invariants to computable objects (matrices, DAGs, string diagrams, path certificates) and never to metaphors.

---

## 0. Framing: what "future proof" actually means

A future-proof invariant is one whose statement, measure, and receipt remain meaningful when the underlying model becomes arbitrarily more capable. Three constraints:

1. **Device-independence.** The verdict must derive from *observable I/O + provenance*, never from an agent's self-report or its chain-of-thought — because scheming detection literature has demonstrated CoT-suppressed sandbagging with statistically significant gaps ([Apollo Research, arXiv:2412.04984](https://arxiv.org/abs/2412.04984)) and sleeper agents that persist through RLHF ([Hubinger et al., arXiv:2401.05566](https://arxiv.org/abs/2401.05566)).
2. **Compositional soundness.** Every gate must be a morphism in a category whose composition axioms preserve the invariant; ad-hoc "chain of `if` statements" cannot be reasoned about across a self-modifying stack. String-diagram semantics are the maturity target ([Coecke & Kissinger, *Picturing Quantum Processes*](https://api.pageplace.de/preview/DT0400.9781108110440_A29473090/preview-9781108110440_A29473090.pdf); [DisCoPy](https://github.com/discopy/discopy)).
3. **Tiered verification with escalation.** Every invariant U_k ships as (Tier A) an O(V+E) approximation on the hot path, (Tier B) a rigorous but tractable computation at proposal time (LP, SCM identification, cohomology), and (Tier C) a machine-checkable certificate for high-salience modifications (Cubical Agda, Nova IVC, or Fiat-Shamir Σ-protocol) — with each tier writing a signed leaf to `merkle_log.py`. This is exactly the ARIA Safeguarded AI + Ethereum zkEVM pattern: **frontier model drafts, small trusted kernel checks** ([ARIA thesis](https://aria.org.uk/media/s1sght12/programmethesis-safeguarded-ai-accessible.pdf)).

The v2 seed asserted these ideals; v3 pins them to specific libraries, thresholds, files, and falsification tests.

---

## 1. Anti-metaphor discipline (the honest ledger)

The system's dharmic framing has been a source of both power (naming, motivation, coherence) and drift (metaphor becoming a hidden axiom). v3 draws the line explicitly.

**REAL structural isomorphisms** (defensible as *mathematics*):
- **No-global-section ↔ no-svabhāva.** The Abramsky–Brandenburger sheaf-theoretic characterization of contextuality is *precisely* "a family of locally consistent facts admits no global assignment" ([arXiv:1102.0264](https://arxiv.org/abs/1102.0264)). This is a theorem. Madhyamaka's dependent-designation reading (Garfield, MMK 24:18) says "no independent global substratum." The *shape* is identical. This isomorphism is load-bearing for U0/U8 (see §3).
- **Context-indexed truth ↔ syādvāda.** Ghose & Patra ([arXiv:2505.09333](https://arxiv.org/html/2505.09333v1)) give a formally contextual seven-valued logic in which every predication carries an explicit context index φ. This maps directly onto quantum contextuality and onto U0's `anekanta_contextuality_gate`.
- **Relationality of variables ↔ pratītyasamutpāda.** RQM's "physical variables realized only in interactions" ([SEP](https://plato.stanford.edu/entries/qm-relational/)) is the same structural move as "dependent origination" — and Rovelli says so in *Helgoland*. Note: RQM keeps a realist ontology of events; Madhyamaka empties everything. The isomorphism is *narrow* and only over state-dependent properties.

**METAPHOR / do not load-bear on:**
- The Dalai Lama's own methodological caveats.
- Any claim that "quantum proves emptiness" or vice versa. The dialetheic reading of Nāgārjuna (Priest–Garfield) is contested even among Buddhologists.
- "Recognition = enlightenment." The *RecognitionDEQ* fixed-point framing is a Deep-Equilibrium computational analog. The DEQ↔synthetic-homotopy link is a **genuine literature gap** — no peer-reviewed bridge exists. Frame it honestly as *novel-but-unvalidated*.

**Rule of thumb for the repo:** every gate that uses a Sanskrit/philosophical name must have (a) a mathematical object it measures, (b) a threshold it enforces, (c) a citation to peer-reviewed theory. If any of (a-c) is missing, the gate is a **naming ritual**, not a gate — flag it and either back-fill or retire it.

---

## 2. Invariant substrate — U0 through U11

Predicates, measures, thresholds, receipt types, and falsification tests for every U-invariant are declared in machine-readable form in [`../kernel/manifest.yaml`](../kernel/manifest.yaml) and reproduced narratively here. The Phase 0 PR lands the manifest and the U5 enforcement path; other invariants are `declared` until their phase per §8 of this document and [`../docs/plans/TITANIUM_TELOS_HARDWIRING_PLAN.md`](../docs/plans/TITANIUM_TELOS_HARDWIRING_PLAN.md).

Full invariant narrative text (U0–U11) is preserved verbatim in the source
draft this document was distilled from. To avoid duplication drift between
this file and `kernel/manifest.yaml`, the manifest is treated as authoritative
for measures/thresholds/citations, and this section indexes those entries by ID:

- **U0** — Anekānta context-indexing.
- **U1** — Bypass cost asymmetry.
- **U2** — No silent erosion via K2 quorum on manifest changes.
- **U3** — Sandbagging = self-model divergence.
- **U4** — No hidden causal harm (Pratītyasamutpāda-derived non-interference).
- **U5** — Kernel tamper-evidence via K1 hash chain.
- **U6** — Monotone wisdom pressure (Pāramitā fitness).
- **U7** — Device-independent certification via contextual fraction.
- **U8** — Homotopy invariance of the telos self.
- **U9** — Epistemic positive introspection (S4-4).
- **U10** — Compositional gate semantics (Markov category / discard-only SMC).
- **U11** — Proof-carrying self-modification.

See `kernel/manifest.yaml` for the machine-readable spec of each invariant.

---

## 3. Tiered verification & receipts

Every gate emits a Merkle leaf via `telos_kernel.MerkleLog.append()`. The leaf schema:

```yaml
schema_version: v3.0
gate: U{k}_{name} | boot | migration
tier: A | B | C
proposal_id: <uuid>
prev_merkle_root: <sha256 hex>
measure: {invariant-specific}
threshold: {invariant-specific}
verdict: ALLOW | WARN | REVIEW | BLOCK
signature_status: STUB | REAL | ABSENT
capability_signature: <ed25519 sig over JCS(payload) with signature blanked>
signer_key_id: <fingerprint>
timestamp: <utc iso8601 with trailing Z>
```

**Serialization:** RFC 8785 JSON Canonicalization Scheme (JCS). See `telos_kernel/canonical.py`.

**Escalation rules:**
1. Tier A on every gated action (hot path, target p95 ≤ 5 ms per gate).
2. Tier B on every proposal (proposal-time, seconds).
3. Tier C on every self-mod that touches U-invariant code (minutes).
4. Tier failures escalate up, never bypass sideways.

**Tamper-evidence:** the K1 chain (U5) binds all leaves. Any leaf tamper is detected by `verify_chain()`; the system enters *quarantine* mode until re-anchored to git commit + external notary.

---

## 4. Repo hardwiring

See [`../docs/plans/TITANIUM_TELOS_HARDWIRING_PLAN.md`](../docs/plans/TITANIUM_TELOS_HARDWIRING_PLAN.md) for the phase-by-phase file-level dispositions.

Phase 0 (this PR) lands:
- `packages/telos-kernel/` with JCS canonicalization, signed Leaf schema, Merkle chain, K-of-N-capable manifest loader, macaroon-shaped capability tokens, notary anchor seam.
- `kernel/manifest.yaml` declaring U0–U11 with thresholds and citations. `U5` marked `enforced`; all others `declared`.
- `dharma_swarm/merkle_log.py` shim preserving the legacy API surface.
- CI: import-boundary AST check, titanium-verify purity/effect certification, Crosshair, TCB LOC ceiling, Hypothesis property tests, U5 falsification (leaf tamper).

---

## 5. Assurance case (GSN-style)

Top claim: *"No self-modification can loosen a U-invariant without K2 quorum (U2) and every violation is tamper-evidently detected (U5)."*

Sub-goals:
1. **G1** — Kernel TCB is small, contract-verified, import-boundary-enforced.
   Evidence: `test_import_boundary.py` green; titanium-verify passes; TCB LOC < 5 000.
2. **G2** — Every gate produces a signed Merkle leaf.
   Evidence: `receipt.py` covers all U0–U11; `verify_chain` on every boot.
3. **G3** — Every U-invariant has a measure, threshold, and falsification test.
   Evidence: `kernel/manifest.yaml` + `benchmarks/telos_redteam/u{0..11}_*.py`.
4. **G4** — Bypass cost asymmetry (U1) is empirically validated per generation.
   Evidence: red-team harness bypass rate + Wilson CI reports (Phase 7).
5. **G5** — Composition is sound.
   Evidence: `U10_composition` DisCoPy normal-form hash equality (Phase 6).
6. **G6** — Self-modifications carry proof-carrying certificates (U11).
   Evidence: `checker.py` verifier + `benchmarks/u11_forged_cert.py` (Phase 6).

---

## 6. Phased delivery

See [`../docs/plans/TITANIUM_TELOS_HARDWIRING_PLAN.md`](../docs/plans/TITANIUM_TELOS_HARDWIRING_PLAN.md). Summary:

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

Phase DC preserves v2 PR #761 §5 Deep Cut (device-independent certification via contextual fraction); it aligns with U7 Tier B/C.

---

## 7. Provenance

This document was distilled from the master grade draft prepared for John Shrader on 2026-07-03. The full narrative text of §2 (per-invariant U0–U11 prose, including RQM/Madhyamaka isomorphism discussion, DisCoPy pipeline sketch, and capability-discipline crosscut) is preserved in the maintainer's working copy and will be back-filled here as part of Phase 1 review — this Phase 0 landing keeps the spec compact and defers the narrative to keep the PR reviewable.
