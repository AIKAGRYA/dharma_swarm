"""Cloud-agent ingress adapter for the A2A/NATS substrate.

This module is local-only. It validates an already-received cloud-agent packet,
maps it onto the existing A2A task envelope, and publishes through
``A2ANatsTransport`` so runtime-state receipts and idempotency remain owned by
the current NATS transport layer. It does not expose public HTTP ingress.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from dharma_swarm.a2a.a2a_server import A2AMessage, A2ATask
from dharma_swarm.a2a.contact_registry import (
    CONTACT_KIND_CLOUD_AGENT,
    ContactRegistry,
    ContactRegistryError,
    default_contact_registry,
)
from dharma_swarm.a2a.nats_transport import (
    A2ANatsTransport,
    JetStreamLike,
    NatsPublishAck,
    NatsTransportConfig,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity

SCHEMA_VERSION = "dharma.a2a.cloud_contact.v1"
JETSTREAM_PUBLISH_CONTRACT = "jetstream.publish"


class CloudContactError(ValueError):
    """Raised when a cloud contact ingress packet cannot be admitted."""


@dataclass(frozen=True)
class CloudContactIngress:
    """Validated cloud-agent ingress packet."""

    from_agent: str
    to_agent: str
    content: str
    packet_id: str
    capability: str = "cloud-contact"
    kind: str = "task"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("from_agent", "to_agent", "content", "packet_id"):
            if not str(getattr(self, field_name) or "").strip():
                raise CloudContactError(f"{field_name} is required")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CloudContactIngress":
        if str(payload.get("schema_version") or SCHEMA_VERSION) != SCHEMA_VERSION:
            raise CloudContactError("unsupported cloud contact schema_version")
        metadata = payload.get("metadata")
        return cls(
            from_agent=str(payload.get("from_agent") or payload.get("from") or ""),
            to_agent=str(payload.get("to_agent") or payload.get("to") or ""),
            content=str(payload.get("content") or ""),
            packet_id=str(payload.get("packet_id") or ""),
            capability=str(payload.get("capability") or "cloud-contact"),
            kind=str(payload.get("kind") or "task"),
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
        )


@dataclass(frozen=True)
class CloudContactPublishResult:
    ingress: CloudContactIngress
    task: A2ATask
    subject: str
    ack: NatsPublishAck
    contact_evidence_tier: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "dharma.a2a.cloud_contact_publish.v1",
            "from_agent": self.ingress.from_agent,
            "to_agent": self.ingress.to_agent,
            "packet_id": self.ingress.packet_id,
            "task_id": self.task.id,
            "subject": self.subject,
            "ack_status": self.ack.status,
            "ack_receipt_id": self.ack.receipt_id,
            "contact_evidence_tier": self.contact_evidence_tier,
            "operator_transport_required": False,
        }


def task_from_cloud_ingress(
    ingress: CloudContactIngress,
    *,
    registry: ContactRegistry | None = None,
) -> A2ATask:
    resolved_registry = registry or default_contact_registry()
    contact = resolved_registry.require(ingress.from_agent)
    target = resolved_registry.require(ingress.to_agent)
    if contact.kind != CONTACT_KIND_CLOUD_AGENT:
        raise ContactRegistryError(
            f"{ingress.from_agent} is registered as {contact.kind}, not cloud_agent"
        )
    task = A2ATask(
        id=f"a2a-cloud-{_stable_digest(ingress.from_agent, ingress.packet_id)}",
        from_agent=ingress.from_agent,
        to_agent=ingress.to_agent,
        capability=ingress.capability,
        history=[A2AMessage.text(ingress.content)],
        metadata={
            **dict(ingress.metadata),
            "schema_version": SCHEMA_VERSION,
            "cloud_agent": ingress.from_agent,
            "cloud_agent_kind": contact.kind,
            "target_agent_kind": target.kind,
            "cloud_contact_packet_id": ingress.packet_id,
            "operator_transport_required": False,
            "transport_adapter": "dharma_swarm.a2a.a2a_cloud_contact",
        },
    )
    task.dharma_task_id = f"task-a2a-cloud-{_stable_digest(task.id)}"
    return task


def execution_identity_for_cloud_ingress(
    ingress: CloudContactIngress,
    task: A2ATask,
) -> ExecutionIdentity:
    digest = _stable_digest(ingress.from_agent, ingress.to_agent, ingress.packet_id)
    return ExecutionIdentity.new(
        task_id=task.dharma_task_id or task.id,
        agent_id=ingress.to_agent,
        session_id="a2a_cloud_contact",
        trace_id=f"trace_a2a_cloud_{digest}",
        correlation_id=f"a2a_cloud:{ingress.from_agent}:{ingress.packet_id}",
        run_id=f"run_a2a_cloud_{digest}",
        claim_id=f"claim_a2a_cloud_{digest}",
        idempotency_key=f"idem_a2a_cloud:{ingress.from_agent}:{ingress.packet_id}",
        external_a2a_task_id=task.id,
        metadata={
            "surface": "dharma_swarm.a2a.a2a_cloud_contact",
            "cloud_agent": ingress.from_agent,
            "operator_transport_required": False,
        },
    )


async def publish_cloud_ingress(
    ingress: CloudContactIngress,
    *,
    runtime_state: RuntimeStateStore,
    jetstream: JetStreamLike,
    registry: ContactRegistry | None = None,
    config: NatsTransportConfig | None = None,
) -> CloudContactPublishResult:
    """Publish cloud ingress to NATS through the existing transport owner.

    The actual broker side effect is performed by ``A2ANatsTransport`` via the
    established ``jetstream.publish`` contract marker above.
    """

    task = task_from_cloud_ingress(ingress, registry=registry)
    identity = execution_identity_for_cloud_ingress(ingress, task)
    transport = A2ANatsTransport(
        runtime_state=runtime_state,
        jetstream=jetstream,
        config=config,
    )
    ack = await transport.publish_task(task, identity=identity)
    return CloudContactPublishResult(
        ingress=ingress,
        task=task,
        subject=ack.subject,
        ack=ack,
        contact_evidence_tier=(
            "PUBLISH_ACCEPTED" if ack.status == "ack" else "PUBLISH_DEDUPED"
        ),
    )


def _stable_digest(*parts: str) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
