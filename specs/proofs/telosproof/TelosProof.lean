/-
  TelosProof — v1 expressiveness sample (NOT v0 runtime, NOT wired into apply path).

  Models the 8 protected-body invariants a self-modification patch must satisfy
  before it may enter an apply path (dgm_loop.py / diff_applier.py). The proof is
  about the BODY of a change (what the diff does), never about mind/intent.

  Python interface this mirrors (do NOT redefine those in Python — import them):
    - dharma_swarm/models.py  : ProofObligation, GateCheckResult.proof_obligation
    - dharma_swarm/dgm_loop.py: DGM_PROTECTED_FILES, _is_protected_dgm_target,
                                DHARMA_EVOLUTION_SHADOW (env, default "1")
    - dharma_swarm/diff_applier.py: apply(), apply_and_test()

  ADVISORY ONLY. Enforcement is gated by env DHARMA_PROOF_ENFORCE (default OFF),
  mirroring DHARMA_EVOLUTION_SHADOW. No mathlib import.
-/

namespace TelosProof

/-- Abstract summary of what a patch's body does to the 8 protected invariants.
    `true` means "the patch did the unsafe thing"; safety wants protected flags `false`. -/
structure ChangeSummary where
  touchesProtectedFile   : Bool  -- (1) touches a dgm_loop.DGM_PROTECTED_FILES member
  disablesReceiptEmission : Bool  -- (2) disables receipt emission
  disablesRollback       : Bool  -- (3) disables rollback
  bypassesHumanApproval  : Bool  -- (4) bypasses human approval
  raisesAutonomyLevel    : Bool  -- (5) raises autonomy level
  disablesShadowMode     : Bool  -- (6) disables shadow mode
  createsNewPersistence  : Bool  -- (7) creates new persistence substrate
  preservesReplayRollback : Bool  -- (8) preserves replay/rollback metadata (must be TRUE)
  deriving Repr

/-- The patch preserves the telos boundary iff every protected flag is `false`,
    AND replay/rollback metadata is preserved (`true`). -/
def preservesTelosBoundary (c : ChangeSummary) : Prop :=
  c.touchesProtectedFile = false ∧
  c.disablesReceiptEmission = false ∧
  c.disablesRollback = false ∧
  c.bypassesHumanApproval = false ∧
  c.raisesAutonomyLevel = false ∧
  c.disablesShadowMode = false ∧
  c.createsNewPersistence = false ∧
  c.preservesReplayRollback = true

/-- A proof-carrying-telos certificate: a change together with a proof its body
    preserves the boundary. Maps to models.ProofObligation (advisory). -/
structure TelosProof where
  change : ChangeSummary
  proof  : preservesTelosBoundary change

/-- SAFE sample: a benign refactor patch. All protected flags false; replay preserved. -/
def safeChange : ChangeSummary :=
  { touchesProtectedFile := false, disablesReceiptEmission := false,
    disablesRollback := false, bypassesHumanApproval := false,
    raisesAutonomyLevel := false, disablesShadowMode := false,
    createsNewPersistence := false, preservesReplayRollback := true }

/-- The certificate type-checks: `decide` discharges the conjunction of Bool equalities. -/
def safeProof : TelosProof :=
  { change := safeChange, proof := by decide }

/-- UNSAFE sample: this patch disables rollback and shadow mode. `TelosProof` for it
    is UNCONSTRUCTIBLE — uncomment the body below and the file FAILS to compile,
    which is exactly the advisory guard the Python gate function will surface. -/
def unsafeChange : ChangeSummary :=
  { touchesProtectedFile := false, disablesReceiptEmission := false,
    disablesRollback := true,  bypassesHumanApproval := false,
    raisesAutonomyLevel := false, disablesShadowMode := true,
    createsNewPersistence := false, preservesReplayRollback := true }

-- def unsafeProof : TelosProof :=
--   { change := unsafeChange, proof := by decide }  -- FAILS: `decide` proves False

#eval safeProof.change   -- prints the safe summary
#check @TelosProof       -- the certificate type exists

end TelosProof
