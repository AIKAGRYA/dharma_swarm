"""Late-completion adoption after a timeout/reconciler requeue.

Production failure mode: a task's execution exceeds the timeout, the timeout
handler (or the graph reconciler's "orphaned run requeued" pass) flips the
task RUNNING -> PENDING, and when the still-live execution coroutine later
finishes, the completion write is rejected with
"Invalid transition: pending -> completed" — finished work discarded.

The fix: ``TaskBoard.complete`` accepts a ``claim_id``; when it matches the
task's stored dispatch claim (``last_claim``, stamped by the orchestrator's
``_prepare_claim`` at assign time) the board re-adopts the task through the
legal FSM. A non-owner run, or a never-dispatched task, still hits the
strict transition table.
"""

import pytest

from dharma_swarm.models import TaskStatus
from dharma_swarm.task_board import TaskBoard, TaskBoardError


@pytest.fixture
async def board(tmp_path):
    b = TaskBoard(tmp_path / "tasks.db")
    await b.init_db()
    return b


async def _dispatch_and_requeue(
    board: TaskBoard,
    *,
    claim_id: str = "claim-run-1",
    agent_id: str = "a1",
):
    """Drive a task through dispatch -> RUNNING -> timeout requeue.

    Mirrors the orchestrator flow: ``_prepare_claim`` stamps ``last_claim``
    into metadata at assign time, then the timeout handler / graph reconciler
    requeues RUNNING -> PENDING while the execution coroutine is still alive.
    """
    task = await board.create("Ship feature", metadata={"origin": "test"})
    claim = {"claim_id": claim_id, "agent_id": agent_id}
    await board.assign(
        task.id,
        agent_id,
        metadata={**task.metadata, "last_claim": claim, "active_claim": claim},
    )
    await board.start(task.id)
    await board.requeue(task.id, reason="Task execution timed out after 0.0s")
    requeued = await board.get(task.id)
    assert requeued is not None
    assert requeued.status == TaskStatus.PENDING
    return task


@pytest.mark.asyncio
async def test_late_completion_accepted_after_timeout_requeue(board):
    task = await _dispatch_and_requeue(board)

    completed = await board.complete(
        task.id, "late but real result", claim_id="claim-run-1",
    )

    assert completed.status == TaskStatus.COMPLETED
    assert completed.result == "late but real result"
    # Re-adopted by the owning agent, not left unassigned.
    assert completed.assigned_to == "a1"


@pytest.mark.asyncio
async def test_late_completion_accepted_via_update_task_route(board):
    """The orchestrator writes through update_task(status=..., claim_id=...)."""
    task = await _dispatch_and_requeue(board)

    await board.update_task(
        task.id,
        status=TaskStatus.COMPLETED,
        result="late result via orchestrator route",
        claim_id="claim-run-1",
    )

    loaded = await board.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.COMPLETED
    assert loaded.result == "late result via orchestrator route"


@pytest.mark.asyncio
async def test_late_completion_from_non_owner_run_rejected(board):
    task = await _dispatch_and_requeue(board)

    with pytest.raises(TaskBoardError, match="pending -> completed"):
        await board.complete(task.id, "stale clobber", claim_id="claim-other-run")

    loaded = await board.get(task.id)
    assert loaded is not None
    assert loaded.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_late_completion_without_claim_still_rejected(board):
    task = await _dispatch_and_requeue(board)

    with pytest.raises(TaskBoardError, match="pending -> completed"):
        await board.complete(task.id, "no ownership proof")


@pytest.mark.asyncio
async def test_never_dispatched_task_cannot_be_completed_late(board):
    """No last_claim on the task -> a claim_id cannot fabricate a completion."""
    task = await board.create("Fresh pending task")

    with pytest.raises(TaskBoardError, match="pending -> completed"):
        await board.complete(task.id, "fabricated", claim_id="claim-run-1")


@pytest.mark.asyncio
async def test_redispatch_overwrites_claim_so_stale_run_cannot_adopt(board):
    """After a requeue + re-dispatch under a new claim, only the new run owns."""
    task = await _dispatch_and_requeue(board, claim_id="claim-run-1", agent_id="a1")

    # Re-dispatch to a second run: a new claim replaces last_claim.
    new_claim = {"claim_id": "claim-run-2", "agent_id": "a2"}
    loaded = await board.get(task.id)
    assert loaded is not None
    await board.assign(
        task.id,
        "a2",
        metadata={**loaded.metadata, "last_claim": new_claim, "active_claim": new_claim},
    )
    await board.start(task.id)
    await board.requeue(task.id, reason="second timeout")

    with pytest.raises(TaskBoardError, match="pending -> completed"):
        await board.complete(task.id, "stale first-run result", claim_id="claim-run-1")

    completed = await board.complete(
        task.id, "second-run result", claim_id="claim-run-2",
    )
    assert completed.status == TaskStatus.COMPLETED
    assert completed.result == "second-run result"
    assert completed.assigned_to == "a2"
