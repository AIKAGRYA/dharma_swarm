"""Fractal room health evaluation for Guardian Crew integration.

Checks budget depletion, kill conditions, and spinout readiness
for all active rooms. Returns GuardianFinding objects compatible
with the existing guardian_crew synthesize_report pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dharma_swarm.fractal.fractal_room import (
    VentureCellV1,
    evaluate_kill_conditions,
)


def _guardian_finding(
    severity: str, check: str, title: str, detail: str, fix_hint: str = "",
) -> Any:
    """Create a GuardianFinding without importing guardian_crew at module level."""
    from dharma_swarm.guardian_crew import GuardianFinding

    return GuardianFinding(
        severity=severity, check=check, title=title,
        detail=detail, fix_hint=fix_hint,
    )


def room_runtime_kpis(
    room: VentureCellV1,
    *,
    now: datetime | None = None,
    revenue_usd: float = 0.0,
    burn_usd: float = 0.0,
    paying_customers: int = 0,
    operator_kill: bool = False,
    operator_approved_graduation: bool = False,
) -> dict[str, Any]:
    """Build KPI keys that match fractal_room evaluator contracts."""
    now = now or datetime.now(timezone.utc)
    try:
        created = datetime.fromisoformat(room.created_at)
        age_days = (now - created).days
    except (ValueError, TypeError):
        age_days = 0

    return {
        "days_active": age_days,
        "revenue_usd": revenue_usd,
        "burn_usd": burn_usd,
        "budget_ratio": room.current_burn / max(room.budget_tokens, 1),
        "operator_kill": operator_kill,
        "monthly_revenue_gt_burn_months": 0,
        "paying_customers": paying_customers,
        "operator_approved_graduation": operator_approved_graduation,
        "autonomy_stage": room.autonomy_stage,
        "agent_count": len(room.agents),
        "welfare_tons": room.welfare_tons_produced,
    }


async def run_room_health_watcher(registry: Any | None = None) -> list[Any]:
    """ROOM_WATCHER: Check live fractal room health when a registry is supplied."""
    findings: list[Any] = []
    if registry is None:
        findings.append(_guardian_finding(
            severity="WARNING",
            check="ROOM_WATCHER:not_configured",
            title="Room health watcher has no live room registry",
            detail=(
                "Guardian room health is disabled because no runtime RoomRegistry "
                "was supplied. Avoiding static bootstrap prevents decorative health."
            ),
            fix_hint="Run live orchestration with DHARMA_FRACTAL_ROOMS=1 or pass a live registry.",
        ))
        return findings

    try:
        active = registry.active_rooms()
    except Exception as exc:
        findings.append(_guardian_finding(
            severity="WARNING",
            check="ROOM_WATCHER:error",
            title="Room health check failed",
            detail=f"Room health watcher encountered an error: {exc}",
        ))
        return findings

    for room in active:
        remaining = room.remaining_budget()
        if remaining <= 0:
            findings.append(_guardian_finding(
                severity="BLOCKER",
                check="ROOM_WATCHER:budget_depleted",
                title=f"Room '{room.id}' budget fully depleted",
                detail=(
                    f"Room '{room.id}' ({room.kind.value}) has exhausted its budget: "
                    f"0/{room.budget_tokens:,} tokens remaining."
                ),
                fix_hint="Allocate additional budget or archive the room.",
            ))
        elif remaining < room.budget_tokens * 0.2:
            findings.append(_guardian_finding(
                severity="WARNING",
                check="ROOM_WATCHER:budget_low",
                title=f"Room '{room.id}' budget below 20%",
                detail=(
                    f"Room '{room.id}' ({room.kind.value}) budget is low: "
                    f"{remaining:,}/{room.budget_tokens:,} tokens remaining "
                    f"({int(100 * remaining / room.budget_tokens)}%)."
                ),
                fix_hint="Monitor burn rate and consider budget allocation.",
            ))
        if isinstance(room, VentureCellV1):
            kpis = room_runtime_kpis(room)
            kill = evaluate_kill_conditions(room.kill_conditions, kpis)
            if kill:
                findings.append(_guardian_finding(
                    severity="DEGRADED",
                    check="ROOM_WATCHER:kill_condition",
                    title=f"VentureCell '{room.id}' kill condition triggered",
                    detail=(
                        f"VentureCell '{room.id}' has triggered kill conditions. "
                        f"Age: {kpis['days_active']} days, revenue: ${kpis['revenue_usd']}, "
                        f"budget ratio: {kpis['budget_ratio']:.2f}."
                    ),
                    fix_hint="Review kill conditions and decide whether to archive or adjust.",
                ))
    if not findings:
        findings.append(_guardian_finding(
            severity="OK",
            check="ROOM_WATCHER:all_healthy",
            title=f"All {len(active)} fractal rooms healthy",
            detail=f"All {len(active)} active rooms have healthy budgets and no triggered kill conditions.",
        ))
    return findings
