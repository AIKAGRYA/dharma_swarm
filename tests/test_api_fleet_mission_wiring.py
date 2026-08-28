"""Fail-closed composition-root coverage for the Fleet mission read provider."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI

import api.main as api_main
import dharma_swarm.ontology_runtime as ontology_runtime
from dharma_swarm.api_keys import API_MODE_LOCAL_DEV
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard


MISSION_ID = "fleet-wiring-test"


class _TraceStore:
    async def init(self) -> None:
        return None


class _RuntimeLifecycle:
    def __init__(self, runtime_state: Any) -> None:
        self.runtime_state = runtime_state
        self.calls = 0

    def _runtime_state_store(self) -> Any:
        self.calls += 1
        return self.runtime_state


class _Swarm:
    def __init__(
        self,
        task_board: Any,
        runtime_state: Any,
        *,
        init_mode: str = "success",
    ) -> None:
        self._task_board = task_board
        self._runtime_lifecycle = _RuntimeLifecycle(runtime_state)
        self._orchestrator: Any = SimpleNamespace(
            _board=task_board,
            _runtime_lifecycle=self._runtime_lifecycle,
        )
        self._init_mode = init_mode

    async def init(self) -> None:
        if self._init_mode == "partial":
            raise _PartialInitializationError("sensitive-partial-detail")
        if self._init_mode == "timeout":
            await asyncio.Event().wait()


class _PartialInitializationError(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def _isolated_main_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_main, "_state", {})
    monkeypatch.delenv("FLEET_HUB_MISSION_ID", raising=False)
    monkeypatch.delenv("DHARMA_SWARM_INIT_TIMEOUT_SECONDS", raising=False)


def _owners(tmp_path) -> tuple[TaskBoard, RuntimeStateStore]:  # noqa: ANN001
    board = TaskBoard(tmp_path / "tasks.db")
    runtime = RuntimeStateStore(
        tmp_path / "runtime.db",
        include_memory_plane=False,
    )
    return board, runtime


def _patch_lifespan(monkeypatch: pytest.MonkeyPatch, swarm: _Swarm) -> None:
    monkeypatch.setattr(api_main, "dashboard_api_mode", lambda: API_MODE_LOCAL_DEV)
    monkeypatch.setattr(api_main, "normalize_env_aliases", lambda: {})
    monkeypatch.setattr(api_main, "_publish_operator_pid", lambda _pid=None: None)
    monkeypatch.setattr(api_main, "_clear_operator_pid", lambda _pid=None: None)
    monkeypatch.setattr(api_main, "get_trace_store", lambda: _TraceStore())
    monkeypatch.setattr(api_main, "get_swarm", lambda: swarm)
    monkeypatch.setattr(api_main, "_initialize_boardstore_shadow", lambda _swarm: None)
    monkeypatch.setattr(api_main, "_initialize_node_gateway", lambda: None)
    monkeypatch.setattr(api_main, "_initialize_agent_directory", lambda _swarm: None)
    monkeypatch.setattr(api_main, "_log_auth_mode", lambda: None)
    monkeypatch.setattr(ontology_runtime, "get_shared_registry", lambda: object())


def test_lifespan_wires_exact_initialized_owner_instances_read_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    board_path = tmp_path / "tasks.db"
    runtime_path = tmp_path / "runtime.db"
    board, runtime = _owners(tmp_path)
    swarm = _Swarm(board, runtime)
    _patch_lifespan(monkeypatch, swarm)
    monkeypatch.setenv("FLEET_HUB_MISSION_ID", MISSION_ID)
    test_app = FastAPI()

    assert not board_path.exists()
    assert not runtime_path.exists()

    async def exercise() -> None:
        async with api_main.lifespan(test_app):
            provider = test_app.state.mission_snapshot_provider
            owner_reader = provider._get_snapshot.__self__

            assert provider.configured_mission_id == MISSION_ID
            assert owner_reader._board is board
            assert owner_reader._runtime is runtime
            assert swarm._runtime_lifecycle.calls == 1
            for mutation in (
                "create_mission",
                "create_task",
                "start_attempt",
                "heartbeat_lease",
                "finish_attempt",
            ):
                assert not hasattr(provider, mutation)

            # Composition must not initialize or otherwise open either owner DB.
            assert not board_path.exists()
            assert not runtime_path.exists()

    asyncio.run(exercise())

    assert not hasattr(test_app.state, "mission_snapshot_provider")
    assert not board_path.exists()
    assert not runtime_path.exists()


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_missing_mission_configuration_clears_stale_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    caplog: pytest.LogCaptureFixture,
    configured: str | None,
) -> None:
    board, runtime = _owners(tmp_path)
    swarm = _Swarm(board, runtime)
    _patch_lifespan(monkeypatch, swarm)
    if configured is not None:
        monkeypatch.setenv("FLEET_HUB_MISSION_ID", configured)
    test_app = FastAPI()
    test_app.state.mission_snapshot_provider = object()
    caplog.set_level(logging.INFO, logger="api.main")

    async def exercise() -> None:
        async with api_main.lifespan(test_app):
            assert not hasattr(test_app.state, "mission_snapshot_provider")

    asyncio.run(exercise())

    assert "error_type=MissingConfiguration" in caplog.text
    assert not hasattr(test_app.state, "mission_snapshot_provider")


def test_invalid_mission_id_fails_closed_without_logging_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    board, runtime = _owners(tmp_path)
    swarm = _Swarm(board, runtime)
    _patch_lifespan(monkeypatch, swarm)
    invalid_value = "invalid/sensitive-mission"
    monkeypatch.setenv("FLEET_HUB_MISSION_ID", invalid_value)
    test_app = FastAPI()
    caplog.set_level(logging.WARNING, logger="api.main")

    async def exercise() -> None:
        async with api_main.lifespan(test_app):
            assert not hasattr(test_app.state, "mission_snapshot_provider")

    asyncio.run(exercise())

    assert "error_type=MissionControlError" in caplog.text
    assert invalid_value not in caplog.text


@pytest.mark.parametrize("init_mode", ["partial", "timeout"])
def test_partial_or_timed_out_swarm_init_never_wires_partial_owners(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    caplog: pytest.LogCaptureFixture,
    init_mode: str,
) -> None:
    board, runtime = _owners(tmp_path)
    swarm = _Swarm(board, runtime, init_mode=init_mode)
    _patch_lifespan(monkeypatch, swarm)
    monkeypatch.setenv("FLEET_HUB_MISSION_ID", MISSION_ID)
    monkeypatch.setenv("DHARMA_SWARM_INIT_TIMEOUT_SECONDS", "0.001")
    test_app = FastAPI()
    test_app.state.mission_snapshot_provider = object()
    caplog.set_level(logging.WARNING, logger="api.main")

    async def exercise() -> None:
        async with api_main.lifespan(test_app):
            assert not hasattr(test_app.state, "mission_snapshot_provider")

    asyncio.run(exercise())

    assert "error_type=SwarmInitializationIncomplete" in caplog.text
    assert "sensitive-partial-detail" not in caplog.text
    assert swarm._runtime_lifecycle.calls == 0


@pytest.mark.parametrize(
    "missing_owner",
    [
        "task_board",
        "orchestrator",
        "orchestrator_board",
        "runtime_lifecycle",
        "runtime_getter",
        "runtime_state",
    ],
)
def test_missing_or_split_owner_seam_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    caplog: pytest.LogCaptureFixture,
    missing_owner: str,
) -> None:
    board, runtime = _owners(tmp_path)
    swarm = _Swarm(board, runtime)
    if missing_owner == "task_board":
        swarm._task_board = None
    elif missing_owner == "orchestrator":
        swarm._orchestrator = None
    elif missing_owner == "orchestrator_board":
        swarm._orchestrator._board = TaskBoard(tmp_path / "split-tasks.db")
    elif missing_owner == "runtime_lifecycle":
        swarm._orchestrator._runtime_lifecycle = None
    elif missing_owner == "runtime_getter":
        swarm._orchestrator._runtime_lifecycle = object()
    elif missing_owner == "runtime_state":
        swarm._runtime_lifecycle.runtime_state = None

    _patch_lifespan(monkeypatch, swarm)
    monkeypatch.setenv("FLEET_HUB_MISSION_ID", MISSION_ID)
    test_app = FastAPI()
    caplog.set_level(logging.WARNING, logger="api.main")

    async def exercise() -> None:
        async with api_main.lifespan(test_app):
            assert not hasattr(test_app.state, "mission_snapshot_provider")

    asyncio.run(exercise())

    assert "error_type=RuntimeError" in caplog.text
    assert not hasattr(test_app.state, "mission_snapshot_provider")
