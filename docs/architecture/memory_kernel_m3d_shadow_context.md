# MemoryKernel M3D Shadow Context Wrapper

Date: 2026-05-13
Status: disabled-by-default shadow wrapper

## Purpose

M3D adds a compatibility hook around `read_memory_context()` so MemoryKernel can
observe legacy context behavior without replacing it.  The hook runs only when
explicitly enabled by arguments or environment variables, and it never changes
the string returned by the legacy context reader.

This is still not live context replacement.  It is the first runtime-adjacent
shadow point.

## Contract

The shadow wrapper may:

- compare the returned legacy context string with a MemoryKernel parity report
- use explicit MemoryKernel surfaces when a home path and surface IDs are
  supplied
- call an operator/test callback with the parity report
- emit debug logging

The shadow wrapper must not:

- alter prompt text
- write retrieval feedback
- promote, archive, reject, or mutate memory atoms
- write reports into memory surfaces
- read live MemoryKernel home surfaces unless a home path and surface list are
  explicitly supplied

## Activation

Programmatic:

```python
read_memory_context(
    memory_kernel_shadow=True,
    memory_kernel_shadow_home=Path("/path/to/home"),
    memory_kernel_shadow_surfaces=("home.conversation_log",),
    memory_kernel_shadow_callback=reports.append,
)
```

Environment:

```text
DHARMA_MEMORY_KERNEL_CONTEXT_SHADOW=1
DHARMA_MEMORY_KERNEL_HOME=/Users/dhyana
DHARMA_MEMORY_KERNEL_CONTEXT_SURFACES=home.conversation_log,home.memory_plane
```

Without a home path and explicit surfaces, the shadow lane still runs but only
compares the legacy text against an empty MemoryKernel lane.  That is useful for
safety accounting, not retrieval parity.

## Writer Sentinel CI

`scripts/memory_writer_sentinel.py --ci` now composes the safe fail gates:

- registered writers must be present
- registered writers must target known surfaces
- AST discovery is enabled
- action-required discoveries fail the command

It does not use the strict unregistered-discovery gate because generated
artifacts and operational state are intentionally triaged as non-actionable in
the current registry.

## 80% Implication

This moves MemoryKernel from static parity into runtime-adjacent observation.
The remaining 80% work is to collect shadow reports from representative
contexts, then decide whether a flagged `ContextCompiler` compatibility wrapper
should consume MemoryKernel packs directly.
