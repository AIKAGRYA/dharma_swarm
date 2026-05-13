# MemoryKernel M3 Context Admission Preview

Date: 2026-05-12
Status: read-only preview

## Purpose

M3 adds a context admission preview without wiring MemoryKernel into live
prompts.  It answers a narrow question:

```text
Given a bounded stream of MemoryKernel atoms, which atoms could safely enter a
future context pack, and why were the others omitted?
```

It is a context policy artifact, not a ContextCompiler integration.

## Implemented Components

```text
dharma_swarm/memory_kernel/context_admission.py
  MemoryContextBudget
  MemoryContextPack
  MemoryContextPackItem
  preview_memory_pack()
  render_memory_context_pack_markdown()

dharma_swarm/memory_kernel/facade.py
  MemoryKernel.preview_memory_pack()

dharma_swarm/knowledge_ops/cli.py
  --memory-context-pack-out
  --memory-context-pack-md-out
  --memory-context-max-candidates
  --memory-context-max-admitted
```

## Safety Contract

The preview does not:

- inject any memory into runtime prompts
- write retrieval feedback
- promote proposals
- mutate Chetana, wiki, runtime DBs, vector stores, or logs
- treat projections as truth
- include raw content by default
- expose local path references

Default policy is intentionally conservative:

```text
require context_admissible = true
allow observed / curated / canonical truth states only
block projections
block high-risk atoms
emit reference-only items unless content inclusion is explicitly requested
```

Since current adapters default `context_admissible=false`, live MemoryKernel
atoms are expected to be omitted by policy until an explicit admission layer
marks selected atoms as safe.

## Output Shape

Each preview records:

```text
pack_id
budget
candidate_count
admitted_count
omitted_count
candidate_truncated
total_selected_chars
items[]
warnings[]
```

Each item records the atom identity, surface, type, authority, truth state,
scope, lane, sanitized refs, admission status, selection reasons, omission
reasons, and warnings.

## Next Move

The next cut should reconcile context admission with the review artifacts:

```text
M2B evidence review
M2C conflict/projection review
M2D promotion proposal queue
M2E decision ledger
M3 context admission preview
  -> M3B policy joiner
  -> later ContextCompiler compatibility wrapper
```

Do not wire this into `context.py`, `AgentRunner`, or prompt construction until
the policy joiner can consider evidence risk, conflict blockers, promotion
state, and decision state together.
