---
id: wildcard-import-audit
version: 0.0.1
theme: 17-code-health-metrics
status: tested
invariant: >
  `from x import *` imports an unknown, mutable set of names into a namespace —
  defeating static analysis, shadowing silently, and breaking tree-shaking and
  dead-code detection. It is the #1 measured AI-generated smell. The namespace
  contract must be explicit: every imported name is named. Re-export sprawl
  (`__all__` dumps that re-export everything) is the same smell wearing a tie.
lineage:
  - "Parnas — explicit interfaces; a module's imports are part of its contract"
  - "arXiv 2508.14727 — Wildcard Usage is the most common AI-generated smell (97 occ.)"
  - "tree-shaking — wildcard defeats static reachability, so dead code can't be found"
ground_truth_tools: ["grep/AST for `import *` and broad `__all__` re-exports", "the linter's F403/F401"]
returns_clean: true
---

## Prompt

> Audit **wildcard imports and re-export sprawl**. The invariant (Parnas): a
> module's imports are part of its contract, and `from x import *` makes that
> contract an unknown, mutable set — it shadows silently and defeats dead-code/
> tree-shaking analysis. It's the **#1 measured AI smell**.
>
> **Find:** every `from x import *` (`file:line`); broad `__all__` that re-exports a
> whole submodule; star-re-exports in `__init__`. For each: the names it actually
> pulls in (if resolvable) and the explicit-import replacement. **Return clean** if
> there are none — and on a clean repo, *say so plainly*; this is a common
> return-clean case and a generic "avoid wildcard imports" lecture would be noise.

## Why it's built this way

It's a small, high-signal, fully-static check — the kind a heuristic prompt would
either skip or pad. The discipline is just: measure it, replace with explicit names,
and **return clean honestly** when the count is zero (which it often is in
lint-gated repos).

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. Tool: grep/AST for `from … import *`.

- **0 wildcard imports** across the `dharma_swarm/` package. **🟢 Return clean.**
- Honest output: *"No wildcard imports — the namespace contracts are explicit
  (likely ruff F403-gated). Nothing to do on this axis."* No lecture, no invented
  finding. (This is the clean counterpart to the slop-index's wildcard signal =
  GREEN.)

A kit prompt asked to "find wildcard imports" would still emit advice; the
disciplined one reports zero and stops — return-clean is a feature.

## Changelog

- **v0.0.1** (2026-06-25) — wildcard/re-export audit (Parnas/arXiv). Static, high-
  signal, explicit-import fix, honest return-clean. Tested on `dharma_swarm`: **0**
  occurrences → returned clean without padding.
