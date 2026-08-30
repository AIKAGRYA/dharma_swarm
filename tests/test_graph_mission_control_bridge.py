"""Adversarial contracts for the shadow Mission Control graph bridge."""

from __future__ import annotations

import asyncio
import multiprocessing
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm.graph.errors import NodeExecutionError
from dharma_swarm.graph.mission_control_bridge import (
    GRAPH_ID,
    PROGRAM_DIGEST,
    PRODUCTION_PROMOTION_BLOCKER,
    MissionAuthorityDenied,
    MissionControlGraphBridge,
    MissionDispatchGrant,
    MissionDispatchRequest,
    MissionGraphError,
    MissionObservationPending,
    MissionPlanChanged,
    MissionThreadBusy,
    mission_plan_digest,
)
from dharma_swarm.graph.persistence import (
    GraphCheckpointConflictError,
    GraphPersistenceKernel,
)
from dharma_swarm.graph.types import RunCheckpoint
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_contract import stable_id
from dharma_swarm.mission_control_execution import (
    OrchestratorMissionAdapter,
    OwnerExecutionObservation,
    OwnerExecutionRef,
)
from dharma_swarm.mission_control_execution_support import OWNER_BACKEND
from dharma_swarm.models import TaskDispatch, TaskStatus, TopologyType
from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard

_EXECUTION_STAMP_KEYS = frozenset(
    {
        "mission_control_owner_execution",
        "runtime_run_id",
        "run_id",
        "idempotency_key",
        "trace_id",
        "correlation_id",
        "execution_identity",
    }
)


class _TaskBoardPlanSource:
    """Digest task intent while excluding only execution-owned stamp fields."""

    def __init__(self, board: TaskBoard) -> None:
        self.board = board

    async def current_plan_digest(self, mission_id, task_id, dispatch_key):
        task = await self.board.get(task_id)
        if task is None or task.metadata.get("mission_id") != mission_id:
            raise MissionGraphError("fixture plan source found a foreign task")
        plan_metadata = {
            key: value
            for key, value in task.metadata.items()
            if key not in _EXECUTION_STAMP_KEYS
        }
        return mission_plan_digest(
            {
                "mission_id": mission_id,
                "task_id": task.id,
                "dispatch_key": dispatch_key,
                "title": task.title,
                "description": task.description,
                "priority": task.priority.value,
                "created_by": task.created_by,
                "depends_on": sorted(task.depends_on),
                "metadata": plan_metadata,
            }
        )


class _StaticPlanSource:
    def __init__(self, **plan) -> None:
        self.plan = plan or {"task": "bounded-effect-v1"}

    async def current_plan_digest(self, mission_id, task_id, dispatch_key):
        return mission_plan_digest(
            {
                "mission_id": mission_id,
                "task_id": task_id,
                "dispatch_key": dispatch_key,
                **self.plan,
            }
        )


class _ExactMissionAuthority:
    """Fixture authority with a real, revocable grant registry."""

    def __init__(self, now: datetime) -> None:
        self.now = now
        self.authorize_calls = 0
        self.validate_calls = 0
        self.revoked = False
        self.grants: dict[str, MissionDispatchGrant] = {}

    async def authorize(self, request: MissionDispatchRequest) -> MissionDispatchGrant:
        self.authorize_calls += 1
        grant = MissionDispatchGrant(
            grant_id=stable_id(
                "mission_grant", request.scope_digest, str(self.authorize_calls)
            ),
            principal_id="operator:test",
            mission_id=request.mission_id,
            task_id=request.task_id,
            dispatch_key=request.dispatch_key,
            graph_id=request.graph_id,
            program_digest=request.program_digest,
            plan_digest=request.plan_digest,
            graph_run_id=request.graph_run_id,
            thread_id=request.thread_id,
            scope_digest=request.scope_digest,
            issued_at=self.now,
            expires_at=self.now + timedelta(minutes=5),
        )
        self.grants[grant.grant_id] = grant
        return grant

    async def validate(
        self, request: MissionDispatchRequest, grant: MissionDispatchGrant
    ) -> bool:
        self.validate_calls += 1
        return (
            not self.revoked
            and self.grants.get(grant.grant_id) == grant
            and grant.scope_digest == request.scope_digest
        )


class _DeniedMissionAuthority(_ExactMissionAuthority):
    async def authorize(self, request: MissionDispatchRequest) -> MissionDispatchGrant:
        self.authorize_calls += 1
        raise MissionAuthorityDenied("fixture denied")


class _DurableOwnerStub:
    """Canonical-owner-shaped effect whose durable rows support recovery."""

    def __init__(self, runtime: RuntimeStateStore, mission_id: str) -> None:
        self.runtime = runtime
        self.mission_id = mission_id
        self.calls = 0

    async def dispatch(self, task, topology):
        self.calls += 1
        run_id = task.metadata["runtime_run_id"]
        idempotency_key = task.metadata["idempotency_key"]
        agent_id = "mission-graph-owner"
        claim_id = stable_id("mission_graph_claim", run_id)
        session_id = "mission-graph-owner-session"
        identity = ExecutionIdentity.new(
            trace_id=task.metadata["trace_id"],
            correlation_id=task.metadata["correlation_id"],
            task_id=task.id,
            run_id=run_id,
            claim_id=claim_id,
            agent_id=agent_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
        )
        await self.runtime.record_execution_identity(
            identity, source="mission-graph-test-owner"
        )
        await self.runtime.record_task_claim(
            TaskClaim(
                claim_id=claim_id,
                task_id=task.id,
                agent_id=agent_id,
                session_id=session_id,
                status="running",
                stale_after=datetime.now(timezone.utc) + timedelta(minutes=5),
                metadata={"mission_id": self.mission_id},
            )
        )
        await self.runtime.record_delegation_run(
            DelegationRun(
                run_id=run_id,
                task_id=task.id,
                assigned_to=agent_id,
                assigned_by=OWNER_BACKEND,
                claim_id=claim_id,
                session_id=session_id,
                status="running",
                metadata={
                    "mission_id": self.mission_id,
                    "topology": TopologyType.PIPELINE.value,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        return [
            TaskDispatch(
                task_id=task.id,
                agent_id=agent_id,
                topology=topology,
                metadata=dict(task.metadata),
            )
        ]


class _CrashAfterOwnerDispatch:
    def __init__(self, inner: OrchestratorMissionAdapter) -> None:
        self.inner = inner
        self.crash_once = True
        self.dispatch_calls = 0

    async def dispatch(self, mission_id, task_id, *, dispatch_key="default"):
        self.dispatch_calls += 1
        ref = await self.inner.dispatch(mission_id, task_id, dispatch_key=dispatch_key)
        if self.crash_once:
            self.crash_once = False
            raise RuntimeError("fixture crash after durable owner dispatch")
        return ref

    async def observe(self, ref):
        return await self.inner.observe(ref)


class _ScriptedExecution:
    def __init__(self, *states: str) -> None:
        self.states = list(states or ("completed",))
        self.dispatch_calls = 0
        self.observe_calls = 0
        self.ref: OwnerExecutionRef | None = None

    async def dispatch(self, mission_id, task_id, *, dispatch_key="default"):
        self.dispatch_calls += 1
        self.ref = OwnerExecutionRef(
            backend="fixture",
            mission_id=mission_id,
            task_id=task_id,
            dispatch_key=dispatch_key,
            run_id=stable_id("fixture_run", mission_id, task_id, dispatch_key),
            claim_id=stable_id("fixture_claim", mission_id, task_id, dispatch_key),
            agent_id="fixture-agent",
            idempotency_key=stable_id(
                "fixture_idempotency", mission_id, task_id, dispatch_key
            ),
            owner_session_id="fixture-session",
        )
        return self.ref

    async def observe(self, ref):
        self.observe_calls += 1
        state = self.states[min(self.observe_calls - 1, len(self.states) - 1)]
        if state == "completed":
            status, terminal, succeeded, proves = (
                TaskStatus.COMPLETED,
                True,
                True,
                False,
            )
        elif state == "running":
            status, terminal, succeeded, proves = (
                TaskStatus.RUNNING,
                False,
                False,
                False,
            )
        elif state == "malformed":
            status, terminal, succeeded, proves = TaskStatus.RUNNING, False, True, False
        elif state == "false-liveness":
            status, terminal, succeeded, proves = TaskStatus.RUNNING, False, False, True
        else:
            raise AssertionError(f"unknown scripted observation state {state!r}")
        return OwnerExecutionObservation(
            ref=ref,
            task_status=status,
            run_status=status.value,
            claim_status=status.value,
            stale=False,
            receipt_ids=(),
            terminal=terminal,
            succeeded=succeeded,
            result="done" if succeeded else "",
            failure_code="",
            observed_at=datetime(2026, 8, 13, tzinfo=timezone.utc),
            proves_executor_liveness=proves,
        )


def _hold_graph_run_lease(persist_dir: str, thread_id: str, ready, release) -> None:
    kernel = GraphPersistenceKernel(Path(persist_dir))
    with kernel.run_lease(thread_id):
        ready.set()
        if not release.wait(10):
            raise RuntimeError("fixture timed out waiting to release graph lease")


def _acquire_graph_run_lease_and_exit(persist_dir: str, thread_id: str, ready) -> None:
    kernel = GraphPersistenceKernel(Path(persist_dir))
    with kernel.run_lease(thread_id):
        ready.set()
        os._exit(0)


async def _mission_graph_stack(tmp_path: Path):
    mission_id = "mission-graph-alpha"
    board = TaskBoard(tmp_path / "mission-tasks.db")
    runtime = RuntimeStateStore(
        tmp_path / "mission-runtime.db", include_memory_plane=False
    )
    await board.init_db()
    await runtime.init_db()
    control = MissionControl(board, runtime)
    await control.create_mission(
        mission_id,
        title="Mission Graph Alpha",
        goal="Prove authority-gated durable owner recovery",
    )
    task = await control.create_task(
        mission_id,
        title="Execute exactly one bounded effect",
        description="Exercise the real Mission Control owner adapter.",
        idempotency_key="mission-graph-alpha-task",
    )
    owner = _DurableOwnerStub(runtime, mission_id)
    adapter = OrchestratorMissionAdapter(
        owner,  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )
    return mission_id, task.task_id, board, owner, adapter


def _bridge(
    execution,
    authority,
    persistence,
    plan_source,
    *,
    clock,
    polls=2,
):
    return MissionControlGraphBridge(
        execution,
        authority,
        persistence,
        plan_source=plan_source,
        clock=clock,
        max_observation_polls=polls,
        observation_poll_delay=0,
    )


async def test_mission_graph_denied_authority_makes_zero_owner_calls(tmp_path: Path):
    mission_id, task_id, board, owner, adapter = await _mission_graph_stack(tmp_path)
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    bridge = _bridge(
        adapter,
        _DeniedMissionAuthority(now),
        GraphPersistenceKernel(tmp_path / "denied-graph"),
        _TaskBoardPlanSource(board),
        clock=lambda: now,
    )

    with pytest.raises(NodeExecutionError, match="fixture denied"):
        await bridge.run(mission_id, task_id)

    assert owner.calls == 0


async def test_mission_graph_crash_resumes_same_owner_without_duplicate_effect(
    tmp_path: Path,
):
    mission_id, task_id, board, owner, adapter = await _mission_graph_stack(tmp_path)
    crashing = _CrashAfterOwnerDispatch(adapter)
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    authority = _ExactMissionAuthority(now)
    persist_dir = tmp_path / "mission-graph"
    first = _bridge(
        crashing,
        authority,
        GraphPersistenceKernel(persist_dir),
        _TaskBoardPlanSource(board),
        clock=lambda: now,
        polls=1,
    )

    with pytest.raises(NodeExecutionError, match="crash after durable owner dispatch"):
        await first.run(mission_id, task_id)
    assert owner.calls == 1
    assert authority.authorize_calls == 1
    assert authority.validate_calls == 1

    authority.revoked = True
    blocked = _bridge(
        crashing,
        authority,
        GraphPersistenceKernel(persist_dir),
        _TaskBoardPlanSource(board),
        clock=lambda: now,
        polls=1,
    )
    with pytest.raises(NodeExecutionError, match="pre-effect boundary"):
        await blocked.resume(mission_id, task_id)
    assert owner.calls == 1

    authority.revoked = False
    resumed = _bridge(
        crashing,
        authority,
        GraphPersistenceKernel(persist_dir),
        _TaskBoardPlanSource(board),
        clock=lambda: now,
        polls=1,
    )
    with pytest.raises(NodeExecutionError, match="bounded observation budget"):
        await resumed.resume(mission_id, task_id)

    assert owner.calls == 1
    assert crashing.dispatch_calls == 2
    assert authority.authorize_calls == 1
    assert authority.validate_calls == 3
    latest = GraphPersistenceKernel(persist_dir).get_checkpoint_record(
        MissionDispatchRequest.thread_id_for(mission_id, task_id)
    )
    assert latest is not None
    assert latest.state["owner_observation"]["terminal"] is False


def test_mission_request_scope_binds_program_and_plan_digest():
    first = MissionDispatchRequest.create(
        "mission-a", "task-a", mission_plan_digest({"description": "first"})
    )
    changed = MissionDispatchRequest.create(
        "mission-a", "task-a", mission_plan_digest({"description": "changed"})
    )
    assert first.graph_id == GRAPH_ID
    assert first.program_digest == PROGRAM_DIGEST
    assert first.thread_id == changed.thread_id
    assert first.graph_run_id != changed.graph_run_id
    assert first.scope_digest != changed.scope_digest


async def test_shadow_plan_reread_precedes_adapter_but_does_not_span_effect(
    tmp_path: Path,
):
    """Mechanical counterexample for the explicit production-promotion blocker."""

    events: list[str] = []

    class RecordingPlanSource(_StaticPlanSource):
        async def current_plan_digest(self, mission_id, task_id, dispatch_key):
            events.append("plan_reread")
            return await super().current_plan_digest(mission_id, task_id, dispatch_key)

    plan_source = RecordingPlanSource(task="admitted-plan")

    class MutatingExecution(_ScriptedExecution):
        async def dispatch(self, mission_id, task_id, *, dispatch_key="default"):
            events.append("adapter_entered")
            plan_source.plan["task"] = "mutated-after-adapter-entry"
            return await super().dispatch(
                mission_id, task_id, dispatch_key=dispatch_key
            )

    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    result = await _bridge(
        MutatingExecution("completed"),
        _ExactMissionAuthority(now),
        GraphPersistenceKernel(tmp_path / "shadow-race-boundary"),
        plan_source,
        clock=lambda: now,
    ).run("mission-a", "task-a")

    assert events[-2:] == ["plan_reread", "adapter_entered"]
    current = await plan_source.current_plan_digest("mission-a", "task-a", "default")
    assert current != result.request.plan_digest
    assert "atomic TaskBoard owner CAS" in PRODUCTION_PROMOTION_BLOCKER
    assert result.observation.terminal is True


async def test_mission_graph_rejects_task_mutation_after_grant(tmp_path: Path):
    mission_id, task_id, board, owner, adapter = await _mission_graph_stack(tmp_path)
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    authority = _ExactMissionAuthority(now)
    authority.revoked = True
    persistence = GraphPersistenceKernel(tmp_path / "plan-change")
    bridge = _bridge(
        adapter,
        authority,
        persistence,
        _TaskBoardPlanSource(board),
        clock=lambda: now,
    )
    with pytest.raises(NodeExecutionError, match="pre-effect boundary"):
        await bridge.run(mission_id, task_id)
    await board.update_task(task_id, description="MUTATED AFTER GRANT")
    authority.revoked = False

    with pytest.raises(NodeExecutionError, match="task plan changed") as exc_info:
        await bridge.resume(mission_id, task_id)

    assert isinstance(exc_info.value.__cause__, MissionPlanChanged)
    assert owner.calls == 0
    assert authority.validate_calls == 1


async def test_mission_graph_rejects_foreign_graph_checkpoint(tmp_path: Path):
    plan_source = _StaticPlanSource()
    plan_digest = await plan_source.current_plan_digest(
        "mission-a", "task-a", "default"
    )
    request = MissionDispatchRequest.create("mission-a", "task-a", plan_digest)
    persistence = GraphPersistenceKernel(tmp_path / "foreign-graph")
    persistence.put_run_checkpoint(
        request.thread_id,
        RunCheckpoint(
            graph_run_id=request.graph_run_id,
            graph_id="foreign-graph.v1",
            superstep=0,
            state_digest="sha256:foreign",
            channels={},
            versions_seen={},
        ),
    )
    execution = _ScriptedExecution()
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    bridge = _bridge(
        execution,
        _ExactMissionAuthority(now),
        persistence,
        plan_source,
        clock=lambda: now,
    )

    with pytest.raises(MissionGraphError, match="checkpoint graph_id"):
        await bridge.resume("mission-a", "task-a")
    assert execution.dispatch_calls == 0


async def test_mission_graph_rejects_foreign_run_checkpoint(tmp_path: Path):
    plan_source = _StaticPlanSource()
    plan_digest = await plan_source.current_plan_digest(
        "mission-a", "task-a", "default"
    )
    request = MissionDispatchRequest.create("mission-a", "task-a", plan_digest)
    persistence = GraphPersistenceKernel(tmp_path / "foreign-run")
    persistence.put_run_checkpoint(
        request.thread_id,
        RunCheckpoint(
            graph_run_id="foreign-run-id",
            graph_id=GRAPH_ID,
            superstep=0,
            state_digest="sha256:foreign-run",
            channels={
                name: {"value": value, "version": 1}
                for name, value in request.to_state().items()
            },
            versions_seen={},
        ),
    )
    execution = _ScriptedExecution()
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    bridge = _bridge(
        execution,
        _ExactMissionAuthority(now),
        persistence,
        plan_source,
        clock=lambda: now,
    )

    with pytest.raises(MissionGraphError, match="graph_run_id is foreign"):
        await bridge.resume("mission-a", "task-a")
    assert execution.dispatch_calls == 0


async def test_expired_grant_reauthorizes_in_checkpointed_generation(tmp_path: Path):
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    clock = [now]
    authority = _ExactMissionAuthority(now)
    authority.revoked = True
    execution = _ScriptedExecution("completed")
    persistence = GraphPersistenceKernel(tmp_path / "reauthorize")
    bridge = _bridge(
        execution,
        authority,
        persistence,
        _StaticPlanSource(),
        clock=lambda: clock[0],
    )
    with pytest.raises(NodeExecutionError, match="pre-effect boundary"):
        await bridge.run("mission-a", "task-a")
    first_grant_id = next(iter(authority.grants))

    clock[0] = now + timedelta(minutes=10)
    authority.now = clock[0]
    authority.revoked = False
    result = await bridge.resume("mission-a", "task-a")

    assert result.authority_generation == 2
    assert result.grant.grant_id != first_grant_id
    assert authority.authorize_calls == 2
    assert execution.dispatch_calls == 1
    history = persistence.get_state_history(result.request.thread_id)
    generations = [
        record.state.get("authority_generation")
        for record in history
        if record.state.get("authority_generation") is not None
    ]
    assert 1 in generations and 2 in generations


async def test_nonterminal_observation_polls_until_terminal(tmp_path: Path):
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    execution = _ScriptedExecution("running", "completed")
    result = await _bridge(
        execution,
        _ExactMissionAuthority(now),
        GraphPersistenceKernel(tmp_path / "poll-terminal"),
        _StaticPlanSource(),
        clock=lambda: now,
        polls=2,
    ).run("mission-a", "task-a")

    assert result.observation.terminal is True
    assert execution.observe_calls == 2
    assert execution.dispatch_calls == 1


async def test_nonterminal_budget_persists_then_resume_observes_fresh(tmp_path: Path):
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    execution = _ScriptedExecution("running", "completed")
    persistence = GraphPersistenceKernel(tmp_path / "poll-resume")
    bridge = _bridge(
        execution,
        _ExactMissionAuthority(now),
        persistence,
        _StaticPlanSource(),
        clock=lambda: now,
        polls=1,
    )
    with pytest.raises(NodeExecutionError, match="bounded observation budget") as exc:
        await bridge.run("mission-a", "task-a")
    assert isinstance(exc.value.__cause__, MissionObservationPending)

    result = await bridge.resume("mission-a", "task-a")
    assert result.observation.terminal is True
    assert execution.dispatch_calls == 1
    assert execution.observe_calls == 2


async def test_malformed_observation_is_not_checkpointed(tmp_path: Path):
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    execution = _ScriptedExecution("malformed")
    persistence = GraphPersistenceKernel(tmp_path / "malformed-observation")
    bridge = _bridge(
        execution,
        _ExactMissionAuthority(now),
        persistence,
        _StaticPlanSource(),
        clock=lambda: now,
    )
    with pytest.raises(NodeExecutionError, match="success semantics"):
        await bridge.run("mission-a", "task-a")

    thread_id = MissionDispatchRequest.thread_id_for("mission-a", "task-a")
    latest = persistence.get_checkpoint_record(thread_id)
    assert latest is not None
    assert "owner_observation" not in latest.state
    assert execution.observe_calls == 1


async def test_two_concurrent_resumes_admit_only_one_runner(tmp_path: Path):
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    authority = _ExactMissionAuthority(now)
    authority.revoked = True
    plan_source = _StaticPlanSource()
    persist_dir = tmp_path / "same-process-lease"
    seed_execution = _ScriptedExecution()
    seed = _bridge(
        seed_execution,
        authority,
        GraphPersistenceKernel(persist_dir),
        plan_source,
        clock=lambda: now,
    )
    with pytest.raises(NodeExecutionError, match="pre-effect boundary"):
        await seed.run("mission-a", "task-a")
    authority.revoked = False

    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingExecution(_ScriptedExecution):
        async def dispatch(self, mission_id, task_id, *, dispatch_key="default"):
            ref = await super().dispatch(mission_id, task_id, dispatch_key=dispatch_key)
            entered.set()
            await release.wait()
            return ref

    execution = BlockingExecution("completed")
    first = _bridge(
        execution,
        authority,
        GraphPersistenceKernel(persist_dir),
        plan_source,
        clock=lambda: now,
    )
    second = _bridge(
        execution,
        authority,
        GraphPersistenceKernel(persist_dir),
        plan_source,
        clock=lambda: now,
    )
    winner = asyncio.create_task(first.resume("mission-a", "task-a"))
    await asyncio.wait_for(entered.wait(), timeout=2)
    with pytest.raises(MissionThreadBusy):
        await second.resume("mission-a", "task-a")
    release.set()
    result = await winner

    assert result.observation.terminal is True
    assert execution.dispatch_calls == 1


async def test_cross_process_lease_blocks_resume_before_effect(tmp_path: Path):
    now = datetime(2026, 8, 13, tzinfo=timezone.utc)
    authority = _ExactMissionAuthority(now)
    authority.revoked = True
    plan_source = _StaticPlanSource()
    persist_dir = tmp_path / "cross-process-lease"
    execution = _ScriptedExecution()
    bridge = _bridge(
        execution,
        authority,
        GraphPersistenceKernel(persist_dir),
        plan_source,
        clock=lambda: now,
    )
    with pytest.raises(NodeExecutionError, match="pre-effect boundary"):
        await bridge.run("mission-a", "task-a")
    authority.revoked = False

    thread_id = MissionDispatchRequest.thread_id_for("mission-a", "task-a")
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    process = context.Process(
        target=_hold_graph_run_lease,
        args=(str(persist_dir), thread_id, ready, release),
    )
    process.start()
    try:
        assert await asyncio.to_thread(ready.wait, 5)
        with pytest.raises(MissionThreadBusy):
            await bridge.resume("mission-a", "task-a")
        assert execution.dispatch_calls == 0
    finally:
        release.set()
        await asyncio.to_thread(process.join, 5)
    assert process.exitcode == 0


def test_graph_run_lease_releases_after_child_abrupt_exit(tmp_path: Path):
    persist_dir = tmp_path / "crash-release-lease"
    thread_id = "thread-crash-release"
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    process = context.Process(
        target=_acquire_graph_run_lease_and_exit,
        args=(str(persist_dir), thread_id, ready),
    )
    process.start()
    assert ready.wait(5)
    process.join(5)
    assert process.exitcode == 0

    with GraphPersistenceKernel(persist_dir).run_lease(thread_id):
        pass


def test_graph_checkpoint_cas_rejects_stale_parent(tmp_path: Path):
    kernel = GraphPersistenceKernel(tmp_path / "checkpoint-cas")
    first = kernel.put_run_checkpoint(
        "thread-a",
        RunCheckpoint("run-a", "graph-a", 0, "sha256:first", {}, {}),
    )
    second = kernel.put_run_checkpoint(
        "thread-a",
        RunCheckpoint("run-a", "graph-a", 1, "sha256:second", {}, {}),
        parent_checkpoint_id=first.checkpoint_id,
    )

    with pytest.raises(GraphCheckpointConflictError, match="advanced"):
        kernel.put_run_checkpoint_cas(
            "thread-a",
            RunCheckpoint("run-a", "graph-a", 2, "sha256:stale", {}, {}),
            expected_latest_checkpoint_id=first.checkpoint_id,
            parent_checkpoint_id=first.checkpoint_id,
        )
    assert kernel.get_checkpoint_record("thread-a") == second
