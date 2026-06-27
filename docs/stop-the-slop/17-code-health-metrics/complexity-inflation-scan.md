---
id: complexity-inflation-scan
version: 0.0.2
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

**Target:** `dharma_swarm/`, corrected 2026-06-27. Tool: **`radon cc` (the named
ground truth)** — `pip install radon && radon cc dharma_swarm/ -s -n D`.

> **Correction (v0.0.2).** The v0.0.1 demo used a homemade AST branch-count proxy
> *instead of* running `radon` — the exact pattern-matching this library condemns —
> and got the headline wrong. An adversarial reviewer caught it. The numbers below
> are now from radon itself.

- **12,058 functions analyzed; 227 with cc>20 (radon grade D+).** Worst:
  **`dgc_cli.py:1303 main` — cc 231 (F)** · `swarm.py:2093 SwarmManager.tick` cc 96 ·
  `agent_runner.py:2091 run_task` cc 88 · `xray.py:424 analyze_repo` cc 87 ·
  `telos_gates.py:408 TelosGatekeeper.check` cc 85. *(All reproducible via
  `runner/slop_probe.py complexity` — see below.)*
- **The #1 is `dgc_cli.main` at cc 231 — 2.4× `swarm.tick`** — and the proxy missed
  it entirely. It is a **flat argparse dispatch**: very high *cyclomatic* (231 paths)
  but modest *cognitive* load (shallow, not nested) — which is exactly the
  cyclomatic-vs-cognitive nuance this prompt names, and exactly why the fix differs:
  a flat dispatcher splits into a command table + handlers (mechanical), whereas a
  deeply-nested function (`swarm.tick`, `run_task`) needs guard-clauses + extracted
  logic. Both also sit inside god objects, so they converge with the decomposition
  and slop-index findings.
- **Lesson baked in:** the proxy also *overcounted* `cmd_swarm` (claimed ~72; radon
  says **17, grade C** — not a hotspot). Substituting an unvalidated proxy for a
  tool that installs in 3 seconds is the cardinal sin; **run radon.**

## Changelog

- **v0.0.2** (2026-06-27) — **correction after adversarial review.** v0.0.1 ran a
  homemade AST proxy instead of the named `radon` and got the headline wrong (missed
  `dgc_cli.main` cc 231; overcounted `cmd_swarm` 72→17; counts 10,422/161 → radon
  12,058/227). Re-ran radon; corrected the demo; baked the cyclomatic-vs-cognitive
  point into the `dgc_cli.main` flat-dispatch case. The library failing its own
  route-to-ground-truth rule is now a documented cautionary case.
- **v0.0.1** (2026-06-25) — complexity scan (McCabe/Campbell); cyclomatic-vs-cognitive
  distinction, decomposition + test-impact. *(Demo numbers superseded by v0.0.2.)*
