from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dharma_swarm.holon_service_liveness import (
    assess_service_liveness,
    latest_service_heartbeat,
    record_service_heartbeat,
    service_heartbeat_path,
    verify_service_heartbeat_ledger,
)


def test_service_heartbeat_records_hash_chained_liveness(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"

    first = record_service_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        session_id="s1",
        service_id="test-service",
        status="running",
    )
    second = record_service_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        session_id="s2",
        service_id="test-service",
        status="idle",
    )

    path = service_heartbeat_path("codex_composer", agents_root)
    ok, errors = verify_service_heartbeat_ledger(path)
    liveness = assess_service_liveness("codex_composer", agents_root=agents_root)

    assert ok is True
    assert errors == []
    assert first["previous_record_hash"] == ""
    assert second["previous_record_hash"] == first["record_hash"]
    assert latest_service_heartbeat("codex_composer", agents_root)["session_id"] == "s2"
    assert liveness["heartbeat_seen"] is True
    assert liveness["service_alive"] is True
    assert liveness["ledger_ok"] is True
    assert liveness["latest_record_hash"] == second["record_hash"]


def test_service_liveness_reports_missing_heartbeat(tmp_path: Path) -> None:
    liveness = assess_service_liveness("missing", agents_root=tmp_path)

    assert liveness["heartbeat_seen"] is False
    assert liveness["service_alive"] is False
    assert liveness["ledger_ok"] is False
    assert "missing" in liveness["ledger_errors"][0]


def test_service_liveness_reports_stale_heartbeat(tmp_path: Path) -> None:
    observed = datetime.now(UTC) - timedelta(minutes=10)
    record_service_heartbeat(
        "codex_composer",
        agents_root=tmp_path,
        session_id="stale",
        observed_at=observed,
    )

    liveness = assess_service_liveness(
        "codex_composer",
        agents_root=tmp_path,
        now=datetime.now(UTC),
        fresh_after_seconds=60,
    )

    assert liveness["heartbeat_seen"] is True
    assert liveness["fresh"] is False
    assert liveness["service_alive"] is False
    assert liveness["ledger_ok"] is True


def test_service_liveness_can_filter_by_service_id(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    older = datetime.now(UTC) - timedelta(minutes=5)
    record_service_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        session_id="service-cycle",
        service_id="holon-l4-service",
        status="idle",
        observed_at=older,
    )
    record_service_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        session_id="smoke-cycle",
        service_id="holon-l4-smoke",
        status="idle",
    )

    latest_any = latest_service_heartbeat("codex_composer", agents_root)
    latest_service = latest_service_heartbeat(
        "codex_composer",
        agents_root,
        service_id="holon-l4-service",
    )
    liveness = assess_service_liveness(
        "codex_composer",
        agents_root=agents_root,
        fresh_after_seconds=600,
        service_id="holon-l4-service",
    )

    assert latest_any["session_id"] == "smoke-cycle"
    assert latest_service["session_id"] == "service-cycle"
    assert liveness["service_alive"] is True
    assert liveness["latest_service_id"] == "holon-l4-service"
    assert liveness["latest_session_id"] == "service-cycle"
    assert liveness["required_service_id"] == "holon-l4-service"


def test_service_heartbeat_ledger_detects_tamper(tmp_path: Path) -> None:
    record_service_heartbeat(
        "codex_composer",
        agents_root=tmp_path,
        session_id="tamper",
        status="running",
    )
    path = service_heartbeat_path("codex_composer", tmp_path)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["status"] = "stopped"
    path.write_text(json.dumps(rows[0], sort_keys=True) + "\n", encoding="utf-8")

    ok, errors = verify_service_heartbeat_ledger(path)
    liveness = assess_service_liveness("codex_composer", agents_root=tmp_path)

    assert ok is False
    assert errors == ["line 1: record_hash mismatch"]
    assert liveness["service_alive"] is False
    assert liveness["ledger_ok"] is False


def test_stopped_service_heartbeat_is_not_alive(tmp_path: Path) -> None:
    record_service_heartbeat(
        "codex_composer",
        agents_root=tmp_path,
        session_id="stopped",
        status="stopped",
    )

    liveness = assess_service_liveness("codex_composer", agents_root=tmp_path)

    assert liveness["heartbeat_seen"] is True
    assert liveness["fresh"] is True
    assert liveness["service_alive"] is False
    assert liveness["status"] == "stopped"


def test_paused_service_heartbeat_is_intentional_not_dead(tmp_path: Path) -> None:
    record_service_heartbeat(
        "codex_composer",
        agents_root=tmp_path,
        session_id="paused",
        status="paused",
    )

    liveness = assess_service_liveness("codex_composer", agents_root=tmp_path)

    assert liveness["heartbeat_seen"] is True
    assert liveness["fresh"] is True
    assert liveness["ledger_ok"] is True
    assert liveness["service_alive"] is False
    assert liveness["service_paused"] is True
    assert liveness["status"] == "paused"
