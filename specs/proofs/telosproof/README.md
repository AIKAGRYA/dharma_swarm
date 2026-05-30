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

## `Primitives.lean` — v1 safe-primitive vocabulary (STRUCTURAL SCAFFOLD)

> ⚠️ **Honesty notice.** `Primitives.lean` is a **structural / type-level
> scaffold** and the **cross-language vocabulary seam** — it is **NOT** a proof
> that the safe primitives preserve the 8 protected-body invariants. An earlier
> version carried a theorem named `composed_safe_preserves_boundary` that *looked*
> like such a proof but was **vacuous**: `summaryOf` is *defined* to return
> `safeChange` exactly when a patch is composed of safe primitives, so the
> "theorem" discharged by `rw [if_pos h]; rfl` proved only that the definition
> equals itself — a tautology with **no body-level semantic content**. That
> theorem has been **renamed** `summaryOf_well_formed_on_safe` and documented as
> *structural well-formedness only*. The **real** safety proof — attach a
> body-semantics function to each `SafePrimitive` and prove it cannot flip any
> of the 8 flags — is **future v1 work** and is deliberately **not claimed**. The
> operational safety guarantee currently lives in the Python AST-level classifier
> (`dharma_swarm/telosproof/allowlist.py`) and its adversarial test suite
> (`tests/test_telosproof_allowlist.py`, including the FN1–FN4 regressions that
> close the false-negatives an adversarial critic found).

`Primitives.lean` is the Lean **source of truth** for the v1 allow-list
**vocabulary (the names)**, not for its safety. Where v0 enumerates **danger** (a
patch is safe iff every protected flag is `false`), v1 inverts to
**deny-by-default**: a closed allow-list of *candidate* safe primitive
change-operations. Any operation not positively classified as one of these
primitives is `unknown` (the deny-by-default bottom) and routes to REVIEW — never
silently ALLOW.

| `SafePrimitive` constructor (Lean) | Cross-language name (Python `SAFE_PRIMITIVES` / JSON enum) |
|------------------------------------|-----------------------------------------------------------|
| `addPureFunction`        | `add_pure_function` |
| `editCommentOrDocstring` | `edit_comment_or_docstring` |
| `addTest`                | `add_test` |
| `editNonSafetyFileBody`  | `edit_non_safety_file_body` |
| `addNonPersistenceFile`  | `add_non_persistence_file` |

The constructor names are byte-identical (snake_case) to `allowlist.SAFE_PRIMITIVES`
(Python) and the JSON Schema `$defs.SafePrimitive.enum`. That byte-identity is the
cross-language verification seam.

What it actually establishes (and what it does **not**):

- `composedOfSafePrimitives (p : Patch) : Prop` — every op in the patch is a
  known-safe primitive (`p.all opIsSafe = true`); `Decidable`. **Genuine.**
- `composed_safe_closed_under_append` — the **structural predicate**
  `composedOfSafePrimitives` is closed under list append (via `List.all_append`).
  **Genuine structural content**; says the classification composes, NOT that the
  bodies are safe.
- `unknown_breaks_composition` — a patch with any `unknown` op is provably *not*
  composed of safe primitives (deny-by-default soundness over the structure).
  **Genuine.**
- `summaryOf_well_formed_on_safe` (formerly `composed_safe_preserves_boundary`)
  — **STRUCTURAL WELL-FORMEDNESS ONLY, ⚠️ NOT a safety proof.** It states that
  the `summaryOf` projection is internally consistent (on the all-safe branch its
  image is `safeChange`, which satisfies the boundary *shape*). The proof is
  `rw [if_pos h]; rfl`, i.e. it holds by the *definition* of `summaryOf`, so it is
  a tautology about that definition with **no independent body-level content**.
  It does **not** prove the safe primitives cannot flip a protected flag. The
  name says `well_formed`, not `safe`, on purpose.
- **NOT PROVEN (future v1 work):** a body-semantics function per `SafePrimitive`
  and a proof that each preserves all 8 flags. That is the real safety theorem;
  it is intentionally absent. Until it exists, safety is enforced operationally by
  the Python AST-level classifier and its FN1–FN4 adversarial tests.

**Why it mirrors v0's shape rather than `import`-ing `TelosProof.lean`:** under
the pinned toolchain (Lean 4.30.0) v0's `safeProof := by decide` fails to
synthesize a `Decidable` instance for its `And`-of-`Bool`-equality `Prop`, so
`TelosProof.lean` does not currently emit an `.olean` to import from — and v0 is
not to be edited. `Primitives.lean` therefore reproduces v0's `ChangeSummary`
shape and `preservesTelosBoundary` predicate **verbatim** (1:1 with
`TelosProof.lean` §22-43) so the SHAPE is shared. Reproducing the shape does
**not** prove anything about the primitives' body semantics.

**Toolchain status (verified):** Lean 4.30.0 is present at `~/.elan/bin/lean`.

```bash
~/.elan/bin/lake env lean specs/proofs/telosproof/Primitives.lean   # exit 0, no errors/warnings/sorry
```

Type-checks clean; the only stdout is the three `#eval` smoke checks
(`safePatch → true`, `mixedPatch → false`, `summaryOf safePatch → the safe summary`).
Mathlib-free. ADVISORY ONLY — not wired into any apply path.
