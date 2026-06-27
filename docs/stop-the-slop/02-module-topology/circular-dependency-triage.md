---
id: circular-dependency-triage
version: 0.1.1
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

**Target:** `dharma_swarm/` (546 modules with internal import edges), 2026-06-27.
Tool: stdlib AST import-graph + Tarjan SCC (same algorithm as `grimp`/`pydeps`;
none were installed). **This run is now produced by the executable runner**, not
hand-transcribed — `python docs/stop-the-slop/probe/probe.py cycles dharma_swarm`:

```
| Import cycles | 1 load-time cyclic SCC(s); 11 total cyclic SCC(s); largest load-time = 3 modules | RED | HIGH | grimp / import-linter contract |
  LOAD-TIME: dharma_swarm → providers → router_v1
```

The `cycles` signal classifies each edge by where it sits in the AST: a
module-level import is load-time, a function-local one is lazy, and — critically —
an import under `if TYPE_CHECKING:` is type-only and excluded from load-time (a bug
caught in the runner's own self-tests: without that exclusion, the post-merge
provider-routing rewrite reported 4 spurious load-time cycles instead of 1).

### The honest two-pass result (and a self-correction worth keeping)

**Pass 1 — full import graph (load + lazy edges): 11 cyclic SCCs** (was 12 before
main merged the provider-routing consolidation; the load-time core below is
unchanged). This is the number a naive run reports, and the first draft of this
demo ranked those SCCs by *size* (an 8-module SCC, several 7-module SCCs, …) and implied several were
boot-risks. **That was this prompt's own trap, committed by its author** — size
is not danger. A cycle only threatens boot if it closes through *load-time*
edges, and `TYPE_CHECKING` imports never execute at runtime and must be excluded.

**Pass 2 — load-time-only graph, `TYPE_CHECKING` excluded: exactly 1 genuine
load-time cycle.** All the apparent danger collapsed to a single 3-node core:

`dharma_swarm` (package `__init__`) → `providers` → `router_v1` → `dharma_swarm`

Verified module-level (load-time) edges on **this branch** (`claude/prompt-library-v0`),
re-confirmed 2026-06-27 by parsing each module's top-level body:
- `dharma_swarm/__init__.py:6` — `from dharma_swarm.providers import ClaudeCodeProvider, …` **[load-time]**
- `dharma_swarm/providers.py:76` — `from dharma_swarm.router_v1 import build_routing_signals, …` **[load-time]**
- `dharma_swarm/router_v1.py:16` — `from dharma_swarm import model_pool` **[load-time]** ← re-enters the package while `__init__` is still on line 6 (half-initialized-module trap)

The other **10 SCCs close only via lazy/deferred imports** (0 load-time edges) —
**already mitigated; do not refactor.** A heuristic prompt nags about all 11; the
disciplined one says *one* is real.

### Minimum break (proposed; verified on a branch, NOT yet on mainline)
Make the package's provider re-exports lazy (PEP 562 `__getattr__` in
`__init__.py`), so importing the package no longer drags the provider/router
graph into init time. One file, public API unchanged. This fix exists and was
verified to reach **0 load-time cycles** on the unmerged branch
`origin/claude/fix-provider-router-import-cycle`.

**Honesty correction (was an overclaim):** a prior draft of this demo said the fix
had "**Shipped**" and that the mainline load-time graph "is now a DAG." That is not
true on this branch or `main` — the three eager edges above are still present (I
re-read the files to confirm). The accurate statement: **fix proposed and verified
→ 0 on branch `claude/fix-provider-router-import-cycle`; unmerged; mainline still
carries exactly 1 load-time cycle.**

### Verdict
Full graph: not a DAG (11 SCCs). Genuine boot risk on mainline: **1**
(provider/router core), still present here; a verified fix exists on an unmerged
branch. The other 10 are lazy-mitigated and were correctly left alone. The lesson
the prompt enforces — *rank by when the cycle resolves, not by how big it looks* —
is the exact thing its own first draft got wrong, and the rigorous load-time pass
caught it.

## Changelog

- **v0.1.1** (2026-06-27) — demo is now **runner-generated** (`probe.py cycles`),
  not hand-transcribed. Wired the `cycles` signal (AST import graph + iterative
  Tarjan) into the runner with a `TYPE_CHECKING`-exclusion fix that its self-tests
  pin (a planted load-time cycle goes RED; a `TYPE_CHECKING` or function-local
  back-edge does not). Reconciled the full-graph count 12 → **11** after main
  merged the provider-routing consolidation; the single load-time core
  (`dharma_swarm → providers → router_v1`) is unchanged and re-verified at the
  cited `file:line`s.
- **v0.1.0** (2026-06-27) — corrected an overclaim: the provider/router fix is
  verified on the unmerged branch `claude/fix-provider-router-import-cycle`, NOT on
  mainline. Re-confirmed the 3 eager edges still present on this branch by parsing
  module-level bodies (`__init__.py:6`, `providers.py:76`, `router_v1.py:16`).
  Mainline still carries exactly 1 load-time cycle.
- **v0.0.1** (2026-06-25) — initial rewrite of a kit's circular-dependency prompt.
  Replaced "read the import lines" with AST-graph + Tarjan SCC; added the
  load-time-vs-lazy classification as the primary ranking axis; mandated
  minimum-feedback-edge break points at `file:line`; required leaving fully-lazy
  (already-mitigated) cycles alone; added return-clean. Tested against
  `dharma_swarm/`: full graph has 12 SCCs but a rigorous load-time-only pass
  (`TYPE_CHECKING` excluded) found **exactly 1** genuine load-time cycle
  (provider/router core) — the other 11 close via lazy imports. The fix shipped
  and re-running the pass confirms 0 load-time cycles. (The demo also records the
  author's own first-draft slip — ranking SCCs by size — as the cautionary case.)
