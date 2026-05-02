"""VSM (Viable System Model) cybernetic health endpoints.

Exposes Beer's S1-S5 system health, algedonic emergency signals,
gate pressure patterns, agent viability, and variety expansion proposals.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.models import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vsm", tags=["vsm"])


def _get_vsm():
    from api.main import get_vsm
    return get_vsm()


@router.get("/status")
async def vsm_status() -> ApiResponse:
    """Full VSM nervous system status (S1-S5)."""
    try:
        vsm = _get_vsm()
        return ApiResponse(data=vsm.status())
    except Exception as e:
        logger.warning("VSM status failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/algedonic")
async def algedonic_signals() -> ApiResponse:
    """Unacknowledged emergency signals (S5 bypass)."""
    try:
        vsm = _get_vsm()
        signals = vsm.algedonic.active_signals
        return ApiResponse(data=[
            {
                "id": s.id if hasattr(s, "id") else str(i),
                "severity": getattr(s, "severity", "unknown"),
                "source_system": getattr(s, "source_system", ""),
                "title": getattr(s, "title", ""),
                "description": getattr(s, "description", ""),
                "recommended_action": getattr(s, "recommended_action", ""),
                "acknowledged": getattr(s, "acknowledged", False),
                "timestamp": str(getattr(s, "timestamp", "")),
            }
            for i, s in enumerate(signals)
        ])
    except Exception as e:
        logger.warning("Algedonic signals failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.post("/algedonic/{signal_id}/ack")
async def acknowledge_signal(signal_id: str) -> ApiResponse:
    """Acknowledge an algedonic signal (operator action)."""
    try:
        vsm = _get_vsm()
        ok = vsm.algedonic.acknowledge(signal_id)
        return ApiResponse(data={"acknowledged": ok, "signal_id": signal_id})
    except Exception as e:
        logger.warning("Algedonic ack failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/gate-patterns")
async def gate_patterns() -> ApiResponse:
    """Gate pressure statistics — per-gate failure rates and anomaly flags."""
    try:
        vsm = _get_vsm()
        patterns = vsm.gate_patterns.get_all_patterns()
        return ApiResponse(data=[
            {
                "gate_name": getattr(p, "gate_name", ""),
                "failure_count": getattr(p, "failure_count", 0),
                "total_checks": getattr(p, "total_checks", 0),
                "failure_rate": getattr(p, "failure_rate", 0.0),
                "is_anomalous": getattr(p, "is_anomalous", False),
            }
            for p in patterns
        ])
    except Exception as e:
        logger.warning("Gate patterns failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/viability")
async def agent_viability() -> ApiResponse:
    """Agent viability heatmap — S1-S5 scores per agent."""
    try:
        vsm = _get_vsm()
        viabilities = vsm.viability.all_viabilities()
        return ApiResponse(data={
            agent_id: {
                "s1_operations": getattr(v, "s1_operations", 0),
                "s2_coordination": getattr(v, "s2_coordination", 0),
                "s3_control": getattr(v, "s3_control", 0),
                "s4_intelligence": getattr(v, "s4_intelligence", 0),
                "s5_identity": getattr(v, "s5_identity", 0),
                "overall": getattr(v, "overall", 0),
            }
            for agent_id, v in viabilities.items()
        })
    except Exception as e:
        logger.warning("Agent viability failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/viability/fleet")
async def fleet_health() -> ApiResponse:
    """Fleet-wide health score (geometric mean of agent viabilities)."""
    try:
        vsm = _get_vsm()
        return ApiResponse(data={"fleet_health": vsm.viability.fleet_health()})
    except Exception as e:
        logger.warning("Fleet health failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/audit/recent")
async def recent_audits() -> ApiResponse:
    """Recent sporadic audit results (S3* sampling)."""
    try:
        vsm = _get_vsm()
        results = vsm.auditor.recent_results(limit=20)
        return ApiResponse(data=[
            {
                "agent_id": getattr(r, "agent_id", ""),
                "audit_type": getattr(r, "audit_type", ""),
                "passed": getattr(r, "passed", False),
                "findings": getattr(r, "findings", []),
                "timestamp": str(getattr(r, "timestamp", "")),
            }
            for r in results
        ])
    except Exception as e:
        logger.warning("Recent audits failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/variety/pending")
async def variety_pending() -> ApiResponse:
    """Pending gate expansion proposals (variety expansion protocol)."""
    try:
        vsm = _get_vsm()
        pending = vsm.variety.pending
        return ApiResponse(data=[
            {
                "id": getattr(p, "id", ""),
                "gate_name": getattr(p, "proposed_gate", getattr(p, "gate_name", "")),
                "tier": getattr(p, "tier", ""),
                "rationale": getattr(p, "rationale", getattr(p, "justification", "")),
                "status": getattr(p, "status", "proposed"),
            }
            for p in pending
        ])
    except Exception as e:
        logger.warning("Variety pending failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")
