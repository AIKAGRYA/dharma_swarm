from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.runtime.codex_composer_semantic_responder import (
    baseline_existing_deliveries,
    delivery_from_path,
    find_send_receipt,
    pending_deliveries,
    run_once,
    should_mark_processed,
)


def _delivery_record(
    tmp_path: Path,
    *,
    agent_uid: str = "codex_composer",
    packet_id: str = "packet-1",
) -> Path:
    path = tmp_path / "inbox" / f"{packet_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.inbox_delivery.v1",
                "agent_uid": agent_uid,
                "bridge_kind": "filesystem_delivery_handler",
                "source_subject": f"dharma.agent.{agent_uid}.inbox",
                "envelope_sha256": "abc123",
                "envelope": {
                    "packet_id": packet_id,
                    "reply_subject": f"dharma.agent.{agent_uid}.inbox.reply.{packet_id}",
                    "target_uid": agent_uid,
                    "content": "Please produce a semantic receipt.",
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _ignored_ack(tmp_path: Path) -> Path:
    path = tmp_path / "inbox" / "ack.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": "dharma.a2a.ack.v1"}), encoding="utf-8")
    return path


def _send_receipt(tmp_path: Path, *, agent_uid: str = "codex_composer") -> Path:
    path = tmp_path / "send_receipts" / "send.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.send_receipt.v1",
                "packet_id": "packet-1",
                "target_uid": agent_uid,
                "to": agent_uid,
                "status": "CODEX_COMPOSER_CONSUMED",
                "contact_evidence_tier": "HANDLER_ACKED",
                "reply_subject": f"dharma.agent.{agent_uid}.inbox.reply.packet-1",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _canonical_state_path(tmp_path: Path, *, agent_uid: str = "codex_composer") -> Path:
    return tmp_path / "a2a_bus" / "state" / f"{agent_uid}.json"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bridge_heartbeat(tmp_path: Path, *, agent_uid: str = "codex_composer") -> Path:
    path = tmp_path / "a2a_bus" / "bridge_heartbeats" / f"{agent_uid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
                "timestamp": _utc_now(),
                "agent_uid": agent_uid,
                "subject": f"dharma.agent.{agent_uid}.inbox",
                "stream": "DHARMA_FLEET",
                "consumer": f"{agent_uid}_inbox",
                "status": "IDLE",
                "cycle": 11,
                "last_receipt_path": str(tmp_path / "bridge-receipt.json"),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_delivery_from_path_accepts_only_targeted_delivery_records(tmp_path: Path) -> None:
    delivery_path = _delivery_record(tmp_path)
    _ignored_ack(tmp_path)

    delivery = delivery_from_path(delivery_path, agent_uid="codex_composer")

    assert delivery is not None
    assert delivery.packet_id == "packet-1"
    assert delivery.reply_subject == "dharma.agent.codex_composer.inbox.reply.packet-1"
    assert delivery_from_path(delivery_path, agent_uid="hermes-m5") is None


def test_pending_deliveries_skips_processed_and_non_delivery_json(tmp_path: Path) -> None:
    delivery = delivery_from_path(_delivery_record(tmp_path), agent_uid="codex_composer")
    assert delivery is not None
    _ignored_ack(tmp_path)

    pending = pending_deliveries(
        tmp_path / "inbox",
        agent_uid="codex_composer",
        processed_ids={delivery.delivery_id},
        limit=10,
    )

    assert pending == []


def test_find_send_receipt_matches_packet_reply_and_target(tmp_path: Path) -> None:
    send = _send_receipt(tmp_path)

    matched = find_send_receipt(
        tmp_path / "send_receipts",
        agent_uid="codex_composer",
        packet_id="packet-1",
        reply_subject="dharma.agent.codex_composer.inbox.reply.packet-1",
    )

    assert matched == send.resolve()


def test_pending_deliveries_can_filter_to_one_packet_id(tmp_path: Path) -> None:
    _delivery_record(tmp_path, packet_id="packet-1")
    _delivery_record(tmp_path, packet_id="packet-2")

    pending = pending_deliveries(
        tmp_path / "inbox",
        agent_uid="codex_composer",
        processed_ids=set(),
        limit=10,
        packet_id="packet-2",
    )

    assert [delivery.packet_id for delivery in pending] == ["packet-2"]


def test_baseline_existing_deliveries_marks_current_backlog_processed(tmp_path: Path) -> None:
    _delivery_record(tmp_path, packet_id="packet-1")
    _delivery_record(tmp_path, packet_id="packet-2")

    receipt = baseline_existing_deliveries(
        tmp_path / "inbox",
        state_dir=tmp_path / "state",
        agent_uid="codex_composer",
    )

    assert receipt["status"] == "BASELINE_RECORDED"
    assert receipt["delivery_count"] == 2
    processed = (tmp_path / "state" / "processed_deliveries.jsonl").read_text(encoding="utf-8")
    assert "BASELINED_EXISTING" in processed
    assert "packet-1" in processed
    assert "packet-2" in processed


def test_run_once_projects_no_pending_deliveries_as_fresh_canonical_liveness(
    tmp_path: Path,
) -> None:
    canonical_state = _canonical_state_path(tmp_path)
    canonical_state.parent.mkdir(parents=True, exist_ok=True)
    canonical_state.write_text(
        json.dumps(
            {
                "agent": "codex_composer",
                "status": "legacy_stale_status",
                "wake_loop_active": False,
                "legacy_field": "preserve-me",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    bridge = _bridge_heartbeat(tmp_path)

    receipts = run_once(
        inbox_dir=tmp_path / "inbox",
        state_dir=tmp_path / "state",
        send_receipt_root=tmp_path / "send_receipts",
        outbox_root=tmp_path / "outboxes",
        semantic_receipt_dir=tmp_path / "semantic_receipts",
        artifact_receipt_dir=tmp_path / "artifact_receipts",
        drain_receipt_dir=tmp_path / "drain_receipts",
        domain_reply_receipt_dir=tmp_path / "domain_reply_receipts",
        agent_uid="codex_composer",
        provider="ollama",
        model="glm-5:cloud",
        no_publish=False,
        stream="DHARMA_FLEET",
        timeout_s=0.1,
        flush_timeout_s=0.1,
        limit=1,
        lease_ttl_s=60,
        canonical_state_path=canonical_state,
    )

    assert receipts == []
    heartbeat = json.loads((tmp_path / "state" / "heartbeat.json").read_text(encoding="utf-8"))
    projected = json.loads(canonical_state.read_text(encoding="utf-8"))

    assert heartbeat["loop_status"] == "NO_PENDING_DELIVERIES"
    assert heartbeat["fresh"] is True
    assert heartbeat["live_model_call_claimed"] is False
    assert projected["legacy_field"] == "preserve-me"
    assert projected["schema_version"] == "dharma.holon_canonical_state.v1"
    assert projected["status"] == "partial"
    assert projected["last_processed_delivery_status"] == "NO_PENDING_DELIVERIES"
    assert projected["components"]["semantic_responder"]["status"] == "idle"
    assert projected["components"]["semantic_responder"]["fresh"] is True
    assert projected["components"]["semantic_responder"]["service_id"] == "codex-composer-semantic-responder"
    assert projected["live_model_call_claimed"] is False
    assert projected["provider_model_route"] == {
        "provider": "ollama",
        "model": "glm-5:cloud",
        "truth_source": "explicit_args_or_identity_json",
    }
    assert projected["responder_heartbeat_path"] == str(
        tmp_path / "agents" / "codex_composer" / "service_heartbeats.jsonl"
    )
    assert projected["bridge_heartbeat_path"] == str(bridge)
    assert projected["bridge_fresh"] is True
    assert projected["bridge_transport_reachable"] is True
    assert projected["freshness"]["semantic_responder"] == "fresh"
    assert projected["freshness"]["bridge"] == "fresh"


def test_should_mark_processed_retries_transient_failures() -> None:
    assert should_mark_processed("BASELINED_EXISTING") is True
    assert should_mark_processed("DOMAIN_REPLY_PUBLISHED") is True
    assert should_mark_processed("SEMANTIC_DRAINED_NO_PUBLISH") is True
    assert should_mark_processed("SEMANTIC_DRAINED_SEND_RECEIPT_MISSING") is False
    assert should_mark_processed("PUBLISH_FAILED") is False
    assert should_mark_processed("NATS_SECRETS_MISSING") is False
    assert should_mark_processed("SEMANTIC_RESPONDER_FAILED") is False


def test_run_once_drains_publishes_and_marks_processed(tmp_path: Path) -> None:
    _delivery_record(tmp_path)
    _send_receipt(tmp_path)
    outbox_root = tmp_path / "outboxes"

    def fake_drain(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["send_receipt_path"] == (tmp_path / "send_receipts" / "send.json").resolve()
        artifact = outbox_root / "codex_composer" / "packet-1-domain-reply.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            json.dumps(
                {
                    "schema_version": "dharma.a2a.domain_reply_artifact.v1",
                    "authored_by": "codex_composer",
                    "agent_uid": "codex_composer",
                    "packet_id": "packet-1",
                    "reply_subject": "dharma.agent.codex_composer.inbox.reply.packet-1",
                    "verdict": "reviewed",
                    "summary": "Responder test artifact.",
                    "semantic_reply_claim": False,
                    "peer_model_processed_claim": False,
                    "evidence_refs": [str(kwargs["delivery_record_path"])],
                    "send_receipt_path": str(kwargs["send_receipt_path"]),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return {
            "status": "SEMANTIC_INBOX_DRAIN_TYPED_FAILURE",
            "packet_id": "packet-1",
            "reply_subject": "dharma.agent.codex_composer.inbox.reply.packet-1",
            "domain_reply_artifact_path": str(artifact),
            "semantic_reply_claim": False,
        }

    def fake_publish(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["reply_artifact_path"] == outbox_root / "codex_composer" / "packet-1-domain-reply.json"
        return {
            "status": "DOMAIN_REPLY_PUBLISHED",
            "packet_id": "packet-1",
            "domain_receipt_claim": True,
            "semantic_reply_claim": False,
            "receipt_path": str(tmp_path / "domain_publish_receipt.json"),
        }

    receipts = run_once(
        inbox_dir=tmp_path / "inbox",
        state_dir=tmp_path / "state",
        send_receipt_root=tmp_path / "send_receipts",
        outbox_root=outbox_root,
        semantic_receipt_dir=tmp_path / "semantic_receipts",
        artifact_receipt_dir=tmp_path / "artifact_receipts",
        drain_receipt_dir=tmp_path / "drain_receipts",
        domain_reply_receipt_dir=tmp_path / "domain_reply_receipts",
        agent_uid="codex_composer",
        provider="ollama",
        model="glm-5:cloud",
        no_publish=False,
        stream="DHARMA_FLEET",
        timeout_s=0.1,
        flush_timeout_s=0.1,
        limit=1,
        lease_ttl_s=60,
        canonical_state_path=_canonical_state_path(tmp_path),
        drain_func=fake_drain,
        publish_func=fake_publish,
    )

    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["status"] == "DOMAIN_REPLY_PUBLISHED"
    assert receipt["handler_ack_is_semantic_cognition"] is False
    assert receipt["domain_receipt_claim"] is True
    assert Path(receipt["receipt_path"]).is_file()

    processed = (tmp_path / "state" / "processed_deliveries.jsonl").read_text(encoding="utf-8")
    assert "packet-1" in processed
    assert "DOMAIN_REPLY_PUBLISHED" in processed
    projected = json.loads(_canonical_state_path(tmp_path).read_text(encoding="utf-8"))
    assert projected["last_processed_delivery_status"] == "DOMAIN_REPLY_PUBLISHED"
    assert projected["latest_semantic_responder_receipt"]["packet_id"] == "packet-1"
    assert projected["latest_semantic_responder_receipt"]["status"] == "DOMAIN_REPLY_PUBLISHED"
    assert projected["latest_semantic_responder_receipt_path"]


def test_run_once_does_not_mark_processed_when_drain_fails(tmp_path: Path) -> None:
    _delivery_record(tmp_path)
    _send_receipt(tmp_path)

    def fake_drain(**kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("model unavailable")

    receipts = run_once(
        inbox_dir=tmp_path / "inbox",
        state_dir=tmp_path / "state",
        send_receipt_root=tmp_path / "send_receipts",
        outbox_root=tmp_path / "outboxes",
        semantic_receipt_dir=tmp_path / "semantic_receipts",
        artifact_receipt_dir=tmp_path / "artifact_receipts",
        drain_receipt_dir=tmp_path / "drain_receipts",
        domain_reply_receipt_dir=tmp_path / "domain_reply_receipts",
        agent_uid="codex_composer",
        provider="ollama",
        model="glm-5:cloud",
        no_publish=False,
        stream="DHARMA_FLEET",
        timeout_s=0.1,
        flush_timeout_s=0.1,
        limit=1,
        lease_ttl_s=60,
        canonical_state_path=_canonical_state_path(tmp_path),
        drain_func=fake_drain,
    )

    assert receipts[0]["status"] == "SEMANTIC_RESPONDER_FAILED"
    assert not (tmp_path / "state" / "processed_deliveries.jsonl").exists()
