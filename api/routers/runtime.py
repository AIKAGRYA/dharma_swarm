"""Runtime graph inspection endpoints backed by RuntimeStateStore."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Query

from api.models import ApiResponse
from dharma_swarm.operator_views import OperatorViews
from dharma_swarm.runtime_state import DEFAULT_RUNTIME_DB, RuntimeStateStore

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


def _runtime_db_path() -> Path:
    configured = os.getenv("DHARMA_RUNTIME_DB", "").strip()
    return Path(configured) if configured else DEFAULT_RUNTIME_DB


def _operator_views() -> OperatorViews:
    return OperatorViews(RuntimeStateStore(_runtime_db_path()))


@router.get("/graph")
async def runtime_graph(
    session_id: str | None = Query(None, description="Optional runtime session filter."),
    task_id: str | None = Query(None, description="Optional task filter."),
    topology: str | None = Query(None, description="Optional topology filter."),
    limit: int = Query(20, ge=1, le=200, description="Maximum topology/run records."),
    receipt_limit: int = Query(50, ge=1, le=500, description="Maximum runtime receipts."),
) -> ApiResponse:
    """Return live topology graph state, runs, checkpoints, handoffs, and receipts."""
    try:
        snapshot = await _operator_views().runtime_graph(
            session_id=session_id,
            task_id=task_id,
            topology=topology,
            limit=limit,
            receipt_limit=receipt_limit,
        )
        return ApiResponse(data=snapshot)
    except Exception as exc:
        return ApiResponse(
            status="error",
            data=None,
            error=f"runtime graph unavailable: {exc}",
        )


@router.get("/sessions")
async def runtime_sessions(
    status: str | None = Query(None, description="Optional runtime session status filter."),
    limit: int = Query(20, ge=1, le=200, description="Maximum session records."),
) -> ApiResponse:
    """Return persisted runtime session/thread state."""
    try:
        snapshot = await _operator_views().runtime_sessions(
            status=status,
            limit=limit,
        )
        return ApiResponse(data=snapshot)
    except Exception as exc:
        return ApiResponse(
            status="error",
            data=None,
            error=f"runtime sessions unavailable: {exc}",
        )


@router.get("/runs")
async def runtime_runs(
    session_id: str | None = Query(None, description="Optional runtime session filter."),
    task_id: str | None = Query(None, description="Optional task filter."),
    status: str | None = Query(None, description="Optional run status filter."),
    limit: int = Query(20, ge=1, le=200, description="Maximum run records."),
) -> ApiResponse:
    """Return persisted delegation runs with checkpoint summary fields."""
    try:
        snapshot = await _operator_views().runtime_runs(
            session_id=session_id,
            task_id=task_id,
            status=status,
            limit=limit,
        )
        return ApiResponse(data=snapshot)
    except Exception as exc:
        return ApiResponse(
            status="error",
            data=None,
            error=f"runtime runs unavailable: {exc}",
        )


@router.get("/runs/{run_id}")
async def runtime_run_detail(run_id: str) -> ApiResponse:
    """Return canonical runtime ledger detail for one run."""
    try:
        snapshot = await _operator_views().runtime_run_detail(run_id)
        return ApiResponse(data=snapshot)
    except Exception as exc:
        return ApiResponse(
            status="error",
            data=None,
            error=f"runtime run detail unavailable: {exc}",
        )


@router.get("/checkpoints")
async def runtime_checkpoints(
    session_id: str | None = Query(None, description="Optional runtime session filter."),
    task_id: str | None = Query(None, description="Optional task filter."),
    topology: str | None = Query(None, description="Optional topology filter."),
    limit: int = Query(20, ge=1, le=200, description="Maximum checkpoint records."),
) -> ApiResponse:
    """Return persisted checkpoint/topology history snapshots."""
    try:
        snapshot = await _operator_views().runtime_checkpoints(
            session_id=session_id,
            task_id=task_id,
            topology=topology,
            limit=limit,
        )
        return ApiResponse(data=snapshot)
    except Exception as exc:
        return ApiResponse(
            status="error",
            data=None,
            error=f"runtime checkpoints unavailable: {exc}",
        )


@router.get("/events")
async def runtime_events(
    session_id: str | None = Query(None, description="Optional runtime session filter."),
    ledger_kind: str | None = Query(None, description="Optional ledger kind filter."),
    event_name: str | None = Query(None, description="Optional event name filter."),
    limit: int = Query(20, ge=1, le=500, description="Maximum runtime event records."),
) -> ApiResponse:
    """Return persisted runtime/session event history."""
    try:
        snapshot = await _operator_views().runtime_events(
            session_id=session_id,
            ledger_kind=ledger_kind,
            event_name=event_name,
            limit=limit,
        )
        return ApiResponse(data=snapshot)
    except Exception as exc:
        return ApiResponse(
            status="error",
            data=None,
            error=f"runtime events unavailable: {exc}",
        )
