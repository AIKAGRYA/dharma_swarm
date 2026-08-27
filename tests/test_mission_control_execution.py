from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import dharma_swarm.orchestrator as orchestrator_module
from dharma_swarm.agent_memory_manager import AgentMemoryManager
from dharma_swarm.agent_runner import AgentPool
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_contract import (
    MissionControlError,
    stable_id,
    utc_now,
)
from dharma_swarm.mission_control_execution import (
    OWNER_BACKEND,
    OrchestratorMissionAdapter,
    OwnerExecutionRef,
)
from dharma_swarm.models import (
    AgentConfig,
    AgentRole,
    LLMRequest,
    LLMResponse,
    ProviderType,
    TaskDispatch,
    TaskStatus,
    TopologyType,
)
from dharma_swarm.orchestrator import Orchestrator
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeStateStore,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard


MISSION_ID = "mission-alpha"
OWNER_SESSION_ID = "owner-session-alpha"
DISPATCH_KEY = "default"


class _FakeProvider:
    available = True

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            content=(
                "Hermetic owner execution completed successfully. Evidence was "
                "recorded in the isolated TaskBoard and RuntimeStateStore fixture; "
                "the result is deterministic and requires no external provider."
            ),
            model="fixture-model",
            provider="fixture",
            usage={"total_tokens": 23},
        )


class _MissionBoundary:
    """Expose mission lookup while exploding on duplicate P0 lifecycle calls."""

    def __init__(self, control: MissionControl) -> None:
        self.control = control
        self.lifecycle_calls = 0

    async def get_mission(self, mission_id: str):
        return await self.control.get_mission(mission_id)

    async def start_attempt(self, *args: Any, **kwargs: Any) -> None:
        self.lifecycle_calls += 1
        raise AssertionError("adapter must not create a Mission Control attempt")

    async def heartbeat_lease(self, *args: Any, **kwargs: Any) -> None:
        self.lifecycle_calls += 1
        raise AssertionError("adapter must not heartbeat a Mission Control lease")

    async def finish_attempt(self, *args: Any, **kwargs: Any) -> None:
        self.lifecycle_calls += 1
        raise AssertionError("adapter must not finish a Mission Control attempt")


class _NoDispatch:
    def __init__(self) -> None:
        self.calls = 0

    async def dispatch(self, task, topology):
        self.calls += 1
        return []


class _ManyDispatches:
    def __init__(self) -> None:
        self.calls = 0

    async def dispatch(self, task, topology):
        self.calls += 1
        return [
            TaskDispatch(task_id=task.id, agent_id="agent-a", topology=topology),
            TaskDispatch(task_id=task.id, agent_id="agent-b", topology=topology),
        ]


async def _stack(tmp_path: Path):
    board = TaskBoard(tmp_path / "tasks.db")
    runtime = RuntimeStateStore(
        tmp_path / "runtime.db",
        include_memory_plane=False,
    )
    await board.init_db()
    await runtime.init_db()
    control = MissionControl(board, runtime)
    await control.create_mission(
        MISSION_ID,
        title="Mission Alpha",
        goal="Exercise the canonical executor adapter",
    )
    task = await control.create_task(
        MISSION_ID,
        title="Produce the hermetic owner result",
        description="Return one deterministic local result.",
        idempotency_key="mission-alpha-task",
    )
    return board, runtime, control, task


def _expected(task_id: str, dispatch_key: str = DISPATCH_KEY) -> tuple[str, str]:
    parts = (MISSION_ID, task_id, dispatch_key)
    return (
        stable_id("owner_run", *parts),
        stable_id("owner_dispatch", *parts),
    )


async def _record_owner_execution(
    runtime: RuntimeStateStore,
    *,
    task_id: str,
    run_id: str,
    idempotency_key: str,
    claim_id: str,
    agent_id: str,
    owner_session_id: str,
    status: str = "running",
) -> OwnerExecutionRef:
    identity = ExecutionIdentity.new(
        trace_id=f"trace-{run_id}",
        correlation_id=f"corr-{run_id}",
        task_id=task_id,
        run_id=run_id,
        claim_id=claim_id,
        agent_id=agent_id,
        session_id=owner_session_id,
        idempotency_key=idempotency_key,
    )
    await runtime.record_execution_identity(identity, source="test-owner")
    await runtime.record_task_claim(
        TaskClaim(
            claim_id=claim_id,
            task_id=task_id,
            agent_id=agent_id,
            status=status,
            session_id=owner_session_id,
            stale_after=utc_now() + timedelta(minutes=5),
            metadata={"mission_id": MISSION_ID},
        )
    )
    await runtime.record_delegation_run(
        DelegationRun(
            run_id=run_id,
            task_id=task_id,
            assigned_to=agent_id,
            assigned_by=OWNER_BACKEND,
            claim_id=claim_id,
            session_id=owner_session_id,
            status=status,
            metadata={
                "mission_id": MISSION_ID,
                "topology": TopologyType.PIPELINE.value,
                "idempotency_key": idempotency_key,
            },
        )
    )
    return OwnerExecutionRef(
        backend=OWNER_BACKEND,
        mission_id=MISSION_ID,
        task_id=task_id,
        dispatch_key=DISPATCH_KEY,
        run_id=run_id,
        claim_id=claim_id,
        agent_id=agent_id,
        idempotency_key=idempotency_key,
        owner_session_id=owner_session_id,
    )


@pytest.mark.asyncio
async def test_real_agent_pool_runner_executes_once_and_retry_recovers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fast_gate,
) -> None:
    monkeypatch.setenv("DHARMA_FAST_BOOT", "1")
    monkeypatch.setenv("DGC_AGENT_PROMPT_MEMORY_MODE", "off")
    monkeypatch.setattr(
        orchestrator_module,
        "check_with_reflective_reroute",
        lambda **_: fast_gate,
    )

    async def _no_optional_background_work(*args: Any, **kwargs: Any) -> None:
        return None

    from dharma_swarm.sleep_time_agent import SleepTimeAgent
    import dharma_swarm.telos_tracker as telos_tracker

    monkeypatch.setattr(
        SleepTimeAgent,
        "consolidate_knowledge",
        _no_optional_background_work,
    )
    monkeypatch.setattr(
        telos_tracker,
        "record_task_completion",
        _no_optional_background_work,
    )

    board, runtime, control, task_view = await _stack(tmp_path)
    provider = _FakeProvider()
    memory = AgentMemoryManager(
        "fixture-owner-agent",
        db_path=tmp_path / "agent-memory.db",
    )
    pool = AgentPool()
    state_dir = tmp_path / "agent-state"
    state_dir.mkdir()
    config = AgentConfig(
        id="fixture-owner-agent",
        name="fixture-owner-agent",
        role=AgentRole.GENERAL,
        provider=ProviderType.LOCAL,
        model="fixture-model",
        metadata={
            "state_dir": str(state_dir),
            "memory_state_dir": str(state_dir),
        },
    )
    await pool.spawn(
        config,
        provider=provider,
        ontology_path=tmp_path / "ontology.db",
        advanced_memory=memory,
    )
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=tmp_path / "ledgers",
        runtime_db_path=tmp_path / "runtime.db",
        shared_dir=tmp_path / "shared",
        stigmergy_dir=tmp_path / "stigmergy",
        session_id=OWNER_SESSION_ID,
    )
    boundary = _MissionBoundary(control)
    adapter = OrchestratorMissionAdapter(
        orchestrator,
        boundary,  # type: ignore[arg-type]
        board,
        runtime,
    )

    try:
        ref = await adapter.dispatch(MISSION_ID, task_view.task_id)
        observation = await adapter.wait(
            ref,
            timeout_seconds=20,
            poll_interval_seconds=0.02,
        )
        recovered = await adapter.dispatch(MISSION_ID, task_view.task_id)

        assert recovered == ref
        assert ref.owner_session_id == OWNER_SESSION_ID
        assert ref.owner_session_id != f"mission:{MISSION_ID}"
        assert observation.task_status == TaskStatus.COMPLETED
        assert observation.run_status == "completed"
        assert observation.claim_status == "completed"
        assert observation.terminal is True
        assert observation.succeeded is True
        assert observation.proves_executor_liveness is False
        assert "Hermetic owner execution" in observation.result
        assert len(provider.requests) == 1
        assert boundary.lifecycle_calls == 0

        runs = await runtime.list_delegation_runs(
            task_id=task_view.task_id,
            limit=20,
        )
        identities = [
            await runtime.get_execution_identity(run.run_id) for run in runs
        ]
        assert [run.run_id for run in runs] == [ref.run_id]
        assert identities[0] is not None
        assert identities[0].idempotency_key == ref.idempotency_key
    finally:
        await asyncio.sleep(0.05)
        await pool.shutdown_all()
        memory.close()


@pytest.mark.asyncio
async def test_retry_recovers_durable_owner_without_dispatch(tmp_path: Path) -> None:
    board, runtime, control, task = await _stack(tmp_path)
    run_id, idempotency_key = _expected(task.task_id)
    expected = await _record_owner_execution(
        runtime,
        task_id=task.task_id,
        run_id=run_id,
        idempotency_key=idempotency_key,
        claim_id="owner-claim",
        agent_id="owner-agent",
        owner_session_id=OWNER_SESSION_ID,
    )
    orchestrator = _NoDispatch()
    adapter = OrchestratorMissionAdapter(
        orchestrator,  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )

    recovered = await adapter.dispatch(MISSION_ID, task.task_id)

    assert recovered == expected
    assert orchestrator.calls == 0


@pytest.mark.asyncio
async def test_duplicate_idempotency_matches_fail_closed(tmp_path: Path) -> None:
    board, runtime, control, task = await _stack(tmp_path)
    run_id, idempotency_key = _expected(task.task_id)
    await _record_owner_execution(
        runtime,
        task_id=task.task_id,
        run_id=run_id,
        idempotency_key=idempotency_key,
        claim_id="claim-a",
        agent_id="agent-a",
        owner_session_id="owner-a",
    )
    await _record_owner_execution(
        runtime,
        task_id=task.task_id,
        run_id="duplicate-owner-run",
        idempotency_key=idempotency_key,
        claim_id="claim-b",
        agent_id="agent-b",
        owner_session_id="owner-b",
    )
    orchestrator = _NoDispatch()
    adapter = OrchestratorMissionAdapter(
        orchestrator,  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )

    with pytest.raises(MissionControlError, match="ambiguous"):
        await adapter.dispatch(MISSION_ID, task.task_id)
    assert orchestrator.calls == 0


@pytest.mark.asyncio
async def test_foreign_active_orchestrator_run_blocks_new_key(tmp_path: Path) -> None:
    board, runtime, control, task = await _stack(tmp_path)
    await _record_owner_execution(
        runtime,
        task_id=task.task_id,
        run_id="foreign-active-run",
        idempotency_key="foreign-idempotency-key",
        claim_id="foreign-active-claim",
        agent_id="foreign-agent",
        owner_session_id="foreign-owner-session",
    )
    orchestrator = _NoDispatch()
    adapter = OrchestratorMissionAdapter(
        orchestrator,  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )

    with pytest.raises(MissionControlError, match="conflicting active"):
        await adapter.dispatch(MISSION_ID, task.task_id)
    assert orchestrator.calls == 0


@pytest.mark.asyncio
async def test_saturated_run_scan_fails_before_dispatch(tmp_path: Path) -> None:
    board, runtime, control, task = await _stack(tmp_path)
    for index in range(2):
        await runtime.record_delegation_run(
            DelegationRun(
                run_id=f"foreign-run-{index}",
                task_id=task.task_id,
                assigned_to=f"agent-{index}",
                assigned_by="foreign",
            )
        )
    orchestrator = _NoDispatch()
    adapter = OrchestratorMissionAdapter(
        orchestrator,  # type: ignore[arg-type]
        control,
        board,
        runtime,
        scan_limit=2,
    )

    with pytest.raises(MissionControlError, match="scan saturated"):
        await adapter.dispatch(MISSION_ID, task.task_id)
    assert orchestrator.calls == 0


@pytest.mark.asyncio
async def test_exactly_one_dispatch_result_is_required(tmp_path: Path) -> None:
    board, runtime, control, task = await _stack(tmp_path)
    orchestrator = _ManyDispatches()
    adapter = OrchestratorMissionAdapter(
        orchestrator,  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )

    with pytest.raises(MissionControlError, match="exactly one"):
        await adapter.dispatch(MISSION_ID, task.task_id)
    assert orchestrator.calls == 1


@pytest.mark.asyncio
async def test_unfinished_dependency_blocks_owner_dispatch(tmp_path: Path) -> None:
    board, runtime, control, dependency = await _stack(tmp_path)
    dependent = await control.create_task(
        MISSION_ID,
        title="Dependent task",
        depends_on=[dependency.task_id],
    )
    orchestrator = _NoDispatch()
    adapter = OrchestratorMissionAdapter(
        orchestrator,  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )

    with pytest.raises(MissionControlError, match="dependency"):
        await adapter.dispatch(MISSION_ID, dependent.task_id)
    assert orchestrator.calls == 0


@pytest.mark.asyncio
async def test_observe_is_read_only_and_never_claims_liveness(tmp_path: Path) -> None:
    board, runtime, control, task = await _stack(tmp_path)
    await board.assign(task.task_id, "owner-agent")
    await board.start(task.task_id)
    run_id, idempotency_key = _expected(task.task_id)
    ref = await _record_owner_execution(
        runtime,
        task_id=task.task_id,
        run_id=run_id,
        idempotency_key=idempotency_key,
        claim_id="owner-claim",
        agent_id="owner-agent",
        owner_session_id=OWNER_SESSION_ID,
    )
    adapter = OrchestratorMissionAdapter(
        _NoDispatch(),  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )
    task_before = await board.get(task.task_id)
    run_before = await runtime.get_delegation_run(run_id)
    claim_before = await runtime.get_task_claim(ref.claim_id)

    first = await adapter.observe(ref)
    second = await adapter.observe(ref)

    assert first.terminal is False
    assert first.proves_executor_liveness is False
    assert second.proves_executor_liveness is False
    assert await board.get(task.task_id) == task_before
    assert await runtime.get_delegation_run(run_id) == run_before
    assert await runtime.get_task_claim(ref.claim_id) == claim_before


@pytest.mark.asyncio
async def test_wait_is_bounded_and_read_only(tmp_path: Path) -> None:
    board, runtime, control, task = await _stack(tmp_path)
    await board.assign(task.task_id, "owner-agent")
    await board.start(task.task_id)
    run_id, idempotency_key = _expected(task.task_id)
    ref = await _record_owner_execution(
        runtime,
        task_id=task.task_id,
        run_id=run_id,
        idempotency_key=idempotency_key,
        claim_id="owner-claim",
        agent_id="owner-agent",
        owner_session_id=OWNER_SESSION_ID,
    )
    adapter = OrchestratorMissionAdapter(
        _NoDispatch(),  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )
    claim_before = await runtime.get_task_claim(ref.claim_id)

    with pytest.raises(TimeoutError, match="did not become terminal"):
        await adapter.wait(
            ref,
            timeout_seconds=0.02,
            poll_interval_seconds=0.005,
        )

    assert await runtime.get_task_claim(ref.claim_id) == claim_before


@pytest.mark.asyncio
async def test_observe_rejects_forged_dispatch_key(tmp_path: Path) -> None:
    board, runtime, control, task = await _stack(tmp_path)
    await board.assign(task.task_id, "owner-agent")
    await board.start(task.task_id)
    run_id, idempotency_key = _expected(task.task_id)
    ref = await _record_owner_execution(
        runtime,
        task_id=task.task_id,
        run_id=run_id,
        idempotency_key=idempotency_key,
        claim_id="owner-claim",
        agent_id="owner-agent",
        owner_session_id=OWNER_SESSION_ID,
    )
    adapter = OrchestratorMissionAdapter(
        _NoDispatch(),  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )

    with pytest.raises(MissionControlError, match="stable dispatch key"):
        await adapter.observe(replace(ref, dispatch_key="forged"))


@pytest.mark.asyncio
async def test_stale_is_owner_evidence_not_liveness_proof(tmp_path: Path) -> None:
    board, runtime, control, task = await _stack(tmp_path)
    await board.assign(task.task_id, "owner-agent")
    await board.start(task.task_id)
    run_id, idempotency_key = _expected(task.task_id)
    ref = await _record_owner_execution(
        runtime,
        task_id=task.task_id,
        run_id=run_id,
        idempotency_key=idempotency_key,
        claim_id="owner-claim",
        agent_id="owner-agent",
        owner_session_id=OWNER_SESSION_ID,
    )
    claim = await runtime.get_task_claim(ref.claim_id)
    assert claim is not None
    await runtime.record_task_claim(
        replace(claim, stale_after=utc_now() - timedelta(seconds=1))
    )
    adapter = OrchestratorMissionAdapter(
        _NoDispatch(),  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )

    observation = await adapter.observe(ref)

    assert observation.stale is True
    assert observation.proves_executor_liveness is False


def test_invalid_scan_budget_fails_fast() -> None:
    with pytest.raises(ValueError, match="scan_limit"):
        OrchestratorMissionAdapter(  # type: ignore[arg-type]
            _NoDispatch(),
            object(),
            object(),
            object(),
            scan_limit=1,
        )


@pytest.mark.asyncio
async def test_invalid_wait_budget_fails_before_owner_reads() -> None:
    adapter = OrchestratorMissionAdapter(  # type: ignore[arg-type]
        _NoDispatch(),
        object(),
        object(),
        object(),
    )
    ref = OwnerExecutionRef(
        backend=OWNER_BACKEND,
        mission_id=MISSION_ID,
        task_id="task-id",
        dispatch_key=DISPATCH_KEY,
        run_id="run-id",
        claim_id="claim-id",
        agent_id="agent-id",
        idempotency_key="idempotency-key",
        owner_session_id=OWNER_SESSION_ID,
    )

    with pytest.raises(ValueError, match="timeout_seconds"):
        await adapter.wait(ref, timeout_seconds=0)
