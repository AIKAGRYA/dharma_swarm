---
title: NAGA-IR Language Womb Research Wiki
type: research_wiki
status: high_priority_seed
priority: HIGH
created: 2026-07-05
source_branch: telos_titanium/naga_ir_language_womb_seed
source_commit: 0ce104896a38
related:
  - docs/plans/2026-07-05-karpathy-llm-wiki-system-integration.md
  - BRAIN.md
tags:
  - naga-ir
  - language-womb
  - epistemic-types
  - provenance
  - agent-safety
---

# NAGA-IR Language Womb Research Wiki

## Thesis

The NAGA-IR language-womb branch is only worth separating from ordinary
governance if it changes the semantics of programs. If it merely emits receipts
after Python code runs, it should fold back into governance. The real delta is a
language where epistemic modality, authority, provenance, and outbound-action
capability become typechecker and evaluator semantics.

Canonical litmus:

```text
Claim[Attested_by, womb] cannot satisfy Claim[Proven_by, core]
```

without an explicit promotion proof and receipt. That property should be
checked before execution, not reconstructed after execution.

## Prior Art Map

### LLM Programming Languages

LMQL shows that prompting can be treated as programming: text prompting plus
scripting, constraints over model output, and inference procedures generated
from control flow and constraints. Its relevance is output-shape and
interaction-control semantics, but not authority semantics.

DSPy abstracts LM pipelines as declarative text-transformation graphs and uses
a compiler to optimize them against metrics. Its relevance is compilation and
optimization of agent/LM pipelines, but it treats correctness primarily as a
metric target, not as an authority type.

SGLang splits structured language model programs into a frontend language and a
runtime, with execution optimizations for multi-call, structured-output, RAG,
and agent-control workloads. Its relevance is runtime design: if NAGA becomes a
language, it needs an execution substrate, not only a schema.

SPL treats the context window as a constrained resource with declarative budget
management, optimizer behavior, EXPLAIN-style transparency, native RAG, memory,
model routing, and benchmark persistence. Its relevance is that context,
retrieval, memory, and model choice can be part of a language rather than hidden
application glue.

Design implication: NAGA should not compete as "another prompt DSL." Its unique
surface should be authority-aware claims, promotion proofs, and capability
effects. LMQL/DSPy/SGLang/SPL are substrate lessons, not the differentiator.

### Verification Languages And Proof Assistants

Lean demonstrates the strongest end of proof-carrying semantics: claims become
objects in a formal environment, and proof checking is part of the workflow.
Its lesson is that serious trust requires machine-checkable proof terms or
kernel-checked derivations, not persuasive prose.

Dafny demonstrates verification-aware programming: specifications sit in the
program and a static verifier checks implementation against those specs. Its
lesson is ergonomic: developers can tolerate formal constraints when they live
close to code and compile into ordinary environments.

Koka makes effects explicit in types. This is the clearest analogy for NAGA:
authority, evidence use, memory reads, external communication, and identity
actions should be effects tracked by the type system.

Unison uses content-addressed code and abilities. Its lesson for NAGA is that
identity by hash and explicit abilities can make dependency/provenance drift
visible instead of name-based and ambient.

Design implication: NAGA should be a small authority/evidence calculus first,
with possible embeddings into Python/TypeScript later. It should not start as a
large general-purpose language.

### Evidence Tracing And Provenance

Recent agent provenance work converges on a hard point: final-answer accuracy is
not enough. Agent executions need typed provenance graphs that explain tool
use, memory influence, evidence support, recovery, and failure origin.

PROV-AGENT extends W3C PROV toward agentic workflows and uses MCP/data
observability to capture prompts, responses, decisions, and workflow context.
This is close to NAGA's receipt mesh layer, but still mostly observational.

ProvenAI separates answer correctness, citation fidelity, and actual
per-document influence. That distinction is critical: a cited source may not
have influenced the output, and an uncited source may have shifted it.

Design implication: NAGA receipts should distinguish:

- evidence retrieved
- evidence cited
- evidence causally influential
- evidence promoted
- authority accepted
- authority refused

Anything less will overstate trust.

### Paraconsistent And Modal Logic

The language-womb needs a logic that can retain contradiction without collapse.
Belnap-Dunn style four-valued logic is a useful reference point: true, false,
both, neither. NAGA does not have to adopt that exact logic, but it needs a way
to type disputed claims without converting them into either accepted truth or
garbage.

Modal logic supplies the shape for "claimed by," "observed by," "attested by,"
"verified by," "proven by," and "authorized by." The core move is to stop
treating these as metadata strings and make them type-level modalities.

Design implication: contradiction and uncertainty are not exceptions. They are
first-class states with promotion rules.

### Moltbook Boundary

Moltbook is relevant because it is an agent-only social environment where
instructions, norms, identities, and agent-to-agent influence are live data. It
is also a prompt-injection-rich external action surface.

The OpenClaw Moltbook study found routine action-inducing instruction sharing
and selective norm-enforcing replies among agents. The Observatory Archive
paper documents a large passive dataset of posts, comments, profiles,
communities, platform time series, and word-frequency trends.

Design implication: NAGA may ingest public Moltbook papers, public docs, and
public datasets as read-only evidence. Credentialed login, posting, commenting,
voting, live feed ingestion, or acting as a named account requires explicit
operator authorization, account-owner authorization, sandboxing, and an
outbound-action block.

## Proposed Core Semantics

### Claim Type

```text
Claim[
  modality,
  authority,
  evidence_lineage,
  evaluator_context,
  promotion_state
]
```

Example modalities:

- `Observed_by`
- `Claimed_by`
- `Attested_by`
- `Verified_by`
- `Proven_by`
- `Authorized_by`

Example authorities:

- `womb`
- `agent`
- `council`
- `operator`
- `core`
- `external_source`

Example promotion states:

- `raw`
- `candidate`
- `staged`
- `trusted`
- `disputed`
- `deprecated`

### Authority Subtyping

Authority is not monotonic by vibes. `Claim[Attested_by, womb]` is not a
subtype of `Claim[Proven_by, core]`. Promotion requires a proof object:

```text
promote : Claim[Attested_by, womb, L, C, staged]
       -> PromotionProof[L, C, gate_set]
       -> Claim[Verified_by, core, L, C, trusted]
```

The evaluator rejects authority substitution unless the promotion proof is
present and valid.

### Effects

NAGA should track at least these effects:

- `reads_memory`
- `retrieves_external`
- `uses_model`
- `uses_tool`
- `writes_receipt`
- `stages_claim`
- `promotes_claim`
- `contacts_external`
- `acts_as_identity`
- `spends_money`

High-risk effects such as `contacts_external`, `acts_as_identity`, and
`spends_money` require explicit operator capability grants. Moltbook login or
posting lives behind these effects.

### Evaluator Rule

The evaluator should produce receipts as a consequence of checked semantics,
not as a substitute for checked semantics. Receipt emission proves that a run
happened. It does not prove that the program was allowed to conflate authority
levels.

## Minimal Language Womb Stack

1. Surface syntax: small, readable claim/effect syntax.
2. Core IR: normalized claim/effect/promotion terms.
3. Typechecker: authority/modal/effect constraints.
4. Evaluator: executes only well-typed terms.
5. Receipt exporter: emits NAGA-IR receipts for accepted transitions.
6. Witness mesh: records non-authoritative observations and disagreements.
7. Interop bridge: calls existing governance/Python code only through typed
   capabilities.

## First High-Priority Build Slice

1. Define the core `Claim[...]` grammar and normalized IR.
2. Implement a checker that rejects authority substitution without a
   `PromotionProof`.
3. Add effect labels for memory, external retrieval, receipt writing, and
   external action.
4. Add a fixture showing Moltbook public-paper ingestion is allowed while login
   or posting is blocked without capability.
5. Export a NAGA-IR receipt only after the checker approves the transition.

## Non-Goals

- Do not build a full programming language first.
- Do not add credentialed Moltbook actions.
- Do not import live Moltbook feeds by default.
- Do not treat citations as evidence influence.
- Do not let post-hoc receipts compensate for untyped authority escalation.

## Sources

- LMQL: https://arxiv.org/abs/2212.06094
- DSPy: https://arxiv.org/abs/2310.03714
- SGLang: https://arxiv.org/abs/2312.07104
- SPL: https://arxiv.org/abs/2602.21257
- Agent evidence tracing survey: https://arxiv.org/abs/2606.04990
- PROV-AGENT: https://arxiv.org/abs/2508.02866
- ProvenAI: https://arxiv.org/abs/2606.26449
- Lean: https://lean-lang.org/
- Dafny: https://dafny.org/
- Koka: https://koka-lang.github.io/koka/doc/index.html
- Unison: https://www.unison-lang.org/
- Moltbook OpenClaw study: https://arxiv.org/abs/2602.02625
- Moltbook Observatory Archive: https://arxiv.org/abs/2605.13860

