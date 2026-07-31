import CrispOpen

namespace CrispOpen.Surface8

/-!
Surface 8 asks whether maintaining the invariant while increasing complexity is
load-bearing. The answer for the Iteration 5 parity model is negative.

A growth move that wraps a program in `succ` increases the same semantic
coordinate and violates the invariant. The fixed checker rejects installation
of that future operator. But the one-node rewrite `wrapDouble` is reachable
from the actual initial state and then increases complexity forever while
preserving the invariant. Therefore the coupling is formal but practically
costless.
-/

def doubledProgram : Nat → Expr
  | 0 => .lit 4
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
      simpa [doubledProgram, observe, denote, eval] using
        Nat.add_pos_left previous (observe (doubledProgram depth))

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

theorem initialProposesDoublingSeed :
    ProposedBy initial (doublingState 0) := by
  rfl

theorem initialToDoublingStateAccepted :
    Accepted initial (doublingState 0) := by
  apply checkerComplete
  exact ⟨
    rfl,
    initialInvariant,
    initialModifierCertified,
    initialProposesDoublingSeed,
    doublingStateModifierCertified 0
  ⟩

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

theorem doublingStateReachable :
    ∀ depth, Reach (depth + 1) (doublingState depth)
  | 0 => by
      simpa using
        Reach.succ (Reach.zero : Reach 0 initial)
          initialToDoublingStateAccepted
  | depth + 1 => by
      simpa using
        Reach.succ (doublingStateReachable depth)
          (fixedGrowthMoveAccepted depth)

theorem fixedGrowthMoveIncreasesComplexity (depth : Nat) :
    complexity (doublingState (depth + 1)) >
      complexity (doublingState depth) := by
  have positive := doubledProgramPositive depth
  simpa [complexity, doublingState, doubledProgram, observe, denote, eval] using
    Nat.lt_add_of_pos_right positive

/--
The generic successor wrapper is a complexity-increasing but unsafe rewrite.
The future state below is what that operator would produce.
-/
def unsafeFutureState (depth : Nat) : State := {
  kernelId := 0
  program := .succ (doubledProgram (depth + 1))
  modifier := .wrapDouble
}

theorem successorGrowthIncreasesComplexity (depth : Nat) :
    complexity (unsafeFutureState depth) >
      complexity (doublingState (depth + 1)) := by
  simp [complexity, unsafeFutureState, doublingState,
    observe, denote, eval]

theorem successorGrowthViolatesInvariant (depth : Nat) :
    ¬ Invariant (unsafeFutureState depth) := by
  have safe := doubledProgramInvariant (depth + 1)
  unfold HasType at safe
  unfold Invariant HasType
  simp [unsafeFutureState, observe, denote, eval] at safe ⊢
  omega

/--
Attempt to install `wrapSucc` as the next modification operator while executing
the current safe doubling move. The program proposal is exact, but the fixed
checker rejects the unsafe future operator before it can run.
-/
def unsafeModifierCandidate (depth : Nat) : State := {
  kernelId := 0
  program := doubledProgram (depth + 1)
  modifier := .wrapSucc
}

theorem unsafeModifierCandidateIsProposed (depth : Nat) :
    ProposedBy (doublingState depth) (unsafeModifierCandidate depth) := by
  rfl

theorem unsafeModifierWouldProduceUnsafeGrowth (depth : Nat) :
    applyRewrite (M (unsafeModifierCandidate depth))
        (unsafeModifierCandidate depth).program =
      (unsafeFutureState depth).program := by
  rfl

theorem unsafeModifierRejected (depth : Nat) :
    K (doublingState depth) (unsafeModifierCandidate depth) = false := by
  simp [K, Admissible, ModifierCertified, M, unsafeModifierCandidate,
    HasRewriteType, rewriteSafeBool]

/-- A fixed, constant-description move accepted at every reachable depth. -/
def FixedTrivialGrowthExists : Prop :=
  ∃ rewrite : Rewrite,
    ∀ depth,
      Reach (depth + 1) (doublingState depth) ∧
      M (doublingState depth) = rewrite ∧
      Accepted (doublingState depth) (doublingState (depth + 1)) ∧
      complexity (doublingState (depth + 1)) >
        complexity (doublingState depth)

theorem fixedTrivialGrowthExists : FixedTrivialGrowthExists := by
  refine ⟨.wrapDouble, ?_⟩
  intro depth
  exact ⟨
    doublingStateReachable depth,
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
