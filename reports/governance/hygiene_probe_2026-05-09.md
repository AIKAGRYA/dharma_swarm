# Hygiene Probe 2026-05-09

## Scope

Read-only source probe against a deliberately suspect Python slice:

- `dharma_swarm/providers_extended.py`
- `dharma_swarm/vector_store.py`
- `dharma_swarm/scout_framework.py`
- `dharma_swarm/file_lock.py`
- `dharma_swarm/guardian_crew.py`

Total slice size: 2,911 LOC.

Fallow is JS/TS-only, so it was run separately against `dashboard/`.

All generated evidence is under:

- `quality-reports/hygiene-probe-2026-05-09/`

No source code was changed by this probe.

## Python Detector Results

| Check | Result |
| --- | --- |
| `compileall` | Pass |
| `pytest` targeted direct tests | 68 passed, 3 skipped |
| `pytest` vector-store integration slice | 6 passed |
| `pytest` file-lock integration | 1 passed |
| `pytest` with coverage over target modules | 75 passed, 3 skipped, 28 deselected |
| `pyright` | 12 errors, 7 warnings |
| `mypy` | 7 errors |
| `vulture` | 37 findings |
| `radon cc` | 12 C/D complexity blocks, average C |
| `bandit` | 20 findings: 17 low, 3 medium |
| `semgrep` | 3 blocking governance findings |

Coverage from the targeted test pass:

| Module | Coverage |
| --- | ---: |
| `dharma_swarm/file_lock.py` | 85% |
| `dharma_swarm/guardian_crew.py` | 21% |
| `dharma_swarm/providers_extended.py` | 51% |
| `dharma_swarm/vector_store.py` | 57% |
| `dharma_swarm/scout_framework.py` | not imported |
| Total | 49% |

## What Passed Anyway

The important result is not that the tests pass; it is that tests pass while the quality mesh still finds real risk:

- `providers_extended.py` passes its provider tests while Vulture flags three intentional-but-ugly unreachable `yield` statements after `raise NotImplementedError`.
- `vector_store.py` passes vector tests while Pyright flags an invalid `Embedder.fit_add` call, Bandit flags SQL-string construction and swallowed exceptions, Semgrep flags a local `_utc_now()` copy, and coverage shows large unexercised branches.
- `scout_framework.py` has no direct targeted test coverage in this probe, and both mypy and Pyright flag the `StigmergyStore.leave_mark` call as signature drift.
- `guardian_crew.py` has a working hygiene test and generated Guardian report, but Pyright flags `importlib.util`, Radon flags two D-grade functions, Bandit flags swallowed exceptions, Semgrep flags direct `~/.dharma` ownership, and coverage is only 21%.
- `file_lock.py` looks comparatively healthy: tests pass, coverage is 85%, and findings are mostly dead-code/noise candidates.

This is exactly the gap the mesh is meant to expose: normal unit tests prove selected happy paths, not architectural health.

## Current Slop Router Scores

Using `quality-reports/hygiene-probe-2026-05-09/normalized-findings.jsonl` with `scripts/governance/slop_verify.py`:

| Module | Probability | Action | Blocks |
| --- | ---: | --- | --- |
| `dharma_swarm/guardian_crew.py` | 0.54 | `block_regression` | false |
| `dharma_swarm/vector_store.py` | 0.46 | `warn` | false |
| `dharma_swarm/scout_framework.py` | 0.23 | `log` | false |
| `dharma_swarm/file_lock.py` | 0.20 | `log` | false |
| `dharma_swarm/providers_extended.py` | 0.12 | `log` | false |

These are intentionally non-blocking because the probe marks findings as pre-existing rather than introduced regressions.

## Raw Tool Findings Worth Acting On

Highest-confidence items:

- `dharma_swarm/scout_framework.py:455`: `StigmergyStore.leave_mark` is called with obsolete keyword arguments. Both mypy and Pyright agree.
- `dharma_swarm/vector_store.py:476`: `Embedder` does not define `fit_add`; the call is wrapped in broad exception swallowing, so tests can miss it.
- `dharma_swarm/vector_store.py:608`, `:612`, `:618`: Bandit flags string-built SQL deletion queries. The placeholder list is probably internally generated, but this should be reviewed or suppressed with evidence.
- `dharma_swarm/vector_store.py:40`: Semgrep flags a local `_utc_now()` copy despite the canonical `dharma_swarm.utils.time.utc_now`.
- `dharma_swarm/guardian_crew.py:672`: Semgrep flags direct `~/.dharma` access outside the canonical owner allowlist.
- `dharma_swarm/guardian_crew.py:140`: Radon reports `run_auditor` as D-grade complexity.
- `dharma_swarm/guardian_crew.py:369`: Radon reports `run_router_probe` as D-grade complexity.

## Fallow Dashboard Pass

Fallow 2.67.0 ran against `dashboard/` in 883 ms.

| Category | Count |
| --- | ---: |
| Total static issues | 111 |
| Unused files | 1 |
| Unused exports | 83 |
| Unused types | 23 |
| Unused class members | 3 |
| Duplicate exports | 1 |
| Circular dependencies | 0 |
| Boundary violations | 0 |
| Unlisted dependencies | 0 |
| Unused dependencies | 0 |
| Duplicate clone groups | 64 |
| Duplicate clone families | 30 |
| Health findings above threshold | 159 |
| Critical health findings | 57 |
| High health findings | 34 |
| Moderate health findings | 68 |

Top Fallow complexity/CRAP hotspots:

- `src/app/dashboard/agents/[id]/config/page.tsx:73` `AgentConfigPage`, CRAP 4830.0
- `src/components/layout/OperatorMicrographics.tsx:376` `OperatorMicrographics`, CRAP 3422.0
- `src/app/dashboard/qwen35/page.tsx:276` `Qwen35Page`, CRAP 3306.0
- `src/app/dashboard/telemetry/page.tsx:31` `TelemetryPage`, CRAP 2862.0
- `src/app/dashboard/agents/[id]/page.tsx:15` `AgentOverviewPage`, CRAP 2550.0

Dashboard ESLint also failed independently with 6 errors and 26 warnings. Key errors:

- Conditional React hooks in `src/app/dashboard/agents/[id]/config/page.tsx`.
- `Math.random()` during render in `MicrographicsScene.tsx`.
- `Math.random()` during render in `OperatorMicrographics.tsx`.

Fallow and ESLint are complementary: Fallow finds dead-code/complexity/duplication architecture debt; ESLint catches React correctness.

## Mesh Weaknesses Found By The Probe

The mesh itself needs three fixes before its scores are safe to promote:

1. `parse_bandit` currently misparses Bandit `Location: path:line:col` rows. The parser stores paths like `./dharma_swarm/vector_store.py:608` and line numbers as columns, so per-module security scores are undercounted.
2. `parse_coverage` does not parse coverage.py branch tables with `Stmts Miss Branch BrPart Cover`, so low coverage did not enter normalized findings.
3. `parse_pyright_json` preserves Pyright's zero-based line number directly, so normalized Pyright findings are one line too high/low depending on display context.

These are parser/normalization fixes, not detector failures. The raw tools found the issues; the governance layer loses some signal while routing them.

## Interpretation

The current mesh is already useful as an advisory system. It found real risks in code that passes tests, and it separated Python slop governance from Fallow's JS/TS-only coverage. The strongest immediate value is as a reviewer assistant and nightly triage source.

It is not yet robust enough for automatic blocking beyond narrowly selected gates. The deterministic floor works, but the router needs parser correctness fixes, coverage ingestion, and better signal weighting before probabilities can be treated as enforcement-grade.

Recommended next fixes:

1. Fix Bandit path/line parsing.
2. Fix coverage branch-table parsing.
3. Fix Pyright line normalization.
4. Re-run this exact probe and compare slop probabilities.
5. Then address `scout_framework.py:455`, `vector_store.py:476`, and the `guardian_crew.py` direct state ownership finding.
