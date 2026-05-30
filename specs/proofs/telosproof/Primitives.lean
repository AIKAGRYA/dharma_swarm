/-
  Primitives — v1 deny-by-default safe-primitive vocabulary
  (Lean STRUCTURAL / TYPE-LEVEL SCAFFOLD — NOT a safety proof).

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ HONESTY NOTICE (read first).                                             │
  │                                                                          │
  │ This file is a STRUCTURAL SCAFFOLD and a cross-language vocabulary seam. │
  │ It is NOT — and does not claim to be — a proof that the safe primitives  │
  │ preserve the 8 protected-body invariants. An earlier version asserted a  │
  │ theorem (`composed_safe_preserves_boundary`) that LOOKED like such a     │
  │ proof but was VACUOUS: `summaryOf` was DEFINED to return `safeChange`    │
  │ exactly when the patch is composed of safe primitives, so the "theorem"  │
  │ discharged by `rw [if_pos h]; rfl` proved only that the definition       │
  │ matches itself — a tautology with NO body-level semantic content. It     │
  │ proved nothing about what `add_pure_function` et al. actually DO.        │
  │                                                                          │
  │ The REAL safety proof (attach a body-level semantics function to each    │
  │ `SafePrimitive` and prove it cannot flip any of the 8 flags) is FUTURE   │
  │ v1 WORK and is deliberately NOT claimed here. The operational safety     │
  │ proof currently lives in the Python AST-level classifier                 │
  │ (`dharma_swarm/telosproof/allowlist.py`) and its adversarial test suite  │
  │ (`tests/test_telosproof_allowlist.py`, incl. the FN1–FN4 regressions).   │
  │ What THIS file contributes is type-level WELL-FORMEDNESS only.           │
  └─────────────────────────────────────────────────────────────────────────┘

  v0 (TelosProof.lean) enumerates DANGER: a patch is safe iff every protected flag
  is `false`. The v1 adversarial-review insight is that enumerating danger is
  rename/synonym-bypassable. v1 INVERTS to a closed ALLOW-LIST: a fixed set of
  candidate safe primitive change-operations. Any operation that is NOT one of
  these primitives is `unknown` (the deny-by-default bottom) and must route to
  REVIEW — it is NEVER admitted as safe.

  This file is the Lean SOURCE OF TRUTH for the safe-primitive VOCABULARY (the
  names), not for its safety. The constructor names of `SafePrimitive` are
  byte-identical (snake_case) to:
    - allowlist.SAFE_PRIMITIVES (Python, dharma_swarm/telosproof/allowlist.py)
    - the JSON Schema $defs.SafePrimitive.enum (change_summary.schema.json)
  That byte-identity is the cross-language verification seam, and is the ONLY
  property the parity test (tests/test_telosproof_schema_parity.py) relies on.

  ADVISORY ONLY. No mathlib import.

  Why this file MIRRORS the v0 boundary shape rather than `import`-ing
  TelosProof.lean: under the pinned toolchain (Lean 4.30.0) v0's
  `safeProof := by decide` does not synthesize a `Decidable` instance for its
  `And`-of-`Bool`-equality `Prop`, so `TelosProof.lean` does not currently
  produce an `.olean` to import from — and we are forbidden from editing v0. We
  therefore reproduce v0's `ChangeSummary` shape and `preservesTelosBoundary`
  predicate VERBATIM (fields, safe values, and the conjunction are 1:1 with
  TelosProof.lean lines 22-43) so the SHAPE is shared; we do NOT thereby prove
  anything about the primitives' body semantics.
-/

namespace Primitives

/-- 1:1 mirror of `TelosProof.ChangeSummary` (TelosProof.lean §22-31): an abstract
    body-level summary of what a patch does to the 8 protected invariants. `true`
    means "the patch did the unsafe thing". -/
structure ChangeSummary where
  touchesProtectedFile    : Bool  -- (1) touches a dgm_loop.DGM_PROTECTED_FILES member
  disablesReceiptEmission : Bool  -- (2) disables receipt emission
  disablesRollback        : Bool  -- (3) disables rollback
  bypassesHumanApproval   : Bool  -- (4) bypasses human approval
  raisesAutonomyLevel     : Bool  -- (5) raises autonomy level
  disablesShadowMode      : Bool  -- (6) disables shadow mode
  createsNewPersistence   : Bool  -- (7) creates new persistence substrate
  preservesReplayRollback : Bool  -- (8) preserves replay/rollback metadata (must be TRUE)
  deriving Repr, DecidableEq

/-- 1:1 mirror of `TelosProof.preservesTelosBoundary` (TelosProof.lean §35-43):
    the patch preserves the telos boundary iff every protected flag is `false` and
    replay/rollback metadata is preserved (`true`). THIS IS THE v0 BOUNDARY. -/
def preservesTelosBoundary (c : ChangeSummary) : Prop :=
  c.touchesProtectedFile = false ∧
  c.disablesReceiptEmission = false ∧
  c.disablesRollback = false ∧
  c.bypassesHumanApproval = false ∧
  c.raisesAutonomyLevel = false ∧
  c.disablesShadowMode = false ∧
  c.createsNewPersistence = false ∧
  c.preservesReplayRollback = true

/-- 1:1 mirror of `TelosProof.safeChange` (TelosProof.lean §52-56): benign refactor —
    all protected flags false, replay preserved. -/
def safeChange : ChangeSummary :=
  { touchesProtectedFile := false, disablesReceiptEmission := false,
    disablesRollback := false, bypassesHumanApproval := false,
    raisesAutonomyLevel := false, disablesShadowMode := false,
    createsNewPersistence := false, preservesReplayRollback := true }

/-- The closed allow-list of provably-non-violating change-operation classes. Names
    are byte-identical to allowlist.SAFE_PRIMITIVES (Python) and the JSON Schema enum.
    Mapping (snake_case Python/JSON ↔ camelCase Lean):
      addPureFunction          ↔ "add_pure_function"
      editCommentOrDocstring   ↔ "edit_comment_or_docstring"
      addTest                  ↔ "add_test"
      editNonSafetyFileBody    ↔ "edit_non_safety_file_body"
      addNonPersistenceFile    ↔ "add_non_persistence_file" -/
inductive SafePrimitive where
  | addPureFunction
  | editCommentOrDocstring
  | addTest
  | editNonSafetyFileBody
  | addNonPersistenceFile
  deriving DecidableEq, Repr

/-- A single patch operation: either a known-safe primitive, or `unknown`
    (deny-by-default bottom — an op we could NOT positively classify as safe). -/
inductive Op where
  | safe (p : SafePrimitive)
  | unknown
  deriving DecidableEq, Repr

/-- A patch is a list of operations (mirrors ClassificationResult: allowed ++ unknown). -/
abbrev Patch := List Op

/-- A single op is safe iff it is a known-safe primitive; `unknown` is never safe. -/
def opIsSafe : Op → Bool
  | Op.safe _   => true
  | Op.unknown  => false

/-- The deny-by-default predicate: a patch is composed of safe primitives iff EVERY
    operation in it is a known-safe primitive. A single `unknown` op falsifies it. -/
def composedOfSafePrimitives (p : Patch) : Prop :=
  p.all opIsSafe = true

instance (p : Patch) : Decidable (composedOfSafePrimitives p) := by
  unfold composedOfSafePrimitives; infer_instance

/-- A *definitional* projection from the structural classification to a v0-shaped
    summary. ⚠️ This is a MODELLING CHOICE, not a derived fact: `summaryOf` is
    DEFINED to return `safeChange` exactly when the patch is composed of safe
    primitives, and the maximally-unsafe summary otherwise. It therefore carries
    NO body-level semantics — it does not look at what `addPureFunction` et al.
    actually do; it only branches on the structural `composedOfSafePrimitives`
    flag. The intended (but here UNPROVEN) reading is that each safe primitive is
    a sufficient condition for non-violation of the 8 invariants:
      addPureFunction        — pure addition, no removal, no protected surface.
      editCommentOrDocstring — zero substantive lines changed.
      addTest                — new test under tests/, no persistence, no removal.
      editNonSafetyFileBody  — non-safety file, no danger op, ZERO removal.
      addNonPersistenceFile  — new non-store source/text under a non-safety path.
    Establishing that reading is FUTURE v1 WORK: it requires attaching a real
    body-semantics function to each `SafePrimitive` and proving each preserves all
    8 flags. Until then, the operational guarantee is enforced by the Python
    AST-level classifier + adversarial tests, NOT by this projection. -/
def summaryOf (p : Patch) : ChangeSummary :=
  if composedOfSafePrimitives p then safeChange
  else
    { touchesProtectedFile := true, disablesReceiptEmission := true,
      disablesRollback := true, bypassesHumanApproval := true,
      raisesAutonomyLevel := true, disablesShadowMode := true,
      createsNewPersistence := true, preservesReplayRollback := false }

/-- STRUCTURAL WELL-FORMEDNESS ONLY — ⚠️ NOT a safety proof.

    This lemma states that the `summaryOf` projection is internally consistent:
    when a patch is structurally all-safe, its `summaryOf` image is `safeChange`,
    which (being all-`false`/replay-`true` by definition) satisfies the v0
    `preservesTelosBoundary` predicate-shape. The proof is `rw [if_pos h]; rfl`
    — i.e. it follows IMMEDIATELY from the definition of `summaryOf`. That makes
    it a TAUTOLOGY about the definition, with NO independent body-level content:
    it does NOT prove that the safe primitives cannot flip a protected flag. The
    real safety theorem (`safe primitive body semantics ⇒ no flag flips`) is
    deliberately NOT claimed here and is future v1 work (see HONESTY NOTICE at
    the top of this file). The name says `well_formed`, not `safe`, precisely so
    no caller mistakes this for a discharged safety obligation. -/
theorem summaryOf_well_formed_on_safe
    (p : Patch) (h : composedOfSafePrimitives p) :
    preservesTelosBoundary (summaryOf p) := by
  -- Holds by definitional unfolding of `summaryOf` on the `if_pos` branch.
  -- This is structural well-formedness of the projection, NOT a safety result.
  unfold summaryOf
  rw [if_pos h]
  refine ⟨rfl, rfl, rfl, rfl, rfl, rfl, rfl, rfl⟩

/-- Composition closure (a GENUINE structural fact, not vacuous): the predicate
    `composedOfSafePrimitives` is closed under list append — concatenating two
    all-safe patches yields an all-safe patch. This is real content about the
    `List.all` structure (proved via `List.all_append`), independent of any
    `summaryOf` definitional branching. It says the STRUCTURAL classification
    composes; it does NOT claim body-level safety. -/
theorem composed_safe_closed_under_append
    (p q : Patch)
    (hp : composedOfSafePrimitives p) (hq : composedOfSafePrimitives q) :
    composedOfSafePrimitives (p ++ q) := by
  unfold composedOfSafePrimitives at *
  simp [List.all_append, hp, hq]

/-- Deny-by-default soundness (the inverse direction): a patch containing ANY unknown
    op is NOT composed of safe primitives — unknown forces failure, never silently
    passes. This is what makes ALLOW a positive proof, not an absence-of-red-flag. -/
theorem unknown_breaks_composition
    (p : Patch) (h : Op.unknown ∈ p) :
    composedOfSafePrimitives p = False := by
  have hfalse : p.all opIsSafe = false := by
    induction p with
    | nil => cases h
    | cons a t ih =>
      simp only [List.all_cons, Bool.and_eq_false_iff]
      cases h with
      | head => exact Or.inl (by rfl)
      | tail _ hmem => exact Or.inr (ih hmem)
  unfold composedOfSafePrimitives
  simp [hfalse]

-- Smoke checks: an all-safe patch evaluates true; a mixed patch (with .unknown) false.
def safePatch : Patch :=
  [Op.safe SafePrimitive.addPureFunction,
   Op.safe SafePrimitive.editCommentOrDocstring,
   Op.safe SafePrimitive.addTest]

def mixedPatch : Patch :=
  [Op.safe SafePrimitive.addPureFunction, Op.unknown]

example : composedOfSafePrimitives safePatch := by decide
example : ¬ composedOfSafePrimitives mixedPatch := by decide

#eval (safePatch.all opIsSafe)   -- true
#eval (mixedPatch.all opIsSafe)  -- false
#eval (summaryOf safePatch)      -- the safe summary (== mirror of TelosProof.safeChange)

end Primitives
