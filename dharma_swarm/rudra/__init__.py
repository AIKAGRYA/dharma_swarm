"""RUDRA v0: the missing join in the evolution lane.

frozen goal → persistent action → exact workspace → fresh oracle → recovery

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md. GoalGate owns
terminal truth; the executor produces candidate mutations and observations
only. The package performs no network I/O of its own: ``codex_driver`` owns
the narrow protocol framing, ``live_driver`` binds a real app-server process
through ProcessOwner, and the live binding activates only via the explicit
env + contract pin in ``terminal_commands.rudra``.
"""

from dharma_swarm.rudra.contracts import (
    AdmissionError,
    AdmissionReject,
    ReproducedCompletion,
    RudraMissionContract,
    Terminal,
    parse_mission,
)
from dharma_swarm.rudra.goal_gate import GoalGate
from dharma_swarm.rudra.runner import MissionRunner

__all__ = [
    "AdmissionError",
    "AdmissionReject",
    "GoalGate",
    "MissionRunner",
    "ReproducedCompletion",
    "RudraMissionContract",
    "Terminal",
    "parse_mission",
]
