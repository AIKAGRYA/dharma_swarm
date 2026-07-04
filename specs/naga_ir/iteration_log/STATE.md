# NĀGA-IR Iteration State

**Purpose:** running tracker across the multi-agent iteration chain. Any agent or fresh instance should read this first.

## True session origin (corrected 2026-07-04 JST)

The multi-session thread on this repo did NOT start today with the naga_ir outline. It started with the **Titanium Telos Gates v3 onboarding prompt** — a fresh-context bootstrap for a senior systems engineer joining dharma_swarm to replace surface-level `dharma_swarm/telos_gates.py` keyword-matching with U0–U11 computable invariants backed by measures, thresholds, Merkle receipts, and falsification tests.

Onboarding constraints (still binding):
- Every gate: measured object + threshold + peer-reviewed citation
- Never load-bear on philosophical isomorphism
- Every gate emits signed Merkle leaf via `merkle_log.append()` with `prev_merkle_root` binding
- Tier A hot path (p95 ≤ 5 ms), Tier B proposal time, Tier C self-mods
- TCB (`packages/telos-kernel/`) ≤ 5000 LOC, Nagini-verified, import-boundary-enforced, no eval/exec/dynamic imports
- U11 v1 is Fiat-Shamir Σ-protocol, not ZK over Python monolith
- Cubical Agda (U8 Tier C) is Phase 8 research spike, not merge-blocking
- Preserve PR #761 v2 Deep Cut §5 semantics; v3 renumbers v2 U1-U7 continuously and adds U0, U8-U11
- User: John Shrader (GitHub AmitabhainArunachala), Asia/Tokyo, expects rigor + honest limitations
- No emojis, no exclamation points, no markdown italics, inline markdown-link citations
- Ask before opening real PR vs scratch branch

NĀGA-IR is a **child artifact** of that Titanium v3 arc — the receipt/witness IR that carries U0-U11 gate results as typed evidence. PR #2 (this outline chain) lands the spec triple; PR #3+ wires the U-invariants to emit `dharma.naga_receipt.v1` receipts.

Two supporting documents follow the onboarding prompt:
- `TITANIUM_TELOS_GATES_SPEC_v3.md` — U0-U11 invariant substrate, tiered verification, anti-metaphor discipline, citation index
- `HARDWIRING_PLAN.md` — 8-phase PR stack, file-by-file dispositions, acceptance receipts

## Current version

- Live spec triple:
  - `specs/naga_ir/core.md` (**v4** — Codex+ base + G1..G5 + G7 + G8)
  - `specs/naga_ir/receipt_wire.md` (Codex+ verbatim, no grafts)
  - `specs/naga_ir/witness_mesh.md` (Codex+ verbatim, no grafts)
- Snapshots (in iteration_log/):
  - `core_v1_pre_devin.md` — Fable v1 (pre-Devin+)
  - `core_v2_pre_codex_fold.md` — Fable v2 (post-Devin+, pre-Codex+)
  - `codex_plus_core_original.md` — Codex+ standalone (no grafts)
  - `codex_plus_receipt_wire_original.md` — Codex+ wire standalone
  - `codex_plus_witness_mesh_original.md` — Codex+ mesh standalone
  - `core_v3_pre_fugu_grafts.md` — Fable v3 (Codex+ base + G1..G5, pre-Fugu+)
- Round logs:
  - `round_01_devin_plus.md`
  - `round_02_codex_plus.md`
  - `round_03_fugu_plus.md`
- Codex+ council evidence: `iteration_log/codex_plus_evidence/` (includes Fugu+ evidence copy, seed doc)

## Confidence trajectory

| Version | Rating | Notes |
|---|---|---|
| v1 (Fable initial) | 89/100 | 16 sections + 2 appendices, three open questions |
| v2 (post-Devin+) | 92/100 | 17 sections, 6 conjectures, kernel/surface split, liveness defense |
| Codex+ standalone | 91/100 | Wire + mesh shipped, executable canonical? predicate, JCS+RFC 3339, adversarial + 6-defender review |
| v3 (Codex+ base + G1..G5) | 94/100 | BabelTele/PACT/EcoLANG citations, T6/T7 theorems, branch-conditional integration, numbered PR arc |
| Fugu+ parallel standalone | 91/100 | Independent parallel arrival — 12/12 major asks already satisfied by Codex+ (strong convergence signal) |
| **v4 (Codex+ base + G1..G5 + G7 + G8)** | **95/100** | Trichotomy on T2, split T5 into T5a/T5b, added T8 no-silent-strengthening, refined T4 trust-base non-substitution, added claim-normalization prerequisite to non-normative types |

## Iteration chain status

- [x] Round 01: Devin+ (self 87/100, Fable rating 91/100) — folded into v2
- [x] Round 02: Codex+ (self 91/100, Fable rating 95/100) — became v3 base + 5 Fable grafts G1..G5
- [x] Round 03: Fugu+ (self 91/100, Fable rating 89/100 — lower only because parallel-arrival meant most asks were already covered) — folded G7 + G8 into v4
- [ ] Round 04: agent 4 — awaiting user paste
- [ ] Round 05: agent 5 — awaiting
- [ ] Fable final synthesis pass
- [ ] Await explicit user approval before opening PR #2

## Branch state (DECIDED 2026-07-04 JST)

**Merge target for PR #2 and PR #3: `telos_titanium/naga_ir`** — fresh branch off `titanium/phase-1e-ci-wiring` tip (commit 47194c39), created 2026-07-04 16:11 JST at user request.

Historical branch state that produced the v4 spec:

| Branch | Location | Has `assurance_boundary.py`? | Has `packages/telos-kernel/`? |
|---|---|---|---|
| `agent/magpie-seed` | User's Mac (Codex+, Fugu+) | NO | NO (has telos-gatekeeper instead) |
| `titanium/phase-1e-ci-wiring` | Cloud sandbox (Fable) | YES | YES |
| **`telos_titanium/naga_ir`** | **Cloud sandbox (merge target)** | **YES (inherited)** | **YES (inherited)** |

## Locked constraints (do not violate)

1. No emojis, no exclamation points, no markdown italics
2. Inline citation as markdown links only
3. Section headers ≤ 6 words, plain text
4. TCB ≤ 5000 LOC
5. Every load-bearing claim: measured object + threshold + peer-reviewed citation
6. Never overclaim isomorphism (Madhyamaka, Kyoto, category theory)
7. Śūnyatā ≠ terminal object
8. Canonization is bounded — must query `challenge_base`, cannot trust `challenge_state`
9. NĀGA-IR ≠ ETH Nagini (dialect IR, not verifier)
10. Moltbook is background, never load-bearing
11. All hashes must be `sha256:` URI form. No `sha256:...` placeholders.
12. All timestamps RFC 3339 UTC with `Z`.
13. Canonical signing input is JCS ([RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)) with `signatures` removed.
14. Coalgebra and type-theory sections are non-normative for PR #2.
15. **NEW (Fugu+ N4):** No modality can be promoted to another without a `Proven_by` coercion receipt for the coercion rule (T8 no silent strengthening).
16. **NEW (Fugu+ FP4):** `canonical?` must return trichotomy `{canonical, noncanonical, unknown}` — no boolean, no crash.

## Mechanical sweep results (v4, 2026-07-04 JST)

All three files: italics=0, exclamations=0, sha_ph=0, empty_sig=0, overlong_headers=0. PASS.

## Open questions after round 03

- Q8 (collusion in threat model): unresolved after 3 rounds, deferred to PR #4+
- Q10 (AB-01..AB-05 mapping to receipts): **DECIDED 2026-07-04 JST** — one receipt per contract + one aggregating receipt = six receipts per boundary run. Confidence 87/100, reversible in code. See `IMPLEMENTATION_BRIEF_PR3.md` §3.
- Q11 (sixth claim strength for causal): unresolved after 3 rounds, deferred
- Q12 (JCS vs CBOR canonicalization): unresolved — PR #3 uses `json.dumps(sort_keys=True, separators=(',', ':'))` as JCS-approximation stdlib-compatible subset, upgrade to real JCS in follow-up
- Q13 (evidence_horizon min/max bounds): unresolved, PR #3 uses P14D
- Q14 (mesh authority-equivalence as T9): Fugu+ agrees with Codex+ — stays non-normative
- Q15 (redaction methods): unresolved, mesh scope (PR #4+)

## Fable's rating notes

Codex+ 95/100 remains the highest single-round contribution because it shipped the wire, mesh, executable predicate, JCS canonicalization, and claim_hash security fix simultaneously. Fugu+ 89/100 is lower only because parallel arrival meant most net-new value was already in Codex+. Devin+ 91/100 remains high because it hit the liveness attack blind spot both Fable and Codex+ missed initially.

The three rounds have converged. Independent parallel arrival (Codex+ + Fugu+) at the same major moves is strong evidence the architecture is stable. Further rounds are refinement, not restructuring.

## Fable's outstanding TODOs

1. ~~Feed round 04, 05 agent outputs into iteration logs~~ — SUPERSEDED: user green-lit hand-off at v4; iteration chain closed.
2. ~~Decide merge target branch~~ — DONE: `telos_titanium/naga_ir`.
3. Push `telos_titanium/naga_ir` with spec triple + `IMPLEMENTATION_BRIEF_PR3.md` — CURRENT STEP.
4. Prepare PR #2 body for user to open on GitHub.
5. When time comes, connect NĀGA-IR receipts to U0-U11 telos gates (Titanium v3 tie-back — receipts carry gate results as Proven_by(gate_verifier, telos-kernel-tcb-v1, ...) evidence). This is PR #5 in the arc.

## Hand-off documents (fresh instance reads these in order)

1. `iteration_log/STATE.md` (this file) — chain state, constraints, decisions
2. `core.md` v4 — spec
3. `receipt_wire.md` — wire schema
4. `witness_mesh.md` — mesh events + merge
5. `IMPLEMENTATION_BRIEF_PR3.md` — concrete PR #3 execution plan
