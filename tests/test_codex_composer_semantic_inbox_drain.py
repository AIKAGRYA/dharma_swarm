from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.operator_core.semantic_receipt import SCHEMA_VERSION
from scripts.runtime.codex_composer_semantic_inbox_drain import drain_semantic_inbox


def _delivery_record(tmp_path: Path, *, agent_uid: str = "codex_composer") -> Path:
    path = tmp_path / "delivery.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.inbox_delivery.v1",
                "agent_uid": agent_uid,
                "bridge_kind": "filesystem_delivery_handler",
                "source_subject": f"dharma.agent.{agent_uid}.inbox",
                "envelope_sha256": "abc123",
                "envelope": {
                    "packet_id": "packet-1",
                    "reply_subject": f"dharma.agent.{agent_uid}.inbox.reply.packet-1",
                    "target_uid": agent_uid,
                    "body": "Please produce a semantic receipt.",
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _mock_model_response(tmp_path: Path) -> Path:
    path = tmp_path / "model_response.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "receipt_id": "semr-codex",
                "created_at": "2026-06-11T16:40:00Z",
                "agent_uid": "codex_composer",
                "critic_agent_id": "ollama:glm-5:cloud",
                "model_identity": {"provider": "ollama", "model": "glm-5:cloud"},
                "authored_by_model": True,
                "review_target": "a2a:packet-1",
                "intent_ack": True,
                "capability_match": 0.9,
                "understood_request": True,
                "missing_context": [],
                "verdict": "pass",
                "summary": "The A2A delivery asks for semantic proof and is understood.",
                "recommendations": [{"priority": "p1", "action": "publish domain reply"}],
                "acceptance_gates": [{"name": "semantic", "condition": "valid", "met": True}],
                "explicit_disagreement": "",
                "evidence_refs": [],
                "confidence": 0.84,
                "not_claimed_agents": ["claude", "fable", "hermes", "devin"],
                "failure_type": "",
                "failure_reason": "",
                "correlation_id": "packet-1",
                "reply_to": "dharma.agent.codex_composer.inbox.reply.packet-1",
                "model_call_latency_ms": 17,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _mock_invalid_model_response(tmp_path: Path) -> Path:
    path = tmp_path / "invalid_model_response.txt"
    path.write_text("not json", encoding="utf-8")
    return path


def test_drain_semantic_inbox_writes_semantic_receipt_and_domain_artifact(tmp_path: Path) -> None:
    receipt = drain_semantic_inbox(
        delivery_record_path=_delivery_record(tmp_path),
        mock_response_file=_mock_model_response(tmp_path),
        outbox_root=tmp_path / "outboxes",
        semantic_receipt_dir=tmp_path / "semantic_receipts",
        artifact_receipt_dir=tmp_path / "artifact_receipts",
        drain_receipt_dir=tmp_path / "drain_receipts",
    )

    assert receipt["status"] == "SEMANTIC_INBOX_DRAINED"
    assert receipt["semantic_reply_claim"] is True
    assert receipt["handler_ack_is_semantic_cognition"] is False
    semantic_path = Path(receipt["semantic_receipt_path"])
    artifact_path = Path(receipt["domain_reply_artifact_path"])
    assert semantic_path.exists()
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["schema_version"] == "dharma.a2a.domain_reply_artifact.v1"
    assert artifact["agent_uid"] == "codex_composer"
    assert artifact["semantic_reply_claim"] is True
    assert artifact["peer_model_processed_claim"] is True
    assert artifact["source_audit_claim"] is False
    assert artifact["authenticated_target_runtime_claim"] is False
    assert artifact["semantic_audit_depth"] == "packet_only"
    assert artifact["summary"].startswith("Semantic packet receipt only; source audit not claimed.")
    assert artifact["semantic_receipt_path"] == str(semantic_path)
    assert str(semantic_path) in artifact["evidence_refs"]


def test_drain_semantic_inbox_supports_non_codex_target_identity(tmp_path: Path) -> None:
    receipt = drain_semantic_inbox(
        delivery_record_path=_delivery_record(tmp_path, agent_uid="hermes-m5"),
        mock_response_file=_mock_model_response(tmp_path),
        outbox_root=tmp_path / "outboxes",
        semantic_receipt_dir=tmp_path / "semantic_receipts",
        artifact_receipt_dir=tmp_path / "artifact_receipts",
        drain_receipt_dir=tmp_path / "drain_receipts",
        agent_uid="hermes-m5",
    )

    assert receipt["status"] == "SEMANTIC_INBOX_DRAINED"
    assert receipt["schema_version"] == "dharma.a2a.semantic_inbox_drain.v1"
    prompt = Path(receipt["prompt_file"]).read_text(encoding="utf-8")
    assert "Read this delivered A2A packet as hermes-m5." in prompt

    semantic = json.loads(Path(receipt["semantic_receipt_path"]).read_text(encoding="utf-8"))
    assert semantic["agent_uid"] == "hermes-m5"
    assert semantic["reply_to"] == "dharma.agent.hermes-m5.inbox.reply.packet-1"

    artifact = json.loads(Path(receipt["domain_reply_artifact_path"]).read_text(encoding="utf-8"))
    assert artifact["agent_uid"] == "hermes-m5"
    assert artifact["author_kind"] == "hermes-m5_semantic_inbox_drain"
    assert artifact["semantic_reply_claim"] is True
    assert artifact["source_audit_claim"] is False


def test_drain_semantic_inbox_marks_typed_failures_without_source_audit_depth(tmp_path: Path) -> None:
    receipt = drain_semantic_inbox(
        delivery_record_path=_delivery_record(tmp_path, agent_uid="hermes-m5"),
        mock_response_file=_mock_invalid_model_response(tmp_path),
        outbox_root=tmp_path / "outboxes",
        semantic_receipt_dir=tmp_path / "semantic_receipts",
        artifact_receipt_dir=tmp_path / "artifact_receipts",
        drain_receipt_dir=tmp_path / "drain_receipts",
        agent_uid="hermes-m5",
    )

    assert receipt["status"] == "SEMANTIC_INBOX_DRAIN_TYPED_FAILURE"
    assert receipt["semantic_reply_claim"] is False
    assert receipt["source_audit_claim"] is False
    assert receipt["semantic_audit_depth"] == "typed_failure"

    artifact = json.loads(Path(receipt["domain_reply_artifact_path"]).read_text(encoding="utf-8"))
    assert artifact["semantic_reply_claim"] is False
    assert artifact["source_audit_claim"] is False
    assert artifact["semantic_audit_depth"] == "typed_failure"


def test_drain_semantic_inbox_rejects_wrong_target(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="is not 'codex_composer'"):
        drain_semantic_inbox(
            delivery_record_path=_delivery_record(tmp_path, agent_uid="hermes-m5"),
            mock_response_file=_mock_model_response(tmp_path),
            outbox_root=tmp_path / "outboxes",
            semantic_receipt_dir=tmp_path / "semantic_receipts",
            artifact_receipt_dir=tmp_path / "artifact_receipts",
            drain_receipt_dir=tmp_path / "drain_receipts",
        )
