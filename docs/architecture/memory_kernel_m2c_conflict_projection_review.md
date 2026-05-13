# MemoryKernel M2C Conflict Projection Review

Date: 2026-05-12
Status: read-only structural review

## Purpose

M2C adds the next KnowledgeOps review layer over MemoryKernel atoms.  It does
not decide semantic truth.  It finds structural conflict candidates, projection
blockers, privacy/canon-risk blockers, and conservative promotion candidates.

The boundary is:

```text
MemoryKernel atoms
  -> evidence review
  -> conflict/projection review
  -> later human/gated promotion queue
```

## Implemented Components

```text
dharma_swarm/knowledge_ops/memory_conflict_review.py
  MemoryConflictProjectionReview
  MemoryReviewFinding
  MemoryPromotionCandidate
  review_memory_conflicts()
  render_memory_conflict_review_markdown()

dharma_swarm/knowledge_ops/cli.py
  --memory-conflict-review-out
  --memory-conflict-review-md-out
```

## Safety Contract

The review is structural and read-only.  It does not:

- infer contradiction from raw text
- copy raw atom content into JSON or Markdown reports
- promote, archive, supersede, or delete memory
- mutate Chetana, wiki, ontology, runtime state, vectors, memory plane, or logs
- wire ContextCompiler or agent prompts

Findings use atom IDs, surface IDs, content refs, truth-state labels, authority
labels, projection flags, and risk labels.  Bounded raw content remains outside
the report.

## Review Signals

M2C currently detects:

- same `content_ref` with divergent truth states
- same `content_ref` with divergent authority levels
- projection atoms being treated as non-authority
- high or critical canon risk
- high or critical PII/secrets risk
- superseded or rejected atoms
- atoms claiming to supersede other atoms
- atoms marked context-admissible
- atoms marked promotion-allowed
- atoms carrying bounded content

Promotion candidates are conservative.  An atom must be promotion-allowed,
observed or curated, non-projection, not high-risk, not superseded/rejected, and
not content-bearing.  Passing that structural gate still does not make it canon.

## Report Honesty

The report separates totals from displayed bounded samples:

```text
finding_count
displayed_finding_count
finding_truncated
promotion_candidate_count
displayed_promotion_candidate_count
promotion_candidate_truncated
promotion_blocked_atom_count
promotion_blocker_count
```

This avoids the false-confidence failure mode where a bounded review looks
complete after hitting a display cap.

## CLI Example

```bash
python -m dharma_swarm.knowledge_ops.cli \
  --repo-root . \
  --include-memory-kernel \
  --memory-surface home.conversation_log \
  --memory-limit-total 5 \
  --memory-limit-per-surface 5 \
  --memory-review-out /private/tmp/memory_review.json \
  --memory-review-md-out /private/tmp/memory_review.md \
  --memory-conflict-review-out /private/tmp/memory_conflict.json \
  --memory-conflict-review-md-out /private/tmp/memory_conflict.md
```

Current bounded run with `home.conversation_log` reports:

```text
total atoms: 5
findings: 15
projection blockers: 5
promotion candidates: 0
promotion-blocked atoms: 5
promotion blocker occurrences: 25
```

Path-like and long content refs are rendered as `redacted_ref:<hash>` in review
artifacts.  This preserves stable correlation without exposing local paths or
payload text.

## Next Move

M2D now covers the read-only proposal queue:

```text
M2C structural review
  -> M2D explicit promotion proposal queue
  -> human/gated review contract
  -> later ContextCompiler admission policy
```

See `docs/architecture/memory_kernel_m2d_promotion_proposal_queue.md`.

Do not route MemoryKernel atoms directly into agent prompts until context
admission policy can consume evidence review, conflict review, provenance, and
privacy labels together.
