"""Sarathi gateway source surface.

This is a read-only source package entrypoint. Starting daemons or setting
``wake_loop_active`` requires a separate proof-backed runtime action.
"""

from __future__ import annotations

from .brief import build_operator_brief
from .pulse import sarathi_pulse
from .roster import load_roster
from .scoreboard import organ_scoreboard


def gateway_snapshot(roster_path: str | None = None) -> dict[str, object]:
    roster = load_roster(roster_path)
    pulse = sarathi_pulse(roster)
    return {
        "schema_version": "dharma.sarathi.gateway_snapshot.v1",
        "wake_loop_active": False,
        "alive_claim": False,
        "pulse": pulse,
        "brief": build_operator_brief(pulse),
        "scoreboard": list(organ_scoreboard()),
    }


__all__ = ["gateway_snapshot"]
