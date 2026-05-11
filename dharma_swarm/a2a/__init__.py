"""A2A (Agent-to-Agent) protocol implementation for dharma_swarm.

Implements a subset of Google's Agent-to-Agent protocol for standardized
agent discovery and task delegation. Replaces file-based TRISHULA messaging
with structured agent cards, capability discovery, and task lifecycle.

Core components:
    - AgentCard / CardRegistry: capability advertisement and discovery
    - A2AServer: receives task delegations, dispatches to orchestrator
    - A2AClient: discovers agents, delegates tasks, monitors completion
    - A2ABridge: backward-compatible bridge to TRISHULA and signal_bus
    - NodeGateway: HTTP transport layer (FastAPI router per node)
    - NodeRegistry: central directory of fleet nodes with health monitoring
"""

from dharma_swarm.a2a.agent_card import (
    AgentCard,
    AgentCapability,
    CardRegistry,
)
from dharma_swarm.a2a.a2a_server import A2AServer
from dharma_swarm.a2a.a2a_client import A2AClient
from dharma_swarm.a2a.a2a_bridge import A2ABridge
from dharma_swarm.a2a.node_registry import NodeRegistry, RemoteNode

__all__ = [
    "AgentCard",
    "AgentCapability",
    "CardRegistry",
    "A2AServer",
    "A2AClient",
    "A2ABridge",
    "NodeRegistry",
    "RemoteNode",
]
