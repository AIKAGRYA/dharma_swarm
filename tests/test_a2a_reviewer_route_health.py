from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.runtime import a2a_reviewer_route_health


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _request(record_dir: Path, agent_id: str) -> None:
    _write_json(
        record_dir / "requests" / f"{agent_id}.json",
        {
            "schema_version": "dharma.a2a.prod_readiness_solicitation.v1",
            "target_agent_id": agent_id,
            "requested_role": "adversarial_security_reviewer",
            "model_family_hint": "anthropic",
            "route": "a2a",
        },
    )


def _delivery(path: Path, *targets: dict[str, Any]) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "dharma.a2a.prod_readiness_delivery_status.v1",
            "targets": list(targets),
        },
    )


def _repair(path: Path, *targets: dict[str, Any]) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "dharma.a2a.live_handler_repair_plan.v1",
            "missing_reviewer_records": list(targets),
        },
    )


def _attempt(
    record_dir: Path,
    agent_id: str,
    *,
    failure_class: str | None = None,
    stderr_summary: str = "",
) -> None:
    payload: dict[str, Any] = {
        "schema_version": "dharma.a2a.prod_readiness_reviewer_attempt.v1",
        "agent_id": agent_id,
        "created_at": "2026-06-13T00:00:00Z",
        "status": "FAILED",
        "stderr_summary": stderr_summary,
        "reviewer_record_written": False,
        "production_claim": False,
    }
    if failure_class:
        payload["failure_class"] = failure_class
    _write_json(
        record_dir / "reviewer_attempts" / f"20260613T000000Z-{agent_id}.json",
        payload,
    )


def _build(
    tmp_path: Path,
    *,
    record_dir: Path,
    delivery_path: Path,
    repair_path: Path,
) -> dict[str, Any]:
    return a2a_reviewer_route_health.build_route_health(
        record_dir=record_dir,
        delivery_status_path=delivery_path,
        repair_plan_path=repair_path,
        agents_root=tmp_path / "agents",
        state_root=tmp_path / "state",
        command_lookup=lambda command: f"/bin/{command}"
        if command in {"claude", "hermes"}
        else None,
        created_at="2026-06-13T00:00:00+00:00",
    )


def test_reviewer_record_satisfies_route(tmp_path: Path) -> None:
    record_dir = tmp_path / "records"
    _request(record_dir, "codex_composer")
    _write_json(record_dir / "codex_composer.json", {"agent_id": "codex_composer"})
    delivery_path = _delivery(tmp_path / "delivery.json")
    repair_path = _repair(tmp_path / "repair.json")

    payload = _build(
        tmp_path,
        record_dir=record_dir,
        delivery_path=delivery_path,
        repair_path=repair_path,
    )

    assert payload["status"] == "ALL_REVIEWER_ROUTES_SATISFIED"
    assert payload["routes"][0]["route_classification"] == "REVIEW_RECORD_PRESENT"
    assert payload["production_claim"] is False


def test_provider_credit_blocks_missing_fable_record(tmp_path: Path) -> None:
    record_dir = tmp_path / "records"
    _request(record_dir, "fable_composer")
    _attempt(
        record_dir,
        "fable_composer",
        failure_class="PROVIDER_CREDIT_EXHAUSTED",
        stderr_summary="Credit balance is too low",
    )
    _write_json(
        tmp_path / "agents" / "fable_composer" / "identity.json",
        {
            "agent_uid": "fable_composer",
            "model_route": {"route_status": "session_borne"},
            "wake_loop_active": False,
        },
    )
    delivery_path = _delivery(
        tmp_path / "delivery.json",
        {
            "target_agent_id": "fable_composer",
            "delivery_status": "CONSUMER_EMPTY_NO_DELIVERY",
        },
    )
    repair_path = _repair(
        tmp_path / "repair.json",
        {"target_agent_id": "fable_composer"},
    )

    payload = _build(
        tmp_path,
        record_dir=record_dir,
        delivery_path=delivery_path,
        repair_path=repair_path,
    )

    route = payload["routes"][0]
    assert payload["status"] == "ROUTE_HEALTH_BLOCKED"
    assert route["route_classification"] == "PROVIDER_BLOCKED"
    assert route["blocks_production_quorum"] is True


def test_timeout_inferred_from_attempt_text(tmp_path: Path) -> None:
    record_dir = tmp_path / "records"
    _request(record_dir, "hermes_m5")
    _attempt(record_dir, "hermes_m5", stderr_summary="timed out after 45s")
    delivery_path = _delivery(
        tmp_path / "delivery.json",
        {
            "target_agent_id": "hermes_m5",
            "delivery_status": "CONSUMER_EMPTY_NO_DELIVERY",
        },
    )
    repair_path = _repair(
        tmp_path / "repair.json",
        {"target_agent_id": "hermes_m5"},
    )

    payload = _build(
        tmp_path,
        record_dir=record_dir,
        delivery_path=delivery_path,
        repair_path=repair_path,
    )

    route = payload["routes"][0]
    assert route["route_classification"] == "PROVIDER_TIMEOUT_OR_HANDLER_STALLED"
    assert route["latest_attempt"]["failure_class"] == "PROVIDER_TIMEOUT"


def test_write_receipt_writes_json(tmp_path: Path) -> None:
    payload = {
        "schema_version": "dharma.a2a.reviewer_route_health.v1",
        "status": "ROUTE_HEALTH_BLOCKED",
    }
    path = tmp_path / "receipt.json"

    a2a_reviewer_route_health.write_receipt(path, payload)

    assert json.loads(path.read_text(encoding="utf-8")) == payload
