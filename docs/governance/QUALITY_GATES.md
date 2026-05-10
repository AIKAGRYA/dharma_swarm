# Quality Gates

Status: canonical hygiene-gate policy
Last reviewed: 2026-05-09

This file is the single source of truth for the Dharmic Hygiene Mesh gate
contract. Tool configs and CI may implement this policy, but this file owns the
coherence claims.

## Targets

- Python version: `3.11`
- Package target: `dharma_swarm`
- Local report directory: `quality-reports/`
- Ledger target: `.dharma/slop_ledger/<date>.jsonl`
- Base comparison ref: `origin/main` unless a command explicitly supplies a
  different base

Current live-state check: `pyrightconfig.json`, `pyproject.toml`, `Makefile`,
and `.github/workflows/quality.yml` agree on Python `3.11` and package target
`dharma_swarm`.

## Canonical Reports

| Tool | Canonical report |
| --- | --- |
| vulture | `quality-reports/vulture.txt` |
| radon complexity | `quality-reports/radon-cc.txt` |
| radon maintainability | `quality-reports/radon-mi.txt` |
| bandit | `quality-reports/bandit.txt` |
| mypy | `quality-reports/mypy.txt` |
| pyright | `quality-reports/pyright.json` |
| pytest coverage | `quality-reports/coverage.xml` and `quality-reports/pytest-cov.txt` |
| Fallow | `quality-reports/fallow.json` in CI; `quality-reports/fallow.txt` for human diagnostics |

The router must not advertise a report as routed unless it has a parser for the
actual emitted filename and format.

## Modes And Budgets

| Mode | Scope | Budget | Policy |
| --- | --- | --- | --- |
| pre-commit | changed files | `< 5 sec` | advisory only |
| ci | changed files plus context | `< 90 sec` | advisory until promoted by ratchet |
| hourly | incremental reports | `< 2 min` | advisory loop closure |
| nightly | full repo | `< 10 min` | expensive evidence joins allowed |

If a detector misses its budget, move it to the next slower mode or require
cached evidence.

## Ratchet Policy

- New detectors start advisory.
- One detector family can warn but cannot block.
- Blocking requires a regression versus base plus at least two independent
  detector families.
- Secrets, owned ERROR Semgrep rules, and explicitly protected authority-surface
  checks may block immediately when their owning policy already says so.
- Promote one gate at a time after ledger evidence shows acceptable
  false-positive behavior.
- Never auto-merge, auto-delete, or mutate authority surfaces from a quality
  router.

## Router Contract

`scripts/governance/route_quality_findings.py` is the quality-ingress router.
It must normalize findings before aggregation and preserve:

- tool
- detector family
- issue type
- path and line when available
- severity
- confidence
- mode
- base ref
- commit
- raw or structured evidence
- suggested action

Unknown or unsupported report formats must be reported as unsupported, not
silently dropped.
