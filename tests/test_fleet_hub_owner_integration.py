"""Integration proof: Fleet reads a real canonical owner projection over HTTP."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.control_surface import router
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_contract import MissionControlError
from dharma_swarm.mission_control_projection import (
    ConfiguredMissionSnapshotProvider,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard


MISSION_ID = "fleet-owner-integration"


def _owner_provider(tmp_path) -> ConfiguredMissionSnapshotProvider:  # noqa: ANN001
    async def build() -> ConfiguredMissionSnapshotProvider:
        board = TaskBoard(tmp_path / "tasks.db")
        runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
        await board.init_db()
        await runtime.init_db()
        control = MissionControl(board, runtime)
        await control.create_mission(
            MISSION_ID,
            title="Fleet owner integration",
            goal="Prove one real owner-backed phone read",
            operator_id="integration-test",
        )
        await control.create_task(
            MISSION_ID,
            title="Bind Fleet Hub to Mission Control",
            description="Read only; canonical owners remain authoritative",
            created_by="integration-test",
            idempotency_key="fleet-owner-task-1",
        )
        return ConfiguredMissionSnapshotProvider(control, mission_id=MISSION_ID)

    return asyncio.run(build())


def test_http_snapshot_reads_real_taskboard_and_runtime_state(tmp_path) -> None:  # noqa: ANN001
    provider = _owner_provider(tmp_path)
    app = FastAPI()
    app.state.mission_snapshot_provider = provider
    app.include_router(router)

    response = TestClient(app).get(
        f"/api/control-surface/missions/{MISSION_ID}/snapshot"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_errors"] == []
    assert body["data"]["state"] == "observed"
    assert body["data"]["runtime_projection_mode"] == "owner_supplied_read_only"
    snapshot = body["data"]["snapshot"]
    assert snapshot["authority"] == "TaskBoard+RuntimeStateStore"
    assert snapshot["mission"]["mission_id"] == MISSION_ID
    assert [task["title"] for task in snapshot["tasks"]] == [
        "Bind Fleet Hub to Mission Control"
    ]
    assert snapshot["proves_executor_liveness"] is False
    assert body["data"]["proves_executor_liveness"] is False


def test_configured_provider_exposes_no_owner_mutations(tmp_path) -> None:  # noqa: ANN001
    provider = _owner_provider(tmp_path)

    assert provider.configured_mission_id == MISSION_ID
    assert callable(provider.get_snapshot)
    for mutation in (
        "create_mission",
        "create_task",
        "start_attempt",
        "heartbeat_lease",
        "finish_attempt",
    ):
        assert not hasattr(provider, mutation)


def test_configured_provider_rejects_foreign_mission_before_owner_read(
    tmp_path,
) -> None:  # noqa: ANN001
    provider = _owner_provider(tmp_path)

    with pytest.raises(MissionControlError, match="not configured"):
        asyncio.run(provider.get_snapshot("foreign-mission"))


@pytest.mark.parametrize(
    "mission_id",
    ["", "-mission", "mission/path", "x" * 129],
)
def test_configured_provider_rejects_ambiguous_or_unbounded_id(
    mission_id: str,
) -> None:
    class Reader:
        async def get_snapshot(self, requested: str) -> None:
            raise AssertionError(requested)

    with pytest.raises(MissionControlError):
        ConfiguredMissionSnapshotProvider(Reader(), mission_id=mission_id)
