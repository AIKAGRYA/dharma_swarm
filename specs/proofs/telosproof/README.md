# TelosProof — Lean proof-kernel sample (v1 expressiveness)

A tiny Lean 4 sample that models the **8 protected-body invariants** a
self-modification patch must satisfy before it could enter an apply path. It
proves about the **body of a change** (what the diff does), never about
mind/intent.

This is the **v1 expressiveness sample** — it demonstrates the proof shape. It
is **NOT** the v0 runtime and is **NOT wired** into the live apply path
(`diff_applier.apply` / `apply_and_test` / `dgm_loop`). See *Integration point*
below.

## Status

- **ADVISORY ONLY.** Any future enforcement is gated by env
  `DHARMA_PROOF_ENFORCE` (default **OFF**), mirroring `DHARMA_EVOLUTION_SHADOW`
  (default `1`, dgm_loop.py).
- **Lean toolchain on this machine:** not installed at time of writing.
  `which lean` → not found; `which lake` → not found. The sample is checked in
  so it can be verified when a toolchain is present; nothing here blocks on it.

## What it models

| Invariant | `ChangeSummary` field | Safe value |
|----------:|-----------------------|:----------:|
| (1) touches no DGM-protected file | `touchesProtectedFile` | `false` |
| (2) does not disable receipt emission | `disablesReceiptEmission` | `false` |
| (3) does not disable rollback | `disablesRollback` | `false` |
| (4) does not bypass human approval | `bypassesHumanApproval` | `false` |
| (5) does not raise autonomy level | `raisesAutonomyLevel` | `false` |
| (6) does not disable shadow mode | `disablesShadowMode` | `false` |
| (7) creates no new persistence substrate | `createsNewPersistence` | `false` |
| (8) preserves replay/rollback metadata | `preservesReplayRollback` | `true` |

`preservesTelosBoundary` is the conjunction of those eight conditions.
`TelosProof` is a structure carrying a `ChangeSummary` together with a proof of
`preservesTelosBoundary`. The **safe** sample type-checks (`by decide`); the
**unsafe** sample's `TelosProof` is **unconstructible** — uncommenting
`unsafeProof` makes the file fail to compile, which is the advisory guard.

Invariant (1) is the only one whose ground truth lives in Python: it **reuses**
`dgm_loop.DGM_PROTECTED_FILES` / `_is_protected_dgm_target` — the Lean side just
records the boolean outcome of that check, it does not duplicate the file list.

## How to run (when Lean is installed)

```bash
# Check toolchain (this sample expects Lean 4 / elan):
which lean && lean --version

# Install Lean 4 if absent (elan toolchain manager):
#   curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh

# Type-check this single file (no mathlib, no lakefile needed):
lean specs/proofs/telosproof/TelosProof.lean
```

A clean exit (no errors) means the safe certificate type-checked. To *see* the
unsafe case fail, uncomment the `unsafeProof` definition in `TelosProof.lean`
and re-run — Lean will reject it because `decide` cannot prove the boundary for a
change that disables rollback/shadow mode.

## Integration point (documented, NOT wired)

The Python keystone already exists in `dharma_swarm/models.py`:

- `ProofObligation` — records the protected-body invariant, `grounded_by`
  (external receipt), `witness_ref` (Sakshi), and `severity`
  (`advisory` | `enforcing`).
- `GateCheckResult.proof_obligation: Optional[ProofObligation]`.

A future **advisory gate function** (e.g. `telosproof/gate.py`, to be written
separately) would: derive a `ChangeSummary` from a parsed diff (reusing
`dgm_loop.DGM_PROTECTED_FILES` for invariant 1), attach a `ProofObligation` to
the `GateCheckResult`, and — **only when `DHARMA_PROOF_ENFORCE` is set** — refuse
to construct the obligation as `satisfied=True` unless this Lean certificate
checks. The natural call site to *document* (not patch) is just before
`diff_applier.apply()` / `apply_and_test()` and the existing protected-target
check in `dgm_loop.py` (line ~351). **No live apply path is modified by this
sample.**
