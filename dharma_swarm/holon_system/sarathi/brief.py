"""Operator brief rendering for Sarathi.

Two surfaces coexist here:

- ``build_operator_brief``: honest markdown brief over the read-only pulse
  projection (asserts "not alive" until proof exists).
- ``generate_brief``: operator-facing daily brief for phone/Telegram delivery.
  Receipts only, one highest-leverage lane, mobile-first plain text, honest
  under-reporting ("fleet idle" when nothing happened).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .pulse import sarathi_pulse


def build_operator_brief(pulse: dict[str, object] | None = None) -> str:
    pulse = pulse or sarathi_pulse()
    lines = [
        "# Sarathi Operator Brief",
        "",
        "Status: not alive; no unattended wake-loop proof is claimed.",
        f"Schema: {pulse.get('schema_version')}",
        "",
        "## Roster",
    ]
    for row in pulse.get("roster", []) or []:
        if isinstance(row, dict):
            lines.append(f"- {row.get('name')}: registered={row.get('registered')} kill_requested={row.get('kill_requested')}")
    return "\n".join(lines) + "\n"


def _format_roster_line(seats: list[dict[str, Any]]) -> str:
    """Compact one-line-per-seat roster for the brief."""
    lines = []
    for seat in seats:
        name = seat["name"].replace("_", " ").replace("-", " ")
        status = seat["status"]
        alive = "●" if seat.get("is_alive") else "○"
        lines.append(f"  {alive} {name:25s} {status}")
    return "\n".join(lines)


def _pick_top_lane(roster: dict[str, Any], gate: dict[str, Any]) -> str:
    """Pick the ONE highest-leverage thing to surface.

    This is deliberately simple: it prioritizes security/blocker signals,
    then dead seats, then idle. It does NOT invent urgency.
    """
    dead = roster.get("dead_seats", [])
    alive = roster.get("alive_seats", [])
    gate_class = gate.get("action_class", "unknown")

    # If a critical seat is dead, surface that
    critical_seats = {"fable_composer", "codex_composer", "hermes-m5"}
    dead_critical = [s for s in dead if s in critical_seats]
    if dead_critical:
        return f"⚠️ Critical seat offline: {', '.join(dead_critical)}"

    # If the gate blocked something, surface that
    if gate_class not in ("reversible_safe",):
        return f"🔐 Gate held: planned action classified as {gate_class}"

    # If more than 2 seats are dead
    if len(dead) > 2:
        return f"📋 {len(dead)} seats need attention: {', '.join(dead)}"

    # Default: fleet is alive, nothing urgent
    return f"✅ Fleet stable: {len(alive)}/{roster.get('total_seats', 0)} seats alive"


def generate_brief(
    *,
    roster: dict[str, Any],
    gate_result: Any = None,
) -> str:
    """Generate a plain-text operator brief.

    Args:
        roster: The fleet_summary() dict from roster.py
        gate_result: The GatewayResult from gateway.evaluate() (optional)

    Returns:
        A plain-text brief string suitable for Telegram delivery.
    """
    now = datetime.now(timezone.utc)
    ts_str = now.strftime("%Y-%m-%d %H:%M UTC")

    gate_dict = gate_result.gate_decision if gate_result else {}
    top_lane = _pick_top_lane(roster, gate_dict)

    brief = f""" SARATHI PULSE — {ts_str}

TOP LANE: {top_lane}

FLEET:
{_format_roster_line(roster.get('seats', []))}

GATE: {gate_dict.get('action_class', 'n/a')} — {gate_dict.get('risk', 'n/a')}
ACTION: {gate_dict.get('action', 'read fleet status')}
"""
    return brief.strip()


def main() -> None:
    """CLI entry: generate and print a brief."""
    from .gateway import evaluate
    from .roster import fleet_summary

    roster = fleet_summary()
    gate = evaluate("read fleet status", operator_reachable=False)
    print(generate_brief(roster=roster, gate_result=gate))


if __name__ == "__main__":
    main()


__all__ = ["build_operator_brief", "generate_brief"]
