from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.runtime import a2a_inbox_bridge


class _FakeMessage:
    def __init__(
        self,
        payload: dict,
        *,
        subject: str = "dharma.agent.hermes-m5.inbox",
        on_ack=None,
        delivery_count: int = 1,
    ) -> None:
        self.subject = subject
        self.data = json.dumps(payload).encode("utf-8")
        self.acked = 0
        self.nacked = 0
        self.on_ack = on_ack
        self.metadata = type("Metadata", (), {"num_delivered": delivery_count})()

    async def ack(self) -> None:
        if self.on_ack is not None:
            self.on_ack()
        self.acked += 1

    async def nak(self) -> None:
        self.nacked += 1


class _FakePublisher:
    def __init__(
        self,
        *,
        fail_publish: bool = False,
        fail_publish_calls: int = 0,
        return_puback: bool = True,
    ) -> None:
        self.fail_publish = fail_publish
        self.fail_publish_calls = fail_publish_calls
        self.return_puback = return_puback
        self.published: list[tuple[str, bytes]] = []
        self.publish_kwargs: list[dict] = []
        self.flushes = 0
        self.publish_calls = 0

    async def publish(self, subject: str, payload: bytes, **kwargs):
        self.publish_calls += 1
        if self.fail_publish or self.publish_calls <= self.fail_publish_calls:
            raise RuntimeError("publish failed")
        self.published.append((subject, payload))
        self.publish_kwargs.append(kwargs)
        if self.return_puback:
            return SimpleNamespace(stream="DHARMA_A2A", seq=self.publish_calls)
        return None

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
        job_db=tmp_path / "semantic_jobs.sqlite3",
        max_deliveries=3,
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
    assert publisher.flushes == 0
    assert publisher.published[0][0] == "dharma.agent.hermes-m5.inbox.ack.packet-1"
    assert publisher.publish_kwargs[0]["headers"]["Nats-Msg-Id"].startswith("handler_ack_")
    assert receipt["envelope_ack_transport_ack"] == {
        "transport_ack": "JETSTREAM_PUB_ACK",
        "stream": "DHARMA_A2A",
        "seq": 1,
    }

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
async def test_process_message_commits_semantic_job_before_source_ack(tmp_path: Path) -> None:
    config = _config(tmp_path)

    def assert_job_committed() -> None:
        job = a2a_inbox_bridge.load_committed_job(config.job_db, "packet-1")
        assert job is not None
        assert job["status"] == "PENDING"
        assert job["envelope"]["packet_id"] == "packet-1"

    message = _FakeMessage(_payload(), on_ack=assert_job_committed)

    receipt = await a2a_inbox_bridge.process_message(
        message,
        publisher=_FakePublisher(),
        config=config,
    )

    assert receipt["status"] == "DELIVERED_AND_ACKED"
    assert receipt["semantic_job_status"] == "PENDING"
    assert receipt["durable_job_committed"] is True


@pytest.mark.asyncio
async def test_process_message_dead_letters_missing_ack_subject(tmp_path: Path) -> None:
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

    assert receipt["status"] == "DEAD_LETTERED"
    assert receipt["failure_kind"] == "MALFORMED_ENVELOPE"
    assert "ack_subject" in receipt["error"]
    assert message.acked == 1
    assert message.nacked == 0
    assert publisher.published[0][0] == "dharma.dlq.dharma_fleet.hermes_inbox"


@pytest.mark.asyncio
async def test_process_message_naks_when_handler_ack_has_no_jetstream_puback(tmp_path: Path) -> None:
    config = _config(tmp_path)
    message = _FakeMessage(_payload())

    receipt = await a2a_inbox_bridge.process_message(
        message,
        publisher=_FakePublisher(return_puback=False),
        config=config,
    )

    assert receipt["status"] == "DELIVERY_FAILED"
    assert "durable puback" in receipt["error"]
    assert receipt["durable_job_committed"] is True
    assert receipt["envelope_ack_published"] is False
    assert message.acked == 0
    assert message.nacked == 1


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


@pytest.mark.asyncio
async def test_malformed_message_is_typed_dead_letter_not_false_success(tmp_path: Path) -> None:
    config = _config(tmp_path)
    message = _FakeMessage(_payload())
    message.data = b"{not-json"
    publisher = _FakePublisher()

    receipt = await a2a_inbox_bridge.process_message(
        message,
        publisher=publisher,
        config=config,
    )

    assert receipt["status"] == "DEAD_LETTERED"
    assert receipt["contact_evidence_tier"] == "NO_CONTACT"
    assert receipt["collaboration_claim"] == "none"
    assert receipt["broker_ack"] is True
    assert message.acked == 1
    assert message.nacked == 0
    assert publisher.published[0][0] == "dharma.dlq.dharma_fleet.hermes_inbox"
    dead_letter = json.loads(publisher.published[0][1].decode("utf-8"))
    assert dead_letter["schema"] == "dharma.nats.envelope.v1"
    assert dead_letter["payload"]["schema"] == "dharma.nats.dlq_failure.v1"
    assert dead_letter["payload"]["failure_kind"] == "MALFORMED_ENVELOPE"
    assert dead_letter["payload"]["original_payload_sha256"]
    assert "original_payload" not in dead_letter["payload"]
    assert receipt["dlq_transport_ack"]["transport_ack"] == "JETSTREAM_PUB_ACK"


@pytest.mark.asyncio
async def test_exhausted_transient_failure_dead_letters_then_source_acks(tmp_path: Path) -> None:
    config = _config(tmp_path)
    message = _FakeMessage(_payload(), delivery_count=config.max_deliveries)
    publisher = _FakePublisher(fail_publish_calls=1)

    receipt = await a2a_inbox_bridge.process_message(
        message,
        publisher=publisher,
        config=config,
    )

    assert receipt["status"] == "DEAD_LETTERED"
    assert receipt["failure_kind"] == "MAX_DELIVER_EXHAUSTED"
    assert receipt["durable_job_committed"] is True
    assert message.acked == 1
    assert message.nacked == 0
    assert publisher.published[0][0] == "dharma.dlq.dharma_fleet.hermes_inbox"
    dead_letter = json.loads(publisher.published[0][1])
    assert dead_letter["payload"]["delivery_count"] == 3
    assert dead_letter["payload"]["max_deliveries"] == 3


@pytest.mark.asyncio
async def test_packet_id_collision_dead_letters_without_overwriting_job(tmp_path: Path) -> None:
    config = _config(tmp_path)
    original = _payload()
    first = await a2a_inbox_bridge.process_message(
        _FakeMessage(original),
        publisher=_FakePublisher(),
        config=config,
    )
    assert first["status"] == "DELIVERED_AND_ACKED"
    original_job = a2a_inbox_bridge.load_committed_job(config.job_db, "packet-1")

    collision = dict(original)
    collision["content"] = "different command"
    message = _FakeMessage(collision, delivery_count=2)
    publisher = _FakePublisher()
    receipt = await a2a_inbox_bridge.process_message(
        message,
        publisher=publisher,
        config=config,
    )

    assert receipt["status"] == "DEAD_LETTERED"
    assert receipt["failure_kind"] == "IDEMPOTENCY_COLLISION"
    assert message.acked == 1
    assert json.loads(publisher.published[0][1])["payload"]["failure_kind"] == "IDEMPOTENCY_COLLISION"
    assert a2a_inbox_bridge.load_committed_job(config.job_db, "packet-1") == original_job
    assert a2a_inbox_bridge.count_committed_jobs(config.job_db) == 1


@pytest.mark.asyncio
async def test_restart_redelivery_reuses_one_durable_semantic_job(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = _FakeMessage(_payload())

    failed = await a2a_inbox_bridge.process_message(
        first,
        publisher=_FakePublisher(fail_publish=True),
        config=config,
    )

    assert failed["status"] == "DELIVERY_FAILED"
    assert first.nacked == 1
    redelivery = _FakeMessage(_payload(), delivery_count=2)
    recovered = await a2a_inbox_bridge.process_message(
        redelivery,
        publisher=_FakePublisher(),
        config=config,
    )

    assert recovered["status"] == "DELIVERED_AND_ACKED"
    assert recovered["duplicate"] is True
    assert redelivery.acked == 1
    assert a2a_inbox_bridge.count_committed_jobs(config.job_db) == 1


def test_subject_for_agent_rejects_unsafe_uid() -> None:
    with pytest.raises(ValueError):
        a2a_inbox_bridge.subject_for_agent("bad.agent")
