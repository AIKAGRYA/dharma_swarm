from __future__ import annotations

import json
from pathlib import Path

from scripts.runtime import a2a_live_handler_repair_plan


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_plan_reports_daemon_and_delivery_gaps(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.json"
    delivery_path = tmp_path / "delivery.json"
    _write_json(
        audit_path,
        {
            "schema_version": "dharma.a2a.daemon_wiring_audit.v1",
            "status": "FAIL",
            "candidates": [
                {
                    "label": "com.dhyana.nats-a2a-bridge",
                    "status": "FAIL",
                    "path": "/tmp/com.dhyana.nats-a2a-bridge.plist",
                    "working_directory": "/tmp/repo",
                    "program_arguments": ["/usr/bin/python3", "-m", "missing.module"],
                    "issues": [
                        {"type": "missing_module_target"},
                        {"type": "broker_scope_mismatch"},
                    ],
                },
                {
                    "label": "com.dhyana.nats",
                    "status": "PASS",
                    "issues": [],
                },
            ],
        },
    )
    _write_json(
        delivery_path,
        {
            "schema_version": "dharma.a2a.prod_readiness_delivery_status.v1",
            "status": "PENDING_REVIEWER_RECORDS",
            "targets": [
                {
                    "target_agent_id": "codex_composer",
                    "delivery_status": "REVIEW_RECORD_PRESENT",
                },
                {
                    "target_agent_id": "fable_composer",
                    "subject": "dharma.a2a.fable_composer",
                    "consumer": "fable_composer_inbox",
                    "delivery_status": "PENDING_DELIVERY",
                    "consumer_info": {"num_pending": 2, "num_ack_pending": 0},
                    "next_required_receipt": "/tmp/fable.json",
                },
            ],
        },
    )

    plan = a2a_live_handler_repair_plan.build_plan(
        audit_path=audit_path,
        delivery_status_path=delivery_path,
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert plan["status"] == "REPAIR_REQUIRED"
    assert plan["production_claim"] is False
    assert plan["summary"]["failing_daemon_count"] == 1
    assert plan["summary"]["delivery_gap_count"] == 1
    assert plan["summary"]["daemon_issue_counts"] == {
        "broker_scope_mismatch": 1,
        "missing_module_target": 1,
    }
    assert plan["delivery_gaps"][0]["target_agent_id"] == "fable_composer"
    assert "PUBLISH_ACCEPTED is not live contact." in plan["delivery_gaps"][0]["must_not_claim"]


def test_build_plan_ready_only_when_no_gaps(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.json"
    delivery_path = tmp_path / "delivery.json"
    _write_json(
        audit_path,
        {
            "schema_version": "dharma.a2a.daemon_wiring_audit.v1",
            "status": "PASS",
            "candidates": [{"label": "com.dhyana.nats", "status": "PASS", "issues": []}],
        },
    )
    _write_json(
        delivery_path,
        {
            "schema_version": "dharma.a2a.prod_readiness_delivery_status.v1",
            "status": "READY",
            "targets": [
                {
                    "target_agent_id": "codex_composer",
                    "delivery_status": "REVIEW_RECORD_PRESENT",
                }
            ],
        },
    )

    plan = a2a_live_handler_repair_plan.build_plan(
        audit_path=audit_path,
        delivery_status_path=delivery_path,
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert plan["status"] == "READY_TO_MUTATE"
    assert plan["summary"]["failing_daemon_count"] == 0
    assert plan["summary"]["delivery_gap_count"] == 0


def test_empty_consumer_without_reviewer_record_is_ready_to_mutate_not_prod_ready(
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "audit.json"
    delivery_path = tmp_path / "delivery.json"
    _write_json(
        audit_path,
        {
            "schema_version": "dharma.a2a.daemon_wiring_audit.v1",
            "status": "PASS",
            "candidates": [{"label": "com.dhyana.nats", "status": "PASS", "issues": []}],
        },
    )
    _write_json(
        delivery_path,
        {
            "schema_version": "dharma.a2a.prod_readiness_delivery_status.v1",
            "status": "PENDING_REVIEWER_RECORDS",
            "targets": [
                {
                    "target_agent_id": "fable_composer",
                    "subject": "dharma.a2a.fable_composer",
                    "consumer": "fable_composer_inbox",
                    "delivery_status": "CONSUMER_EMPTY_NO_DELIVERY",
                    "consumer_info": {"num_pending": 0, "num_ack_pending": 0},
                    "next_required_receipt": "/tmp/fable.json",
                }
            ],
        },
    )

    plan = a2a_live_handler_repair_plan.build_plan(
        audit_path=audit_path,
        delivery_status_path=delivery_path,
        created_at="2026-06-13T00:00:00+00:00",
    )

    assert plan["status"] == "READY_TO_MUTATE"
    assert plan["production_claim"] is False
    assert plan["summary"]["delivery_gap_count"] == 0
    assert plan["summary"]["missing_reviewer_record_count"] == 1
    assert plan["missing_reviewer_records"][0]["blocks_production_quorum"] is True
    assert "READY_TO_MUTATE is not production readiness." in plan["missing_reviewer_records"][0][
        "must_not_claim"
    ]


def test_write_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    payload = {"schema_version": a2a_live_handler_repair_plan.SCHEMA_VERSION}

    a2a_live_handler_repair_plan.write_receipt(receipt_path, payload)

    assert json.loads(receipt_path.read_text(encoding="utf-8")) == payload
