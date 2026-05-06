"""Hypernode dashboard endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from api.models import ApiResponse
from dharma_swarm.hypernode_seed import ensure_empty_quadrant_hypernode

router = APIRouter(prefix="/api", tags=["hypernodes"])


def _get_registry():
    from dharma_swarm.ontology_runtime import get_shared_registry

    return get_shared_registry()


@router.get("/hypernodes/empty-quadrant")
async def empty_quadrant_hypernode() -> ApiResponse:
    registry = _get_registry()
    seeded = ensure_empty_quadrant_hypernode(registry, created_by="api.hypernodes")
    if seeded.errors:
        return ApiResponse(status="error", error="; ".join(seeded.errors))
    return ApiResponse(data=seeded.payload.model_dump(mode="json"))
