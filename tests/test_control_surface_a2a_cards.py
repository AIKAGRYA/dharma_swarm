import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client() -> TestClient:
    from api.routers.control_surface import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _write_receipt(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "dharma.a2a.send_receipt.v1",
        "packet_id": "a2a-api",
        "timestamp": "2026-06-11T07:45:00Z",
        "to": "hermes-m5",
        "subject": "dharma.a2a.hermes-m5",
        "ack_subject": "dharma.a2a.hermes-m5.ack.a2a-api",
        "reply_subject": "dharma.a2a.hermes-m5.reply.a2a-api",
        "file": "packet.md",
        "status": "NATS_CLIENT_MISSING",
        "contact_evidence_tier": "NO_CONTACT",
        "live_contact_claim": False,
        "collaboration_claim": "none",
        "operator_contact_note": "no live A2A collaboration proven",
    }
    (root / "20260611T074500Z-hermes-m5-a2a-api.json").write_text(
        json.dumps(receipt, sort_keys=True),
        encoding="utf-8",
    )


def test_control_surface_projects_a2a_send_receipts(tmp_path, monkeypatch):
    import api.routers.control_surface as control_surface_router

    _write_receipt(tmp_path)
    monkeypatch.setattr(control_surface_router, "_A2A_SEND_RECEIPT_ROOT", tmp_path)
    monkeypatch.setattr(control_surface_router, "_A2A_INBOX_BRIDGE_RECEIPT_ROOT", tmp_path / "bridge-empty")
    monkeypatch.setattr(control_surface_router, "_A2A_DOMAIN_REPLY_RECEIPT_ROOT", tmp_path / "domain-empty")
    monkeypatch.setattr(control_surface_router, "_A2A_REPLY_RECEIPT_ROOT", tmp_path / "reply-empty")

    resp = _client().get("/api/control-surface/a2a/cards?target=hermes-m5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["source_errors"] == []
    assert body["data"]["card_count"] == 1
    card = body["data"]["cards"][0]
    assert card["id"] == "a2a_hermes-m5_a2a-api"
    assert card["status"] == "blocked"
    assert card["render_hints"]["lane_hint"] == "a2a"
    assert card["receipt_refs"][0]["kind"] == "a2a_send_receipt"
    assert "contact_evidence_tier: NO_CONTACT" in card["body"]


def test_control_surface_projects_a2a_bridge_receipts(tmp_path, monkeypatch):
    import api.routers.control_surface as control_surface_router

    send_root = tmp_path / "send"
    bridge_root = tmp_path / "bridge"
    bridge_root.mkdir(parents=True)
    receipt = {
        "schema_version": "dharma.a2a.inbox_bridge_receipt.v1",
        "timestamp": "2026-06-11T08:15:00Z",
        "agent_uid": "hermes-m5",
        "subject": "dharma.agent.hermes-m5.inbox",
        "consumer": "hermes_inbox",
        "packet_id": "bridge-api",
        "status": "DELIVERED_AND_ACKED",
        "ack_subject": "dharma.agent.hermes-m5.inbox.ack.bridge-api",
        "contact_evidence_tier": "HANDLER_ACKED",
        "collaboration_claim": "filesystem_delivery_handler_ack",
        "semantic_reply_claim": False,
        "peer_model_processed_claim": False,
        "delivery_path": "/tmp/bridge-api.json",
    }
    (bridge_root / "20260611T081500Z-hermes-m5-bridge-api.json").write_text(
        json.dumps(receipt, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(control_surface_router, "_A2A_SEND_RECEIPT_ROOT", send_root)
    monkeypatch.setattr(control_surface_router, "_A2A_INBOX_BRIDGE_RECEIPT_ROOT", bridge_root)
    monkeypatch.setattr(control_surface_router, "_A2A_DOMAIN_REPLY_RECEIPT_ROOT", tmp_path / "domain-empty")
    monkeypatch.setattr(control_surface_router, "_A2A_REPLY_RECEIPT_ROOT", tmp_path / "reply-empty")

    resp = _client().get("/api/control-surface/a2a/cards?target=hermes-m5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["source_errors"] == []
    assert body["data"]["bridge_receipt_root"] == str(bridge_root)
    assert body["data"]["card_count"] == 1
    card = body["data"]["cards"][0]
    assert card["id"] == "a2a_bridge_hermes-m5_bridge-api"
    assert card["status"] == "review"
    assert card["receipt_refs"][0]["kind"] == "a2a_inbox_bridge_receipt"
    assert "semantic_reply_claim: False" in card["body"]


def test_control_surface_projects_a2a_reply_receipts(tmp_path, monkeypatch):
    import api.routers.control_surface as control_surface_router

    send_root = tmp_path / "send"
    bridge_root = tmp_path / "bridge"
    reply_root = tmp_path / "reply"
    reply_root.mkdir(parents=True)
    receipt = {
        "schema_version": "dharma.a2a.reply_capture_receipt.v1",
        "timestamp": "2026-06-11T08:32:00Z",
        "to": "hermes",
        "target_uid": "hermes-m5",
        "packet_id": "reply-api",
        "status": "NO_REPLY",
        "reply_evidence_tier": "NO_REPLY",
        "contact_evidence_tier": "HANDLER_ACKED",
        "semantic_reply_claim": False,
        "domain_receipt_claim": False,
        "reply_subject": "dharma.agent.hermes-m5.inbox.reply.reply-api",
        "send_receipt_path": "/tmp/reply-api-send.json",
    }
    (reply_root / "20260611T083200Z-hermes-reply-api.json").write_text(
        json.dumps(receipt, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(control_surface_router, "_A2A_SEND_RECEIPT_ROOT", send_root)
    monkeypatch.setattr(control_surface_router, "_A2A_INBOX_BRIDGE_RECEIPT_ROOT", bridge_root)
    monkeypatch.setattr(control_surface_router, "_A2A_DOMAIN_REPLY_RECEIPT_ROOT", tmp_path / "domain-empty")
    monkeypatch.setattr(control_surface_router, "_A2A_REPLY_RECEIPT_ROOT", reply_root)

    resp = _client().get("/api/control-surface/a2a/cards?target=hermes")

    assert resp.status_code == 200
    body = resp.json()
    assert body["source_errors"] == []
    assert body["data"]["reply_receipt_root"] == str(reply_root)
    assert body["data"]["card_count"] == 1
    card = body["data"]["cards"][0]
    assert card["id"] == "a2a_reply_hermes_reply-api"
    assert card["status"] == "review"
    assert card["receipt_refs"][0]["kind"] == "a2a_reply_capture_receipt"
    assert "reply_evidence_tier: NO_REPLY" in card["body"]


def test_control_surface_projects_a2a_domain_reply_receipts(tmp_path, monkeypatch):
    import api.routers.control_surface as control_surface_router

    send_root = tmp_path / "send"
    bridge_root = tmp_path / "bridge"
    domain_reply_root = tmp_path / "domain"
    reply_root = tmp_path / "reply"
    domain_reply_root.mkdir(parents=True)
    receipt = {
        "schema_version": "dharma.a2a.domain_reply_publish_receipt.v1",
        "timestamp": "2026-06-11T08:49:00Z",
        "agent_uid": "hermes-m5",
        "packet_id": "domain-api",
        "status": "ARTIFACT_INVALID",
        "reply_evidence_tier": "NO_CONTACT",
        "contact_evidence_tier": "NO_CONTACT",
        "semantic_reply_claim": False,
        "domain_receipt_claim": False,
        "target_owned_artifact_claim": False,
        "reply_subject": "dharma.agent.hermes-m5.inbox.reply.domain-api",
        "send_receipt_path": "/tmp/domain-api-send.json",
        "reply_artifact_path": "/tmp/domain-api-reply.json",
    }
    (domain_reply_root / "20260611T084900Z-hermes-m5-domain-api.json").write_text(
        json.dumps(receipt, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(control_surface_router, "_A2A_SEND_RECEIPT_ROOT", send_root)
    monkeypatch.setattr(control_surface_router, "_A2A_INBOX_BRIDGE_RECEIPT_ROOT", bridge_root)
    monkeypatch.setattr(control_surface_router, "_A2A_DOMAIN_REPLY_RECEIPT_ROOT", domain_reply_root)
    monkeypatch.setattr(control_surface_router, "_A2A_REPLY_RECEIPT_ROOT", reply_root)

    resp = _client().get("/api/control-surface/a2a/cards?target=hermes-m5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["source_errors"] == []
    assert body["data"]["domain_reply_receipt_root"] == str(domain_reply_root)
    assert body["data"]["card_count"] == 1
    card = body["data"]["cards"][0]
    assert card["id"] == "a2a_domain_reply_hermes-m5_domain-api"
    assert card["status"] == "blocked"
    assert card["receipt_refs"][0]["kind"] == "a2a_domain_reply_publish_receipt"
    assert "kind: domain_reply_publish" in card["body"]
