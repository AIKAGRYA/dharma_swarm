from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import scripts.runtime.codex_composer_semantic_responder as responder


def test_live_receipt_defaults_share_responder_state_custody() -> None:
    receipt_dirs = {
        responder.DEFAULT_SEMANTIC_RECEIPT_DIR,
        responder.DEFAULT_ARTIFACT_RECEIPT_DIR,
        responder.DEFAULT_DRAIN_RECEIPT_DIR,
        responder.DEFAULT_DOMAIN_REPLY_RECEIPT_DIR,
    }

    assert receipt_dirs
    assert all(path.is_relative_to(responder.DEFAULT_STATE_DIR) for path in receipt_dirs)
    assert all(not path.is_relative_to(responder.REPO_ROOT) for path in receipt_dirs)


def _delivery_record(tmp_path: Path, *, packet_id: str = "packet-1") -> Path:
    path = tmp_path / "inbox" / f"{packet_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.inbox_delivery.v1",
                "agent_uid": "codex_composer",
                "envelope_sha256": "abc123",
                "envelope": {
                    "packet_id": packet_id,
                    "reply_subject": (
                        f"dharma.agent.codex_composer.inbox.reply.{packet_id}"
                    ),
                    "target_uid": "codex_composer",
                    "content": "Produce a semantic receipt.",
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _send_receipt(tmp_path: Path, *, packet_id: str = "packet-1") -> Path:
    path = tmp_path / "send_receipts" / "send.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.send_receipt.v1",
                "packet_id": packet_id,
                "target_uid": "codex_composer",
                "reply_subject": (
                    f"dharma.agent.codex_composer.inbox.reply.{packet_id}"
                ),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _semantic_drain(tmp_path: Path):
    artifact = tmp_path / "outboxes" / "codex_composer" / "packet-1-domain-reply.json"
    calls = {"count": 0}

    def drain(**_: Any) -> dict[str, Any]:
        calls["count"] += 1
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            json.dumps(
                {
                    "schema_version": "dharma.a2a.domain_reply_artifact.v1",
                    "agent_uid": "codex_composer",
                    "packet_id": "packet-1",
                    "semantic_reply_claim": True,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return {
            "status": "SEMANTIC_INBOX_DRAINED",
            "packet_id": "packet-1",
            "domain_reply_artifact_path": str(artifact),
            "semantic_receipt_path": str(tmp_path / "semantic.json"),
            "semantic_receipt_id": "semantic-1",
            "semantic_reply_claim": True,
        }

    return drain, calls, artifact


def _run_once(
    tmp_path: Path,
    *,
    drain_func,
    publish_func,
    max_publish_attempts: int,
) -> list[dict[str, Any]]:
    return responder.run_once(
        inbox_dir=tmp_path / "inbox",
        state_dir=tmp_path / "state",
        send_receipt_root=tmp_path / "send_receipts",
        outbox_root=tmp_path / "outboxes",
        semantic_receipt_dir=tmp_path / "semantic_receipts",
        artifact_receipt_dir=tmp_path / "artifact_receipts",
        drain_receipt_dir=tmp_path / "drain_receipts",
        domain_reply_receipt_dir=tmp_path / "domain_reply_receipts",
        agent_uid="codex_composer",
        provider="test",
        model="test",
        no_publish=False,
        stream="DHARMA_FLEET",
        timeout_s=0.1,
        flush_timeout_s=0.1,
        limit=1,
        lease_ttl_s=0,
        max_publish_attempts=max_publish_attempts,
        project_canonical_state=False,
        drain_func=drain_func,
        publish_func=publish_func,
    )


def _unexpected_publish(**_: Any) -> dict[str, Any]:
    raise AssertionError("publisher must not run without a causal send receipt")


def test_missing_send_receipt_dead_letters_without_remodelling(
    tmp_path: Path,
) -> None:
    _delivery_record(tmp_path)
    drain, drain_calls, artifact = _semantic_drain(tmp_path)

    first = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=_unexpected_publish,
        max_publish_attempts=3,
    )
    second = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=_unexpected_publish,
        max_publish_attempts=3,
    )
    third = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=_unexpected_publish,
        max_publish_attempts=3,
    )

    assert first[0]["status"] == responder.PENDING_PUBLISH_STATUS
    assert second[0]["status"] == responder.PENDING_PUBLISH_STATUS
    assert third[0]["status"] == responder.PUBLISH_RETRIES_EXHAUSTED_STATUS
    assert third[0]["publish_attempt_count"] == 3
    assert third[0]["terminal_effect_created"] is True
    assert drain_calls["count"] == 1
    assert artifact.is_file()
    assert (
        list(
            (tmp_path / "state" / responder.PENDING_PUBLISH_DIRNAME).glob("*.json")
        )
        == []
    )

    dead_letters = list(
        (tmp_path / "state" / responder.DEAD_LETTER_DIRNAME).glob("*.json")
    )
    assert len(dead_letters) == 1
    terminal = json.loads(dead_letters[0].read_text(encoding="utf-8"))
    assert terminal["semantic_reply_claim"] is True
    assert terminal["publish_attempt_count"] == 3
    assert terminal["authority_boundary"].endswith(
        "domain publication or remote effect."
    )

    processed_lines = (
        tmp_path / "state" / responder.PROCESSED_FILENAME
    ).read_text(encoding="utf-8").splitlines()
    assert len(processed_lines) == 1
    assert responder.PUBLISH_RETRIES_EXHAUSTED_STATUS in processed_lines[0]

    fourth = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=_unexpected_publish,
        max_publish_attempts=3,
    )
    assert fourth == []
    assert drain_calls["count"] == 1


def test_publish_failure_is_bounded_and_preserves_artifact(tmp_path: Path) -> None:
    _delivery_record(tmp_path)
    _send_receipt(tmp_path)
    drain, drain_calls, artifact = _semantic_drain(tmp_path)
    publish_calls = {"count": 0}

    def failed_publish(**_: Any) -> dict[str, Any]:
        publish_calls["count"] += 1
        raise RuntimeError("NATS unavailable")

    first = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=failed_publish,
        max_publish_attempts=2,
    )
    second = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=failed_publish,
        max_publish_attempts=2,
    )

    assert first[0]["status"] == responder.PENDING_PUBLISH_STATUS
    assert second[0]["status"] == responder.PUBLISH_RETRIES_EXHAUSTED_STATUS
    assert "NATS unavailable" in second[0]["error"]
    assert drain_calls["count"] == 1
    assert publish_calls["count"] == 2
    assert artifact.is_file()


def test_existing_terminal_effect_is_reused_after_crash_window(
    tmp_path: Path,
) -> None:
    _delivery_record(tmp_path)
    drain, drain_calls, _ = _semantic_drain(tmp_path)
    _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=_unexpected_publish,
        max_publish_attempts=1,
    )
    (tmp_path / "state" / responder.PROCESSED_FILENAME).unlink()

    def no_second_model(**_: Any) -> dict[str, Any]:
        raise AssertionError("terminal replay must not invoke the model")

    replay = _run_once(
        tmp_path,
        drain_func=no_second_model,
        publish_func=_unexpected_publish,
        max_publish_attempts=1,
    )

    assert replay[0]["status"] == responder.PUBLISH_RETRIES_EXHAUSTED_STATUS
    assert replay[0]["terminal_effect_reused"] is True
    assert drain_calls["count"] == 1
    assert len(
        list((tmp_path / "state" / responder.DEAD_LETTER_DIRNAME).glob("*.json"))
    ) == 1


def test_operator_quarantine_terminalizes_legacy_pin_exactly_once(
    tmp_path: Path,
) -> None:
    delivery_path = _delivery_record(tmp_path)
    delivery = responder.delivery_from_path(
        delivery_path,
        agent_uid="codex_composer",
    )
    assert delivery is not None
    artifact = tmp_path / "outboxes" / "codex_composer" / "packet-1-domain-reply.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text('{"semantic_reply_claim": true}\n', encoding="utf-8")
    pending_path = (
        tmp_path
        / "state"
        / responder.PENDING_PUBLISH_DIRNAME
        / f"{delivery.delivery_id}.json"
    )
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text(
        json.dumps(
            {
                "schema_version": responder.SCHEMA_VERSION,
                "timestamp": "2026-07-05T03:38:58Z",
                "delivery_id": delivery.delivery_id,
                "packet_id": delivery.packet_id,
                "reply_subject": delivery.reply_subject,
                "delivery_record_path": str(delivery.path),
                "domain_reply_artifact_path": str(artifact),
                "semantic_receipt_path": str(tmp_path / "semantic.json"),
                "semantic_receipt_id": "semantic-legacy",
                "semantic_reply_claim": True,
                "drain_receipt": {
                    "domain_reply_artifact_path": str(artifact),
                    "semantic_reply_claim": True,
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    first = responder.quarantine_packet(
        inbox_dir=tmp_path / "inbox",
        state_dir=tmp_path / "state",
        agent_uid="codex_composer",
        packet_id="packet-1",
        reason="historic unbounded retry incident",
        lease_ttl_s=0,
    )
    second = responder.quarantine_packet(
        inbox_dir=tmp_path / "inbox",
        state_dir=tmp_path / "state",
        agent_uid="codex_composer",
        packet_id="packet-1",
        reason="historic unbounded retry incident",
        lease_ttl_s=0,
    )

    assert first["terminal_effect_created"] is True
    assert second["terminal_effect_created"] is False
    assert artifact.is_file()
    assert not pending_path.exists()
    assert len(
        list((tmp_path / "state" / responder.DEAD_LETTER_DIRNAME).glob("*.json"))
    ) == 1
    processed_lines = (
        tmp_path / "state" / responder.PROCESSED_FILENAME
    ).read_text(encoding="utf-8").splitlines()
    assert len(processed_lines) == 1


def test_missing_mainline_projection_is_reported_not_claimed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(responder, "CANONICAL_PROJECTION_AVAILABLE", False)

    heartbeat = responder.write_responder_heartbeat(
        tmp_path / "state",
        agent_uid="codex_composer",
        provider="test",
        model="test",
        loop_status=responder.NO_PENDING_DELIVERIES_STATUS,
        pending_delivery_count=0,
        project_canonical_state=True,
    )

    assert heartbeat["canonical_projection_status"] == "UNAVAILABLE_ON_CHECKOUT"
    assert heartbeat["canonical_state_path"] == ""
