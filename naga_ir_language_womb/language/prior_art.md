# Prior Art Gate

Status: initial research map, 2026-07-05. This is not a design decision.
It is a gate: no substantial language construct should be added until its
nearest prior art is identified and the remaining delta is stated explicitly.

## Highest Goal

The language womb is not another receipt emitter and not another governance
layer. Those already exist in `dharma_swarm`.

The highest goal is an AI-native programming language where model outputs,
retrieval results, experiments, human review, formal proofs, authority scopes,
and uncertainty are values with static semantics. A program should fail before
execution if it tries to feed an `Attested_by` claim into a `Proven_by` slot, or
if it moves a womb-local claim into core authority without an explicit coercion
receipt.

If the womb only records receipts after Python code runs, it is redundant. The
new contribution must be typechecking and evaluation rules for epistemic
dependency, not more logging.

Confidence: 92/100. This is the cleanest non-redundant target relative to the
runtime spine and governance layers already present in `dharma_swarm`.

## Research Protocol

Every future language feature must start with a prior-art note that includes:

- at least two primary sources or official project references;
- what the prior art already solves;
- what remains unsolved for this womb;
- whether the feature belongs in the language, the runtime spine, governance, or
  ordinary experiment tooling;
- a proposed `naga_ir_language_womb.prior_art_review.v1` receipt once that
  receipt writer exists.

The default answer should be "do not add a language feature" unless the feature
creates a compile-time or evaluator-level guarantee that runtime receipts alone
cannot provide.

## Prior Art Map

### Language Model Programming

**LMQL** frames prompting as programming: text prompting plus scripting,
constraints over model output, and optimized inference plans. It is close to the
surface syntax problem, but it does not make evidence grade or authority part of
the type system.

Source: <https://arxiv.org/abs/2212.06094>

**DSPy** treats language-model pipelines as declarative modules that can be
compiled and optimized against metrics. It is strong prior art for prompt
pipeline optimization, not for epistemic modality or cross-fragment authority.

Source: <https://arxiv.org/abs/2310.03714>

**SGLang** provides a frontend language and efficient runtime for structured
language-model programs, including generation primitives, parallel control, and
runtime optimizations. It informs execution strategy, but it is not an evidence
calculus.

Source: <https://arxiv.org/abs/2312.07104>

**Structured Prompt Language** treats context windows as managed resources and
adds SQL-like prompt orchestration. It overlaps with retrieval and context
budgeting, not with type-level claim strength.

Source: <https://arxiv.org/abs/2602.21257>

Implication: the womb should not compete with LMQL, DSPy, SGLang, SPL, guidance,
or constrained-generation libraries at the prompt-orchestration layer. It should
consume them as backends if useful.

### Evidence, Provenance, And Claim Support

**PaperTrail** decomposes LLM scholarly answers and source documents into
claim/evidence relationships. It is highly relevant to corpus-backed research
review, but it is an interface and evaluation workflow, not a programming
language semantics.

Source: <https://arxiv.org/abs/2602.21045>

**ProvenAI** separates answer correctness, citation fidelity, and document
influence. This matters because a citation can be present without being the
actual causal support for an answer. The womb should treat "cited" and
"influential" as distinct evidence predicates.

Source: <https://arxiv.org/abs/2606.26449>

**Evidence tracing and execution provenance for LLM agents** surveys trace links
among retrieved evidence, tool outputs, memory, intermediate claims, actions, and
final answers. This is direct prior art for experiment receipts, but it still
does not by itself typecheck the downstream use of a claim.

Source: <https://arxiv.org/abs/2606.04990>

Implication: evidence lineage belongs in the language core only when dependency
on that lineage affects whether a program typechecks or evaluates.

### Formal Proof And Verification-Aware Languages

**Lean** is an open-source programming language and proof assistant for formally
verified code and mathematics. Lean's minimal trusted kernel and extensible
metaprogramming are prior art for `Proven_by` claims, not for lower-grade model
attestations.

Source: <https://lean-lang.org/>

**Dafny** is a verification-aware language with specifications,
preconditions/postconditions, invariants, and SMT-backed verification. It is
prior art for code plus proof obligations. Recent agentic Dafny work is also
relevant to model-generated proofs.

Sources: <https://dafny.org/>, <https://arxiv.org/abs/2606.32007>

**Proof-carrying code** shows that executable code can carry a proof checked
against a host policy before execution. This is a direct ancestor for the
`Proven_by` lane.

Source: <https://www.cs.cmu.edu/~necula/Papers/pcc-oakland96.pdf>

Implication: the womb should not invent formal proof checking. `Proven_by`
should delegate to Lean/Dafny/Rocq/Isabelle-style artifacts and only define how
those proofs compose with weaker AI-native claims.

### Type, Effect, And Capability Systems

**Koka** is a functional language with effect types and handlers. It shows how a
type can track not only a value but what computation may do while producing it.

Source: <https://koka-lang.github.io/koka/doc/index.html>

**Unison** tracks abilities such as `IO` and `Exception`, and names code by hash
rather than unstable textual names. Its ability system and content-addressed
codebase are both relevant.

Source: <https://www.unison-lang.org/>

Implication: the likely language shape is a type-and-effect system where
epistemic modality is an effect or indexed type:

```text
Claim[Attested_by, womb]
Claim[Tested_by, womb]
Claim[Proven_by, core]
```

Promotion is not assignment. It is an effectful proof or review operation with
an explicit receipt.

### Probabilistic And Paraconsistent Semantics

**Probabilistic programming** systems such as Stan, Anglican, Church, and ProbLog
make uncertainty executable. They are prior art for probabilistic inference, but
probability is not the same thing as authority. A claim may be highly probable
and still not be allowed to control core code.

Sources: <https://mc-stan.org/>, <https://arxiv.org/abs/1608.05263>,
<https://dtai.cs.kuleuven.be/problog/>

**Belnap-Dunn four-valued logic** is prior art for incomplete and contradictory
information states. It supports the governance layer's need to represent both
conflict and absence without explosion.

Sources: <https://plato.stanford.edu/entries/logic-paraconsistent/>,
<https://arxiv.org/abs/2503.20679>

Implication: the womb should separate at least three axes that ordinary language
models blur: truth value, probability/confidence, and admissible authority.

### Database And Datalog Provenance

Semiring provenance tracks how query results depend on input facts and can
generalize trust, cost, and likelihood annotations. Recent work on determination
provenance extends this toward ambiguous outcomes and layered commitments.

Sources: <https://arxiv.org/abs/2202.10766>,
<https://arxiv.org/abs/2606.10270>

Implication: provenance algebra is prior art for claim dependency graphs. The
womb's novelty should be typed use of those graphs under model-generated,
human-reviewed, experiment-tested, and proof-checked modalities.

### Agent Social Networks And Moltbook

Moltbook is useful as a field site for agent discourse, instruction sharing,
norm enforcement, and prompt-injection risk. It is not authoritative prior art
for programming-language design.

Primary research sources identify both interesting social dynamics and serious
safety concerns:

- OpenClaw agents on Moltbook show routine action-inducing instruction sharing.
  Source: <https://arxiv.org/abs/2602.02625>
- Larger studies report shallow reciprocity, prompt/social-engineering risk,
  and "form without function" social behavior.
  Sources: <https://arxiv.org/abs/2602.13284>,
  <https://arxiv.org/abs/2604.13052>
- The Moltbook Observatory Archive offers a passive dataset for analysis without
  logging in or posting as an agent.
  Source: <https://arxiv.org/abs/2605.13860>

Access policy:

- Allowed now: public papers, public documentation, public datasets, and
  read-only analysis of exported/archive data.
- Not allowed by default: logging in as `rushabev`, `hermes`, or any other
  agent; posting; commenting; voting; following; importing live feed text into a
  tool-enabled agent loop.
- Required before credentialed access: explicit operator approval, account owner
  authorization, a read-only/sandboxed token if possible, outbound-action block,
  prompt-injection quarantine, and a receipt naming the account, scope, and
  allowed actions.

Confidence: 95/100. Credentialed Moltbook engagement is a higher-risk external
action surface and should not be part of language prior-art research unless the
research question specifically requires live agent-social observation.

## Candidate Delta

The tentative delta, subject to deeper review, is:

1. Model calls are typed effects, not just runtime events.
2. Claims carry modality and authority in their type, not only in receipt
   metadata.
3. Composition rules prevent epistemic substitution, e.g. `Attested_by` cannot
   satisfy `Tested_by` or `Proven_by` requirements.
4. Promotion is an explicit program transformation requiring evidence and a
   receipt.
5. Evaluation is Lyapunov-aware: a program that increases governance risk must
   carry a valid predecessor/coercion explanation.

This delta is plausible but not proven. The next research pass should falsify it
against type-and-effect systems, proof-carrying code, Datalog provenance, and
LLM programming languages before any larger grammar is designed.
