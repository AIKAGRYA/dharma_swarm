"""Manifest Health API — declared-vs-observed comparison.

GET /api/manifest/health   → full health report (all sections)
GET /api/manifest/summary  → counts only (live / degraded / broken / stub)
GET /api/manifest/entity/{entity_id} → single entity detail
GET /api/manifest/autocatalytic → ten-node metabolic topology + latest proof
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from api.models import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/manifest", tags=["manifest"])


def _get_report() -> dict[str, Any]:
    from dharma_swarm.manifest_health import build_health_report

    return build_health_report()


@router.get("/health")
async def manifest_health() -> ApiResponse:
    """Full manifest health report with all sections and checks."""
    try:
        report = _get_report()
        if "error" in report and report["error"]:
            return ApiResponse(data=report, error=report["error"])
        return ApiResponse(data=report)
    except Exception as e:
        logger.exception("manifest/health failed")
        return ApiResponse(data=None, error=str(e))


@router.get("/summary")
async def manifest_summary() -> ApiResponse:
    """Lightweight summary: counts by observed status."""
    try:
        report = _get_report()
        return ApiResponse(
            data={
                "manifest_version": report.get("manifest_version"),
                "last_updated": report.get("last_updated"),
                "summary": report.get("summary", {}),
            }
        )
    except Exception as e:
        logger.exception("manifest/summary failed")
        return ApiResponse(data=None, error=str(e))


@router.get("/autocatalytic")
async def manifest_autocatalytic() -> ApiResponse:
    """Ten-node portfolio read model and locally receipt-consistent cycle.

    The endpoint is read-only. A local mutable store is not authenticated
    execution provenance; the witness remains capped at ``local_rehearsal``
    and cannot claim external effects.
    """
    try:
        from dharma_swarm.autocatalytic_portfolio import (
            build_autocatalytic_snapshot,
        )

        return ApiResponse(data=build_autocatalytic_snapshot())
    except Exception as e:
        logger.exception("manifest/autocatalytic failed")
        return ApiResponse(data=None, error=str(e))


@router.get("/entity/{entity_id}")
async def manifest_entity(entity_id: str) -> ApiResponse:
    """Single entity health detail by ID."""
    try:
        report = _get_report()
        for section in report.get("sections", []):
            for entity in section.get("entities", []):
                if entity["id"] == entity_id:
                    return ApiResponse(data=entity)
        raise HTTPException(
            status_code=404, detail=f"entity '{entity_id}' not found in manifest"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("manifest/entity failed")
        return ApiResponse(data=None, error=str(e))
