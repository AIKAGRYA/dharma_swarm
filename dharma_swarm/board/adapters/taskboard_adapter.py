"""TaskBoard adapter — maps TaskBoard (async SQLite FSM) behind BoardStore facade.

This is Step 3 of the 5-step BoardStore migration plan:
  1. Scaffold package (done)
  2. Schema + event log (done)
  3. Adapt first store (this file)
  4. Client SDK
  5. Cutover

The adapter provides:
- Bidirectional mapping: Task ↔ Card
- Event emission: every TaskBoard mutation emits a BoardEvent
- Compatibility: existing TaskBoard callers are NOT changed; the adapter
  is a *projection* layer that keeps the facade's card registry in sync.
- Rollback semantics: if a TaskBoard op fails, no event is emitted.

The adapter does NOT replace TaskBoard. It sits beside it. Both the direct
TaskBoard API and the facade API remain valid. The adapter ensures that
facade consumers see TaskBoard tasks as Cards with proper status mapping.
"""

from __future__ import annotations

import logging
from typing import Any

from dharma_swarm.board.event_log import BoardEvent, BoardEventLog
from dharma_swarm.board.models import (
    Card,
    CardId,
    CardStatus,
    IsoDatetime,
    Version,
)
from dharma_swarm.models import Task, TaskPriority, TaskStatus
from dharma_swarm.task_board import TaskBoard

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status mapping: TaskBoard FSM → Card statuses
# ---------------------------------------------------------------------------

_TASK_TO_CARD_STATUS: dict[TaskStatus, CardStatus] = {
    TaskStatus.PENDING: "claimable",
    TaskStatus.ASSIGNED: "claimed",
    TaskStatus.RUNNING: "running",
    TaskStatus.COMPLETED: "done",
    TaskStatus.FAILED: "failed",
    TaskStatus.CANCELLED: "cancelled",
    TaskStatus.QUARANTINED_FAKE_RESULT: "quarantined",
}

_CARD_TO_TASK_STATUS: dict[CardStatus, TaskStatus] = {
    "claimable": TaskStatus.PENDING,
    "claimed": TaskStatus.ASSIGNED,
    "running": TaskStatus.RUNNING,
    "done": TaskStatus.COMPLETED,
    "failed": TaskStatus.FAILED,
    "cancelled": TaskStatus.CANCELLED,
}

# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------

_PRIORITY_TO_WEIGHT: dict[TaskPriority, float] = {
    TaskPriority.LOW: 0.25,
    TaskPriority.NORMAL: 0.50,
    TaskPriority.HIGH: 0.75,
    TaskPriority.URGENT: 1.00,
}


def _now_iso() -> IsoDatetime:
    import time

    return IsoDatetime(time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()))


def _card_id_from_task(task_id: str) -> CardId:
    return CardId(f"tb_{task_id}")


def _task_id_from_card(card_id: CardId) -> str:
    if card_id.startswith("tb_"):
        return card_id[3:]
    return card_id


# ---------------------------------------------------------------------------
# Projection: Task → Card (read-only transform)
# ---------------------------------------------------------------------------


def task_to_card(task: Task) -> Card:
    """Project a TaskBoard Task into the BoardStore Card schema."""
    card_status = _TASK_TO_CARD_STATUS.get(task.status, "inbox")
    created_at = IsoDatetime(task.created_at.isoformat() if task.created_at else "")
    updated_at = IsoDatetime(task.updated_at.isoformat() if task.updated_at else "")

    return Card(
        id=_card_id_from_task(task.id),
        title=task.title,
        body=task.description,
        status=card_status,
        assignee_kind="unknown",
        arjuna_weight=_PRIORITY_TO_WEIGHT.get(task.priority, 0.5),
        created_by=task.created_by,
        created_at=created_at,
        updated_at=updated_at,
        last_transitioned_at=updated_at,
        source_surface="task_board",
        version=Version(1),
        idempotency_key=f"tb_sync_{task.id}",
    )


# ---------------------------------------------------------------------------
# TaskBoardAdapter — projection + event bridge
# ---------------------------------------------------------------------------


class TaskBoardAdapter:
    """Bridges TaskBoard operations into the BoardStore facade layer.

    Usage:
        board = TaskBoard(db_path)
        await board.init_db()
        event_log = BoardEventLog()
        adapter = TaskBoardAdapter(board, event_log)

        # Create via adapter (emits BoardEvent + writes to TaskBoard)
        card = await adapter.create_task("Do X", priority=TaskPriority.HIGH)

        # Or sync existing tasks into the card registry
        await adapter.sync_all()
    """

    def __init__(
        self,
        task_board: TaskBoard,
        event_log: BoardEventLog | None = None,
    ) -> None:
        self._board = task_board
        self._event_log = event_log or BoardEventLog()
        self._cards: dict[CardId, Card] = {}

    @property
    def event_log(self) -> BoardEventLog:
        return self._event_log

    @property
    def task_board(self) -> TaskBoard:
        """Return the canonical TaskBoard owned by this projection adapter."""
        return self._board

    @property
    def cards(self) -> dict[CardId, Card]:
        return dict(self._cards)

    def get_card(self, card_id: CardId) -> Card | None:
        return self._cards.get(card_id)

    def list_cards(self, status: CardStatus | None = None) -> list[Card]:
        if status is None:
            return list(self._cards.values())
        return [c for c in self._cards.values() if c.status == status]

    # -- Write operations (delegate to TaskBoard, then project) -------------

    async def create_task(
        self,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        created_by: str = "system",
        depends_on: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Card:
        """Create a task via TaskBoard and project it as a Card."""
        task = await self._board.create(
            title=title,
            description=description,
            priority=priority,
            created_by=created_by,
            depends_on=depends_on,
            metadata=metadata,
        )
        card = task_to_card(task)
        self._cards[card.id] = card

        self._event_log.append(
            BoardEvent(
                kind="card_created",
                card_id=card.id,
                actor_id=created_by,
                actor_kind="agent",
                card_version=Version(1),
                to_status=card.status,
                idempotency_key=card.idempotency_key,
            )
        )
        logger.info("adapter.create: %s → %s", task.id, card.id)
        return card

    async def transition_task(
        self,
        task_id: str,
        to_status: TaskStatus,
        actor_id: str = "adapter",
        **kwargs: Any,
    ) -> Card:
        """Transition a task and emit a BoardEvent for the change.

        Delegates to the appropriate TaskBoard method (assign, start,
        complete, fail, cancel, requeue) based on to_status.
        """
        method_map: dict[TaskStatus, str] = {
            TaskStatus.ASSIGNED: "assign",
            TaskStatus.RUNNING: "start",
            TaskStatus.COMPLETED: "complete",
            TaskStatus.FAILED: "fail",
            TaskStatus.CANCELLED: "cancel",
            TaskStatus.PENDING: "requeue",
        }

        method_name = method_map.get(to_status)
        if method_name is None:
            raise ValueError(f"Unsupported target status: {to_status}")

        method = getattr(self._board, method_name)

        if to_status == TaskStatus.ASSIGNED:
            updated_task = await method(task_id, kwargs.get("agent_id", actor_id))
        elif to_status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            updated_task = await method(task_id, kwargs.get("result", ""))
        elif to_status == TaskStatus.PENDING:
            updated_task = await method(task_id, reason=kwargs.get("reason", ""))
        else:
            updated_task = await method(task_id)

        card_id = _card_id_from_task(task_id)
        old_card = self._cards.get(card_id)
        from_status = old_card.status if old_card else None

        new_card = task_to_card(updated_task)
        new_version = Version((old_card.version + 1) if old_card else 1)
        new_card = new_card.model_copy(update={"version": new_version})
        self._cards[card_id] = new_card

        if kwargs.get("_emit_event", True):
            self._event_log.append(
                BoardEvent(
                    kind="card_transitioned",
                    card_id=card_id,
                    actor_id=actor_id,
                    actor_kind="agent",
                    card_version=new_version,
                    from_status=from_status,
                    to_status=new_card.status,
                    idempotency_key=f"tb_trans_{task_id}_{to_status.value}",
                )
            )
        logger.info(
            "adapter.transition: %s %s→%s",
            card_id,
            from_status or "?",
            new_card.status,
        )
        return new_card

    # -- Sync: bulk-project existing TaskBoard state into cards --------------

    async def sync_all(self) -> int:
        """Load all tasks from TaskBoard and project them as Cards.

        Passes a high limit to avoid the default cap of 50.

        Returns the number of cards synced.
        """
        tasks = await self._board.list_tasks(limit=100_000)
        synced = 0
        for task in tasks:
            card = task_to_card(task)
            existing = self._cards.get(card.id)
            if existing is None or existing.status != card.status:
                if existing:
                    card = card.model_copy(
                        update={"version": Version(existing.version + 1)}
                    )
                self._cards[card.id] = card
                synced += 1
        logger.info("adapter.sync_all: %d cards synced", synced)
        return synced

    async def sync_one(self, task_id: str) -> Card | None:
        """Sync a single task from TaskBoard into the card registry."""
        task = await self._board.get(task_id)
        if task is None:
            return None
        card = task_to_card(task)
        existing = self._cards.get(card.id)
        if existing:
            card = card.model_copy(
                update={"version": Version(existing.version + 1)}
            )
        self._cards[card.id] = card
        return card
