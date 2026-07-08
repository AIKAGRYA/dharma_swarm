"""Sarathi apex holon source package.

The apex continuity holon — chief-of-staff seat that holds the whole
fleet/life map, runs ONLY reversible-safe loops unattended, and surfaces
one highest-leverage lane to the operator.

Modules:
    roster  — load + status of sub-holons and Hermes organ (read-only)
    gateway — reversibility gate evaluation + optional execution
    pulse   — one governed tick: read → gate → brief → receipt
    brief   — operator-facing daily brief generation

Safety invariant: the gate takes NO model input by construction. Whether
an action may run unattended is decided by CODE (reversibility_gate.py),
never by the resolved model's judgment.

Status: gates 5-8 source modules built. Gate 9 (overnight durability)
remains OPEN — wake_loop_active stays False until proven.
"""

from dharma_swarm.holon_system.sarathi.brief import generate_brief
from dharma_swarm.holon_system.sarathi.gateway import evaluate, gate_and_execute
from dharma_swarm.holon_system.sarathi.pulse import run_pulse
from dharma_swarm.holon_system.sarathi.roster import fleet_summary, load_roster, load_seat

IMPLEMENTED = True  # gates 5-8 built; gate 9 (durability) still open

__all__ = [
    "evaluate",
    "fleet_summary",
    "gate_and_execute",
    "generate_brief",
    "load_roster",
    "load_seat",
    "run_pulse",
]
