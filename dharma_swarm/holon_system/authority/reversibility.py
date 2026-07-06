"""Facade: code-deterministic reversibility gate (the apex safety ceiling).

Canonical owner: dharma_swarm/operator_core/reversibility_gate.py. The gate takes
NO model input by construction; approval is a function of the action string +
operator reachability. Only REVERSIBLE_SAFE actions may run unattended.
"""

from __future__ import annotations

from dharma_swarm.operator_core.reversibility_gate import (
    ActionClass,
    GateDecision,
    ReversibilityGate,
    classify_action,
)

__all__ = ["ActionClass", "GateDecision", "ReversibilityGate", "classify_action"]
