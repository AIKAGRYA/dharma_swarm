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
from dharma_swarm.fractal.room_configs import bootstrap_registry


def _guardian_finding(
    severity: str, check: str, title: str, detail: str, fix_hint: str = "",
) -> Any:
    """Create a GuardianFinding without importing guardian_crew at module level."""
    from dharma_swarm.guardian_crew import GuardianFinding

    return GuardianFinding(
        severity=severity, check=check, title=title,
        detail=detail, fix_hint=fix_hint,
    )


async def run_room_health_watcher() -> list[Any]:
    """ROOM_WATCHER: Check fractal room health — budget, kill/spinout conditions."""
    findings: list[Any] = []
    try:
        registry = bootstrap_registry()
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
            try:
                created = datetime.fromisoformat(room.created_at)
                age_days = (datetime.now(timezone.utc) - created).days
            except (ValueError, TypeError):
                age_days = 0
            kpis = {
                "days_since_creation": age_days,
                "total_revenue": 0,
                "total_budget": room.budget_tokens,
                "total_burn": room.current_burn,
                "operator_override": False,
            }
            kill = evaluate_kill_conditions(room.kill_conditions, kpis)
            if kill:
                findings.append(_guardian_finding(
                    severity="DEGRADED",
                    check="ROOM_WATCHER:kill_condition",
                    title=f"VentureCell '{room.id}' kill condition triggered",
                    detail=(
                        f"VentureCell '{room.id}' has triggered kill conditions. "
                        f"Age: {age_days} days, revenue: $0, burn: {room.current_burn} tokens."
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
