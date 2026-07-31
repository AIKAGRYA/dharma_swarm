import Std

namespace CrispOpen.AbstractReplay

/-!
A model-independent impossibility theorem for the directive's range-based
anti-generator condition. Any fixed Boolean transition checker admits a fixed
certificate-replay program: the program stays constant while its finite input
carries a candidate path. Consequently every state reachable by a finite chain
of accepted steps lies in that one program's range.
-/

inductive Reach
    {State : Type}
    (initial : State)
    (step : State → State → Bool) : Nat → State → Prop where
  | zero : Reach initial step 0 initial
  | succ {depth : Nat} {source target : State} :
      Reach initial step depth source →
      step source target = true →
      Reach initial step (depth + 1) target

def replay
    {State : Type}
    (initial : State)
    (step : State → State → Bool) : List State → Option State
  | [] => some initial
  | target :: rest =>
      match replay initial step rest with
      | none => none
      | some source =>
          if step source target then some target else none

theorem reachableHasReplayCertificate
    {State : Type}
    {initial : State}
    {step : State → State → Bool}
    {depth : Nat}
    {state : State}
    (reachable : Reach initial step depth state) :
    ∃ certificate,
      replay initial step certificate = some state := by
  induction reachable with
  | zero =>
      exact ⟨[], rfl⟩
  | succ previous accepted inductionHypothesis =>
      rename_i stepDepth stepSource stepTarget
      rcases inductionHypothesis with ⟨certificate, replayed⟩
      refine ⟨stepTarget :: certificate, ?_⟩
      simp [replay, replayed, accepted]

def EscapesGenerator
    {State Code : Type}
    (run : Code → List State → Option State)
    (generator : Code)
    (state : State) : Prop :=
  ∀ certificate,
    run generator certificate ≠ some state

def RangeAntiGenerator
    {State Code : Type}
    (initial : State)
    (step : State → State → Bool)
    (complexity : State → Nat)
    (run : Code → List State → Option State) : Prop :=
  ∀ generator bound,
    ∃ depth state,
      Reach initial step depth state ∧
      complexity state > bound ∧
      EscapesGenerator run generator state

theorem replayCodeKillsRangeAntiGenerator
    {State Code : Type}
    (initial : State)
    (step : State → State → Bool)
    (complexity : State → Nat)
    (run : Code → List State → Option State)
    (replayCode : Code)
    (implementsReplay :
      ∀ certificate,
        run replayCode certificate =
          replay initial step certificate) :
    ¬ RangeAntiGenerator initial step complexity run := by
  intro antiGenerator
  rcases antiGenerator replayCode 0 with
    ⟨depth, state, reachable, larger, escaped⟩
  rcases reachableHasReplayCertificate reachable with
    ⟨certificate, replayed⟩
  apply escaped certificate
  calc
    run replayCode certificate =
        replay initial step certificate :=
      implementsReplay certificate
    _ = some state := replayed

/-- A one-constructor code language makes the fixed-description claim explicit. -/
inductive ReplayCode where
  | replay
  deriving DecidableEq, Repr

def runReplayCode
    {State : Type}
    (initial : State)
    (step : State → State → Bool) :
    ReplayCode → List State → Option State
  | .replay, certificate => replay initial step certificate

def descriptionLength : ReplayCode → Nat
  | .replay => 1

theorem replayDescriptionIsBounded :
    descriptionLength .replay = 1 := by
  rfl

/--
For every fixed Boolean transition checker and every complexity measure, the
range-based anti-generator condition fails. The result is independent of the
invariant, coupling proof, and opening measure.
-/
theorem rangeAntiGeneratorImpossible
    {State : Type}
    (initial : State)
    (step : State → State → Bool)
    (complexity : State → Nat) :
    ¬ RangeAntiGenerator
      initial step complexity (runReplayCode initial step) := by
  exact replayCodeKillsRangeAntiGenerator
    initial step complexity (runReplayCode initial step) .replay
    (fun _ => rfl)

end CrispOpen.AbstractReplay
