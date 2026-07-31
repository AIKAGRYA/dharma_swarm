import Std

namespace CrispOpen

/-!
A small proof-carrying self-modification model.

The mutable object is a finite Boolean truth table over natural-number inputs.
Inputs beyond the stored table evaluate to false.  The checker and invariant
are Lean definitions outside the mutable state.  Every admitted rewrite grows
the table by one cell, keeps the checker identity, and carries evidence that
the distinguished input zero remains false.
-/

abbrev Program := List Bool

/-- Observable semantics of a finite truth table. -/
def eval : Program → Nat → Bool
  | [], _ => false
  | bit :: _, 0 => bit
  | _ :: rest, index + 1 => eval rest index

/-- Semantic safety policy: distinguished input zero must remain false. -/
def Invariant (program : Program) : Prop := eval program 0 = false

/-- Number of observable inputs on which the program returns true. -/
def support : Program → Nat
  | [] => 0
  | bit :: rest => (if bit then 1 else 0) + support rest

structure State where
  kernelId : Nat
  program : Program
  deriving DecidableEq, Repr

/-- Initial system: fixed checker identity zero and one protected output. -/
def initial : State := {
  kernelId := 0
  program := [false]
}

/-- The proposition certified by every accepted rewrite. -/
def Admissible (source target : State) : Prop :=
  target.kernelId = source.kernelId ∧
  target.program.length = source.program.length + 1 ∧
  Invariant target.program

instance (source target : State) : Decidable (Admissible source target) :=
  inferInstance

/-- Immutable executable checker.  It is not stored inside `State`. -/
def K (source target : State) : Bool := decide (Admissible source target)

/-- A term of `M source target` is the proof carried by one modification. -/
def M (source target : State) : Prop := K source target = true

theorem checkerSound {source target : State} (accepted : M source target) :
    Admissible source target := by
  apply of_decide_eq_true
  simpa [M, K] using accepted

theorem checkerComplete {source target : State}
    (certificate : Admissible source target) : M source target := by
  simp [M, K, certificate]

/-- Exact-depth reachability; the index is unbounded. -/
inductive Reach : Nat → State → Prop where
  | zero : Reach 0 initial
  | succ {depth : Nat} {source target : State} :
      Reach depth source → M source target → Reach (depth + 1) target

/-- Limb (A): every state reachable at any natural depth satisfies `Invariant`. -/
theorem closure {depth : Nat} {state : State} (reachable : Reach depth state) :
    Invariant state.program := by
  induction reachable with
  | zero => rfl
  | succ previous accepted inductionHypothesis =>
      exact (checkerSound accepted).2.2

/-- No reachable rewrite changes the immutable checker identity. -/
theorem kernelFixed {depth : Nat} {state : State} (reachable : Reach depth state) :
    state.kernelId = initial.kernelId := by
  induction reachable with
  | zero => rfl
  | succ previous accepted inductionHypothesis =>
      calc
        _ = _ := (checkerSound accepted).1
        _ = initial.kernelId := inductionHypothesis

/-- Concrete unsafe target with the right growth but a forbidden output. -/
def unsafeState : State := {
  kernelId := 0
  program := [true, true]
}

theorem unsafeViolatesInvariant : ¬ Invariant unsafeState.program := by
  simp [Invariant, unsafeState, eval]

theorem unsafeRejected : K initial unsafeState = false := by
  simp [K, Admissible, initial, unsafeState, Invariant, eval]

/-- Concrete accepted target: the gate does not reject everything. -/
def acceptedState : State := {
  kernelId := 0
  program := [false, true]
}

theorem nontrivialAccepted : M initial acceptedState := by
  simp [M, K, Admissible, initial, acceptedState, Invariant, eval]

/-- A later rewrite may alter old mutable outputs, not merely append bytes. -/
def rewrittenState : State := {
  kernelId := 0
  program := [false, false, true]
}

theorem rewriteExistingCellAccepted : M acceptedState rewrittenState := by
  simp [M, K, Admissible, acceptedState, rewrittenState, Invariant, eval]

theorem rewriteChangesObservableBehavior :
    eval acceptedState.program 1 ≠ eval rewrittenState.program 1 := by
  simp [acceptedState, rewrittenState, eval]

/-- A private generator for the canonical opening lineage. -/
def ones : Nat → List Bool
  | 0 => []
  | depth + 1 => true :: ones depth

theorem onesLength (depth : Nat) : (ones depth).length = depth := by
  induction depth with
  | zero => rfl
  | succ depth inductionHypothesis =>
      simp [ones, inductionHypothesis]

theorem supportOnes (depth : Nat) : support (ones depth) = depth := by
  induction depth with
  | zero => rfl
  | succ depth inductionHypothesis =>
      simp [ones, support, inductionHypothesis]

def openProgram (depth : Nat) : Program := false :: ones depth

def lineage (depth : Nat) : State := {
  kernelId := 0
  program := openProgram depth
}

theorem openProgramLength (depth : Nat) :
    (openProgram depth).length = depth + 1 := by
  simp [openProgram, onesLength]

theorem openProgramSupport (depth : Nat) : support (openProgram depth) = depth := by
  simp [openProgram, support, supportOnes]

theorem lineageAdmissible (depth : Nat) :
    Admissible (lineage depth) (lineage (depth + 1)) := by
  constructor
  · rfl
  constructor
  · simp [lineage, openProgramLength]
  · rfl

theorem lineageStep (depth : Nat) : M (lineage depth) (lineage (depth + 1)) :=
  checkerComplete (lineageAdmissible depth)

theorem lineageReachable (depth : Nat) : Reach depth (lineage depth) := by
  induction depth with
  | zero =>
      simpa [lineage, initial, openProgram, ones] using (Reach.zero : Reach 0 initial)
  | succ depth inductionHypothesis =>
      simpa [Nat.succ_eq_add_one] using
        (Reach.succ inductionHypothesis (lineageStep depth))

/-- Extensional opening measure for this truth-table language. -/
def complexity (state : State) : Nat := support state.program

theorem lineageComplexity (depth : Nat) : complexity (lineage depth) = depth := by
  simp [complexity, lineage, openProgramSupport]

/-- Appending an observationally false cell cannot inflate the measure. -/
theorem falsePaddingNoProgress (program : Program) :
    support (program ++ [false]) = support program := by
  induction program with
  | nil => rfl
  | cons bit rest inductionHypothesis =>
      simp [support, inductionHypothesis]

/-- Strong opening witness: every natural complexity occurs at the same depth. -/
theorem exactOpening (depth : Nat) :
    ∃ state, Reach depth state ∧ complexity state = depth := by
  exact ⟨lineage depth, lineageReachable depth, lineageComplexity depth⟩

/-- Limb (B): reachable semantic support is unbounded. -/
theorem opening (bound : Nat) :
    ∃ depth state, Reach depth state ∧ complexity state > bound := by
  refine ⟨bound + 1, lineage (bound + 1), lineageReachable (bound + 1), ?_⟩
  simp [lineageComplexity]

/-- The exact joint target proved by this development. -/
theorem targetTheorem :
    (∀ depth state, Reach depth state → Invariant state.program) ∧
    (∀ bound, ∃ depth state, Reach depth state ∧ complexity state > bound) := by
  constructor
  · intro depth state reachable
    exact closure reachable
  · intro bound
    exact opening bound

end CrispOpen
