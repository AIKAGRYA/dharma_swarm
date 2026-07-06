"""Identity organ — who a holon is, how it is registered/admitted.

Thin re-export over:
- dharma_swarm.agent_registry.AgentRegistry (identity + policy records)
- dharma_swarm.external_agent_registration (roaming/external admission)
- dharma_swarm.holon_bridge.load_holon / RunningHolon (identity -> runnable)
"""

from __future__ import annotations

from dharma_swarm.agent_registry import AgentRegistry
from dharma_swarm.holon_bridge import RunningHolon, load_holon

__all__ = ["AgentRegistry", "RunningHolon", "load_holon"]
