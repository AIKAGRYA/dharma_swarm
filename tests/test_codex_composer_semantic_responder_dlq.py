from __future__ import annotations

import json
import multiprocessing
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import scripts.runtime.codex_composer_semantic_inbox_drain as semantic_drain
import scripts.runtime.codex_composer_semantic_responder as responder
from dharma_swarm.models import ProviderType


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
    no_publish: bool = False,
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
        no_publish=no_publish,
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


def _lease_holder(
    state_dir: str,
    commands: Any,
    events: Any,
) -> None:
    lease = responder.acquire_lease(Path(state_dir), "delivery-1", ttl_s=0)
    events.put("acquired" if lease is not None else "failed")
    while True:
        command = commands.get(timeout=10)
        if command == "release":
            responder.release_lease(lease)
            events.put("released")
        elif command == "release-again":
            responder.release_lease(lease)
            events.put("released-again")
        elif command == "stop":
            return


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


def test_publish_exception_terminalizes_unknown_and_preserves_artifact(
    tmp_path: Path,
) -> None:
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

    assert first[0]["status"] == responder.PUBLISH_OUTCOME_UNKNOWN_STATUS
    assert second == []
    assert "NATS unavailable" in first[0]["error"]
    assert drain_calls["count"] == 1
    assert publish_calls["count"] == 1
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


def test_operator_quarantine_classifies_invalid_legacy_pin_exactly_once(
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

    assert first["status"] == responder.PENDING_PUBLISH_INVALID_STATUS
    assert second["status"] == responder.PENDING_PUBLISH_INVALID_STATUS
    assert first["terminal_effect_created"] is True
    assert second["terminal_effect_created"] is False
    assert artifact.is_file()
    assert pending_path.exists()
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


def test_dead_letters_are_classified_before_generic_processed_status() -> None:
    for status in responder.DEAD_LETTER_STATUSES:
        assert responder._responder_runtime_status(status) == "dead_lettered"
        assert responder._canonical_status_for_loop(status).endswith("_dead_lettered")


def test_same_second_responder_receipts_never_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(responder, "stamp", lambda: "20260723T000000Z")
    first = {"status": "TEST_STATUS", "packet_id": "packet-1", "attempt": 1}
    second = {"status": "TEST_STATUS", "packet_id": "packet-1", "attempt": 2}

    first_path = responder.write_responder_receipt(tmp_path / "state", first)
    first_bytes = first_path.read_bytes()
    second_path = responder.write_responder_receipt(tmp_path / "state", second)

    assert first_path != second_path
    assert first_path.read_bytes() == first_bytes
    assert json.loads(first_path.read_text(encoding="utf-8"))["attempt"] == 1
    assert json.loads(second_path.read_text(encoding="utf-8"))["attempt"] == 2


def test_no_publish_preserves_existing_pin_without_model_or_publisher(
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
    assert first[0]["status"] == responder.PENDING_PUBLISH_STATUS
    pinned_bytes = artifact.read_bytes()

    def no_second_model(**_: Any) -> dict[str, Any]:
        raise AssertionError("--no-publish must not rerun a pinned model result")

    second = _run_once(
        tmp_path,
        drain_func=no_second_model,
        publish_func=_unexpected_publish,
        max_publish_attempts=3,
        no_publish=True,
    )

    assert second[0]["status"] == responder.PENDING_PUBLISH_STATUS
    assert second[0]["publish_attempt_count"] == 1
    assert drain_calls["count"] == 1
    assert artifact.is_file()
    assert artifact.read_bytes() == pinned_bytes
    assert len(
        list(
            (tmp_path / "state" / responder.PENDING_PUBLISH_DIRNAME).glob(
                "*.json"
            )
        )
    ) == 1
    assert not (tmp_path / "state" / responder.PROCESSED_FILENAME).exists()


def test_corrupt_pending_state_fails_closed_under_no_publish(
    tmp_path: Path,
) -> None:
    _delivery_record(tmp_path)
    drain, drain_calls, _ = _semantic_drain(tmp_path)
    first = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=_unexpected_publish,
        max_publish_attempts=3,
    )
    assert first[0]["status"] == responder.PENDING_PUBLISH_STATUS
    pending_path = next(
        (tmp_path / "state" / responder.PENDING_PUBLISH_DIRNAME).glob("*.json")
    )
    pending_path.write_text("{not-json", encoding="utf-8")
    calls = {"model": 0, "publish": 0}

    def model(**_: Any) -> dict[str, Any]:
        calls["model"] += 1
        raise AssertionError("invalid recovery state must block the model")

    def publisher(**_: Any) -> dict[str, Any]:
        calls["publish"] += 1
        raise AssertionError("invalid recovery state must block the publisher")

    second = _run_once(
        tmp_path,
        drain_func=model,
        publish_func=publisher,
        max_publish_attempts=3,
        no_publish=True,
    )

    assert second[0]["status"] == responder.PENDING_PUBLISH_INVALID_STATUS
    assert second[0]["semantic_reply_claim"] is False
    assert second[0]["semantic_success_pinned"] is False
    assert calls == {"model": 0, "publish": 0}
    assert drain_calls["count"] == 1

    (tmp_path / "state" / responder.PROCESSED_FILENAME).unlink()
    replay = _run_once(
        tmp_path,
        drain_func=model,
        publish_func=publisher,
        max_publish_attempts=3,
    )
    assert replay[0]["status"] == responder.PENDING_PUBLISH_INVALID_STATUS
    assert replay[0]["semantic_success_pinned"] is False
    assert replay[0]["terminal_effect_reused"] is True
    assert calls == {"model": 0, "publish": 0}


def test_original_artifact_replacement_cannot_change_pinned_publish(
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
    assert first[0]["status"] == responder.PENDING_PUBLISH_STATUS
    pending_path = next(
        (tmp_path / "state" / responder.PENDING_PUBLISH_DIRNAME).glob("*.json")
    )
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    pinned_path = Path(pending["domain_reply_artifact_path"])
    pinned_bytes = pinned_path.read_bytes()
    assert len(pending["domain_reply_artifact_sha256"]) == 64
    assert pinned_path != artifact

    artifact.write_text('{"changed": true}\n', encoding="utf-8")
    _send_receipt(tmp_path)
    published: dict[str, Any] = {}

    def publisher(**kwargs: Any) -> dict[str, Any]:
        published["path"] = kwargs["reply_artifact_path"]
        published["bytes"] = kwargs["reply_artifact_path"].read_bytes()
        published["sha256"] = kwargs["expected_artifact_sha256"]
        return {
            "status": "DOMAIN_REPLY_PUBLISHED",
            "domain_receipt_claim": True,
        }

    second = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=publisher,
        max_publish_attempts=3,
    )

    assert second[0]["status"] == "DOMAIN_REPLY_PUBLISHED"
    assert drain_calls["count"] == 1
    assert published["path"] == pinned_path
    assert published["bytes"] == pinned_bytes
    assert published["sha256"] == pending["domain_reply_artifact_sha256"]


def test_pinned_artifact_hash_mismatch_terminalizes_without_replay(
    tmp_path: Path,
) -> None:
    _delivery_record(tmp_path)
    drain, drain_calls, _ = _semantic_drain(tmp_path)
    first = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=_unexpected_publish,
        max_publish_attempts=3,
    )
    assert first[0]["status"] == responder.PENDING_PUBLISH_STATUS
    pending_path = next(
        (tmp_path / "state" / responder.PENDING_PUBLISH_DIRNAME).glob("*.json")
    )
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    pinned_path = Path(pending["domain_reply_artifact_path"])
    replacement = pinned_path.with_name(f".{pinned_path.name}.replacement")
    replacement.write_text('{"changed": true}\n', encoding="utf-8")
    replacement.replace(pinned_path)
    _send_receipt(tmp_path)
    calls = {"model": 0, "publish": 0}

    def no_model(**_: Any) -> dict[str, Any]:
        calls["model"] += 1
        raise AssertionError("hash mismatch must block the model")

    def no_publish(**_: Any) -> dict[str, Any]:
        calls["publish"] += 1
        raise AssertionError("hash mismatch must block the publisher")

    second = _run_once(
        tmp_path,
        drain_func=no_model,
        publish_func=no_publish,
        max_publish_attempts=3,
    )

    assert second[0]["status"] == responder.PENDING_PUBLISH_INVALID_STATUS
    assert "SHA-256 mismatch" in second[0]["error"]
    assert calls == {"model": 0, "publish": 0}
    assert drain_calls["count"] == 1


def test_atomic_pending_replace_failure_preserves_previous_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _delivery_record(tmp_path)
    drain, _, _ = _semantic_drain(tmp_path)
    first = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=_unexpected_publish,
        max_publish_attempts=3,
    )
    assert first[0]["status"] == responder.PENDING_PUBLISH_STATUS
    pending_path = next(
        (tmp_path / "state" / responder.PENDING_PUBLISH_DIRNAME).glob("*.json")
    )
    original_bytes = pending_path.read_bytes()
    real_replace = responder.os.replace

    def fail_pending_replace(source: Any, target: Any) -> None:
        if Path(target) == pending_path:
            raise OSError("simulated atomic replacement failure")
        real_replace(source, target)

    monkeypatch.setattr(responder.os, "replace", fail_pending_replace)
    second = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=_unexpected_publish,
        max_publish_attempts=3,
    )

    assert second[0]["status"] == responder.PENDING_PUBLISH_INVALID_STATUS
    assert pending_path.read_bytes() == original_bytes
    assert isinstance(
        json.loads(pending_path.read_text(encoding="utf-8")),
        dict,
    )


def test_publish_crash_after_effect_is_never_replayed(
    tmp_path: Path,
) -> None:
    _delivery_record(tmp_path)
    _send_receipt(tmp_path)
    drain, drain_calls, artifact = _semantic_drain(tmp_path)
    effects: list[str] = []

    def crash_after_effect(**_: Any) -> dict[str, Any]:
        effects.append("external-effect")
        raise SystemExit("simulated process death")

    with pytest.raises(SystemExit, match="simulated process death"):
        _run_once(
            tmp_path,
            drain_func=drain,
            publish_func=crash_after_effect,
            max_publish_attempts=3,
        )

    def no_replay(**_: Any) -> dict[str, Any]:
        raise AssertionError("restart must not repeat model or publisher")

    replay = _run_once(
        tmp_path,
        drain_func=no_replay,
        publish_func=no_replay,
        max_publish_attempts=3,
    )

    assert replay[0]["status"] == responder.PUBLISH_OUTCOME_UNKNOWN_STATUS
    assert replay[0]["terminal_effect_created"] is True
    assert effects == ["external-effect"]
    assert drain_calls["count"] == 1
    assert artifact.is_file()
    assert len(
        list(
            (tmp_path / "state" / responder.PUBLISH_IN_FLIGHT_DIRNAME).glob(
                "*.json"
            )
        )
    ) == 1
    assert len(
        list((tmp_path / "state" / responder.DEAD_LETTER_DIRNAME).glob("*.json"))
    ) == 1
    assert _run_once(
        tmp_path,
        drain_func=no_replay,
        publish_func=no_replay,
        max_publish_attempts=3,
    ) == []


def test_quarantine_preserves_unknown_outcome_after_publish_crash(
    tmp_path: Path,
) -> None:
    _delivery_record(tmp_path)
    _send_receipt(tmp_path)
    drain, drain_calls, _ = _semantic_drain(tmp_path)
    effects: list[str] = []

    def crash_after_effect(**_: Any) -> dict[str, Any]:
        effects.append("external-effect")
        raise SystemExit("simulated process death")

    with pytest.raises(SystemExit, match="simulated process death"):
        _run_once(
            tmp_path,
            drain_func=drain,
            publish_func=crash_after_effect,
            max_publish_attempts=3,
        )

    first = responder.quarantine_packet(
        inbox_dir=tmp_path / "inbox",
        state_dir=tmp_path / "state",
        agent_uid="codex_composer",
        packet_id="packet-1",
        reason="operator containment after responder crash",
        lease_ttl_s=0,
    )
    second = responder.quarantine_packet(
        inbox_dir=tmp_path / "inbox",
        state_dir=tmp_path / "state",
        agent_uid="codex_composer",
        packet_id="packet-1",
        reason="operator containment after responder crash",
        lease_ttl_s=0,
    )

    assert first["status"] == responder.PUBLISH_OUTCOME_UNKNOWN_STATUS
    assert second["status"] == responder.PUBLISH_OUTCOME_UNKNOWN_STATUS
    assert first["terminal_effect_created"] is True
    assert second["terminal_effect_created"] is False
    assert effects == ["external-effect"]
    assert drain_calls["count"] == 1
    assert list(
        (tmp_path / "state" / responder.PUBLISH_IN_FLIGHT_DIRNAME).glob("*.json")
    )


def test_success_is_processed_before_recovery_state_is_cleared(
    tmp_path: Path,
) -> None:
    _delivery_record(tmp_path)
    _send_receipt(tmp_path)
    drain, drain_calls, _ = _semantic_drain(tmp_path)
    publish_calls = {"count": 0}

    def published(**_: Any) -> dict[str, Any]:
        publish_calls["count"] += 1
        return {
            "status": "DOMAIN_REPLY_PUBLISHED",
            "domain_receipt_claim": True,
            "receipt_path": str(tmp_path / "domain-receipt.json"),
        }

    first = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=published,
        max_publish_attempts=3,
    )
    second = _run_once(
        tmp_path,
        drain_func=drain,
        publish_func=published,
        max_publish_attempts=3,
    )

    assert first[0]["status"] == "DOMAIN_REPLY_PUBLISHED"
    assert second == []
    assert drain_calls["count"] == 1
    assert publish_calls["count"] == 1
    processed = (
        tmp_path / "state" / responder.PROCESSED_FILENAME
    ).read_text(encoding="utf-8")
    assert "DOMAIN_REPLY_PUBLISHED" in processed
    assert list(
        (tmp_path / "state" / responder.PENDING_PUBLISH_DIRNAME).glob("*.json")
    ) == []
    assert list(
        (tmp_path / "state" / responder.PUBLISH_IN_FLIGHT_DIRNAME).glob(
            "*.json"
        )
    ) == []


def test_corrupt_in_flight_marker_fails_closed_without_replay(
    tmp_path: Path,
) -> None:
    delivery_path = _delivery_record(tmp_path)
    delivery = responder.delivery_from_path(
        delivery_path,
        agent_uid="codex_composer",
    )
    assert delivery is not None
    marker = (
        tmp_path
        / "state"
        / responder.PUBLISH_IN_FLIGHT_DIRNAME
        / f"{delivery.delivery_id}.json"
    )
    marker.parent.mkdir(parents=True)
    marker.write_text("{not-json", encoding="utf-8")

    def no_replay(**_: Any) -> dict[str, Any]:
        raise AssertionError("corrupt write-ahead marker must block all replay")

    receipt = _run_once(
        tmp_path,
        drain_func=no_replay,
        publish_func=no_replay,
        max_publish_attempts=3,
    )

    assert receipt[0]["status"] == responder.PUBLISH_OUTCOME_UNKNOWN_STATUS
    assert len(
        list((tmp_path / "state" / responder.DEAD_LETTER_DIRNAME).glob("*.json"))
    ) == 1


def test_typed_semantic_failure_terminalizes_without_publication(
    tmp_path: Path,
) -> None:
    _delivery_record(tmp_path)
    _send_receipt(tmp_path)
    calls = {"drain": 0, "publish": 0}

    def typed_failure(**_: Any) -> dict[str, Any]:
        calls["drain"] += 1
        return {
            "status": "SEMANTIC_INBOX_DRAIN_TYPED_FAILURE",
            "packet_id": "packet-1",
            "domain_reply_artifact_path": str(tmp_path / "typed-failure.json"),
            "semantic_receipt_path": str(tmp_path / "semantic-failure.json"),
            "semantic_receipt_id": "semantic-failure-1",
            "semantic_reply_claim": False,
        }

    def publisher(**_: Any) -> dict[str, Any]:
        calls["publish"] += 1
        raise AssertionError("typed semantic failure must never publish")

    first = _run_once(
        tmp_path,
        drain_func=typed_failure,
        publish_func=publisher,
        max_publish_attempts=3,
    )
    (tmp_path / "state" / responder.PROCESSED_FILENAME).unlink()

    def no_replay(**_: Any) -> dict[str, Any]:
        raise AssertionError("typed dead letter must suppress all replay")

    replay = _run_once(
        tmp_path,
        drain_func=no_replay,
        publish_func=no_replay,
        max_publish_attempts=3,
    )
    second = _run_once(
        tmp_path,
        drain_func=no_replay,
        publish_func=no_replay,
        max_publish_attempts=3,
    )

    assert first[0]["status"] == responder.SEMANTIC_DRAIN_TYPED_FAILURE_STATUS
    assert replay[0]["status"] == responder.SEMANTIC_DRAIN_TYPED_FAILURE_STATUS
    assert replay[0]["terminal_effect_reused"] is True
    assert second == []
    assert calls == {"drain": 1, "publish": 0}
    assert len(
        list((tmp_path / "state" / responder.DEAD_LETTER_DIRNAME).glob("*.json"))
    ) == 1
    processed = (
        tmp_path / "state" / responder.PROCESSED_FILENAME
    ).read_text(encoding="utf-8")
    assert responder.SEMANTIC_DRAIN_TYPED_FAILURE_STATUS in processed


def test_os_lease_cannot_be_stolen_or_released_by_stale_owner(
    tmp_path: Path,
) -> None:
    context = multiprocessing.get_context("spawn")
    commands = context.Queue()
    events = context.Queue()
    process = context.Process(
        target=_lease_holder,
        args=(str(tmp_path / "state"), commands, events),
    )
    process.start()
    try:
        assert events.get(timeout=10) == "acquired"
        assert (
            responder.acquire_lease(
                tmp_path / "state",
                "delivery-1",
                ttl_s=0,
            )
            is None
        )
        commands.put("release")
        assert events.get(timeout=10) == "released"
        new_owner = responder.acquire_lease(
            tmp_path / "state",
            "delivery-1",
            ttl_s=0,
        )
        assert new_owner is not None
        commands.put("release-again")
        assert events.get(timeout=10) == "released-again"
        assert (
            responder.acquire_lease(
                tmp_path / "state",
                "delivery-1",
                ttl_s=0,
            )
            is None
        )
        responder.release_lease(new_owner)
        final_owner = responder.acquire_lease(
            tmp_path / "state",
            "delivery-1",
            ttl_s=0,
        )
        assert final_owner is not None
        responder.release_lease(final_owner)
    finally:
        commands.put("stop")
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    assert process.exitcode == 0


def _install_mock_critic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    calls: dict[str, Any] = {"count": 0}

    def critic(**kwargs: Any) -> dict[str, Any]:
        calls["count"] += 1
        calls["provider"] = kwargs["provider"]
        calls["model"] = kwargs["model"]
        receipt_path = Path(kwargs["out_dir"]) / f"semantic-{calls['count']}.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt = {
            "receipt_id": f"semantic-{calls['count']}",
            "semantic_reply_claim": True,
            "verdict": "approved",
            "summary": "Benign packet processed.",
            "semantic_claim_basis": "mocked executable test",
        }
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return {"receipt": receipt, "artifact_path": str(receipt_path)}

    monkeypatch.setattr(semantic_drain, "run_model_critic", critic)
    monkeypatch.setattr(
        semantic_drain,
        "preferred_runtime_provider_configs",
        lambda *, model, provider_order: (
            calls.update({"provider_order": provider_order})
            or [
                SimpleNamespace(
                    provider=ProviderType.OLLAMA,
                    default_model=model or "qwen-test",
                    available=True,
                )
            ]
        ),
    )
    return calls


def test_default_drain_uses_supported_ollama_and_state_owned_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivery = _delivery_record(tmp_path)
    calls = _install_mock_critic(tmp_path, monkeypatch)
    state_dir = tmp_path / "runtime-state"
    monkeypatch.setattr(semantic_drain, "stamp", lambda: "20260723T000000Z")

    first = semantic_drain.drain_semantic_inbox(
        delivery_record_path=delivery,
        state_dir=state_dir,
    )
    second = semantic_drain.drain_semantic_inbox(
        delivery_record_path=delivery,
        state_dir=state_dir,
    )

    assert calls["provider_order"] == (ProviderType.OLLAMA,)
    assert calls["provider"] == ProviderType.OLLAMA.value
    assert calls["model"] == "qwen-test"
    assert first["semantic_reply_claim"] is True
    for field in (
        "prompt_file",
        "semantic_receipt_path",
        "domain_reply_artifact_path",
        "domain_reply_artifact_author_receipt_path",
        "drain_receipt_path",
    ):
        Path(first[field]).resolve().relative_to(state_dir.resolve())
    assert first["drain_receipt_path"] != second["drain_receipt_path"]
    assert Path(first["drain_receipt_path"]).is_file()
    assert Path(second["drain_receipt_path"]).is_file()


def test_runtime_defaults_are_resolved_from_current_dharma_state_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_root = tmp_path / "dharma-state"
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_root))

    paths = semantic_drain.semantic_responder_runtime_paths(
        agent_uid="codex_composer",
    )

    for path in (
        paths.state_dir,
        paths.outbox_root,
        paths.semantic_receipt_dir,
        paths.artifact_receipt_dir,
        paths.drain_receipt_dir,
        paths.domain_reply_receipt_dir,
    ):
        path.relative_to(state_root.resolve())


def test_unsupported_critic_provider_fails_before_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        semantic_drain,
        "resolve_runtime_provider_config",
        lambda *_args, **_kwargs: pytest.fail(
            "unsupported provider must fail before runtime resolution"
        ),
    )
    with pytest.raises(ValueError, match="not supported by the model critic"):
        semantic_drain._resolve_runtime_critic_defaults(
            provider=ProviderType.NVIDIA_NIM.value,
            model=None,
        )


@pytest.mark.parametrize(
    "packet_id",
    [
        "/tmp/pwn",
        "../../pwn",
        "foo/bar",
        ".",
        "..",
        "white space",
        "a.b",
        "back\\slash",
        "é",
        "a" * 97,
    ],
)
def test_invalid_packet_id_fails_before_prompt_or_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    packet_id: str,
) -> None:
    delivery_path = _delivery_record(tmp_path)
    payload = json.loads(delivery_path.read_text(encoding="utf-8"))
    payload["envelope"]["packet_id"] = packet_id
    delivery_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        semantic_drain,
        "run_model_critic",
        lambda **_kwargs: pytest.fail("invalid packet id reached model critic"),
    )
    state_dir = tmp_path / "state"

    with pytest.raises(ValueError, match="packet_id"):
        semantic_drain.drain_semantic_inbox(
            delivery_record_path=delivery_path,
            state_dir=state_dir,
        )

    assert not (state_dir / "drain_receipts" / "prompts").exists()
