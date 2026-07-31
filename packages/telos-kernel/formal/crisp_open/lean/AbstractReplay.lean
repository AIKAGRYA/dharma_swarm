import Std
import Init.Data.Nat.Log2

namespace CrispOpen.AbstractReplay

/-!
Iteration 6 keeps the range-based replay result, but demotes it to what it
actually proves: one naive anti-generator definition is impossible for every
effectively checkable finite-path transition system.

The main result is now an object-language-relative description-length ceiling.
A closed deterministic lineage can be described by a shortest seed program, a
fixed step program, and a self-delimiting description of the depth.  Opening the
system adds exactly one new term: the description length of the consumed input.
-/

-- Finite accepted paths and the withdrawn range condition --------------------

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

inductive ReplayCode where
  | replay
  deriving DecidableEq, Repr

def runReplayCode
    {State : Type}
    (initial : State)
    (step : State → State → Bool) :
    ReplayCode → List State → Option State
  | .replay, certificate => replay initial step certificate

def replayDescriptionLength : ReplayCode → Nat
  | .replay => 1

theorem replayDescriptionIsBounded :
    replayDescriptionLength .replay = 1 := by
  rfl

theorem replayCodeCoversReachable
    {State : Type}
    (initial : State)
    (step : State → State → Bool)
    {depth : Nat}
    {state : State}
    (reachable : Reach initial step depth state) :
    ∃ certificate,
      runReplayCode initial step .replay certificate = some state := by
  simpa [runReplayCode] using reachableHasReplayCertificate reachable

/--
Corollary retained from Iteration 5: the withdrawn range-based anti-generator
condition fails for every fixed Boolean transition checker and every measure.
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

-- Minimal description length over an explicit object language ----------------

structure DescriptionLanguage (Output : Type) where
  Code : Type
  run : Code → Output
  codeLength : Code → Nat
  quote : Output → Code
  quoteSound : ∀ output, run (quote output) = output

def DescribedAtLength
    {Output : Type}
    (language : DescriptionLanguage Output)
    (output : Output)
    (size : Nat) : Prop :=
  ∃ code : language.Code,
    language.run code = output ∧
    language.codeLength code = size

theorem descriptionExists
    {Output : Type}
    (language : DescriptionLanguage Output)
    (output : Output) :
    ∃ size, DescribedAtLength language output size := by
  refine ⟨language.codeLength (language.quote output), ?_⟩
  exact ⟨language.quote output, language.quoteSound output, rfl⟩

/-- Minimal description length relative to the declared object language. -/
noncomputable def mdl
    {Output : Type}
    (language : DescriptionLanguage Output)
    (output : Output) : Nat := by
  classical
  exact Nat.find (descriptionExists language output)

theorem mdlSpec
    {Output : Type}
    (language : DescriptionLanguage Output)
    (output : Output) :
    DescribedAtLength language output (mdl language output) := by
  classical
  exact Nat.find_spec (descriptionExists language output)

theorem mdlLeOfCode
    {Output : Type}
    (language : DescriptionLanguage Output)
    {code : language.Code}
    {output : Output}
    (runs : language.run code = output) :
    mdl language output ≤ language.codeLength code := by
  classical
  exact Nat.find_min' (descriptionExists language output) ⟨code, runs, rfl⟩

/-- Number of bits in the ordinary binary representation, with zero costing one. -/
def bitLength (value : Nat) : Nat :=
  Nat.log2 (value + 1) + 1

/--
An explicit self-delimiting natural-number code.  Its shape is
`log n + 2 log log n + O(1)`; the shifts make the expression total at zero.
-/
def natCodeLength (value : Nat) : Nat :=
  bitLength value + 2 * bitLength (bitLength value) + 1

theorem natCodeLengthShape (value : Nat) :
    natCodeLength value =
      bitLength value + 2 * bitLength (bitLength value) + 1 := by
  rfl

def iterate
    {State : Type}
    (step : State → State) : Nat → State → State
  | 0, state => state
  | depth + 1, state => step (iterate step depth state)

def ClosedReach
    {State : Type}
    (seed : State)
    (step : State → State)
    (depth : Nat)
    (state : State) : Prop :=
  iterate step depth seed = state

inductive ClosedProgram (State StepCode : Type) where
  | quote : State → ClosedProgram State StepCode
  | iterate :
      StepCode →
      ClosedProgram State StepCode →
      Nat →
      ClosedProgram State StepCode

def runClosed
    {State StepCode : Type}
    (decodeStep : StepCode → State → State) :
    ClosedProgram State StepCode → State
  | .quote state => state
  | .iterate stepCode seedProgram depth =>
      iterate (decodeStep stepCode) depth (runClosed decodeStep seedProgram)

def closedProgramLength
    {State StepCode : Type}
    (quoteLength : State → Nat)
    (stepLength : StepCode → Nat) :
    ClosedProgram State StepCode → Nat
  | .quote state => quoteLength state
  | .iterate stepCode seedProgram depth =>
      closedProgramLength quoteLength stepLength seedProgram +
        stepLength stepCode +
        natCodeLength depth +
        1

def closedLanguage
    {State StepCode : Type}
    (decodeStep : StepCode → State → State)
    (quoteLength : State → Nat)
    (stepLength : StepCode → Nat) :
    DescriptionLanguage State where
  Code := ClosedProgram State StepCode
  run := runClosed decodeStep
  codeLength := closedProgramLength quoteLength stepLength
  quote := .quote
  quoteSound := fun _ => rfl

/--
The logarithmic ceiling for a closed deterministic lineage:

`K(state) ≤ K(seed) + K(step) + K(depth) + 1`.

Here each `K` is the minimal description length or declared code length in the
same explicit object language, and `K(depth)` is `natCodeLength depth`.
-/
theorem closedLogarithmicCeiling
    {State StepCode : Type}
    (decodeStep : StepCode → State → State)
    (quoteLength : State → Nat)
    (stepLength : StepCode → Nat)
    (seed : State)
    (stepCode : StepCode)
    {depth : Nat}
    {state : State}
    (reachable :
      ClosedReach seed (decodeStep stepCode) depth state) :
    mdl (closedLanguage decodeStep quoteLength stepLength) state ≤
      mdl (closedLanguage decodeStep quoteLength stepLength) seed +
        stepLength stepCode +
        natCodeLength depth +
        1 := by
  classical
  rcases mdlSpec
      (closedLanguage decodeStep quoteLength stepLength) seed with
    ⟨seedProgram, seedRuns, seedLength⟩
  have generated :
      runClosed decodeStep
          (.iterate stepCode seedProgram depth) = state := by
    change iterate (decodeStep stepCode) depth
      (runClosed decodeStep seedProgram) = state
    rw [seedRuns]
    exact reachable
  have upper :=
    mdlLeOfCode
      (closedLanguage decodeStep quoteLength stepLength) generated
  change
    mdl (closedLanguage decodeStep quoteLength stepLength) state ≤
      closedProgramLength quoteLength stepLength seedProgram +
        stepLength stepCode +
        natCodeLength depth +
        1 at upper
  change
    closedProgramLength quoteLength stepLength seedProgram =
      mdl (closedLanguage decodeStep quoteLength stepLength) seed at seedLength
  rw [seedLength] at upper
  exact upper

def ClosedCeilingExceeded
    {State StepCode : Type}
    (decodeStep : StepCode → State → State)
    (quoteLength : State → Nat)
    (stepLength : StepCode → Nat)
    (seed : State)
    (stepCode : StepCode)
    (depth : Nat)
    (state : State) : Prop :=
  mdl (closedLanguage decodeStep quoteLength stepLength) state >
    mdl (closedLanguage decodeStep quoteLength stepLength) seed +
      stepLength stepCode +
      natCodeLength depth +
      1

theorem closedCannotExceedDescriptionCeiling
    {State StepCode : Type}
    (decodeStep : StepCode → State → State)
    (quoteLength : State → Nat)
    (stepLength : StepCode → Nat)
    (seed : State)
    (stepCode : StepCode)
    {depth : Nat}
    {state : State}
    (reachable :
      ClosedReach seed (decodeStep stepCode) depth state) :
    ¬ ClosedCeilingExceeded
      decodeStep quoteLength stepLength seed stepCode depth state := by
  exact Nat.not_lt_of_ge
    (closedLogarithmicCeiling
      decodeStep quoteLength stepLength seed stepCode reachable)

-- A pure counter receives the same upper bound -------------------------------

def counterStep (state : Nat) : Nat :=
  state + 1

theorem iterateCounter (depth seed : Nat) :
    iterate counterStep depth seed = seed + depth := by
  induction depth with
  | zero =>
      simp [iterate]
  | succ depth inductionHypothesis =>
      simp [iterate, counterStep, inductionHypothesis, Nat.add_assoc]

theorem iterateCounterFromZero (depth : Nat) :
    iterate counterStep depth 0 = depth := by
  simpa using iterateCounter depth 0

inductive CounterStepCode where
  | increment

def decodeCounter : CounterStepCode → Nat → Nat
  | .increment => counterStep

def counterStepLength : CounterStepCode → Nat
  | .increment => 1

def counterQuoteLength (state : Nat) : Nat :=
  natCodeLength state + 1

/--
The closed ceiling does not distinguish a novelty-producing process from a
counter: the depth itself is a complete description of the counter state.
-/
theorem pureCounterHasClosedCeiling (depth : Nat) :
    mdl
        (closedLanguage
          decodeCounter counterQuoteLength counterStepLength)
        depth ≤
      mdl
          (closedLanguage
            decodeCounter counterQuoteLength counterStepLength)
          0 +
        counterStepLength .increment +
        natCodeLength depth +
        1 := by
  exact closedLogarithmicCeiling
    decodeCounter counterQuoteLength counterStepLength
    0 .increment
    (by
      simpa [ClosedReach, decodeCounter] using
        iterateCounterFromZero depth)

-- Exit 1: open systems and explicit information accounting -------------------

def consumeInputs
    {State Input : Type}
    (step : State → Input → State) :
    List Input → State → State
  | [], state => state
  | input :: rest, state =>
      consumeInputs step rest (step state input)

def OpenReach
    {State Input : Type}
    (seed : State)
    (step : State → Input → State)
    (inputs : List Input)
    (state : State) : Prop :=
  consumeInputs step inputs seed = state

def inputInformation
    {Input : Type}
    (inputLength : Input → Nat) : List Input → Nat
  | [] => 0
  | input :: rest =>
      inputLength input + inputInformation inputLength rest

inductive OpenProgram (State StepCode Input : Type) where
  | quote : State → OpenProgram State StepCode Input
  | consume :
      StepCode →
      OpenProgram State StepCode Input →
      List Input →
      OpenProgram State StepCode Input

def runOpen
    {State StepCode Input : Type}
    (decodeStep : StepCode → State → Input → State) :
    OpenProgram State StepCode Input → State
  | .quote state => state
  | .consume stepCode seedProgram inputs =>
      consumeInputs (decodeStep stepCode) inputs
        (runOpen decodeStep seedProgram)

def openProgramLength
    {State StepCode Input : Type}
    (quoteLength : State → Nat)
    (stepLength : StepCode → Nat)
    (inputLength : Input → Nat) :
    OpenProgram State StepCode Input → Nat
  | .quote state => quoteLength state
  | .consume stepCode seedProgram inputs =>
      openProgramLength quoteLength stepLength inputLength seedProgram +
        stepLength stepCode +
        inputInformation inputLength inputs +
        1

def openLanguage
    {State StepCode Input : Type}
    (decodeStep : StepCode → State → Input → State)
    (quoteLength : State → Nat)
    (stepLength : StepCode → Nat)
    (inputLength : Input → Nat) :
    DescriptionLanguage State where
  Code := OpenProgram State StepCode Input
  run := runOpen decodeStep
  codeLength :=
    openProgramLength quoteLength stepLength inputLength
  quote := .quote
  quoteSound := fun _ => rfl

/--
Opening the lineage replaces the depth-code term with the information actually
consumed from outside:

`K(state) ≤ K(seed) + K(step) + I(inputs) + 1`.
-/
theorem openInformationBound
    {State StepCode Input : Type}
    (decodeStep : StepCode → State → Input → State)
    (quoteLength : State → Nat)
    (stepLength : StepCode → Nat)
    (inputLength : Input → Nat)
    (seed : State)
    (stepCode : StepCode)
    {inputs : List Input}
    {state : State}
    (reachable :
      OpenReach seed (decodeStep stepCode) inputs state) :
    mdl
        (openLanguage
          decodeStep quoteLength stepLength inputLength)
        state ≤
      mdl
          (openLanguage
            decodeStep quoteLength stepLength inputLength)
          seed +
        stepLength stepCode +
        inputInformation inputLength inputs +
        1 := by
  classical
  rcases mdlSpec
      (openLanguage
        decodeStep quoteLength stepLength inputLength)
      seed with
    ⟨seedProgram, seedRuns, seedLength⟩
  have generated :
      runOpen decodeStep
          (.consume stepCode seedProgram inputs) = state := by
    change consumeInputs (decodeStep stepCode) inputs
      (runOpen decodeStep seedProgram) = state
    rw [seedRuns]
    exact reachable
  have upper :=
    mdlLeOfCode
      (openLanguage
        decodeStep quoteLength stepLength inputLength)
      generated
  change
    mdl
        (openLanguage
          decodeStep quoteLength stepLength inputLength)
        state ≤
      openProgramLength
          quoteLength stepLength inputLength seedProgram +
        stepLength stepCode +
        inputInformation inputLength inputs +
        1 at upper
  change
    openProgramLength quoteLength stepLength inputLength seedProgram =
      mdl
        (openLanguage
          decodeStep quoteLength stepLength inputLength)
        seed at seedLength
  rw [seedLength] at upper
  exact upper

theorem consumeInputsPreserves
    {State Input : Type}
    (step : State → Input → State)
    (Invariant : State → Prop)
    (preserves :
      ∀ state input,
        Invariant state →
        Invariant (step state input))
    {seed : State}
    (seedSafe : Invariant seed)
    (inputs : List Input) :
    Invariant (consumeInputs step inputs seed) := by
  induction inputs generalizing seed with
  | nil =>
      simpa [consumeInputs] using seedSafe
  | cons input rest inductionHypothesis =>
      simp only [consumeInputs]
      exact inductionHypothesis
        (preserves seed input seedSafe)

/--
The fixed-kernel closure proof and the information budget are independent
obligations.  Closure constrains every result of consuming input; it does not
bound how much input arrives.
-/
theorem openClosureAndInformationAccounting
    {State StepCode Input : Type}
    (decodeStep : StepCode → State → Input → State)
    (quoteLength : State → Nat)
    (stepLength : StepCode → Nat)
    (inputLength : Input → Nat)
    (seed : State)
    (stepCode : StepCode)
    (Invariant : State → Prop)
    (preserves :
      ∀ state input,
        Invariant state →
        Invariant (decodeStep stepCode state input))
    (seedSafe : Invariant seed)
    {inputs : List Input}
    {state : State}
    (reachable :
      OpenReach seed (decodeStep stepCode) inputs state) :
    Invariant state ∧
      mdl
          (openLanguage
            decodeStep quoteLength stepLength inputLength)
          state ≤
        mdl
            (openLanguage
              decodeStep quoteLength stepLength inputLength)
            seed +
          stepLength stepCode +
          inputInformation inputLength inputs +
          1 := by
  constructor
  · rw [← reachable]
    exact consumeInputsPreserves
      (decodeStep stepCode) Invariant preserves seedSafe inputs
  · exact openInformationBound
      decodeStep quoteLength stepLength inputLength
      seed stepCode reachable

def unitInputs : Nat → List Unit
  | 0 => []
  | count + 1 => () :: unitInputs count

theorem unitInputsCarryLinearInformation (count : Nat) :
    inputInformation (fun _ : Unit => 1) (unitInputs count) = count := by
  induction count with
  | zero =>
      rfl
  | succ count inductionHypothesis =>
      simp [unitInputs, inputInformation, inductionHypothesis]

end CrispOpen.AbstractReplay
