"""Tests for dharma_swarm.board.adapters.taskboard_adapter."""

import pytest

from dharma_swarm.board.adapters.taskboard_adapter import (
    TaskBoardAdapter,
    task_to_card,
    _card_id_from_task,
    _task_id_from_card,
    _TASK_TO_CARD_STATUS,
)
from dharma_swarm.board.event_log import BoardEventLog
from dharma_swarm.models import TaskPriority, TaskStatus
from dharma_swarm.task_board import TaskBoard, TaskBoardError


@pytest.fixture
async def board(tmp_path):
    b = TaskBoard(tmp_path / "tasks.db")
    await b.init_db()
    return b


@pytest.fixture
async def adapter(board, tmp_path):
    event_log = BoardEventLog(path=tmp_path / "adapter_events.db")
    return TaskBoardAdapter(board, event_log)


# ---------------------------------------------------------------------------
# Unit: status mapping
# ---------------------------------------------------------------------------


class TestStatusMapping:
    def test_all_task_statuses_mapped(self):
        for status in TaskStatus:
            assert status in _TASK_TO_CARD_STATUS, f"{status} not mapped"

    def test_pending_maps_to_claimable(self):
        assert _TASK_TO_CARD_STATUS[TaskStatus.PENDING] == "claimable"

    def test_running_maps_to_running(self):
        assert _TASK_TO_CARD_STATUS[TaskStatus.RUNNING] == "running"

    def test_completed_maps_to_done(self):
        assert _TASK_TO_CARD_STATUS[TaskStatus.COMPLETED] == "done"

    def test_quarantined_fake_result_maps_to_quarantined(self):
        assert (
            _TASK_TO_CARD_STATUS[TaskStatus.QUARANTINED_FAKE_RESULT]
            == "quarantined"
        )


# ---------------------------------------------------------------------------
# Unit: ID mapping
# ---------------------------------------------------------------------------


class TestIdMapping:
    def test_card_id_prefix(self):
        assert _card_id_from_task("abc123") == "tb_abc123"

    def test_task_id_roundtrip(self):
        task_id = "task_abc123"
        card_id = _card_id_from_task(task_id)
        assert _task_id_from_card(card_id) == task_id


# ---------------------------------------------------------------------------
# Unit: task_to_card projection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_to_card_basic(board):
    task = await board.create("Test task", description="A body")
    card = task_to_card(task)

    assert card.id == f"tb_{task.id}"
    assert card.title == "Test task"
    assert card.body == "A body"
    assert card.status == "claimable"
    assert card.source_surface == "task_board"
    assert card.arjuna_weight == 0.5  # NORMAL priority


@pytest.mark.asyncio
async def test_task_to_card_urgent_priority(board):
    task = await board.create("Urgent", priority=TaskPriority.URGENT)
    card = task_to_card(task)
    assert card.arjuna_weight == 1.0


# ---------------------------------------------------------------------------
# Integration: adapter create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adapter_create(adapter):
    card = await adapter.create_task("Hello world", description="desc")

    assert card.title == "Hello world"
    assert card.body == "desc"
    assert card.status == "claimable"
    assert card.source_surface == "task_board"
    assert adapter.event_log.count() == 1


@pytest.mark.asyncio
async def test_adapter_create_with_priority(adapter):
    card = await adapter.create_task("High pri", priority=TaskPriority.HIGH)
    assert card.arjuna_weight == 0.75


# ---------------------------------------------------------------------------
# Integration: adapter transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adapter_assign(adapter):
    card = await adapter.create_task("Assign me")
    task_id = card.id[3:]  # strip "tb_" prefix

    updated = await adapter.transition_task(
        task_id, TaskStatus.ASSIGNED, agent_id="agent-1"
    )
    assert updated.status == "claimed"
    assert updated.version == 2
    assert adapter.event_log.count() == 2  # create + transition


@pytest.mark.asyncio
async def test_adapter_full_lifecycle(adapter):
    card = await adapter.create_task("Lifecycle task")
    task_id = card.id[3:]

    # PENDING → ASSIGNED
    card = await adapter.transition_task(task_id, TaskStatus.ASSIGNED, agent_id="a1")
    assert card.status == "claimed"

    # ASSIGNED → RUNNING
    card = await adapter.transition_task(task_id, TaskStatus.RUNNING)
    assert card.status == "running"

    # RUNNING → COMPLETED
    card = await adapter.transition_task(
        task_id, TaskStatus.COMPLETED, result="All done"
    )
    assert card.status == "done"
    assert card.version == 4

    # 4 events: create + 3 transitions
    assert adapter.event_log.count() == 4


@pytest.mark.asyncio
async def test_adapter_fail_and_requeue(adapter):
    card = await adapter.create_task("Failing task")
    task_id = card.id[3:]

    await adapter.transition_task(task_id, TaskStatus.ASSIGNED, agent_id="a1")
    await adapter.transition_task(task_id, TaskStatus.RUNNING)
    card = await adapter.transition_task(
        task_id, TaskStatus.FAILED, result="oops"
    )
    assert card.status == "failed"

    # Requeue: FAILED → PENDING
    card = await adapter.transition_task(
        task_id, TaskStatus.PENDING, reason="retry"
    )
    assert card.status == "claimable"


@pytest.mark.asyncio
async def test_adapter_invalid_transition_raises(adapter):
    card = await adapter.create_task("Bad transition")
    task_id = card.id[3:]

    with pytest.raises(TaskBoardError):
        # PENDING → COMPLETED is not a valid transition
        await adapter.transition_task(task_id, TaskStatus.COMPLETED)


# ---------------------------------------------------------------------------
# Integration: sync
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adapter_sync_all(board, tmp_path):
    # Create tasks directly on TaskBoard
    await board.create("Task A")
    await board.create("Task B")
    await board.create("Task C")

    # New adapter with empty card registry
    adapter = TaskBoardAdapter(board, BoardEventLog(path=tmp_path / "sync_events.db"))
    assert len(adapter.cards) == 0

    synced = await adapter.sync_all()
    assert synced == 3
    assert len(adapter.cards) == 3


@pytest.mark.asyncio
async def test_adapter_sync_one(board, tmp_path):
    task = await board.create("Sync me")

    adapter = TaskBoardAdapter(board, BoardEventLog(path=tmp_path / "sync1_events.db"))
    card = await adapter.sync_one(task.id)

    assert card is not None
    assert card.title == "Sync me"
    assert card.id == f"tb_{task.id}"


@pytest.mark.asyncio
async def test_adapter_sync_incremental(board, tmp_path):
    await board.create("Incremental")

    adapter = TaskBoardAdapter(board, BoardEventLog(path=tmp_path / "incr_events.db"))
    await adapter.sync_all()
    assert len(adapter.cards) == 1

    # Sync again — no change, so synced count should be 0
    synced = await adapter.sync_all()
    assert synced == 0


# ---------------------------------------------------------------------------
# Integration: get / list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adapter_get_card(adapter):
    card = await adapter.create_task("Get me")
    found = adapter.get_card(card.id)
    assert found is not None
    assert found.title == "Get me"


@pytest.mark.asyncio
async def test_adapter_list_by_status(adapter):
    await adapter.create_task("A")
    await adapter.create_task("B")

    claimable = adapter.list_cards(status="claimable")
    assert len(claimable) == 2

    running = adapter.list_cards(status="running")
    assert len(running) == 0


@pytest.mark.asyncio
async def test_adapter_list_all(adapter):
    await adapter.create_task("X")
    await adapter.create_task("Y")

    all_cards = adapter.list_cards()
    assert len(all_cards) == 2


@pytest.mark.asyncio
async def test_adapter_sync_all_beyond_default_limit(board, tmp_path):
    """Regression: sync_all must retrieve ALL tasks, not just the first 50."""
    for i in range(75):
        await board.create(f"Task {i:03d}")

    adapter = TaskBoardAdapter(board, BoardEventLog(path=tmp_path / "bulk_events.db"))
    synced = await adapter.sync_all()
    assert synced == 75
    assert len(adapter.cards) == 75
