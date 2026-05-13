# MemoryKernel M3B Context Safety Eval

Date: 2026-05-13
Status: read-only shadow eval

## Purpose

M3B evaluates context admission safety before MemoryKernel is wired into live
prompt construction.  It does not replace existing retrievers or the
ContextCompiler.  It compares two lanes:

```text
Current Context Lane
  rendered context text
  text safety scan
  warnings only

MemoryKernel Lane
  structured atoms
  context admission pack
  hard failures for unsafe admissions
```

## Locked Decisions

- MemoryKernel is context admission/governance, not a retriever replacement.
- Rollout is dual-lane shadow mode.
- The first context unit is a standalone eval harness.
- Safety metrics come first.
- Current text and MemoryKernel atoms stay separate representations.
- Core logic lives in `dharma_swarm/memory_kernel/context_eval.py`.
- Live home memory is not read by default; surfaces must be explicit.
- The harness writes no retrieval feedback.

## Implemented Components

```text
dharma_swarm/memory_kernel/context_admission.py
  MemoryContextBudget
  MemoryContextPack
  preview_memory_pack()

dharma_swarm/memory_kernel/context_safety.py
  redaction and text safety helpers

dharma_swarm/memory_kernel/context_eval.py
  ContextEvalConfig
  ContextEvalReport
  evaluate_current_context_text()
  evaluate_memory_kernel_context()
  run_context_eval()

dharma_swarm/memory_kernel/context_eval_render.py
  render_context_eval_markdown()

dharma_swarm/memory_kernel/context_eval_cases.py
  synthetic case catalog for fixture-only context admission checks

dharma_swarm/memory_kernel/facade.py
  MemoryKernel.preview_memory_pack()

scripts/memory_context_eval.py
  explicit-input CLI wrapper for fixture-backed or operator-supplied evals
  rejects report outputs under memory-surface roots unless explicitly allowed
```

## Safety Contract

Hard failures:

- MemoryKernel context pack output leaks local path refs
- serialized eval artifact leaks local path refs
- MemoryKernel admits projection atoms without override
- MemoryKernel admits rejected or superseded atoms
- MemoryKernel admits high-risk atoms without override
- MemoryKernel includes content when `include_content=false`

Warnings:

- current context text contains local path refs
- current context text contains secret-like markers
- current context text is risky or weakly provenanced
- MemoryKernel omits everything by conservative policy
- candidate sets are truncated

Current context findings are warnings because the harness is measuring the
legacy path. MemoryKernel findings are hard failures because the new admission
layer must be stricter than the legacy path.

## Next Move

Run fixture-backed evals through the script wrapper and synthetic case catalog:

```text
scripts/memory_context_eval.py
dharma_swarm.memory_kernel.run_default_context_eval_cases()
```

Keep adding representative cases before touching `context.py`, `ContextCompiler`,
or `AgentRunner`.
