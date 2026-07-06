"""Facade: holon orchestration wiring.

Canonical owner: dharma_swarm/holon_orchestrate.py, which explicitly does NOT
create a second orchestrator/task store/model router/receipt spine.
"""

from __future__ import annotations

from dharma_swarm.holon_orchestrate import (
    HolonOrchestrationConfig,
    HolonOrchestrationError,
    run_holon_orchestration,
)

__all__ = [
    "HolonOrchestrationConfig",
    "HolonOrchestrationError",
    "run_holon_orchestration",
]
