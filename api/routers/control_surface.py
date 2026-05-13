"""Control Surface API — declared intent vs observed reality.

GET  /api/control-surface/summary         -> coherence summary counts
GET  /api/control-surface/rows            -> full list of ControlSurfaceRow
GET  /api/control-surface/rows/{id}       -> single row by id
POST /api/control-surface/rows/{id}/handoff-prompt -> agent handoff prompt
GET  /api/control-surface/stream          -> SSE stream of updated rows

ACTIVE_SURFACE_MANIFEST.yaml declares intent; observed reality comes from
runtime/code/evidence adapters.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.models import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control-surface", tags=["control-surface"])


def _build_rows() -> list[dict[str, Any]]:
    from dharma_swarm.operator_core.control_surface import build_control_surface_rows
    rows = build_control_surface_rows()
    return [row.to_dict() for row in rows]


def _find_row_object(row_id: str):  # noqa: ANN202
    from dharma_swarm.operator_core.control_surface import build_control_surface_rows
    rows = build_control_surface_rows()
    for row in rows:
        if row.id == row_id:
            return row
    return None


@router.get("/summary")
async def control_surface_summary() -> ApiResponse:
    """Lightweight coherence summary with counts by state."""
    try:
        from dharma_swarm.operator_core.control_surface import (
            build_control_surface_rows,
            build_control_surface_summary,
        )
        rows = build_control_surface_rows()
        summary = build_control_surface_summary(rows)
        return ApiResponse(data=summary)
    except Exception as e:
        logger.exception("control-surface/summary failed")
        return ApiResponse(status="error", data=None, error=str(e))


@router.get("/stream")
async def control_surface_stream():
    """SSE stream pushing updated rows when the projection changes."""
    async def event_generator():  # noqa: ANN202
        last_hash: str | None = None
        while True:
            try:
                row_dicts = _build_rows()
                payload = json.dumps(row_dicts, sort_keys=True)
                current_hash = hashlib.md5(payload.encode()).hexdigest()  # noqa: S324
                if current_hash != last_hash:
                    yield f"data: {payload}\n\n"
                    last_hash = current_hash
            except Exception:
                logger.exception("control-surface/stream iteration failed")
            await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/rows")
async def control_surface_rows() -> ApiResponse:
    """All control surface rows — declared intent reconciled with observed reality."""
    try:
        return ApiResponse(data=_build_rows())
    except Exception as e:
        logger.exception("control-surface/rows failed")
        return ApiResponse(status="error", data=None, error=str(e))


@router.post("/rows/{row_id:path}/handoff-prompt")
async def control_surface_handoff_prompt(row_id: str) -> ApiResponse:
    """Generate a scoped agent handoff prompt for a control surface row."""
    try:
        from dharma_swarm.operator_core.control_surface import generate_handoff_prompt

        row = _find_row_object(row_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"row '{row_id}' not found")
        prompt = generate_handoff_prompt(row)
        return ApiResponse(data=prompt.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("control-surface/handoff-prompt failed")
        return ApiResponse(status="error", data=None, error=str(e))


@router.get("/rows/{row_id:path}")
async def control_surface_row(row_id: str) -> ApiResponse:
    """Single control surface row by ID."""
    try:
        rows = _build_rows()
        for row in rows:
            if row["id"] == row_id:
                return ApiResponse(data=row)
        raise HTTPException(status_code=404, detail=f"row '{row_id}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("control-surface/rows/<id> failed")
        return ApiResponse(status="error", data=None, error=str(e))
