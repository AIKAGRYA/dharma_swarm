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

_LAZY_EXPORTS = {
    "A2A_INBOX_ROUTE_ALIAS": "dharma_swarm.a2a.agent_card",
    "A2AInboxRoute": "dharma_swarm.a2a.agent_card",
    "AgentCard": "dharma_swarm.a2a.agent_card",
    "AgentCapability": "dharma_swarm.a2a.agent_card",
    "AgentSkill": "dharma_swarm.a2a.agent_card",
    "CardRegistry": "dharma_swarm.a2a.agent_card",
    "SecurityScheme": "dharma_swarm.a2a.agent_card",
    "a2a_inbox_subject": "dharma_swarm.a2a.agent_card",
    "resolve_agent_uid": "dharma_swarm.a2a.agent_card",
    "A2AArtifact": "dharma_swarm.a2a.a2a_server",
    "A2AExtension": "dharma_swarm.a2a.a2a_server",
    "A2AMessage": "dharma_swarm.a2a.a2a_server",
    "A2APart": "dharma_swarm.a2a.a2a_server",
    "A2APartType": "dharma_swarm.a2a.a2a_server",
    "A2AServer": "dharma_swarm.a2a.a2a_server",
    "A2ATask": "dharma_swarm.a2a.a2a_server",
    "A2ATaskStatus": "dharma_swarm.a2a.a2a_server",
    "A2ATransitionError": "dharma_swarm.a2a.a2a_server",
    "A2AClient": "dharma_swarm.a2a.a2a_client",
    "A2ABridge": "dharma_swarm.a2a.a2a_bridge",
    "A2ANatsTransport": "dharma_swarm.a2a.nats_transport",
    "NatsTransportConfig": "dharma_swarm.a2a.nats_transport",
    "NodeRegistry": "dharma_swarm.a2a.node_registry",
    "RemoteNode": "dharma_swarm.a2a.node_registry",
    "hydrate_from_receipts": "dharma_swarm.a2a.registry_hydrator",
    "AgentPresence": "dharma_swarm.a2a.agent_presence",
    "list_agent_presence": "dharma_swarm.a2a.agent_presence",
    "RECEIPT_SCHEMA": "dharma_swarm.a2a.task_receipt",
    "ReceiptValidation": "dharma_swarm.a2a.task_receipt",
    "bounce_payload": "dharma_swarm.a2a.task_receipt",
    "validate_or_quarantine_file": "dharma_swarm.a2a.task_receipt",
    "validate_task_receipt": "dharma_swarm.a2a.task_receipt",
}

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
    "A2ATransitionError",
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


def __getattr__(name: str):
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals().keys(), *_LAZY_EXPORTS])
