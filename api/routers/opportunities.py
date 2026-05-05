"""API router for the opportunity / revenue loop."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from dharma_swarm.opportunity_dispatcher import OpportunityDispatcher
from dharma_swarm.opportunity_refill import OpportunityRefill, OpportunityRow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


def _get_dispatcher() -> OpportunityDispatcher:
    return OpportunityDispatcher()


def _get_refill() -> OpportunityRefill:
    return OpportunityRefill(dispatcher=_get_dispatcher())


@router.get("/stages")
async def list_stages() -> dict[str, Any]:
    """List the canonical opportunity stages."""
    from dharma_swarm.opportunity_dispatcher import OPPORTUNITY_STAGES
    return {"stages": list(OPPORTUNITY_STAGES)}


@router.post("/refill")
async def refill_opportunity(row: OpportunityRow) -> dict[str, Any]:
    """Refill a single opportunity through all stages."""
    refill = _get_refill()
    result = refill.refill(row)
    return result.model_dump()


@router.post("/dispatch")
async def dispatch_opportunity(opportunity: dict[str, Any]) -> dict[str, Any]:
    """Dispatch an opportunity through the runtime."""
    dispatcher = _get_dispatcher()
    results = dispatcher.dispatch_opportunity_sync(opportunity)
    return {"results": [r.to_dict() for r in results]}
