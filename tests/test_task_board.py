"""Tests for dharma_swarm.task_board."""

import asyncio
import copy
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from uuid import UUID

import pytest
import aiosqlite

import dharma_swarm.task_board as task_board_mod
import dharma_swarm.task_board_campaign_guard as campaign_guard_mod
from dharma_swarm.models import GateCheckResult, GateDecision
from dharma_swarm.models import Task, TaskPriority, TaskStatus
from dharma_swarm.mission_control_execution_support import owner_execution_identity
from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.task_board import TaskBoard, TaskBoardError
from dharma_swarm.task_board_campaign_guard import (
    runtime_idempotency_authority_snapshot_sha256,
    runtime_run_authority_snapshot_sha256,
)


@pytest.fixture
async def board(tmp_path):
    b = TaskBoard(tmp_path / "tasks.db")
    await b.init_db()
    return b


@pytest.fixture
async def projection_runtime(tmp_path):
    store = RuntimeStateStore(tmp_path / "projection-runtime.db")
    await store.init_db()
    return store


@pytest.fixture
async def persisted_quarantined_task(board):
    task = await board.create("Audited fake result")
    async with board._open() as db:
        await db.execute(
            "UPDATE tasks SET status = ?, metadata = ? WHERE id = ?",
            (
                "quarantined_fake_result",
                (
                    '{"original_status":"completed",'
                    '"quarantine_reason":"fake_tool_call_xml_result_pre_fix"}'
                ),
                task.id,
            ),
        )
        await db.commit()
    return task.id


def _campaign_attempt_metadata(
    task_id: str,
    *,
    generation: int = 0,
    maximum: int = 2,
) -> dict:
    authority = {
        "schema_version": "dharma.sadhana.campaign_task_authority.v5",
        "campaign_id": "campaign-exact",
        "mission_id": "campaign-exact",
        "goal_id": "G01",
        "portfolio_contract_sha256": "sha256:" + "a" * 64,
        "goal_contract_sha256": "sha256:" + "b" * 64,
        "manifest_digest": "sha256:" + "c" * 64,
        "agent_roster_sha256": "d" * 64,
        "effect_mode": "read_only",
        "campaign_end": "2026-09-02T00:00:00+00:00",
        "agent_name": "exact-seat",
        "claimed_principal": "agent-exact",
        "dispatch_key": f"dispatch-{generation}",
        "request_id": f"request-{generation}",
        "workspace_path": "workspaces/exact",
        "allowed_files": ["workspaces/exact"],
        "max_usd": 0.0,
        "authority_ref": f"lease-{generation}",
        "authority_digest": "sha256:" + f"{generation + 1:x}" * 64,
        "attempt_generation": generation,
        "max_attempts": maximum,
        "observed_input_manifest_digest": "sha256:" + "e" * 64,
        "held_out_oracle_manifest_digest": "sha256:" + "f" * 64,
        "operator_control_semantics_sha256": "sha256:" + "0" * 64,
        "operator_control_authority_binding_sha256": "sha256:" + "4" * 64,
        "deployment_authority_topology_sha256": "sha256:" + "5" * 64,
        "deployment_authority_credential_clarification_sha256": ("sha256:" + "6" * 64),
        "observed_input_ref": {
            "receipt_id": "observed-receipt",
            "receipt_sha256": "sha256:" + "1" * 64,
            "artifact_id": "observed-artifact",
            "artifact_record_sha256": "sha256:" + "2" * 64,
            "content_sha256": "sha256:" + "3" * 64,
        },
        "route_lock": {
            "schema_version": "dharma.sadhana.campaign_route_lock.v1",
            "task_id": task_id,
            "principal_id": "agent-exact",
            "provider": "ollama",
            "model": "fixture-model",
            "allow_provider_routing": False,
        },
    }
    governance = {
        key: value
        for key, value in authority.items()
        if key
        not in {
            "agent_name",
            "claimed_principal",
            "dispatch_key",
            "request_id",
            "authority_ref",
            "authority_digest",
            "route_lock",
        }
    }
    governance["schema_version"] = "dharma.sadhana.campaign_governance.v4"
    governance["forbidden_files"] = []
    owner = {
        "schema_version": "dharma.mission_control.owner_execution.v2",
        "backend": "orchestrator",
        "mission_id": authority["mission_id"],
        "task_id": task_id,
        "dispatch_key": authority["dispatch_key"],
        "attempt_generation": generation,
        "run_id": f"run-{generation}",
        "claim_id": f"claim-{generation}",
        "idempotency_key": f"idem-{generation}",
        "trace_id": f"trace-{generation}",
        "correlation_id": f"correlation-{generation}",
    }
    return {
        "attempt_ceiling": maximum,
        "attempt_generation": generation,
        "mission_campaign_authority": authority,
        "mission_control_governance": governance,
        "mission_control_owner_execution": owner,
        **{
            key: owner[key]
            for key in (
                "run_id",
                "claim_id",
                "idempotency_key",
                "trace_id",
                "correlation_id",
            )
        },
    }


async def _new_bound_campaign_task(
    board: TaskBoard,
    title: str,
    *,
    generation: int = 0,
    maximum: int = 2,
    without_owner: bool = False,
) -> tuple[Task, dict]:
    bootstrap = {
        "sadhana_bootstrap_schema": "dharma.sadhana.mission_bootstrap.v1",
        "campaign_id": "campaign-exact",
        "goal_id": "G01",
        "mission_task_creation_hash": "sha256:" + "9" * 64,
    }
    task = await board.create(title, metadata=bootstrap)
    metadata = {
        **bootstrap,
        **_campaign_attempt_metadata(
            task.id,
            generation=generation,
            maximum=maximum,
        ),
    }
    if without_owner:
        for key in (
            "mission_control_owner_execution",
            "runtime_run_id",
            "run_id",
            "claim_id",
            "idempotency_key",
            "trace_id",
            "correlation_id",
            "attempt_generation",
        ):
            metadata.pop(key, None)
    bound = await board.compare_and_swap_campaign_metadata(task, metadata=metadata)
    assert bound is not None
    return bound, metadata


def _next_attempt(metadata: dict) -> tuple[dict, dict, dict]:
    authority = copy.deepcopy(metadata["mission_campaign_authority"])
    authority.update(
        {
            "attempt_generation": 1,
            "dispatch_key": "dispatch-1",
            "request_id": "request-1",
            "authority_ref": "lease-1",
            "authority_digest": "sha256:" + "2" * 64,
        }
    )
    governance = copy.deepcopy(metadata["mission_control_governance"])
    governance["attempt_generation"] = 1
    routing = {
        "campaign_effect_mode": "read_only",
        "requires_tooling": False,
        "allow_provider_routing": False,
        "provider_allowlist": ["ollama"],
        "preferred_provider": "ollama",
        "preferred_model": "fixture-model",
    }
    return authority, governance, routing


async def _typed_campaign_status(
    board: TaskBoard,
    task_id: str,
    *,
    new_status: TaskStatus,
    metadata: dict,
):
    expected = await board.get(task_id)
    assert expected is not None
    updated = await board.compare_and_swap_campaign_status(
        expected,
        new_status=new_status,
        assigned_to="agent-exact",
        metadata=metadata,
    )
    assert updated is not None
    return updated


@pytest.mark.asyncio
async def test_create_task(board):
    task = await board.create("Build feature", description="Do the thing")
    assert task.title == "Build feature"
    assert task.status == TaskStatus.PENDING
    assert len(task.id) == 16


@pytest.mark.asyncio
async def test_create_task_persists_metadata(board):
    trace_id = "trc_test_123"
    task = await board.create(
        "Metadata task",
        metadata={"trace_id": trace_id, "created_via": "test"},
    )
    loaded = await board.get(task.id)
    assert loaded is not None
    assert loaded.metadata["trace_id"] == trace_id
    assert loaded.metadata["created_via"] == "test"


@pytest.mark.asyncio
async def test_get_task(board):
    task = await board.create("Test task")
    found = await board.get(task.id)
    assert found is not None
    assert found.title == "Test task"


@pytest.mark.asyncio
async def test_get_nonexistent(board):
    assert await board.get("nonexistent") is None


@pytest.mark.asyncio
async def test_persisted_quarantined_fake_result_is_readable_and_terminal(
    board,
    persisted_quarantined_task,
):
    task_id = persisted_quarantined_task

    loaded = await board.get(task_id)
    assert loaded is not None
    assert loaded.status == TaskStatus.QUARANTINED_FAKE_RESULT
    assert loaded.metadata["original_status"] == "completed"

    assert task_id in {task.id for task in await board.list_tasks()}
    quarantined = await board.list_tasks(status=TaskStatus.QUARANTINED_FAKE_RESULT)
    assert [task.id for task in quarantined] == [task_id]

    stats = await board.stats()
    assert stats["quarantined_fake_result"] == 1
    assert stats["total"] == 1
    assert task_id not in {task.id for task in await board.get_ready_tasks()}
    assert task_board_mod._TRANSITIONS[TaskStatus.QUARANTINED_FAKE_RESULT] == set()

    with pytest.raises(
        TaskBoardError,
        match="Invalid transition: quarantined_fake_result -> pending",
    ):
        await board._set_status(task_id, TaskStatus.PENDING)
    for status in (
        TaskStatus.QUARANTINED_FAKE_RESULT,
        TaskStatus.QUARANTINED_FAKE_RESULT.value,
    ):
        with pytest.raises(TaskBoardError, match="audit-only terminal status"):
            await board.update_task(task_id, status=status)

    unchanged = await board.get(task_id)
    assert unchanged is not None
    assert unchanged.status == TaskStatus.QUARANTINED_FAKE_RESULT


@pytest.mark.asyncio
async def test_update_task_rejects_unknown_raw_status_without_mutating(board):
    task = await board.create("Reject unknown status")

    with pytest.raises(TaskBoardError, match="Invalid task status"):
        await board.update_task(task.id, status="not_a_real_status")

    unchanged = await board.get(task.id)
    assert unchanged is not None
    assert unchanged.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_list_tasks(board):
    await board.create("Task 1")
    await board.create("Task 2")
    tasks = await board.list_tasks()
    assert len(tasks) == 2


@pytest.mark.asyncio
async def test_list_tasks_by_status(board):
    t = await board.create("Task 1")
    await board.assign(t.id, "agent1")
    pending = await board.list_tasks(status=TaskStatus.PENDING)
    assigned = await board.list_tasks(status=TaskStatus.ASSIGNED)
    assert len(pending) == 0
    assert len(assigned) == 1


@pytest.mark.asyncio
async def test_full_lifecycle(board):
    task = await board.create("Lifecycle test")
    assert task.status == TaskStatus.PENDING

    task = await board.assign(task.id, "agent-1")
    assert task.status == TaskStatus.ASSIGNED
    assert task.assigned_to == "agent-1"

    task = await board.start(task.id)
    assert task.status == TaskStatus.RUNNING

    task = await board.complete(task.id, result="done!")
    assert task.status == TaskStatus.COMPLETED
    assert task.result == "done!"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prior", "terminal"),
    [
        (TaskStatus.ASSIGNED, TaskStatus.CANCELLED),
        (TaskStatus.RUNNING, TaskStatus.FAILED),
    ],
)
async def test_campaign_pre_effect_failure_is_exact_owner_cas(
    board: TaskBoard,
    prior: TaskStatus,
    terminal: TaskStatus,
) -> None:
    task, metadata = await _new_bound_campaign_task(board, "Campaign task")
    task = await _typed_campaign_status(
        board, task.id, new_status=TaskStatus.ASSIGNED, metadata=metadata
    )
    if prior is TaskStatus.RUNNING:
        task = await _typed_campaign_status(
            board, task.id, new_status=TaskStatus.RUNNING, metadata=metadata
        )

    result = await board.resolve_campaign_pre_effect_failure(
        task.id,
        expected_status=prior,
        expected_agent_id="agent-exact",
        expected_metadata=metadata,
        authenticated_principal="agent-exact",
    )
    resolved = await board.get(task.id)

    assert result == "indeterminate"
    assert resolved is not None
    assert resolved.status is terminal
    assert resolved.assigned_to == "agent-exact"
    assert resolved.metadata["campaign_dispatch_recovery"] == {
        "schema_version": "dharma.sadhana.dispatch_recovery.v2",
        "state": "dispatch_indeterminate",
        "task_id": task.id,
        "authenticated_principal": "agent-exact",
        "prior_status": prior.value,
        "provider_task_scheduled": False,
        "attempt_generation": 0,
        "max_attempts": 2,
        "dispatch_key": "dispatch-0",
        "request_id": "request-0",
        "authority_ref": "lease-0",
        "authority_digest": "sha256:" + "1" * 64,
        "run_id": "run-0",
        "claim_id": "claim-0",
        "idempotency_key": "idem-0",
    }


@pytest.mark.asyncio
async def test_campaign_pre_effect_failure_never_overwrites_drift(
    board: TaskBoard,
) -> None:
    task, metadata = await _new_bound_campaign_task(board, "Campaign task")
    assigned = await _typed_campaign_status(
        board,
        task.id,
        new_status=TaskStatus.ASSIGNED,
        metadata=metadata,
    )
    async with board._open() as db:
        await db.execute(
            "UPDATE tasks SET metadata = ? WHERE id = ?",
            (json.dumps({"owner": "concurrent"}), task.id),
        )
        await db.commit()

    result = await board.resolve_campaign_pre_effect_failure(
        task.id,
        expected_status=assigned.status,
        expected_agent_id="agent-exact",
        expected_metadata=assigned.metadata,
        authenticated_principal="agent-exact",
    )
    unchanged = await board.get(task.id)

    assert result == "conflict"
    assert unchanged is not None
    assert unchanged.status is TaskStatus.ASSIGNED
    assert unchanged.metadata == {"owner": "concurrent"}


@pytest.mark.asyncio
async def test_campaign_pending_recovery_witness_is_byte_stable(
    board: TaskBoard,
) -> None:
    task, metadata = await _new_bound_campaign_task(board, "Campaign task")
    task = await board.get(task.id)
    assert task is not None

    result = await board.resolve_campaign_pre_effect_failure(
        task.id,
        expected_status=TaskStatus.PENDING,
        expected_agent_id=None,
        expected_metadata=task.metadata,
        authenticated_principal="agent-exact",
    )

    assert result == "pending"
    assert await board.get(task.id) == task


async def _indeterminate_campaign_task(
    board: TaskBoard,
    *,
    maximum: int = 2,
) -> tuple[object, dict]:
    task, metadata = await _new_bound_campaign_task(
        board,
        "Campaign attempt",
        maximum=maximum,
    )
    task = await _typed_campaign_status(
        board, task.id, new_status=TaskStatus.ASSIGNED, metadata=metadata
    )
    outcome = await board.resolve_campaign_pre_effect_failure(
        task.id,
        expected_status=TaskStatus.ASSIGNED,
        expected_agent_id="agent-exact",
        expected_metadata=metadata,
        authenticated_principal="agent-exact",
    )
    assert outcome == "indeterminate"
    terminal = await board.get(task.id)
    assert terminal is not None
    return terminal, metadata


@pytest.mark.asyncio
async def test_campaign_attempt_advance_is_exact_and_append_only(
    board: TaskBoard,
) -> None:
    terminal, original = await _indeterminate_campaign_task(board)
    authority, governance, routing = _next_attempt(original)

    result = await board.advance_campaign_dispatch_attempt(
        terminal.id,
        expected_status=TaskStatus.CANCELLED,
        expected_agent_id="agent-exact",
        expected_metadata=terminal.metadata,
        next_authority=authority,
        next_governance=governance,
        next_routing=routing,
    )

    assert result == "advanced"
    advanced = await board.get(terminal.id)
    assert advanced is not None
    assert advanced.status is TaskStatus.PENDING
    assert advanced.assigned_to is None
    assert advanced.metadata["attempt_generation"] == 1
    evidence = advanced.metadata["campaign_dispatch_attempt_history"]
    assert len(evidence) == 1
    assert evidence[0]["authority"] == original["mission_campaign_authority"]
    assert evidence[0]["owner_execution"] == original["mission_control_owner_execution"]


@pytest.mark.asyncio
async def test_campaign_attempt_advance_rejects_nested_history_forgery(
    board: TaskBoard,
) -> None:
    terminal, original = await _indeterminate_campaign_task(board, maximum=3)
    authority, governance, routing = _next_attempt(original)
    assert (
        await board.advance_campaign_dispatch_attempt(
            terminal.id,
            expected_status=TaskStatus.CANCELLED,
            expected_agent_id="agent-exact",
            expected_metadata=terminal.metadata,
            next_authority=authority,
            next_governance=governance,
            next_routing=routing,
        )
        == "advanced"
    )
    advanced = await board.get(terminal.id)
    assert advanced is not None
    generation_one = _campaign_attempt_metadata(terminal.id, generation=1, maximum=3)
    active = copy.deepcopy(advanced.metadata)
    owner = generation_one["mission_control_owner_execution"]
    active["mission_control_owner_execution"] = owner
    active.update(
        {
            key: owner[key]
            for key in (
                "run_id",
                "claim_id",
                "idempotency_key",
                "trace_id",
                "correlation_id",
            )
        }
    )
    assigned = await _typed_campaign_status(
        board,
        terminal.id,
        new_status=TaskStatus.ASSIGNED,
        metadata=active,
    )
    assert (
        await board.resolve_campaign_pre_effect_failure(
            terminal.id,
            expected_status=TaskStatus.ASSIGNED,
            expected_agent_id="agent-exact",
            expected_metadata=assigned.metadata,
            authenticated_principal="agent-exact",
        )
        == "indeterminate"
    )
    loaded = await board.get(terminal.id)
    assert loaded is not None
    forged = copy.deepcopy(loaded.metadata)
    forged["campaign_dispatch_attempt_history"][0]["authority"]["goal_id"] = "foreign"
    # Fixture-only pre-existing corruption. The generic API now rejects this
    # write; seed it below that boundary to prove typed recovery also fails.
    async with board._open() as db:
        cursor = await db.execute(
            "UPDATE tasks SET metadata = ? WHERE id = ? AND status = ?"
            " AND assigned_to IS ? AND result IS ? AND metadata = ?"
            " AND updated_at = ?",
            (
                board._coerce_db_value("metadata", forged),
                loaded.id,
                loaded.status.value,
                loaded.assigned_to,
                loaded.result,
                board._coerce_db_value("metadata", loaded.metadata),
                loaded.updated_at.isoformat(),
            ),
        )
        assert cursor.rowcount == 1
        await db.commit()
    next_authority = copy.deepcopy(authority)
    next_authority.update(
        attempt_generation=2,
        dispatch_key="dispatch-2",
        request_id="request-2",
        authority_ref="lease-2",
        authority_digest="sha256:" + "3" * 64,
    )
    next_governance = copy.deepcopy(governance)
    next_governance["attempt_generation"] = 2

    with pytest.raises(TaskBoardError, match="history authority is foreign"):
        await board.advance_campaign_dispatch_attempt(
            terminal.id,
            expected_status=TaskStatus.CANCELLED,
            expected_agent_id="agent-exact",
            expected_metadata=forged,
            next_authority=next_authority,
            next_governance=next_governance,
            next_routing=routing,
        )


@pytest.mark.asyncio
async def test_campaign_attempt_exhaustion_is_exact_row_fenced(
    board: TaskBoard,
) -> None:
    terminal, _ = await _indeterminate_campaign_task(board, maximum=1)
    bogus = copy.deepcopy(terminal.metadata["mission_campaign_authority"])

    assert (
        await board.advance_campaign_dispatch_attempt(
            terminal.id,
            expected_status=TaskStatus.CANCELLED,
            expected_agent_id="agent-exact",
            expected_metadata=terminal.metadata,
            next_authority=bogus,
            next_governance=terminal.metadata["mission_control_governance"],
            next_routing={},
        )
        == "exhausted"
    )

    # Simulate a pre-upgrade/concurrent writer that bypassed the now-typed
    # generic result guard. The attempt CAS must still fence the exact row.
    async with board._open() as db:
        cursor = await db.execute(
            "UPDATE tasks SET result = ? WHERE id = ? AND result = ?",
            ("concurrent-drift", terminal.id, terminal.result),
        )
        assert cursor.rowcount == 1
        await db.commit()
    assert (
        await board.advance_campaign_dispatch_attempt(
            terminal.id,
            expected_status=TaskStatus.CANCELLED,
            expected_agent_id="agent-exact",
            expected_metadata=terminal.metadata,
            next_authority=bogus,
            next_governance=terminal.metadata["mission_control_governance"],
            next_routing={},
        )
        == "conflict"
    )


@pytest.mark.asyncio
async def test_fail_and_retry(board):
    task = await board.create("Retry test")
    task = await board.assign(task.id, "agent")
    task = await board.start(task.id)
    task = await board.fail(task.id, error="timeout")
    assert task.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_cancel(board):
    task = await board.create("Cancel test")
    task = await board.cancel(task.id)
    assert task.status == TaskStatus.CANCELLED


@pytest.mark.asyncio
async def test_invalid_transition(board):
    task = await board.create("Bad transition")
    task = await board.assign(task.id, "a")
    task = await board.start(task.id)
    task = await board.complete(task.id)
    with pytest.raises(TaskBoardError, match="Invalid transition"):
        await board.assign(task.id, "b")


@pytest.mark.asyncio
async def test_dependencies(board):
    t1 = await board.create("Dep 1")
    t2 = await board.create("Dep 2", depends_on=[t1.id])

    deps = await board.get_dependencies(t2.id)
    assert t1.id in deps


@pytest.mark.asyncio
async def test_get_ready_tasks(board):
    t1 = await board.create("Blocker")
    t2 = await board.create("Blocked", depends_on=[t1.id])
    t3 = await board.create("Independent")

    ready = await board.get_ready_tasks()
    ready_ids = [t.id for t in ready]
    assert t3.id in ready_ids
    assert t1.id in ready_ids
    assert t2.id not in ready_ids  # blocked by t1

    # Complete t1, t2 should become ready
    await board.assign(t1.id, "a")
    await board.start(t1.id)
    await board.complete(t1.id)
    ready = await board.get_ready_tasks()
    ready_ids = [t.id for t in ready]
    assert t2.id in ready_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", [TaskStatus.FAILED, TaskStatus.CANCELLED])
async def test_failed_or_cancelled_dependency_never_makes_child_ready(
    board,
    terminal_status,
):
    parent = await board.create("Terminal prerequisite")
    child = await board.create("Must remain blocked", depends_on=[parent.id])

    if terminal_status == TaskStatus.FAILED:
        await board.assign(parent.id, "fixture-agent")
        await board.start(parent.id)
        await board.fail(parent.id, error="fixture failure")
    else:
        await board.cancel(parent.id)

    ready_ids = {task.id for task in await board.get_ready_tasks()}
    assert child.id not in ready_ids


@pytest.mark.asyncio
async def test_missing_dependency_is_rejected_without_persisting_child(board):
    with pytest.raises(TaskBoardError, match="missing dependency"):
        await board.create("Invalid child", depends_on=["missing-parent"])

    assert await board.get_by_title("Invalid child") is None


@pytest.mark.asyncio
async def test_batch_and_add_dependency_reject_missing_tasks(board):
    child = await board.create("Existing child")

    with pytest.raises(TaskBoardError, match="missing dependency"):
        await board.create_batch(
            [{"title": "Invalid batch child", "depends_on": ["missing-parent"]}]
        )
    with pytest.raises(TaskBoardError, match="missing dependency"):
        await board.add_dependency(child.id, "missing-parent")
    with pytest.raises(TaskBoardError, match="missing task"):
        await board.add_dependency("missing-child", child.id)


@pytest.mark.asyncio
async def test_task_board_connections_enforce_foreign_keys(board):
    async with board._open() as db:
        row = await (await db.execute("PRAGMA foreign_keys")).fetchone()
    assert row == (1,)


@pytest.mark.asyncio
async def test_legacy_dangling_dependency_keeps_child_blocked(board):
    child = await board.create("Legacy dangling child")

    # Simulate a pre-enforcement database row using a raw SQLite connection,
    # whose foreign-key checks are disabled by default.
    with sqlite3.connect(board._db_path) as db:
        db.execute(
            "INSERT INTO task_dependencies (task_id, depends_on_id) VALUES (?, ?)",
            (child.id, "missing-parent"),
        )

    ready_ids = {task.id for task in await board.get_ready_tasks()}
    assert child.id not in ready_ids


@pytest.mark.asyncio
async def test_create_batch_persists_metadata(board):
    tasks = await board.create_batch(
        [
            {
                "title": "Batch 1",
                "metadata": {"trace_id": "trc_batch_1", "batch_id": "b1"},
            },
            {
                "title": "Batch 2",
                "metadata": {"trace_id": "trc_batch_2", "batch_id": "b1"},
            },
        ]
    )
    loaded = await board.get(tasks[0].id)
    assert loaded is not None
    assert loaded.metadata["trace_id"] == "trc_batch_1"
    assert loaded.metadata["batch_id"] == "b1"


@pytest.mark.asyncio
async def test_update_task_serializes_metadata(board):
    task = await board.create("Serialize metadata")
    await board.update_task(task.id, metadata={"foo": "bar", "n": 1})
    loaded = await board.get(task.id)
    assert loaded is not None
    assert loaded.metadata["foo"] == "bar"
    assert loaded.metadata["n"] == 1


@pytest.mark.asyncio
async def test_requeue_failed_task_to_pending(board):
    task = await board.create("Retry me")
    await board.assign(task.id, "agent")
    await board.start(task.id)
    await board.fail(task.id, error="boom")

    requeued = await board.requeue(
        task.id,
        reason="retry",
        metadata={"retry_count": 1},
    )
    assert requeued.status == TaskStatus.PENDING
    assert requeued.assigned_to is None
    assert requeued.metadata["retry_count"] == 1


@pytest.mark.asyncio
async def test_generic_requeue_cannot_overwrite_newer_projection_history(board):
    task = await board.create("Stale retry writer")
    await board.assign(task.id, "agent")
    await board.start(task.id)
    await board.fail(task.id, error="boom")
    current_marker = {"run_id": "run-new", "projected_at": "new"}
    current_history = {"run-new": current_marker}
    current_metadata = {
        "retry_count": 1,
        "graph_reconcile_projection": current_marker,
        "graph_reconcile_projection_history": current_history,
    }
    async with board._open() as db:
        await db.execute(
            "UPDATE tasks SET metadata = ? WHERE id = ?",
            (json.dumps(current_metadata), task.id),
        )
        await db.commit()

    with pytest.raises(TaskBoardError, match="Graph projection receipts"):
        await board.requeue(
            task.id,
            reason="stale generic retry",
            metadata={
                "retry_count": 2,
                "graph_reconcile_projection": {
                    "run_id": "run-old",
                    "projected_at": "old",
                },
                "graph_reconcile_projection_history": {
                    "run-old": {"run_id": "run-old", "projected_at": "old"}
                },
            },
        )

    preserved = await board.get(task.id)
    assert preserved is not None
    assert preserved.status is TaskStatus.FAILED
    assert preserved.metadata == current_metadata


@pytest.mark.asyncio
async def test_generic_requeue_cannot_mint_campaign_attempt(board):
    task, metadata = await _new_bound_campaign_task(
        board,
        "Typed campaign retry boundary",
    )
    assigned = await _typed_campaign_status(
        board, task.id, new_status=TaskStatus.ASSIGNED, metadata=metadata
    )
    await _typed_campaign_status(
        board, assigned.id, new_status=TaskStatus.RUNNING, metadata=metadata
    )
    await board.fail(task.id, error="connection error", metadata=metadata)

    with pytest.raises(TaskBoardError, match="typed attempt recovery"):
        await board.requeue(task.id, reason="generic daemon rescue")
    with pytest.raises(TaskBoardError, match="typed attempt recovery"):
        await board.update_task(
            task.id,
            status=TaskStatus.PENDING,
            result="generic status repair",
        )

    preserved = await board.get(task.id)
    assert preserved is not None
    assert preserved.status == TaskStatus.FAILED
    assert preserved.metadata["mission_campaign_authority"]["attempt_generation"] == 0


@pytest.mark.asyncio
async def test_generic_complete_cannot_assert_campaign_success(board):
    task, metadata = await _new_bound_campaign_task(
        board,
        "Receipt-bound campaign completion",
    )
    assigned = await _typed_campaign_status(
        board,
        task.id,
        new_status=TaskStatus.ASSIGNED,
        metadata=metadata,
    )
    running = await _typed_campaign_status(
        board,
        assigned.id,
        new_status=TaskStatus.RUNNING,
        metadata=metadata,
    )

    with pytest.raises(TaskBoardError, match="receipt-backed"):
        await board.complete(running.id, result="fabricated-success")
    assert await board.get(running.id) == running


@pytest.mark.asyncio
async def test_generic_metadata_update_cannot_erase_campaign_authority(board):
    terminal, original = await _indeterminate_campaign_task(board)

    with pytest.raises(TaskBoardError, match="cannot remove or replace"):
        await board.update_task(terminal.id, metadata={})

    preserved = await board.get(terminal.id)
    assert preserved is not None
    assert preserved.status == terminal.status
    assert (
        preserved.metadata["mission_campaign_authority"]
        == original["mission_campaign_authority"]
    )


@pytest.mark.asyncio
async def test_generic_metadata_update_cannot_strip_attempt_authority_aliases(board):
    terminal, original = await _indeterminate_campaign_task(board)
    authority_only = {
        key: original[key]
        for key in (
            "mission_campaign_authority",
            "sadhana_bootstrap_schema",
            "campaign_id",
            "goal_id",
            "mission_task_creation_hash",
        )
    }

    with pytest.raises(TaskBoardError, match="attempt authority"):
        await board.update_task(terminal.id, metadata=authority_only)

    assert await board.get(terminal.id) == terminal


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "forged"),
    [
        ("mission_task_id", "foreign-task"),
        ("task_id", "foreign-task"),
        ("external_a2a_task_id", "foreign-a2a"),
        ("mission_id", "foreign-mission"),
        ("preferred_provider", "foreign-provider"),
        ("mission_observed_input", {"self_asserted": True}),
    ],
)
async def test_generic_metadata_update_cannot_add_authority_alias(
    board: TaskBoard,
    field: str,
    forged: object,
) -> None:
    task, current = await _new_bound_campaign_task(
        board,
        f"Reject generic authority alias {field}",
    )
    replacement = {**current, field: forged}

    with pytest.raises(TaskBoardError, match="attempt authority"):
        await board.update_task(task.id, metadata=replacement)

    assert await board.get(task.id) == task


def _owner_promotion_metadata(
    current: dict,
    task_id: str,
    *,
    mission_id: str,
    dispatch_key: str,
    generation: int,
) -> dict:
    identity = owner_execution_identity(
        mission_id,
        task_id,
        dispatch_key,
        generation,
    )
    marker = {
        "schema_version": "dharma.mission_control.owner_execution.v2",
        "backend": "orchestrator",
        "mission_id": mission_id,
        "task_id": task_id,
        "dispatch_key": dispatch_key,
        "attempt_generation": generation,
        **identity,
    }
    return {
        **current,
        "mission_control_owner_execution": marker,
        "runtime_run_id": identity["run_id"],
        **identity,
        "attempt_generation": generation,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign_coordinate", ["mission", "dispatch", "generation"])
async def test_owner_stamp_promotion_closes_over_campaign_authority(
    board: TaskBoard,
    foreign_coordinate: str,
) -> None:
    task, current = await _new_bound_campaign_task(
        board,
        "Owner promotion closure",
        without_owner=True,
    )
    authority = current["mission_campaign_authority"]
    coordinates = {
        "mission_id": authority["mission_id"],
        "dispatch_key": authority["dispatch_key"],
        "generation": authority["attempt_generation"],
    }
    coordinates.update(
        {
            "mission": {"mission_id": "foreign-mission"},
            "dispatch": {"dispatch_key": "foreign-dispatch"},
            "generation": {"generation": 1},
        }[foreign_coordinate]
    )
    poisoned = _owner_promotion_metadata(current, task.id, **coordinates)

    with pytest.raises(TaskBoardError, match="attempt authority"):
        await board.update_task(task.id, metadata=poisoned)

    preserved = await board.get(task.id)
    assert preserved is not None
    assert preserved.metadata == current


@pytest.mark.asyncio
async def test_owner_stamp_promotion_accepts_exact_campaign_authority(
    board: TaskBoard,
) -> None:
    task, current = await _new_bound_campaign_task(
        board,
        "Exact owner promotion",
        without_owner=True,
    )
    authority = current["mission_campaign_authority"]
    replacement = _owner_promotion_metadata(
        current,
        task.id,
        mission_id=authority["mission_id"],
        dispatch_key=authority["dispatch_key"],
        generation=authority["attempt_generation"],
    )

    await board.update_task(task.id, metadata=replacement)

    promoted = await board.get(task.id)
    assert promoted is not None
    assert promoted.metadata == replacement


@pytest.mark.asyncio
@pytest.mark.parametrize("api", ["update_task", "fail"])
@pytest.mark.parametrize(
    ("carrier", "value"),
    [
        ("mission_campaign_authority", {"schema_version": "forged"}),
        (
            "sadhana_bootstrap_schema",
            "dharma.sadhana.mission_bootstrap.v1",
        ),
        ("campaign_dispatch_recovery", {"state": "dispatch_indeterminate"}),
        ("campaign_runtime_recovery_fence", {"authority_digest": "forged"}),
        ("campaign_dispatch_attempt_history", []),
    ],
)
async def test_generic_api_cannot_mint_campaign_carrier_on_ordinary_task(
    board: TaskBoard,
    api: str,
    carrier: str,
    value: object,
) -> None:
    task = await board.create("Ordinary task", metadata={"ordinary": True})
    if api == "fail":
        task = await board.assign(task.id, "ordinary-agent")
        task = await board.start(task.id)
    forged = {**task.metadata, carrier: value}

    with pytest.raises(TaskBoardError, match="cannot mint campaign authority"):
        if api == "update_task":
            await board.update_task(task.id, metadata=forged)
        else:
            await board.fail(task.id, error="forged", metadata=forged)

    assert await board.get(task.id) == task


def _legacy_mission_campaign_promotion(
    current: dict,
    task_id: str,
) -> dict:
    attempt = _campaign_attempt_metadata(task_id)
    authority = attempt["mission_campaign_authority"]
    return {
        **current,
        "sadhana_bootstrap_schema": "dharma.sadhana.mission_bootstrap.v1",
        "campaign_id": authority["campaign_id"],
        "goal_id": authority["goal_id"],
        "mission_task_id": task_id,
        "attempt_generation": authority["attempt_generation"],
        "attempt_ceiling": authority["max_attempts"],
        "mission_control_governance": attempt["mission_control_governance"],
        "mission_campaign_authority": authority,
    }


@pytest.mark.asyncio
async def test_legacy_mission_task_accepts_exact_bootstrap_authority_promotion(
    board: TaskBoard,
) -> None:
    legacy = {
        "schema_version": "dharma.mission_control.v1",
        "mission_id": "campaign-exact",
        "mission_task_idempotency_key": "legacy-task-key",
        "mission_task_creation_hash": "sha256:" + "9" * 64,
        "mission_control_governance": {"allowed_files": ["workspaces/exact"]},
    }
    task = await board.create("Legacy typed promotion", metadata=legacy)
    replacement = _legacy_mission_campaign_promotion(legacy, task.id)

    await board.update_task(task.id, metadata=replacement)

    promoted = await board.get(task.id)
    assert promoted is not None
    assert promoted.metadata == replacement


@pytest.mark.asyncio
async def test_legacy_authority_only_promotion_synthesizes_exact_governance(
    board: TaskBoard,
) -> None:
    legacy = {
        "schema_version": "dharma.mission_control.v1",
        "mission_id": "campaign-exact",
        "mission_task_idempotency_key": "legacy-task-key",
        "mission_task_creation_hash": "sha256:" + "9" * 64,
    }
    task = await board.create("Legacy authority-only promotion", metadata=legacy)
    replacement = _legacy_mission_campaign_promotion(legacy, task.id)
    replacement.pop("mission_control_governance")

    await board.update_task(task.id, metadata=replacement)

    promoted = await board.get(task.id)
    assert promoted is not None
    governance = promoted.metadata["mission_control_governance"]
    assert governance["schema_version"] == "dharma.sadhana.campaign_governance.v4"
    assert governance["forbidden_files"] == []
    assert governance["max_usd"] == 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize("governance_attack", ["sparse", "max_usd"])
async def test_legacy_mission_task_rejects_inexact_governance_promotion(
    board: TaskBoard,
    governance_attack: str,
) -> None:
    legacy = {
        "schema_version": "dharma.mission_control.v1",
        "mission_id": "campaign-exact",
        "mission_task_idempotency_key": "legacy-task-key",
        "mission_task_creation_hash": "sha256:" + "9" * 64,
        "mission_control_governance": {"allowed_files": ["workspaces/exact"]},
    }
    task = await board.create("Invalid legacy typed promotion", metadata=legacy)
    replacement = _legacy_mission_campaign_promotion(legacy, task.id)
    if governance_attack == "sparse":
        replacement["mission_control_governance"] = legacy[
            "mission_control_governance"
        ]
    else:
        replacement["mission_control_governance"] = copy.deepcopy(
            replacement["mission_control_governance"]
        )
        replacement["mission_control_governance"]["max_usd"] = 1.0

    with pytest.raises(TaskBoardError, match="cannot mint campaign authority"):
        await board.update_task(task.id, metadata=replacement)

    assert await board.get(task.id) == task


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("carrier", "forged"),
    [
        ("mission_control_owner_execution", {"self_asserted": True}),
        ("active_claim", {"claim_id": "forged-claim"}),
        ("execution_identity", {"run_id": "forged-run"}),
        ("run_id", "forged-run"),
        ("task_id", "forged-task"),
        ("external_a2a_task_id", "forged-a2a"),
    ],
)
async def test_legacy_authority_promotion_rejects_attempt_owner_carriers(
    board: TaskBoard,
    carrier: str,
    forged: object,
) -> None:
    legacy = {
        "schema_version": "dharma.mission_control.v1",
        "mission_id": "campaign-exact",
        "mission_task_idempotency_key": "legacy-task-key",
        "mission_task_creation_hash": "sha256:" + "9" * 64,
    }
    task = await board.create(f"Forged legacy carrier {carrier}", metadata=legacy)
    replacement = _legacy_mission_campaign_promotion(legacy, task.id)
    replacement[carrier] = forged

    with pytest.raises(TaskBoardError, match="cannot mint campaign authority"):
        await board.update_task(task.id, metadata=replacement)

    assert await board.get(task.id) == task


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("authority_key", "authority_value"),
    [
        (
            "campaign_dispatch_recovery",
            {
                "schema_version": "dharma.sadhana.dispatch_recovery.v2",
                "state": "dispatch_indeterminate",
            },
        ),
        (
            "campaign_runtime_recovery_fence",
            {
                "schema_version": (
                    "dharma.sadhana.campaign_runtime_recovery_fence.v1"
                ),
                "authority_digest": "sha256:" + "1" * 64,
            },
        ),
    ],
)
async def test_generic_fail_cannot_mint_campaign_recovery_authority(
    board: TaskBoard,
    authority_key: str,
    authority_value: dict,
) -> None:
    task, metadata = await _new_bound_campaign_task(
        board,
        "Campaign recovery forgery",
    )
    assigned = await _typed_campaign_status(
        board,
        task.id,
        new_status=TaskStatus.ASSIGNED,
        metadata=metadata,
    )
    running = await _typed_campaign_status(
        board,
        assigned.id,
        new_status=TaskStatus.RUNNING,
        metadata=metadata,
    )
    forged = copy.deepcopy(running.metadata)
    forged[authority_key] = authority_value

    with pytest.raises(TaskBoardError, match="attempt authority"):
        await board.fail(
            running.id,
            error="INDETERMINATE_RESULT",
            metadata=forged,
        )

    assert await board.get(running.id) == running


def _projection_marker(
    task_id: str,
    result: str,
    *,
    run_id: str,
    runtime_authority_sha256: str = "a" * 64,
    action: str = "receipt",
    run_status: str = "completed",
) -> dict:
    return {
        "schema_version": "dharma.graph.board_projection_receipt.v1",
        "task_id": task_id,
        "run_id": run_id,
        "action": action,
        "run_status": run_status,
        "runtime_authority_snapshot_sha256": runtime_authority_sha256,
        "board_result_sha256": hashlib.sha256(result.encode("utf-8")).hexdigest(),
        "projected_at": "2026-08-23T12:00:00+00:00",
    }


def _projection_completion_binding(task_id: str, result: str) -> dict:
    side_effect_key = f"invoke_agent:{task_id}:agent-exact"
    return {
        "schema_version": "dharma.graph.task_board_completion_binding.v1",
        "task_id": task_id,
        "run_id": "run-0",
        "claim_id": "claim-0",
        "agent_id": "agent-exact",
        "receipt_id": "00000000-0000-0000-0000-000000000001",
        "side_effect_key": side_effect_key,
        "idempotency_key": "sek_"
        + hashlib.sha256(side_effect_key.encode()).hexdigest(),
        "dispatch_idempotency_key": "dispatch-idem-0",
        "result_sha256": hashlib.sha256(result.encode()).hexdigest(),
    }


async def _seed_runtime_projection_authority(
    store: RuntimeStateStore,
    task_id: str,
    result: str,
    *,
    status: str = "completed",
) -> tuple[dict, str]:
    binding = _projection_completion_binding(task_id, result)
    side_effect_key = binding["side_effect_key"]
    operation_hash = hashlib.sha256(side_effect_key.encode()).hexdigest()
    claim = ExecutionIdentity.new(
        trace_id="trace-0",
        correlation_id="correlation-0",
        task_id=task_id,
        run_id="run-0",
        claim_id="claim-0",
        idempotency_key=binding["idempotency_key"],
        agent_id="agent-exact",
        session_id="session-0",
    )
    receipt = EvidenceReceipt(
        receipt_id=UUID(binding["receipt_id"]),
        trace_id=claim.trace_id,
        context_id=claim.session_id,
        task_id=task_id,
        claim_id=claim.claim_id,
        agent_id=claim.agent_id,
        provider="fixture-provider",
        model="fixture-model",
        operation="invoke_agent",
        provider_attempted=True,
        status="ok" if status == "completed" else "failed",
        error_source="none" if status == "completed" else "provider_failed",
        error_detail=None if status == "completed" else result,
        started_at=datetime(2026, 8, 23, 11, 59, tzinfo=timezone.utc),
        finished_at=datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc),
        attributes={
            "run_id": claim.run_id,
            "idempotency_key": claim.idempotency_key,
            "dispatch_idempotency_key": "dispatch-idem-0",
            "side_effect_key": side_effect_key,
        },
    )
    assert await store.try_begin_idempotent_side_effect(
        claim,
        side_effect_key,
        metadata={"operation_hash": operation_hash, "task_id": task_id},
    )
    record = await store.complete_idempotent_side_effect(
        claim,
        side_effect_key,
        status=status,
        result_receipt_id=binding["receipt_id"],
        metadata={
            "operation_hash": operation_hash,
            "receipt": receipt.to_dict(),
            "result_json": json.dumps(result) if status == "completed" else None,
            "result_omitted_reason": None,
        },
    )
    return binding, runtime_idempotency_authority_snapshot_sha256(record)


async def _seed_failed_run_projection_authority(
    store: RuntimeStateStore,
    task_id: str,
    result: str,
    *,
    causation_id: str = "causation-0",
    parent_run_id: str = "parent-run-0",
) -> str:
    identity = {
        "trace_id": "trace-0",
        "correlation_id": "correlation-0",
        "causation_id": causation_id,
        "task_id": task_id,
        "run_id": "run-0",
        "claim_id": "claim-0",
        "parent_run_id": parent_run_id,
        "idempotency_key": "dispatch-idem-0",
        "agent_id": "agent-exact",
        "session_id": "session-0",
        "external_a2a_task_id": "",
        "message_id": "",
        "event_id": "",
        "artifact_id": "",
        "proposal_id": "",
    }
    run = await store.record_delegation_run(
        DelegationRun(
            run_id=identity["run_id"],
            task_id=task_id,
            assigned_to=identity["agent_id"],
            status="failed",
            session_id=identity["session_id"],
            claim_id=identity["claim_id"],
            parent_run_id=identity["parent_run_id"],
            assigned_by="orchestrator",
            started_at=datetime(2026, 8, 23, 11, 59, tzinfo=timezone.utc),
            completed_at=datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc),
            failure_code="provider_failed",
            metadata={
                "status": "failed",
                "error": result,
                "runtime_db_path": str(store.db_path),
                "execution_identity": identity,
                "trace_id": identity["trace_id"],
                "correlation_id": identity["correlation_id"],
                "idempotency_key": identity["idempotency_key"],
            },
        )
    )
    return runtime_run_authority_snapshot_sha256(run)


async def _seed_projection_history_for_test(
    board: TaskBoard,
    expected: Task,
    metadata: dict,
):
    """Represent a receipt already committed by the Graph projection boundary."""
    # The generic TaskBoard API must not mint Graph projection receipts. This
    # fixture writes a prior-process state directly so the terminal CAS can be
    # tested against an existing append-only history.
    async with board._open() as db:
        cursor = await db.execute(
            "UPDATE tasks SET metadata = ? WHERE id = ? AND status = ?"
            " AND assigned_to IS ? AND result IS ? AND metadata = ?"
            " AND updated_at = ?",
            (
                board._coerce_db_value("metadata", metadata),
                expected.id,
                expected.status.value,
                expected.assigned_to,
                expected.result,
                board._coerce_db_value("metadata", expected.metadata),
                expected.updated_at.isoformat(),
            ),
        )
        assert cursor.rowcount == 1
        await db.commit()
    seeded = await board.get(expected.id)
    assert seeded is not None
    return seeded


async def _running_campaign_projection_task(
    board: TaskBoard,
    runtime_state_store: RuntimeStateStore,
):
    bootstrap = {
        "sadhana_bootstrap_schema": "dharma.sadhana.mission_bootstrap.v1",
        "campaign_id": "campaign-exact",
        "goal_id": "G01",
        "mission_task_creation_hash": "sha256:" + "9" * 64,
    }
    task = await board.create("Campaign projection CAS", metadata=bootstrap)
    metadata = {**bootstrap, **_campaign_attempt_metadata(task.id)}
    identity = {
        "trace_id": "trace-0",
        "correlation_id": "correlation-0",
        "causation_id": "causation-0",
        "task_id": task.id,
        "run_id": "run-0",
        "claim_id": "claim-0",
        "parent_run_id": "parent-run-0",
        "idempotency_key": "dispatch-idem-0",
        "agent_id": "agent-exact",
        "session_id": "session-0",
    }
    metadata["execution_identity"] = identity
    metadata["runtime_db_path"] = str(runtime_state_store.db_path)
    metadata["mission_control_owner_execution"].update(
        {
            "run_id": identity["run_id"],
            "claim_id": identity["claim_id"],
            "idempotency_key": identity["idempotency_key"],
            "trace_id": identity["trace_id"],
            "correlation_id": identity["correlation_id"],
            "attempt_generation": 0,
        }
    )
    metadata.update(
        {
            "trace_id": identity["trace_id"],
            "correlation_id": identity["correlation_id"],
            "causation_id": identity["causation_id"],
            "task_id": identity["task_id"],
            "runtime_run_id": identity["run_id"],
            "run_id": identity["run_id"],
            "claim_id": identity["claim_id"],
            "parent_run_id": identity["parent_run_id"],
            "agent_id": identity["agent_id"],
            "session_id": identity["session_id"],
            "idempotency_key": identity["idempotency_key"],
        }
    )
    metadata["active_claim"] = {"claim_id": "claim-0"}
    task = await board.compare_and_swap_campaign_metadata(task, metadata=metadata)
    assert task is not None
    assigned = await _typed_campaign_status(
        board,
        task.id,
        new_status=TaskStatus.ASSIGNED,
        metadata=metadata,
    )
    running = await _typed_campaign_status(
        board,
        assigned.id,
        new_status=TaskStatus.RUNNING,
        metadata=metadata,
    )
    prior = _projection_marker(task.id, "prior-result", run_id="run-prior")
    seeded_metadata = copy.deepcopy(running.metadata)
    seeded_metadata["graph_reconcile_projection"] = prior
    seeded_metadata["graph_reconcile_projection_history"] = {"run-prior": prior}
    seeded = await _seed_projection_history_for_test(
        board,
        running,
        seeded_metadata,
    )
    return seeded, prior


@pytest.mark.asyncio
async def test_terminal_projection_cas_preserves_campaign_authority_and_history(
    board,
    projection_runtime,
):
    running, prior = await _running_campaign_projection_task(
        board, projection_runtime
    )
    result = "verified result"
    binding, authority_sha256 = await _seed_runtime_projection_authority(
        projection_runtime, running.id, result
    )
    marker = _projection_marker(
        running.id,
        result,
        run_id="run-0",
        runtime_authority_sha256=authority_sha256,
    )
    metadata = copy.deepcopy(running.metadata)
    metadata.pop("active_claim")
    metadata["task_board_completion_binding"] = binding
    metadata["graph_reconcile_projection"] = marker
    metadata["graph_reconcile_projection_history"] = {
        "run-prior": prior,
        "run-0": marker,
    }

    projected = await board.compare_and_swap_terminal_projection(
        running,
        metadata=metadata,
        result=result,
        runtime_state_store=projection_runtime,
    )

    assert projected is not None
    assert projected.status is TaskStatus.COMPLETED
    assert (
        projected.metadata["mission_campaign_authority"]
        == running.metadata["mission_campaign_authority"]
    )
    assert projected.metadata["graph_reconcile_projection_history"] == {
        "run-prior": prior,
        "run-0": marker,
    }


@pytest.mark.asyncio
async def test_failed_receipt_projection_requires_exact_runtime_failure(
    board,
    projection_runtime,
):
    running, prior = await _running_campaign_projection_task(
        board, projection_runtime
    )
    result = "provider failed"
    binding, authority_sha256 = await _seed_runtime_projection_authority(
        projection_runtime,
        running.id,
        result,
        status="failed",
    )
    marker = _projection_marker(
        running.id,
        result,
        run_id="run-0",
        runtime_authority_sha256=authority_sha256,
        run_status="failed",
    )
    metadata = copy.deepcopy(running.metadata)
    metadata.pop("active_claim")
    metadata["task_board_completion_binding"] = binding
    metadata["graph_reconcile_projection"] = marker
    metadata["graph_reconcile_projection_history"] = {
        "run-prior": prior,
        "run-0": marker,
    }

    projected = await board.compare_and_swap_terminal_projection(
        running,
        metadata=metadata,
        result=result,
        runtime_state_store=projection_runtime,
    )

    assert projected is not None
    assert projected.status is TaskStatus.FAILED
    assert projected.result == result


@pytest.mark.asyncio
async def test_terminal_projection_requires_bound_concrete_runtime_store(
    board,
    projection_runtime,
    tmp_path,
):
    running, prior = await _running_campaign_projection_task(
        board, projection_runtime
    )
    result = "verified result"
    binding, authority_sha256 = await _seed_runtime_projection_authority(
        projection_runtime, running.id, result
    )
    marker = _projection_marker(
        running.id,
        result,
        run_id="run-0",
        runtime_authority_sha256=authority_sha256,
    )
    metadata = copy.deepcopy(running.metadata)
    metadata["task_board_completion_binding"] = binding
    metadata["graph_reconcile_projection"] = marker
    metadata["graph_reconcile_projection_history"] = {
        "run-prior": prior,
        "run-0": marker,
    }
    foreign_store = RuntimeStateStore(tmp_path / "foreign-runtime.db")
    await foreign_store.init_db()

    for authority_store in (None, foreign_store):
        with pytest.raises(TaskBoardError, match="durable runtime authority"):
            await board.compare_and_swap_terminal_projection(
                running,
                metadata=metadata,
                result=result,
                runtime_state_store=authority_store,
            )

    assert await board.get(running.id) == running


@pytest.mark.asyncio
async def test_requeue_projection_requires_exact_failed_runtime_run(
    board,
    projection_runtime,
):
    running, prior = await _running_campaign_projection_task(
        board, projection_runtime
    )
    result = "provider failed"
    authority_sha256 = await _seed_failed_run_projection_authority(
        projection_runtime,
        running.id,
        result,
    )
    marker = _projection_marker(
        running.id,
        result,
        run_id="run-0",
        runtime_authority_sha256=authority_sha256,
        action="requeue",
        run_status="failed",
    )
    metadata = copy.deepcopy(running.metadata)
    metadata.pop("active_claim")
    metadata["graph_reconcile_projection"] = marker
    metadata["graph_reconcile_projection_history"] = {
        "run-prior": prior,
        "run-0": marker,
    }

    projected = await board.compare_and_swap_terminal_projection(
        running,
        metadata=metadata,
        result=result,
        expected_claim_id="claim-0",
        expected_agent_id="agent-exact",
        runtime_state_store=projection_runtime,
    )

    assert projected is not None
    assert projected.status is TaskStatus.PENDING
    assert projected.assigned_to is None
    assert projected.metadata["graph_reconcile_projection"] == marker


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lineage_field", "foreign_value"),
    [
        ("causation_id", "foreign-causation"),
        ("parent_run_id", "foreign-parent-run"),
    ],
)
async def test_requeue_projection_rejects_foreign_runtime_lineage(
    board: TaskBoard,
    projection_runtime: RuntimeStateStore,
    lineage_field: str,
    foreign_value: str,
) -> None:
    running, prior = await _running_campaign_projection_task(
        board,
        projection_runtime,
    )
    result = "provider failed"
    authority_sha256 = await _seed_failed_run_projection_authority(
        projection_runtime,
        running.id,
        result,
        **{lineage_field: foreign_value},
    )
    marker = _projection_marker(
        running.id,
        result,
        run_id="run-0",
        runtime_authority_sha256=authority_sha256,
        action="requeue",
        run_status="failed",
    )
    metadata = copy.deepcopy(running.metadata)
    metadata.pop("active_claim")
    metadata["graph_reconcile_projection"] = marker
    metadata["graph_reconcile_projection_history"] = {
        "run-prior": prior,
        "run-0": marker,
    }

    with pytest.raises(TaskBoardError, match="authority|boundary"):
        await board.compare_and_swap_terminal_projection(
            running,
            metadata=metadata,
            result=result,
            expected_claim_id="claim-0",
            expected_agent_id="agent-exact",
            runtime_state_store=projection_runtime,
        )

    assert await board.get(running.id) == running


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "expected_status"),
    [
        ("requeue", TaskStatus.PENDING),
        ("quarantine", TaskStatus.FAILED),
    ],
)
async def test_recovery_projection_identical_replay_is_exact_noop(
    board: TaskBoard,
    projection_runtime: RuntimeStateStore,
    action: str,
    expected_status: TaskStatus,
) -> None:
    running, prior = await _running_campaign_projection_task(
        board,
        projection_runtime,
    )
    result = "provider failed"
    authority_sha256 = await _seed_failed_run_projection_authority(
        projection_runtime,
        running.id,
        result,
    )
    marker = _projection_marker(
        running.id,
        result,
        run_id="run-0",
        runtime_authority_sha256=authority_sha256,
        action=action,
        run_status="failed",
    )
    metadata = copy.deepcopy(running.metadata)
    metadata.pop("active_claim")
    metadata["graph_reconcile_projection"] = marker
    metadata["graph_reconcile_projection_history"] = {
        "run-prior": prior,
        "run-0": marker,
    }
    projected = await board.compare_and_swap_terminal_projection(
        running,
        metadata=metadata,
        result=result,
        expected_claim_id="claim-0",
        expected_agent_id="agent-exact",
        runtime_state_store=projection_runtime,
    )
    assert projected is not None
    assert projected.status is expected_status

    replayed = await board.compare_and_swap_terminal_projection(
        projected,
        metadata=copy.deepcopy(projected.metadata),
        result=result,
        expected_claim_id="claim-0",
        expected_agent_id="agent-exact",
        runtime_state_store=projection_runtime,
    )

    assert replayed == projected

    forged = copy.deepcopy(projected.metadata)
    forged_marker = copy.deepcopy(marker)
    forged_marker["projected_at"] = "2026-08-23T12:00:01+00:00"
    forged["graph_reconcile_projection"] = forged_marker
    forged["graph_reconcile_projection_history"]["run-0"] = forged_marker
    with pytest.raises(TaskBoardError, match="boundary"):
        await board.compare_and_swap_terminal_projection(
            projected,
            metadata=forged,
            result=result,
            expected_claim_id="claim-0",
            expected_agent_id="agent-exact",
            runtime_state_store=projection_runtime,
        )
    assert await board.get(projected.id) == projected


@pytest.mark.asyncio
@pytest.mark.parametrize("authority_kind", ["failed_idempotency", "failed_run"])
async def test_runtime_authority_writer_lock_is_held_through_board_commit(
    board: TaskBoard,
    projection_runtime: RuntimeStateStore,
    monkeypatch: pytest.MonkeyPatch,
    authority_kind: str,
) -> None:
    running, prior = await _running_campaign_projection_task(
        board,
        projection_runtime,
    )
    result = "provider failed"
    binding = None
    if authority_kind == "failed_idempotency":
        binding, authority_sha256 = await _seed_runtime_projection_authority(
            projection_runtime,
            running.id,
            result,
            status="failed",
        )
        action = "receipt"
    else:
        authority_sha256 = await _seed_failed_run_projection_authority(
            projection_runtime,
            running.id,
            result,
        )
        action = "requeue"
    marker = _projection_marker(
        running.id,
        result,
        run_id="run-0",
        runtime_authority_sha256=authority_sha256,
        action=action,
        run_status="failed",
    )
    metadata = copy.deepcopy(running.metadata)
    metadata.pop("active_claim")
    if binding is not None:
        metadata["task_board_completion_binding"] = binding
    metadata["graph_reconcile_projection"] = marker
    metadata["graph_reconcile_projection_history"] = {
        "run-prior": prior,
        "run-0": marker,
    }
    authority_checked = asyncio.Event()
    release_authorizer = asyncio.Event()
    mutation_started = asyncio.Event()
    runtime_writer_acquired = asyncio.Event()
    original_authorizer = campaign_guard_mod._runtime_projection_is_authorized

    async def paused_authorizer(*args, **kwargs):
        authorized = await original_authorizer(*args, **kwargs)
        assert authorized
        authority_checked.set()
        await release_authorizer.wait()
        return authorized

    monkeypatch.setattr(
        campaign_guard_mod,
        "_runtime_projection_is_authorized",
        paused_authorizer,
    )
    cas_kwargs = {
        "metadata": metadata,
        "result": result,
        "runtime_state_store": projection_runtime,
    }
    if authority_kind == "failed_run":
        cas_kwargs.update(
            expected_claim_id="claim-0",
            expected_agent_id="agent-exact",
        )
    projection_task = asyncio.create_task(
        board.compare_and_swap_terminal_projection(running, **cas_kwargs)
    )
    await asyncio.wait_for(authority_checked.wait(), timeout=2.0)
    observed_board: dict[str, object] = {}

    async def mutate_runtime_authority() -> None:
        async with aiosqlite.connect(projection_runtime.db_path, timeout=2.0) as db:
            await db.execute("PRAGMA busy_timeout=2000")
            mutation_started.set()
            await db.execute("BEGIN IMMEDIATE")
            runtime_writer_acquired.set()
            async with board._open() as board_db:
                row = await (
                    await board_db.execute(
                        "SELECT status, metadata FROM tasks WHERE id = ?",
                        (running.id,),
                    )
                ).fetchone()
            assert row is not None
            observed_board.update(status=row[0], metadata=json.loads(row[1]))
            if authority_kind == "failed_idempotency":
                assert binding is not None
                prior = await (
                    await db.execute(
                        "SELECT idempotency_key, side_effect_key, run_id, task_id,"
                        " trace_id, correlation_id, status, result_receipt_id,"
                        " metadata_json, created_at, updated_at"
                        " FROM idempotency_records WHERE idempotency_key = ?"
                        " AND side_effect_key = ?",
                        (binding["idempotency_key"], binding["side_effect_key"]),
                    )
                ).fetchone()
                assert prior is not None
                cursor = await db.execute(
                    "UPDATE idempotency_records SET status = 'started'"
                    " WHERE idempotency_key IS ? AND side_effect_key IS ?"
                    " AND run_id IS ? AND task_id IS ? AND trace_id IS ?"
                    " AND correlation_id IS ? AND status IS ?"
                    " AND result_receipt_id IS ? AND metadata_json IS ?"
                    " AND created_at IS ? AND updated_at IS ?",
                    tuple(prior),
                )
            else:
                prior = await (
                    await db.execute(
                        "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
                        " assigned_by, assigned_to, requested_output_json,"
                        " current_artifact_id, status, started_at, completed_at,"
                        " failure_code, metadata_json, trace_id, receipt_json"
                        " FROM delegation_runs"
                        " WHERE run_id = ?",
                        ("run-0",),
                    )
                ).fetchone()
                assert prior is not None
                cursor = await db.execute(
                    "UPDATE delegation_runs SET status = 'completed'"
                    " WHERE run_id IS ? AND session_id IS ? AND task_id IS ?"
                    " AND claim_id IS ? AND parent_run_id IS ? AND assigned_by IS ?"
                    " AND assigned_to IS ? AND requested_output_json IS ?"
                    " AND current_artifact_id IS ? AND status IS ?"
                    " AND started_at IS ? AND completed_at IS ?"
                    " AND failure_code IS ? AND metadata_json IS ?"
                    " AND trace_id IS ? AND receipt_json IS ?",
                    tuple(prior),
                )
            assert cursor.rowcount == 1
            await db.commit()

    mutation_task = asyncio.create_task(mutate_runtime_authority())
    await asyncio.wait_for(mutation_started.wait(), timeout=2.0)
    writer_was_blocked = False
    try:
        await asyncio.wait_for(runtime_writer_acquired.wait(), timeout=0.05)
    except TimeoutError:
        writer_was_blocked = True
    finally:
        release_authorizer.set()

    projected = await projection_task
    await mutation_task

    assert writer_was_blocked
    assert projected is not None
    assert observed_board["status"] == projected.status.value
    observed_metadata = observed_board["metadata"]
    assert isinstance(observed_metadata, dict)
    assert observed_metadata["graph_reconcile_projection"] == marker


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "corruption",
    [
        "nested_trace",
        "flat_task",
        "flat_parent_run",
        "flat_causation",
        "owner_generation_bool",
        "board_generation_bool",
        "authority_schema",
        "authority_extra_field",
        "authority_effect_mode",
        "authority_campaign_closure",
        "authority_goal_closure",
        "authority_ceiling_closure",
        "governance_closure",
        "attempt_history",
        "mission_task_id",
        "active_claim_type",
        "owner_mission",
        "owner_dispatch",
        "owner_generation",
        "board_generation",
    ],
)
async def test_terminal_projection_rejects_preexisting_attempt_contradiction(
    board,
    projection_runtime,
    corruption: str,
):
    running, prior = await _running_campaign_projection_task(
        board, projection_runtime
    )
    corrupted_metadata = copy.deepcopy(running.metadata)
    if corruption == "nested_trace":
        corrupted_metadata["execution_identity"]["trace_id"] = "foreign-trace"
    elif corruption == "flat_task":
        corrupted_metadata["task_id"] = "foreign-task"
    elif corruption == "flat_parent_run":
        corrupted_metadata["parent_run_id"] = "foreign-parent-run"
    elif corruption == "flat_causation":
        corrupted_metadata["causation_id"] = "foreign-causation"
    elif corruption == "owner_generation_bool":
        corrupted_metadata["mission_control_owner_execution"][
            "attempt_generation"
        ] = False
    elif corruption == "board_generation_bool":
        corrupted_metadata["attempt_generation"] = False
    elif corruption == "authority_schema":
        corrupted_metadata["mission_campaign_authority"][
            "schema_version"
        ] = "dharma.sadhana.campaign_task_authority.v4"
    elif corruption == "authority_extra_field":
        corrupted_metadata["mission_campaign_authority"]["self_asserted"] = True
    elif corruption == "authority_effect_mode":
        corrupted_metadata["mission_campaign_authority"]["effect_mode"] = "write"
    elif corruption == "authority_campaign_closure":
        corrupted_metadata["mission_campaign_authority"].update(
            campaign_id="foreign-campaign",
            mission_id="foreign-campaign",
        )
        corrupted_metadata["mission_control_owner_execution"][
            "mission_id"
        ] = "foreign-campaign"
    elif corruption == "authority_goal_closure":
        corrupted_metadata["mission_campaign_authority"]["goal_id"] = "foreign-goal"
        corrupted_metadata["mission_control_governance"]["goal_id"] = "foreign-goal"
    elif corruption == "authority_ceiling_closure":
        corrupted_metadata["mission_campaign_authority"]["max_attempts"] = 3
        corrupted_metadata["mission_control_governance"]["max_attempts"] = 3
    elif corruption == "governance_closure":
        corrupted_metadata["mission_control_governance"][
            "campaign_id"
        ] = "foreign-campaign"
    elif corruption == "attempt_history":
        corrupted_metadata["campaign_dispatch_attempt_history"] = [
            {"self_asserted": True}
        ]
    elif corruption == "mission_task_id":
        corrupted_metadata["mission_task_id"] = "foreign-task"
    elif corruption == "active_claim_type":
        corrupted_metadata["active_claim"] = "forged-claim"
    elif corruption == "owner_mission":
        corrupted_metadata["mission_control_owner_execution"][
            "mission_id"
        ] = "foreign-mission"
    elif corruption == "owner_dispatch":
        corrupted_metadata["mission_control_owner_execution"][
            "dispatch_key"
        ] = "foreign-dispatch"
    elif corruption == "owner_generation":
        corrupted_metadata["mission_control_owner_execution"][
            "attempt_generation"
        ] = 1
    else:
        corrupted_metadata["attempt_generation"] = 1
    corrupted = await _seed_projection_history_for_test(
        board,
        running,
        corrupted_metadata,
    )
    result = "verified result"
    binding, authority_sha256 = await _seed_runtime_projection_authority(
        projection_runtime, running.id, result
    )
    marker = _projection_marker(
        running.id,
        result,
        run_id="run-0",
        runtime_authority_sha256=authority_sha256,
    )
    metadata = copy.deepcopy(corrupted.metadata)
    metadata["task_board_completion_binding"] = binding
    metadata["graph_reconcile_projection"] = marker
    metadata["graph_reconcile_projection_history"]["run-0"] = marker

    with pytest.raises(TaskBoardError, match="boundary"):
        await board.compare_and_swap_terminal_projection(
            corrupted,
            metadata=metadata,
            result=result,
            runtime_state_store=projection_runtime,
        )

    assert await board.get(running.id) == corrupted


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "attack",
    [
        "erase_authority",
        "replace_authority",
        "rewrite_history",
        "malformed_authority_snapshot",
        "valid_but_foreign_authority_snapshot",
        "inject_unbound_history",
        "rewrite_flat_identity",
        "rewrite_flat_trace",
        "rewrite_nested_identity",
        "rewrite_nested_trace",
        "rewrite_active_claim",
        "inject_mission_task_id",
        "inject_flat_task_alias",
        "inject_external_identity_alias",
        "owner_mission_mismatch",
        "owner_dispatch_mismatch",
        "owner_generation_mismatch",
        "board_generation_mismatch",
        "foreign_runtime_path",
        "marker_binding_run_mismatch",
        "foreign_marker_and_binding_run",
        "foreign_dispatch_idempotency",
        "foreign_side_effect",
        "invalid_run_status",
        "invalid_projected_at",
        "inject_recovery_authority",
    ],
)
async def test_terminal_projection_cas_rejects_authority_or_history_forgery(
    board,
    projection_runtime,
    attack: str,
):
    running, prior = await _running_campaign_projection_task(
        board, projection_runtime
    )
    result = "verified result"
    binding, authority_sha256 = await _seed_runtime_projection_authority(
        projection_runtime, running.id, result
    )
    marker = _projection_marker(
        running.id,
        result,
        run_id="run-0",
        runtime_authority_sha256=authority_sha256,
    )
    metadata = copy.deepcopy(running.metadata)
    metadata["task_board_completion_binding"] = binding
    metadata["graph_reconcile_projection"] = marker
    metadata["graph_reconcile_projection_history"] = {
        "run-prior": copy.deepcopy(prior),
        "run-0": marker,
    }
    if attack == "erase_authority":
        metadata.pop("mission_campaign_authority")
    elif attack == "replace_authority":
        metadata["mission_campaign_authority"]["claimed_principal"] = "intruder"
    elif attack == "rewrite_history":
        metadata["graph_reconcile_projection_history"]["run-prior"][
            "projected_at"
        ] = "forged"
    elif attack == "malformed_authority_snapshot":
        marker["runtime_authority_snapshot_sha256"] = "not-a-sha256"
    elif attack == "valid_but_foreign_authority_snapshot":
        marker["runtime_authority_snapshot_sha256"] = "f" * 64
    elif attack == "inject_unbound_history":
        metadata["graph_reconcile_projection_history"]["forged-run"] = marker
    elif attack == "rewrite_flat_identity":
        metadata["claim_id"] = "foreign-claim"
    elif attack == "rewrite_flat_trace":
        metadata["trace_id"] = "foreign-trace"
    elif attack == "rewrite_nested_identity":
        metadata["execution_identity"]["idempotency_key"] = "forged-idempotency"
    elif attack == "rewrite_nested_trace":
        metadata["execution_identity"]["trace_id"] = "foreign-trace"
    elif attack == "rewrite_active_claim":
        metadata["active_claim"]["claim_id"] = "foreign-claim"
    elif attack == "inject_mission_task_id":
        metadata["mission_task_id"] = "foreign-task"
    elif attack == "inject_flat_task_alias":
        metadata["task_id"] = "foreign-task"
    elif attack == "inject_external_identity_alias":
        metadata["external_a2a_task_id"] = "foreign-a2a"
    elif attack == "owner_mission_mismatch":
        metadata["mission_control_owner_execution"]["mission_id"] = "foreign-mission"
    elif attack == "owner_dispatch_mismatch":
        metadata["mission_control_owner_execution"]["dispatch_key"] = "foreign-dispatch"
    elif attack == "owner_generation_mismatch":
        metadata["mission_control_owner_execution"]["attempt_generation"] = 1
    elif attack == "board_generation_mismatch":
        metadata["attempt_generation"] = 1
    elif attack == "foreign_runtime_path":
        metadata["runtime_db_path"] = "/tmp/foreign-runtime.db"
    elif attack == "marker_binding_run_mismatch":
        metadata["graph_reconcile_projection_history"].pop("run-0")
        marker["run_id"] = "foreign-run"
        metadata["graph_reconcile_projection_history"]["foreign-run"] = marker
    elif attack == "foreign_marker_and_binding_run":
        metadata["graph_reconcile_projection_history"].pop("run-0")
        marker["run_id"] = "foreign-run"
        metadata["task_board_completion_binding"]["run_id"] = "foreign-run"
        metadata["graph_reconcile_projection_history"]["foreign-run"] = marker
    elif attack == "foreign_dispatch_idempotency":
        metadata["task_board_completion_binding"][
            "dispatch_idempotency_key"
        ] = "foreign-dispatch"
    elif attack == "foreign_side_effect":
        side_effect_key = f"invoke_agent:{running.id}:foreign-agent"
        metadata["task_board_completion_binding"].update(
            {
                "side_effect_key": side_effect_key,
                "idempotency_key": "sek_"
                + hashlib.sha256(side_effect_key.encode()).hexdigest(),
            }
        )
    elif attack == "invalid_run_status":
        marker["run_status"] = "untyped-outcome"
    elif attack == "inject_recovery_authority":
        metadata["campaign_dispatch_recovery"] = {
            "schema_version": "dharma.sadhana.dispatch_recovery.v2",
            "state": "dispatch_indeterminate",
        }
    else:
        marker["projected_at"] = "not-an-aware-timestamp"

    with pytest.raises(
        TaskBoardError,
        match="authority|history|boundary|binding",
    ):
        await board.compare_and_swap_terminal_projection(
            running,
            metadata=metadata,
            result=result,
            runtime_state_store=projection_runtime,
        )

    assert await board.get(running.id) == running


@pytest.mark.asyncio
async def test_terminal_projection_identical_replay_is_exact_noop(
    board,
    projection_runtime,
):
    running, prior = await _running_campaign_projection_task(
        board, projection_runtime
    )
    result = "verified result"
    binding, authority_sha256 = await _seed_runtime_projection_authority(
        projection_runtime, running.id, result
    )
    marker = _projection_marker(
        running.id,
        result,
        run_id="run-0",
        runtime_authority_sha256=authority_sha256,
    )
    metadata = copy.deepcopy(running.metadata)
    metadata["task_board_completion_binding"] = binding
    metadata["graph_reconcile_projection"] = marker
    metadata["graph_reconcile_projection_history"] = {
        "run-prior": prior,
        "run-0": marker,
    }
    projected = await board.compare_and_swap_terminal_projection(
        running,
        metadata=metadata,
        result=result,
        runtime_state_store=projection_runtime,
    )
    assert projected is not None

    replayed = await board.compare_and_swap_terminal_projection(
        projected,
        metadata=copy.deepcopy(projected.metadata),
        result=result,
        runtime_state_store=projection_runtime,
    )

    assert replayed == projected


@pytest.mark.asyncio
async def test_generic_result_update_cannot_rewrite_projected_campaign_receipt(
    board: TaskBoard,
    projection_runtime: RuntimeStateStore,
) -> None:
    running, prior = await _running_campaign_projection_task(
        board,
        projection_runtime,
    )
    result = "verified result"
    binding, authority_sha256 = await _seed_runtime_projection_authority(
        projection_runtime,
        running.id,
        result,
    )
    marker = _projection_marker(
        running.id,
        result,
        run_id="run-0",
        runtime_authority_sha256=authority_sha256,
    )
    metadata = copy.deepcopy(running.metadata)
    metadata["task_board_completion_binding"] = binding
    metadata["graph_reconcile_projection"] = marker
    metadata["graph_reconcile_projection_history"] = {
        "run-prior": prior,
        "run-0": marker,
    }
    projected = await board.compare_and_swap_terminal_projection(
        running,
        metadata=metadata,
        result=result,
        runtime_state_store=projection_runtime,
    )
    assert projected is not None

    with pytest.raises(TaskBoardError, match="result mutation"):
        await board.update_task(projected.id, result="forged-result")

    assert await board.get(projected.id) == projected


@pytest.mark.asyncio
async def test_update_task_pending_requeues(board):
    task = await board.create("Pending requeue")
    await board.assign(task.id, "agent")
    await board.start(task.id)
    await board.fail(task.id, error="fail once")

    await board.update_task(
        task.id,
        status=TaskStatus.PENDING,
        result="retry requested",
        metadata={"retry_count": 2},
    )
    loaded = await board.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.PENDING
    assert loaded.metadata["retry_count"] == 2


@pytest.mark.asyncio
async def test_priority_ordering(board):
    await board.create("Low", priority=TaskPriority.LOW)
    await board.create("Urgent", priority=TaskPriority.URGENT)
    await board.create("Normal", priority=TaskPriority.NORMAL)

    ready = await board.get_ready_tasks()
    assert ready[0].priority == TaskPriority.URGENT


@pytest.mark.asyncio
async def test_stats(board):
    await board.create("T1")
    t2 = await board.create("T2")
    await board.assign(t2.id, "a")
    stats = await board.stats()
    assert stats["pending"] == 1
    assert stats["assigned"] == 1
    assert stats["total"] == 2


@pytest.mark.asyncio
async def test_get_by_title(board):
    """MM-17 pinning test: get_by_title must exist and find tasks by title."""
    await board.create("Unique title")
    await board.create("Other title")
    found = await board.get_by_title("Unique title")
    assert found is not None
    assert found.title == "Unique title"
    missing = await board.get_by_title("nonexistent")
    assert missing is None


@pytest.mark.asyncio
async def test_get_by_title_dedup(board):
    """MM-17: gnani_lodestone uses get_by_title for deduplication during seeding."""
    await board.create("Seed task")
    first = await board.get_by_title("Seed task")
    assert first is not None
    # Creating a second with same title - get_by_title returns the first
    await board.create("Seed task")
    found = await board.get_by_title("Seed task")
    assert found is not None
    assert found.id == first.id


@pytest.mark.asyncio
async def test_complete_transition_block_raises(board, monkeypatch):
    class _Outcome:
        def __init__(self):
            self.result = GateCheckResult(
                decision=GateDecision.BLOCK,
                reason="forced block for test",
                gate_results={},
            )

    monkeypatch.setattr(
        task_board_mod,
        "check_with_reflective_reroute",
        lambda **_: _Outcome(),
    )

    task = await board.create("Blocked completion")
    task = await board.assign(task.id, "agent")
    task = await board.start(task.id)
    with pytest.raises(TaskBoardError, match="Telos blocked transition"):
        await board.complete(task.id, result="done")
