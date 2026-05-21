"""Goodworks DGM API router.

The router exposes the Goodworks-first goal loop as an agent-native surface:
status, goal creation, and receipts. It intentionally exposes only dry-run and
shadow execution; live mutation remains behind the existing DGM gates.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Query

from api.models import ApiResponse
from dharma_swarm.goodworks_dgm import (
    GoalDomain,
    GoalSpec,
    GoodworksDGMService,
    MutationMode,
)

router = APIRouter(prefix="/api/goodworks-dgm", tags=["goodworks-dgm"])


class GoalCreateRequest(BaseModel):
    title: str = Field(..., min_length=3)
    objective: str = Field(..., min_length=3)
    domain: GoalDomain = GoalDomain.GOODWORKS_MRV
    success_metric: str = "increase_verified_restorative_flow_without_invalidating_ledger"
    mutation_mode: MutationMode = MutationMode.DRY_RUN
    budget_iterations: int = Field(default=1, ge=1, le=5)
    operator_note: str = ""
    run_now: bool = True


@router.get("/status")
async def goodworks_dgm_status(limit: int = Query(default=10, ge=1, le=100)) -> ApiResponse:
    service = GoodworksDGMService()
    return ApiResponse(data=service.status(limit=limit))


@router.get("/receipts")
async def goodworks_dgm_receipts(
    limit: int = Query(default=20, ge=1, le=200),
) -> ApiResponse:
    service = GoodworksDGMService()
    return ApiResponse(data=service.recent_receipts(limit=limit))


@router.post("/goal")
async def create_goodworks_dgm_goal(request: GoalCreateRequest) -> ApiResponse:
    service = GoodworksDGMService()
    spec = GoalSpec(
        title=request.title,
        objective=request.objective,
        domain=request.domain,
        success_metric=request.success_metric,
        mutation_mode=request.mutation_mode,
        budget_iterations=request.budget_iterations,
        operator_note=request.operator_note,
    )
    run = await service.create_goal(spec, run_now=request.run_now)
    return ApiResponse(data=run.model_dump(mode="json"))
