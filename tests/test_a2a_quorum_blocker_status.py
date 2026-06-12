from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.runtime import a2a_quorum_blocker_status


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _evidence_path(root: Path) -> Path:
    return _write_json(root / "evidence" / "receipt.json", {"status": "ok"})


def _reviewer(
    record_dir: Path,
    name: str,
    *,
    agent_id: str,
    blockers: list[str],
    readiness_percent: int = 62,
) -> None:
    _write_json(
        record_dir / name,
        {
            "schema_version": "dharma.a2a.prod_readiness_reviewer.v1",
            "agent_id": agent_id,
            "model_family": "openai",
            "role": "ops_verifier",
            "readiness_percent": readiness_percent,
            "verdict": "not_ready",
            "red_blockers": blockers,
            "evidence_refs": [str(_evidence_path(record_dir))],
            "created_at": "2026-06-13T00:00:00+00:00",
        },
    )


def _base_inputs(tmp_path: Path) -> dict[str, Path]:
    record_dir = tmp_path / "records"
    quorum = _write_json(
        tmp_path / "latest.json",
        {
            "status": "NOT_READY",
            "agent_ids": ["codex_composer", "gemini_reviewer", "qwen_code"],
            "model_families": ["alibaba", "google", "openai"],
            "readiness_percent_median": 62,
            "red_blocker_records": ["codex_composer"],
        },
    )
    delivery = _write_json(
        tmp_path / "latest_delivery_status.json",
        {
            "status": "PENDING_REVIEWER_RECORDS",
            "summary": {
                "pending_delivery_targets": [],
            },
            "targets": [
                {
                    "target_agent_id": "fable_composer",
                    "reviewer_record_present": False,
                    "delivery_status": "CONSUMER_EMPTY_NO_DELIVERY",
                },
                {
                    "target_agent_id": "hermes_m5",
                    "reviewer_record_present": False,
                    "delivery_status": "CONSUMER_EMPTY_NO_DELIVERY",
                },
            ],
        },
    )
    repair = _write_json(
        tmp_path / "repair.json",
        {
            "status": "READY_TO_MUTATE",
            "missing_reviewer_records": [
                {"target_agent_id": "fable_composer"},
                {"target_agent_id": "hermes_m5"},
            ],
        },
    )
    file_bus = _write_json(tmp_path / "file_bus.json", {"status": "PASS"})
    hermes = _write_json(tmp_path / "hermes.json", {"broadcast_disabled": True})
    return {
        "record_dir": record_dir,
        "quorum_path": quorum,
        "delivery_status_path": delivery,
        "repair_plan_path": repair,
        "file_bus_guard_path": file_bus,
        "hermes_guard_path": hermes,
    }


def _build(paths: dict[str, Path]) -> dict[str, Any]:
    return a2a_quorum_blocker_status.build_blocker_status(
        **paths,
        created_at="2026-06-13T00:00:00+00:00",
    )


def test_resolved_diversity_and_current_missing_target_records(tmp_path: Path) -> None:
    paths = _base_inputs(tmp_path)
    _reviewer(
        paths["record_dir"],
        "codex.json",
        agent_id="codex_composer",
        blockers=[
            "Only one reviewer record exists; the required two persistent agent IDs and three model families have not reported.",
            "Target-owned Fable and Hermes reviewer records are missing; consumers exist but are empty.",
        ],
    )

    status = _build(paths)

    blockers = status["reviewer_records"][0]["blockers"]
    assert blockers[0]["status"] == "resolved"
    assert blockers[1]["status"] == "current"
    assert status["status"] == "BLOCKED_BY_CURRENT_EVIDENCE"
    assert status["summary"]["resolved_stale_blocker_count"] == 1


def test_pending_delivery_claim_becomes_partially_resolved_when_consumers_empty(
    tmp_path: Path,
) -> None:
    paths = _base_inputs(tmp_path)
    _reviewer(
        paths["record_dir"],
        "qwen.json",
        agent_id="qwen_code",
        blockers=[
            "Fable/Hermes target-owned handler receipts missing and both solicitation messages sit PENDING_DELIVERY in AGNI.",
        ],
    )

    status = _build(paths)

    blocker = status["reviewer_records"][0]["blockers"][0]
    assert blocker["status"] == "partially_resolved"
    assert "old pending/backlog claim is resolved" in blocker["reason"]


def test_hermes_broadcast_blocker_is_resolved_when_guards_are_green(tmp_path: Path) -> None:
    paths = _base_inputs(tmp_path)
    _reviewer(
        paths["record_dir"],
        "qwen.json",
        agent_id="qwen_code",
        blockers=[
            "The out-of-repo Hermes alert-router broadcast source can still repopulate file inboxes.",
        ],
    )

    status = _build(paths)

    blocker = status["reviewer_records"][0]["blockers"][0]
    assert blocker["status"] == "resolved"
    assert status["status"] == "BLOCKED_BY_STALE_REVIEW_RECORDS"


def test_write_receipt_writes_requested_path(tmp_path: Path) -> None:
    payload = {
        "schema_version": "dharma.a2a.quorum_blocker_status.v1",
        "status": "BLOCKED_BY_CURRENT_EVIDENCE",
    }
    output = tmp_path / "receipt.json"

    a2a_quorum_blocker_status.write_receipt(output, payload)

    assert json.loads(output.read_text(encoding="utf-8")) == payload
