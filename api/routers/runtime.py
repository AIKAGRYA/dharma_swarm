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
