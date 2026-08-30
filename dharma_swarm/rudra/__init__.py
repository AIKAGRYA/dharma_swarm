"""RUDRA v0: the missing join in the evolution lane.

frozen goal → persistent action → exact workspace → fresh oracle → recovery

Normative source: docs/plans/rudra_v0/RUDRA_BUILD_SPEC.md. GoalGate owns
terminal truth; the executor produces candidate mutations and observations
only. This package performs no network I/O: v0 ships the provider interface
plus a deterministic stub executor, and the live app-server binding is a
later, separately gated step.
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
