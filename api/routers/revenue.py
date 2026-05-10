"""API router for the revenue pipeline."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/revenue", tags=["revenue"])


def _get_spine():  # type: ignore[return]
    from dharma_swarm.revenue.spine import EconomicSpine as RevenueSpine
    return RevenueSpine()


def _get_engine():  # type: ignore[return]
    try:
        from dharma_swarm.organism import get_organism
        org = get_organism()
        if org and getattr(org, "economic_engine", None):
            return org.economic_engine
    except Exception:
        pass
    try:
        from dharma_swarm.economic_engine import EconomicEngine
        return EconomicEngine()
    except Exception:
        return None


@router.get("/snapshot")
async def pipeline_snapshot() -> dict[str, Any]:
    """Return a snapshot of the revenue pipeline."""
    spine = _get_spine()
    return spine.snapshot().model_dump()


@router.get("/targets")
async def list_targets() -> dict[str, Any]:
    """List all revenue targets."""
    spine = _get_spine()
    targets = list(spine._targets.values())
    return {
        "count": len(targets),
        "targets": [t.model_dump() for t in targets],
    }


@router.get("/outreach")
async def list_outreach() -> dict[str, Any]:
    """List all outreach drafts."""
    spine = _get_spine()
    drafts = list(spine._outreach.values())
    return {
        "count": len(drafts),
        "drafts": [d.model_dump() for d in drafts],
    }


@router.get("/engagements")
async def list_engagements() -> dict[str, Any]:
    """List all engagements."""
    spine = _get_spine()
    engagements = list(spine._engagements.values())
    return {
        "count": len(engagements),
        "engagements": [e.model_dump() for e in engagements],
    }


@router.post("/approve-outreach/{draft_id}")
async def approve_outreach(
    draft_id: str, approver: str = "",
) -> dict[str, Any]:
    """Approve an outreach draft for sending (requires human approver name)."""
    if not approver:
        return {"error": "approver name is required — no autonomous spam"}
    spine = _get_spine()
    result = spine.approve_outreach(draft_id, approved_by=approver)
    if result:
        return {"approved": True, "draft_id": draft_id, "approved_by": approver}
    return {"approved": False, "error": f"Draft {draft_id} not found"}


@router.post("/record-payment/{engagement_id}")
async def record_payment(
    engagement_id: str, amount_usd: float = 0.0,
) -> dict[str, Any]:
    """Record a payment on an engagement, bridging to EconomicEngine."""
    spine = _get_spine()
    engine = _get_engine()
    result = spine.record_payment(engagement_id, amount_usd, economic_engine=engine)
    return {"recorded": result, "engagement_id": engagement_id, "amount_usd": amount_usd}


@router.post("/reinvest/{engagement_id}")
async def reinvest(
    engagement_id: str,
    amount_usd: float = 0.0,
    target_category: str = "training",
    provider: str = "",
) -> dict[str, Any]:
    """Reinvest revenue from an engagement into compute, bridging to EconomicEngine."""
    spine = _get_spine()
    engine = _get_engine()
    record = spine.reinvest(
        engagement_id, amount_usd,
        target_category=target_category,
        provider=provider,
        economic_engine=engine,
    )
    return record.model_dump()
