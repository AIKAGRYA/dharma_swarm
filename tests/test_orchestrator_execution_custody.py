"""Real-store regressions for execution cancellation custody ordering."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from unittest.mock import AsyncMock

from dharma_swarm.agent_runner import AgentPool
from dharma_swarm.models import (
    AgentRole,
    AgentState,
    AgentStatus,
    TaskDispatch,
    TaskStatus,
)
from dharma_swarm.orchestrator import Orchestrator
from dharma_swarm.spine import ExecutionIdentity, identity_metadata
from dharma_swarm.task_board import TaskBoard


class _FixtureRunner:
    def __init__(self, agent_id: str, *, raises: bool = False) -> None:
        self._state = AgentState(
            id=agent_id,
            name=f"{agent_id}-seat",
            role=AgentRole.CODER,
            status=AgentStatus.IDLE,
        )
        self._lock = asyncio.Lock()
        self._config = SimpleNamespace(
            id=agent_id,
            name=self._state.name,
            model="fixture-model",
            provider="fixture-provider",
        )
        self.entered = asyncio.Event()
        self.blocked = asyncio.Event()
        self.raises = raises

    @property
    def state(self) -> AgentState:
        return self._state

    async def run_task(self, _task: Any, **_kwargs: Any) -> str:
        self.entered.set()
        if self.raises:
            raise RuntimeError("provider execution failed")
        await self.blocked.wait()
        return "unreachable"


class _FaultedTerminalBoard(TaskBoard):
    """Keep reads real while making every terminal Board write unavailable."""

    terminal_fault = True

    async def compare_and_swap_terminal_projection(self, *args: Any, **kwargs: Any):
        if self.terminal_fault:
            raise RuntimeError("terminal projection unavailable")
        return await super().compare_and_swap_terminal_projection(*args, **kwargs)

    async def update_task(self, task_id: str, **fields: Any) -> None:
        if self.terminal_fault and fields.get("status") is TaskStatus.FAILED:
            raise RuntimeError("terminal quarantine unavailable")
        await super().update_task(task_id, **fields)


async def _running_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    campaign: bool = False,
    provider_raises: bool = False,
    board_type: type[TaskBoard] = TaskBoard,
) -> tuple[Orchestrator, TaskBoard, AgentPool, _FixtureRunner, Any, TaskDispatch, Any]:
    monkeypatch.setenv("HOME", str(tmp_path))
    board = board_type(tmp_path / "task-board.db")
    await board.init_db()
    task = await board.create(
        "custody regression",
        metadata={"retry_count": 0, "max_retries": 1 if provider_raises else 0},
    )
    agent_id = "campaign-agent" if campaign else "generic-agent"
    identity = ExecutionIdentity.new(
        task_id=task.id,
        agent_id=agent_id,
        session_id="custody-regression",
    ).require_for_dispatch()
    metadata = {**task.metadata, **identity_metadata(identity, surface="fixture")}
    metadata["active_claim"] = {"claim_id": identity.claim_id}
    metadata["runtime_db_path"] = str((tmp_path / "runtime.db").resolve())
    task = await board.assign(task.id, agent_id, metadata=metadata)
    task = await board.start(task.id, metadata=metadata)
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id=agent_id,
        metadata={
            **identity_metadata(identity, surface="fixture"),
            "attempt_generation": 0,
            "runtime_db_path": metadata["runtime_db_path"],
        },
    )
    runner = _FixtureRunner(agent_id, raises=provider_raises)
    pool = AgentPool()
    pool._agents[agent_id] = runner
    token: Any = (
        {
            "reservation_id": "post-effect-token",
            "attempt_generation": 0,
            "provider_task_scheduled": True,
        }
        if campaign
        else dispatch
    )
    assert await pool.reserve(agent_id, task.id, reservation_token=token)
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path / "ledgers",
        runtime_db_path=tmp_path / "runtime.db",
        shared_dir=tmp_path / "shared",
        stigmergy_dir=tmp_path / "stigmergy",
        session_id="custody-regression",
    )
    orchestrator._active_dispatches[task.id] = dispatch
    if campaign:
        orchestrator._campaign_reservations[(task.id, agent_id, 0)] = token
        dispatch.metadata["_campaign_active_owner_installed"] = True
    else:
        orchestrator._spine_dispatch_enabled = lambda: False  # type: ignore[method-assign]
    board._witness_transition = AsyncMock()  # type: ignore[method-assign]
    return orchestrator, board, pool, runner, task, dispatch, token


def _track_execution(
    orchestrator: Orchestrator,
    task_id: str,
    dispatch: TaskDispatch,
    coroutine: Any,
) -> asyncio.Task[None]:
    execution = asyncio.create_task(coroutine)
    orchestrator._running_tasks[task_id] = execution
    orchestrator._running_dispatch_owners[task_id] = (execution, dispatch)
    return execution


@pytest.mark.asyncio
async def test_generic_external_cancel_quarantines_board_before_exact_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator, board, pool, runner, task, dispatch, _ = await _running_fixture(
        tmp_path, monkeypatch
    )
    execution = _track_execution(
        orchestrator,
        task.id,
        dispatch,
        orchestrator._execute_task(runner, task, dispatch),
    )
    await asyncio.wait_for(runner.entered.wait(), timeout=2)

    execution.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(execution, timeout=2)

    assert (await board.get(task.id)).status is TaskStatus.FAILED  # type: ignore[union-attr]
    assert not pool.owns_reservation(
        dispatch.agent_id, task.id, reservation_token=dispatch
    )
    assert orchestrator._active_dispatches == {}
    assert orchestrator._generic_recovery_owners == {}
    summary = await orchestrator.graceful_stop(1)
    assert "live" not in summary
    assert orchestrator._running_dispatch_owners == {}


@pytest.mark.asyncio
async def test_campaign_post_effect_cancel_terminalizes_before_exact_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator, board, pool, runner, task, dispatch, token = await _running_fixture(
        tmp_path, monkeypatch, campaign=True
    )
    entered = asyncio.Event()
    blocked = asyncio.Event()

    async def post_effect_provider(*_args: Any, **_kwargs: Any) -> str:
        entered.set()
        await blocked.wait()
        return "unreachable"

    orchestrator._spine_dispatch_enabled = lambda: True  # type: ignore[method-assign]
    orchestrator._run_task_via_spine = post_effect_provider  # type: ignore[method-assign]
    execution = _track_execution(
        orchestrator,
        task.id,
        dispatch,
        orchestrator._execute_campaign_task(
            runner,
            task,
            dispatch,
            campaign_principal=dispatch.agent_id,
            campaign_reservation_token=token,
        ),
    )
    await asyncio.wait_for(entered.wait(), timeout=2)

    execution.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(execution, timeout=5)

    assert (await board.get(task.id)).status is TaskStatus.FAILED  # type: ignore[union-attr]
    assert not pool.owns_reservation(
        dispatch.agent_id, task.id, reservation_token=token
    )
    assert orchestrator._active_dispatches == {}
    assert orchestrator._campaign_reservations == {}
    assert orchestrator._campaign_recovery_owners == {}
    summary = await orchestrator.graceful_stop(1)
    assert "live" not in summary


@pytest.mark.asyncio
async def test_projection_failure_retains_visible_custody_until_board_recovers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator, board, pool, runner, task, dispatch, _ = await _running_fixture(
        tmp_path,
        monkeypatch,
        provider_raises=True,
        board_type=_FaultedTerminalBoard,
    )
    execution = _track_execution(
        orchestrator,
        task.id,
        dispatch,
        orchestrator._execute_task(runner, task, dispatch),
    )
    await asyncio.wait_for(runner.entered.wait(), timeout=2)
    with pytest.raises(RuntimeError, match="retained indeterminate custody"):
        await asyncio.wait_for(execution, timeout=5)

    assert (await board.get(task.id)).status is TaskStatus.RUNNING  # type: ignore[union-attr]
    assert pool.owns_reservation(
        dispatch.agent_id, task.id, reservation_token=dispatch
    )
    assert orchestrator._generic_recovery_owners[id(dispatch)][0] is dispatch
    summary = await orchestrator.graceful_stop(0.05)
    assert summary["live_task_ids"] == [task.id]
    assert summary["indeterminate_custody_task_ids"] == [task.id]

    assert isinstance(board, _FaultedTerminalBoard)
    board.terminal_fault = False
    recovered = await orchestrator.graceful_stop(1)
    assert "live" not in recovered
    assert (await board.get(task.id)).status is TaskStatus.FAILED  # type: ignore[union-attr]
    assert orchestrator._generic_recovery_owners == {}
