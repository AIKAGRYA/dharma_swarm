# Guardian Warning Result

Date: 2026-04-27
Branch: `fix/guardian-warning-cases`
Issue: #29 Slice 3.1 Guardian warnings

## Summary

Extended Guardian with read-only warning checks beyond the existing `LEDGER_WATCHER` blocker/degraded thresholds.

Implemented:

- Warning when repo-root `GUARDIAN_REPORT.md` exists and is older than 24 hours.
- Warning when the configured `.dharma` state dir contains an unregistered top-level feature directory.
- Warning when `session_events` has 24h growth but `task_claims`, `delegation_runs`, and `artifact_records` have no 24h growth.

No new substrate was added. The new state-directory registration boundary is an in-code allowlist used only for read-only warning detection.

Post-PR #46 maintenance:

- Rebased `fix/guardian-warning-cases` onto `origin/main` at `70230e4f89e4e4a3e1bec6bddd6760b9ffc59313`.
- Reproduced the `module-budget` failure locally: `dharma_swarm/guardian_crew.py` crossed `778 -> 1012` lines.
- Narrowly extracted Guardian repo/state warning helpers to `dharma_swarm/guardian_runtime_checks.py`.
- Kept `guardian_crew.py` as the Guardian orchestrator/report synthesizer; it is now 881 lines.
- Did not touch `orchestrator.py` or `runtime_lifecycle.py`.

## Files Changed

- `dharma_swarm/guardian_crew.py`
- `dharma_swarm/guardian_runtime_checks.py`
- `tests/test_guardian_crew.py`
- `reports/ops/GUARDIAN_WARNING_RESULT.md`

No `orchestrator.py` or `runtime_lifecycle.py` changes.

## Tests

Passed:

```bash
python -m compileall dharma_swarm tests
```

Passed:

```bash
python -m pytest tests/test_guardian_crew.py -q --tb=short
```

Result: `8 passed, 1 warning`.

Passed:

```bash
python -m pytest tests/test_runtime_lifecycle.py tests/test_bootstrap_loops.py tests/test_runtime_state.py -q --tb=short
```

Result: `20 passed, 1 warning`.

Passed:

```bash
python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD
```

Result: `Module line-budget check OK.`

## Notes

- Tests use temp state dirs only.
- Warning tests monkeypatch `Path.home()` where relevant to guard against live `~/.dharma` reads.
- Existing `LEDGER_WATCHER` blocker and degraded cases continue to assert one finding each.
- Local pre-commit hooks were not usable in this worktree: the hook Python lacked `pytest`, `scripts/uplift_guards/run_pre_commit.py` was absent on this baseline, and Semgrep hit a local CA trust-store error. The focused pytest and compileall checks above passed.
