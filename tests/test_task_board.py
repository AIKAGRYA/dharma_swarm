"""Tests for dharma_swarm.task_board."""

import copy
import sqlite3

import pytest

import dharma_swarm.task_board as task_board_mod
from dharma_swarm.models import GateCheckResult, GateDecision
from dharma_swarm.models import TaskPriority, TaskStatus
from dharma_swarm.task_board import TaskBoard, TaskBoardError


@pytest.fixture
async def board(tmp_path):
    b = TaskBoard(tmp_path / "tasks.db")
    await b.init_db()
    return b


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
        "schema_version": "dharma.sadhana.campaign_task_authority.v4",
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
        "deployment_authority_credential_clarification_sha256": (
            "sha256:" + "6" * 64
        ),
        "observed_input_ref": {
            "receipt_id": "observed-receipt",
            "receipt_sha256": "sha256:" + "1" * 64,
            "artifact_id": "observed-artifact",
            "artifact_record_sha256": "sha256:" + "2" * 64,
            "content_sha256": "sha256:" + "3" * 64,
        },
    }
    governance = {
        key: value
        for key, value in authority.items()
        if key
        not in {
            "agent_name", "claimed_principal", "dispatch_key", "request_id",
            "authority_ref", "authority_digest",
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
                "run_id", "claim_id", "idempotency_key", "trace_id",
                "correlation_id",
            )
        },
    }


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
    quarantined = await board.list_tasks(
        status=TaskStatus.QUARANTINED_FAKE_RESULT
    )
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
    task = await board.create("Campaign task")
    metadata = _campaign_attempt_metadata(task.id)
    await board.update_task(task.id, metadata=metadata)
    task = await board.assign(task.id, "agent-exact", metadata=metadata)
    if prior is TaskStatus.RUNNING:
        task = await board.start(task.id, metadata=metadata)

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
async def test_campaign_pre_effect_failure_never_overwrites_drift(board: TaskBoard) -> None:
    task = await board.create("Campaign task")
    metadata = _campaign_attempt_metadata(task.id)
    await board.update_task(task.id, metadata=metadata)
    assigned = await board.assign(
        task.id,
        "agent-exact",
        metadata=metadata,
    )
    await board.update_task(task.id, metadata={"owner": "concurrent"})

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
async def test_campaign_pending_recovery_witness_is_byte_stable(board: TaskBoard) -> None:
    task = await board.create("Campaign task")
    metadata = _campaign_attempt_metadata(task.id)
    await board.update_task(task.id, metadata=metadata)
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
    task = await board.create("Campaign attempt")
    metadata = _campaign_attempt_metadata(task.id, maximum=maximum)
    task = await board.assign(task.id, "agent-exact", metadata=metadata)
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
async def test_campaign_attempt_advance_is_exact_and_append_only(board: TaskBoard) -> None:
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
    assert await board.advance_campaign_dispatch_attempt(
        terminal.id,
        expected_status=TaskStatus.CANCELLED,
        expected_agent_id="agent-exact",
        expected_metadata=terminal.metadata,
        next_authority=authority,
        next_governance=governance,
        next_routing=routing,
    ) == "advanced"
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
                "run_id", "claim_id", "idempotency_key", "trace_id",
                "correlation_id",
            )
        }
    )
    assigned = await board.assign(terminal.id, "agent-exact", metadata=active)
    assert await board.resolve_campaign_pre_effect_failure(
        terminal.id,
        expected_status=TaskStatus.ASSIGNED,
        expected_agent_id="agent-exact",
        expected_metadata=assigned.metadata,
        authenticated_principal="agent-exact",
    ) == "indeterminate"
    loaded = await board.get(terminal.id)
    assert loaded is not None
    forged = copy.deepcopy(loaded.metadata)
    forged["campaign_dispatch_attempt_history"][0]["authority"]["goal_id"] = "foreign"
    await board.update_task(terminal.id, metadata=forged)
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
async def test_campaign_attempt_exhaustion_is_exact_row_fenced(board: TaskBoard) -> None:
    terminal, _ = await _indeterminate_campaign_task(board, maximum=1)
    bogus = copy.deepcopy(terminal.metadata["mission_campaign_authority"])

    assert await board.advance_campaign_dispatch_attempt(
        terminal.id,
        expected_status=TaskStatus.CANCELLED,
        expected_agent_id="agent-exact",
        expected_metadata=terminal.metadata,
        next_authority=bogus,
        next_governance=terminal.metadata["mission_control_governance"],
        next_routing={},
    ) == "exhausted"

    await board.update_task(terminal.id, result="concurrent-drift")
    assert await board.advance_campaign_dispatch_attempt(
        terminal.id,
        expected_status=TaskStatus.CANCELLED,
        expected_agent_id="agent-exact",
        expected_metadata=terminal.metadata,
        next_authority=bogus,
        next_governance=terminal.metadata["mission_control_governance"],
        next_routing={},
    ) == "conflict"


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
