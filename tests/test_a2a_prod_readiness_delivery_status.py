from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.runtime import a2a_prod_readiness_delivery_status


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_request(record_dir: Path, agent_id: str) -> None:
    _write_json(
        record_dir / "requests" / f"{agent_id}.json",
        {
            "schema_version": "dharma.a2a.prod_readiness_solicitation.v1",
            "target_agent_id": agent_id,
            "requested_role": "adversarial_security_reviewer",
            "model_family_hint": "anthropic",
        },
    )


def _write_send_receipt(
    record_dir: Path,
    *,
    agent_id: str,
    consumer: str,
    subject: str = "dharma.a2a.fable_composer",
) -> None:
    _write_json(
        record_dir / f"{agent_id.upper()}_SOLICITATION_NATS_SEND.json",
        {
            "schema_version": "dharma.a2a.prod_readiness_solicitation_send_receipt.v1",
            "created_at": "2026-06-13T00:00:00+00:00",
            "status": "PUBLISH_ACKED",
            "ack_tier": "PUBLISH_ACCEPTED",
            "target_agent_id": agent_id,
            "subject": subject,
            "consumer_witness": {
                "consumer": consumer,
                "filter_subject": subject,
                "unprocessed_messages_after_send": 1,
            },
        },
    )


def _write_governed_send_receipt(
    record_dir: Path,
    *,
    target_uid: str,
    request_agent_id: str | None = None,
    subject: str = "dharma.a2a.fable_composer",
    timestamp: str = "2026-06-13T00:01:00Z",
) -> Path:
    request_file = (
        f"reports/a2a/prod_readiness_quorum/2026-06-13/requests/{request_agent_id}.json"
        if request_agent_id
        else ""
    )
    path = record_dir / "send_receipts" / f"20260613T000100Z-{target_uid}-abc123.json"
    _write_json(
        path,
        {
            "schema_version": "dharma.a2a.send_receipt.v1",
            "timestamp": timestamp,
            "status": "PUBLISH_ACKED",
            "ack_tier": "PUBLISH_ACCEPTED",
            "subject": subject,
            "target_uid": target_uid,
            "to": target_uid,
            "file": request_file,
            "transport_ack": "NATS_CONTEXT_CLI_JETSTREAM_PUB_ACK",
        },
    )
    return path


def _write_reviewer_record(record_dir: Path, agent_id: str) -> None:
    _write_json(
        record_dir / f"{agent_id}.json",
        {
            "schema_version": "dharma.a2a.prod_readiness_reviewer.v1",
            "agent_id": agent_id,
            "model_family": "anthropic",
            "role": "adversarial_security_reviewer",
            "readiness_percent": 82,
            "verdict": "not_ready",
            "red_blockers": [],
            "evidence_refs": ["reports/a2a/nats_reset/2026-06-13/AFTER.json"],
            "created_at": "2026-06-13T00:00:00+00:00",
        },
    )


def _runner_with_consumer_info(payload: dict[str, Any]):
    def run(
        command: list[str],
        *,
        capture_output: bool,
        text: bool,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        assert command[:4] == ["nats", "--context", "agni-wss", "--timeout=30s"]
        assert capture_output is True
        assert text is True
        assert timeout == 35
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    return run


def test_live_probe_marks_pending_delivery(tmp_path: Path) -> None:
    record_dir = tmp_path / "2026-06-13"
    _write_request(record_dir, "fable_composer")
    _write_send_receipt(
        record_dir,
        agent_id="fable_composer",
        consumer="fable_composer_inbox",
    )

    status = a2a_prod_readiness_delivery_status.build_delivery_status(
        root=tmp_path,
        date="2026-06-13",
        probe_live=True,
        runner=_runner_with_consumer_info(
            {
                "name": "fable_composer_inbox",
                "config": {
                    "ack_policy": "explicit",
                    "deliver_policy": "new",
                    "filter_subject": "dharma.a2a.fable_composer",
                    "max_deliver": 5,
                },
                "delivered": {"consumer_seq": 0, "stream_seq": 8106912},
                "ack_floor": {"consumer_seq": 0, "stream_seq": 0},
                "num_pending": 2,
                "num_ack_pending": 0,
                "num_redelivered": 0,
                "num_waiting": 0,
            }
        ),
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert status["status"] == "PENDING_REVIEWER_RECORDS"
    assert status["summary"]["pending_delivery_targets"] == ["fable_composer"]
    assert status["targets"][0]["delivery_status"] == "PENDING_DELIVERY"
    assert status["targets"][0]["consumer_info"]["num_pending"] == 2
    assert status["production_claim"] is False


def test_nested_governed_send_receipt_aliases_to_requested_target(tmp_path: Path) -> None:
    record_dir = tmp_path / "2026-06-13"
    _write_request(record_dir, "hermes_m5")
    nested_path = _write_governed_send_receipt(
        record_dir,
        target_uid="hermes",
        request_agent_id="hermes_m5",
        subject="dharma.a2a.hermes",
    )

    status = a2a_prod_readiness_delivery_status.build_delivery_status(
        root=tmp_path,
        date="2026-06-13",
        probe_live=False,
        created_at="2026-06-13T00:00:00+00:00",
    )

    target = status["targets"][0]
    assert target["target_agent_id"] == "hermes_m5"
    assert target["send_receipt_count"] == 1
    assert target["latest_send_receipt_path"] == str(nested_path)
    assert target["delivery_status"] == "NO_CONSUMER_WITNESS"


def test_latest_governed_receipt_can_use_legacy_consumer_witness(tmp_path: Path) -> None:
    record_dir = tmp_path / "2026-06-13"
    _write_request(record_dir, "fable_composer")
    _write_send_receipt(
        record_dir,
        agent_id="fable_composer",
        consumer="fable_composer_inbox",
    )
    nested_path = _write_governed_send_receipt(
        record_dir,
        target_uid="fable_composer",
        request_agent_id="fable_composer",
    )

    status = a2a_prod_readiness_delivery_status.build_delivery_status(
        root=tmp_path,
        date="2026-06-13",
        probe_live=True,
        runner=_runner_with_consumer_info(
            {
                "name": "fable_composer_inbox",
                "config": {
                    "ack_policy": "explicit",
                    "deliver_policy": "new",
                    "filter_subject": "dharma.a2a.fable_composer",
                    "max_deliver": 5,
                },
                "delivered": {"consumer_seq": 0, "stream_seq": 8106912},
                "ack_floor": {"consumer_seq": 0, "stream_seq": 0},
                "num_pending": 2,
                "num_ack_pending": 0,
                "num_redelivered": 0,
                "num_waiting": 0,
            }
        ),
        created_at="2026-06-13T00:00:00+00:00",
    )

    target = status["targets"][0]
    assert target["send_receipt_count"] == 2
    assert target["latest_send_receipt_path"] == str(nested_path)
    assert target["consumer_witness_receipt_path"].endswith("FABLE_COMPOSER_SOLICITATION_NATS_SEND.json")
    assert target["delivery_status"] == "PENDING_DELIVERY"


def test_reviewer_record_satisfies_target_without_live_probe(tmp_path: Path) -> None:
    record_dir = tmp_path / "2026-06-13"
    _write_request(record_dir, "fable_composer")
    _write_send_receipt(
        record_dir,
        agent_id="fable_composer",
        consumer="fable_composer_inbox",
    )
    _write_reviewer_record(record_dir, "fable_composer")

    status = a2a_prod_readiness_delivery_status.build_delivery_status(
        root=tmp_path,
        date="2026-06-13",
        probe_live=False,
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert status["status"] == "ALL_REVIEW_RECORDS_PRESENT"
    assert status["summary"]["reviewer_records_missing"] == 0
    assert status["targets"][0]["delivery_status"] == "REVIEW_RECORD_PRESENT"
    assert status["targets"][0]["next_required_receipt"] is None


def test_publish_without_live_probe_is_not_delivery_verified(tmp_path: Path) -> None:
    record_dir = tmp_path / "2026-06-13"
    _write_request(record_dir, "hermes_m5")
    _write_send_receipt(
        record_dir,
        agent_id="hermes_m5",
        consumer="claude_from_hermes",
        subject="dharma.a2a.hermes",
    )

    status = a2a_prod_readiness_delivery_status.build_delivery_status(
        root=tmp_path,
        date="2026-06-13",
        probe_live=False,
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert status["targets"][0]["delivery_status"] == "PUBLISH_ACCEPTED_NOT_DELIVERY_VERIFIED"
    assert status["targets"][0]["next_required_receipt"].endswith("hermes_m5.json")


def test_write_status_writes_daily_and_latest_receipts(tmp_path: Path) -> None:
    payload = {
        "schema_version": "dharma.a2a.prod_readiness_delivery_status.v1",
        "record_dir": str(tmp_path / "2026-06-13"),
        "summary": {},
    }

    output = a2a_prod_readiness_delivery_status.write_status(
        tmp_path,
        payload,
        write_latest=True,
    )

    assert output == tmp_path / "2026-06-13" / "QUORUM_DELIVERY_STATUS.json"
    assert output.exists()
    assert (tmp_path / "latest_delivery_status.json").exists()
