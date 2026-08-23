"""Focused contract tests for the explicit-mission control-surface projection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.control_surface import router
from dharma_swarm.mission_control_contract import (
    AgentLeaseView,
    AttemptView,
    MissionSnapshot,
    MissionView,
    ReceiptView,
    ReconciliationState,
    TaskView,
)
from dharma_swarm.models import TaskPriority, TaskStatus


MISSION_ID = "sadhana-10-20260823"


def _client(provider: Any = None) -> TestClient:
    app = FastAPI()
    if provider is not None:
        app.state.mission_snapshot_provider = provider
    app.include_router(router)
    return TestClient(app)


def _snapshot() -> MissionSnapshot:
    observed_at = datetime(2026, 8, 23, 1, 30, tzinfo=UTC)
    return MissionSnapshot(
        mission=MissionView(
            mission_id=MISSION_ID,
            session_id=f"mission:{MISSION_ID}",
            title="Sadhana 10",
            goal="Sustain ten evidence-backed goals.",
            operator_id="operator",
            status="active",
            created_at=observed_at - timedelta(hours=1),
            updated_at=observed_at,
        ),
        tasks=(
            TaskView(
                task_id="task-01",
                mission_id=MISSION_ID,
                title="Stand up the constellation",
                description="Project canonical state without promotion.",
                status=TaskStatus.RUNNING,
                priority=TaskPriority.URGENT,
                assigned_to="hermes-planner",
                result="",
                metadata={
                    "mission_control_owner_execution": {
                        "schema_version": ("dharma.mission_control.owner_execution.v1"),
                        "backend": "orchestrator",
                        "mission_id": MISSION_ID,
                        "task_id": "task-01",
                        "dispatch_key": "primary",
                        "run_id": "owner-run-01",
                    },
                    "runtime_run_id": "owner-run-01",
                },
                created_at=observed_at - timedelta(minutes=20),
                updated_at=observed_at,
            ),
        ),
        attempts=(
            AttemptView(
                attempt_id="attempt-01",
                mission_id=MISSION_ID,
                session_id=f"mission:{MISSION_ID}",
                task_id="task-01",
                claim_id="claim-01",
                assigned_to="hermes-planner",
                assigned_by="mission-control",
                status="running",
                failure_code="",
                idempotency_key="attempt-key-01",
                started_at=observed_at - timedelta(minutes=10),
            ),
        ),
        leases=(
            AgentLeaseView(
                claim_id="claim-01",
                mission_id=MISSION_ID,
                session_id=f"mission:{MISSION_ID}",
                task_id="task-01",
                agent_id="hermes-planner",
                attempt_id="attempt-01",
                status="running",
                active=True,
                expired=False,
                heartbeat_at=observed_at - timedelta(seconds=15),
                stale_after=observed_at + timedelta(seconds=45),
            ),
        ),
        receipts=(
            ReceiptView(
                receipt_id="receipt-01",
                mission_id=MISSION_ID,
                task_id="task-01",
                attempt_id="attempt-01",
                agent_id="hermes-planner",
                receipt_type="runtime_evidence",
                status="working",
                idempotency_key="receipt-key-01",
                payload={"evidence_ref": "trace-01"},
                created_at=observed_at - timedelta(seconds=10),
            ),
        ),
        reconciliation=ReconciliationState.COHERENT,
        observed_at=observed_at,
    )


def _operator_control_evidence() -> dict[str, Any]:
    return {
        "schema_version": "dharma.sadhana.operator_control_evidence.v1",
        "claim_stage": "authority_applied",
        "control_state": "PAUSED",
        "campaign_generation": 3,
        "transition_sequence": 1,
        "request_id": "pause-one",
        "idempotency_key": "pause-idempotency-one",
        "action": "pause",
        "source_envelope_sha256": "sha256:" + "a" * 64,
        "authority_receipt_ref": "runtime-receipt:pause-one",
        "authority_receipt_sha256": "sha256:" + "b" * 64,
        "authority_applied_at": "2026-08-23T01:29:57Z",
        "effect_state": "unobserved",
        "effect_receipt_ref": "",
        "effect_receipt_sha256": "",
        "effect_observed_at": None,
    }


def test_snapshot_endpoint_without_provider_is_typed_unknown() -> None:
    response = _client().get(f"/api/control-surface/missions/{MISSION_ID}/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {
        "schema_version": "dharma.control_surface.mission_snapshot_projection.v1",
        "mission_id": MISSION_ID,
        "state": "uninitialized",
        "source_mode": "injected_read_only",
        "snapshot": None,
        "runtime_projection_ready": False,
        "runtime_projection_mode": "unavailable",
        "proves_executor_liveness": False,
    }
    assert body["source_errors"][0]["source"] == "mission_snapshot_provider"
    assert body["source_errors"][0]["error"] == "read-only provider is not injected"


def test_snapshot_endpoint_projects_exact_canonical_snapshot() -> None:
    class Provider:
        runtime_projection_mode = "immutable_copy"

        def __init__(self) -> None:
            self.calls: list[str] = []

        async def get_snapshot(self, mission_id: str) -> MissionSnapshot:
            self.calls.append(mission_id)
            return _snapshot()

    provider = Provider()
    response = _client(provider).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert provider.calls == [MISSION_ID]
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"
    assert body["data"]["proves_executor_liveness"] is False
    assert body["data"]["runtime_projection_ready"] is True
    assert body["data"]["runtime_projection_mode"] == "immutable_copy"
    assert "operator_control_evidence" not in body["data"]
    snapshot = body["data"]["snapshot"]
    assert snapshot["mission"]["mission_id"] == MISSION_ID
    assert snapshot["tasks"][0]["status"] == "running"
    assert (
        snapshot["tasks"][0]["metadata"]["mission_control_owner_execution"]["run_id"]
        == "owner-run-01"
    )
    assert snapshot["leases"][0]["active"] is True
    assert snapshot["reconciliation"] == "coherent"
    assert snapshot["observed_at"] == "2026-08-23T01:30:00+00:00"


def test_snapshot_endpoint_attaches_atomic_operator_control_sibling() -> None:
    class Provider:
        runtime_projection_mode = "unavailable"

        def __init__(self) -> None:
            self.calls: list[str] = []

        async def get_snapshot_with_operator_control(
            self, mission_id: str
        ) -> tuple[MissionSnapshot, dict[str, Any]]:
            self.calls.append(mission_id)
            return _snapshot(), _operator_control_evidence()

        async def get_snapshot(self, _mission_id: str) -> MissionSnapshot:
            raise AssertionError("atomic provider bundle must be read exactly once")

    provider = Provider()
    response = _client(provider).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert provider.calls == [MISSION_ID]
    assert body["source_errors"] == []
    projection = body["data"]
    assert projection["state"] == "observed"
    assert projection["runtime_projection_mode"] == "unavailable"
    assert projection["operator_control_evidence"] == _operator_control_evidence()
    assert "operator_control_evidence" not in projection["snapshot"]


def test_snapshot_endpoint_rejects_foreign_operator_control_shape() -> None:
    class Provider:
        async def get_snapshot_with_operator_control(
            self, _mission_id: str
        ) -> tuple[MissionSnapshot, dict[str, Any]]:
            evidence = {**_operator_control_evidence(), "operator_login": "private"}
            return _snapshot(), evidence

    response = _client(Provider()).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert "operator_login" not in response.text
    assert body["source_errors"][0]["error"] == "read failed (TypeError)"


def test_snapshot_endpoint_preserves_exact_mission_absence_as_unknown() -> None:
    async def missing(_mission_id: str) -> None:
        return None

    response = _client(missing).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["source"] == "mission_snapshot"


def test_snapshot_endpoint_rejects_cross_mission_projection() -> None:
    wrong = {
        "mission": {
            "mission_id": "another-mission",
        },
        "tasks": [],
        "attempts": [],
        "leases": [],
        "receipts": [],
        "reconciliation": "coherent",
        "observed_at": "2026-08-23T01:30:00Z",
    }

    response = _client(lambda _mission_id: wrong).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    body = response.json()
    assert body["data"]["state"] == "unknown"
    assert body["data"]["snapshot"] is None
    assert body["source_errors"][0]["source"] == "mission_snapshot_provider"
    assert body["source_errors"][0]["error"] == "read failed (ValueError)"


def test_snapshot_endpoint_redacts_provider_exception_detail() -> None:
    def failing(_mission_id: str) -> None:
        raise RuntimeError("/private/supervisor/canonical-runtime.sqlite")

    response = _client(failing).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    serialized = response.text
    assert response.json()["data"]["state"] == "unknown"
    assert "canonical-runtime.sqlite" not in serialized
    assert response.json()["source_errors"][0]["error"] == "read failed (RuntimeError)"


def test_snapshot_endpoint_rejects_unbounded_identifier() -> None:
    response = _client().get("/api/control-surface/missions/contains%20space/snapshot")

    assert response.status_code == 422


def test_dashboard_owner_join_is_schema_bound_and_never_uses_attempt_fallback() -> None:
    """Keep P2 owner-run identity distinct from Mission Control attempts."""
    source = (
        Path(__file__).parents[1] / "dashboard/src/hooks/useMissionSarathi.ts"
    ).read_text(encoding="utf-8")

    assert "dharma.mission_control.owner_execution.v1" in source
    assert "mission_control_owner_execution" in source
    assert "stamp.mission_id !== task.mission_id" in source
    assert "stamp.task_id !== task.task_id" in source
    assert "run.run_id === attemptId" not in source
    assert "Arbitrary receipt names/statuses cannot be" in source
