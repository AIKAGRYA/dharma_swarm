# 06 Slice 2 Artifact Result

Date: 2026-04-26
Branch: `promote/lf5-runtime-spine`
Worktree: `/Users/dhyana/promotion_worktrees/dharma_swarm_lf5_promotion`

## 1. Files Changed

- `dharma_swarm/orchestrator.py`
- `tests/test_bootstrap_loops.py`
- `reports/audit/runtime_truth/06_SLICE2_ARTIFACT_RESULT.md`

No dashboard, identity, routing, Shakti, Darwin, docs drift, AGNI, NATS, live LF5, `build_registry.py`, or new artifact registry was touched.

## 2. Artifact Writer Used Or Added

Used existing `RuntimeStateStore.record_artifact(ArtifactRecord)`.

No `RuntimeStateStore` writer method was added.

Patch details:

- Added `Orchestrator._record_runtime_artifact(...)`.
- Passed the existing delegation `runtime_run_id` into `_persist_result(...)`.
- After `_persist_result()` writes the shared task-result artifact file, it records a stable artifact row:
  - `artifact_id = artifact_task_result_<task_id>`
  - `artifact_kind = task_result`
  - `payload_path = <shared task result artifact path>`
  - `manifest_path = <provenance json path>`
  - `checksum = sha256(result)`
  - `promotion_state = ephemeral`

The stable artifact id lets `record_artifact()` upsert the same completed task result instead of creating duplicate rows.

## 3. Before/After artifact_records Row Count

Isolated temp runtime DB proof:

```text
before {'session_events': 0, 'task_claims': 0, 'delegation_runs': 0, 'artifact_records': 0}
after_dispatch {'dispatched': 1, 'task_claims': 1, 'artifact_records': 0}
after_execution {'session_events': 5, 'task_claims': 1, 'delegation_runs': 1, 'artifact_records': 1}
after_second_tick {'dispatched': 0, 'artifact_records': 1}
```

The proof used a temp state directory and temp `runtime.db`; it did not use `~/.dharma/state/runtime.db`.

The proof command emitted `lancedb not installed — run: pip install lancedb`; this was non-fatal and did not affect the row assertions.

## 4. Idempotence Proof

`tests/test_bootstrap_loops.py::test_task_lifecycle` now asserts:

- `artifact_records == 0` before dispatch.
- `artifact_records >= 1` after task completion.
- The artifact row has `artifact_kind == "task_result"`.
- The artifact row belongs to the completed task id.
- The artifact payload path exists.
- A second tick has `dispatched == 0` and keeps `artifact_records` at the same count.

## 5. Tests Run

- `python -m compileall dharma_swarm tests` -> passed
- `python -m pytest tests/test_session_ledger.py -q --tb=short` -> 3 passed, 1 pytest config warning
- `python -m pytest tests/test_runtime_state.py -q --tb=short` -> 4 passed, 1 pytest config warning
- `python -m pytest tests/test_bootstrap_loops.py -q --tb=short` -> 15 passed, 1 pytest config warning
- `git diff --check` -> passed

The pytest warning is the pre-existing `Unknown config option: timeout`.

## 6. Next Unresolved Structured Producer

The next unresolved structured producer is `memory_facts` from completed task output or a read-before-propose path that cites `session_events` / `memory_facts`.

Recommended next slice: decide the smallest memory producer/read-before-propose acceptance test before adding any new memory substrate.
