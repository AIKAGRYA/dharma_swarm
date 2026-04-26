# 11 Promotion PR Readiness

Date: 2026-04-26
Branch: `promote/lf5-runtime-spine`
Worktree: `/Users/dhyana/promotion_worktrees/dharma_swarm_lf5_promotion`
Baseline: `origin/main` at `da6a4fa`

## 1. Commits On promote/lf5-runtime-spine

```text
da0774a fix(guardian): detect empty structured runtime tables
b3bf897 docs(audit): record hook environment gap
1ab1c8a fix(runtime): record task result artifacts
b20d661 docs(audit): summarize end-to-end coherence gaps
35b9521 fix(runtime): record task claims and delegation runs
```

This is the intended promotion spine: Slice 1 runtime claims/runs, Slice 2 task-result artifacts, Slice 3 Guardian invariant, plus the narrow audit synthesis and hook-gap note.

## 2. Tests Passed Across Slices 1-3

Final promotion pass run after Slice 3 commit:

```text
python -m compileall dharma_swarm tests
python -m pytest tests/test_session_ledger.py tests/test_runtime_state.py tests/test_bootstrap_loops.py tests/test_guardian_crew.py -q --tb=short
```

Results:

- `compileall`: passed.
- focused pytest pass: 26 passed, 1 warning in 23.46s.
- Warning: pre-existing `PytestConfigWarning: Unknown config option: timeout`.

Slice reports also recorded the same targeted suite passing at each slice boundary:

- Slice 1: session ledger 3 passed, runtime state 4 passed, bootstrap loops 15 passed.
- Slice 2: session ledger 3 passed, runtime state 4 passed, bootstrap loops 15 passed, `git diff --check` passed.
- Slice 3: session ledger 3 passed, runtime state 4 passed, bootstrap loops 15 passed, guardian crew 4 passed, `git diff --check` passed.

## 3. Runtime Tables Now Covered

The branch now covers the first runtime structured-table triad:

- `session_events`: existing SessionLedger projection remains preserved.
- `task_claims`: Slice 1 records dispatch/running/completed/failed claim state.
- `delegation_runs`: Slice 1 records running/completed/failed execution state.
- `artifact_records`: Slice 2 records completed task-result artifacts with stable IDs.

Temp runtime DB proofs show:

- after dispatch: `task_claims == 1`.
- after execution: `delegation_runs == 1`.
- after execution: `artifact_records == 1`.
- second tick: no duplicate task claim, delegation run, or artifact row for the same completed task.

## 4. Guardian Invariant Now Enforced

Slice 3 adds `run_ledger_watcher(state_dir)` in `dharma_swarm/guardian_crew.py`.

The watcher reads the state-local RuntimeStateStore SQLite database in read-only mode and emits:

- `DEGRADED` when `session_events > 100` and `task_claims == delegation_runs == artifact_records == 0`.
- `BLOCKER` when `session_events > 1000` and all three structured producer tables are still zero.
- no finding when any structured producer row exists.

Tests seed only temp runtime DBs and include a `Path.home()` monkeypatch that raises if the watcher attempts to consult live `~/.dharma`.

## 5. Files Changed

Compared with `origin/main`, this branch changes:

```text
M  dharma_swarm/guardian_crew.py
M  dharma_swarm/orchestrator.py
A  reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md
A  reports/audit/runtime_truth/04_SLICE1_RUNTIME_SPINE_RESULT.md
A  reports/audit/runtime_truth/05_SLICE1_REVIEW.md
A  reports/audit/runtime_truth/06_SLICE2_ARTIFACT_RESULT.md
A  reports/audit/runtime_truth/07_SLICE2_REVIEW.md
A  reports/audit/runtime_truth/08_HOOK_ENV_GAP.md
A  reports/audit/runtime_truth/09_SLICE3_LEDGER_WATCHER_RESULT.md
A  reports/audit/runtime_truth/10_SLICE3_REVIEW.md
M  tests/test_bootstrap_loops.py
A  tests/test_guardian_crew.py
M  tests/test_session_ledger.py
```

After this readiness artifact is staged later, `reports/audit/runtime_truth/11_PROMOTION_PR_READINESS.md` should be included as a docs-only PR readiness commit.

## 6. Files Intentionally Not Promoted

The branch did not promote or edit:

- `build_registry.py`
- `build_authority.py`
- `task_contract.py`
- `task_board_mirror.py`
- `frontier_council.py`
- `agent_runner.py`
- dashboard/API code
- identity/routing code
- Shakti/Darwin code
- AGNI/NATS code
- live LF5 source tree under `/Users/dhyana/dharma_swarm_lf5`
- dirty main tree under `/Users/dhyana/dharma_swarm`
- live state under `~/.dharma`

The raw end-to-end audit archive is also intentionally left untracked for a later archive decision.

## 7. Remaining Untracked Reports

Current untracked files intentionally not included in the runtime promotion commits:

```text
reports/audit/end_to_end/10_RUNTIME_SPINE_MAP.md
reports/audit/end_to_end/20_AGENT_IDENTITY_COHERENCE.md
reports/audit/end_to_end/30_MODEL_ROUTING_COHERENCE.md
reports/audit/end_to_end/40_MEMORY_SUBSTRATE_MAP.md
reports/audit/end_to_end/50_GUARDIAN_OBSERVABILITY_MAP.md
reports/audit/end_to_end/60_API_DASHBOARD_COHERENCE.md
reports/audit/end_to_end/70_SHAKTI_DARWIN_LOOP_MAP.md
reports/audit/end_to_end/80_REPO_GOVERNANCE_MAP.md
reports/audit/end_to_end/90_TEST_COVERAGE_BY_LOOP.md
reports/audit/end_to_end/100_DOCS_DRIFT_REGISTER.md
reports/audit/runtime_truth/03_MATRIX_REVIEW.md
```

These can stay local or become a later audit-archive commit. They should not be mixed into the runtime-spine PR unless the PR explicitly expands to include the full audit archive.

## 8. Pre-Commit Hook Gap

The local pre-commit hook reports no `.pre-commit-config.yaml` in this worktree and blocks normal commit unless overridden.

Slice 3 was committed with:

```text
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "fix(guardian): detect empty structured runtime tables"
```

This is a tooling/environment gap, not a runtime-spine issue. Keep it separate in a CI/tooling branch instead of mixing it into this promotion branch.

## 9. Daemon And Live LF5 Status

Read-only process check:

```text
PID 20465 running for 08:18:53
Command: /Users/dhyana/dharma_swarm_lf5/.venv/bin/dgc orchestrate-live
```

No daemon stop, restart, checkout, live LF5 edit, dirty main edit, or live `~/.dharma` test path was used by this PR-readiness step.

## 10. Recommendation

Recommendation: open the first LF5 promotion PR from `promote/lf5-runtime-spine` after committing this readiness artifact if desired.

The final focused promotion test pass is green. A broader whole-repo pytest run may still be useful before push if the operator wants extra confidence, but the accepted Slice 1-3 gates are satisfied.
