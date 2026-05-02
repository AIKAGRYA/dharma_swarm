"""Telos gate endpoints — dharmic safety gate system.

Exposes gate definitions, check capability, proposals, and witness logs.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel

from api.models import ApiResponse
from dharma_swarm.runtime_config import dharma_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gates", tags=["gates"])

_WITNESS_DIR = dharma_path("witness")


def _get_gatekeeper():
    from api.main import get_gatekeeper
    return get_gatekeeper()


class GateCheckRequest(BaseModel):
    action: str
    content: str = ""


@router.get("/definitions")
async def gate_definitions() -> ApiResponse:
    """All gate names, tiers, and descriptions."""
    try:
        gk = _get_gatekeeper()
        gates = []
        gate_map = getattr(gk, "GATES", {})
        for name, tier in gate_map.items():
            tier_str = tier.value if hasattr(tier, "value") else str(tier)
            gates.append({
                "name": name,
                "tier": tier_str.split(".")[-1] if "." in tier_str else tier_str,
                "description": "",
            })
        if hasattr(gk, "_registry") and gk._registry:
            for g in gk._registry.load_approved():
                gates.append({
                    "name": getattr(g, "name", ""),
                    "tier": getattr(g, "tier", "C"),
                    "description": getattr(g, "justification", ""),
                })
        return ApiResponse(data=gates)
    except Exception as e:
        logger.warning("Gate definitions failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.post("/check")
async def gate_check(req: GateCheckRequest) -> ApiResponse:
    """Run a gate check on an action (operator test)."""
    try:
        gk = _get_gatekeeper()
        result = gk.check(action=req.action, content=req.content)
        return ApiResponse(data={
            "decision": getattr(result, "decision", "ALLOW"),
            "reason": getattr(result, "reason", ""),
            "per_gate": getattr(result, "per_gate_results", {}),
        })
    except Exception as e:
        logger.warning("Gate check failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/proposals")
async def gate_proposals(
    status: str | None = Query(None, description="Filter by status: proposed, approved, rejected"),
) -> ApiResponse:
    """Custom gate proposals (variety expansion protocol)."""
    try:
        gk = _get_gatekeeper()
        if hasattr(gk, "_registry") and gk._registry:
            proposals = gk._registry.list_proposals(status=status)
            return ApiResponse(data=[
                {
                    "name": getattr(p, "name", ""),
                    "tier": getattr(p, "tier", "C"),
                    "justification": getattr(p, "justification", ""),
                    "status": getattr(p, "status", "proposed"),
                    "trigger_patterns": getattr(p, "trigger_patterns", []),
                }
                for p in proposals
            ])
        return ApiResponse(data=[])
    except Exception as e:
        logger.warning("Gate proposals failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/witness/recent")
async def recent_witness_logs(
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse:
    """Recent witness audit logs from ~/.dharma/witness/."""
    try:
        if not _WITNESS_DIR.exists():
            return ApiResponse(data=[])

        entries: list[dict] = []
        files = sorted(_WITNESS_DIR.glob("witness_*.jsonl"), reverse=True)
        for f in files[:7]:
            try:
                for line in reversed(f.read_text(encoding="utf-8").strip().splitlines()):
                    if len(entries) >= limit:
                        break
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            except OSError:
                continue
            if len(entries) >= limit:
                break

        return ApiResponse(data=entries[:limit])
    except Exception as e:
        logger.warning("Witness logs failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")
