"""Tests for task_board_mirror.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.models import TaskPriority, TaskStatus
from dharma_swarm.task_board import TaskBoard
from dharma_swarm.task_board_mirror import CanonicalTaskMirror, MirroredTaskSpec


@pytest.mark.asyncio
async def test_mirror_advances_task_through_lifecycle(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    mirror = CanonicalTaskMirror(state_dir)

    spec = MirroredTaskSpec(
        mirror_key="external:test:1",
        title="Mirror task",
        description="Mirror lifecycle",
        priority=TaskPriority.HIGH,
        created_by="external_system",
        assigned_to="external_system",
        status=TaskStatus.PENDING,
        metadata={"source": "external_system"},
    )

    await mirror.sync(spec)
    await mirror.sync(MirroredTaskSpec(**{**spec.__dict__, "status": TaskStatus.RUNNING}))
    completed = await mirror.sync(
        MirroredTaskSpec(
            **{
                **spec.__dict__,
                "status": TaskStatus.COMPLETED,
                "result": "done",
                "metadata": {"source": "external_system", "phase": "complete"},
            }
        )
    )

    assert completed.status == TaskStatus.COMPLETED
    assert completed.result == "done"
    assert completed.metadata["mirror_key"] == "external:test:1"
    assert completed.metadata["phase"] == "complete"


@pytest.mark.asyncio
async def test_mirror_creates_new_episode_when_terminal_task_reappears(tmp_path: Path) -> None:
    state_dir = tmp_path / ".dharma"
    mirror = CanonicalTaskMirror(state_dir)

    base = MirroredTaskSpec(
        mirror_key="persistent_agent:test:abc",
        title="Recurring conductor task",
        created_by="conductor_a",
        assigned_to="conductor_a",
        status=TaskStatus.COMPLETED,
        result="first pass",
        metadata={"source": "persistent_agent.self"},
    )
    await mirror.sync(base)

    reopened = await mirror.sync(
        MirroredTaskSpec(
            **{
                **base.__dict__,
                "status": TaskStatus.RUNNING,
                "result": "",
            }
        )
    )

    board = TaskBoard(state_dir / "db" / "tasks.db")
    await board.init_db()
    tasks = await board.list_tasks(limit=10)

    assert len(tasks) == 2
    assert reopened.status == TaskStatus.RUNNING
    assert reopened.metadata["mirror_parent_key"] == "persistent_agent:test:abc"
    assert reopened.metadata["mirror_key"].startswith("persistent_agent:test:abc:")

    completed = await mirror.sync(
        MirroredTaskSpec(
            **{
                **base.__dict__,
                "status": TaskStatus.COMPLETED,
                "result": "second pass",
            }
        )
    )

    refreshed = await board.get(reopened.id)
    assert refreshed is not None
    assert completed.id == reopened.id
    assert refreshed.status == TaskStatus.COMPLETED
    assert refreshed.result == "second pass"
    assert refreshed.metadata["mirror_parent_key"] == "persistent_agent:test:abc"
