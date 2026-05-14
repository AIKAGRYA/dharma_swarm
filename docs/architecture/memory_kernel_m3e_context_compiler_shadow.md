# MemoryKernel M3E Context Compiler Shadow

Date: 2026-05-13
Status: disabled-by-default `ContextCompiler` shadow wrapper

## Purpose

M3E extends MemoryKernel observation from `read_memory_context()` into the
primary runtime `ContextCompiler.compile_bundle()` seam.  The compiler still
builds and persists the legacy context bundle exactly as before.  When shadow
mode is enabled, MemoryKernel evaluates the rendered bundle text against the
MemoryKernel context lane and reports parity/safety findings through a callback
or debug log.

This is still not live context replacement.  No MemoryKernel atoms are injected
into prompts or bundles.

## Contract

The shadow wrapper may:

- compare the rendered legacy context bundle with a MemoryKernel parity report
- use explicit MemoryKernel surfaces when a home path and surface IDs are
  supplied
- call an operator/test callback with the parity report
- emit debug logging

The shadow wrapper must not:

- alter `ContextBundleRecord.rendered_text`
- add MemoryKernel atoms to context sections
- write retrieval feedback
- promote, archive, reject, or mutate memory atoms
- write reports into memory surfaces
- read live MemoryKernel home surfaces unless a home path and surface list are
  explicitly supplied

## Activation

Programmatic:

```python
bundle = await compiler.compile_bundle(
    session_id="sess",
    task_description="Review the active task.",
    memory_kernel_shadow=True,
    memory_kernel_shadow_home=Path("/path/to/home"),
    memory_kernel_shadow_surfaces=("home.memory_plane",),
    memory_kernel_shadow_callback=reports.append,
)
```

Environment:

```text
DHARMA_MEMORY_KERNEL_CONTEXT_COMPILER_SHADOW=1
DHARMA_MEMORY_KERNEL_HOME=/Users/dhyana
DHARMA_MEMORY_KERNEL_CONTEXT_COMPILER_SURFACES=home.memory_plane,home.runtime_state
```

The global `DHARMA_MEMORY_KERNEL_CONTEXT_SHADOW=1` flag also enables the
compiler shadow lane.  Without a home path and explicit surfaces, the shadow
lane compares the rendered bundle against an empty MemoryKernel lane.  That is
useful for safety accounting, not retrieval parity.

## 80% Implication

MemoryKernel can now shadow both the lightweight legacy memory reader and the
primary runtime context compiler.  The remaining step before live context
admission is representative report collection: run task, review, KnowledgeOps,
route/witness, and secret-contaminated scenarios and inspect whether the
MemoryKernel lane is safer, smaller, and sufficiently grounded.
