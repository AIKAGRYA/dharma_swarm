"""Runtime graph inspection endpoints backed by RuntimeStateStore."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

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


@router.get("/events/stream")
async def runtime_events_stream(
    session_id: str | None = Query(None, description="Optional runtime session filter."),
    ledger_kind: str | None = Query(None, description="Optional ledger kind filter."),
    event_name: str | None = Query(None, description="Optional event name filter."),
    limit: int = Query(20, ge=1, le=500, description="Maximum event records per poll."),
    poll_seconds: float = Query(2.0, ge=0.01, le=30.0, description="SSE polling interval."),
    max_events: int | None = Query(None, ge=1, le=1000, description="Optional finite stream cap."),
) -> StreamingResponse:
    """Stream persisted runtime/session events as server-sent events."""

    async def event_generator():  # noqa: ANN202
        seen_event_ids: set[str] = set()
        emitted = 0
        while True:
            snapshot = await _operator_views().runtime_events(
                session_id=session_id,
                ledger_kind=ledger_kind,
                event_name=event_name,
                limit=limit,
            )
            events = list(reversed(snapshot["events"]))
            for event in events:
                event_id = str(event.get("event_id") or "")
                if event_id in seen_event_ids:
                    continue
                seen_event_ids.add(event_id)
                payload = json.dumps(event, sort_keys=True)
                yield f"event: runtime_event\ndata: {payload}\n\n"
                emitted += 1
                if max_events is not None and emitted >= max_events:
                    return
            await asyncio.sleep(poll_seconds)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/interrupts")
async def runtime_interrupts(
    session_id: str | None = Query(None, description="Optional runtime session filter."),
    status: str | None = Query(None, description="Optional interrupt/control status filter."),
    limit: int = Query(20, ge=1, le=200, description="Maximum interrupt/control records."),
) -> ApiResponse:
    """Return persisted interrupt, resume, and human-approval runtime state."""
    try:
        snapshot = await _operator_views().runtime_interrupts(
            session_id=session_id,
            status=status,
            limit=limit,
        )
        return ApiResponse(data=snapshot)
    except Exception as exc:
        return ApiResponse(
            status="error",
            data=None,
            error=f"runtime interrupts unavailable: {exc}",
        )


@router.get("/assistants")
async def runtime_assistants(
    limit: int = Query(50, ge=1, le=200, description="Maximum assistant records."),
) -> ApiResponse:
    """Return Agent Server-style assistants and configurations from runtime state."""
    try:
        snapshot = await _operator_views().runtime_assistants(limit=limit)
        return ApiResponse(data=snapshot)
    except Exception as exc:
        return ApiResponse(
            status="error",
            data=None,
            error=f"runtime assistants unavailable: {exc}",
        )


@router.get("/background-jobs")
async def runtime_background_jobs(
    limit: int = Query(50, ge=1, le=200, description="Maximum background job records."),
) -> ApiResponse:
    """Return background/cron jobs and runs from runtime and cron storage."""
    try:
        snapshot = await _operator_views().runtime_background_jobs(limit=limit)
        return ApiResponse(data=snapshot)
    except Exception as exc:
        return ApiResponse(
            status="error",
            data=None,
            error=f"runtime background jobs unavailable: {exc}",
        )
