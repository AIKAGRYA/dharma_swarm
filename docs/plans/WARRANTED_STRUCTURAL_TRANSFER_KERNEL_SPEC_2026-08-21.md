# Warranted Structural Transfer — kernel build spec (v0)

**Date:** 2026-08-21
**Status:** SPEC / BRAINSTORM companion to PR #1431. Confers no implementation
authority, no canon change, no active-track mutation. The portfolio is at its
WIP cap (10/10 per `docs/governance/ACTIVE_TRACK.yaml`); building anything in
this spec requires a portfolio slot first. This document exists so the kill
test and any later build have a fixed, criticizable target.
**Companion:** the adversarial review on PR #1431
(refutations R1–R9, proposals P1–P6) is normative input; where this spec and
that review disagree, flag it — do not silently pick one.

## 0. The one thing

Build the **deterministic claim kernel** and nothing else first: a small,
LLM-free, side-effect-free library that takes two typed situations, a mapping,
and a set of claims, and returns computed statuses, typed residue, gather
obligations, and a canonical content-addressed WarrantRecord.

Everything else — pramana projection, shakti evidence, vibe-halt falsification,
Foundry evolution, the adjudication canvas — is a thin adapter around that
kernel. If the kernel is right, every integration is one small file. If the
kernel is wrong, no integration saves it.

## 1. Decisions

### D1 — The central object is the WarrantRecord, not the graph

The role graph is an *input representation*. The durable, signed, versioned,
sellable artifact is the warrant. Storage, digests, adjudication chains, and
promotion all key off the warrant, never off a graph store. This is what keeps
the build from becoming "another knowledge graph" (PR #1431 §13 non-goal; the
MemoryKernel surface census already tracks KNOWLEDGE_GRAPH and INTENT_GRAPH
surfaces — `dharma_swarm/memory_kernel/atoms.py:32-33`).

### D2 — A situation is a typed fact base; the graph is a view

Answer to "is it a graph? is it a role graph?": the machine representation is a
**typed fact base** — the graph is how humans see it, facts are how the kernel
reasons over it.

```text
role(id, type)                      # nodes
rel(type, subject, object)          # typed edges
axiom: Horn rule over predicates    # what the situation guarantees
observation: ground fact + provenance + valid_until   # what was witnessed
```

The two-pane graph canvas renders this; the kernel never sees a canvas. No
graph database is built or bought. Persisted situations register in the
MemoryKernel surface census (`dharma_swarm/memory_kernel/atoms.py:1-5`) —
an unregistered store is the second-truth-store failure PR #1431 §12.6 fears.

### D3 — Claim language v0: Datalog, stratified negation, no function symbols

The single decision the concept PR omitted, and the one that decides whether
gather obligations are mechanical or LLM wish lists (review R5). v0 grammar:

```text
claim := atom (',' atom)*
atom  := pred '(' term (',' term)* ')' | '!' atom     # stratified negation only
term  := role_id | constant                            # no function symbols
arity <= 4
```

This fragment is decidable, PTIME-evaluable, and sufficient for the Wedge A
claim family: authority ("who can approve X"), ordering ("approval precedes
irreversible effect"), reachability ("output flows to uncontrolled channel"),
capability containment. Widening the language later is allowed only with a
demonstrated claim that cannot be expressed, recorded in this file's changelog.

### D4 — Statuses are computed, never authored

Per review R1/P1. For each claim φ, translated under mapping M to φ′:

```text
1. translation fails (roles outside dom(M))
     -> residue-blocked; obligation: extend/justify M
2. φ′ derivable from B's facts + axioms
     -> support path: derived (proof tree recorded)
3. an explicit transfer rule licenses φ′, given a recorded proof of φ in A
     -> support path: transferred(rule_id)
4. B derives ¬φ′, or a recorded counterexample is ADMISSIBLE
   (consistent with B's stated facts and axioms)
     -> refuted (counterexample retained — this is deliverable data)
5. otherwise
     -> unprovable-from-here; obligations = the open leaves of the failed
        proof tree, typed by predicate (missing observation / axiom / test)
```

All succeeding support paths are recorded (over-determination is robustness
information); a display status may summarize with priority
`refuted > derived > transferred > unprovable-from-here`.
`evidence_valid_until` = min over supporting observations' validity windows;
an expired window flips the display status to `stale` without re-adjudication.
An INADMISSIBLE counterexample (one exploiting something B's model is silent
on) does not refute; it downgrades to `unprovable-from-here` and emits the
obligation "pin down this axiom in B" — admissibility is checked mechanically
against B's axiom set, never judged by a model.

### D5 — Residue has three computed classes

Per review R7. Set subtraction over nodes is not a graph-valid notion.

```text
nodal      : roles outside dom(M) / range(M)
relational : rel(t, x, y) with x, y mapped but no type-corresponding
             rel(t', M(x), M(y)) in B          # the non-commuting edges
axiomatic  : axioms of A used in any accepted claim's derivation whose
             translation is not entailed by B  # THE retest list
```

Axiomatic residue is the product. "Assurance in A depended on axiom α; α is
not established in B" is precisely what a buyer must retest before deploying.

### D6 — The epistemic taxonomy is a projection of pramana, not a rival

Per review R2. `dharma_swarm/pramana.py:1-15` is the existing epistemic SSOT;
upamana (comparison) already carries lower weight (0.15) than pratyaksha
(0.30) — the codebase encoded "transfer is weaker than derivation" before this
proposal existed. The kernel's statuses project onto it in an adapter:
`derived` → pratyaksha/anumana/arthapatti-supported; `transferred` →
upamana-only; `refuted` → blocking failure. The kernel itself carries no
confidence floats (D9); weights live in the adapter.

### D7 — A transfer warrant emits evidence; it never holds authority

Per review R3. The name "Warrant" is taken by the action-warrant path
(`dharma_swarm/shakti_warrant.py:25-31`, `WarrantVerdict`), and that collision
points at the correct wiring: the kernel's output is consumed as
`WarrantEvidence` ("evidence grounding a warrant in something outside intent
text", `dharma_swarm/shakti_warrant.py:45-50`) by the existing action path.
Reasoning/authority separation becomes a type-level fact. Working internal
name for the kernel artifact: **TransferRecord** (external marketing names are
out of scope; ADR-008 grammar review required before any code lands).

### D8 — LLMs sit outside the trust boundary

The kernel makes no model calls, ever. Models may *propose* facts, mappings,
and claims; every proposal enters as unadjudicated input and only
human-adjudicated or receipt-backed observations count toward status
computation. This is the containment for "formalization is where all the error
enters": the kernel is deterministic and dumb; the assist layer is smart and
untrusted. Mirrors the promotion discipline in
`dharma_swarm/memory_kernel/promotion_gate.py:1-4`.

### D9 — Determinism and canonical form are non-negotiable

The warrant digest is meaningless without them (review of 2026-08-21, item 4).

- Interned symbols: every string interned to a u32 in first-seen-after-sort
  order; the symbol table is part of the canonical serialization.
- Facts are fixed-width tuples `(pred: u32, args: [u32; 4])`; iteration is
  always over sorted fact sets; evaluation is semi-naive with a worklist —
  bit-identical output across runs and platforms.
- **No floating point in the kernel.** Integers and strings only. Confidence
  weights are adapter concerns (D6).
- Canonical serialization: UTF-8, sorted keys, no insignificant whitespace —
  behaviorally pinned to `canonical_json` in
  `dharma_swarm/memory_kernel/write_receipts.py` by a shared golden-vector
  test (the package cannot import it: D11 forbids runtime imports).
- Digests: SHA-256 over canonical bytes. Warrant digest covers
  `(schema_version, engine_version, ruleset_version, a_digest, b_digest,
  mapping_digest, claims_digest, residue_digest, obligations_digest,
  adjudication_parent_digest)`.

### D10 — The C question: write it C-portable, not in C

Direct answer to "can we write it in C?": **not first, and not for speed we
don't yet need — but the kernel is specified so that a C core can drop in
later without a redesign.**

Why not now: the repo is Python 3.11 + Pydantic 2 (`CLAUDE.md` §Architecture);
every integration surface (pramana, shakti_warrant, dharma_corpus, memory
kernel) is a Pydantic model; v0 situations are tens-to-hundreds of roles,
where Datalog evaluation is sub-millisecond in pure Python; and a native core
adds FFI, toolchain, and memory-safety review cost to `hermetic.yml` for zero
measured benefit. A memory-corruption bug in a *truth-warrant* engine is a
brand-ending irony — which is also why, when a native core is justified, the
in-repo precedent points to Rust (vibe-halt's engine) or Go (`tools/*_go/`)
before C.

What we do instead — the C-programmer discipline without the C:

- data layout already C-compatible: u32 symbols, fixed-arity fact tuples,
  flat arrays, no recursion in the eval hot path, typed error results instead
  of exceptions crossing the kernel boundary;
- frozen wire format + **conformance vectors** (`tests/vectors/*.json`): input
  situations/mappings/claims and the exact expected warrant bytes. Any future
  native core (Rust preferred; C admissible) must pass the identical battery
  bit-for-bit before it replaces the reference implementation;
- rewrite trigger: a profiled kernel evaluation exceeding an agreed budget on
  a real corpus (thousands of roles), not aesthetics.

The reference implementation in Python is therefore also the executable spec.

### D11 — Placement and import direction

Standalone package with **zero imports from organism runtime** (pattern:
`packages/telos-kernel/`, `packages/titanium-verify/`). `dharma_swarm/` may
import the package; never the reverse. Adapters (D6, D7, census registration)
live inside `dharma_swarm/` and are Phase 1. Runtime warrant stores live under
`~/.dharma/transfer/` as append-only JSONL — runtime receipts never enter git
(`CLAUDE.md` §Hard rules).

## 2. Module map (Phase 0 — the whole build)

```text
transfer_kernel/
  symbols.py    # string <-> u32 interning, deterministic assignment
  situation.py  # roles, relations, axioms, observations, validity, digest
  claims.py     # D3 grammar: parse, validate, stratification check
  eval.py       # semi-naive Datalog eval; proof trees; open leaves
  mapping.py    # type correspondence, role map, transfer rules, translation
  status.py     # D4 lattice; admissibility routing of counterexamples
  residue.py    # D5 three classes
  canon.py      # canonical bytes + SHA-256 digests (golden-pinned)
  warrant.py    # TransferRecord assembly; adjudication version chain
```

Nine small modules, each with a matching `tests/test_transfer_*.py`.
Estimated 1,500–2,500 lines plus tests. Nothing async, nothing stored,
nothing networked, nothing modeled.

## 3. The kill test ships with Phase 0

The kernel is built *together with* its falsifier (review P3): a retrospective
harness of 5–10 historical A→B transfer decisions with known outcomes —
public agent-deployment postmortems plus this repo's own model/tool/permission
swaps — encoded manually as fixtures.

**Metric:** for each case, did `refuted` or axiomatic residue flag the thing
that actually bit? **KILL** if missed in ≥ half the cases.
**Arjuna boundary:** repo-internal cases are rehearsal only; the promoting
receipt (PR #1431 Triangulation item 4) must remain external.

The later live pilot (PR #1431 §11) additionally requires a baseline arm — the
same decision via a plain memo — per review R8; a zero decision-delta over the
memo is a KILL condition.

## 4. Phases

```text
Phase 0  kernel + conformance vectors + retrospective harness   (needs a slot)
Phase 1  adapters: pramana projection, WarrantEvidence emitter,
         census registration, signing, ~/.dharma storage         (gated on 3)
Phase 2  vibe-halt property compiler (role-graph claim ->
         executable trace property), Foundry corpus, canvas      (gated, large)
```

Phase 2's property compiler is the named missing artifact between this kernel
and vibe-halt (review R6): today's bridge is engine-liveness calibration only
(`dharma_swarm/vibe_halt_observer.py:1-5,24`). Until it exists, every claim in
a warrant carries `falsifier_class: unchallenged` — overstating adversarial
coverage is the exact sin the vibe-halt observer's own docstring refuses.

## 5. Non-goals (v0)

No UI or canvas. No LLM calls in the kernel. No graph database. No new
epistemic taxonomy (D6). No new truth store outside the census (D2). No
mappings-of-mappings / concept families (earn it after ≥ 20 adjudicated real
warrants). No customer platform. No claim that market demand exists.

## 6. Changelog

- 2026-08-21 — initial spec, distilled from PR #1431 and its adversarial
  review; decisions D1–D11.
