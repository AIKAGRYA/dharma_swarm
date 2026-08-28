"""telos-gatekeeper: dharmic constraint enforcement for autonomous AI agents.

Thin distribution shim over the TelosGatekeeper from DHARMA SWARM: the core
dharmic gates, reflective rerouting, and GateCheckResult infrastructure,
re-exported without the rest of the swarm package.

Full implementation: dharma_swarm/telos_gates.py in the parent repo.

NOTE: there is no bundled standalone implementation. This package requires
``dharma_swarm`` to be importable; without it, importing this package raises
ImportError.
"""
from __future__ import annotations

from dharma_swarm.telos_gates import (
    TelosGatekeeper,
    GateProposal,
    GateCheckResult,
    GateRegistry,
    ReflectiveGateOutcome,
    check_action,
    check_with_reflective_reroute,
)

__all__ = [
    "TelosGatekeeper",
    "GateProposal",
    "GateCheckResult",
    "GateRegistry",
    "ReflectiveGateOutcome",
    "check_action",
    "check_with_reflective_reroute",
]

__version__ = "0.1.0"
