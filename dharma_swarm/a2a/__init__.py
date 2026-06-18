"""A2A (Agent-to-Agent) protocol implementation for dharma_swarm.

Implements the A2A 1.0 spec (Linux Foundation) for standardized
agent discovery and task delegation. Replaces file-based TRISHULA messaging
with structured agent cards, skill discovery, and task lifecycle.

A2A 1.0 conformance:
    - 8 task states (SUBMITTED through AUTH_REQUIRED)
    - contextId for grouping related tasks
    - Part as strict one-of (text|raw|url|data) with mediaType/filename
    - Artifact distinct from Message (outputs vs conversation)
    - AgentSkill with id, tags, examples, per-skill security
    - SecuritySchemes (APIKey, HTTPAuth, OAuth2, MutualTLS, OpenIdConnect)
    - JWS-signed Agent Cards (signatures[])
    - extensions[] for dharma-specific layers (telos, witness, gnani)
    - Cycle detection on dispatch chains

Core components:
    - AgentCard / CardRegistry: skill advertisement and discovery
    - A2AServer: receives task delegations, dispatches to orchestrator
    - A2AClient: discovers agents, delegates tasks with cycle guard
    - A2ABridge: backward-compatible bridge to TRISHULA and signal_bus
    - NodeGateway: HTTP transport layer (FastAPI router per node)
    - NodeRegistry: central directory of fleet nodes with health monitoring
"""

from dharma_swarm.a2a.agent_card import (
    A2A_INBOX_ROUTE_ALIAS,
    A2AInboxRoute,
    AgentCard,
    AgentCapability,
    AgentSkill,
    CardRegistry,
    SecurityScheme,
    a2a_inbox_subject,
    resolve_agent_uid,
)
from dharma_swarm.a2a.a2a_server import (
    A2AArtifact,
    A2AExtension,
    A2AMessage,
    A2APart,
    A2APartType,
    A2AServer,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.a2a.a2a_client import A2AClient
from dharma_swarm.a2a.a2a_bridge import A2ABridge
from dharma_swarm.a2a.nats_transport import A2ANatsTransport, NatsTransportConfig
from dharma_swarm.a2a.node_registry import NodeRegistry, RemoteNode
from dharma_swarm.a2a.registry_hydrator import hydrate_from_receipts
from dharma_swarm.a2a.agent_presence import AgentPresence, list_agent_presence
from dharma_swarm.a2a.task_receipt import (
    RECEIPT_SCHEMA,
    ReceiptValidation,
    bounce_payload,
    validate_or_quarantine_file,
    validate_task_receipt,
)

__all__ = [
    "AgentCard",
    "A2A_INBOX_ROUTE_ALIAS",
    "A2AInboxRoute",
    "AgentCapability",
    "AgentSkill",
    "CardRegistry",
    "SecurityScheme",
    "a2a_inbox_subject",
    "resolve_agent_uid",
    "A2AArtifact",
    "A2AExtension",
    "A2AMessage",
    "A2APart",
    "A2APartType",
    "A2AServer",
    "A2ATask",
    "A2ATaskStatus",
    "A2AClient",
    "A2ABridge",
    "A2ANatsTransport",
    "NatsTransportConfig",
    "NodeRegistry",
    "RemoteNode",
    "hydrate_from_receipts",
    "AgentPresence",
    "list_agent_presence",
    "RECEIPT_SCHEMA",
    "ReceiptValidation",
    "bounce_payload",
    "validate_or_quarantine_file",
    "validate_task_receipt",
]
