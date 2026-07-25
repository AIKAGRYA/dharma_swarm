"""Non-authoritative TaskBoard → BoardStore command projection boundary.

The TaskBoard remains canonical during this migration.  This outbox projects a
completed canonical write into the app-scoped BoardStore facade; projection
failure is observable but never changes the already-returned TaskBoard result.
"""

from __future__ import annotations

import logging

from dharma_swarm.board.adapters.taskboard_adapter import TaskBoardAdapter
from dharma_swarm.board.event_log import BoardEvent
from dharma_swarm.board.facade import BoardStoreFacade
from dharma_swarm.board.models import Card
from dharma_swarm.models import TaskStatus

logger = logging.getLogger(__name__)


class TaskCommandOutbox:
    """Best-effort shadow publisher for canonical TaskBoard command writes."""

    def __init__(self, *, facade: BoardStoreFacade, adapter: TaskBoardAdapter) -> None:
        self.facade = facade
        self.adapter = adapter
        self.last_error_type = ""

    def _record_projection_error(self, task_id: str, operation: str, exc: Exception) -> None:
        self.last_error_type = type(exc).__name__
        logger.warning(
            "BoardStore shadow projection failed for task %s (%s): %s",
            task_id,
            operation,
            self.last_error_type,
        )
        try:
            self.facade.event_log.append(
                BoardEvent(
                    kind="adapter_error",
                    actor_id="command_api",
                    actor_kind="facade",
                    idempotency_key=f"shadow_error_{operation}_{task_id}",
                    detail={
                        "operation": operation,
                        "mode": "shadow",
                        "error_type": self.last_error_type,
                    },
                )
            )
        except Exception:
            logger.warning(
                "BoardStore shadow error event could not be recorded for task %s (%s)",
                task_id,
                operation,
            )

    def _project_card_best_effort(self, task_id: str, card: Card, operation: str) -> bool:
        try:
            self.facade.project_card(card, operation=operation)
        except Exception as exc:
            self._record_projection_error(task_id, operation, exc)
            return False
        self.last_error_type = ""
        return True

    async def publish(self, task_id: str, *, operation: str) -> bool:
        """Project one canonical task and append a BoardStore audit event."""
        try:
            card = await self.adapter.sync_one(task_id)
            if card is None:
                raise KeyError(f"Task not found after canonical {operation}")
        except Exception as exc:
            self._record_projection_error(task_id, operation, exc)
            return False
        return self._project_card_best_effort(task_id, card, operation)

    async def transition(
        self,
        task_id: str,
        to_status: TaskStatus,
        **kwargs: object,
    ) -> Card:
        """Write through the TaskBoard adapter, then project into the facade."""
        card = await self.adapter.transition_task(
            task_id,
            to_status,
            _emit_event=False,
            **kwargs,
        )
        self._project_card_best_effort(task_id, card, "transition")
        return card

    async def cancel(self, task_id: str) -> Card:
        """Cancel through the canonical adapter and retain the TaskBoard ID mapping."""
        card = await self.adapter.transition_task(
            task_id,
            TaskStatus.CANCELLED,
            _emit_event=False,
        )
        self._project_card_best_effort(task_id, card, "cancel")
        return card
