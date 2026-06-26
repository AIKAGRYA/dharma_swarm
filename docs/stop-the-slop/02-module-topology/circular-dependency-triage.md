---
id: circular-dependency-triage
version: 0.0.1
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
`grimp`/`pydeps`; none were installed). **12 cyclic SCCs found.** (A heuristic
"read the imports" prompt finds the 2-module ones and misses the 7–8 module
chains entirely — and can't tell the boot-fragile ones from the harmless ones.)

### #1 — LOAD-TIME (boot risk) · provider/router · SCC size 7

Members: `dharma_swarm` (package `__init__`), `providers`, `provider_policy`,
`router_v1`, `runtime_provider`, `smart_router`, `swarm_router`. **9 load-time
edges.** The knot closes through the package root:

- `dharma_swarm/__init__.py:6` — `from dharma_swarm.providers import …` **[load-time]**
- `dharma_swarm/providers.py:62` — `from dharma_swarm.provider_policy import …` **[load-time]**
- `dharma_swarm/provider_policy.py:31` — `from dharma_swarm.smart_router import …` **[load-time]**
- `dharma_swarm/smart_router.py:28` — `from dharma_swarm.router_v1 import …` **[load-time]**
- `dharma_swarm/router_v1.py:16` — `from dharma_swarm import …` **[load-time]** ← closes the loop through `__init__`

**Minimum break:** `router_v1.py:16` (`from dharma_swarm import …`). It imports the
package root *while the root's `__init__` is still executing line 6* — the textbook
half-initialized-module trap. Defer it inside the function that uses it (or import
the specific submodule, not the package). One-line cut; breaks the back-edge with
the least churn. Secondary option: make `__init__.py:6` lazy.

### #2 — LOAD-TIME · ontology/organism · SCC size 8

Members include `ontology`, `ontology_hub`, `ontology_runtime`, `telic_seam`,
`lineage`, `organism`, `telos_gates`, `dharma_attractor`. 6 load-time edges;
e.g. `telic_seam.py:41 → ontology_runtime` and `ontology_runtime.py:17 →
ontology_hub` both `[load-time]`. **Minimum break:** defer `telic_seam.py:40–41`
(it eagerly pulls three ontology modules; it's a consumer, not a definer — the
natural place to cut).

### #3–#7 — MIXED / smaller load-time cycles
`memory_kernel` context cluster (size 7, 7 load edges), evolution/jikoku cluster
(size 7), `consistency_guard↔guardian_crew↔watchdog↔room_health` (size 4),
`evolution_roster↔model_pool↔ollama_config` (size 3), `surface_specs` cluster
(size 3). Each has a named one-line break.

### ALREADY MITIGATED (do not refactor)
`build_engine ↔ custodians ↔ foreman` (SCC size 3) — **0 load-time edges, all 3
lazy.** The authors already deferred these imports; the cycle never fires at boot.
A heuristic prompt would tell you to "fix" it. The correct call is: **leave it.**

### Verdict
The import graph is **not** a DAG (12 SCCs). The actionable set is the load-time
cycles led by the provider/router knot through `__init__.py` — a genuine
boot-fragility with a one-line break. One of the 12 is already correctly mitigated
and should be left alone.

## Changelog

- **v0.0.1** (2026-06-25) — initial rewrite of a kit's circular-dependency prompt.
  Replaced "read the import lines" with AST-graph + Tarjan SCC; added the
  load-time-vs-lazy classification as the primary ranking axis; mandated
  minimum-feedback-edge break points at `file:line`; required leaving fully-lazy
  (already-mitigated) cycles alone; added return-clean. Tested against
  `dharma_swarm/` (12 cycles; correctly ranked the `__init__`-mediated provider
  cycle top and the lazy `build_engine` cycle as mitigated).
