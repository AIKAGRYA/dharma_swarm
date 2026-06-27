from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dharma_swarm.holon_transport_liveness import (
    assess_a2a_inbox_bridge_liveness,
    assess_transport_liveness,
    record_a2a_bridge_transport_heartbeat,
    record_transport_heartbeat,
    transport_heartbeat_path,
    verify_transport_heartbeat_ledger,
)


def _write_heartbeat(path: Path, *, timestamp: str, status: str = "IDLE") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "dharma.a2a.inbox_bridge_heartbeat.v1",
                "timestamp": timestamp,
                "agent_uid": "codex_composer",
                "subject": "dharma.agent.codex_composer.inbox",
                "stream": "DHARMA_FLEET",
                "consumer": "codex_composer_inbox",
                "status": status,
                "cycle": 7,
                "last_receipt_path": "/tmp/receipt.json",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_a2a_bridge_liveness_reports_fresh_transport_reachable(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat.json"
    now = datetime.now(UTC)
    _write_heartbeat(heartbeat, timestamp=now.isoformat().replace("+00:00", "Z"))

    liveness = assess_a2a_inbox_bridge_liveness(
        "codex_composer",
        heartbeat_path=heartbeat,
        now=now,
    )

    assert liveness["heartbeat_seen"] is True
    assert liveness["schema_ok"] is True
    assert liveness["fresh"] is True
    assert liveness["transport_reachable"] is True
    assert liveness["status"] == "IDLE"
    assert liveness["cycle"] == 7
    assert liveness["failure_reasons"] == []


def test_a2a_bridge_liveness_reports_missing_heartbeat(tmp_path: Path) -> None:
    liveness = assess_a2a_inbox_bridge_liveness(
        "codex_composer",
        heartbeat_path=tmp_path / "missing.json",
    )

    assert liveness["heartbeat_seen"] is False
    assert liveness["transport_reachable"] is False
    assert liveness["failure_reasons"] == ["a2a_inbox_bridge_heartbeat_missing"]


def test_a2a_bridge_liveness_reports_stale_heartbeat(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat.json"
    now = datetime.now(UTC)
    stale = now - timedelta(hours=2)
    _write_heartbeat(heartbeat, timestamp=stale.isoformat().replace("+00:00", "Z"))

    liveness = assess_a2a_inbox_bridge_liveness(
        "codex_composer",
        heartbeat_path=heartbeat,
        now=now,
        fresh_after_seconds=60,
    )

    assert liveness["heartbeat_seen"] is True
    assert liveness["fresh"] is False
    assert liveness["transport_reachable"] is False
    assert "a2a_inbox_bridge_heartbeat_stale" in liveness["failure_reasons"]


def test_a2a_bridge_liveness_refuses_failed_transport_status(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat.json"
    now = datetime.now(UTC)
    _write_heartbeat(
        heartbeat,
        timestamp=now.isoformat().replace("+00:00", "Z"),
        status="NATS_CLIENT_MISSING",
    )

    liveness = assess_a2a_inbox_bridge_liveness(
        "codex_composer",
        heartbeat_path=heartbeat,
        now=now,
    )

    assert liveness["heartbeat_seen"] is True
    assert liveness["fresh"] is True
    assert liveness["transport_reachable"] is False
    assert "a2a_inbox_bridge_status_nats_client_missing" in liveness["failure_reasons"]


def test_a2a_bridge_liveness_refuses_wrong_schema(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat.json"
    now = datetime.now(UTC)
    _write_heartbeat(heartbeat, timestamp=now.isoformat().replace("+00:00", "Z"))
    payload = json.loads(heartbeat.read_text(encoding="utf-8"))
    payload["schema_version"] = "wrong"
    heartbeat.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    liveness = assess_a2a_inbox_bridge_liveness(
        "codex_composer",
        heartbeat_path=heartbeat,
        now=now,
    )

    assert liveness["schema_ok"] is False
    assert liveness["transport_reachable"] is False
    assert "a2a_inbox_bridge_heartbeat_schema_mismatch" in liveness["failure_reasons"]


def test_a2a_bridge_projection_writes_hash_chained_livingdock_heartbeat(tmp_path: Path) -> None:
    heartbeat = tmp_path / "bridge" / "codex_composer.json"
    agents_root = tmp_path / "agents"
    now = datetime.now(UTC)
    _write_heartbeat(heartbeat, timestamp=now.isoformat().replace("+00:00", "Z"))

    row = record_a2a_bridge_transport_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        heartbeat_path=heartbeat,
        now=now,
    )

    ledger = transport_heartbeat_path("codex_composer", agents_root)
    ledger_ok, errors = verify_transport_heartbeat_ledger(ledger)
    liveness = assess_transport_liveness(
        "codex_composer",
        agents_root=agents_root,
        now=now,
        transport_id="a2a_inbox_bridge",
    )

    assert ledger.exists()
    assert ledger_ok is True
    assert errors == []
    assert row["status"] == "reachable"
    assert row["previous_record_hash"] == ""
    assert row["record_hash"]
    assert liveness["heartbeat_seen"] is True
    assert liveness["ledger_ok"] is True
    assert liveness["transport_reachable"] is True


def test_a2a_bridge_projection_records_unreachable_without_passing_liveness(tmp_path: Path) -> None:
    heartbeat = tmp_path / "bridge" / "codex_composer.json"
    agents_root = tmp_path / "agents"
    now = datetime.now(UTC)
    _write_heartbeat(
        heartbeat,
        timestamp=now.isoformat().replace("+00:00", "Z"),
        status="NATS_CLIENT_MISSING",
    )

    first = record_transport_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        observed_at=now - timedelta(seconds=1),
    )
    second = record_a2a_bridge_transport_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        heartbeat_path=heartbeat,
        now=now,
    )
    liveness = assess_transport_liveness(
        "codex_composer",
        agents_root=agents_root,
        now=now,
        transport_id="a2a_inbox_bridge",
    )

    assert second["previous_record_hash"] == first["record_hash"]
    assert second["status"] == "unreachable"
    assert second["proof_ref"]["failure_reasons"] == ["a2a_inbox_bridge_status_nats_client_missing"]
    assert liveness["heartbeat_seen"] is True
    assert liveness["status"] == "unreachable"
    assert liveness["transport_reachable"] is False
