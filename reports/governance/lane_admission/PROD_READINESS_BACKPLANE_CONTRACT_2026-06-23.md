# Production-Readiness Backplane Contract — 2026-06-23

## Purpose

Make the production-grade review verdicts machine-consumable by the cockpit UI and by future agents, so "checker SHIPPABLE" is never confused with "production-grade / safe to close".

Source of truth (durable):
- `reports/governance/prod_readiness/PROD_GRADE_REVIEW_RESULTS_2026-06-22.{md,json}`
- `reports/governance/prod_readiness/PROD_READINESS_FINAL_CLOSEOUT_2026-06-23.{md,json}`
- `reports/governance/prod_readiness/RENDER_CHECK_DISCREPANCY_RESOLVED_2026-06-23.md`

## Two distinct status axes (must not be collapsed)

1. `checker_status` (from `check_track_status.py`): SHIPPABLE | IN_PROGRESS
2. `production_verdict` (from human/agent prod review): one of the enum below

The cockpit MUST display both. A track that is `SHIPPABLE` + `KEEP_ACTIVE_PROD_HARDENING` must NOT be shown as "ready to close".

## production_verdict enum

- `CLOSE_READY_WITH_FOLLOWUP`
- `KEEP_ACTIVE_PROD_HARDENING`
- `SPLIT_BEFORE_CLOSE`
- `DO_NOT_CLOSE`
- `CLOSE_READY` (none currently qualify)

## Current canonical verdicts (origin/main 839fd25f4, 7 active / max 10)

| Track | checker_status | production_verdict | closure_risk |
|---|---|---|---|
| runtime-truth-reconciliation-2026-06 | SHIPPABLE | CLOSE_READY_WITH_FOLLOWUP | low-medium |
| runtime-truth-nats-2026-06 | SHIPPABLE | KEEP_ACTIVE_PROD_HARDENING | high |
| truth-graph-platform-2026-06 | SHIPPABLE | KEEP_ACTIVE_PROD_HARDENING | medium-high |
| composer-holon-spine-longrun-2026-06 | SHIPPABLE | SPLIT_BEFORE_CLOSE | medium |
| provider-routing-consolidation-2026-06 | SHIPPABLE | CLOSE_READY_WITH_FOLLOWUP | low-medium |
| runtime-truth-spine-adoption-2026-06 | IN_PROGRESS (7/8) | KEEP_ACTIVE (blocker: bypass_allowlist_empty) | n/a |
| loop-closure-2026-06 | IN_PROGRESS (10/11) | KEEP_ACTIVE (blocker: RETROSPECTIVE.md missing) | n/a |

## Carried-forward correction (do not lose)

`render_active_track_includes.py --check` failing is an INTERPRETER/DEPENDENCY artifact, not stale governance content:
- system `python3` (no PyYAML) -> FAIL (fallback parser emits spurious whitespace-only diff)
- repo `.venv/bin/python` (PyYAML 6.0.3) -> PASS

Action: do NOT re-render managed blocks to "fix" this. The real fix is dependency-honesty in governance entrypoints (use repo venv or fail loud). This single fix clears three separately-reported "blockers" (render check, make orient, runtime-truth render) because they share one root cause: a clean tree lacks the dependency env.

## Cockpit display rule

For each track card, the backplane supplies `{checker_status, production_verdict, closure_risk, blocking_followups[]}`. The UI renders production_verdict as the dominant badge for closure decisions; checker_status is secondary.
