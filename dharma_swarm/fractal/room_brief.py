"""Room sections for the Operator Brief.

Generates markdown sections showing active rooms, their budgets,
agents, recent work, and venture cell health. Designed to be appended
to the existing Operator Brief output.
"""

from __future__ import annotations

from typing import Any

from dharma_swarm.fractal.fractal_room import (
    FractalRoom,
    RoomKind,
    RoomRegistry,
    RoomStatus,
    VentureCellV1,
    evaluate_kill_conditions,
    evaluate_spinout_conditions,
)


def render_room_section(
    registry: RoomRegistry,
    *,
    kpis: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Render a markdown section summarizing all active rooms.

    Args:
        registry: The room registry to read from.
        kpis: Optional mapping of room_id → KPI dict for health evaluation.

    Returns:
        Markdown string for embedding in the Operator Brief.
        Returns empty string if no rooms exist.
    """
    active = registry.active_rooms()
    if not active:
        return ""

    kpis = kpis or {}
    lines: list[str] = [
        "## Fractal Room Status\n",
        f"Active rooms: **{len(active)}** | "
        f"Venture cells: **{sum(1 for r in active if r.kind == RoomKind.VENTURE_CELL)}**\n",
    ]

    for room in active:
        lines.append(_render_single_room(room, registry, kpis.get(room.id, {})))

    archived = [
        r for r in registry.all_rooms()
        if r.status == RoomStatus.ARCHIVED
    ]
    if archived:
        lines.append(f"\n_Archived rooms: {len(archived)}_\n")

    return "\n".join(lines)


def _render_single_room(
    room: FractalRoom,
    registry: RoomRegistry,
    kpis: dict[str, Any],
) -> str:
    """Render a single room's brief block."""
    brief = registry.room_brief(room.id)
    wp = brief["work_packets"]
    budget_pct = _budget_pct(room)

    lines: list[str] = [
        f"\n### {room.id} ({room.kind.value})",
        f"**Purpose:** {room.purpose}",
        f"**Status:** {room.status.value} | "
        f"**Agents:** {brief['roster']['count']} | "
        f"**Budget:** {room.remaining_budget():,} / {room.budget_tokens:,} tokens ({budget_pct})",
        f"**Work packets:** {wp['completed']} completed, "
        f"{wp['pending']} pending, {wp['total']} total",
    ]

    if room.forbidden_work:
        lines.append(f"**Forbidden:** {', '.join(room.forbidden_work[:5])}")

    if isinstance(room, VentureCellV1):
        lines.append(_render_vc_health(room, kpis))

    children = registry.children_of(room.id)
    if children:
        child_ids = [c.id for c in children]
        lines.append(f"**Children:** {', '.join(child_ids)}")

    return "\n".join(lines) + "\n"


def _render_vc_health(vc: VentureCellV1, kpis: dict[str, Any]) -> str:
    """Render venture cell health indicators."""
    parts: list[str] = [
        f"**Customer:** {vc.customer_or_beneficiary}",
        f"**Revenue target:** {vc.revenue_target:,} | "
        f"**Autonomy stage:** {vc.autonomy_stage}/5",
    ]

    if kpis:
        kill = evaluate_kill_conditions(vc.kill_conditions, kpis)
        spinout = evaluate_spinout_conditions(vc.spinout_conditions, kpis)
        health = "SPINOUT READY" if spinout else ("KILL TRIGGERED" if kill else "HEALTHY")
        parts.append(f"**Health:** {health}")

    if vc.jagat_kalyan_constraint:
        parts.append(f"**Welfare constraint:** {vc.jagat_kalyan_constraint}")

    return "\n".join(parts)


def _budget_pct(room: FractalRoom) -> str:
    if room.budget_tokens == 0:
        return "N/A"
    remaining = room.remaining_budget()
    pct = int(100 * remaining / room.budget_tokens)
    return f"{pct}%"


def render_room_summary_line(registry: RoomRegistry) -> str:
    """One-line summary for the brief header."""
    active = registry.active_rooms()
    if not active:
        return ""
    vcs = sum(1 for r in active if r.kind == RoomKind.VENTURE_CELL)
    total_agents = sum(len(r.agents) for r in active)
    return (
        f"Rooms: {len(active)} active ({vcs} venture cells), "
        f"{total_agents} agents deployed"
    )
