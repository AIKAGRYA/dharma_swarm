# MemoryKernel M2B KnowledgeOps Intake

Date: 2026-05-11
Status: read-only bridge

## Purpose

M2B gives KnowledgeOps a first consumer path through MemoryKernel.  It does not
scrape memory stores directly, and it does not promote, archive, dedupe canon,
mutate Chetana, rebuild indexes, or route prompt context.

The boundary is:

```text
MemoryKernel atoms
  -> KnowledgeOps evidence/runtime-fact nodes
  -> DERIVED_FROM edges to memory surface nodes
  -> later critique/linking/promotion proposals
```

## Implemented Components

```text
dharma_swarm/knowledge_ops/memory_intake.py
  MemoryKernelIntakeConfig
  MemoryKernelIntake
  MemoryEvidenceReview
  memory_atoms_to_snapshot()
  review_memory_atoms()
  render_memory_evidence_review_markdown()
  merge_snapshots()

dharma_swarm/knowledge_ops/cli.py
  --include-memory-kernel
  --memory-surface
  --memory-limit-total
  --memory-limit-per-surface
  --memory-review-out
  --memory-review-md-out
```

## Safety Contract

Memory atoms enter KnowledgeOps as staged evidence or runtime facts.  The bridge
preserves:

```text
memory_atom_id
surface_id
atom_type
content_ref
authority_level
provenance_quality
projection_of
canon_risk
pii_risk
adapter_name
read_mode
surface_category
surface_role
memory_lane
scope
truth_state
freshness
valid_from / valid_until
source_refs
promotion_allowed
context_admissible
```

The bridge intentionally does not copy atom content into KnowledgeOps metadata.
`has_content` records whether the atom carried content, but content itself stays
out of the projection unless a future reviewed policy adds a bounded evidence
excerpt field.

Path-like or very long refs are redacted to stable `redacted_ref:<hash>` handles
in projection/review artifacts.  The atom ID and surface ID remain available for
correlation without exposing local filesystem paths.

Lifecycle status remains conservative:

```text
raw/claimed/observed/derived/curated/promoted atoms -> staged KnowledgeOps nodes
superseded atoms -> superseded KnowledgeOps nodes
rejected atoms -> contested KnowledgeOps nodes
```

This avoids laundering MemoryKernel evidence into KnowledgeOps canon.

## CLI Example

```bash
python -m dharma_swarm.knowledge_ops.cli \
  --repo-root . \
  --include-memory-kernel \
  --memory-surface home.conversation_log \
  --memory-limit-total 5 \
  --memory-limit-per-surface 5 \
  --memory-review-out reports/knowledge_ops/memory_review.json \
  --memory-review-md-out reports/knowledge_ops/memory_review.md
```

Current bounded run with `home.conversation_log` adds:

```text
derived_from edges: 5
evidence nodes: 6
memory review total atoms: 5
memory review warnings: 3
```

The extra evidence node is the MemoryKernel surface node.  Each selected atom
gets a `DERIVED_FROM` edge back to that surface.

The generated review report currently flags the bounded conversation-log sample
as:

```text
5 high/critical canon-risk atoms
5 high/critical PII-risk atoms
5 projection atoms
0 content-bearing atoms
0 context-admissible atoms
0 promotion-allowed atoms
```

## Next Move

M2C now covers the immediate read-only review layer:

```text
KnowledgeOps evidence review report
  -> conflict/projection/canon-risk summaries
  -> promotion candidate queue
```

See `docs/architecture/memory_kernel_m2c_conflict_projection_review.md`.

Do not wire ContextCompiler or agent prompts yet.  Context admission should wait
until KnowledgeOps can summarize which evidence was raw, projected, stale,
private, or safe for context.
