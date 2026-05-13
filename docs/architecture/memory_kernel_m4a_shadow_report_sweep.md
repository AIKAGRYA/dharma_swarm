# MemoryKernel M4A Shadow Report Sweep

Date: 2026-05-14
Status: read-only shadow report sweep

## Purpose

M4A collects representative context parity reports before MemoryKernel is used
as a live context source.  The sweep exercises legacy context-shaped text
against the MemoryKernel lane across normal work, code review, KnowledgeOps,
routing/witness, stale conflict, sensitive contamination, and large noisy
contexts.

This is still shadow-mode only.  The sweep does not inject prompts, write
retrieval feedback, mutate memory, promote knowledge, or write to Chetana/canon.

## Command

```bash
python scripts/memory_context_shadow_sweep.py \
  --repo-root . \
  --output-json /private/tmp/memory_context_shadow_sweep.json \
  --output-md /private/tmp/memory_context_shadow_sweep.md
```

Optional explicit MemoryKernel surface comparison:

```bash
python scripts/memory_context_shadow_sweep.py \
  --repo-root . \
  --memory-home /Users/dhyana \
  --memory-surface home.memory_plane \
  --memory-surface home.runtime_state \
  --dry-run
```

## Safety Contract

The sweep must:

- redact local paths and secret-like strings in stdout, JSON, and Markdown
- reject outputs under memory roots such as `.dharma`, `.smriti`,
  `.codex/memories`, repo-local `.dharma`, and repo-local `.swarm`
- avoid live home reads unless `--memory-home` and at least one
  `--memory-surface` are explicit
- use `include_content=false` for MemoryKernel packs
- preserve the distinction between legacy context findings and MemoryKernel
  context-lane findings

## Scenarios

- `normal_task_context`
- `code_review_context`
- `knowledge_ops_context`
- `routing_witness_context`
- `stale_conflict_context`
- `sensitive_contamination_context`
- `large_noisy_context`

## 90% Implication

M4A provides the report collection substrate needed before KnowledgeOps intake
or opt-in context preview sections rely on MemoryKernel.  The next 90% steps are
M4B KnowledgeOps evidence intake, M4C adapter coverage hardening, M4D CI wiring,
and M4F readiness reporting.
