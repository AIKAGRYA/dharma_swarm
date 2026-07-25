"""Operator brief rendering for Sarathi."""

from __future__ import annotations

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


__all__ = ["build_operator_brief"]
