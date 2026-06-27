---
id: complexity-inflation-scan
version: 0.1.0
theme: 17-code-health-metrics
status: tested
reproduce: "python docs/stop-the-slop/probe/probe.py complexity <pkg>  # routes to radon"
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

**Target:** `dharma_swarm/`, 2026-06-27. Tool: **radon 6.0.1** (the named ground
truth), via `python docs/stop-the-slop/probe/probe.py complexity dharma_swarm`.

- **12,058 blocks analyzed; 227 with cc>20.** Worst, ranked by radon cc:

  | cc | function | location |
  |---:|---|---|
  | **231** | `main` | `dgc_cli.py:1303` |
  | 96 | `tick` | `swarm.py:2093` |
  | 88 | `run_task` | `agent_runner.py:2091` |
  | 87 | `analyze_repo` | `xray.py:424` |
  | 85 | `check` | `telos_gates.py:408` |
  | 83 | `resolve_runtime_provider_config` | `runtime_provider.py:163` |

- **Reading it (cyclomatic vs cognitive — the distinction that matters here):**
  `dgc_cli.main` at **cc=231** is the #1 liability by a wide margin — 2.4× the next
  function. But its *shape* matters: it's a flat argparse command dispatcher (a long
  `if cmd == …: elif …:` ladder), so its **cognitive** load is lower than its
  cyclomatic number suggests — the correct fix is mechanical: replace the ladder
  with a **command table** (`{name: handler}`), turning one cc=231 function into a
  one-line lookup plus N small, independently-testable handlers.
  `swarm.tick` (cc=96) and `agent_runner.run_task` (cc=88) are the opposite — deeply
  *nested* control flow inside god-object modules, where high cyclomatic **and** high
  cognitive complexity coincide; extract the nested arms into named handlers.
- **Why the number moved from a prior draft:** an earlier version of this demo used a
  homemade AST branch-count and reported `swarm.tick cc~88` as the worst function,
  never surfacing `dgc_cli.main` (231) at all. Routing to radon — the tool this
  prompt names — corrected the ranking. That is the whole thesis: **run the named
  instrument, don't approximate it.** Confirm with `radon cc -n D` in CI.

## Changelog

- **v0.1.0** (2026-06-27) — regenerated from radon (the named tool) via the `probe/`
  runner. Corrects the worst-function ranking: `dgc_cli.main` **cc=231** is the real
  #1 (a flat dispatch — cognitive < cyclomatic), not `swarm.tick` (cc=96) as the
  prior AST-proxy draft claimed. Counts updated to radon's: 227 blocks cc>20 of
  12,058. Demonstrates the cyclomatic-vs-cognitive distinction on a real divergent case.
- **v0.0.1** (2026-06-25) — complexity scan (McCabe/Campbell), real tool / AST,
  cyclomatic-vs-cognitive distinction, decomposition + test-impact.
