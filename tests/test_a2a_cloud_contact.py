from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from dharma_swarm.a2a.a2a_cloud_contact import (
    CloudContactIngress,
    publish_cloud_ingress,
)
from dharma_swarm.a2a.a2a_server import A2AServer, A2ATask, A2ATaskStatus
from dharma_swarm.a2a.contact_registry import (
    A2AContact,
    CONTACT_KIND_CLOUD_AGENT,
    ContactRegistryError,
    default_contact_registry,
)
from dharma_swarm.a2a.nats_transport import A2ANatsTransport
from dharma_swarm.a2a.verifier import build_denominator_report, cloud_agent_denominator
from dharma_swarm.runtime_state import RuntimeStateStore


@dataclass
class _FakePubAck:
    stream: str = "DHARMA_A2A"
    seq: int = 1


class _FakeJetStream:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes, dict[str, str] | None, float | None]] = []

    async def publish(
        self,
        subject: str,
        payload: bytes,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> _FakePubAck:
        self.published.append((subject, payload, headers, timeout))
        return _FakePubAck(seq=len(self.published))


class _FakeMessage:
    def __init__(self, subject: str, data: bytes) -> None:
        self.subject = subject
        self.data = data
        self.acked = 0
        self.nacked = 0

    async def ack(self) -> None:
        self.acked += 1

    async def nak(self) -> None:
        self.nacked += 1


@pytest.mark.asyncio
async def test_round_trip_without_operator_transport(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    jetstream = _FakeJetStream()
    ingress = CloudContactIngress(
        from_agent="perplexity-computer",
        to_agent="codex_composer",
        packet_id="packet-cloud-1",
        capability="probe",
        content="Can you synthesize the A2A bridge state?",
    )

    publish_result = await publish_cloud_ingress(
        ingress,
        runtime_state=runtime,
        jetstream=jetstream,
    )

    assert publish_result.contact_evidence_tier == "PUBLISH_ACCEPTED"
    assert publish_result.to_dict()["operator_transport_required"] is False
    assert len(jetstream.published) == 1
    subject, payload, headers, timeout = jetstream.published[0]
    assert subject == publish_result.subject
    assert headers and headers["Dharma-Correlation-Id"].startswith("a2a_cloud:")
    assert timeout == 2.0

    server = A2AServer(runtime_state=runtime, persist=False, require_execution_identity=True)
    seen: list[A2ATask] = []

    def handler(task: A2ATask) -> A2ATask:
        seen.append(task)
        task.status = A2ATaskStatus.COMPLETED
        task.result = "cloud packet accepted"
        return task

    server.register_handler("probe", handler)
    consumer = A2ANatsTransport(
        runtime_state=runtime,
        server=server,
        jetstream=jetstream,
    )
    message = _FakeMessage(subject, payload)
    consume_ack = await consumer.consume_message(message)

    assert consume_ack.status == "ack"
    assert message.acked == 1
    assert message.nacked == 0
    assert [task.from_agent for task in seen] == ["perplexity-computer"]
    assert seen[0].metadata["cloud_agent"] == "perplexity-computer"
    assert seen[0].metadata["operator_transport_required"] is False

    ledger = await runtime.get_run_ledger(headers["Dharma-Run-Id"])
    receipt_types = {(receipt.receipt_type, receipt.status) for receipt in ledger["receipts"]}
    assert ("nats_publish", "ack") in receipt_types
    assert ("nats_consume", "ack") in receipt_types


def test_contact_registry_includes_cloud_agent_population() -> None:
    registry = default_contact_registry()

    cloud_agents = registry.cloud_agents()

    assert len(cloud_agents) == 1
    assert cloud_agents[0].agent_uid == "perplexity-computer"
    assert cloud_agents[0].kind == CONTACT_KIND_CLOUD_AGENT


def test_cloud_agent_denominator_is_explicit() -> None:
    report = build_denominator_report()

    assert report.cloud_agent_denominator == cloud_agent_denominator()
    assert report.cloud_agent_denominator == 1
    assert report.total_agent_denominator == 5
    assert any(
        item["agent_uid"] == "perplexity-computer" and item["kind"] == "cloud_agent"
        for item in report.to_dict()["contacts"]
    )


def test_local_agent_cannot_enter_cloud_contact_path() -> None:
    registry = default_contact_registry()
    ingress = CloudContactIngress(
        from_agent="codex_composer",
        to_agent="perplexity-computer",
        packet_id="packet-local-1",
        content="This should use the local contact path.",
    )

    with pytest.raises(ContactRegistryError, match="not cloud_agent"):
        from dharma_swarm.a2a.a2a_cloud_contact import task_from_cloud_ingress

        task_from_cloud_ingress(ingress, registry=registry)


def test_unknown_target_cannot_enter_cloud_contact_path() -> None:
    registry = default_contact_registry()
    ingress = CloudContactIngress(
        from_agent="perplexity-computer",
        to_agent="ghost-agent",
        packet_id="packet-unknown-target",
        content="This should not route to an undeclared target.",
    )

    with pytest.raises(ContactRegistryError, match="unknown A2A contact"):
        from dharma_swarm.a2a.a2a_cloud_contact import task_from_cloud_ingress

        task_from_cloud_ingress(ingress, registry=registry)


def test_contact_registry_rejects_non_normalized_agent_uid() -> None:
    with pytest.raises(ContactRegistryError, match="agent_uid must be normalized"):
        A2AContact(
            agent_uid=" codex_composer",
            kind="local_agent",
            inbox_subject="dharma.agent.codex_composer.inbox",
        )


def test_cloud_contact_payload_schema_round_trip() -> None:
    payload = {
        "schema_version": "dharma.a2a.cloud_contact.v1",
        "from": "perplexity-computer",
        "to": "codex_composer",
        "packet_id": "packet-json-1",
        "capability": "probe",
        "content": "hello",
        "metadata": {"source": "unit-test"},
    }

    ingress = CloudContactIngress.from_payload(json.loads(json.dumps(payload)))

    assert ingress.from_agent == "perplexity-computer"
    assert ingress.to_agent == "codex_composer"
    assert ingress.metadata == {"source": "unit-test"}
