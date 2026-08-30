"""Typed, fail-closed Mission Control HTTP projection contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.control_surface import router


def _client(provider: Any = None, *, inject: bool = True) -> TestClient:
    app = FastAPI()
    if inject:
        app.state.mission_snapshot_provider = provider
    app.include_router(router)
    return TestClient(app)


def _snapshot(mission_id: str, **overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "mission": {
            "mission_id": mission_id,
            "session_id": f"mission:{mission_id}",
            "title": "Fleet advancement",
            "goal": "Advance the governed fleet",
            "operator_id": "operator",
            "status": "active",
            "metadata": {},
            "created_at": "2026-08-26T01:00:00Z",
            "updated_at": "2026-08-26T01:10:00Z",
        },
        "tasks": [],
        "attempts": [],
        "leases": [],
        "receipts": [],
        "reconciliation": "coherent",
        "observed_at": "2026-08-26T01:10:00Z",
        "authority": "TaskBoard+RuntimeStateStore",
        "proves_executor_liveness": False,
    }
    value.update(overrides)
    return value


class _AsyncProvider:
    runtime_projection_mode = "immutable_copy"

    def __init__(self, result: dict[str, Any] | None) -> None:
        self.result = result
        self.calls: list[str] = []

    async def get_snapshot(self, mission_id: str) -> dict[str, Any] | None:
        self.calls.append(mission_id)
        return self.result


def test_uninitialized_projection_does_not_invent_runtime_state() -> None:
    response = _client(inject=False).get(
        "/api/control-surface/missions/fleet-advancement-20260826/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {
        "schema_version": "dharma.control_surface.mission_snapshot_projection.v1",
        "mission_id": "fleet-advancement-20260826",
        "state": "uninitialized",
        "authority": "TaskBoard+RuntimeStateStore",
        "source_mode": "injected_read_only",
        "runtime_projection_mode": "unavailable",
        "simulation": False,
        "snapshot": None,
        "proves_executor_liveness": False,
    }
    assert body["source_errors"][0]["source"] == "mission_snapshot_provider"
    assert body["source_errors"][0]["error"] == "read-only provider is not injected"


def test_async_provider_projects_exact_typed_snapshot() -> None:
    mission_id = "fleet-advancement-20260826"
    provider = _AsyncProvider(
        _snapshot(
            mission_id,
            tasks=[
                {
                    "task_id": "fleet-t01",
                    "mission_id": mission_id,
                    "title": "Polish Fleet Hub",
                    "description": "Bounded prototype",
                    "status": "running",
                    "priority": "high",
                    "assigned_to": "fleet-seat",
                    "result": "",
                    "metadata": {},
                }
            ],
        )
    )

    response = _client(provider).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert provider.calls == [mission_id]
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"
    assert body["data"]["runtime_projection_mode"] == "immutable_copy"
    assert body["data"]["snapshot"]["mission"]["mission_id"] == mission_id
    assert body["data"]["snapshot"]["tasks"][0]["task_id"] == "fleet-t01"
    assert body["data"]["proves_executor_liveness"] is False
    assert body["data"]["simulation"] is False


@pytest.mark.parametrize(
    "mission_id",
    ["-leading-dash", "has space", "slash/value", "a" * 201, "semi;colon"],
)
def test_rejects_unbounded_or_ambiguous_identifiers(mission_id: str) -> None:
    response = _client(inject=False).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code in {404, 422}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["mission"].update(mission_id="different-mission"),
        lambda value: value.update(authority="untrusted-store"),
        lambda value: value.update(proves_executor_liveness=True),
        lambda value: value.update(tasks={"not": "a list"}),
    ],
)
def test_mismatch_or_forged_claim_fails_closed(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _snapshot(mission_id)
    mutate(value)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["data"]["proves_executor_liveness"] is False
    assert body["source_errors"][0]["error"].startswith("read failed (")
    assert "different-mission" not in body["source_errors"][0]["error"]


def test_provider_failure_is_sanitized() -> None:
    class FailingProvider:
        def get_snapshot(self, mission_id: str) -> None:
            raise RuntimeError(f"secret path for {mission_id}")

    response = _client(FailingProvider()).get(
        "/api/control-surface/missions/fleet-advancement-20260826/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["source_errors"][0]["source"] == "mission_snapshot_provider"
    assert body["source_errors"][0]["error"] == "read failed (RuntimeError)"
    assert "secret path" not in response.text
