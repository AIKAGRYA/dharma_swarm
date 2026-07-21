from __future__ import annotations

from pathlib import Path

from scripts.runtime.agni_hub_readiness import (
    build_agni_hub_readiness,
    write_readiness,
)


def _service_rows(active: bool = True) -> dict[str, dict[str, object]]:
    return {
        "nats.service": {"status": "active" if active else "inactive", "active": active},
        "openclaw.service": {"status": "active", "active": True},
    }


def test_agni_hub_readiness_degrades_on_stale_agents_and_disk_pressure(tmp_path: Path) -> None:
    payload = build_agni_hub_readiness(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        nats_jsz_payload={"streams": 7, "consumers": 27, "messages": 105, "storage": 285350},
        agents_payload={
            "status": "ok",
            "data": [
                {
                    "id": "agent-1",
                    "provider": "ollama",
                    "last_heartbeat": "2026-06-27T00:00:00+00:00",
                }
            ],
        },
        fleet_payload={
            "count": 1,
            "nodes": [{"node_id": "sab-agni", "status": "online"}],
        },
        services_payload=_service_rows(),
        memory_payload={"available": True, "available_gib": 5.0},
        disk_payload={"available": True, "used_pct": 78.0, "free_gib": 27.0},
        bridge_heartbeat_payload={
            "exists": True,
            "timestamp": "2026-07-01T03:00:00Z",
            "age_minutes": 5,
            "semantic_reply_capable": True,
        },
    )

    checks = {check["id"]: check for check in payload["checks"]}
    assert payload["status"] == "degraded"
    assert checks["nats.jetstream"]["status"] == "ok"
    assert checks["api.agents"]["status"] == "warn"
    assert checks["api.agents"]["details"]["semantic_liveness_claim"] is False
    assert checks["host.resources"]["status"] == "warn"
    assert checks["host.resources"]["details"]["warnings"] == ["disk_pressure"]
    assert payload["summary"]["mutation_claim"] is False


def test_agni_hub_readiness_blocks_when_required_service_inactive(tmp_path: Path) -> None:
    payload = build_agni_hub_readiness(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        nats_jsz_payload={"streams": 1, "consumers": 1, "messages": 1},
        agents_payload={"status": "ok", "data": []},
        fleet_payload={"count": 0, "nodes": []},
        services_payload=_service_rows(active=False),
        memory_payload={"available": True, "available_gib": 5.0},
        disk_payload={"available": True, "used_pct": 50.0, "free_gib": 60.0},
        bridge_heartbeat_payload={"exists": False},
    )

    checks = {check["id"]: check for check in payload["checks"]}
    assert payload["status"] == "blocked"
    assert checks["systemd.required"]["status"] == "fail"
    assert "nats.service" in checks["systemd.required"]["details"]["inactive"]


def test_agni_hub_readiness_blocks_when_nats_unreachable(tmp_path: Path) -> None:
    payload = build_agni_hub_readiness(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        nats_jsz_error="URLError: refused",
        agents_payload={"status": "ok", "data": []},
        fleet_payload={"count": 0, "nodes": []},
        services_payload=_service_rows(),
        memory_payload={"available": True, "available_gib": 5.0},
        disk_payload={"available": True, "used_pct": 50.0, "free_gib": 60.0},
        bridge_heartbeat_payload={"exists": False},
    )

    checks = {check["id"]: check for check in payload["checks"]}
    assert payload["status"] == "blocked"
    assert checks["nats.jetstream"]["status"] == "fail"


def test_agni_hub_readiness_without_write_does_not_create_receipt(tmp_path: Path) -> None:
    output = tmp_path / "state" / "ops" / "agni_hub_readiness.json"

    payload = build_agni_hub_readiness(
        repo_root=tmp_path,
        state_root=tmp_path / "state",
        nats_jsz_payload={"streams": 1, "consumers": 1, "messages": 1},
        agents_payload={"status": "ok", "data": []},
        fleet_payload={"count": 0, "nodes": []},
        services_payload=_service_rows(),
        memory_payload={"available": True, "available_gib": 5.0},
        disk_payload={"available": True, "used_pct": 50.0, "free_gib": 60.0},
        bridge_heartbeat_payload={"exists": False},
    )

    assert payload["schema_version"] == "agni_hub_readiness.v1"
    assert not output.exists()

    written = write_readiness(payload, output)
    assert written == output
    assert output.exists()
