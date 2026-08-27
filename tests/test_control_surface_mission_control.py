"""Typed, fail-closed Mission Control HTTP projection contracts."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.control_surface import control_surface_mission_snapshot, router


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
                    "created_at": "2026-08-26T01:00:00Z",
                    "updated_at": "2026-08-26T01:10:00Z",
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


def _populated_snapshot(mission_id: str) -> dict[str, Any]:
    return _snapshot(
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
                "created_at": "2026-08-26T01:00:00Z",
                "updated_at": "2026-08-26T01:10:00Z",
            }
        ],
        attempts=[
            {
                "attempt_id": "attempt-01",
                "mission_id": mission_id,
                "session_id": f"mission:{mission_id}",
                "task_id": "fleet-t01",
                "claim_id": "claim-01",
                "assigned_to": "fleet-seat",
                "assigned_by": "operator",
                "status": "running",
                "failure_code": "",
                "idempotency_key": "attempt-01",
                "metadata": {},
                "started_at": "2026-08-26T01:01:00Z",
                "completed_at": None,
            }
        ],
        leases=[
            {
                "claim_id": "claim-01",
                "mission_id": mission_id,
                "session_id": f"mission:{mission_id}",
                "task_id": "fleet-t01",
                "agent_id": "fleet-seat",
                "attempt_id": "attempt-01",
                "status": "active",
                "active": True,
                "expired": False,
                "heartbeat_at": "2026-08-26T01:09:00Z",
                "stale_after": None,
                "metadata": {},
            }
        ],
        receipts=[
            {
                "receipt_id": "receipt-01",
                "mission_id": mission_id,
                "task_id": "fleet-t01",
                "attempt_id": "attempt-01",
                "agent_id": "fleet-seat",
                "receipt_type": "progress",
                "status": "recorded",
                "idempotency_key": "receipt-01",
                "payload": {},
                "created_at": "2026-08-26T01:09:00Z",
            }
        ],
    )


def test_provider_projects_only_validated_public_snapshot_fields() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    value["tasks"][0]["private_provider_field"] = "not public"

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    snapshot = response.json()["data"]["snapshot"]
    assert response.status_code == 200
    assert set(snapshot) == {
        "mission",
        "tasks",
        "attempts",
        "leases",
        "receipts",
        "reconciliation",
        "observed_at",
        "authority",
        "proves_executor_liveness",
    }
    assert "private_provider_field" not in snapshot["tasks"][0]


@pytest.mark.parametrize("field", ["agents", "needs_action"])
def test_collection_outside_public_snapshot_contract_fails_closed(field: str) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    value[field] = [None]

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None


@pytest.mark.parametrize(
    ("field", "malformed_member"),
    [
        ("tasks", None),
        ("tasks", {"task_id": "missing-status"}),
        ("attempts", None),
        ("leases", {"active": True}),
        ("receipts", "not-an-object"),
    ],
)
def test_malformed_collection_member_fails_closed(
    field: str,
    malformed_member: Any,
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    value[field].append(malformed_member)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    body = response.json()
    assert response.status_code == 200
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["error"].startswith("read failed (")


def test_collection_member_from_another_mission_fails_closed() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    value["receipts"][0]["mission_id"] = "another-mission"

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None


@pytest.mark.parametrize("view", ["mission", "attempts", "leases"])
def test_foreign_session_identity_fails_closed(view: str) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    if view == "mission":
        value[view]["session_id"] = "mission:another-mission"
    else:
        value[view][0]["session_id"] = "mission:another-mission"

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert "another-mission" not in body["source_errors"][0]["error"]


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


@pytest.mark.parametrize(
    "observed_at",
    ["definitely-not-a-timestamp", "2026-08-26T01:10:00", ""],
)
def test_malformed_or_ambiguous_observation_time_fails_closed(
    observed_at: str,
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _snapshot(mission_id, observed_at=observed_at)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["error"] == "read failed (ValueError)"


def test_sync_provider_is_offloaded_while_event_loop_remains_live() -> None:
    mission_id = "fleet-advancement-20260826"
    started = threading.Event()
    release = threading.Event()
    provider_thread: list[int] = []

    class BlockingProvider:
        def get_snapshot(self, requested_mission_id: str) -> dict[str, Any]:
            provider_thread.append(threading.get_ident())
            started.set()
            if not release.wait(timeout=2):
                raise TimeoutError("test did not release provider")
            return _snapshot(requested_mission_id)

    async def exercise() -> dict[str, Any]:
        loop_thread = threading.get_ident()
        app = SimpleNamespace(
            state=SimpleNamespace(mission_snapshot_provider=BlockingProvider())
        )
        request = SimpleNamespace(app=app)
        response_task = asyncio.create_task(
            control_surface_mission_snapshot(mission_id, request)
        )
        provider_started = await asyncio.to_thread(started.wait, 1)
        assert provider_started
        assert len(provider_thread) == 1
        assert provider_thread[0] != loop_thread
        release.set()
        return await response_task

    body = asyncio.run(exercise())
    assert body["data"]["state"] == "observed"


def test_async_provider_remains_awaited_on_event_loop() -> None:
    mission_id = "fleet-advancement-20260826"
    provider_thread: list[int] = []

    class TrackingAsyncProvider:
        async def get_snapshot(self, requested_mission_id: str) -> dict[str, Any]:
            provider_thread.append(threading.get_ident())
            await asyncio.sleep(0)
            return _snapshot(requested_mission_id)

    async def exercise() -> tuple[int, dict[str, Any]]:
        loop_thread = threading.get_ident()
        app = SimpleNamespace(
            state=SimpleNamespace(mission_snapshot_provider=TrackingAsyncProvider())
        )
        request = SimpleNamespace(app=app)
        body = await control_surface_mission_snapshot(mission_id, request)
        return loop_thread, body

    loop_thread, body = asyncio.run(exercise())
    assert provider_thread == [loop_thread]
    assert body["data"]["state"] == "observed"


def test_provider_failure_is_sanitized(caplog: pytest.LogCaptureFixture) -> None:
    class FailingProvider:
        def get_snapshot(self, mission_id: str) -> None:
            raise RuntimeError(f"secret path for {mission_id}\nFORGED LOG LINE")

    with caplog.at_level(logging.WARNING, logger="api.routers.control_surface"):
        response = _client(FailingProvider()).get(
            "/api/control-surface/missions/fleet-advancement-20260826/snapshot"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["source_errors"][0]["source"] == "mission_snapshot_provider"
    assert body["source_errors"][0]["error"] == "read failed (RuntimeError)"
    assert "secret path" not in response.text
    assert caplog.messages == [
        "mission snapshot provider failed (kind=read_failed)"
    ]
    assert "fleet-advancement-20260826" not in caplog.text
    assert "FORGED LOG LINE" not in caplog.text
