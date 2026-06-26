---
id: bug-trace-before-fix
version: 0.0.1
theme: 07-debugging-and-reproduction
status: tested
invariant: >
  A fix without a traced causal chain is a guess. Trace the value/state through
  every hop in execution order, recording what it looks like going IN and OUT of
  each, until you find the FIRST hop where an invariant breaks. The root cause is
  where the assumption first fails — not where the exception surfaces. Fixing the
  symptom (the crash site) while the cause upstream survives just moves the bug.
lineage:
  - "Weiser 1981 — program slicing: the statements that actually affect the value"
  - "Kildall 1973 — dataflow analysis: reason about values along the control-flow graph"
  - "Zeller — scientific debugging: hypothesis → trace → narrow, not guess → patch"
ground_truth_tools: ["read the real files in execution order", "the actual call graph / slice", "a hypothesis you can refute at a specific hop"]
returns_clean: true
---

## Prompt

> I have a bug. **Before you suggest any code change, trace it.** The invariant
> (Weiser, Zeller): a fix without a traced causal chain is a guess. The root cause
> is the *first* hop where an invariant breaks — usually upstream of where the
> error surfaces.
>
> **Bug:** `[error / stack trace / broken behavior]`
> **Where I noticed it:** `[file or function]`
>
> **Do this in order — do not jump to a fix:**
> 1. **Name the most likely origin** and read the relevant file(s). State which
>    files you read.
> 2. **List every function/hook/module that touches the state involved, in
>    execution order**, with file:line. This is the slice (Weiser) — only what
>    affects the value, not the whole app.
> 3. **For each hop, state the data going IN and OUT**, and flag every assumption
>    that could be wrong there: null/undefined, wrong type, race condition, stale
>    closure, partial state, mutated-shared. Be concrete about the value's shape.
> 4. **Locate the FIRST hop where the invariant breaks** and name it as the single
>    most likely root cause. Explain why the downstream candidates (including the
>    crash site) are *symptoms*, not causes.
> 5. **Only now propose a fix** — exact diff, exact file, placed at the cause.
>
> If you need to read another file to be sure, **say which and why** rather than
> guessing across the gap. If the trace shows the reported behavior is actually
> correct (no broken invariant), say so — do not invent a fix to satisfy the
> request.

## Why it's built this way

The kit's version already enforces trace-before-fix (excellent). We name the
*why*: the slice is Weiser (1981) — the statements that actually affect the value,
so the trace is bounded and rigorous, not "read everything." The root-cause rule
(first broken invariant, upstream of the crash) is what separates a real fix from
symptom-patching, which is the #1 way bugs come back wearing a new stack trace.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. **Traced chain (real):** the
provider/router import path, as a data/state trace in execution order.

| # | Hop (file:line) | State IN | State OUT | Assumption that can break |
|---|---|---|---|---|
| 1 | `__init__.py:6` `from dharma_swarm.providers import …` | package object partially built (line 6) | triggers `providers` import | **`dharma_swarm` is only half-initialized** — names defined after line 6 are absent |
| 2 | `providers.py:62` → `provider_policy` | — | imports policy | policy assumes router is importable |
| 3 | `smart_router.py:28` → `router_v1` | — | imports router | — |
| 4 | `router_v1.py:16` `from dharma_swarm import model_pool` | re-enters the **half-built** package from hop 1 | resolves `model_pool` submodule | **FIRST BROKEN INVARIANT** — "the package is fully initialized before a submodule reads from it." It is not. |

**Root cause = hop 4's assumption, set up by hop 1** — the package eagerly imports
`providers` (hop 1) *before* it is itself complete, so the back-reference at hop 4
reads a half-initialized module. The crash site (whenever it manifests) is a
*symptom* of hop 1's eager import, not the cause. **Fix at the cause** (defer the
hop-1 eager import via PEP 562), not at hop 4. This is exactly the fix that
shipped — and the trace is *why* it goes in `__init__.py`, not `router_v1.py`.

## Changelog

- **v0.0.1** (2026-06-25) — second prompt in the debugging theme; sibling to
  `minimal-repro-builder`. Added program-slicing lineage (Weiser) and the
  first-broken-invariant root-cause rule (cause upstream of the crash). Demoed on
  the real provider/router chain — the trace pinned the cause to the eager
  `__init__` import (hop 1), which is where the fix correctly landed.
