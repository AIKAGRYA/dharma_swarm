from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.runtime import a2a_reply_capture


class _FakeMessage:
    def __init__(
        self,
        payload: object,
        *,
        subject: str = "dharma.agent.hermes-m5.inbox.reply.pkt",
        fail_ack: bool = False,
    ) -> None:
        self.subject = subject
        self.data = json.dumps(payload).encode("utf-8")
        self.fail_ack = fail_ack
        self.acked = 0
        self.nacked = 0

    async def ack(self) -> None:
        if self.fail_ack:
            raise RuntimeError("source ack failed")
        self.acked += 1

    async def nak(self) -> None:
        self.nacked += 1


def _send_receipt(tmp_path: Path, *, replied: bool = False) -> Path:
    root = tmp_path / "send"
    root.mkdir()
    receipt = {
        "schema_version": "dharma.a2a.send_receipt.v1",
        "timestamp": "2026-06-11T08:24:42Z",
        "to": "hermes",
        "target_uid": "hermes-m5",
        "packet_id": "pkt",
        "status": "HERMES_M5_CONSUMED",
        "contact_evidence_tier": "HANDLER_ACKED",
        "reply_subject": "dharma.agent.hermes-m5.inbox.reply.pkt",
        "replied": replied,
    }
    path = root / "20260611T082442Z-hermes-pkt.json"
    path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    return path


def _target(path: Path) -> a2a_reply_capture.ReplyCaptureTarget:
    return a2a_reply_capture.pending_reply_targets(path.parent)[0]


def test_pending_reply_targets_skips_replied_receipts(tmp_path: Path) -> None:
    _send_receipt(tmp_path, replied=True)

    assert a2a_reply_capture.pending_reply_targets(tmp_path / "send") == []


def test_pending_reply_targets_loads_unreplied_receipt(tmp_path: Path) -> None:
    path = _send_receipt(tmp_path)

    targets = a2a_reply_capture.pending_reply_targets(path.parent, target="hermes-m5")

    assert len(targets) == 1
    assert targets[0].packet_id == "pkt"
    assert targets[0].reply_subject == "dharma.agent.hermes-m5.inbox.reply.pkt"


def test_normalize_deliver_policy_accepts_latest_aliases() -> None:
    assert a2a_reply_capture.normalize_deliver_policy("") == "all"
    assert a2a_reply_capture.normalize_deliver_policy("all") == "all"
    assert a2a_reply_capture.normalize_deliver_policy("last-per-subject") == "latest"


def test_no_reply_receipt_preserves_original_handler_ack(tmp_path: Path) -> None:
    target = _target(_send_receipt(tmp_path))

    receipt = a2a_reply_capture.no_reply_receipt(
        target,
        stream="DHARMA_FLEET",
        endpoint="nats://127.0.0.1:4222",
    )

    assert receipt["status"] == "NO_REPLY"
    assert receipt["reply_evidence_tier"] == "NO_REPLY"
    assert receipt["contact_evidence_tier"] == "HANDLER_ACKED"
    assert receipt["semantic_reply_claim"] is False
    assert receipt["domain_receipt_claim"] is False


def test_reply_capture_consumer_name_is_stable_and_subject_scoped() -> None:
    subject = "dharma.agent.hermes-m5.inbox.reply.pkt"

    first = a2a_reply_capture.reply_consumer_name(subject)

    assert first == a2a_reply_capture.reply_consumer_name(subject)
    assert first.startswith("reply_capture_")
    assert first != a2a_reply_capture.reply_consumer_name(f"{subject}-other")


@pytest.mark.asyncio
async def test_capture_reply_message_records_untyped_reply(tmp_path: Path) -> None:
    target = _target(_send_receipt(tmp_path))
    message = _FakeMessage({"from": "hermes-m5", "content": "seen"})

    receipt = await a2a_reply_capture.capture_reply_message(
        target,
        message,
        receipt_root=tmp_path / "reply",
        stream="DHARMA_FLEET",
        endpoint="nats://127.0.0.1:4222",
    )

    assert receipt["status"] == "REPLY_CAPTURED"
    assert receipt["contact_evidence_tier"] == "HANDLER_ACKED"
    assert receipt["semantic_reply_claim"] is False
    assert receipt["domain_receipt_claim"] is False
    assert message.acked == 1
    assert Path(receipt["receipt_path"]).is_file()


@pytest.mark.asyncio
async def test_capture_reply_message_rejects_untyped_domain_receipt_self_assertion(tmp_path: Path) -> None:
    target = _target(_send_receipt(tmp_path))
    message = _FakeMessage(
        {
            "from": "hermes-m5",
            "packet_id": "pkt",
            "domain_receipt": True,
            "semantic_reply_claim": True,
        }
    )

    receipt = await a2a_reply_capture.capture_reply_message(
        target,
        message,
        receipt_root=tmp_path / "reply",
        stream="DHARMA_FLEET",
        endpoint="nats://127.0.0.1:4222",
    )

    assert receipt["status"] == "REPLY_CAPTURED"
    assert receipt["reply_schema"] == ""
    assert receipt["contact_evidence_tier"] == "HANDLER_ACKED"
    assert receipt["semantic_reply_claim"] is False
    assert receipt["domain_receipt_claim"] is False


@pytest.mark.asyncio
async def test_capture_reply_message_marks_subject_mismatch_red(tmp_path: Path) -> None:
    target = _target(_send_receipt(tmp_path))
    message = _FakeMessage(
        {"schema_version": "dharma.a2a.domain_receipt.v1", "packet_id": "pkt"},
        subject="dharma.agent.hermes-m5.inbox.reply.forged",
    )

    receipt = await a2a_reply_capture.capture_reply_message(
        target,
        message,
        receipt_root=tmp_path / "reply",
        stream="DHARMA_FLEET",
        endpoint="nats://127.0.0.1:4222",
    )

    assert receipt["status"] == "REPLY_SUBJECT_MISMATCH"
    assert receipt["reply_evidence_tier"] == "RED_MISMATCH"
    assert receipt["semantic_reply_claim"] is False
    assert receipt["domain_receipt_claim"] is False
    assert message.acked == 0
    assert message.nacked == 1


@pytest.mark.asyncio
async def test_capture_reply_message_records_domain_receipt(tmp_path: Path) -> None:
    target = _target(_send_receipt(tmp_path))
    message = _FakeMessage(
        {
            "schema_version": "dharma.a2a.domain_receipt.v1",
            "from": "hermes-m5",
            "packet_id": "pkt",
            "verdict": "reviewed",
            "semantic_reply_claim": False,
            "peer_model_processed_claim": False,
        }
    )

    receipt = await a2a_reply_capture.capture_reply_message(
        target,
        message,
        receipt_root=tmp_path / "reply",
        stream="DHARMA_FLEET",
        endpoint="nats://127.0.0.1:4222",
    )

    assert receipt["status"] == "DOMAIN_RECEIPTED"
    assert receipt["contact_evidence_tier"] == "DOMAIN_RECEIPTED"
    assert receipt["semantic_reply_claim"] is False
    assert receipt["domain_receipt_claim"] is True
    assert receipt["reply_schema"] == "dharma.a2a.domain_receipt.v1"


@pytest.mark.asyncio
async def test_reply_capture_ack_failure_redelivery_reuses_one_durable_receipt(tmp_path: Path) -> None:
    target = _target(_send_receipt(tmp_path))
    payload = {
        "schema_version": "dharma.a2a.domain_receipt.v1",
        "from": "hermes-m5",
        "packet_id": "pkt",
        "verdict": "reviewed",
    }
    first_message = _FakeMessage(payload, fail_ack=True)

    first = await a2a_reply_capture.capture_reply_message(
        target,
        first_message,
        receipt_root=tmp_path / "reply",
        stream="DHARMA_A2A",
        endpoint="nats://127.0.0.1:4222",
    )

    assert first["status"] == "REPLY_CAPTURE_FAILED"
    assert first_message.acked == 0
    assert first_message.nacked == 1
    committed_path = Path(first["recoverable_receipt_path"])
    assert committed_path.is_file()
    assert json.loads(committed_path.read_text())["status"] == "DOMAIN_RECEIPTED"

    redelivery = _FakeMessage(payload)
    recovered = await a2a_reply_capture.capture_reply_message(
        target,
        redelivery,
        receipt_root=tmp_path / "reply",
        stream="DHARMA_A2A",
        endpoint="nats://127.0.0.1:4222",
    )

    assert recovered["status"] == "DOMAIN_RECEIPTED"
    assert Path(recovered["receipt_path"]) == committed_path
    assert redelivery.acked == 1
    assert len(list((tmp_path / "reply").glob("*.json"))) == 1
