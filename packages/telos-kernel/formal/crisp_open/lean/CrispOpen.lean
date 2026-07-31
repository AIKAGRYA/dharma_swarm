import Std
import Lean.Elab.Tactic.Omega

namespace CrispOpen

/-!
Iteration 5 replaces the killed truth-table construction with:

* a total expression language with composition, branching, and bounded recursion;
* a mutable AST-rewrite language stored inside each state;
* a fixed checker that validates both the current and proposed rewrite operators;
* an invariant and complexity measure on the same semantic coordinate; and
* a fixed certificate-replay generator that defeats the requested anti-generator
  condition.

The positive closure, opening, and coupling limbs are retained only to isolate
the pre-registered Fork B. The final theorem is an incompatibility result for
the revised four-limb target in this model.
-/

-- Object language ------------------------------------------------------------

/-- A small total language denoting functions `Nat → Nat`. -/
inductive Expr where
  | input : Expr
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

/-- Total evaluation. -/
def eval : Expr → Nat → Nat
  | .input, input => input
  | .lit value, _ => value
  | .add left right, input => eval left input + eval right input
  | .double term, input => eval term input + eval term input
  | .succ term, input => eval term input + 1
  | .iteZero condition whenZero whenNonzero, input =>
      if eval condition input = 0 then
        eval whenZero input
      else
        eval whenNonzero input
  | .iterDouble count seed, input =>
      repeatDouble (eval count input) (eval seed input)

abbrev Denotation := Nat → Nat

def denote (program : Expr) : Denotation :=
  fun input => eval program input

/-- The shared semantic coordinate used by both the invariant and complexity. -/
def observe (program : Expr) : Nat :=
  denote program 0

inductive Ty where
  | nat
  | safe
  deriving DecidableEq, Repr

/--
`safe` is semantic: the denoted function must return an even number at input
zero. Odd values are rejected, so the judgment is non-vacuous.
-/
def HasType (program : Expr) : Ty → Prop
  | .nat => True
  | .safe => observe program % 2 = 0

instance (program : Expr) (ty : Ty) : Decidable (HasType program ty) := by
  cases ty <;> unfold HasType <;> infer_instance

-- Required denotation-gap witnesses -----------------------------------------

def sameSemanticsLeft : Expr :=
  .double .input

def sameSemanticsRight : Expr :=
  .add .input .input

theorem sameSemanticsSyntaxDistinct :
    sameSemanticsLeft ≠ sameSemanticsRight := by
  decide

theorem sameSemanticsDenotationEqual :
    denote sameSemanticsLeft = denote sameSemanticsRight := by
  funext input
  rfl

theorem sameSemanticsInvariantAgrees :
    HasType sameSemanticsLeft .safe ↔
      HasType sameSemanticsRight .safe := by
  rfl

def safeByConstructor : Expr :=
  .double (.lit 0)

def unsafeByConstructor : Expr :=
  .succ (.lit 0)

theorem oneConstructorSyntaxDifference :
    safeByConstructor ≠ unsafeByConstructor := by
  decide

theorem oneConstructorInvariantDifference :
    HasType safeByConstructor .safe ∧
      ¬ HasType unsafeByConstructor .safe := by
  decide

def branchingExample : Expr :=
  .iteZero .input (.lit 2) (.lit 3)

theorem branchingExampleAtZero :
    eval branchingExample 0 = 2 := by
  decide

theorem branchingExampleAwayFromZero :
    eval branchingExample 1 = 3 := by
  decide

def recursiveLarge : Expr :=
  .iterDouble (.lit 3) (.lit 1)

def recursiveCollapsed : Expr :=
  .iterDouble (.lit 3) (.lit 0)

theorem boundedRecursionSemanticGap :
    observe recursiveLarge = 8 ∧
      observe recursiveCollapsed = 0 := by
  decide

-- Mutable modification-operator language ------------------------------------

/--
A finite AST-transformer language. `replace`, `compose`, and `branch` make the
operator a genuine rewrite over program syntax rather than a data-table update.
`wrapSucc` is deliberately present but cannot receive the preservation type.
-/
inductive Rewrite where
  | keep : Rewrite
  | replace : Expr → Rewrite
  | wrapSucc : Rewrite
  | wrapDouble : Rewrite
  | compose : Rewrite → Rewrite → Rewrite
  | branch : Expr → Rewrite → Rewrite → Rewrite
  deriving DecidableEq, Repr

def applyRewrite : Rewrite → Expr → Expr
  | .keep, program => program
  | .replace replacement, _ => replacement
  | .wrapSucc, program => .succ program
  | .wrapDouble, program => .double program
  | .compose first second, program =>
      applyRewrite second (applyRewrite first program)
  | .branch guard whenZero whenNonzero, program =>
      if observe guard = 0 then
        applyRewrite whenZero program
      else
        applyRewrite whenNonzero program

inductive RewriteTy where
  | preservesSafe
  deriving DecidableEq, Repr

/--
A decidable certificate checker for rewrite operators. Replacement carries a
semantic certificate for its replacement program; composition and branching
carry certificates recursively. `wrapSucc` is rejected.
-/
def rewriteSafeBool : Rewrite → Bool
  | .keep => true
  | .replace replacement => decide (HasType replacement .safe)
  | .wrapSucc => false
  | .wrapDouble => true
  | .compose first second =>
      rewriteSafeBool first && rewriteSafeBool second
  | .branch _ whenZero whenNonzero =>
      rewriteSafeBool whenZero && rewriteSafeBool whenNonzero

def HasRewriteType (rewrite : Rewrite) : RewriteTy → Prop
  | .preservesSafe => rewriteSafeBool rewrite = true

instance (rewrite : Rewrite) (ty : RewriteTy) :
    Decidable (HasRewriteType rewrite ty) := by
  cases ty
  unfold HasRewriteType
  infer_instance

/-- The checker for rewrite certificates is sound for the semantic type. -/
theorem rewriteTypeSound
    {rewrite : Rewrite} {program : Expr}
    (typed : HasRewriteType rewrite .preservesSafe)
    (safe : HasType program .safe) :
    HasType (applyRewrite rewrite program) .safe := by
  induction rewrite generalizing program with
  | keep =>
      simpa [applyRewrite] using safe
  | replace replacement =>
      have replacementSafe : HasType replacement .safe := by
        apply of_decide_eq_true
        simpa [HasRewriteType, rewriteSafeBool] using typed
      simpa [applyRewrite] using replacementSafe
  | wrapSucc =>
      simp [HasRewriteType, rewriteSafeBool] at typed
  | wrapDouble =>
      change (eval program 0 + eval program 0) % 2 = 0
      omega
  | compose first second firstIH secondIH =>
      have parts :
          HasRewriteType first .preservesSafe ∧
            HasRewriteType second .preservesSafe := by
        simpa [HasRewriteType, rewriteSafeBool] using typed
      exact secondIH parts.2 (firstIH parts.1 safe)
  | branch guard whenZero whenNonzero zeroIH nonzeroIH =>
      have parts :
          HasRewriteType whenZero .preservesSafe ∧
            HasRewriteType whenNonzero .preservesSafe := by
        simpa [HasRewriteType, rewriteSafeBool] using typed
      simp only [applyRewrite]
      split
      · exact zeroIH parts.1 safe
      · exact nonzeroIH parts.2 safe

-- Fixed checker and mutable state --------------------------------------------

structure State where
  kernelId : Nat
  program : Expr
  modifier : Rewrite
  deriving DecidableEq, Repr

/-- The active modification operator lives in mutable state. -/
def M (state : State) : Rewrite :=
  state.modifier

def ProposedBy (source target : State) : Prop :=
  target.program = applyRewrite (M source) source.program

def Invariant (state : State) : Prop :=
  HasType state.program .safe

instance (state : State) : Decidable (Invariant state) := by
  unfold Invariant
  infer_instance

def ModifierCertified (state : State) : Prop :=
  HasRewriteType (M state) .preservesSafe

/-- Even semantic values provide an unbounded, coupled lineage. -/
def evenValue (depth : Nat) : Nat :=
  (depth + 1) + (depth + 1)

def lineage (depth : Nat) : State := {
  kernelId := 0
  program := .lit (evenValue depth)
  modifier := .replace (.lit (evenValue (depth + 1)))
}

def initial : State :=
  lineage 0

/--
The immutable kernel checks the source invariant, the current operator's
certificate, the exact AST rewrite, and the proposed next operator's
certificate. It does not live inside `State`.
-/
def Admissible (source target : State) : Prop :=
  target.kernelId = source.kernelId ∧
  Invariant source ∧
  ModifierCertified source ∧
  ProposedBy source target ∧
  ModifierCertified target

instance (source target : State) : Decidable (Admissible source target) := by
  unfold Admissible Invariant ModifierCertified ProposedBy M
  infer_instance

def K (source target : State) : Bool :=
  decide (Admissible source target)

def Accepted (source target : State) : Prop :=
  K source target = true

theorem checkerSound
    {source target : State}
    (accepted : Accepted source target) :
    Admissible source target := by
  apply of_decide_eq_true
  simpa [Accepted, K] using accepted

theorem checkerComplete
    {source target : State}
    (certificate : Admissible source target) :
    Accepted source target := by
  simp [Accepted, K, certificate]

/-- An accepted certificate implies semantic preservation. -/
theorem acceptedPreservesInvariant
    {source target : State}
    (accepted : Accepted source target) :
    Invariant target := by
  have certificate := checkerSound accepted
  have sourceInvariant : Invariant source :=
    certificate.2.1
  have sourceModifier : ModifierCertified source :=
    certificate.2.2.1
  have proposed : ProposedBy source target :=
    certificate.2.2.2.1
  have transformed :
      HasType (applyRewrite (M source) source.program) .safe :=
    rewriteTypeSound sourceModifier sourceInvariant
  unfold Invariant
  rw [proposed]
  exact transformed

/-- Exact-depth reachability over an unbounded natural index. -/
inductive Reach : Nat → State → Prop where
  | zero : Reach 0 initial
  | succ {depth : Nat} {source target : State} :
      Reach depth source →
      Accepted source target →
      Reach (depth + 1) target

theorem initialInvariant :
    Invariant initial := by
  simp [Invariant, initial, lineage, evenValue, HasType, observe, denote, eval]

theorem initialModifierCertified :
    ModifierCertified initial := by
  simp [ModifierCertified, M, initial, lineage, evenValue, HasRewriteType,
    rewriteSafeBool, HasType, observe, denote, eval]

/-- Limb (A): structural induction over arbitrary modification depth. -/
theorem closure
    {depth : Nat} {state : State}
    (reachable : Reach depth state) :
    Invariant state := by
  induction reachable with
  | zero =>
      exact initialInvariant
  | succ previous accepted inductionHypothesis =>
      exact acceptedPreservesInvariant accepted

theorem modifierCertifiedClosure
    {depth : Nat} {state : State}
    (reachable : Reach depth state) :
    ModifierCertified state := by
  induction reachable with
  | zero =>
      exact initialModifierCertified
  | succ previous accepted inductionHypothesis =>
      exact (checkerSound accepted).2.2.2.2

/--
The external checker identity remains fixed even through arbitrarily many
rewrites of the in-state modification operator.
-/
theorem kernelFixed
    {depth : Nat} {state : State}
    (reachable : Reach depth state) :
    state.kernelId = initial.kernelId := by
  induction reachable with
  | zero =>
      rfl
  | succ previous accepted inductionHypothesis =>
      calc
        _ = _ := (checkerSound accepted).1
        _ = initial.kernelId := inductionHypothesis

-- Non-vacuity and actual self-modification -----------------------------------

def unsafeProgram : Expr :=
  .succ (.lit 0)

def unsafeSource : State := {
  kernelId := 0
  program := .lit 2
  modifier := .replace unsafeProgram
}

def unsafeState : State := {
  kernelId := 0
  program := unsafeProgram
  modifier := .keep
}

theorem unsafeProposed :
    ProposedBy unsafeSource unsafeState := by
  rfl

theorem unsafeViolatesInvariant :
    ¬ Invariant unsafeState := by
  decide

theorem unsafeRejected :
    K unsafeSource unsafeState = false := by
  decide

/--
This target has the correct next program but proposes an unsafe future
modification operator. The fixed kernel rejects the rewrite of `M` itself.
-/
def badModifierTarget : State := {
  kernelId := 0
  program := (lineage 1).program
  modifier := .wrapSucc
}

theorem badModifierProgramIsProposed :
    ProposedBy initial badModifierTarget := by
  rfl

theorem badModifierRejected :
    K initial badModifierTarget = false := by
  decide

theorem lineageStepAccepted (depth : Nat) :
    Accepted (lineage depth) (lineage (depth + 1)) := by
  apply checkerComplete
  simp [Admissible, Invariant, ModifierCertified, ProposedBy, M, lineage,
    evenValue, HasType, HasRewriteType, rewriteSafeBool, applyRewrite,
    observe, denote, eval] <;> omega

theorem nontrivialAccepted :
    Accepted initial (lineage 1) := by
  simpa [initial] using lineageStepAccepted 0

theorem modifierActuallyRewritten :
    M initial ≠ M (lineage 1) := by
  decide

theorem lineageModifierSemanticChanges (depth : Nat) :
    observe (applyRewrite (M (lineage depth)) (.lit 0)) ≠
      observe (applyRewrite (M (lineage (depth + 1))) (.lit 0)) := by
  simp [M, lineage, evenValue, applyRewrite, observe, denote, eval]
  omega

theorem lineageReachable :
    ∀ depth, Reach depth (lineage depth)
  | 0 => by
      simpa [initial] using (Reach.zero : Reach 0 initial)
  | depth + 1 => by
      simpa using
        Reach.succ (lineageReachable depth) (lineageStepAccepted depth)

-- Coupled opening ------------------------------------------------------------

def complexity (state : State) : Nat :=
  observe state.program

/-- Limb (B): the shared semantic coordinate is unbounded on reachable states. -/
theorem opening (bound : Nat) :
    ∃ depth state,
      Reach depth state ∧
      complexity state > bound := by
  refine ⟨bound, lineage bound, lineageReachable bound, ?_⟩
  simp [complexity, lineage, evenValue, observe, denote, eval]
  omega

def SemanticInvariant (value : Nat) : Prop :=
  value % 2 = 0

instance (value : Nat) : Decidable (SemanticInvariant value) := by
  unfold SemanticInvariant
  infer_instance

def SemanticComplexity (value : Nat) : Nat :=
  value

theorem invariantUsesSemanticCoordinate (state : State) :
    Invariant state ↔
      SemanticInvariant (observe state.program) := by
  rfl

theorem complexityUsesSemanticCoordinate (state : State) :
    complexity state =
      SemanticComplexity (observe state.program) := by
  rfl

/-- Every odd neighboring value is rejected by the same coordinate constraint. -/
theorem oddSemanticValuesViolate (value : Nat) :
    ¬ SemanticInvariant ((value + value) + 1) := by
  unfold SemanticInvariant
  omega

/-- Every lineage value satisfies the coupled semantic constraint. -/
theorem lineageSemanticValuesSatisfy (depth : Nat) :
    SemanticInvariant (SemanticComplexity (evenValue depth)) := by
  unfold SemanticInvariant SemanticComplexity evenValue
  omega

-- Surface 7: no protected/free product factorization -------------------------

/-- A minimal bijection structure, kept local to avoid importing a larger library. -/
structure Bijection (α β : Type) where
  toFun : α → β
  invFun : β → α
  leftInv : ∀ value, invFun (toFun value) = value
  rightInv : ∀ value, toFun (invFun value) = value

/--
A forbidden orthogonalization of the shared semantic coordinate: the invariant
reads only a protected factor while complexity reads only a free factor.
-/
structure OrthogonalDecomposition where
  protectedSpace : Type
  freeSpace : Type
  semanticBijection :
    Bijection Nat (protectedSpace × freeSpace)
  protectedInvariant : protectedSpace → Prop
  freeComplexity : freeSpace → Nat
  invariantFactors :
    ∀ value,
      SemanticInvariant value ↔
        protectedInvariant (semanticBijection.toFun value).1
  complexityFactors :
    ∀ value,
      SemanticComplexity value =
        freeComplexity (semanticBijection.toFun value).2

/--
Because complexity is the identity coordinate, fixing the free factor fixes the
entire semantic value. Surjectivity therefore collapses the protected factor.
-/
theorem orthogonalProtectedSubsingleton
    (decomposition : OrthogonalDecomposition) :
    ∀ left right : decomposition.protectedSpace,
      left = right := by
  intro left right
  let free : decomposition.freeSpace :=
    (decomposition.semanticBijection.toFun 0).2
  let leftValue : Nat :=
    decomposition.semanticBijection.invFun (left, free)
  let rightValue : Nat :=
    decomposition.semanticBijection.invFun (right, free)
  have leftPair :
      decomposition.semanticBijection.toFun leftValue =
        (left, free) := by
    exact decomposition.semanticBijection.rightInv (left, free)
  have rightPair :
      decomposition.semanticBijection.toFun rightValue =
        (right, free) := by
    exact decomposition.semanticBijection.rightInv (right, free)
  have leftFree :
      (decomposition.semanticBijection.toFun leftValue).2 =
        free := by
    rw [leftPair]
  have rightFree :
      (decomposition.semanticBijection.toFun rightValue).2 =
        free := by
    rw [rightPair]
  have leftProtected :
      (decomposition.semanticBijection.toFun leftValue).1 =
        left := by
    rw [leftPair]
  have rightProtected :
      (decomposition.semanticBijection.toFun rightValue).1 =
        right := by
    rw [rightPair]
  have leftMeasure :
      leftValue = decomposition.freeComplexity free := by
    calc
      leftValue = SemanticComplexity leftValue := by
        rfl
      _ = decomposition.freeComplexity
          (decomposition.semanticBijection.toFun leftValue).2 :=
        decomposition.complexityFactors leftValue
      _ = decomposition.freeComplexity free := by
        rw [leftFree]
  have rightMeasure :
      rightValue = decomposition.freeComplexity free := by
    calc
      rightValue = SemanticComplexity rightValue := by
        rfl
      _ = decomposition.freeComplexity
          (decomposition.semanticBijection.toFun rightValue).2 :=
        decomposition.complexityFactors rightValue
      _ = decomposition.freeComplexity free := by
        rw [rightFree]
  have valuesEqual : leftValue = rightValue :=
    leftMeasure.trans rightMeasure.symm
  have imagesEqual :
      decomposition.semanticBijection.toFun leftValue =
        decomposition.semanticBijection.toFun rightValue :=
    congrArg decomposition.semanticBijection.toFun valuesEqual
  calc
    left =
        (decomposition.semanticBijection.toFun leftValue).1 :=
      leftProtected.symm
    _ =
        (decomposition.semanticBijection.toFun rightValue).1 :=
      congrArg Prod.fst imagesEqual
    _ = right :=
      rightProtected

/-- Formal discharge of Surface 7 for the selected `I` and `C`. -/
theorem coordinateOrthogonalityImpossible :
    ¬ Nonempty OrthogonalDecomposition := by
  rintro ⟨decomposition⟩
  have protectedEqual :
      (decomposition.semanticBijection.toFun 0).1 =
        (decomposition.semanticBijection.toFun 1).1 :=
    orthogonalProtectedSubsingleton decomposition _ _
  have safeZero : SemanticInvariant 0 := by
    decide
  have unsafeOne : ¬ SemanticInvariant 1 := by
    decide
  have protectedZero :
      decomposition.protectedInvariant
        (decomposition.semanticBijection.toFun 0).1 :=
    (decomposition.invariantFactors 0).mp safeZero
  have protectedOne :
      decomposition.protectedInvariant
        (decomposition.semanticBijection.toFun 1).1 := by
    rw [← protectedEqual]
    exact protectedZero
  exact unsafeOne
    ((decomposition.invariantFactors 1).mpr protectedOne)

-- Fork B: effective reachability has a fixed finite generator ----------------

/--
A fixed program replays a finite reverse-chronological path certificate. The
program does not change; longer inputs carry longer candidate paths.
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
    ∃ certificate,
      replayCertificates certificate = some state := by
  induction reachable with
  | zero =>
      exact ⟨[], rfl⟩
  | succ previous accepted inductionHypothesis =>
      rename_i stepDepth stepSource stepTarget
      rcases inductionHypothesis with ⟨certificate, replayed⟩
      refine ⟨stepTarget :: certificate, ?_⟩
      change K stepSource stepTarget = true at accepted
      simp [replayCertificates, replayed, accepted]

/-- Finite generator syntax containing the decisive replay interpreter. -/
inductive GeneratorCode where
  | reject
  | replay
  | fallback : GeneratorCode → GeneratorCode → GeneratorCode
  deriving DecidableEq, Repr

def runGenerator : GeneratorCode → List State → Option State
  | .reject, _ => none
  | .replay, certificate => replayCertificates certificate
  | .fallback first second, certificate =>
      match runGenerator first certificate with
      | some state => some state
      | none => runGenerator second certificate

def generatorDescriptionLength : GeneratorCode → Nat
  | .reject => 1
  | .replay => 1
  | .fallback first second =>
      1 + generatorDescriptionLength first +
        generatorDescriptionLength second

theorem replayGeneratorHasBoundedDescription :
    generatorDescriptionLength .replay = 1 := by
  rfl

theorem fixedReplayGeneratorCovers
    {depth : Nat} {state : State}
    (reachable : Reach depth state) :
    ∃ certificate,
      runGenerator .replay certificate = some state := by
  simpa [runGenerator] using
    reachableHasReplayCertificate reachable

def EscapesGenerator
    (generator : GeneratorCode)
    (state : State) : Prop :=
  ∀ certificate,
    runGenerator generator certificate ≠ some state

/--
The directive's `GEN` alternative, strengthened so the state escaping each
fixed generator must also witness opening above every requested bound.
-/
def AntiGenerator : Prop :=
  ∀ generator bound,
    ∃ depth state,
      Reach depth state ∧
      complexity state > bound ∧
      EscapesGenerator generator state

/-- Fork B lands: one bounded-description replay program covers every reachable state. -/
theorem antiGeneratorImpossible :
    ¬ AntiGenerator := by
  intro antiGenerator
  rcases antiGenerator .replay 0 with
    ⟨depth, state, reachable, larger, escaped⟩
  rcases fixedReplayGeneratorCovers reachable with
    ⟨certificate, generated⟩
  exact escaped certificate generated

-- Revised target and incompatibility ----------------------------------------

def ClosureProperty : Prop :=
  ∀ depth state,
    Reach depth state → Invariant state

def OpeningProperty : Prop :=
  ∀ bound,
    ∃ depth state,
      Reach depth state ∧
      complexity state > bound

def CouplingProperty : Prop :=
  ¬ Nonempty OrthogonalDecomposition

theorem closurePropertyHolds :
    ClosureProperty := by
  intro depth state reachable
  exact closure reachable

theorem openingPropertyHolds :
    OpeningProperty := by
  intro bound
  exact opening bound

theorem couplingPropertyHolds :
    CouplingProperty :=
  coordinateOrthogonalityImpossible

/-- The three non-`GEN` limbs hold simultaneously in the rebuilt model. -/
theorem targetTheorem :
    ClosureProperty ∧
      OpeningProperty ∧
      CouplingProperty := by
  exact
    ⟨closurePropertyHolds,
      openingPropertyHolds,
      couplingPropertyHolds⟩

/-- The pre-registered Fork B, isolated as a machine-checkable statement. -/
theorem forkB :
    (ClosureProperty ∧
      OpeningProperty ∧
      CouplingProperty) ∧
      ¬ AntiGenerator := by
  exact ⟨targetTheorem, antiGeneratorImpossible⟩

/--
The revised four-limb target is incompatible in this model. The contradiction
is direct: `GEN` demands a reachable state outside the range of the fixed replay
generator, while `reachableHasReplayCertificate` places every reachable state
inside that range.
-/
theorem revisedTargetImpossible :
    ¬ (ClosureProperty ∧
      OpeningProperty ∧
      CouplingProperty ∧
      AntiGenerator) := by
  intro target
  exact antiGeneratorImpossible target.2.2.2

end CrispOpen
