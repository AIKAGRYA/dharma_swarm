# MemoryKernel M2E Promotion Decision Ledger

Date: 2026-05-12
Status: read-only decision review

## Purpose

M2E adds a review ledger after the promotion proposal queue.  It gives humans
or future gatekeepers a structured place to accept, reject, or defer a
MemoryKernel promotion proposal without mutating memory stores or canon.

The boundary is:

```text
MemoryKernel atoms
  -> evidence review
  -> conflict/projection review
  -> promotion proposal queue
  -> promotion decision ledger
  -> later governed canon/write path
```

## Implemented Components

```text
dharma_swarm/knowledge_ops/memory_decision_ledger.py
  MemoryPromotionDecisionLedger
  MemoryPromotionDecision
  MemoryPromotionDecisionReview
  MemoryPromotionDecisionKind
  MemoryPromotionDecisionValidity
  build_memory_decision_ledger()
  load_memory_promotion_decisions()
  render_memory_decision_ledger_markdown()

dharma_swarm/knowledge_ops/cli.py
  --memory-decision-in
  --memory-decision-ledger-out
  --memory-decision-ledger-md-out
```

## Safety Contract

The ledger is still an artifact, not an authority store.  It does not:

- mark anything canonical
- write to Chetana, wiki, ontology, runtime state, vectors, memory plane, or logs
- change source atoms or proposals
- infer semantic truth from payload text
- expose raw content or local path refs
- route anything into prompt context

Valid decisions are review records, not canon writes.

## Decision Validation

Decision rows can be loaded from JSON.  Each decision must reference an existing
proposal and include:

```text
proposal_id
atom_id
surface_id
decision: accept | reject | defer
reviewer
rationale
approved_gates
```

Accept decisions must approve every gate required by the proposal:

```text
human_review
provenance_review
conflict_review
privacy_review
canon_policy_review
knowledgeops_linking
```

Reject and defer decisions still require reviewer and rationale, but they do
not require all proposal gates.

## CLI Example

```bash
python -m dharma_swarm.knowledge_ops.cli \
  --repo-root . \
  --include-memory-kernel \
  --memory-surface home.runtime_state \
  --memory-limit-total 10 \
  --memory-decision-in /private/tmp/memory_decisions.json \
  --memory-decision-ledger-out /private/tmp/memory_decision_ledger.json \
  --memory-decision-ledger-md-out /private/tmp/memory_decision_ledger.md
```

## Next Move

The next cut is context admission policy, still off the hot path:

```text
M2E decision ledger
  -> M3 context admission policy and memory pack preview
  -> later ContextCompiler compatibility wrapper
```

Do not wire MemoryKernel atoms into prompts until context admission can consume
evidence review, conflict review, proposal state, and decision state together.
