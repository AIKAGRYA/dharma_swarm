"""Read-only Mission Control HTTP projection for external owner clients.

This is the owner-side half of the Fleet Hub "authenticated read-only owner
adapter" (``fleet-hub/docs/FLEET_HUB_V1_IMPLEMENTATION.md`` promotion gate 2).
Fleet Hub must never open TaskBoard/RuntimeStateStore SQLite files itself, so
the canonical owner exposes the same projection its MCP surface already serves
(``dharma_swarm/mission_control_mcp.py``) over the dashboard's bearer-guarded
HTTP ingress (``api/main.py`` ``IngressAuthMiddleware``).

Contract, deliberately narrow:

- reads only; no route here can create, claim, heartbeat, or finish anything;
- every read runs against a disposable immutable copy of the owner databases
  (``_ImmutableSnapshotMissionControl``), never the live files;
- a snapshot is an observed projection: ``authority`` is the literal owner
  string and ``proves_executor_liveness`` is always ``False``;
- absent state is a typed ``state_not_initialized`` 503, never an empty list
  masquerading as "no missions".

The wire shape of ``snapshot`` is the JSON projection of
``dharma_swarm.mission_control_contract.MissionSnapshot`` and is validated on
the consumer side by Fleet Hub's ``hub.mission_contract.validate_owner_snapshot``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.mission_control_contract import (
    SESSION_PREFIX,
    MissionControlError,
    mission_view,
)
from dharma_swarm.mission_control_mcp import (
    SCHEMA_VERSION,
    _ImmutableSnapshotMissionControl,
    _json_projection,
)

router = APIRouter(prefix="/api/mission-control", tags=["mission-control"])

AUTHORITY = "TaskBoard+RuntimeStateStore"
MAX_LIST_LIMIT = 200
_MISSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

TASK_DB_ENV = "DHARMA_MISSION_CONTROL_TASK_DB"
RUNTIME_DB_ENV = "DHARMA_MISSION_CONTROL_RUNTIME_DB"


def owner_db_paths() -> tuple[Path, Path]:
    """Resolve the canonical owner databases (same roots as the MCP surface).

    ``DHARMA_STATE_DIR`` moves the whole state tree; the two explicit env
    overrides exist so a test or a read-only replica can point at copies
    without relocating ``~/.dharma``.  Paths are resolved per request so key
    rotation and state relocation never require a process restart.
    """

    state_dir = dharma_state_dir("DHARMA_STATE_DIR")
    task_db = Path(os.environ.get(TASK_DB_ENV) or state_dir / "db" / "tasks.db")
    runtime_db = Path(
        os.environ.get(RUNTIME_DB_ENV) or state_dir / "state" / "runtime.db"
    )
    return task_db, runtime_db


def _error(status: int, code: str, message: str, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {
        "ok": False,
        "error_code": code,
        "message": message,
        "schema_version": SCHEMA_VERSION,
        "authority": AUTHORITY,
        "proves_executor_liveness": False,
    }
    body.update(extra)
    return JSONResponse(status_code=status, content=body)


def _state_not_initialized(task_db: Path, runtime_db: Path) -> JSONResponse | None:
    missing = [
        name
        for name, path in (("runtime_db", runtime_db), ("task_db", task_db))
        if not path.is_file()
    ]
    if not missing:
        return None
    return _error(
        503,
        "state_not_initialized",
        "Mission Control owner state is not initialized on this host",
        missing=missing,
    )


def _list_mission_views(runtime_db: Path, limit: int) -> list[dict[str, Any]]:
    """Project mission sessions from a disposable immutable runtime copy."""

    import sqlite3
    import tempfile

    from dharma_swarm.mission_control_mcp import _copy_immutable_sqlite
    from dharma_swarm.runtime_state import RuntimeStateStore

    with tempfile.TemporaryDirectory(prefix="dharma-mission-control-list-") as raw:
        copy = Path(raw) / "runtime.db"
        _copy_immutable_sqlite(runtime_db, copy)
        store = RuntimeStateStore(copy, include_memory_plane=False)
        try:
            # Sessions are ordered by updated_at; mission sessions share one
            # prefix, so over-fetch then filter keeps the projection bounded.
            sessions = store.list_sessions_sync(limit=max(limit * 4, 50))
        except sqlite3.Error:
            return []
    views: list[dict[str, Any]] = []
    for session in sessions:
        if not session.session_id.startswith(SESSION_PREFIX):
            continue
        view = mission_view(session)
        if not view.mission_id or not _MISSION_ID.fullmatch(view.mission_id):
            continue
        views.append(_json_projection(view))
        if len(views) >= limit:
            break
    return views


@router.get("/missions")
async def list_missions(
    limit: int = Query(default=50, ge=1, le=MAX_LIST_LIMIT),
) -> JSONResponse:
    """List mission views known to the runtime owner (bounded, read-only)."""

    import asyncio

    task_db, runtime_db = owner_db_paths()
    if not runtime_db.is_file():
        return _error(
            503,
            "state_not_initialized",
            "Mission Control owner state is not initialized on this host",
            missing=["runtime_db"],
        )
    missions = await asyncio.to_thread(_list_mission_views, runtime_db, limit)
    return JSONResponse(
        content={
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "authority": AUTHORITY,
            "proves_executor_liveness": False,
            "discovery_complete": False,
            "count": len(missions),
            "missions": missions,
            "commands": [],
            "commands_available": False,
        }
    )


@router.get("/missions/{mission_id}/snapshot")
async def mission_snapshot(mission_id: str) -> JSONResponse:
    """Return one mission's observed snapshot projection."""

    if not _MISSION_ID.fullmatch(mission_id):
        return _error(400, "invalid_mission_id", "Mission ID is invalid")
    task_db, runtime_db = owner_db_paths()
    not_ready = _state_not_initialized(task_db, runtime_db)
    if not_ready is not None:
        return not_ready
    control = _ImmutableSnapshotMissionControl(task_db=task_db, runtime_db=runtime_db)
    try:
        snapshot = await control.get_snapshot(mission_id)
    except MissionControlError as exc:
        return _error(400, "invalid_mission_id", str(exc))
    if snapshot is None:
        return _error(
            404,
            "not_found",
            f"mission {mission_id!r} was not found",
            mission_id=mission_id,
        )
    projected = _json_projection(snapshot)
    return JSONResponse(
        content={
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "authority": AUTHORITY,
            "proves_executor_liveness": False,
            "observed_at": projected["observed_at"],
            "snapshot": projected,
            "commands": [],
            "commands_available": False,
        }
    )


__all__ = ["router", "owner_db_paths", "TASK_DB_ENV", "RUNTIME_DB_ENV"]
