"""Facade: governed holon wake loop.

Canonical owner: dharma_swarm/holon_runtime.py. holon_wake_cycle now accepts an
optional `planned_action` that routes through the deterministic reversibility gate
before any work runs (see authority/reversibility.py).
"""

from __future__ import annotations

from dharma_swarm.holon_runtime import AgentRunner, holon_wake_cycle, run_holon_loop

__all__ = ["AgentRunner", "holon_wake_cycle", "run_holon_loop"]
