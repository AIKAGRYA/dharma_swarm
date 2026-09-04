"""Read-only Mission Control HTTP projection (api/routers/mission_control.py).

The router is the owner-side half of Fleet Hub's authenticated read-only
owner adapter.  These tests pin:

- reads run against the canonical owner DBs resolved per request, so a test
  can point the router at a seeded temporary state tree;
- absent state is a typed 503, never an empty catalog;
- the snapshot wire shape carries the owner authority literal, timezone-aware
  timestamps, and ``proves_executor_liveness: False`` — the exact invariants
  Fleet Hub's ``hub.mission_contract`` validates on the other side;
- the router exposes no mutation route, and the dashboard bearer middleware
  guards it like every other non-public ingress.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.main as api_main
from api.routers import mission_control as mc_router
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard

FIXTURE_KEY = "fixture-token-not-live-mission-control"


def _seed(state_dir: Path) -> None:
    async def build() -> None:
        runtime = RuntimeStateStore(
            state_dir / "state" / "runtime.db", include_memory_plane=False
        )
        board = TaskBoard(state_dir / "db" / "tasks.db")
        await runtime.init_db()
        await board.init_db()
        control = MissionControl(board, runtime)
        await control.create_mission(
            "m-alpha", title="Alpha", goal="Prove the HTTP adapter"
        )
        task = await control.create_task(
            "m-alpha", title="Run proof", idempotency_key="task-proof"
        )
        attempt = await control.start_attempt(
            "m-alpha", task.task_id, "agent-a", attempt_key="attempt-proof"
        )
        assert attempt.attempt_id
        await control.create_mission("m-beta", title="Beta")

    (state_dir / "state").mkdir(parents=True)
    (state_dir / "db").mkdir(parents=True)
    asyncio.run(build())


@pytest.fixture()
def seeded_state(tmp_path: Path, monkeypatch) -> Path:
    state_dir = tmp_path / "dharma"
    _seed(state_dir)
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state_dir))
    monkeypatch.delenv(mc_router.TASK_DB_ENV, raising=False)
    monkeypatch.delenv(mc_router.RUNTIME_DB_ENV, raising=False)
    return state_dir


@pytest.fixture()
def client() -> TestClient:
    # A bare app with only this router: the ingress middleware is covered by
    # tests/test_api_auth.py; here we pin the projection contract itself.
    app = FastAPI()
    app.include_router(mc_router.router)
    return TestClient(app)


def _aware(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None, value
    return parsed


class TestMissionList:
    def test_lists_only_mission_sessions_bounded_and_read_only(
        self, seeded_state, client
    ):
        response = client.get("/api/mission-control/missions")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["authority"] == "TaskBoard+RuntimeStateStore"
        assert body["proves_executor_liveness"] is False
        assert body["discovery_complete"] is False
        assert body["commands"] == [] and body["commands_available"] is False
        ids = sorted(item["mission_id"] for item in body["missions"])
        assert ids == ["m-alpha", "m-beta"]
        assert body["count"] == 2
        for item in body["missions"]:
            assert item["session_id"] == f"mission:{item['mission_id']}"
            _aware(item["created_at"])

    def test_limit_is_honoured(self, seeded_state, client):
        body = client.get("/api/mission-control/missions?limit=1").json()
        assert body["count"] == 1 and len(body["missions"]) == 1

    def test_missing_state_is_typed_503_not_empty_catalog(
        self, tmp_path, monkeypatch, client
    ):
        monkeypatch.setenv("DHARMA_STATE_DIR", str(tmp_path / "nowhere"))
        response = client.get("/api/mission-control/missions")
        assert response.status_code == 503
        body = response.json()
        assert body["error_code"] == "state_not_initialized"
        assert "missions" not in body


class TestMissionSnapshot:
    def test_snapshot_matches_fleet_hub_wire_invariants(self, seeded_state, client):
        response = client.get("/api/mission-control/missions/m-alpha/snapshot")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True and body["mission_id"] == "m-alpha"
        snapshot = body["snapshot"]
        assert snapshot["authority"] == "TaskBoard+RuntimeStateStore"
        assert snapshot["proves_executor_liveness"] is False
        assert snapshot["mission"]["mission_id"] == "m-alpha"
        assert snapshot["mission"]["session_id"] == "mission:m-alpha"
        _aware(snapshot["observed_at"])
        assert body["observed_at"] == snapshot["observed_at"]
        assert len(snapshot["tasks"]) == 1
        task = snapshot["tasks"][0]
        assert task["mission_id"] == "m-alpha"
        assert isinstance(task["status"], str)  # enums are projected as values
        assert isinstance(task["priority"], str)
        assert len(snapshot["attempts"]) == 1
        assert len(snapshot["leases"]) == 1
        assert snapshot["reconciliation"] in {
            "coherent",
            "needs_task_projection",
            "missing_terminal_receipt",
            "conflicting_active_claims",
            "active_claim_without_run",
            "expired_lease",
            "evidence_scan_saturated",
            "foreign_runtime_record",
            "conflicting_terminal_evidence",
        }
        # Every record belongs to the requested mission — the consumer rejects
        # cross-mission splices, so the owner must never emit one.
        for collection in ("tasks", "attempts", "leases", "receipts"):
            assert all(r["mission_id"] == "m-alpha" for r in snapshot[collection])

    def test_unknown_mission_is_404(self, seeded_state, client):
        response = client.get("/api/mission-control/missions/m-nope/snapshot")
        assert response.status_code == 404
        assert response.json()["error_code"] == "not_found"

    def test_invalid_mission_id_is_400(self, seeded_state, client):
        response = client.get("/api/mission-control/missions/bad%20id/snapshot")
        assert response.status_code == 400
        assert response.json()["error_code"] == "invalid_mission_id"

    def test_missing_state_is_typed_503(self, tmp_path, monkeypatch, client):
        monkeypatch.setenv("DHARMA_STATE_DIR", str(tmp_path / "nowhere"))
        response = client.get("/api/mission-control/missions/m-alpha/snapshot")
        assert response.status_code == 503
        body = response.json()
        assert body["error_code"] == "state_not_initialized"
        assert sorted(body["missing"]) == ["runtime_db", "task_db"]

    def test_explicit_db_env_overrides_state_dir(
        self, seeded_state, tmp_path, monkeypatch, client
    ):
        monkeypatch.setenv("DHARMA_STATE_DIR", str(tmp_path / "elsewhere"))
        monkeypatch.setenv(
            mc_router.TASK_DB_ENV, str(seeded_state / "db" / "tasks.db")
        )
        monkeypatch.setenv(
            mc_router.RUNTIME_DB_ENV, str(seeded_state / "state" / "runtime.db")
        )
        response = client.get("/api/mission-control/missions/m-alpha/snapshot")
        assert response.status_code == 200

    def test_owner_files_are_never_written(self, seeded_state, client):
        runtime_db = seeded_state / "state" / "runtime.db"
        task_db = seeded_state / "db" / "tasks.db"
        before = (runtime_db.read_bytes(), task_db.read_bytes())
        client.get("/api/mission-control/missions")
        client.get("/api/mission-control/missions/m-alpha/snapshot")
        assert (runtime_db.read_bytes(), task_db.read_bytes()) == before


class TestSurface:
    def test_router_exposes_reads_only(self):
        methods = {
            method
            for route in mc_router.router.routes
            for method in getattr(route, "methods", set())
        }
        assert methods == {"GET"}

    def test_registered_on_dashboard_app_behind_bearer_auth(self, monkeypatch):
        monkeypatch.setenv("DASHBOARD_API_KEY", FIXTURE_KEY)
        paths = {getattr(route, "path", "") for route in api_main.app.routes}
        assert "/api/mission-control/missions" in paths
        assert "/api/mission-control/missions/{mission_id}/snapshot" in paths
        client = TestClient(api_main.app, base_url="http://203.0.113.9")
        anonymous = client.get("/api/mission-control/missions")
        assert anonymous.status_code == 401
