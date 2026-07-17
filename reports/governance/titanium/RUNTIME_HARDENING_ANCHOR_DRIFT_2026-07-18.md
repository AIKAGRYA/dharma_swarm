# Titanium Runtime Hardening — Anchor Drift Receipt

**Doc role (per `docs/AGENTS.md`):** `witness` — current-state receipt for the `hardening/five-pillar-synthesis` worktree. Subordinate to `docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md` and `docs/plans/TITANIUM_RUNTIME_HARDENING_WPS_2026-07-17.md`.

**Worktree:** `/Users/dhyana/ds-wt-hardening-20260717`  
**Branch:** `hardening/five-pillar-synthesis`  
**Purpose:** prevent stale audit anchors from driving unsafe implementation.

## Summary

The old audit anchor for TIT-020 (`_ATTEMPT_IDENTITY_METADATA_KEYS` / `_clear_attempt_identity_metadata`) is **not present** on the current hardening branch. That means the exact earlier patch (“remove `idempotency_key` from the attempt wipe list”) is already structurally drifted away. The invariant still matters: future retry-cleanup code must not remove `idempotency_key` or equivalent intent keys.

## Verification commands

```bash
grep -R "_ATTEMPT_IDENTITY_METADATA_KEYS\|_clear_attempt_identity_metadata\|pop(.*idempotency_key\|del .*idempotency_key" -n dharma_swarm/orchestrator.py dharma_swarm | head -120
.venv/bin/python -m pytest -q tests/governance/test_titanium_runtime_hardening_fitness.py
```

## Observed result

- No current source hit for the old retry-cleanup helper/list in `dharma_swarm/orchestrator.py`.
- Added `tests/governance/test_titanium_runtime_hardening_fitness.py` to lock the TIT-020 invariant structurally.
- The same guard locks the frontier-capacity-first doctrine so WP-A does not regress into cost-minimizing model downgrades.

## Resulting implementation guidance

- WP-B/TIT-020 should not blindly apply the stale “remove list entry” patch on this branch.
- Next WP-B code step should focus on positive intent-key derivation and provider/message-bus propagation, not only deletion of the old cleanup list.
- WP-A/TIT-016 should implement a `FrontierCapacityGate`-compatible rail name or wrapper; retaining `check_global_cost_cap()` internally is acceptable only if docs/tests prove it cannot downgrade authorized frontier lanes.


## Follow-up implementation receipt — TIT-020 positive invariant

After this drift receipt, the branch added the positive default-key fix:

- `dharma_swarm/spine/identity.py::intent_idempotency_key()` now derives missing idempotency keys from stable intent/origin material.
- `ExecutionIdentity.new()` no longer defaults to `idem_{run_id}` when `idempotency_key` is omitted.
- The default key intentionally excludes retry/attempt fields: `run_id`, `claim_id`, `trace_id`, `agent_id`, and `session_id`.
- Explicit caller-provided idempotency keys remain preserved for compatibility.

Verification command:

```bash
.venv/bin/python -m pytest -q tests/test_runtime_state_invariants.py tests/test_runtime_state_recovery.py tests/test_spine_mapping_receipts.py tests/test_runtime_lifecycle.py::test_runtime_lifecycle_preserves_structured_row_idempotence tests/test_spine_identity.py tests/governance/test_titanium_runtime_hardening_fitness.py
```

Observed result: `19 passed`.

## Follow-up implementation receipt — TIT-021 message bus wedge

The branch also closed the `message_bus.send` wedge class called out in WP-B/TIT-021:

- `MessageBus.send()` now passes a finite `stale_after_seconds` value to the runtime idempotency begin call.
- If an existing idempotency record prevents execution, `send()` verifies the idempotency record exists and only returns success when a completed record points to a real `messages` row.
- Stale/started/incomplete records now fail closed with `RuntimeError` instead of returning the attempted message id as if the send happened.

Verification command:

```bash
.venv/bin/python -m pytest -q tests/test_runtime_state_recovery.py tests/test_message_bus.py tests/test_runtime_truth_spine_adoption.py tests/test_runtime_truth_spine_v1.py tests/governance/test_titanium_runtime_hardening_fitness.py
.venv/bin/ruff check dharma_swarm/message_bus.py tests/test_runtime_state_recovery.py
```

Observed result: `31 passed`; ruff passed.

## Follow-up implementation receipt — TIT-024 agent-runner path confinement

The branch added the first WP-C/TIT-024 confinement guard for local tool paths:

- `_resolve_local_tool_path()` now resolves model-supplied paths against the selected workdir and rejects final paths outside that root.
- The guard rejects parent traversal and absolute host paths outside the workspace.
- Relative paths and absolute paths inside the workdir still resolve normally.

Verification command:

```bash
.venv/bin/python -m pytest -q tests/test_agent_runner_path_confinement.py tests/test_agent_runner.py::test_build_prompt_uses_active_memory_recall_by_default tests/test_agent_runner.py::test_build_prompt_prefers_local_state_dir_when_available tests/governance/test_titanium_runtime_hardening_fitness.py
git diff --check
```

Observed result: `8 passed`; diff check passed. Ruff over the entire legacy `agent_runner.py` still reports pre-existing lint issues unrelated to this packet (`E402` import placement and an unused `mem` local), so this receipt scopes verification to the new path-confinement behavior.
