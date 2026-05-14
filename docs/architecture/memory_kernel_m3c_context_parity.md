# MemoryKernel M3C Context Parity

Date: 2026-05-13
Status: read-only parity harness and 60->80 roadmap

## Purpose

M3C turns the M3B safety eval into a parity harness.  The goal is to measure
whether MemoryKernel atoms can represent the same operational context currently
served by the legacy context lane without replacing that lane.

M3C is not live context replacement.  It does not inject MemoryKernel atoms into
prompts, route atoms through `ContextCompiler`, change `AgentRunner`, write
retrieval feedback, mutate Chetana, or change canon.  It produces shadow reports
that humans and later gates can inspect before any runtime wiring is considered.

```text
Legacy Current Context Lane
  rendered current-context text
  redaction and safety scan
  warnings only

MemoryKernel Atom Lane
  structured atoms
  read-only context pack preview
  stricter admission policy

M3C Parity Harness
  compares behavior and safety signals
  records admitted and omitted atoms
  reports gaps without merging lanes
```

## Locked Decisions

- M3C is a read-only parity harness, not a prompt or context replacement.
- Legacy current context and MemoryKernel atoms remain separate lanes.
- Current context text is evaluated as legacy output; findings there are
  warnings unless a future gate explicitly changes the contract.
- MemoryKernel atoms are evaluated as candidate structured context; unsafe
  admissions are hard failures.
- Reports may compare the two lanes, but they must not merge, promote, or
  write back from either lane.
- MemoryKernel atoms remain evidence with provenance and risk labels, not canon.
- Projection stores remain projections.  They cannot become higher-authority just
  because a parity report includes them.

## Safety Contract

M3C must not:

- inject prompt context or alter prompt construction
- wire MemoryKernel atoms into `context.py`, `ContextCompiler`, or `AgentRunner`
- write retrieval feedback, scores, preference records, or success markers
- promote, archive, supersede, reject, or delete memory atoms
- mutate Chetana, canon, ontology, wiki, vector stores, runtime state, logs, or
  KnowledgeOps source data
- serialize raw legacy context text, raw bounded atom content, local paths, or
  secret-like markers in reports

The harness may read explicit fixture or operator-supplied inputs.  Live memory
surfaces must remain opt-in and bounded.

## Required Metrics

M3C reports should make parity and safety visible without implying acceptance.
The required metric families are:

- Hard failures: MemoryKernel pack output leaks local path refs; serialized eval
  artifacts leak local path refs; projections are admitted without override;
  rejected or superseded atoms are admitted; high-risk atoms are admitted without
  override; content appears when `include_content=false`.
- Warnings: legacy current context contains local path refs, secret-like markers,
  weak provenance, risky text, or other unsafe patterns; MemoryKernel omits all
  candidates by conservative policy; no MemoryKernel surfaces are configured;
  candidate or display limits truncate review; content exists but is not
  included.
- Redaction: path-like refs, local source paths, secret-like markers, and long
  refs are redacted to bounded stable handles or redacted previews before report
  serialization.
- Admitted and omitted atoms: `candidate_count`, `admitted_count`,
  `omitted_count`, `candidate_truncated`, `total_selected_chars`, per-atom
  selection reasons, per-atom omission reasons, and pack warnings.
- Projection handling: projection surfaces, projection lanes, and atoms with
  `projection_of` are omitted by default and become hard failures if admitted
  without an explicit override.
- High-risk handling: high or critical canon/PII risk atoms are omitted by
  default and become hard failures if admitted without an explicit override.
- Rejected and superseded handling: rejected and superseded atoms are omitted by
  default and become hard failures if admitted.
- Truncation and budget behavior: candidate caps, admitted-atom caps,
  per-atom character caps, total character caps, and display caps are reported
  separately so a bounded sample cannot masquerade as a complete review.

## Parity Interpretation

Parity is not "the two lanes render the same text."  Current context is a text
lane; MemoryKernel is a structured atom lane.  M3C parity means the shadow report
can answer these questions for a representative case:

- Which current-context risks would MemoryKernel block, redact, or warn about?
- Which MemoryKernel atoms would be admitted, and why?
- Which atoms would be omitted, and which policy blocked them?
- Did any safety rule become weaker than the legacy path?
- Did conservative policy omit enough material that task usefulness would drop?
- Did budgets or truncation hide relevant candidates?

A parity pass is therefore evidence for later review, not permission to wire
MemoryKernel into live prompts.

## 60->80 Roadmap

The current state is roughly 60% of the architecture target: the read-only M3B
harness exists, synthetic cases cover the core safety blockers, and the report
shape distinguishes warnings from hard failures.  Reaching the 80% architecture
bar requires these additions before runtime integration is considered:

1. Parity case catalog: expand fixture-backed cases for legacy context text,
   empty result sets, high-risk omissions, projection omissions, rejected and
   superseded atoms, redaction, budget truncation, and useful admitted atoms.
2. CLI reports: make JSON and Markdown parity reports routine artifacts with
   stable counts for hard failures, warnings, redactions, admitted atoms,
   omitted atoms, truncation, and budget behavior.
3. Shadow wrapper behind flag: add a disabled-by-default wrapper that can run
   legacy current context and MemoryKernel parity side by side without changing
   prompt construction or agent behavior.
4. KnowledgeOps defaulting to MemoryKernel atoms: make read-only KnowledgeOps
   evidence review prefer MemoryKernel atom inputs where available, while still
   preserving separate lanes and never promoting atoms by default.
5. Writer sentinel CI: add CI coverage that fails if M3C paths write retrieval
   feedback, mutate Chetana or canon, touch vector stores, change source atoms,
   or route MemoryKernel atoms into live prompts.

The 80% gate is architectural confidence, not production rollout.  Runtime
replacement still needs explicit review after parity reports show safety is at
least as strict as the legacy lane and useful context is not lost to over-broad
omission.

## Next Move

Treat M3C as the bridge from safety eval to measured parity:

```text
M3B safety eval
  -> M3C parity case catalog and shadow reports
  -> writer sentinel CI
  -> later guarded runtime proposal
```

Do not touch live prompt construction until the parity harness can demonstrate
both safety preservation and useful context coverage across representative
cases.
