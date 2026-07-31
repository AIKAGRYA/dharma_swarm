import CrispOpen

namespace CrispOpen.Surface8

/-!
Surface 8 asks whether maintaining the invariant while increasing complexity is
load-bearing. The answer for the Iteration 5 parity model is negative.

A growth move that wraps the program in `succ` increases the same semantic
coordinate, violates the invariant, and is rejected. But the fixed one-node
rewrite `wrapDouble` also increases that coordinate forever while preserving
the invariant. Therefore the coupling is formal but practically costless.
-/

def doubledProgram : Nat → Expr
  | 0 => .lit 2
  | depth + 1 => .double (doubledProgram depth)

def doublingState (depth : Nat) : State := {
  kernelId := 0
  program := doubledProgram depth
  modifier := .wrapDouble
}

theorem doubledProgramPositive :
    ∀ depth, 0 < observe (doubledProgram depth)
  | 0 => by
      decide
  | depth + 1 => by
      have previous := doubledProgramPositive depth
      simp [doubledProgram, observe, denote, eval]
      omega

theorem doubledProgramInvariant :
    ∀ depth, HasType (doubledProgram depth) .safe
  | 0 => by
      decide
  | depth + 1 => by
      exact rewriteTypeSound
        (by rfl : HasRewriteType .wrapDouble .preservesSafe)
        (doubledProgramInvariant depth)

theorem doublingStateInvariant (depth : Nat) :
    Invariant (doublingState depth) := by
  exact doubledProgramInvariant depth

theorem doublingStateModifierCertified (depth : Nat) :
    ModifierCertified (doublingState depth) := by
  rfl

theorem fixedGrowthMoveProposesNext (depth : Nat) :
    ProposedBy (doublingState depth) (doublingState (depth + 1)) := by
  rfl

theorem fixedGrowthMoveAccepted (depth : Nat) :
    Accepted (doublingState depth) (doublingState (depth + 1)) := by
  apply checkerComplete
  exact ⟨
    rfl,
    doublingStateInvariant depth,
    doublingStateModifierCertified depth,
    fixedGrowthMoveProposesNext depth,
    doublingStateModifierCertified (depth + 1)
  ⟩

theorem fixedGrowthMoveIncreasesComplexity (depth : Nat) :
    complexity (doublingState (depth + 1)) >
      complexity (doublingState depth) := by
  have positive := doubledProgramPositive depth
  simp [complexity, doublingState, doubledProgram, observe, denote, eval]
  omega

/-- A superficially useful pressure witness: successor growth is unsafe. -/
def unsafeGrowthSource (depth : Nat) : State := {
  kernelId := 0
  program := doubledProgram depth
  modifier := .wrapSucc
}

def unsafeGrowthTarget (depth : Nat) : State := {
  kernelId := 0
  program := .succ (doubledProgram depth)
  modifier := .wrapDouble
}

theorem unsafeGrowthIsProposed (depth : Nat) :
    ProposedBy (unsafeGrowthSource depth) (unsafeGrowthTarget depth) := by
  rfl

theorem unsafeGrowthIncreasesComplexity (depth : Nat) :
    complexity (unsafeGrowthTarget depth) >
      complexity (unsafeGrowthSource depth) := by
  simp [complexity, unsafeGrowthTarget, unsafeGrowthSource,
    observe, denote, eval]

theorem unsafeGrowthViolatesInvariant (depth : Nat) :
    ¬ Invariant (unsafeGrowthTarget depth) := by
  have safe := doubledProgramInvariant depth
  unfold HasType at safe
  unfold Invariant HasType
  simp [unsafeGrowthTarget, observe, denote, eval] at safe ⊢
  omega

theorem unsafeGrowthRejected (depth : Nat) :
    K (unsafeGrowthSource depth) (unsafeGrowthTarget depth) = false := by
  simp [K, Admissible, ModifierCertified, M, unsafeGrowthSource,
    HasRewriteType, rewriteSafeBool]

/-- A fixed, constant-description move accepted at every depth. -/
def FixedTrivialGrowthExists : Prop :=
  ∃ rewrite : Rewrite,
    ∀ depth,
      M (doublingState depth) = rewrite ∧
      Accepted (doublingState depth) (doublingState (depth + 1)) ∧
      complexity (doublingState (depth + 1)) >
        complexity (doublingState depth)

theorem fixedTrivialGrowthExists : FixedTrivialGrowthExists := by
  refine ⟨.wrapDouble, ?_⟩
  intro depth
  exact ⟨
    rfl,
    fixedGrowthMoveAccepted depth,
    fixedGrowthMoveIncreasesComplexity depth
  ⟩

/-- Surface 8's requested load-bearing property. -/
def CouplingLoadBearing : Prop :=
  ¬ FixedTrivialGrowthExists

/-- Surface 8 lands on the Iteration 5 model. -/
theorem couplingLoadBearingFails :
    ¬ CouplingLoadBearing := by
  intro loadBearing
  exact loadBearing fixedTrivialGrowthExists

end CrispOpen.Surface8
