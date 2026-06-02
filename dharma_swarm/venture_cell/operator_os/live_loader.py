"""Read-only live state loaders for VentureCell Operator OS."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Mapping

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.models import TaskStatus
from dharma_swarm.operator_core.a2a_task_lifecycle import read_queue
from dharma_swarm.task_board import TaskBoard
from dharma_swarm.venture_cell.operator_os.projection import OperatorOSInputs


def default_state_root() -> Path:
    """Return the existing Dharma state root used by runtime organs."""

    return dharma_state_dir("DHARMA_STATE_ROOT", "DHARMA_STATE_DIR")


def default_task_db_path(state_root: Path | str | None = None) -> Path:
    """Return the existing TaskBoard database path for a state root."""

    root = Path(state_root).expanduser() if state_root is not None else default_state_root()
    return root / "db" / "tasks.db"


async def load_task_board_tasks_async(
    *,
    task_db_path: Path | str | None = None,
    state_root: Path | str | None = None,
    status: str | TaskStatus | None = None,
    assigned_to: str | None = None,
    limit: int = 50,
) -> tuple[Any, ...]:
    """Load TaskBoard rows from an injected database path."""

    db_path = (
        Path(task_db_path).expanduser()
        if task_db_path is not None
        else default_task_db_path(state_root)
    )
    if not db_path.exists():
        return ()
    board = TaskBoard(db_path)
    tasks = await board.list_tasks(
        status=_coerce_status(status),
        assigned_to=assigned_to,
        limit=limit,
    )
    return tuple(tasks)


def load_task_board_tasks(
    *,
    task_db_path: Path | str | None = None,
    state_root: Path | str | None = None,
    status: str | TaskStatus | None = None,
    assigned_to: str | None = None,
    limit: int = 50,
) -> tuple[Any, ...]:
    """Synchronously load TaskBoard rows for CLI/report surfaces."""

    return asyncio.run(
        load_task_board_tasks_async(
            task_db_path=task_db_path,
            state_root=state_root,
            status=status,
            assigned_to=assigned_to,
            limit=limit,
        )
    )


def load_a2a_task_rows(
    *,
    state_root: Path | str | None = None,
    limit: int = 50,
) -> tuple[Mapping[str, Any], ...]:
    """Load A2A filesystem queue rows as evidence-only task rows."""

    rows = read_queue(state_root)
    return tuple(rows[:limit])


def load_live_operator_inputs(
    *,
    bundle_path: Path | str | None = None,
    state_root: Path | str | None = None,
    task_db_path: Path | str | None = None,
    task_limit: int = 50,
    a2a_limit: int = 50,
    max_memory_scan: int = 5000,
) -> OperatorOSInputs:
    """Build projection inputs from existing local organs."""

    root = Path(state_root).expanduser() if state_root is not None else default_state_root()
    return OperatorOSInputs(
        bundle_path=Path(bundle_path).expanduser() if bundle_path is not None else None,
        task_board_tasks=load_task_board_tasks(
            task_db_path=task_db_path,
            state_root=root,
            limit=task_limit,
        ),
        a2a_tasks=load_a2a_task_rows(state_root=root, limit=a2a_limit),
        state_root=root,
        max_memory_scan=max_memory_scan,
    )


def _coerce_status(value: str | TaskStatus | None) -> TaskStatus | None:
    if value is None or isinstance(value, TaskStatus):
        return value
    return TaskStatus(str(value))
