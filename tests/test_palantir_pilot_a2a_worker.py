from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.runtime import palantir_pilot_a2a_worker as worker


class _FakeMessage:
    def __init__(self, payload: dict, *, subject: str = worker.NATS_SUBJECT) -> None:
        self.subject = subject
        self.data = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.acked = 0
        self.nacked = 0

    async def ack(self) -> None:
        self.acked += 1

    async def nak(self) -> None:
        self.nacked += 1


class _FakePublisher:
    def __init__(self, *, fail_publish: bool = False) -> None:
        self.fail_publish = fail_publish
        self.published: list[tuple[str, bytes]] = []
        self.flushes = 0

    async def publish(self, subject: str, payload: bytes) -> None:
        if self.fail_publish:
            raise RuntimeError("publish failed")
        self.published.append((subject, payload))

    async def flush(self, timeout: float | None = None) -> None:
        self.flushes += 1


def _payload() -> dict:
    return {
        "schema_version": "dharma.a2a.send.v1",
        "packet_id": "pkt-palantir",
        "from": "codex",
        "to": "palantir-pilot",
        "subject": worker.NATS_SUBJECT,
        "ack_subject": "dharma.a2a.palantir-pilot.ack.pkt-palantir",
        "reply_subject": "dharma.a2a.palantir-pilot.reply.pkt-palantir",
        "content": "Advise on ontology name drift.",
    }


def _answer_builder(query: str, **_kwargs) -> dict:
    return {
        "schema_version": "palantir_pilot.answer_packet.v1",
        "query": query,
        "answer": "Treat name drift as ontology drift.",
        "confidence": "test_grounded",
        "source_boundary": "Public-source workspace synthesis only.",
        "source_citations": [
            {
                "url": "https://palantir.com/docs/foundry/api/ontology-resources/object-types/object-type-basics/",
                "family": "foundry",
            }
        ],
        "note_citations": [
            {
                "path": "/tmp/palantir-note.md",
                "snippet": "objects, links, actions",
            }
        ],
    }


def _config(tmp_path: Path) -> worker.PalantirPilotWorkerConfig:
    return worker.PalantirPilotWorkerConfig(
        receipt_dir=tmp_path / "receipts",
        outbox_dir=tmp_path / "outbox",
        dharma_home=tmp_path / ".dharma",
    )


@pytest.mark.asyncio
async def test_process_message_acks_answers_persists_and_replies(tmp_path: Path) -> None:
    config = _config(tmp_path)
    message = _FakeMessage(_payload())
    publisher = _FakePublisher()

    receipt = await worker.process_message(
        message,
        publisher=publisher,
        config=config,
        answer_builder=_answer_builder,
    )

    assert receipt["status"] == worker.STATUS_REPLIED
    assert receipt["contact_evidence_tier"] == "HANDLER_ACKED"
    assert receipt["reply_evidence_tier"] == worker.REPLY_TIER_SEMANTIC
    assert receipt["semantic_reply_claim"] is True
    assert receipt["peer_model_processed_claim"] is False
    assert receipt["live_contact_claim"] is True
    assert message.acked == 1
    assert message.nacked == 0
    assert publisher.flushes == 2
    assert [subject for subject, _payload in publisher.published] == [
        "dharma.a2a.palantir-pilot.ack.pkt-palantir",
        "dharma.a2a.palantir-pilot.reply.pkt-palantir",
    ]

    ack_payload = json.loads(publisher.published[0][1].decode("utf-8"))
    assert ack_payload["schema_version"] == worker.HANDLER_ACK_SCHEMA
    assert ack_payload["ack_tier"] == "HANDLER_ACKED"
    assert ack_payload["semantic_reply_claim"] is False

    reply_payload = json.loads(publisher.published[1][1].decode("utf-8"))
    assert reply_payload["schema_version"] == worker.SEMANTIC_REPLY_SCHEMA
    assert reply_payload["from_agent"] == "palantir-pilot"
    assert reply_payload["answer"] == "Treat name drift as ontology drift."
    assert reply_payload["semantic_reply_claim"] is True
    assert reply_payload["peer_model_processed_claim"] is False
    assert reply_payload["registration_boundary"]["authority"] == "external_worker_evidence_only"
    assert reply_payload["registration_boundary"]["official_affiliation"] is False
    assert reply_payload["evidence_refs"][0]["kind"] == "public_url_metadata"

    artifact = tmp_path / "outbox" / "pkt-palantir-answer.json"
    assert artifact.is_file()
    assert json.loads(artifact.read_text(encoding="utf-8")) == reply_payload
    assert Path(receipt["receipt_path"]).is_file()


@pytest.mark.asyncio
async def test_process_message_naks_invalid_packet_without_contact_claim(tmp_path: Path) -> None:
    config = _config(tmp_path)
    payload = _payload()
    payload.pop("ack_subject")
    message = _FakeMessage(payload)
    publisher = _FakePublisher()

    receipt = await worker.process_message(
        message,
        publisher=publisher,
        config=config,
        answer_builder=_answer_builder,
    )

    assert receipt["status"] == worker.STATUS_FAILED
    assert "ack_subject" in receipt["error"]
    assert receipt["contact_evidence_tier"] == "NO_CONTACT"
    assert receipt["semantic_reply_claim"] is False
    assert receipt["live_contact_claim"] is False
    assert message.acked == 0
    assert message.nacked == 1
    assert publisher.published == []


@pytest.mark.asyncio
async def test_process_message_naks_when_reply_publish_fails(tmp_path: Path) -> None:
    config = _config(tmp_path)
    message = _FakeMessage(_payload())
    publisher = _FakePublisher(fail_publish=True)

    receipt = await worker.process_message(
        message,
        publisher=publisher,
        config=config,
        answer_builder=_answer_builder,
    )

    assert receipt["status"] == worker.STATUS_FAILED
    assert "publish failed" in receipt["error"]
    assert receipt["semantic_reply_claim"] is False
    assert receipt["reply_published"] is False
    assert message.acked == 0
    assert message.nacked == 1
