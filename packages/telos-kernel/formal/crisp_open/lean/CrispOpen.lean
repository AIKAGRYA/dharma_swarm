import Std

namespace CrispOpen

/-!
Iteration 5 replaces the truth-table accumulator with a total expression
language and formalizes the pre-registered anti-generator fork.

The fixed kernel `K` remains outside mutable state.  The active modification
operator `M state` is an expression stored inside the state: its denotation is
the denotation the next program must have.  Every accepted transition may
replace that operator with another well-typed expression.

The positive limbs establish unbounded-depth closure, unbounded semantic
magnitude, and a formal non-orthogonality result.  The decisive result is
negative: because `K` is decidable, a single fixed finite certificate-replay
generator enumerates every reachable state.  Therefore the requested
anti-generator condition cannot hold in this model.
-/

-- Object language ------------------------------------------------------------

/-- A small total language with composition, branching, and bounded recursion. -/
inductive Expr where
  | lit : Nat → Expr
  | add : Expr → Expr → Expr
  | double : Expr → Expr
  | succ : Expr → Expr
  | iteZero : Expr → Expr → Expr → Expr
  | iterDouble : Expr → Expr → Expr
  deriving DecidableEq, Repr

/-- Bounded recursion used by `Expr.iterDouble`. -/
def repeatDouble : Nat → Nat → Nat
  | 0, seed => seed
  | count + 1, seed => repeatDouble count (seed + seed)

/-- Total evaluation of closed expressions. -/
def eval : Expr → Nat
  | .lit value => value
  | .add left right => eval left + eval right
  | .double term => eval term + eval term
  | .succ term => eval term + 1
  | .iteZero condition whenZero whenNonzero =>
      if eval condition = 0 then eval whenZero else eval whenNonzero
  | .iterDouble count seed => repeatDouble (eval count) (eval seed)

/--
A denotation is a nullary total function.  Keeping the function layer explicit
ensures that semantic equality is not syntax equality.
-/
abbrev Denotation := Unit → Nat

def denote (program : Expr) : Denotation := fun _ => eval program

def observe (program : Expr) : Nat := denote program ()

/-- Explicit typing judgment.  `safe` programs and `step` operators must denote
a nonzero result; the judgment is semantic but decidable for this total language.
-/
inductive Ty where
  | nat
  | safe
  | step
  deriving DecidableEq, Repr

def HasType (program : Expr) : Ty → Prop
  | .nat => True
  | .safe => observe program ≠ 0
  | .step => observe program ≠ 0

instance (program : Expr) (ty : Ty) : Decidable (HasType program ty) := by
  cases ty <;> unfold HasType <;> infer_instance

-- Required denotation-gap witnesses -----------------------------------------

def sameSemanticsLeft : Expr := .add (.lit 0) (.lit 1)
def sameSemanticsRight : Expr := .lit 1

theorem sameSemanticsSyntaxDistinct :
    sameSemanticsLeft ≠ sameSemanticsRight := by
  decide

theorem sameSemanticsDenotationEqual :
    denote sameSemanticsLeft = denote sameSemanticsRight := by
  funext input
  cases input
  rfl

theorem sameSemanticsInvariantAgrees :
    HasType sameSemanticsLeft .safe ↔
      HasType sameSemanticsRight .safe := by
  rfl

def safeByConstructor : Expr := .succ (.lit 0)
def unsafeByConstructor : Expr := .double (.lit 0)

theorem oneConstructorSyntaxDifference :
    safeByConstructor ≠ unsafeByConstructor := by
  decide

theorem oneConstructorInvariantDifference :
    HasType safeByConstructor .safe ∧
      ¬ HasType unsafeByConstructor .safe := by
  simp [safeByConstructor, unsafeByConstructor, HasType, observe, denote, eval]

def recursiveLarge : Expr := .iterDouble (.lit 3) (.lit 1)
def recursiveCollapsed : Expr := .iterDouble (.lit 3) (.lit 0)

theorem boundedRecursionSemanticGap :
    observe recursiveLarge = 8 ∧ observe recursiveCollapsed = 0 := by
  decide

-- Mutable self-modification model -------------------------------------------

structure State where
  kernelId : Nat
  program : Expr
  modifier : Expr
  deriving DecidableEq, Repr

/-- The active modification operator is mutable state, not a fixed relation. -/
def M (state : State) : Expr := state.modifier

/-- The current operator proposes the denotation of the next program. -/
def ProposedBy (source target : State) : Prop :=
  observe target.program = observe (M source)

/-- The protected semantic invariant. -/
def Invariant (state : State) : Prop :=
  HasType state.program .safe

/-- The mutable operator must remain executable in the restricted language. -/
def ModifierWellTyped (state : State) : Prop :=
  HasType (M state) .step

def initial : State := {
  kernelId := 0
  program := .lit 1
  modifier := .lit 1
}

/-- The exact certificate checked by the immutable kernel. -/
def Admissible (source target : State) : Prop :=
  target.kernelId = source.kernelId ∧
  ProposedBy source target ∧
  Invariant target ∧
  ModifierWellTyped target

instance (source target : State) : Decidable (Admissible source target) := by
  unfold Admissible ProposedBy Invariant ModifierWellTyped M HasType
  infer_instance

/-- Immutable external checker. -/
def K (source target : State) : Bool :=
  decide (Admissible source target)

/-- An accepted proof-carrying rewrite. -/
def Accepted (source target : State) : Prop :=
  K source target = true

theorem checkerSound {source target : State}
    (accepted : Accepted source target) :
    Admissible source target := by
  apply of_decide_eq_true
  simpa [Accepted, K] using accepted

theorem checkerComplete {source target : State}
    (certificate : Admissible source target) :
    Accepted source target := by
  simp [Accepted, K, certificate]

/-- Exact-depth reachability over an unbounded natural index. -/
inductive Reach : Nat → State → Prop where
  | zero : Reach 0 initial
  | succ {depth : Nat} {source target : State} :
      Reach depth source →
      Accepted source target →
      Reach (depth + 1) target

theorem initialInvariant : Invariant initial := by
  simp [Invariant, initial, HasType, observe, denote, eval]

theorem initialModifierWellTyped : ModifierWellTyped initial := by
  simp [ModifierWellTyped, M, initial, HasType, observe, denote, eval]

/-- Limb (A), by structural induction over arbitrary modification depth. -/
theorem closure {depth : Nat} {state : State}
    (reachable : Reach depth state) :
    Invariant state := by
  induction reachable with
  | zero =>
      exact initialInvariant
  | succ previous accepted inductionHypothesis =>
      exact (checkerSound accepted).2.2.1

theorem modifierTypedClosure {depth : Nat} {state : State}
    (reachable : Reach depth state) :
    ModifierWellTyped state := by
  induction reachable with
  | zero =>
      exact initialModifierWellTyped
  | succ previous accepted inductionHypothesis =>
      exact (checkerSound accepted).2.2.2

/-- The external kernel identity remains fixed while `M` changes. -/
theorem kernelFixed {depth : Nat} {state : State}
    (reachable : Reach depth state) :
    state.kernelId = initial.kernelId := by
  induction reachable with
  | zero =>
      rfl
  | succ previous accepted inductionHypothesis =>
      calc
        _ = _ := (checkerSound accepted).1
        _ = initial.kernelId := inductionHypothesis

-- Non-vacuity and actual operator rewriting ---------------------------------

def unsafeState : State := {
  kernelId := 0
  program := unsafeByConstructor
  modifier := .lit 1
}

/-- A source whose operator genuinely proposes semantic zero. -/
def unsafeSource : State := {
  kernelId := 0
  program := .lit 1
  modifier := unsafeByConstructor
}

theorem unsafeProposed :
    ProposedBy unsafeSource unsafeState := by
  rfl

theorem unsafeViolatesInvariant :
    ¬ Invariant unsafeState := by
  simp [Invariant, unsafeState, unsafeByConstructor, HasType, observe, denote, eval]

theorem unsafeRejected :
    K unsafeSource unsafeState = false := by
  simp [K, Admissible, ProposedBy, unsafeSource, unsafeState, Invariant,
    ModifierWellTyped, M, unsafeByConstructor, HasType, observe, denote, eval]

/-- First accepted transition rewrites the modification operator from 1 to 2. -/
def modifierRewriteState : State := {
  kernelId := 0
  program := .lit 1
  modifier := .double (.lit 1)
}

theorem nontrivialAccepted :
    Accepted initial modifierRewriteState := by
  simp [Accepted, K, Admissible, ProposedBy, initial, modifierRewriteState,
    Invariant, ModifierWellTyped, M, HasType, observe, denote, eval]

theorem modifierActuallyRewritten :
    observe (M initial) ≠ observe (M modifierRewriteState) := by
  simp [M, initial, modifierRewriteState, observe, denote, eval]

/-- The rewritten operator now proposes 2, which the old operator did not. -/
def modifierEffectState : State := {
  kernelId := 0
  program := .lit 2
  modifier := .lit 1
}

theorem rewriteExistingCellAccepted :
    Accepted modifierRewriteState modifierEffectState := by
  simp [Accepted, K, Admissible, ProposedBy, modifierRewriteState,
    modifierEffectState, Invariant, ModifierWellTyped, M, HasType, observe,
    denote, eval]

theorem rewrittenOperatorChangesProposal :
    ProposedBy modifierRewriteState modifierEffectState ∧
      ¬ ProposedBy initial modifierEffectState := by
  simp [ProposedBy, M, modifierRewriteState, modifierEffectState, initial,
    observe, denote, eval]

-- Positive opening limb ------------------------------------------------------

def stage1 (bound : Nat) : State := {
  kernelId := 0
  program := .lit 1
  modifier := .lit (bound + 1)
}

def stage2 (bound : Nat) : State := {
  kernelId := 0
  program := .lit (bound + 1)
  modifier := .lit 1
}

theorem stage1Accepted (bound : Nat) :
    Accepted initial (stage1 bound) := by
  simp [Accepted, K, Admissible, ProposedBy, initial, stage1, Invariant,
    ModifierWellTyped, M, HasType, observe, denote, eval]

theorem stage2Accepted (bound : Nat) :
    Accepted (stage1 bound) (stage2 bound) := by
  simp [Accepted, K, Admissible, ProposedBy, stage1, stage2, Invariant,
    ModifierWellTyped, M, HasType, observe, denote, eval]

theorem stage1Reachable (bound : Nat) :
    Reach 1 (stage1 bound) := by
  simpa using
    (Reach.succ (Reach.zero : Reach 0 initial) (stage1Accepted bound))

theorem stage2Reachable (bound : Nat) :
    Reach 2 (stage2 bound) := by
  simpa using
    (Reach.succ (stage1Reachable bound) (stage2Accepted bound))

/-- Complexity is magnitude in the same semantic coordinate constrained by `I`. -/
def complexity (state : State) : Nat :=
  observe state.program

/-- Limb (B): semantic magnitude is unbounded among reachable states. -/
theorem opening (bound : Nat) :
    ∃ depth state, Reach depth state ∧ complexity state > bound := by
  refine ⟨2, stage2 bound, stage2Reachable bound, ?_⟩
  simpa [complexity, stage2, observe, denote, eval] using Nat.lt_succ_self bound

-- Surface 7: coordinate orthogonality ---------------------------------------

def SemanticInvariant (value : Nat) : Prop :=
  value ≠ 0

def SemanticComplexity (value : Nat) : Nat :=
  value

theorem invariantUsesSemanticCoordinate (state : State) :
    Invariant state ↔ SemanticInvariant (observe state.program) := by
  rfl

theorem complexityUsesSemanticCoordinate (state : State) :
    complexity state = SemanticComplexity (observe state.program) := by
  rfl

/--
A prohibited orthogonalization: an equivalence splits the semantic space into
protected and free coordinates, `I` reads only the protected coordinate, and
`C` reads only the free coordinate.
-/
structure OrthogonalDecomposition where
  protectedSpace : Type
  freeSpace : Type
  split : Nat ≃ protectedSpace × freeSpace
  protectedInvariant : protectedSpace → Prop
  freeComplexity : freeSpace → Nat
  invariantFactors :
    ∀ value, SemanticInvariant value ↔
      protectedInvariant (split value).1
  complexityFactors :
    ∀ value, SemanticComplexity value =
      freeComplexity (split value).2

/--
Because `C` is the identity semantic coordinate, a fixed free coordinate can
correspond to only one semantic value.  Surjectivity of `split` therefore
forces the protected factor to be a subsingleton.
-/
theorem orthogonalProtectedSubsingleton
    (decomposition : OrthogonalDecomposition) :
    ∀ left right : decomposition.protectedSpace, left = right := by
  intro left right
  let free : decomposition.freeSpace := (decomposition.split 0).2
  let leftValue : Nat := decomposition.split.symm (left, free)
  let rightValue : Nat := decomposition.split.symm (right, free)
  have leftFree :
      (decomposition.split leftValue).2 = free := by
    simp [leftValue]
  have rightFree :
      (decomposition.split rightValue).2 = free := by
    simp [rightValue]
  have leftMeasure :
      leftValue = decomposition.freeComplexity free := by
    calc
      leftValue =
          decomposition.freeComplexity (decomposition.split leftValue).2 := by
            simpa [SemanticComplexity] using
              decomposition.complexityFactors leftValue
      _ = decomposition.freeComplexity free := by rw [leftFree]
  have rightMeasure :
      rightValue = decomposition.freeComplexity free := by
    calc
      rightValue =
          decomposition.freeComplexity (decomposition.split rightValue).2 := by
            simpa [SemanticComplexity] using
              decomposition.complexityFactors rightValue
      _ = decomposition.freeComplexity free := by rw [rightFree]
  have valuesEqual : leftValue = rightValue :=
    leftMeasure.trans rightMeasure.symm
  have pairsEqual : (left, free) = (right, free) := by
    calc
      (left, free) = decomposition.split leftValue := by
        simp [leftValue]
      _ = decomposition.split rightValue := congrArg decomposition.split valuesEqual
      _ = (right, free) := by
        simp [rightValue]
  exact congrArg Prod.fst pairsEqual

/-- Formal discharge of Surface 7 for the selected `I` and `C`. -/
theorem coordinateOrthogonalityImpossible :
    ¬ Nonempty OrthogonalDecomposition := by
  rintro ⟨decomposition⟩
  have protectedEqual :
      (decomposition.split 1).1 = (decomposition.split 0).1 :=
    orthogonalProtectedSubsingleton decomposition _ _
  have safeOne : SemanticInvariant 1 := by
    simp [SemanticInvariant]
  have unsafeZero : ¬ SemanticInvariant 0 := by
    simp [SemanticInvariant]
  have protectedOne :
      decomposition.protectedInvariant (decomposition.split 1).1 :=
    (decomposition.invariantFactors 1).mp safeOne
  have protectedZero :
      decomposition.protectedInvariant (decomposition.split 0).1 := by
    rw [← protectedEqual]
    exact protectedOne
  exact unsafeZero ((decomposition.invariantFactors 0).mpr protectedZero)

-- Fork B: decidable reachability has a fixed finite generator ----------------

/--
A fixed program replays a finite reverse-chronological certificate path.
The generator itself never changes; its input carries the candidate path.
-/
def replayCertificates : List State → Option State
  | [] => some initial
  | target :: rest =>
      match replayCertificates rest with
      | none => none
      | some source =>
          if K source target then some target else none

theorem reachableHasReplayCertificate
    {depth : Nat} {state : State}
    (reachable : Reach depth state) :
    ∃ certificate, replayCertificates certificate = some state := by
  induction reachable with
  | zero =>
      exact ⟨[], rfl⟩
  | succ previous accepted inductionHypothesis =>
      rcases inductionHypothesis with ⟨certificate, replayed⟩
      refine ⟨target :: certificate, ?_⟩
      simp [replayCertificates, replayed, accepted, Accepted]

/-- A finite generator language containing the decisive fixed generator. -/
inductive GeneratorProgram where
  | reject
  | replay
  deriving DecidableEq, Repr

def runGenerator : GeneratorProgram → List State → Option State
  | .reject, _ => none
  | .replay, certificate => replayCertificates certificate

def generatorDescriptionLength : GeneratorProgram → Nat
  | .reject => 1
  | .replay => 1

theorem replayGeneratorHasBoundedDescription :
    generatorDescriptionLength .replay = 1 := by
  rfl

theorem fixedReplayGeneratorCovers
    {depth : Nat} {state : State}
    (reachable : Reach depth state) :
    ∃ certificate, runGenerator .replay certificate = some state := by
  simpa [runGenerator] using reachableHasReplayCertificate reachable

/--
The directive's anti-generator obligation, specialized to a finite generator
language that includes certificate replay.
-/
def AntiGenerator : Prop :=
  ∀ generator : GeneratorProgram,
    ∃ depth state,
      Reach depth state ∧
      ∀ certificate, runGenerator generator certificate ≠ some state

/-- Fork B lands: the replay generator's range contains every reachable state. -/
theorem antiGeneratorImpossible :
    ¬ AntiGenerator := by
  intro antiGenerator
  rcases antiGenerator .replay with
    ⟨depth, state, reachable, escaped⟩
  rcases fixedReplayGeneratorCovers reachable with
    ⟨certificate, generated⟩
  exact escaped certificate generated

-- Revised target and incompatibility ----------------------------------------

def ClosureProperty : Prop :=
  ∀ depth state, Reach depth state → Invariant state

def OpeningProperty : Prop :=
  ∀ bound, ∃ depth state,
    Reach depth state ∧ complexity state > bound

def CouplingProperty : Prop :=
  ¬ Nonempty OrthogonalDecomposition

theorem closurePropertyHolds : ClosureProperty := by
  intro depth state reachable
  exact closure reachable

theorem openingPropertyHolds : OpeningProperty := by
  intro bound
  exact opening bound

theorem couplingPropertyHolds : CouplingProperty :=
  coordinateOrthogonalityImpossible

/-- Positive conjunction retained as an audit boundary; it excludes `GEN`. -/
theorem targetTheorem :
    ClosureProperty ∧ OpeningProperty ∧ CouplingProperty := by
  exact ⟨closurePropertyHolds, openingPropertyHolds, couplingPropertyHolds⟩

/--
The revised four-limb target is impossible in this model.  The proof does not
need to weaken closure, opening, or coupling: `GEN` is contradicted directly by
the fixed certificate-replay generator forced by decidable checking.
-/
theorem revisedTargetImpossible :
    ¬ (ClosureProperty ∧ OpeningProperty ∧ CouplingProperty ∧ AntiGenerator) := by
  intro target
  exact antiGeneratorImpossible target.2.2.2

end CrispOpen
