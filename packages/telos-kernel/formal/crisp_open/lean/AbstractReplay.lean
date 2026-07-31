import Std
import Init.Data.Nat.Log2

namespace CrispOpen.AbstractReplay

/-!
Iteration 6 keeps the certificate-replay theorem, but narrows its meaning: it
refutes one withdrawn range-based definition of open-endedness.  The main
result is instead an object-language-relative description-length ceiling.

`MDLModel` does not postulate universal Kolmogorov complexity.  It packages one
explicit description language together with its shortest-code function, the
exact length of that code, and the lower-bound law that characterizes the
minimum.  The closed and open theorems are parametric over every such model.
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
        run replayCode certificate = replay initial step certificate) :
    ¬ RangeAntiGenerator initial step complexity run := by
  intro antiGenerator
  rcases antiGenerator replayCode 0 with
    ⟨depth, state, reachable, larger, escaped⟩
  rcases reachableHasReplayCertificate reachable with
    ⟨certificate, replayed⟩
  apply escaped certificate
  calc
    run replayCode certificate = replay initial step certificate :=
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

/-- The withdrawn range condition fails for every fixed Boolean checker. -/
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

/--
One explicit description language and its minimum-description-length function.
`shortest` realizes the minimum; `lowerBound` proves no code is shorter.
-/
structure MDLModel (Output : Type) where
  Code : Type
  run : Code → Output
  codeLength : Code → Nat
  K : Output → Nat
  shortest : Output → Code
  shortestRuns : ∀ output, run (shortest output) = output
  shortestLength : ∀ output, codeLength (shortest output) = K output
  lowerBound : ∀ code, K (run code) ≤ codeLength code

theorem KLeOfCode
    {Output : Type}
    (language : MDLModel Output)
    (code : language.Code) :
    language.K (language.run code) ≤ language.codeLength code :=
  language.lowerBound code

/-- Ordinary binary length, charging one bit for zero. -/
def bitLength (value : Nat) : Nat :=
  Nat.log2 (value + 1) + 1

/-- A total self-delimiting natural-number code length. -/
def natCodeLength (value : Nat) : Nat :=
  bitLength value + 2 * bitLength (bitLength value) + 1

theorem natCodeLengthShape (value : Nat) :
    natCodeLength value =
      bitLength value + 2 * bitLength (bitLength value) + 1 := by
  rfl

/-- A concrete object language for natural numbers. -/
def natMDL : MDLModel Nat where
  Code := Nat
  run := fun value => value
  codeLength := natCodeLength
  K := natCodeLength
  shortest := fun value => value
  shortestRuns := fun _ => rfl
  shortestLength := fun _ => rfl
  lowerBound := fun _ => Nat.le_refl _

theorem natKIsSelfDelimiting (value : Nat) :
    natMDL.K value = natCodeLength value := by
  rfl

-- Closed deterministic systems ------------------------------------------------

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

/--
A fixed interpreter that combines descriptions of a seed, deterministic step,
and depth into a state description.  `overhead` is the fixed interpreter cost.
-/
structure ClosedComposer
    (State : Type)
    (stateLanguage : MDLModel State)
    (stepLanguage : MDLModel (State → State))
    (depthLanguage : MDLModel Nat) where
  overhead : Nat
  compose :
    stateLanguage.Code →
    stepLanguage.Code →
    depthLanguage.Code →
    stateLanguage.Code
  sound : ∀ seedCode stepCode depthCode,
    stateLanguage.run (compose seedCode stepCode depthCode) =
      iterate
        (stepLanguage.run stepCode)
        (depthLanguage.run depthCode)
        (stateLanguage.run seedCode)
  lengthBound : ∀ seedCode stepCode depthCode,
    stateLanguage.codeLength (compose seedCode stepCode depthCode) ≤
      stateLanguage.codeLength seedCode +
        stepLanguage.codeLength stepCode +
        depthLanguage.codeLength depthCode +
        overhead

/--
The exact closed-system ceiling requested by Iteration 6:

`K(state) ≤ K(seed) + K(step) + K(depth) + O(1)`.
-/
theorem closedLogarithmicCeiling
    {State : Type}
    (stateLanguage : MDLModel State)
    (stepLanguage : MDLModel (State → State))
    (depthLanguage : MDLModel Nat)
    (composer :
      ClosedComposer State stateLanguage stepLanguage depthLanguage)
    (seed : State)
    (step : State → State)
    {depth : Nat}
    {state : State}
    (reachable : ClosedReach seed step depth state) :
    stateLanguage.K state ≤
      stateLanguage.K seed +
        stepLanguage.K step +
        depthLanguage.K depth +
        composer.overhead := by
  let seedCode := stateLanguage.shortest seed
  let stepCode := stepLanguage.shortest step
  let depthCode := depthLanguage.shortest depth
  let composite := composer.compose seedCode stepCode depthCode
  have compositeRuns : stateLanguage.run composite = state := by
    dsimp [composite, seedCode, stepCode, depthCode]
    rw [composer.sound]
    rw [stateLanguage.shortestRuns]
    rw [stepLanguage.shortestRuns]
    rw [depthLanguage.shortestRuns]
    exact reachable
  have lower := stateLanguage.lowerBound composite
  rw [compositeRuns] at lower
  calc
    stateLanguage.K state ≤ stateLanguage.codeLength composite := lower
    _ ≤ stateLanguage.codeLength seedCode +
          stepLanguage.codeLength stepCode +
          depthLanguage.codeLength depthCode +
          composer.overhead :=
      composer.lengthBound seedCode stepCode depthCode
    _ = stateLanguage.K seed +
          stepLanguage.K step +
          depthLanguage.K depth +
          composer.overhead := by
      rw [stateLanguage.shortestLength]
      rw [stepLanguage.shortestLength]
      rw [depthLanguage.shortestLength]

/-- Specialization to the explicit self-delimiting natural-number language. -/
theorem closedSelfDelimitingCeiling
    {State : Type}
    (stateLanguage : MDLModel State)
    (stepLanguage : MDLModel (State → State))
    (composer : ClosedComposer State stateLanguage stepLanguage natMDL)
    (seed : State)
    (step : State → State)
    {depth : Nat}
    {state : State}
    (reachable : ClosedReach seed step depth state) :
    stateLanguage.K state ≤
      stateLanguage.K seed +
        stepLanguage.K step +
        natCodeLength depth +
        composer.overhead := by
  exact closedLogarithmicCeiling
    stateLanguage stepLanguage natMDL composer seed step reachable

def ClosedCeilingExceeded
    {State : Type}
    (stateLanguage : MDLModel State)
    (stepLanguage : MDLModel (State → State))
    (composer : ClosedComposer State stateLanguage stepLanguage natMDL)
    (seed : State)
    (step : State → State)
    (depth : Nat)
    (state : State) : Prop :=
  stateLanguage.K state >
    stateLanguage.K seed +
      stepLanguage.K step +
      natCodeLength depth +
      composer.overhead

theorem closedCannotExceedDescriptionCeiling
    {State : Type}
    (stateLanguage : MDLModel State)
    (stepLanguage : MDLModel (State → State))
    (composer : ClosedComposer State stateLanguage stepLanguage natMDL)
    (seed : State)
    (step : State → State)
    {depth : Nat}
    {state : State}
    (reachable : ClosedReach seed step depth state) :
    ¬ ClosedCeilingExceeded
      stateLanguage stepLanguage composer seed step depth state := by
  exact Nat.not_lt_of_ge
    (closedSelfDelimitingCeiling
      stateLanguage stepLanguage composer seed step reachable)

-- A pure counter spends exactly the depth-description term -------------------

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

/--
The counter contains no structure beyond its depth, yet its declared descriptive
complexity is the same self-delimiting depth code used in the closed ceiling.
-/
theorem pureCounterComplexityIsDepthCode (depth : Nat) :
    natMDL.K (iterate counterStep depth 0) = natCodeLength depth := by
  rw [iterateCounterFromZero]
  rfl

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

/-- A fixed interpreter for seed, step, and externally supplied input. -/
structure OpenComposer
    (State Input : Type)
    (stateLanguage : MDLModel State)
    (stepLanguage : MDLModel (State → Input → State))
    (inputLanguage : MDLModel (List Input)) where
  overhead : Nat
  compose :
    stateLanguage.Code →
    stepLanguage.Code →
    inputLanguage.Code →
    stateLanguage.Code
  sound : ∀ seedCode stepCode inputCode,
    stateLanguage.run (compose seedCode stepCode inputCode) =
      consumeInputs
        (stepLanguage.run stepCode)
        (inputLanguage.run inputCode)
        (stateLanguage.run seedCode)
  lengthBound : ∀ seedCode stepCode inputCode,
    stateLanguage.codeLength (compose seedCode stepCode inputCode) ≤
      stateLanguage.codeLength seedCode +
        stepLanguage.codeLength stepCode +
        inputLanguage.codeLength inputCode +
        overhead

/--
Exit 1 replaces the depth term by the description length of information
actually consumed from outside the lineage.
-/
theorem openInformationBound
    {State Input : Type}
    (stateLanguage : MDLModel State)
    (stepLanguage : MDLModel (State → Input → State))
    (inputLanguage : MDLModel (List Input))
    (composer :
      OpenComposer State Input stateLanguage stepLanguage inputLanguage)
    (seed : State)
    (step : State → Input → State)
    {inputs : List Input}
    {state : State}
    (reachable : OpenReach seed step inputs state) :
    stateLanguage.K state ≤
      stateLanguage.K seed +
        stepLanguage.K step +
        inputLanguage.K inputs +
        composer.overhead := by
  let seedCode := stateLanguage.shortest seed
  let stepCode := stepLanguage.shortest step
  let inputCode := inputLanguage.shortest inputs
  let composite := composer.compose seedCode stepCode inputCode
  have compositeRuns : stateLanguage.run composite = state := by
    dsimp [composite, seedCode, stepCode, inputCode]
    rw [composer.sound]
    rw [stateLanguage.shortestRuns]
    rw [stepLanguage.shortestRuns]
    rw [inputLanguage.shortestRuns]
    exact reachable
  have lower := stateLanguage.lowerBound composite
  rw [compositeRuns] at lower
  calc
    stateLanguage.K state ≤ stateLanguage.codeLength composite := lower
    _ ≤ stateLanguage.codeLength seedCode +
          stepLanguage.codeLength stepCode +
          inputLanguage.codeLength inputCode +
          composer.overhead :=
      composer.lengthBound seedCode stepCode inputCode
    _ = stateLanguage.K seed +
          stepLanguage.K step +
          inputLanguage.K inputs +
          composer.overhead := by
      rw [stateLanguage.shortestLength]
      rw [stepLanguage.shortestLength]
      rw [inputLanguage.shortestLength]

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
      exact inductionHypothesis (preserves seed input seedSafe)

/--
Closure and information supply are formally independent conjuncts: preservation
constrains every consumed input, while the description bound charges the input.
-/
theorem openClosureAndInformationAccounting
    {State Input : Type}
    (stateLanguage : MDLModel State)
    (stepLanguage : MDLModel (State → Input → State))
    (inputLanguage : MDLModel (List Input))
    (composer :
      OpenComposer State Input stateLanguage stepLanguage inputLanguage)
    (seed : State)
    (step : State → Input → State)
    (Invariant : State → Prop)
    (preserves :
      ∀ state input,
        Invariant state →
        Invariant (step state input))
    (seedSafe : Invariant seed)
    {inputs : List Input}
    {state : State}
    (reachable : OpenReach seed step inputs state) :
    Invariant state ∧
      stateLanguage.K state ≤
        stateLanguage.K seed +
          stepLanguage.K step +
          inputLanguage.K inputs +
          composer.overhead := by
  constructor
  · rw [← reachable]
    exact consumeInputsPreserves
      step Invariant preserves seedSafe inputs
  · exact openInformationBound
      stateLanguage stepLanguage inputLanguage composer
      seed step reachable

/-- A simple information ledger whose cost grows one unit per input. -/
def unitInputs : Nat → List Unit
  | 0 => []
  | count + 1 => () :: unitInputs count

def unitInputInformation : List Unit → Nat
  | [] => 0
  | () :: rest => 1 + unitInputInformation rest

theorem unitInputsCarryLinearInformation (count : Nat) :
    unitInputInformation (unitInputs count) = count := by
  induction count with
  | zero =>
      rfl
  | succ count inductionHypothesis =>
      simp [unitInputs, unitInputInformation, inductionHypothesis, Nat.add_comm]

end CrispOpen.AbstractReplay
