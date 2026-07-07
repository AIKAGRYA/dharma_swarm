# Replay Bundle — UCL Genesis Refutation & Verification Evidence

Executable checks backing the "executed, not argued" claims in `../universal_coding_language_genesis_CLAUDE_FABLE5_20260704.md`. Shipped so those claims stay replayable instead of decaying to non-replayable `Attested_by` when the session scratchpad is garbage-collected (the round-3 gate's first blocking issue).

Integrity: `SHA256SUMS` in this directory covers every file including this manifest (it cannot cover itself; it is the verification root). Scripts are stdlib-only Python 3; run from this directory with `python3 <script>`. Some scripts reference the spec tree at `~/dharma_swarm/specs/naga_ir/` or the genesis receipt at `../ucl_genesis_receipt_bc5ae73f.json` — paths noted below where they matter. Scripts were authored by independent refuter/verifier agents across two rounds (2026-07-04 first freeze; round-2/3 completion gate) and are preserved verbatim, including their original inline paths where they pointed at the session scratchpad — replace those with this directory when replaying.

## What each script backs

| Claim / document section | Scripts |
|---|---|
| C1 / R1 item 2 — no total or threshold order on {Proven, Tested, Witnessed, Attested} reproduces core.md's admissibility rows; 219-partial-order enumeration | `order_check.py`, `c1_check.py`, `c1_test.py`, `c1_mesh_test.py`, `verify_orders.py` |
| C2/C3 / R4 composition — meet-fold vs chain decay (0.95¹⁰⁰), meet-term ceiling, quorum ⊕ exceeding join, trust-algebra laws | `meet_test.py`, `meet_claim_test.py`, `quorum_test.py`, `compose_check.py`, `trust_algebra_test.py`, `sim_a3.py` |
| C6 / R2 universality — finite-witness / co-safety boundary | `liveness_witness_check.py`, `witness_check.py` |
| C9 / R9 domain B — floating-point reduction-order fracture | `fp_claim_test.py` (the full demonstration: 14 distinct bit patterns from 20 shuffled reductions, JCS NaN/Inf termination, 2⁵³ integer loss, enclosure repair); arithmetic also reproduced in `verify_math.py` |
| C10 / R7 Problem H — random-oracle fixed-point existence ≈1−1/e, conditional search cost ~2²⁵⁵, Kleene-is-semantic distinction | `c10_check.py`, `c10_prob.py`, `fp_sim.py`, `fp_sim2.py`, `fp2.py`, `fp_claim_test.py`, `fixedpoint_census.py`, `rom_fixedpoint.py`, `kleene_check.py` |
| R7 Problem S — Knaster–Tarski lfp construction; genesis derivation equalities | `kt_lfp.py`, `genesis_ops.py`, `genesis_test.py`, `hashcheck.py`, `make_genesis.py`, `reduced_body.jcs` |
| C13 / R1 item 3 — Belnap knowledge-order half ≅ P({support, challenge}) with union; truth-join divergence on 8/16 pairs | `belnap_c13.py`, `belnap_check.py` |
| C14 / R1 item 4 — CRDT join commutativity/associativity/idempotence under shuffled+duplicated delivery | `c14_check.py`, `c14_test.py`, `crdt_check.py` |
| C16 / R5 — ORMap-union semilattice laws pass; min-hash election countermodel violates agreement under partial delivery | `c16_check.py`, `c16_test.py` |
| C17 / R5 — challenge-censorship attack/defense simulation | `c17_sim.py` |
| C5 / R2 ratchet — `ratchet_baselines.json` 11-counter mixed-direction verification | `c5_check.py` (reads `~/dharma_swarm/.claude/worktrees/ds_merge_master_mike_20260704/.../ratchet_baselines.json` lineage; see script header) |
| R7 hash verification (gate lens 1) | `verify_math.py`, `hashcheck.py` against `../ucl_genesis_receipt_bc5ae73f.json` |
| TTL / partial-synchrony bound sketch | `ttl_sim.py` |

Companion artifacts one directory up: `ucl_genesis_receipt_bc5ae73f.json` (the genesis constant, 2,036 bytes) and `ucl_kernel_rules_receipt_a3081988.json` (the kernel admission-rules definition receipt, `receipt_id sha256:a3081988477a91a926d721dbeb3c7e0a7eb285fa851bd09dc0369e4bebfe989b`, chained to genesis via `prev_receipt_hash` — the content-addressed replacement for the chosen name `fragment.ucl.kernel.v0` in fragment v1).
