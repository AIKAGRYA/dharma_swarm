from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from types import SimpleNamespace
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import dharma_swarm.orchestrator as orchestrator_module
import dharma_swarm.task_board as task_board_module
from dharma_swarm.agent_memory_manager import AgentMemoryManager
from dharma_swarm.agent_runner import AgentPool
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_campaign import CampaignConfig, CampaignSupervisor
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
from dharma_swarm.mission_control_evidence import (
    EVIDENCE_DELTA_RECEIPT_TYPE,
    EvidenceDelta,
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
    RuntimeReceipt,
    RuntimeStateStore,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard
from dharma_swarm.task_board_projection_intent import stable_sha256


MISSION_ID = "mission-alpha"
OWNER_SESSION_ID = "owner-session-alpha"


def _typed_campaign_metadata(principal: str, task_id: str) -> dict[str, Any]:
    portfolio = "sha256:" + "a" * 64
    goal = "sha256:" + "b" * 64
    content = "Observed execution fixture; verify independently.\n"
    content_sha256 = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
    observed_manifest = "sha256:" + "3" * 64
    observed_ref = {
        "receipt_id": "observed-receipt-fixture",
        "receipt_sha256": "sha256:" + "4" * 64,
        "artifact_id": "observed-artifact-fixture",
        "artifact_record_sha256": "sha256:" + "5" * 64,
        "content_sha256": content_sha256,
    }
    return {
        "campaign_id": MISSION_ID,
        "goal_id": "goal-one",
        "portfolio_contract_sha256": portfolio,
        "goal_contract_sha256": goal,
        "attempt_ceiling": 3,
        "attempt_generation": 0,
        "mission_task_id": task_id,
        "mission_observed_input": {
            "schema_version": "dharma.sadhana.observed_input_prompt.v1",
            "campaign_id": MISSION_ID,
            "mission_id": MISSION_ID,
            "goal_id": "goal-one",
            "task_id": task_id,
            "manifest_digest": observed_manifest,
            "goal_contract_sha256": goal,
            "task_creation_hash": "6" * 64,
            "observed_at": "2026-08-23T00:00:00+00:00",
            "epistemic_state": "observed_unverified",
            "authority_scope": "prompt_context_only",
            "media_type": "text/markdown; charset=utf-8",
            "content": content,
            "content_sha256": content_sha256,
            "observed_input_ref": observed_ref,
        },
        "campaign_effect_mode": "read_only",
        "requires_tooling": False,
        "allow_provider_routing": False,
        "provider_allowlist": ["local"],
        "preferred_provider": "local",
        "preferred_model": "fixture-model",
        "mission_campaign_authority": {
            "schema_version": "dharma.sadhana.campaign_task_authority.v5",
            "campaign_id": MISSION_ID,
            "mission_id": MISSION_ID,
            "goal_id": "goal-one",
            "portfolio_contract_sha256": portfolio,
            "goal_contract_sha256": goal,
            "manifest_digest": "sha256:" + "c" * 64,
            "agent_roster_sha256": "d" * 64,
            "effect_mode": "read_only",
            "campaign_end": "2026-09-02T00:00:00+00:00",
            "agent_name": "campaign-seat",
            "claimed_principal": principal,
            "dispatch_key": "default",
            "request_id": "request-fixture",
            "workspace_path": "workspaces/goal-one",
            "allowed_files": ["workspaces/goal-one/**"],
            "max_usd": 0.0,
            "authority_ref": "lease-fixture",
            "authority_digest": "sha256:" + "e" * 64,
            "attempt_generation": 0,
            "max_attempts": 3,
            "observed_input_manifest_digest": observed_manifest,
            "held_out_oracle_manifest_digest": "sha256:" + "7" * 64,
            "operator_control_semantics_sha256": "sha256:" + "8" * 64,
            "operator_control_authority_binding_sha256": "sha256:" + "9" * 64,
            "deployment_authority_topology_sha256": "sha256:" + "0" * 64,
            "deployment_authority_credential_clarification_sha256": (
                "sha256:" + "1" * 64
            ),
            "observed_input_ref": observed_ref,
            "route_lock": {
                "schema_version": "dharma.sadhana.campaign_route_lock.v1",
                "task_id": task_id,
                "principal_id": principal,
                "provider": "local",
                "model": "fixture-model",
                "allow_provider_routing": False,
            },
        },
    }
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


class _CapturingDispatch:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    async def dispatch(self, task, topology, **kwargs):
        self.kwargs = kwargs
        return []


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

    from dharma_swarm.graph import reconcile_board as reconcile_board_module

    real_settle_task_board = reconcile_board_module.settle_task_board
    projection_settlement_started = asyncio.Event()
    projection_settlement_finished = asyncio.Event()
    release_projection_settlement = asyncio.Event()
    settlement_calls = 0

    async def _paused_settle_task_board(*args: Any, **kwargs: Any) -> None:
        nonlocal settlement_calls
        settlement_calls += 1
        projection_settlement_started.set()
        await release_projection_settlement.wait()
        try:
            await real_settle_task_board(*args, **kwargs)
        finally:
            projection_settlement_finished.set()

    monkeypatch.setattr(
        reconcile_board_module,
        "settle_task_board",
        _paused_settle_task_board,
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
        real_observe = adapter.observe
        pending_observations = 0
        pending_observed = asyncio.Event()

        async def _counted_observe(owner_ref: OwnerExecutionRef):
            nonlocal pending_observations
            if pending_observed.is_set() and not projection_settlement_finished.is_set():
                await projection_settlement_finished.wait()
            observed = await real_observe(owner_ref)
            if observed.run_status == "completed" and not observed.terminal:
                pending_observations += 1
                pending_observed.set()
            return observed

        monkeypatch.setattr(adapter, "observe", _counted_observe)
        waiter = asyncio.create_task(
            adapter.wait(
                ref,
                timeout_seconds=20,
                poll_interval_seconds=0.005,
            )
        )
        await asyncio.wait_for(projection_settlement_started.wait(), timeout=20)
        await asyncio.wait_for(pending_observed.wait(), timeout=20)
        assert waiter.done() is False

        pending = await real_observe(ref)
        assert pending.run_status == "completed"
        assert pending.task_status == TaskStatus.RUNNING
        assert pending.terminal is False
        assert pending.succeeded is False

        terminal_run = await runtime.get_delegation_run(ref.run_id)
        assert terminal_run is not None
        original_get_run = runtime.get_delegation_run
        intent_key = "task_board_projection_intent"
        original_intent = terminal_run.metadata[intent_key]
        forged_digest_intent = {
            **original_intent,
            "runtime_authority_snapshot_sha256": "f" * 64,
        }
        forged_digest_intent["intent_sha256"] = stable_sha256(
            {
                key: value
                for key, value in forged_digest_intent.items()
                if key != "intent_sha256"
            }
        )
        forged_binding_intent = {
            **original_intent,
            "completion_binding": {
                **original_intent["completion_binding"],
                "receipt_id": "foreign-runtime-receipt",
            },
        }
        forged_binding_intent["intent_sha256"] = stable_sha256(
            {
                key: value
                for key, value in forged_binding_intent.items()
                if key != "intent_sha256"
            }
        )

        for forged_metadata in (
            {
                key: value
                for key, value in terminal_run.metadata.items()
                if key != intent_key
            },
            {
                **terminal_run.metadata,
                intent_key: {
                    **terminal_run.metadata[intent_key],
                    "intent_sha256": "0" * 64,
                },
            },
            {**terminal_run.metadata, intent_key: forged_digest_intent},
            {**terminal_run.metadata, intent_key: forged_binding_intent},
        ):
            forged_run = replace(terminal_run, metadata=forged_metadata)

            async def _forged_get_run(run_id: str) -> DelegationRun | None:
                if run_id == ref.run_id:
                    return forged_run
                return await original_get_run(run_id)

            with monkeypatch.context() as context:
                context.setattr(runtime, "get_delegation_run", _forged_get_run)
                with pytest.raises(
                    MissionControlError,
                    match="terminal owner run conflicts",
                ):
                    await real_observe(ref)

        # Persist fully self-consistent forgeries so the negative control
        # proves authority is re-derived from runtime truth, rather than only
        # comparing the observer's in-memory run with the durable row.
        for forged_intent in (forged_digest_intent, forged_binding_intent):
            with sqlite3.connect(runtime.db_path) as db:
                db.execute(
                    "UPDATE delegation_runs SET metadata_json = ? WHERE run_id = ?",
                    (
                        json.dumps(
                            {**terminal_run.metadata, intent_key: forged_intent},
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        ref.run_id,
                    ),
                )
                db.commit()
            try:
                with pytest.raises(
                    MissionControlError,
                    match="terminal owner run conflicts",
                ):
                    await real_observe(ref)
            finally:
                with sqlite3.connect(runtime.db_path) as db:
                    db.execute(
                        "UPDATE delegation_runs SET metadata_json = ? WHERE run_id = ?",
                        (
                            json.dumps(
                                terminal_run.metadata,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            ref.run_id,
                        ),
                    )
                    db.commit()

        board_task = await board.get(ref.task_id)
        assert board_task is not None
        original_board_get = board.get
        mismatched_identity = dict(board_task.metadata["execution_identity"])
        mismatched_identity["run_id"] = "foreign-run"
        forged_board_task = board_task.model_copy(
            update={
                "metadata": {
                    **board_task.metadata,
                    "execution_identity": mismatched_identity,
                }
            }
        )

        async def _forged_board_get(task_id: str):
            if task_id == ref.task_id:
                return forged_board_task
            return await original_board_get(task_id)

        with monkeypatch.context() as context:
            context.setattr(board, "get", _forged_board_get)
            with pytest.raises(
                MissionControlError,
                match="terminal owner run conflicts",
            ):
                await real_observe(ref)

        assert (await real_observe(ref)).terminal is False
        release_projection_settlement.set()
        observation = await waiter

        # A structurally exact runtime witness is still not Board authority.
        # Replace its embedded receipt with a different self-consistent receipt
        # and prove Mission Control compares it to the canonical Board ledger.
        from dharma_swarm.graph.reconcile_board_proof import (
            validate_atomic_graph_projection_commit,
        )
        from dharma_swarm.graph.reconcile_board_replay import _projection_marker
        from dharma_swarm.task_board_effect_commit import (
            graph_projection_effect_id,
            load_board_effect_commit,
        )

        terminal_run = await runtime.get_delegation_run(ref.run_id)
        assert terminal_run is not None
        exact_intent = terminal_run.metadata[intent_key]
        exact_marker = _projection_marker(exact_intent)
        board_receipt = await load_board_effect_commit(
            board,
            effect_id=graph_projection_effect_id(ref.run_id),
        )
        assert board_receipt is not None
        foreign_receipt = json.loads(json.dumps(board_receipt))
        foreign_receipt["committed_at"] = "2026-08-24T09:30:00+00:00"
        foreign_receipt["target_snapshot"]["updated_at"] = (
            foreign_receipt["committed_at"]
        )
        foreign_receipt["receipt_sha256"] = stable_sha256(
            {
                key: value
                for key, value in foreign_receipt.items()
                if key != "receipt_sha256"
            }
        )
        assert validate_atomic_graph_projection_commit(
            foreign_receipt,
            intent=exact_intent,
            marker=exact_marker,
        ) == foreign_receipt
        def canonical(value: Any) -> str:
            return json.dumps(value, sort_keys=True, separators=(",", ":"))
        with sqlite3.connect(runtime.db_path) as db:
            db.execute("DROP TRIGGER task_board_atomic_projection_witness_no_update")
            db.execute(
                "UPDATE task_board_atomic_projection_witnesses"
                " SET board_receipt_sha256 = ?, board_receipt_json = ?"
                " WHERE run_id = ?",
                (
                    foreign_receipt["receipt_sha256"],
                    canonical(foreign_receipt),
                    ref.run_id,
                ),
            )
            db.commit()
        try:
            with pytest.raises(
                MissionControlError,
                match="terminal owner run conflicts",
            ):
                await real_observe(ref)
        finally:
            with sqlite3.connect(runtime.db_path) as db:
                db.execute(
                    "DROP TRIGGER task_board_atomic_projection_witness_no_update"
                )
                db.execute(
                    "UPDATE task_board_atomic_projection_witnesses"
                    " SET board_receipt_sha256 = ?, board_receipt_json = ?"
                    " WHERE run_id = ?",
                    (
                        board_receipt["receipt_sha256"],
                        canonical(board_receipt),
                        ref.run_id,
                    ),
                )
                db.execute(
                    "CREATE TRIGGER task_board_atomic_projection_witness_no_update "
                    "BEFORE UPDATE ON task_board_atomic_projection_witnesses "
                    "BEGIN SELECT RAISE(ABORT, "
                    "'task board atomic projection witness is immutable'); END"
                )
                db.commit()

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
        assert settlement_calls == 1
        assert pending_observations >= 1
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

        supervisor = CampaignSupervisor(
            CampaignConfig(MISSION_ID),
            control,
            board,
            runtime,
            adapter,
        )
        await supervisor.start()
        campaign = await supervisor.status(writer_lock_held=True)
        assert campaign.model_execution_state == "observed"
        assert campaign.proves_model_execution is True
    finally:
        release_projection_settlement.set()
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
async def test_campaign_adapter_requires_verified_exact_principal_before_orchestrator(
    tmp_path: Path,
) -> None:
    board, runtime, control, task_view = await _stack(tmp_path)
    task = await board.get(task_view.task_id)
    assert task is not None
    metadata = {
        **task.metadata,
        **_typed_campaign_metadata("campaign-principal", task.id),
    }
    await board.update_task(task.id, metadata=metadata)
    observer = OrchestratorMissionAdapter(
        _NoDispatch(),  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )
    supervisor = CampaignSupervisor(
        CampaignConfig(MISSION_ID),
        control,
        board,
        runtime,
        observer,
    )
    await supervisor.start()
    orchestrator = _CapturingDispatch()
    adapter = OrchestratorMissionAdapter(
        orchestrator,  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )

    with pytest.raises(MissionControlError, match="exact authenticated principal"):
        await adapter.dispatch(MISSION_ID, task.id)
    assert orchestrator.kwargs is None

    with pytest.raises(MissionControlError, match="exactly one"):
        await adapter.dispatch(
            MISSION_ID,
            task.id,
            authenticated_principal_id="campaign-principal",
            attempt_generation=0,
        )

    assert orchestrator.kwargs is not None
    assert orchestrator.kwargs["authenticated_principal_id"] == "campaign-principal"
    fence = orchestrator.kwargs["campaign_effect_fence"]
    assert callable(fence)
    await fence()
    request = SimpleNamespace(
        action=SimpleNamespace(value="pause"),
        request_id="pause-request",
        idempotency_key="pause-key",
        issued_at="2026-08-23T00:00:00Z",
        expires_at="2026-08-23T00:02:00Z",
        reason="operator pause fixture",
        validate_time_window=lambda *, now=None: None,
    )
    result = await supervisor.apply_operator_control_result(
        request,
        "operator@example.test",
        "sha256:" + "a" * 64,
    )
    assert result.status == "applied"
    with pytest.raises(MissionControlError, match="control position changed"):
        await fence()


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
async def test_observe_rejects_terminal_board_without_exact_projection_ack(
    tmp_path: Path,
) -> None:
    board, runtime, control, task = await _stack(tmp_path)
    await board.assign(task.task_id, "owner-agent")
    await board.start(task.task_id)
    await board.complete(task.task_id, "FORGED BOARD RESULT")
    run_id, idempotency_key = _expected(task.task_id)
    ref = await _record_owner_execution(
        runtime,
        task_id=task.task_id,
        run_id=run_id,
        idempotency_key=idempotency_key,
        claim_id="owner-claim",
        agent_id="owner-agent",
        owner_session_id=OWNER_SESSION_ID,
        status="completed",
    )
    adapter = OrchestratorMissionAdapter(
        _NoDispatch(),  # type: ignore[arg-type]
        control,
        board,
        runtime,
    )

    with pytest.raises(
        MissionControlError,
        match="terminal owner run conflicts with TaskBoard state",
    ):
        await adapter.observe(ref)


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


@pytest.mark.asyncio
async def test_evidence_renewal_requires_durable_new_evidence_and_records_receipt(
    tmp_path: Path,
) -> None:
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
    observed_at = utc_now()
    missing = EvidenceDelta.new(
        mission_id=MISSION_ID,
        task_id=task.task_id,
        run_id=ref.run_id,
        claim_id=ref.claim_id,
        agent_id=ref.agent_id,
        sequence=1,
        observed_at=observed_at,
        summary="Created a durable owner result.",
        receipt_ids=("owner-work-receipt",),
    )
    with pytest.raises(MissionControlError, match="missing runtime receipt"):
        await adapter.renew_with_evidence(ref, missing)

    await runtime.record_runtime_receipt(
        RuntimeReceipt(
            receipt_id="owner-work-receipt",
            receipt_type="owner_work",
            status="recorded",
            run_id=ref.run_id,
            task_id=ref.task_id,
            agent_id=ref.agent_id,
            idempotency_key=ref.idempotency_key,
            created_at=observed_at,
        )
    )
    renewed = await adapter.renew_with_evidence(
        ref,
        missing,
        lease_seconds=90,
    )

    assert renewed.heartbeat_at == observed_at
    assert renewed.stale_after == observed_at + timedelta(seconds=90)
    assert renewed.metadata["mission_control_evidence"]["last_sequence"] == 1
    receipts = await runtime.list_runtime_receipts(run_id=ref.run_id, limit=20)
    assert any(
        receipt.receipt_type == EVIDENCE_DELTA_RECEIPT_TYPE
        and receipt.payload["delta_id"] == missing.delta_id
        for receipt in receipts
    )
    with pytest.raises(MissionControlError, match="duplicate or stale"):
        await adapter.renew_with_evidence(ref, missing)

    reused = EvidenceDelta.new(
        mission_id=MISSION_ID,
        task_id=task.task_id,
        run_id=ref.run_id,
        claim_id=ref.claim_id,
        agent_id=ref.agent_id,
        sequence=2,
        observed_at=observed_at + timedelta(seconds=1),
        summary="Attempted to reuse the previous durable evidence.",
        receipt_ids=("owner-work-receipt",),
    )
    with pytest.raises(MissionControlError, match="already consumed"):
        await adapter.renew_with_evidence(ref, reused)


@pytest.mark.asyncio
async def test_evidence_renewal_rejects_stale_wrong_run_and_terminal_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fast_gate,
) -> None:
    monkeypatch.setattr(
        task_board_module,
        "check_with_reflective_reroute",
        lambda **_: fast_gate,
    )
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
    evidence_values = {
        "mission_id": MISSION_ID,
        "task_id": task.task_id,
        "claim_id": ref.claim_id,
        "agent_id": ref.agent_id,
        "sequence": 1,
        "observed_at": utc_now(),
        "summary": "Evidence used only after the identity fence passes.",
        "receipt_ids": ("not-reached",),
    }
    wrong_run = EvidenceDelta.new(run_id="foreign-run", **evidence_values)
    with pytest.raises(MissionControlError, match="foreign owner execution"):
        await adapter.renew_with_evidence(ref, wrong_run)

    claim = await runtime.get_task_claim(ref.claim_id)
    assert claim is not None
    await runtime.record_task_claim(
        replace(claim, stale_after=utc_now() - timedelta(seconds=1))
    )
    correct = EvidenceDelta.new(run_id=ref.run_id, **evidence_values)
    with pytest.raises(MissionControlError, match="stale owner claim"):
        await adapter.renew_with_evidence(ref, correct)

    claim = await runtime.get_task_claim(ref.claim_id)
    run = await runtime.get_delegation_run(ref.run_id)
    assert claim is not None
    assert run is not None
    await runtime.record_task_claim(
        replace(
            claim,
            status="completed",
            stale_after=utc_now() + timedelta(minutes=5),
        )
    )
    await runtime.record_delegation_run(
        replace(run, status="completed", completed_at=utc_now())
    )
    await board.complete(task.task_id, result="owner candidate")
    with pytest.raises(MissionControlError, match="terminal owner execution"):
        await adapter.renew_with_evidence(ref, correct)
