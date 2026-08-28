"""Typed, fail-closed Mission Control HTTP projection contracts."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.control_surface import control_surface_mission_snapshot, router
from dharma_swarm.mission_control_contract import (
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION,
    TERMINAL_RECEIPT_TYPE,
    ReconciliationState,
    stable_id,
)


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
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "mission_id": mission_id,
            },
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
            reconciliation="needs_task_projection",
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
                    "metadata": {
                        "schema_version": "dharma.mission_control.v1",
                        "mission_id": mission_id,
                        "mission_attempt_id": "attempt-01",
                        "mission_claim_id": "claim-01",
                    },
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
                "metadata": {
                    "schema_version": "dharma.mission_control.v1",
                    "mission_id": mission_id,
                    "mission_attempt_id": "attempt-01",
                    "mission_claim_id": "claim-01",
                },
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
                "metadata": {
                    "schema_version": SCHEMA_VERSION,
                    "mission_id": mission_id,
                    "attempt_id": "attempt-01",
                    "attempt_key": "attempt-01",
                },
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
                "stale_after": "2026-08-26T01:20:00Z",
                "metadata": {
                    "schema_version": SCHEMA_VERSION,
                    "mission_id": mission_id,
                    "attempt_id": "attempt-01",
                    "attempt_key": "attempt-01",
                },
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
                "idempotency_key": "attempt-01",
                "payload": {},
                "created_at": "2026-08-26T01:09:00Z",
            }
        ],
    )


def _queued_snapshot(mission_id: str) -> dict[str, Any]:
    value = _populated_snapshot(mission_id)
    value["tasks"][0]["status"] = "assigned"
    value["attempts"][0]["status"] = "queued"
    value["leases"][0].update(
        status="claimed",
        active=False,
        expired=False,
        heartbeat_at=None,
        stale_after="2026-08-26T01:20:00Z",
    )
    return value


def _terminal_snapshot(mission_id: str) -> dict[str, Any]:
    value = _populated_snapshot(mission_id)
    value["tasks"][0].update(status="completed", result="Fleet Hub polished")
    value["attempts"][0].update(
        status="succeeded", completed_at="2026-08-26T01:09:00Z"
    )
    value["leases"][0].update(status="completed", active=False)
    value["receipts"][0].update(
        receipt_id=stable_id("receipt", "attempt-01", "succeeded"),
        receipt_type=TERMINAL_RECEIPT_TYPE,
        status="succeeded",
        payload={
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": "attempt-01",
            "result": "Fleet Hub polished",
            "failure_code": "",
            "metadata": {
                "schema_version": SCHEMA_VERSION,
                "mission_id": mission_id,
                "attempt_id": "attempt-01",
                "attempt_key": "attempt-01",
            },
        },
    )
    return value


def _recovered_snapshot(mission_id: str) -> dict[str, Any]:
    value = _populated_snapshot(mission_id)
    value["tasks"][0].update(status="pending", assigned_to="")
    value["tasks"][0]["metadata"].pop("mission_attempt_id")
    value["tasks"][0]["metadata"].pop("mission_claim_id")
    value["attempts"][0].update(
        status="stale_recovered",
        failure_code="stale_lease_recovered",
        completed_at="2026-08-26T01:09:00Z",
    )
    value["leases"][0].update(
        status="stale_recovered",
        active=False,
        expired=True,
        stale_after="2026-08-26T01:05:00Z",
    )
    value["receipts"][0].update(
        receipt_id=stable_id("receipt", "attempt-01", "stale_recovered"),
        receipt_type=RECOVERY_RECEIPT_TYPE,
        status="stale_recovered",
        payload={
            "schema_version": SCHEMA_VERSION,
            "mission_id": mission_id,
            "attempt_id": "attempt-01",
            "recovered_claim_id": "claim-01",
            "reason": "expired_lease",
        },
    )
    return value


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


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["tasks"][0].update(status="pending "),
        lambda value: value["tasks"][0].update(priority="high "),
        lambda value: value["attempts"][0].update(status="running "),
        lambda value: value["leases"][0].update(status="active "),
        lambda value: value.update(reconciliation="coherent "),
    ],
)
def test_noncanonical_projection_vocabulary_fails_closed(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    mutate(value)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["error"] == "read failed (ValueError)"


@pytest.mark.parametrize(
    ("view", "field"),
    [
        ("mission", "created_at"),
        ("mission", "updated_at"),
        ("tasks", "created_at"),
        ("tasks", "updated_at"),
        ("attempts", "started_at"),
        ("attempts", "completed_at"),
        ("leases", "heartbeat_at"),
        ("leases", "stale_after"),
        ("receipts", "created_at"),
    ],
)
def test_malformed_nested_timestamp_fails_closed(view: str, field: str) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    member = value[view] if view == "mission" else value[view][0]
    member[field] = "definitely-not-a-timestamp"

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["error"] == "read failed (ValueError)"


@pytest.mark.parametrize(
    "factory", [_queued_snapshot, _terminal_snapshot, _recovered_snapshot]
)
def test_canonical_closed_graph_variants_are_observed(
    factory: Callable[[str], dict[str, Any]],
) -> None:
    mission_id = "fleet-advancement-20260826"

    response = _client(_AsyncProvider(factory(mission_id))).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"
    assert body["data"]["snapshot"]["reconciliation"] == "coherent"


def test_queued_claim_does_not_invent_a_deadline_requirement() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _queued_snapshot(mission_id)
    value["leases"][0]["stale_after"] = None

    body = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"


@pytest.mark.parametrize("field", ["heartbeat_at", "stale_after"])
def test_running_lease_requires_heartbeat_and_deadline_evidence(field: str) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    value["leases"][0][field] = None

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    body = response.json()
    assert response.status_code == 200
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None


@pytest.mark.parametrize(
    ("stale_after", "expired"),
    [
        ("2026-08-26T01:20:00Z", False),
        (None, False),
    ],
)
def test_stale_recovery_requires_an_actually_expired_lease(
    stale_after: str | None,
    expired: bool,
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _recovered_snapshot(mission_id)
    value["leases"][0].update(stale_after=stale_after, expired=expired)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    body = response.json()
    assert response.status_code == 200
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["tasks"][0].update(result="different-result"),
        lambda value: value["attempts"][0].update(
            failure_code="different-failure"
        ),
    ],
)
def test_terminal_receipt_payload_must_match_projected_lineage(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _terminal_snapshot(mission_id)
    mutate(value)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    body = response.json()
    assert response.status_code == 200
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None


@pytest.mark.parametrize("reported_expired", [True, False])
def test_expired_queued_lease_never_promotes_as_coherent(
    reported_expired: bool,
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _queued_snapshot(mission_id)
    value["leases"][0].update(
        expired=reported_expired,
        stale_after="2026-08-26T01:05:00Z",
    )

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["error"] == "read failed (ValueError)"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["receipts"][0].update(receipt_id="forged-receipt"),
        lambda value: value["receipts"][0].update(payload={}),
        lambda value: value["receipts"][0]["payload"].update(
            mission_id="another-mission"
        ),
        lambda value: value["receipts"][0]["payload"].update(result=1),
        lambda value: value["receipts"][0]["payload"].update(metadata={}),
        lambda value: value["receipts"][0]["payload"]["metadata"].update(
            attempt_key="another-attempt"
        ),
    ],
)
def test_forged_terminal_receipt_never_promotes_as_coherent(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _terminal_snapshot(mission_id)
    mutate(value)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["error"] == "read failed (ValueError)"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["receipts"][0].update(receipt_id="forged-receipt"),
        lambda value: value["receipts"][0].update(payload={}),
        lambda value: value["receipts"][0]["payload"].update(
            recovered_claim_id="another-claim"
        ),
        lambda value: value["receipts"][0]["payload"].update(reason="operator"),
    ],
)
def test_forged_recovery_receipt_never_promotes_as_coherent(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _recovered_snapshot(mission_id)
    mutate(value)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["error"] == "read failed (ValueError)"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["mission"]["metadata"].update(schema_version="v0"),
        lambda value: value["tasks"][0]["metadata"].update(
            mission_id="another-mission"
        ),
        lambda value: value["attempts"][0]["metadata"].update(
            schema_version="v0"
        ),
        lambda value: value["attempts"][0]["metadata"].update(
            attempt_id="another-attempt"
        ),
        lambda value: value["attempts"][0]["metadata"].update(
            attempt_key="another-attempt"
        ),
        lambda value: value["attempts"][0]["metadata"].pop("attempt_id"),
        lambda value: value["attempts"][0]["metadata"].pop("attempt_key"),
        lambda value: value["leases"][0]["metadata"].update(
            attempt_id="another-attempt"
        ),
        lambda value: value["leases"][0]["metadata"].update(
            attempt_key="another-attempt"
        ),
        lambda value: value["leases"][0]["metadata"].pop("attempt_key"),
    ],
)
def test_coherent_snapshot_requires_canonical_retained_metadata(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    mutate(value)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["error"] == "read failed (ValueError)"


def test_coherent_snapshot_rejects_consistent_whitespace_attempt_key() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    value["attempts"][0]["idempotency_key"] = " "
    value["attempts"][0]["metadata"]["attempt_key"] = " "
    value["leases"][0]["metadata"]["attempt_key"] = " "
    value["receipts"][0]["idempotency_key"] = " "

    body = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["attempts"][0].update(task_id="missing-task"),
        lambda value: value["attempts"][0].update(claim_id="missing-claim"),
        lambda value: value["leases"][0].update(task_id="missing-task"),
        lambda value: value["leases"][0].update(attempt_id="missing-attempt"),
        lambda value: value["leases"][0].update(agent_id="another-agent"),
        lambda value: value["receipts"][0].update(task_id="missing-task"),
        lambda value: value["receipts"][0].update(attempt_id="missing-attempt"),
        lambda value: value["receipts"][0].update(agent_id="another-agent"),
        lambda value: value["receipts"][0].update(
            idempotency_key="another-attempt"
        ),
        lambda value: value["leases"][0].update(active=False),
        lambda value: value["attempts"][0].update(status="succeeded"),
        lambda value: value["receipts"][0].update(
            receipt_type="mission_attempt_terminal",
            status="succeeded",
        ),
        lambda value: value.update(attempts=[], leases=[], receipts=[]),
        lambda value: value["tasks"][0]["metadata"].update(
            mission_attempt_id="another-attempt"
        ),
        lambda value: value["tasks"][0].update(status="completed"),
        lambda value: value["tasks"][0].update(status="cancelled"),
        lambda value: value["tasks"].append(dict(value["tasks"][0])),
    ],
)
def test_coherent_snapshot_with_open_or_ambiguous_lineage_fails_closed(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    mutate(value)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["error"] == "read failed (ValueError)"


def test_named_noncoherent_snapshot_preserves_orphan_evidence_for_action() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    value["attempts"] = []
    value["receipts"] = []
    value["leases"][0]["attempt_id"] = "missing-attempt"
    value["leases"][0]["metadata"].update(
        attempt_id="missing-attempt",
        attempt_key="missing-attempt",
    )
    value["reconciliation"] = "active_claim_without_run"

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"
    assert body["data"]["snapshot"]["reconciliation"] == "active_claim_without_run"
    assert body["data"]["snapshot"]["leases"][0]["attempt_id"] == "missing-attempt"


@pytest.mark.parametrize("attempt_id", ["", "bad id"])
def test_orphan_lease_attempt_identity_is_foreign_before_active_claim(
    attempt_id: str,
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    value["attempts"] = []
    value["receipts"] = []
    value["leases"][0]["attempt_id"] = attempt_id
    value["leases"][0]["metadata"].update(
        attempt_id=attempt_id,
        attempt_key=attempt_id,
    )
    value["reconciliation"] = "active_claim_without_run"

    rejected = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert rejected["data"]["state"] == "unknown"
    assert rejected["data"]["snapshot"] is None

    value["reconciliation"] = "foreign_runtime_record"
    observed = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert observed["source_errors"] == []
    assert observed["data"]["state"] == "observed"


def test_foreign_runtime_state_preserves_noncanonical_runtime_metadata() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    value["attempts"][0]["metadata"]["schema_version"] = "foreign.v0"
    value["reconciliation"] = "foreign_runtime_record"

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"
    assert body["data"]["snapshot"]["reconciliation"] == "foreign_runtime_record"


@pytest.mark.parametrize(
    "reconciliation",
    [
        state.value
        for state in ReconciliationState
        if state is not ReconciliationState.COHERENT
    ],
)
def test_noncoherent_label_without_public_evidence_fails_closed(
    reconciliation: str,
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _snapshot(mission_id, reconciliation=reconciliation)

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    body = response.json()
    assert response.status_code == 200
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None


def test_saturation_claim_with_full_public_rows_still_fails_closed() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    value["reconciliation"] = "evidence_scan_saturated"

    body = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None


def test_assigned_task_without_runtime_rows_is_visible_projection_drift() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _queued_snapshot(mission_id)
    value.update(
        attempts=[],
        leases=[],
        receipts=[],
        reconciliation="needs_task_projection",
    )

    observed = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert observed["source_errors"] == []
    assert observed["data"]["state"] == "observed"

    value["reconciliation"] = "expired_lease"
    rejected = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert rejected["data"]["state"] == "unknown"
    assert rejected["data"]["snapshot"] is None


def test_terminal_evidence_before_projection_is_visible_needs_action() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _terminal_snapshot(mission_id)
    value["tasks"][0].update(status="running", result="")
    value["attempts"][0].update(status="running", completed_at=None)
    value["leases"][0].update(status="active", active=True)
    value["reconciliation"] = "needs_task_projection"

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    body = response.json()
    assert response.status_code == 200
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"
    assert body["data"]["snapshot"]["reconciliation"] == "needs_task_projection"


def test_expired_open_terminal_lineage_is_projection_drift_before_conflict() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _terminal_snapshot(mission_id)
    value["leases"][0].update(
        status="active",
        active=False,
        expired=True,
        stale_after="2026-08-26T01:05:00Z",
    )
    value["reconciliation"] = "needs_task_projection"

    observed = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert observed["source_errors"] == []
    assert observed["data"]["state"] == "observed"

    value["reconciliation"] = "conflicting_terminal_evidence"
    rejected = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert rejected["data"]["state"] == "unknown"
    assert rejected["data"]["snapshot"] is None


@pytest.mark.parametrize("factory", [_terminal_snapshot, _recovered_snapshot])
def test_missing_lifecycle_receipt_is_publicly_witnessed(
    factory: Callable[[str], dict[str, Any]],
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = factory(mission_id)
    value["receipts"] = []
    value["reconciliation"] = "missing_terminal_receipt"

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    body = response.json()
    assert response.status_code == 200
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"


def _conflicting_claims_snapshot(mission_id: str) -> dict[str, Any]:
    value = _queued_snapshot(mission_id)
    second_attempt = deepcopy(value["attempts"][0])
    second_attempt.update(
        attempt_id="attempt-02",
        claim_id="claim-02",
        idempotency_key="attempt-02",
    )
    second_attempt["metadata"].update(
        attempt_id="attempt-02",
        attempt_key="attempt-02",
    )
    second_lease = deepcopy(value["leases"][0])
    second_lease.update(claim_id="claim-02", attempt_id="attempt-02")
    second_lease["metadata"].update(
        attempt_id="attempt-02",
        attempt_key="attempt-02",
    )
    value["attempts"].append(second_attempt)
    value["leases"].append(second_lease)
    return value


def test_conflicting_claims_precede_active_claim_without_run() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _conflicting_claims_snapshot(mission_id)
    value["reconciliation"] = "conflicting_active_claims"

    observed = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert observed["source_errors"] == []
    assert observed["data"]["state"] == "observed"

    value["attempts"] = []
    value["receipts"] = []
    for lease in value["leases"]:
        lease["metadata"]["attempt_id"] = lease["attempt_id"]
    value["reconciliation"] = "active_claim_without_run"
    rejected = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert rejected["data"]["state"] == "unknown"
    assert rejected["data"]["snapshot"] is None


def test_expired_lease_is_publicly_witnessed_at_deadline() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _queued_snapshot(mission_id)
    value["leases"][0].update(
        expired=True,
        active=False,
        stale_after=value["observed_at"],
    )
    value["reconciliation"] = "expired_lease"

    response = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    )

    body = response.json()
    assert response.status_code == 200
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"


def test_expired_running_lease_is_not_misclassified_as_projection_drift() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    value["leases"][0].update(
        active=False,
        expired=True,
        stale_after=value["observed_at"],
    )
    value["reconciliation"] = "expired_lease"

    body = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"


def test_opposite_terminal_outcome_is_conflict_not_missing() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _terminal_snapshot(mission_id)
    value["receipts"][0].update(
        receipt_id=stable_id("receipt", "attempt-01", "failed"),
        status="failed",
    )
    value["reconciliation"] = "conflicting_terminal_evidence"

    observed = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert observed["source_errors"] == []
    assert observed["data"]["state"] == "observed"

    value["reconciliation"] = "missing_terminal_receipt"
    rejected = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert rejected["data"]["state"] == "unknown"
    assert rejected["data"]["snapshot"] is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["attempts"][0]["metadata"].update(
            attempt_id="contradictory-attempt"
        ),
        lambda value: value["attempts"][0]["metadata"].update(
            attempt_key="contradictory-key"
        ),
        lambda value: value["leases"][0]["metadata"].update(
            attempt_key="contradictory-key"
        ),
        lambda value: value["attempts"][0]["metadata"].pop("attempt_id"),
        lambda value: value["attempts"][0]["metadata"].pop("attempt_key"),
        lambda value: value["leases"][0]["metadata"].pop("attempt_key"),
        lambda value: value["attempts"][0].update(idempotency_key=""),
    ],
)
def test_visible_identity_metadata_conflict_supports_foreign_state(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    mission_id = "fleet-advancement-20260826"
    value = _populated_snapshot(mission_id)
    mutate(value)
    value["reconciliation"] = "foreign_runtime_record"

    body = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"


def test_orphan_receipt_supports_visible_foreign_state() -> None:
    mission_id = "fleet-advancement-20260826"
    value = _snapshot(
        mission_id,
        reconciliation="foreign_runtime_record",
        receipts=[
            {
                "receipt_id": "orphan-receipt",
                "mission_id": mission_id,
                "task_id": "missing-task",
                "attempt_id": "missing-attempt",
                "agent_id": "missing-agent",
                "receipt_type": "progress",
                "status": "recorded",
                "idempotency_key": "missing-attempt",
                "payload": {},
                "created_at": "2026-08-26T01:09:00Z",
            }
        ],
    )

    body = _client(_AsyncProvider(value)).get(
        f"/api/control-surface/missions/{mission_id}/snapshot"
    ).json()
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"


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
