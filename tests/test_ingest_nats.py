from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.operator_core.ingest_nats import publish_ingest_receipts_if_enabled


def test_ingest_nats_flag_off_does_not_probe_or_publish(tmp_path: Path) -> None:
    def fail_probe(**_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("probe must not run when DHARMA_INGEST_NATS is disabled")

    def fail_publisher(**_kwargs: Any) -> list[dict[str, Any]]:
        raise AssertionError("publisher must not run when DHARMA_INGEST_NATS is disabled")

    result = publish_ingest_receipts_if_enabled(
        tmp_path,
        "corr-1",
        env={},
        probe=fail_probe,
        publisher=fail_publisher,
    )

    assert result["enabled"] is False
    assert result["status"] == "disabled"
    assert result["ack_status"] == "unavailable"
    assert result["published_count"] == 0


@pytest.mark.parametrize(
    ("port_open", "expected"),
    [
        (False, "unavailable"),
        (True, "ack_unverified"),
    ],
)
def test_ingest_nats_flag_on_classifies_unverified_ack(
    tmp_path: Path,
    port_open: bool,
    expected: str,
) -> None:
    def probe(**_kwargs: Any) -> dict[str, Any]:
        return {
            "ack_verified": False,
            "port_4222_listening": port_open,
            "endpoint": "nats://fake:4222",
            "reason": "not verified",
        }

    def fail_publisher(**_kwargs: Any) -> list[dict[str, Any]]:
        raise AssertionError("publisher must not run without ack proof")

    result = publish_ingest_receipts_if_enabled(
        tmp_path,
        "corr-1",
        env={"DHARMA_INGEST_NATS": "1"},
        probe=probe,
        publisher=fail_publisher,
    )

    assert result["enabled"] is True
    assert result["status"] == expected
    assert result["ack_status"] == expected
    assert result["publish_status"] == "not_attempted"


def test_ingest_nats_ack_verified_publishes_only_current_run_receipts(tmp_path: Path) -> None:
    receipt_dir = tmp_path / "receipts"
    _write_receipt(receipt_dir, "r1", "corr-live")
    _write_receipt(receipt_dir, "r2", "corr-live")
    _write_receipt(receipt_dir, "other", "corr-other")
    captured: dict[str, Any] = {}

    def probe(**kwargs: Any) -> dict[str, Any]:
        captured["probe_kwargs"] = kwargs
        return {
            "ack_verified": True,
            "port_4222_listening": True,
            "endpoint": "nats://fake:4222",
            "reason": "verified",
        }

    def publisher(**kwargs: Any) -> list[dict[str, Any]]:
        captured["publisher_kwargs"] = kwargs
        payloads = list(kwargs["payloads"])
        return [
            {
                "receipt_id": payload["receipt_id"],
                "ack_tier": "PUBLISH_ACCEPTED",
                "stream": "DHARMA_INGEST_RECEIPTS",
                "seq": index + 1,
            }
            for index, payload in enumerate(payloads)
        ]

    result = publish_ingest_receipts_if_enabled(
        receipt_dir,
        "corr-live",
        env={"DHARMA_INGEST_NATS": "1"},
        probe=probe,
        publisher=publisher,
    )

    assert captured["probe_kwargs"]["verify_ack"] is True
    assert captured["probe_kwargs"]["trust_fresh_receipt"] is True
    assert captured["publisher_kwargs"]["endpoint"] == "nats://fake:4222"
    assert [item["receipt_id"] for item in captured["publisher_kwargs"]["payloads"]] == ["r1", "r2"]
    assert result["status"] == "ack_verified"
    assert result["ack_status"] == "ack_verified"
    assert result["publish_status"] == "published"
    assert result["attempted_count"] == 2
    assert result["published_count"] == 2
    assert result["publish_acks"][0]["ack_tier"] == "PUBLISH_ACCEPTED"


def test_ingest_nats_publish_failure_does_not_claim_publish_success(tmp_path: Path) -> None:
    receipt_dir = tmp_path / "receipts"
    _write_receipt(receipt_dir, "r1", "corr-live")

    def probe(**_kwargs: Any) -> dict[str, Any]:
        return {
            "ack_verified": True,
            "port_4222_listening": True,
            "endpoint": "nats://fake:4222",
            "reason": "verified",
        }

    def publisher(**_kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError("publish failed")

    result = publish_ingest_receipts_if_enabled(
        receipt_dir,
        "corr-live",
        env={"DHARMA_INGEST_NATS": "1"},
        probe=probe,
        publisher=publisher,
    )

    assert result["status"] == "publish_failed"
    assert result["ack_status"] == "ack_verified"
    assert result["publish_status"] == "failed"
    assert result["published_count"] == 0
    assert "publish failed" in result["error"]


def _write_receipt(receipt_dir: Path, receipt_id: str, correlation_id: str) -> None:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    (receipt_dir / f"{receipt_id}.json").write_text(
        json.dumps(
            {
                "receipt_id": receipt_id,
                "correlation_id": correlation_id,
                "schema_version": "go_evidence_receipt.v0",
                "status": "accepted",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
