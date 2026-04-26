# 09 Slice 3 Ledger Watcher Result

Date: 2026-04-26
Branch: `promote/lf5-runtime-spine`
Worktree: `/Users/dhyana/promotion_worktrees/dharma_swarm_lf5_promotion`

## 1. Files Changed

- `dharma_swarm/guardian_crew.py`
- `tests/test_guardian_crew.py`
- `reports/audit/runtime_truth/09_SLICE3_LEDGER_WATCHER_RESULT.md`

No dashboard, identity, routing, Shakti, Darwin, docs drift, AGNI, NATS, LF5 source tree, dirty main tree, new ledger, new DB, or new report substrate was touched.

## 2. Watcher Function Name

Added `run_ledger_watcher(state_dir: Path)`.

Guardian cycle wiring now runs it alongside the existing auditor, loop watcher, and router probe. Report synthesis includes `LEDGER_WATCHER` findings in severity counts and the "Checked By" section.

## 3. Thresholds Implemented

The watcher reads the state-local runtime DB from:

- `<state_dir>/state/runtime.db`
- `<state_dir>/runtime.db`

It does not consult `Path.home()` or default to live `~/.dharma`.

Tables counted:

- `session_events`
- `task_claims`
- `delegation_runs`
- `artifact_records`

Findings:

- `DEGRADED` when `session_events > 100` and `task_claims == delegation_runs == artifact_records == 0`.
- `BLOCKER` when `session_events > 1000` and `task_claims == delegation_runs == artifact_records == 0`.
- No finding when any structured producer rows exist.

Each finding includes a clear title, runtime DB path, exact counts, and a fix hint to wire existing `RuntimeStateStore` producers instead of creating a new ledger.

## 4. Test DB Proof

All tests use temp runtime DBs under `tmp_path/.dharma/state/runtime.db`.

Proof cases:

- Seeded `session_events = 101`, all structured tables empty -> one `DEGRADED` finding.
- Seeded `session_events = 1001`, all structured tables empty -> one `BLOCKER` finding.
- Seeded `session_events = 1001`, plus one row each in `task_claims`, `delegation_runs`, and `artifact_records` -> no finding.
- Patched `Path.home()` to raise during watcher execution -> watcher still returned the expected temp-DB `DEGRADED` finding, proving it does not read live `~/.dharma`.

## 5. Tests Run

- `python -m compileall dharma_swarm tests` -> passed
- `python -m pytest tests/test_session_ledger.py -q --tb=short` -> 3 passed, 1 pytest config warning
- `python -m pytest tests/test_runtime_state.py -q --tb=short` -> 4 passed, 1 pytest config warning
- `python -m pytest tests/test_bootstrap_loops.py -q --tb=short` -> 15 passed, 1 pytest config warning
- `python -m pytest tests/test_guardian_crew.py -q --tb=short` -> 4 passed, 1 pytest config warning
- `git diff --check` -> passed

After a comment-only cleanup in `guardian_crew.py`, `compileall` and `tests/test_guardian_crew.py` were rerun and still passed.

The pytest warning is the pre-existing `Unknown config option: timeout`.

## 6. Next Remaining Observability Gap

The next observability gap is surfacing structured runtime health through operator-visible API/dashboard or telemetry views:

- prove telemetry projection after a real orchestrator dispatch;
- expose claim/run/artifact counts by session;
- assert API task state agrees with runtime claim/run state for the same task.

Do this after Slice 3 review; do not start dashboard/API work inside the Guardian slice.
