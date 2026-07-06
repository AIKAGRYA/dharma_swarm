"""Facade: LivingAgentKernel durability spine.

Canonical owner: dharma_swarm/operator_core/living_agent_kernel.py. This is the
durable wake ledger + proof ledger + lease + source-closeback layer that a holon
reuses; it is NOT a second holon runtime.
"""

from __future__ import annotations

from dharma_swarm.operator_core.living_agent_kernel import LivingAgentKernel

__all__ = ["LivingAgentKernel"]
