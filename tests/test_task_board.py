"""Tests for dharma_swarm.task_board."""

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
    with pytest.raises(TaskBoardError, match="audit-only terminal status"):
        await board.update_task(
            task_id,
            status=TaskStatus.QUARANTINED_FAKE_RESULT,
        )


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
