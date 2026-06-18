"""Model-pool API routes backed by the canonical status projection."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dharma_swarm import model_pool
from dharma_swarm.model_status import (
    save_profile,
    top_floor_models_for_dashboard,
    verify_floor_models,
)

router = APIRouter(prefix="/api/pool", tags=["model-pool"])


class ModelProfilePatch(BaseModel):
    custom_label: str | None = None
    short_name: str | None = None


@router.get("/top10/status")
async def top10_status() -> list[dict]:
    """Return floor model status for the dashboard's historical top10 path."""
    return top_floor_models_for_dashboard()


@router.post("/top10/verify")
async def verify_top10() -> dict:
    """Do not make implicit live calls; report whether live verification ran."""
    return verify_floor_models()


@router.patch("/models/{model_id}/profile")
async def patch_model_profile(model_id: str, patch: ModelProfilePatch) -> dict:
    if model_pool.get_entry(model_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown model id: {model_id}")
    return save_profile(
        model_id,
        custom_label=patch.custom_label,
        short_name=patch.short_name,
    )
