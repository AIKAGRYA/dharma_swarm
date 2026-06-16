from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.runtime import a2a_inbox_bridge


class _FakeMessage:
    def __init__(self, payload: dict, *, subject: str = "dharma.agent.hermes-m5.inbox") -> None:
        self.subject = subject
        self.data = json.dumps(payload).encode("utf-8")
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


def _config(tmp_path: Path) -> a2a_inbox_bridge.InboxBridgeConfig:
    return a2a_inbox_bridge.InboxBridgeConfig(
        agent_uid="hermes-m5",
        subject="dharma.agent.hermes-m5.inbox",
        stream="DHARMA_FLEET",
        consumer="hermes_inbox",
        inbox_dir=tmp_path / "inbox",
        receipt_dir=tmp_path / "receipts",
    )


def _payload() -> dict:
    return {
        "schema_version": "dharma.a2a.send.v1",
        "packet_id": "packet-1",
        "from": "codex_composer",
        "to": "hermes-m5",
        "subject": "dharma.agent.hermes-m5.inbox",
        "ack_subject": "dharma.agent.hermes-m5.inbox.ack.packet-1",
        "reply_subject": "dharma.agent.hermes-m5.inbox.reply.packet-1",
        "content": "hello",
    }


@pytest.mark.asyncio
async def test_process_message_delivers_publishes_ack_and_broker_acks(tmp_path: Path) -> None:
    config = _config(tmp_path)
    message = _FakeMessage(_payload())
    publisher = _FakePublisher()

    receipt = await a2a_inbox_bridge.process_message(
        message,
        publisher=publisher,
        config=config,
    )

    assert receipt["status"] == "DELIVERED_AND_ACKED"
    assert receipt["contact_evidence_tier"] == "HANDLER_ACKED"
    assert receipt["semantic_reply_claim"] is False
    assert receipt["peer_model_processed_claim"] is False
    assert message.acked == 1
    assert message.nacked == 0
    assert publisher.flushes == 1
    assert publisher.published[0][0] == "dharma.agent.hermes-m5.inbox.ack.packet-1"

    ack = json.loads(publisher.published[0][1].decode("utf-8"))
    assert ack["ack_tier"] == "HANDLER_ACKED"
    assert ack["semantic_reply_claim"] is False

    delivered = json.loads((tmp_path / "inbox" / "packet-1.json").read_text())
    assert delivered["schema_version"] == "dharma.a2a.inbox_delivery.v1"
    assert delivered["envelope"]["packet_id"] == "packet-1"
    assert delivered["peer_model_processed_claim"] is False

    receipt_path = Path(receipt["receipt_path"])
    assert receipt_path.is_file()
    assert json.loads(receipt_path.read_text())["status"] == "DELIVERED_AND_ACKED"


@pytest.mark.asyncio
async def test_process_message_naks_missing_ack_subject(tmp_path: Path) -> None:
    payload = _payload()
    payload.pop("ack_subject")
    config = _config(tmp_path)
    message = _FakeMessage(payload)
    publisher = _FakePublisher()

    receipt = await a2a_inbox_bridge.process_message(
        message,
        publisher=publisher,
        config=config,
    )

    assert receipt["status"] == "DELIVERY_FAILED"
    assert "ack_subject" in receipt["error"]
    assert message.acked == 0
    assert message.nacked == 1
    assert publisher.published == []


@pytest.mark.asyncio
async def test_process_message_naks_when_ack_publish_fails(tmp_path: Path) -> None:
    config = _config(tmp_path)
    message = _FakeMessage(_payload())
    publisher = _FakePublisher(fail_publish=True)

    receipt = await a2a_inbox_bridge.process_message(
        message,
        publisher=publisher,
        config=config,
    )

    assert receipt["status"] == "DELIVERY_FAILED"
    assert "publish failed" in receipt["error"]
    assert message.acked == 0
    assert message.nacked == 1
    assert (tmp_path / "inbox" / "packet-1.json").is_file()


def test_subject_for_agent_rejects_unsafe_uid() -> None:
    with pytest.raises(ValueError):
        a2a_inbox_bridge.subject_for_agent("bad.agent")
