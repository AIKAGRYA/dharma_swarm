---
id: circular-dependency-triage
version: 0.0.2
theme: 02-module-topology
status: tested
invariant: >
  A module import graph must be a DAG. A cycle is a defect; the only question is
  blast radius. The danger of a cycle is set by WHEN it resolves: a load-time
  (module-level) cycle is a latent boot failure (ImportError / half-initialized
  module); a lazy cycle (imports deferred inside functions) is usually benign and
  often the correct fix. Rank by load-time danger, never by cycle length.
lineage:
  - "Dijkstra 1968 — structured/layered systems with strict ordering"
  - "Parnas 1972 — information hiding; modules decomposed by secrets"
  - "Tarjan 1972 — strongly-connected components in linear time"
  - "Kahn 1962 — topological sort (a healthy graph is a DAG)"
ground_truth_tools: [AST import graph + Tarjan SCC, grimp, pydeps, "python -X importtime"]
returns_clean: true
---

## Prompt

> You are auditing a codebase's **module import graph**. The invariant you defend
> is from Dijkstra, Parnas, and Tarjan: **a healthy import graph is a DAG.** A
> cycle is a defect — but its real cost is set by *when it resolves*, so your job
> is to find the cycles **with a real algorithm**, then rank them by **load-time
> blast radius**, and to leave alone the cycles the authors have already
> neutralized.
>
> **Hard rules (do not violate, even to produce a fuller-looking report):**
>
> 1. **Build the graph, then run Tarjan — do not pattern-match imports.** A cycle
>    is a strongly-connected component (SCC) of size > 1 in the import digraph.
>    Construct the graph from the real source (parse the AST / use `grimp`,
>    `pydeps`, `madge`, or equivalent) and compute SCCs (Tarjan, 1972). Eyeballing
>    `A imports B` pairs misses every chain of length ≥ 3 and every indirect edge.
> 2. **Classify every edge in a cycle as load-time or lazy.** A *load-time* edge is
>    a module-level `import` (executed at import). A *lazy* edge is an import inside
>    a function/method/`TYPE_CHECKING` block (executed later, or never). This is
>    the single most important distinction and the heuristic kits omit it.
> 3. **Rank by load-time danger, not by length.** A 2-module load-time cycle that
>    runs on boot outranks an 8-module cycle that is entirely lazy. Order:
>    (a) cycles with load-time edges that can fail at import, worst first;
>    (b) mixed cycles; (c) fully-lazy cycles — **report these as ALREADY MITIGATED,
>    not as problems to fix.**
> 4. **Do not flag a cycle the authors already deferred.** If every edge in an SCC
>    is lazy, the team has already applied the correct fix (deferral). Saying
>    "refactor this" is noise. State it's mitigated and move on.
> 5. **Find the minimum feedback edge — the smallest break.** For each load-time
>    cycle, identify the single edge whose removal/deferral makes the component
>    acyclic with the least churn (usually a back-edge importing one name, or an
>    eager import in a package `__init__`). Name the exact `file:line`.
> 6. **Return clean when clean.** If there are no SCCs of size > 1, output:
>    `Import graph is a DAG. N modules, 0 cycles.` Do not manufacture cycles.
>
> **Output contract** — one entry per cycle, ordered load-time-danger first:
> - cycle members (module names) and SCC size
> - the edges *inside* the cycle as `module → module` with `file:line: statement`,
>   each tagged `[load-time]` or `[lazy]`
> - classification: `LOAD-TIME (boot risk)` | `MIXED` | `LAZY (already mitigated)`
> - **minimum break:** the one `file:line` import to remove or defer, and why it's
>   the smallest cut
>
> **Stop when** every SCC is reported and ranked. Do not pad with lazy cycles
> dressed up as findings.

## Why it's built this way

The prompt this rewrites asks the model to spot `A→B→A` by reading import lines.
That fails three ways, all visible on a real repo:

- **It can't see chains.** Real cycles are SCCs of 3–8 modules with indirect
  edges; you find them with Tarjan over a graph, not by eyeballing pairs.
- **It conflates dangerous and harmless.** It treats a load-time cycle (crashes
  on `import`) the same as a lazy cycle (deferred, fine). That's the whole game.
- **It nags about solved problems.** A fully-lazy cycle is the *fix* — flagging it
  tells the author to undo correct work.

So this version builds the graph, runs the 1972 algorithm, and ranks by *when the
cycle resolves*. Lineage isn't decoration: "the graph must be a DAG" is Dijkstra/
Parnas; "find SCCs in linear time" is Tarjan; "a DAG has a topological order" is
Kahn. The analysis is correct because the theory is.

## Demonstration run

**Target:** `dharma_swarm/` (784 internal modules, 565 with internal imports),
2026-06-25. Tool: stdlib AST import-graph + Tarjan SCC (same algorithm as
`grimp`/`pydeps`; none were installed).

### The honest two-pass result (and a self-correction worth keeping)

**Pass 1 — full import graph (load + lazy edges): 12 cyclic SCCs.** This is the
number a naive run reports, and the first draft of this demo ranked those 12 by
*size* (an 8-module SCC, three 7-module SCCs, …) and implied several were
boot-risks. **That was this prompt's own trap, committed by its author** — size
is not danger. A cycle only threatens boot if it closes through *load-time*
edges, and `TYPE_CHECKING` imports never execute at runtime and must be excluded.

**Pass 2 — load-time-only graph, `TYPE_CHECKING` excluded: exactly 1 genuine
load-time cycle.** All the apparent danger collapsed to a single 3-node core:

`dharma_swarm` (package `__init__`) ↔ `providers` ↔ `router_v1`

- `dharma_swarm/__init__.py:6` — `from dharma_swarm.providers import …` **[load-time]**
- `dharma_swarm/providers.py:62` → … → `router_v1.py:28` (provider chain) **[load-time]**
- `dharma_swarm/router_v1.py:16` — `from dharma_swarm import model_pool` **[load-time]** ← re-enters the package while `__init__` is still on line 6 (half-initialized-module trap)

The other **11 SCCs close only via lazy/deferred imports** (e.g. `build_engine ↔
custodians ↔ foreman` — 0 load-time edges) — **already mitigated; do not
refactor.** A heuristic prompt nags about all 12; the disciplined one says *one*
is real.

### Minimum break (proposed on a branch — NOT yet on mainline)
Make the package's provider re-exports lazy (PEP 562 `__getattr__` in
`__init__.py`), so importing the package no longer drags the provider/router
graph into init time. One file, public API unchanged. The fix is **proposed on
`claude/fix-provider-router-import-cycle`** (PR #712); checked out there, pass 2
reaches **0 load-time cycles**.

> **Correction (v0.0.2).** v0.0.1 said the fix "shipped" and the graph "is now a
> DAG." That is true **only on the unmerged fix branch**. On `main` and on this
> library branch the fix is **not present** — `router_v1.py:16` still has the eager
> `from dharma_swarm import model_pool` back-edge and `__init__.py:5–6` still imports
> providers eagerly, so **mainline still has 1 load-time cycle**. An adversarial
> reviewer caught the overclaim. Status: *proposed + verified-on-branch, unmerged.*

### Verdict
Full graph: not a DAG (12 SCCs). Genuine boot risk: **1** (provider/router core) —
mainline **still 1**; a one-file fix is proposed on PR #712 (verified → 0 there,
unmerged). The other 11 are lazy-mitigated and were correctly left alone. The lesson
the prompt enforces — *rank by when the cycle resolves, not by how big it looks* —
is the exact thing its own first draft got wrong, and the rigorous load-time pass
caught it (as a *second* adversarial reviewer later caught the overclaimed "shipped").

## Changelog

- **v0.0.2** (2026-06-27) — **correction after adversarial review.** v0.0.1 claimed
  the fix "shipped" and the load-time graph "is now a DAG." True only on the *unmerged*
  fix branch (PR #712); **mainline still has 1 load-time cycle.** Corrected to
  "proposed + verified-on-branch, unmerged." The Tarjan analysis itself reproduced
  exactly (12 SCCs; 1 load-time) — only the deploy-state claim was overstated.
- **v0.0.1** (2026-06-25) — rewrite of a kit's prompt: AST-graph + Tarjan SCC;
  load-time-vs-lazy ranking; minimum-feedback-edge breaks; leave fully-lazy cycles
  alone; return-clean. 12 SCCs / exactly 1 load-time cycle. *(Records the author's
  own first-draft slip — ranking SCCs by size — as a cautionary case.)*
