import Std

namespace CrispOpen

/-!
Iteration 1 is deliberately weak.  The invariant is vacuous and the opening
measure is representation length.  It exists so the adversarial pass can kill
a concrete compiling construction rather than merely criticize a proposal.
-/

abbrev Program := List Bool

/-- Deliberately vacuous candidate invariant for iteration 1. -/
def Invariant (_ : Program) : Prop := True

structure State where
  kernelId : Nat
  program : Program
  deriving DecidableEq, Repr

/-- The immutable checker identity is modeled as zero. -/
def initial : State := {
  kernelId := 0
  program := []
}

/-- A candidate transition keeps the checker identity and adds one cell. -/
def Admissible (source target : State) : Prop :=
  target.kernelId = source.kernelId ∧
  target.program.length = source.program.length + 1 ∧
  Invariant target.program

instance (source target : State) : Decidable (Admissible source target) :=
  inferInstance

/-- Executable fixed checker. -/
def K (source target : State) : Bool := decide (Admissible source target)

/-- A modification is admitted exactly when the fixed checker returns true. -/
def M (source target : State) : Prop := K source target = true

theorem checker_sound {source target : State} (accepted : M source target) :
    Admissible source target := by
  exact of_decide_eq_true accepted

inductive Reach : Nat → State → Prop where
  | zero : Reach 0 initial
  | succ {depth source target : State} :
      Reach depth source → M source target → Reach (depth + 1) target

/-- Limb (A), but only for the deliberately vacuous iteration-1 invariant. -/
theorem closure {depth : Nat} {state : State} (reachable : Reach depth state) :
    Invariant state.program := by
  induction reachable with
  | zero => trivial
  | succ previous accepted inductionHypothesis =>
      exact (checker_sound accepted).2.2

/-- Deliberately gameable iteration-1 complexity measure. -/
def complexity (state : State) : Nat := state.program.length

def lineage (depth : Nat) : State := {
  kernelId := 0
  program := List.replicate depth false
}

theorem lineageStep (depth : Nat) : M (lineage depth) (lineage (depth + 1)) := by
  simp [M, K, Admissible, lineage, Invariant]

theorem lineageReachable (depth : Nat) : Reach depth (lineage depth) := by
  induction depth with
  | zero =>
      simpa [lineage, initial] using (Reach.zero : Reach 0 initial)
  | succ depth inductionHypothesis =>
      simpa [Nat.succ_eq_add_one] using
        (Reach.succ inductionHypothesis (lineageStep depth))

theorem lineageComplexity (depth : Nat) : complexity (lineage depth) = depth := by
  simp [complexity, lineage]

/-- Limb (B) for raw representation length only. -/
theorem opening (bound : Nat) :
    ∃ depth state, Reach depth state ∧ complexity state > bound := by
  refine ⟨bound + 1, lineage (bound + 1), lineageReachable (bound + 1), ?_⟩
  simp [lineageComplexity]

end CrispOpen
