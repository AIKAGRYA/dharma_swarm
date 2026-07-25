from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.operator_core.semantic_receipt import SCHEMA_VERSION
from scripts.runtime import a2a_domain_reply_worker


class _FakePublisher:
    def __init__(self, *, fail_publish: bool = False, return_puback: bool = True) -> None:
        self.fail_publish = fail_publish
        self.return_puback = return_puback
        self.published: list[tuple[str, bytes]] = []
        self.publish_kwargs: list[dict] = []
        self.flushes = 0

    async def publish(self, subject: str, payload: bytes, **kwargs):
        if self.fail_publish:
            raise RuntimeError("publish failed")
        self.published.append((subject, payload))
        self.publish_kwargs.append(kwargs)
        if self.return_puback:
            return SimpleNamespace(stream="DHARMA_A2A", seq=len(self.published))
        return None

    async def flush(self, timeout: float | None = None) -> None:
        self.flushes += 1


def _send_receipt(tmp_path: Path) -> Path:
    path = tmp_path / "send_receipt.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.send_receipt.v1",
                "packet_id": "packet-1",
                "to": "hermes",
                "target_uid": "hermes-m5",
                "status": "HERMES_M5_CONSUMED",
                "contact_evidence_tier": "HANDLER_ACKED",
                "reply_subject": "dharma.agent.hermes-m5.inbox.reply.packet-1",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _reply_artifact(tmp_path: Path, *, outbox_root: Path | None = None, actor: str = "hermes-m5") -> Path:
    root = outbox_root or tmp_path / "outboxes"
    path = root / "hermes-m5" / "packet-1-domain-reply.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.domain_reply_artifact.v1",
                "authored_by": actor,
                "packet_id": "packet-1",
                "reply_subject": "dharma.agent.hermes-m5.inbox.reply.packet-1",
                "verdict": "reviewed",
                "summary": "Target-owned review artifact.",
                "evidence_refs": ["memory://hermes/example"],
                "peer_model_processed_claim": False,
                "semantic_reply_claim": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _semantic_receipt(tmp_path: Path, *, agent_uid: str = "hermes-m5") -> Path:
    path = tmp_path / "semantic_receipt.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "receipt_id": "semr-hermes",
                "created_at": "2026-06-11T16:40:00Z",
                "agent_uid": agent_uid,
                "critic_agent_id": "ollama:glm-5:cloud",
                "model_identity": {"provider": "ollama", "model": "glm-5:cloud"},
                "authored_by_model": True,
                "review_target": "a2a:packet-1",
                "intent_ack": True,
                "capability_match": 0.9,
                "understood_request": True,
                "missing_context": [],
                "verdict": "pass",
                "summary": "Hermes semantic receipt is model-authored.",
                "recommendations": [],
                "acceptance_gates": [{"name": "semantic", "condition": "valid", "met": True}],
                "explicit_disagreement": "",
                "evidence_refs": ["memory://hermes/example"],
                "confidence": 0.84,
                "not_claimed_agents": ["codex", "claude", "fable", "devin"],
                "failure_type": "",
                "failure_reason": "",
                "correlation_id": "packet-1",
                "reply_to": "dharma.agent.hermes-m5.inbox.reply.packet-1",
                "model_call_latency_ms": 17,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def test_load_domain_reply_target_requires_target_owned_outbox(tmp_path: Path) -> None:
    send = _send_receipt(tmp_path)
    artifact = _reply_artifact(tmp_path, outbox_root=tmp_path / "wrong-outboxes")

    with pytest.raises(ValueError, match="target-owned outbox"):
        a2a_domain_reply_worker.load_domain_reply_target(
            send_receipt_path=send,
            reply_artifact_path=artifact,
            outbox_root=tmp_path / "outboxes",
        )


def test_load_domain_reply_target_rejects_codex_authored_peer_artifact(tmp_path: Path) -> None:
    send = _send_receipt(tmp_path)
    artifact = _reply_artifact(tmp_path, actor="codex_composer")

    with pytest.raises(ValueError, match="does not match target agent"):
        a2a_domain_reply_worker.load_domain_reply_target(
            send_receipt_path=send,
            reply_artifact_path=artifact,
            outbox_root=tmp_path / "outboxes",
        )


def test_load_domain_reply_target_rejects_unbacked_semantic_claim(tmp_path: Path) -> None:
    send = _send_receipt(tmp_path)
    artifact = _reply_artifact(tmp_path)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["peer_model_processed_claim"] = True
    payload["semantic_reply_claim"] = True
    artifact.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="semantic reply claims require"):
        a2a_domain_reply_worker.load_domain_reply_target(
            send_receipt_path=send,
            reply_artifact_path=artifact,
            outbox_root=tmp_path / "outboxes",
        )


def test_load_domain_reply_target_rejects_wrong_packet_semantic_receipt(tmp_path: Path) -> None:
    send = _send_receipt(tmp_path)
    artifact = _reply_artifact(tmp_path)
    semantic = _semantic_receipt(tmp_path)
    semantic_payload = json.loads(semantic.read_text(encoding="utf-8"))
    semantic_payload["correlation_id"] = "packet-2"
    semantic_payload["review_target"] = "a2a:packet-2"
    semantic.write_text(json.dumps(semantic_payload, sort_keys=True), encoding="utf-8")
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["peer_model_processed_claim"] = True
    payload["semantic_reply_claim"] = True
    payload["semantic_receipt_path"] = str(semantic)
    payload["evidence_refs"] = [str(semantic)]
    artifact.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(ValueError, match="matching agent_uid, packet_id, and reply_subject"):
        a2a_domain_reply_worker.load_domain_reply_target(
            send_receipt_path=send,
            reply_artifact_path=artifact,
            outbox_root=tmp_path / "outboxes",
        )


@pytest.mark.asyncio
async def test_publish_domain_reply_emits_typed_domain_receipt(tmp_path: Path) -> None:
    send = _send_receipt(tmp_path)
    artifact = _reply_artifact(tmp_path)
    target = a2a_domain_reply_worker.load_domain_reply_target(
        send_receipt_path=send,
        reply_artifact_path=artifact,
        outbox_root=tmp_path / "outboxes",
    )
    publisher = _FakePublisher()

    receipt = await a2a_domain_reply_worker.publish_domain_reply(
        target,
        publisher=publisher,
        receipt_dir=tmp_path / "receipts",
        endpoint="nats://127.0.0.1:4222",
        stream="DHARMA_FLEET",
    )

    assert receipt["status"] == "DOMAIN_REPLY_PUBLISHED"
    assert receipt["reply_evidence_tier"] == "DOMAIN_RECEIPTED"
    assert receipt["domain_receipt_claim"] is True
    assert receipt["semantic_reply_claim"] is False
    assert publisher.flushes == 1
    assert publisher.published[0][0] == "dharma.agent.hermes-m5.inbox.reply.packet-1"
    assert publisher.publish_kwargs[0]["headers"]["Nats-Msg-Id"].startswith("domain_reply_")
    assert receipt["transport_ack"] == {
        "transport_ack": "JETSTREAM_PUB_ACK",
        "stream": "DHARMA_A2A",
        "seq": 1,
    }

    payload = json.loads(publisher.published[0][1].decode("utf-8"))
    assert payload["schema_version"] == "dharma.a2a.domain_receipt.v1"
    assert payload["from_agent"] == "hermes-m5"
    assert payload["packet_id"] == "packet-1"
    assert payload["domain_receipt"] is True
    assert payload["target_owned_artifact_claim"] is True
    assert payload["authenticated_target_runtime_claim"] is False
    assert payload["source_audit_claim"] is False
    assert payload["semantic_audit_depth"] == "typed_failure"
    assert payload["semantic_reply_claim"] is False
    assert payload["peer_model_processed_claim"] is False
    assert Path(receipt["receipt_path"]).is_file()


@pytest.mark.asyncio
async def test_publish_domain_reply_preserves_explicit_peer_model_semantic_claim(tmp_path: Path) -> None:
    send = _send_receipt(tmp_path)
    artifact = _reply_artifact(tmp_path)
    semantic = _semantic_receipt(tmp_path)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["peer_model_processed_claim"] = True
    payload["semantic_reply_claim"] = True
    payload["semantic_receipt_path"] = str(semantic)
    payload["evidence_refs"] = [str(semantic)]
    artifact.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    target = a2a_domain_reply_worker.load_domain_reply_target(
        send_receipt_path=send,
        reply_artifact_path=artifact,
        outbox_root=tmp_path / "outboxes",
    )
    publisher = _FakePublisher()

    receipt = await a2a_domain_reply_worker.publish_domain_reply(
        target,
        publisher=publisher,
        receipt_dir=tmp_path / "receipts",
        endpoint="nats://127.0.0.1:4222",
        stream="DHARMA_FLEET",
    )

    assert receipt["status"] == "DOMAIN_REPLY_PUBLISHED"
    assert receipt["semantic_reply_claim"] is True
    published = json.loads(publisher.published[0][1].decode("utf-8"))
    assert published["semantic_reply_claim"] is True
    assert published["peer_model_processed_claim"] is True
    assert published["authenticated_target_runtime_claim"] is False
    assert published["validated_semantic_receipt_refs"] == [str(semantic.resolve())]


@pytest.mark.asyncio
async def test_publish_domain_reply_without_jetstream_puback_is_not_success(tmp_path: Path) -> None:
    send = _send_receipt(tmp_path)
    artifact = _reply_artifact(tmp_path)
    target = a2a_domain_reply_worker.load_domain_reply_target(
        send_receipt_path=send,
        reply_artifact_path=artifact,
        outbox_root=tmp_path / "outboxes",
    )

    receipt = await a2a_domain_reply_worker.publish_domain_reply(
        target,
        publisher=_FakePublisher(return_puback=False),
        receipt_dir=tmp_path / "receipts",
        endpoint="nats://127.0.0.1:4222",
        stream="DHARMA_A2A",
    )

    assert receipt["status"] == "PUBLISH_FAILED"
    assert receipt["reply_evidence_tier"] == "NO_CONTACT"
    assert receipt["domain_receipt_claim"] is False
    assert "durable puback" in receipt["error"]


@pytest.mark.asyncio
async def test_publish_domain_reply_failure_does_not_claim_domain_receipt(tmp_path: Path) -> None:
    send = _send_receipt(tmp_path)
    artifact = _reply_artifact(tmp_path)
    target = a2a_domain_reply_worker.load_domain_reply_target(
        send_receipt_path=send,
        reply_artifact_path=artifact,
        outbox_root=tmp_path / "outboxes",
    )

    receipt = await a2a_domain_reply_worker.publish_domain_reply(
        target,
        publisher=_FakePublisher(fail_publish=True),
        receipt_dir=tmp_path / "receipts",
        endpoint="nats://127.0.0.1:4222",
        stream="DHARMA_FLEET",
    )

    assert receipt["status"] == "PUBLISH_FAILED"
    assert receipt["reply_evidence_tier"] == "NO_CONTACT"
    assert receipt["domain_receipt_claim"] is False
    assert "publish failed" in receipt["error"]
