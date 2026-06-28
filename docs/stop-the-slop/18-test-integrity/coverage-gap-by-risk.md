---
id: coverage-gap-by-risk
version: 0.0.1
theme: 18-test-integrity
status: tested
invariant: >
  Coverage % is a vanity metric; what matters is whether the HIGH-RISK code is tested.
  100% coverage of trivial getters and 0% of the payment logic is a failing suite that
  reports green. Rank untested code by risk (complexity × blast-radius × consequence-of-
  failure), and target the gaps that matter. A line covered by a test that asserts
  nothing isn't covered either (see test-mirrors-implementation).
lineage:
  - "Weyuker — test adequacy criteria; not all coverage is equal"
  - "risk-based testing — allocate test effort by failure cost × likelihood"
  - "Dijkstra — testing shows presence of bugs; aim it where bugs are costliest"
ground_truth_tools: ["coverage.py per-module", "cross with complexity + fan-in (risk)", "which high-risk modules have no/weak tests"]
returns_clean: true
---

## Prompt

> Audit **coverage gaps by risk**, not by percentage. The invariant (Weyuker, risk-based
> testing): a green coverage number that skips the high-risk code is a failing suite.
> Cross **coverage** (coverage.py per module) with **risk** (complexity + fan-in +
> consequence-of-failure) and surface the **high-risk, low-coverage** quadrant — the code
> most likely to fail and most damaging when it does, that no test guards. For each: the
> module, its risk signals, current coverage, and the behavior a test should pin. Ignore
> low-risk gaps (a trivial helper at 0% is fine). **Return clean** if the high-risk set is
> well-covered. (Pair with `test-mirrors-implementation`: a covered-but-not-asserted line
> is still a gap.)

## Why it's built this way

Coverage % optimizes the wrong thing (it rewards testing trivia). Risk-based testing aims
effort at failure-cost × likelihood; the discipline is the **2D cross** (coverage ×
risk), which turns "we're at 78%" into "the telos gate logic is at 40% and it's the
highest-stakes module."

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **The cross (route to instruments):** risk signals are already computed by sibling
  prompts — complexity (`swarm.tick` cc~88, `agent_runner.run_task` cc~80), fan-in
  (`models` 156), and consequence (the **telos gates**, the spine dispatch, the merge
  gate are high-stakes). Coverage comes from `coverage.py`. The audit overlays them:
  **high-complexity + high-stakes + low-coverage = the priority gaps.**
- **Disciplined output:** rather than a global %, produce the high-risk/low-coverage
  table — e.g. "run `coverage.py` and check `telos_gates.py`, the `swarm.tick` dispatch,
  and `agent_runner.run_task`: these are the highest risk×complexity modules; any of them
  under-covered is a must-fix, regardless of the repo-wide number." Names the instrument
  + the risk-ranked targets; the exact coverage numbers are UNASSESSED without the
  `coverage.py` run.

## Changelog

- **v0.0.1** (2026-06-25) — coverage-gap-by-risk (Weyuker/risk-based): cross coverage ×
  risk, target high-risk/low-coverage, ignore trivial gaps. Tested on `dharma_swarm`:
  risk-ranked the high-stakes modules (telos gates, dispatch, cc~88 functions) as the
  coverage targets; coverage numbers honestly UNASSESSED pending `coverage.py`.
