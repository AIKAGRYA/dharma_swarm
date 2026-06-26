---
id: complexity-inflation-scan
version: 0.0.1
theme: 17-code-health-metrics
status: tested
invariant: >
  Complexity is the cost of understanding, and it's measurable (cyclomatic =
  independent paths; cognitive = nesting/branching load). A function past the
  threshold is a comprehension and test-coverage liability — you cannot cover N
  paths with M<N tests. Rank by measured complexity on the hottest paths; don't
  guess "this looks gnarly."
lineage:
  - "McCabe 1976 — cyclomatic complexity = independent paths through a function"
  - "Campbell — Cognitive Complexity (nesting/breaks penalize understanding)"
  - "Dijkstra — testing can't show absence; high path count = untestable in full"
ground_truth_tools: ["radon cc / lizard", "AST branch count", "test coverage per high-cc function"]
returns_clean: true
---

## Prompt

> Find **complexity-inflation** hotspots. The invariant (McCabe): cyclomatic
> complexity = independent paths; you can't cover N paths with fewer tests, so a
> high-cc function is both hard to understand and impossible to fully test. **Run a
> real complexity tool** (`radon cc`, `lizard`) or AST branch-count — don't eyeball.
>
> **Output:** functions over a threshold (e.g. cc>15), ranked, with `file:line`,
> the measured cc, and *why* it's complex (deep nesting? a dispatch switch? mixed
> concerns?). Recommend the **decomposition** (extract methods / table-dispatch /
> guard clauses) and note its test impact. **Return clean** if the distribution is
> healthy. Don't flag an inherently-branchy-but-flat dispatch the same as deeply
> nested logic — cite cognitive complexity, not just cyclomatic.

## Why it's built this way

McCabe makes "too complex" a number, and the path-count argument ties it directly
to testability (Dijkstra). The discipline is measuring with a real tool and
distinguishing *cyclomatic* (paths) from *cognitive* (nesting) so a flat dispatch
isn't mis-flagged like deeply-nested spaghetti.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. Tool: AST branch-count (radon absent).

- **10,422 functions analyzed; 161 with cc>20.** Worst:
  `swarm.py:2093 tick` **cc~88** · `agent_runner.py:2091 run_task` **cc~80** ·
  `tui_legacy.py:809 _handle_command` **cc~78** · `lifecycle.py:125 cmd_swarm`
  cc~72 · `tui/app.py:1995 _dispatch_async` cc~71.
- **Reading it:** `swarm.tick` (cc~88, inside the 3,227-line `swarm.py`) is the #1
  comprehension+test liability — 88 independent paths means no realistic test suite
  covers them all. It's also a god-object hotspot, so it's the same target the
  slop-index and decomposition-plan converge on. Fix: extract the dispatch arms of
  `tick`/`run_task` into named handlers (table dispatch), turning one cc~88 function
  into a router + N small testable handlers. Confirm with `radon cc -n D` in CI.

## Changelog

- **v0.0.1** (2026-06-25) — complexity scan (McCabe/Campbell), real tool / AST,
  cyclomatic-vs-cognitive distinction, decomposition + test-impact. Tested on
  `dharma_swarm`: 161 fns cc>20, worst `swarm.tick` cc~88 — converges with the
  god-object and slop-index findings.
