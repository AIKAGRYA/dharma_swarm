"""Control Surface API — declared intent vs observed reality.

GET /api/control-surface/summary  -> coherence summary counts
GET /api/control-surface/rows     -> full list of ControlSurfaceRow
GET /api/control-surface/rows/{id} -> single row by id

ACTIVE_SURFACE_MANIFEST.yaml declares intent; observed reality comes from
runtime/code/evidence adapters.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from api.models import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control-surface", tags=["control-surface"])


def _build_rows() -> list[dict[str, Any]]:
    from dharma_swarm.operator_core.control_surface import build_control_surface_rows
    rows = build_control_surface_rows()
    return [row.to_dict() for row in rows]


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
        return ApiResponse(data=None, error=str(e))


@router.get("/rows")
async def control_surface_rows() -> ApiResponse:
    """All control surface rows — declared intent reconciled with observed reality."""
    try:
        return ApiResponse(data=_build_rows())
    except Exception as e:
        logger.exception("control-surface/rows failed")
        return ApiResponse(data=None, error=str(e))


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
        return ApiResponse(data=None, error=str(e))
