"""Fail-closed tests for the bounded Mission Control HTTP projection."""

from __future__ import annotations

import logging
import threading
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.control_surface import router


MISSION_ID = "fleet-advancement-20260826"


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

    def __init__(
        self,
        result: dict[str, Any] | None,
        *,
        mission_id: str = MISSION_ID,
    ) -> None:
        self.configured_mission_id = mission_id
        self.result = result
        self.calls: list[str] = []

    async def get_snapshot(self, mission_id: str) -> dict[str, Any] | None:
        self.calls.append(mission_id)
        return self.result


def _populated_snapshot(mission_id: str = MISSION_ID) -> dict[str, Any]:
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


def test_uninitialized_projection_does_not_invent_runtime_state() -> None:
    response = _client(inject=False).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "uninitialized"
    assert body["data"]["snapshot"] is None
    assert body["data"]["proves_executor_liveness"] is False
    assert body["source_errors"][0]["source"] == "mission_snapshot_provider"
    assert body["source_errors"][0]["error"] == ("read-only provider is not injected")
    assert response.headers["cache-control"] == "no-store"


def test_provider_must_declare_one_configured_mission() -> None:
    class UnboundProvider:
        async def get_snapshot(self, mission_id: str) -> dict[str, Any]:
            raise AssertionError("unbound provider must not be invoked")

    response = _client(UnboundProvider()).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.status_code == 200
    assert response.json()["data"]["state"] == "uninitialized"
    assert response.json()["source_errors"][0]["error"] == (
        "provider is not bound to one configured mission"
    )


def test_configured_mission_mismatch_never_invokes_provider() -> None:
    provider = _AsyncProvider(_snapshot(MISSION_ID))

    response = _client(provider).get(
        "/api/control-surface/missions/another-mission/snapshot"
    )

    assert response.status_code == 200
    assert provider.calls == []
    assert response.json()["data"]["state"] == "unknown"
    assert response.json()["source_errors"][0]["source"] == "mission_snapshot"
    assert response.json()["source_errors"][0]["error"] == (
        "requested mission is not configured"
    )


def test_async_provider_projects_exact_typed_snapshot() -> None:
    provider = _AsyncProvider(_populated_snapshot())

    response = _client(provider).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert provider.calls == [MISSION_ID]
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"
    assert body["data"]["runtime_projection_mode"] == "immutable_copy"
    assert body["data"]["snapshot"]["mission"]["mission_id"] == MISSION_ID
    assert body["data"]["snapshot"]["tasks"][0]["task_id"] == "fleet-t01"
    assert body["data"]["proves_executor_liveness"] is False


def test_provider_projects_only_allowlisted_snapshot_fields() -> None:
    value = _populated_snapshot()
    value["tasks"][0]["private_provider_field"] = "not public"

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
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


def test_open_metadata_is_redacted_and_bounded_before_transport() -> None:
    value = _populated_snapshot()
    value["mission"]["metadata"] = {
        "Authorization": "Bearer do-not-transport",
        "nested": {"api_key": "also-secret", "safe": "ok"},
        "provider_api_key": "suffix-secret",
        "long": "x" * 3_000,
    }

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    raw = response.text
    metadata = response.json()["data"]["snapshot"]["mission"]["metadata"]
    assert "do-not-transport" not in raw
    assert "also-secret" not in raw
    assert "suffix-secret" not in raw
    assert metadata["Authorization"] == "[REDACTED]"
    assert metadata["nested"]["api_key"] == "[REDACTED]"
    assert metadata["nested"]["safe"] == "ok"
    assert metadata["provider_api_key"] == "[REDACTED]"
    assert metadata["long"].endswith("[TRUNCATED]")


@pytest.mark.parametrize("field", ["agents", "needs_action"])
def test_collection_outside_public_contract_fails_closed(field: str) -> None:
    value = _populated_snapshot()
    value[field] = [None]

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.json()["data"]["state"] == "unknown"
    assert response.json()["data"]["snapshot"] is None


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
    value = _populated_snapshot()
    value[field].append(malformed_member)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    body = response.json()
    assert response.status_code == 200
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["error"].startswith("read failed (")


@pytest.mark.parametrize("field", ["tasks", "attempts", "leases", "receipts"])
def test_collection_over_500_records_fails_closed(field: str) -> None:
    value = _populated_snapshot()
    template = value[field][0]
    identity_field = {
        "tasks": "task_id",
        "attempts": "attempt_id",
        "leases": "claim_id",
        "receipts": "receipt_id",
    }[field]
    value[field] = [
        {**template, identity_field: f"record-{index:03d}"} for index in range(501)
    ]

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.status_code == 200
    assert response.json()["data"]["state"] == "unknown"
    assert response.json()["data"]["snapshot"] is None


def test_cross_mission_collection_member_fails_closed() -> None:
    value = _populated_snapshot()
    value["receipts"][0]["mission_id"] = "another-mission"

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.json()["data"]["state"] == "unknown"


def test_duplicate_collection_identity_fails_closed() -> None:
    value = _populated_snapshot()
    value["tasks"].append(dict(value["tasks"][0]))

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.json()["data"]["state"] == "unknown"


@pytest.mark.parametrize(
    "mission_id",
    ["-leading-dash", "has space", "slash/value", "a" * 129, "semi;colon"],
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
        lambda value: value.update(reconciliation="invented"),
    ],
)
def test_mismatch_or_forged_claim_fails_closed(mutate: Any) -> None:
    value = _snapshot(MISSION_ID)
    mutate(value)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    body = response.json()
    assert response.status_code == 200
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["data"]["proves_executor_liveness"] is False
    assert body["source_errors"][0]["error"].startswith("read failed (")
    assert "different-mission" not in body["source_errors"][0]["error"]


def test_sync_provider_runs_off_the_event_loop() -> None:
    provider_thread: list[int] = []

    class SyncProvider:
        configured_mission_id = MISSION_ID

        def get_snapshot(self, mission_id: str) -> dict[str, Any]:
            provider_thread.append(threading.get_ident())
            return _snapshot(mission_id)

    calling_thread = threading.get_ident()
    response = _client(SyncProvider()).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.status_code == 200
    assert provider_thread
    assert provider_thread[0] != calling_thread


def test_missing_snapshot_is_truthfully_unavailable() -> None:
    response = _client(_AsyncProvider(None)).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["source"] == "mission_snapshot"


def test_provider_failure_is_sanitized(caplog: pytest.LogCaptureFixture) -> None:
    class FailingProvider:
        configured_mission_id = MISSION_ID

        def get_snapshot(self, mission_id: str) -> None:
            raise RuntimeError(f"secret path for {mission_id}\nFORGED LOG LINE")

    with caplog.at_level(logging.WARNING, logger="api.routers.control_surface"):
        response = _client(FailingProvider()).get(
            f"/api/control-surface/missions/{MISSION_ID}/snapshot"
        )

    body = response.json()
    assert response.status_code == 200
    assert body["data"]["state"] == "unknown"
    assert body["source_errors"][0]["error"] == "read failed (RuntimeError)"
    assert "secret path" not in response.text
    assert caplog.messages == ["mission snapshot provider failed (kind=read_failed)"]
    assert MISSION_ID not in caplog.text
    assert "FORGED LOG LINE" not in caplog.text


def test_owner_api_main_bearer_auth_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as api_main

    provider = _AsyncProvider(_snapshot(MISSION_ID))
    monkeypatch.setattr(
        api_main.app.state,
        "mission_snapshot_provider",
        provider,
        raising=False,
    )
    monkeypatch.setenv("DASHBOARD_API_KEY", "owner-fleet-test-key")
    client = TestClient(api_main.app)
    path = f"/api/control-surface/missions/{MISSION_ID}/snapshot"

    assert client.get(path).status_code == 401
    assert (
        client.get(path, headers={"Authorization": "Bearer wrong-key"}).status_code
        == 401
    )
    admitted = client.get(
        path,
        headers={"Authorization": "Bearer owner-fleet-test-key"},
    )
    assert admitted.status_code == 200
    assert admitted.json()["data"]["state"] == "observed"


def test_blank_owner_auth_configuration_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import api.main as api_main

    monkeypatch.setenv("DASHBOARD_API_KEY", "   ")
    response = TestClient(api_main.app).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot",
        headers={"Authorization": "Bearer "},
    )

    assert response.status_code == 503
    assert response.json()["error"] == "auth_misconfigured"
