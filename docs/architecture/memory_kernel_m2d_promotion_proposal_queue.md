# MemoryKernel M2D Promotion Proposal Queue

Date: 2026-05-12
Status: read-only proposal queue

## Purpose

M2D adds an explicit proposal queue after MemoryKernel evidence and
conflict/projection review.  It does not promote memory.  It identifies atoms
that passed structural gates and packages them for later human or governed
review.

The boundary is:

```text
MemoryKernel atoms
  -> evidence review
  -> conflict/projection review
  -> promotion proposal queue
  -> later human/gated promotion
```

## Implemented Components

```text
dharma_swarm/knowledge_ops/memory_promotion_queue.py
  MemoryPromotionProposalQueue
  MemoryPromotionProposal
  MemoryPromotionGate
  MemoryPromotionQueueStatus
  build_memory_promotion_queue()
  render_memory_promotion_queue_markdown()

dharma_swarm/knowledge_ops/cli.py
  --memory-promotion-queue-out
  --memory-promotion-queue-md-out
```

## Safety Contract

The queue is an artifact, not a memory store.  It does not:

- write to MemoryKernel, Chetana, wiki, ontology, runtime state, vectors, or logs
- mark anything promoted
- mutate source atoms
- infer semantic truth from content
- expose raw content or local paths
- route anything into prompt context

Path-like refs are carried as stable `redacted_ref:<hash>` handles.  Atom IDs
and surface IDs remain available for correlation.

## Proposal Gate

M2D consumes the M2C structural review.  A proposal appears only when the atom
already passed the M2C promotion-candidate rules:

- `promotion_allowed == true`
- truth state is observed or curated
- atom is not a projection
- canon risk is not high or critical
- PII/secrets risk is not high or critical
- atom is not superseded or rejected
- atom does not carry bounded content

Every proposal remains `ready_for_review`, not accepted.  Required gates are:

```text
human_review
provenance_review
conflict_review
privacy_review
canon_policy_review
knowledgeops_linking
```

## CLI Example

```bash
python -m dharma_swarm.knowledge_ops.cli \
  --repo-root . \
  --include-memory-kernel \
  --memory-surface home.runtime_state \
  --memory-limit-total 10 \
  --memory-promotion-queue-out /private/tmp/memory_promotion_queue.json \
  --memory-promotion-queue-md-out /private/tmp/memory_promotion_queue.md
```

Current bounded run with `home.conversation_log` reports:

```text
total atoms reviewed: 5
promotion proposals: 0
blocked atoms: 5
blocker occurrences: 25
```

That is the expected result for raw/private/projection-like episodic logs.  They
can feed KnowledgeOps as evidence, but they should not become promotion
proposals without stronger gates.

## Next Move

M2E now covers the decision ledger:

```text
M2D proposal queue
  -> M2E reviewed decision ledger schema
  -> explicit accept/reject/defer decisions
  -> then ContextCompiler admission policy
```

See `docs/architecture/memory_kernel_m2e_decision_ledger.md`.

Do not let the queue itself become authority.  It is a review inbox for
KnowledgeOps, not canon.
