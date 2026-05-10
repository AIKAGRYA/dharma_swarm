"""Mirror external execution lanes into the canonical task board."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dharma_swarm.models import Task, TaskPriority, TaskStatus
from dharma_swarm.task_board import TaskBoard

_TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
}

_ACTIVE_STATUSES = {
    TaskStatus.PENDING,
    TaskStatus.ASSIGNED,
    TaskStatus.RUNNING,
}


@dataclass
class MirroredTaskSpec:
    mirror_key: str
    title: str
    description: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    created_by: str = "system"
    assigned_to: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class CanonicalTaskMirror:
    """Project external task/activity state into the canonical task ledger."""

    def __init__(self, state_dir: Path) -> None:
        self._state_dir = Path(state_dir)
        self._board: TaskBoard | None = None

    async def sync(self, spec: MirroredTaskSpec) -> Task:
        """Create or update a mirrored task record."""
        board = await self._get_board()
        existing = await self._find_by_mirror_key(spec.mirror_key)
        payload = self._metadata(spec)
        if existing is not None:
            payload = self._preserve_episode_identity(existing, spec.mirror_key, payload)
        materialized = self._materialize(spec, payload)

        if existing is None:
            task = await board.create(
                title=materialized.title,
                description=materialized.description,
                priority=materialized.priority,
                created_by=materialized.created_by,
                assigned_to=materialized.assigned_to,
                metadata=materialized.metadata,
            )
            return await self._advance(task, materialized)

        if existing.status in _TERMINAL_STATUSES and spec.status in _ACTIVE_STATUSES:
            payload["mirror_parent_key"] = spec.mirror_key
            payload["mirror_key"] = f"{spec.mirror_key}:{int(time.time())}"
            materialized = self._materialize(spec, payload)
            task = await board.create(
                title=materialized.title,
                description=materialized.description,
                priority=materialized.priority,
                created_by=materialized.created_by,
                assigned_to=materialized.assigned_to,
                metadata=materialized.metadata,
            )
            return await self._advance(task, materialized)

        await board.update_task(
            existing.id,
            title=materialized.title,
            description=materialized.description,
            priority=materialized.priority,
            assigned_to=materialized.assigned_to,
            created_by=materialized.created_by,
            result=materialized.result,
            metadata=materialized.metadata,
        )
        refreshed = await board.get(existing.id)
        assert refreshed is not None
        return await self._advance(refreshed, materialized)

    async def _get_board(self) -> TaskBoard:
        if self._board is None:
            db_path = self._state_dir / "db" / "tasks.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._board = TaskBoard(db_path)
            await self._board.init_db()
        return self._board

    async def _find_by_mirror_key(self, mirror_key: str) -> Task | None:
        board = await self._get_board()
        tasks = await board.list_tasks(limit=2000)
        for task in tasks:
            metadata = dict(task.metadata or {})
            current_key = str(metadata.get("mirror_key", "")).strip()
            parent_key = str(metadata.get("mirror_parent_key", "")).strip()
            if current_key == mirror_key or parent_key == mirror_key:
                return task
        return None

    @staticmethod
    def _metadata(spec: MirroredTaskSpec) -> dict[str, Any]:
        payload = dict(spec.metadata or {})
        payload["mirror_key"] = payload.get("mirror_key") or spec.mirror_key
        payload["external_status"] = spec.status.value
        return payload

    @staticmethod
    def _materialize(spec: MirroredTaskSpec, payload: dict[str, Any]) -> MirroredTaskSpec:
        return MirroredTaskSpec(
            mirror_key=str(payload.get("mirror_key") or spec.mirror_key),
            title=spec.title,
            description=spec.description,
            priority=spec.priority,
            created_by=spec.created_by,
            assigned_to=spec.assigned_to,
            status=spec.status,
            result=spec.result,
            metadata=dict(payload),
        )

    @staticmethod
    def _preserve_episode_identity(
        task: Task,
        requested_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = dict(task.metadata or {})
        current_key = str(metadata.get("mirror_key", "")).strip()
        parent_key = str(metadata.get("mirror_parent_key", "")).strip()

        if parent_key and current_key and parent_key == requested_key:
            payload["mirror_key"] = current_key
            payload["mirror_parent_key"] = parent_key
            return payload

        if parent_key:
            payload["mirror_parent_key"] = parent_key
        if current_key:
            payload["mirror_key"] = current_key
        return payload

    async def _advance(self, task: Task, spec: MirroredTaskSpec) -> Task:
        board = await self._get_board()
        metadata = self._metadata(spec)

        if task.status == spec.status:
            refreshed = await board.get(task.id)
            assert refreshed is not None
            return refreshed

        if spec.status == TaskStatus.PENDING:
            if task.status in {TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.ASSIGNED, TaskStatus.RUNNING}:
                return await board.requeue(
                    task.id,
                    reason=spec.result,
                    metadata=metadata,
                )
            refreshed = await board.get(task.id)
            assert refreshed is not None
            return refreshed

        if spec.status == TaskStatus.ASSIGNED:
            if task.status in {TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.RUNNING}:
                task = await board.requeue(task.id, reason=spec.result, metadata=metadata)
            if task.status == TaskStatus.PENDING:
                return await board.assign(
                    task.id,
                    spec.assigned_to or task.assigned_to or spec.created_by,
                    metadata=metadata,
                )
            refreshed = await board.get(task.id)
            assert refreshed is not None
            return refreshed

        if spec.status == TaskStatus.RUNNING:
            if task.status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
                task = await board.requeue(task.id, reason=spec.result, metadata=metadata)
            if task.status == TaskStatus.PENDING:
                task = await board.assign(
                    task.id,
                    spec.assigned_to or task.assigned_to or spec.created_by,
                    metadata=metadata,
                )
            if task.status == TaskStatus.ASSIGNED:
                return await board.start(task.id, metadata=metadata)
            refreshed = await board.get(task.id)
            assert refreshed is not None
            return refreshed

        if spec.status == TaskStatus.COMPLETED:
            task = await self._advance(
                task,
                MirroredTaskSpec(
                    **{**spec.__dict__, "status": TaskStatus.RUNNING},
                ),
            )
            return await board._set_status(
                task.id,
                TaskStatus.COMPLETED,
                result=spec.result,
                metadata=metadata,
            )

        if spec.status == TaskStatus.FAILED:
            task = await self._advance(
                task,
                MirroredTaskSpec(
                    **{**spec.__dict__, "status": TaskStatus.RUNNING},
                ),
            )
            return await board._set_status(
                task.id,
                TaskStatus.FAILED,
                result=spec.result,
                metadata=metadata,
            )

        if spec.status == TaskStatus.CANCELLED:
            if task.status in {TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.RUNNING}:
                return await board._set_status(
                    task.id,
                    TaskStatus.CANCELLED,
                    metadata=metadata,
                )
            refreshed = await board.get(task.id)
            assert refreshed is not None
            return refreshed

        refreshed = await board.get(task.id)
        assert refreshed is not None
        return refreshed
