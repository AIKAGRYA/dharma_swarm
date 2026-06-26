---
id: god-object-decomposition-plan
version: 0.0.1
theme: 02-module-topology
status: tested
invariant: >
  A module should have one reason to change (SRP). An oversized module bundles
  several secrets; the decomposition follows the seams the code already has —
  cohesive clusters of types/functions that move together — not arbitrary
  line-count splits. Plan the cut along real cohesion, smallest-blast-radius first
  (extract the leaf data types before the entangled logic). Never propose a split
  that breaks a public import without a re-export shim.
lineage:
  - "Parnas 1972 — decompose by secret/responsibility, not by flowchart"
  - "Martin (SRP) — one reason to change per module"
  - "Constantine — maximize cohesion within a module, minimize coupling across"
ground_truth_tools: ["read the module's class/function structure", "fan-in per symbol (what the outside actually uses)", "the import graph for the shim surface"]
returns_clean: true
---

## Prompt

> Produce a **decomposition plan** for an oversized module — not a rewrite. The
> invariant (Parnas, SRP): one reason to change. Find the **cohesive clusters** the
> module already contains (types that move together, functions that share state)
> and propose a split along those seams, **smallest blast radius first**.
>
> **Do this:**
> 1. List the module's top-level classes/functions and group them into cohesive
>    clusters (by shared state, by concept, by who-calls-them).
> 2. Propose target modules, one cluster each, named by responsibility.
> 3. **Order by blast radius:** extract leaf **data types** first (low risk — pure
>    moves), entangled logic last. For each move, note what external code imports it
>    (so a re-export shim preserves the public path).
> 4. Do **not** write the refactor. Output the plan + the order + the shim surface,
>    and stop for review.
>
> **Return clean** if the module is large but genuinely cohesive (one secret, one
> reason to change) — size alone is not a smell. Say so.

## Why it's built this way

The kit-style "this file is too long, split it" is useless — it ignores cohesion
and breaks imports. The disciplined plan follows Parnas's seams (the secrets the
module hides) and sequences by blast radius so the first PR is a safe pure-move of
leaf types. SRP says when to split; cohesion says where.

## Demonstration run

**Target:** `dharma_swarm/thinkodynamic_director.py` — **5,255 lines**, 11 classes,
44 top-level functions, 2026-06-25.

**Cohesion clusters (from real structure):**
- **Data types — signals:** `FileSignal`, `LatentGoldSignal`, `DirectorOpportunity`
  → `thinkodynamic_signals.py` (pure dataclasses; **lowest blast radius — do first**).
- **Data types — workflow plan:** `WorkflowTaskPlan`, `WorkflowPlan`,
  `WorkflowReview`, `ThemeTemplate` → `thinkodynamic_plan.py`.
- **Spec/config:** `DirectorMindSpec` → fold into the plan module or its own.
- **Director logic:** the 44 functions + remaining classes that *operate on* the
  above → stays in `thinkodynamic_director.py`, now ~half the size and importing the
  two new type modules.

**Order (blast radius ascending):** (1) extract `*_signals.py` (pure move) →
(2) `*_plan.py` (pure move) → (3) thin the director to logic-only. Each step is a
mechanical move + a re-export shim in `thinkodynamic_director.py`
(`from .thinkodynamic_signals import *`) so existing imports keep working — verify
against the module's fan-in before deleting the shim.

**Not a rewrite:** the logic is untouched; only the type-bag is unbundled. This is
the SRP cut that also removes ~half the file from the `>3000-line` ratchet
violation set.

## Changelog

- **v0.0.1** (2026-06-25) — decomposition-plan (Parnas/SRP), blast-radius-ordered,
  no-rewrite, shim-preserving. Tested on the repo's largest module
  (`thinkodynamic_director.py`, 5,255 ln): a 3-step plan extracting the signal +
  plan dataclasses first, logic last.
