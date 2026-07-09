"""Sarathi apex holon source package.

The apex continuity holon — chief-of-staff seat that holds the whole
fleet/life map, runs ONLY reversible-safe loops unattended, and surfaces
one highest-leverage lane to the operator.

These modules are honest source surfaces. They do not claim unattended
liveness; runtime-home wrappers should import from here.

Modules:
    roster  — load + status of sub-holons and Hermes organ (read-only)
    gateway — read-only snapshot + reversibility gate evaluation/execution
    pulse   — read-only projection + one governed tick: read → gate → brief → receipt
    brief   — operator-facing brief generation
    scoreboard — Sarathi vs Hermes organ parity table

Safety invariant: the gate takes NO model input by construction. Whether
an action may run unattended is decided by CODE (reversibility_gate.py),
never by the resolved model's judgment.

Status: gates 5-8 source modules built. Gate 9 (overnight durability)
remains OPEN — wake_loop_active stays False until proven.
"""

from .brief import build_operator_brief, generate_brief
from .gateway import evaluate, gate_and_execute, gateway_snapshot
from .pulse import run_pulse, sarathi_pulse
from .roster import fleet_summary, load_fleet_roster, load_roster, load_seat
from .scoreboard import organ_scoreboard

IMPLEMENTED = True  # gates 5-8 built; gate 9 (durability) still open

__all__ = [
    "build_operator_brief",
    "evaluate",
    "fleet_summary",
    "gate_and_execute",
    "gateway_snapshot",
    "generate_brief",
    "load_fleet_roster",
    "load_roster",
    "load_seat",
    "organ_scoreboard",
    "run_pulse",
    "sarathi_pulse",
]
