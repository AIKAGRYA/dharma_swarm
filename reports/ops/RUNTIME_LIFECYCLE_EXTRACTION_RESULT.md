# Runtime Lifecycle Extraction Result

Date: 2026-04-27
Branch: `refactor/runtime-lifecycle-producers`
Worktree: `/Users/dhyana/promotion_worktrees/dharma_swarm_runtime_lifecycle_producers`
Base: `origin/main` at `834b8c20694b05bcbc95f3d781e5cce45c4fea0e`
Issue: `#33`

## Repo State Lock

Used the clean detached `origin/main` snapshot at:

- `/Users/dhyana/promotion_worktrees/dharma_swarm_repo_state_now`

That worktree matched local `origin/main` exactly and was clean before extraction.

## Scope Completed

Added:

- `dharma_swarm/runtime_lifecycle.py`
- `tests/test_runtime_lifecycle.py`

Changed:

- `dharma_swarm/orchestrator.py`

Not changed:

- dashboard or API files
- provider or routing files
- LF5-only modules
- runtime state schema
- memory facts or other runtime producers

## What Moved

Centralized from `orchestrator.py` into `dharma_swarm/runtime_lifecycle.py`:

- task claim recording
- delegation run recording
- artifact record recording
- the private helper logic that those three producers depended on:
  - runtime state store lookup
  - runtime run id allocation
  - runtime metadata envelope assembly
  - runtime status timestamp coercion
  - datetime normalization for stored claim/run fields

`Orchestrator` now owns a single `RuntimeLifecycle(self._ledger)` helper and delegates those writes through it.

## Behavior

No intended behavior change.

The extraction preserves:

- existing `claim_id` / `run_id` / `artifact_id` semantics
- idempotent upsert behavior in `RuntimeStateStore`
- `RuntimeStateStore` as the canonical structured runtime store
- existing metadata payload shapes
- artifact persistence source tag values:
  - `source: orchestrator`
  - `source: orchestrator._persist_result`

## Acceptance Check

- `orchestrator.py` line count decreased:
  - before: `2720`
  - after: `2529`
  - net: `-191`
- Slice 1/2 tests still pass: yes
- artifact/task/run idempotence preserved: yes
- `RuntimeStateStore` remains canonical: yes
- no new substrate introduced: yes

## Verification

```bash
python3 -m py_compile \
  dharma_swarm/runtime_lifecycle.py \
  dharma_swarm/orchestrator.py \
  tests/test_runtime_lifecycle.py
```

Result: passed.

```bash
pytest -q \
  tests/test_bootstrap_loops.py \
  tests/test_runtime_state.py \
  tests/test_runtime_lifecycle.py
```

Result: `20 passed, 1 warning`.

Warning was pre-existing:

- `PytestConfigWarning: Unknown config option: timeout`

## Test Coverage Notes

Existing slice coverage preserved in:

- `tests/test_bootstrap_loops.py`
- `tests/test_runtime_state.py`

New direct extraction coverage:

- `tests/test_runtime_lifecycle.py`

The new test verifies that the extracted helper preserves structured-row idempotence for:

- `task_claims`
- `delegation_runs`
- `artifact_records`

## Diff Summary

```text
 dharma_swarm/orchestrator.py | 211 ++-----------------------------------------
 1 file changed, 10 insertions(+), 201 deletions(-)
```

Additional new files:

- `dharma_swarm/runtime_lifecycle.py`
- `tests/test_runtime_lifecycle.py`

## Remaining Follow-on Work

This extraction did not:

- add `memory_facts`
- change runtime schema ownership
- change task settlement behavior
- change routing
- change dashboard/API surfaces

Natural next extractions after this one:

- result persistence helpers around `_persist_result()`
- remaining claim-preparation helpers if the runtime spine continues to be modularized
- any future runtime producer additions should land in `runtime_lifecycle.py`, not back in `orchestrator.py`
