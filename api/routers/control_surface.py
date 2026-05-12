"""Read-only operator control-surface endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from api.models import ApiResponse
from dharma_swarm.operator_core.control_surface import (
    ControlSurfaceQuery,
    build_control_surface_page,
    build_control_surface_rows,
    build_control_surface_summary,
    find_control_surface_row,
    find_evidence_ref,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control-surface", tags=["control-surface"])


@router.get("/summary")
async def control_surface_summary() -> ApiResponse:
    """Return aggregate counts for the read-only control surface."""
    try:
        rows = build_control_surface_rows()
        return ApiResponse(data=build_control_surface_summary(rows))
    except Exception as exc:
        logger.exception("control-surface summary failed")
        return ApiResponse(status="error", error=str(exc), data=None)


@router.get("/rows")
async def control_surface_rows(
    kind: str | None = Query(None),
    priority: str | None = Query(None),
    coherence_state: str | None = Query(None),
    human_decision_required: bool | None = Query(None),
    stale: bool | None = Query(None),
    source: str | None = Query(None),
    limit: int = Query(250, ge=1, le=1000),
    cursor: str | None = Query(None),
) -> ApiResponse:
    """Return paged read-only control-surface rows."""
    try:
        page = build_control_surface_page(
            query=ControlSurfaceQuery(
                kind=kind,
                priority=priority,
                coherence_state=coherence_state,
                human_decision_required=human_decision_required,
                stale=stale,
                source=source,
                limit=limit,
                cursor=cursor,
            )
        )
        return ApiResponse(data=page.to_dict())
    except Exception as exc:
        logger.exception("control-surface rows failed")
        return ApiResponse(status="error", error=str(exc), data=None)


@router.get("/rows/{row_id:path}")
async def control_surface_row(row_id: str) -> ApiResponse:
    """Return one read-only control-surface row by ID."""
    try:
        row = find_control_surface_row(row_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"row '{row_id}' not found")
        return ApiResponse(data=row.to_dict())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("control-surface row lookup failed")
        return ApiResponse(status="error", error=str(exc), data=None)


@router.get("/evidence/{evidence_id:path}")
async def control_surface_evidence(evidence_id: str) -> ApiResponse:
    """Return a typed evidence pointer by stable evidence ID."""
    try:
        evidence = find_evidence_ref(evidence_id)
        if evidence is None:
            raise HTTPException(status_code=404, detail=f"evidence '{evidence_id}' not found")
        return ApiResponse(data=evidence.to_dict())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("control-surface evidence lookup failed")
        return ApiResponse(status="error", error=str(exc), data=None)
