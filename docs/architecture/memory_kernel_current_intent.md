# MemoryKernel Current Intent

Date: 2026-05-12
Status: coordination note

## Purpose

This note exists to reduce plan-vs-execution drift while MemoryKernel work is
being edited across multiple sessions.  It is not a replacement for PR review,
tests, or the detailed M0-M2 architecture docs.

## Current Architectural Decision

MemoryKernel is the governed coordination layer for memory surfaces.  It is not
a new central memory database.

```text
memory-like surfaces
  -> MemoryKernel registry, adapters, provenance, authority, read budgets
  -> KnowledgeOps evidence intake and review artifacts
  -> Chetana / KnowledgeOps metabolism
  -> human or gated canon decisions
```

MemoryKernel coordinates.  KnowledgeOps metabolizes.  Canon remains gated.

## Current Phase Boundary

The active work should stay within these limits:

- M0: surface census and registry
- M1: read-only adapters and normalized atoms
- M2A: writer sentinel / bypass visibility
- M2B: KnowledgeOps read-only evidence intake
- M2C: conflict and projection review
- M2D: read-only promotion proposal queue
- M2E: read-only promotion decision ledger
- M3: read-only context admission preview
- M3B: read-only context safety eval harness

Do not add runtime prompt injection, canon writes, Chetana mutations, vector
rebuilds, migrations, or write-through gates until the read-only layers are
merged and reviewed. M3/M3B may preview and evaluate context admission as
shadow artifacts, but they must not wire MemoryKernel atoms into `context.py`,
`ContextCompiler`, `AgentRunner`, or prompt construction.

## Reconciliation Rule

For the next active build window, observe shipped changes before rewriting the
plan.  Use:

```bash
python scripts/memory_kernel_plan_observer.py \
  --repo-root . \
  --duration-seconds 21600 \
  --interval-seconds 60 \
  --output reports/knowledge_ops/memory_kernel_plan_observer.jsonl
```

After the window, compare the JSONL trajectory against this intent note and the
M0-M2 docs.  Update the plan to match what actually shipped, and record any
deliberate divergence explicitly.

## Non-Negotiables

- Raw logs, projections, external memories, and generated summaries are not
  authority.
- Vector/LanceDB stores are projections only.
- Chetana staging is not canon.
- Repo-local `.dharma` and `.swarm` state is snapshot or fixture state unless
  explicitly classified otherwise.
- Review artifacts must not expose raw content or local path refs.
- Promotion proposals are review inbox items, not accepted knowledge.
- Context admission evals are shadow-mode only until they preserve safety and
  prove parity against current context behavior.
