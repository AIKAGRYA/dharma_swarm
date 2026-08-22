from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

import dharma_swarm.task_board as task_board_module
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_authority import (
    FileExecutionLeaseAuthorityVerifier,
)
from dharma_swarm.mission_control_campaign import (
    CAMPAIGN_CONTROL_RECEIPT_TYPE,
    CAMPAIGN_CYCLE_RECEIPT_TYPE,
    CampaignConfig,
    CampaignSupervisor,
)
from dharma_swarm.mission_control_contract import MissionControlError, stable_id, utc_now
from dharma_swarm.mission_control_dispatch import (
    GOVERNANCE_METADATA_KEY,
    LEASE_DISPATCH_ACTION,
    LEASE_WORKSPACE_ACTION,
    DispatchAuthorityEnvelope,
    GovernedMissionDispatcher,
    MissionDispatchRequest,
)
from dharma_swarm.mission_control_evidence import (
    VERIFIER_RESULT_RECEIPT_TYPE,
    IndependentAcceptance,
    candidate_output_digest,
)
from dharma_swarm.mission_control_execution import (
    EXECUTION_METADATA_KEY,
    OwnerExecutionObservation,
    OwnerExecutionRef,
)
from dharma_swarm.models import TaskStatus
from dharma_swarm.operator_core.execution_lease import (
    build_execution_lease,
    record_lease_revocation,
    write_execution_lease,
)
from dharma_swarm.runtime_state import (
    ArtifactRecord,
    RuntimeReceipt,
    RuntimeStateStore,
    SessionEventRecord,
)
from dharma_swarm.runtime_state import DelegationRun, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard

MISSION_ID = "campaign-alpha"


def _identity_receipt(
    identity: ExecutionIdentity,
    *,
    receipt_id: str,
    receipt_type: str,
    payload: dict[str, Any],
    status: str = "completed",
) -> RuntimeReceipt:
    return RuntimeReceipt(
        receipt_id=receipt_id,
        receipt_type=receipt_type,
        status=status,
        run_id=identity.run_id,
        task_id=identity.task_id,
        trace_id=identity.trace_id,
        correlation_id=identity.correlation_id,
        causation_id=identity.causation_id,
        parent_run_id=identity.parent_run_id,
        agent_id=identity.agent_id,
        idempotency_key=identity.idempotency_key,
        payload=payload,
        created_at=utc_now(),
    )


def _provider_receipt(
    identity: ExecutionIdentity,
    *,
    receipt_id: str,
    provider: str,
    model: str,
    truth_source: str = "llm_response",
) -> RuntimeReceipt:
    return _identity_receipt(
        identity,
        receipt_id=receipt_id,
        receipt_type="side_effect_complete",
        payload={
            "receipt": {
                "trace_id": identity.trace_id,
                "task_id": identity.task_id,
                "agent_id": identity.agent_id,
                "claim_id": identity.claim_id,
                "status": "ok",
                "attributes": {
                    "run_id": identity.run_id,
                    "dispatch_idempotency_key": identity.idempotency_key,
                    "served_provider": provider,
                    "served_model": model,
                    "provider_truth_source": truth_source,
                },
            }
        },
    )


class _OwnerReader:
    def __init__(self) -> None:
        self.refs: dict[str, OwnerExecutionRef] = {}
        self.observations: dict[str, OwnerExecutionObservation] = {}

    async def recover(
        self,
        mission_id: str,
        task_id: str,
        *,
        dispatch_key: str = "default",
    ) -> OwnerExecutionRef | None:
        ref = self.refs.get(task_id)
        if ref is not None:
            assert (ref.mission_id, ref.dispatch_key) == (mission_id, dispatch_key)
        return ref

    async def observe(self, ref: OwnerExecutionRef) -> OwnerExecutionObservation:
        return self.observations[ref.task_id]


class _CompletingDispatcher:
    def __init__(
        self,
        board: TaskBoard,
        runtime: RuntimeStateStore,
        reader: _OwnerReader,
    ) -> None:
        self.board = board
        self.runtime = runtime
        self.reader = reader
        self.calls = 0

    async def dispatch(self, task) -> OwnerExecutionRef:
        self.calls += 1
        ref = OwnerExecutionRef(
            backend="fixture-owner",
            mission_id=task.mission_id,
            task_id=task.task_id,
            dispatch_key="default",
            run_id=stable_id("owner_run", task.mission_id, task.task_id, "default"),
            claim_id=stable_id("owner_claim", task.mission_id, task.task_id),
            agent_id="producer-agent",
            idempotency_key=stable_id(
                "owner_dispatch", task.mission_id, task.task_id, "default"
            ),
            owner_session_id="owner-session",
        )
        current = await self.board.get(task.task_id)
        assert current is not None
        await self.board.update_task(
            task.task_id,
            metadata={
                **current.metadata,
                EXECUTION_METADATA_KEY: {"dispatch_key": "default"},
            },
        )
        self.reader.refs[task.task_id] = ref
        completed_at = utc_now()
        identity = ExecutionIdentity.new(
            trace_id=f"trace-{ref.run_id}",
            correlation_id=f"correlation-{ref.run_id}",
            task_id=task.task_id,
            run_id=ref.run_id,
            claim_id=ref.claim_id,
            agent_id=ref.agent_id,
            session_id=ref.owner_session_id,
            idempotency_key=ref.idempotency_key,
        )
        await self.runtime.record_execution_identity(identity, source="fixture-owner")
        await self.runtime.record_task_claim(
            TaskClaim(
                claim_id=ref.claim_id,
                task_id=task.task_id,
                agent_id=ref.agent_id,
                status="completed",
                session_id=ref.owner_session_id,
                claimed_at=completed_at,
                heartbeat_at=completed_at,
                metadata={"mission_id": task.mission_id},
            )
        )
        await self.runtime.record_delegation_run(
            DelegationRun(
                run_id=ref.run_id,
                task_id=task.task_id,
                assigned_to=ref.agent_id,
                assigned_by="fixture-owner",
                claim_id=ref.claim_id,
                session_id=ref.owner_session_id,
                status="completed",
                started_at=completed_at,
                completed_at=completed_at,
                metadata={"mission_id": task.mission_id},
            )
        )
        self.reader.observations[task.task_id] = OwnerExecutionObservation(
            ref=ref,
            task_status=TaskStatus.COMPLETED,
            run_status="completed",
            claim_status="completed",
            stale=False,
            receipt_ids=(),
            terminal=True,
            succeeded=True,
            result="candidate output",
            failure_code="",
            observed_at=utc_now(),
        )
        return ref


async def _stack(tmp_path: Path, *, held_out_oracle_digest: str = ""):
    board = TaskBoard(tmp_path / "tasks.db")
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await board.init_db()
    await runtime.init_db()
    control = MissionControl(board, runtime)
    await control.create_mission(MISSION_ID, title="Campaign Alpha")
    task = await control.create_task(
        MISSION_ID,
        title="Produce a candidate",
        idempotency_key="campaign-candidate",
    )
    reader = _OwnerReader()
    dispatcher = _CompletingDispatcher(board, runtime, reader)
    supervisor = CampaignSupervisor(
        CampaignConfig(
            MISSION_ID,
            canary_task_id=task.task_id,
            held_out_oracle_digest=held_out_oracle_digest,
        ),
        control,
        board,
        runtime,
        reader,
        dispatcher=dispatcher,
    )
    return board, runtime, control, task, reader, dispatcher, supervisor


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_campaign_config_rejects_nonfinite_timing(invalid: float) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        CampaignConfig(MISSION_ID, cycle_interval_seconds=invalid)


@pytest.mark.parametrize(
    "invalid",
    ["mission/slash", "mission space", "x" * 201, "mïssion", "~mission", "-mission"],
)
def test_campaign_config_rejects_non_url_safe_mission_ids(invalid: str) -> None:
    with pytest.raises(ValueError, match="URL-safe"):
        CampaignConfig(invalid)


def test_campaign_config_bounds_projection_freshness() -> None:
    assert CampaignConfig(MISSION_ID, freshness_seconds=3600).freshness_seconds == 3600
    with pytest.raises(ValueError, match="at most 3600"):
        CampaignConfig(MISSION_ID, freshness_seconds=3600.01)
    with pytest.raises(ValueError, match="max_dispatch_per_cycle"):
        CampaignConfig(MISSION_ID, max_dispatch_per_cycle=1.5)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_first_start_rolls_back_session_when_control_receipt_conflicts(
    tmp_path: Path,
) -> None:
    _, runtime, _, _, _, _, supervisor = await _stack(tmp_path)
    await runtime.insert_runtime_receipt_exact(
        RuntimeReceipt(
            receipt_id=stable_id(
                "mission_campaign_control",
                MISSION_ID,
                "start",
                "1",
            ),
            receipt_type=CAMPAIGN_CONTROL_RECEIPT_TYPE,
            status="foreign",
            correlation_id=supervisor.config.session_id,
            payload={"mission_id": "foreign"},
            created_at=utc_now(),
        )
    )

    with pytest.raises(ValueError, match="atomic session receipt identity"):
        await supervisor.start()

    assert await runtime.get_session(supervisor.config.session_id) is None


@pytest.mark.asyncio
async def test_completed_owner_output_is_candidate_until_independently_accepted(
    tmp_path: Path,
) -> None:
    _, runtime, _, task, _, dispatcher, supervisor = await _stack(tmp_path)
    await supervisor.start()
    before_cycle = await supervisor.status(writer_lock_held=True)
    assert before_cycle.cycle_sequence == 0
    assert before_cycle.latest_cycle_at is None

    candidate = await supervisor.cycle(writer_lock_held=True)

    assert dispatcher.calls == 1
    assert candidate.candidate_task_ids == (task.task_id,)
    assert candidate.accepted_task_ids == ()
    assert candidate.acceptance_state == "candidate_only"
    assert candidate.canary_acceptance == "candidate"
    assert candidate.proves_semantic_acceptance is False
    assert candidate.mission_snapshot.attempts == ()
    assert len(candidate.owner_executions) == 1

    producer_ref = candidate.owner_executions[0].ref
    await runtime.record_runtime_receipt(
        RuntimeReceipt(
            receipt_id="transport-receipt",
            receipt_type="nats_publish",
            status="acknowledged",
            run_id=producer_ref.run_id,
            task_id=task.task_id,
            agent_id=producer_ref.agent_id,
        )
    )
    producer_identity = await runtime.get_execution_identity(producer_ref.run_id)
    assert producer_identity is not None
    producer_run = await runtime.get_delegation_run(producer_ref.run_id)
    assert producer_run is not None and producer_run.completed_at is not None
    await runtime.record_runtime_receipt(
        _provider_receipt(
            producer_identity,
            receipt_id="configured-model-receipt",
            provider="configured-provider",
            model="configured-only-family",
            truth_source="runner_config",
        )
    )
    configured_only = await supervisor.status(writer_lock_held=True)
    assert configured_only.model_execution_state == "unobserved"
    assert configured_only.proves_model_execution is False
    await runtime.record_runtime_receipt(
        replace(
            _provider_receipt(
                producer_identity,
                receipt_id="model-receipt",
                provider="fixture-provider",
                model="producer-family",
            ),
            created_at=producer_run.completed_at,
        )
    )
    for receipt_id, created_at in (
        ("pre-start-model-receipt", producer_run.started_at - timedelta(microseconds=1)),
        ("post-completion-model-receipt", producer_run.completed_at + timedelta(microseconds=1)),
    ):
        await runtime.record_runtime_receipt(
            replace(
                _provider_receipt(
                    producer_identity,
                    receipt_id=receipt_id,
                    provider="fixture-provider",
                    model="outside-window-family",
                ),
                created_at=created_at,
            )
        )
    routed = await supervisor.status(writer_lock_held=True)
    assert routed.transport_state == "observed"
    assert routed.model_execution_state == "observed"
    assert routed.proves_model_execution is True

    evidence_id = "verifier-receipt"
    verifier_identity = ExecutionIdentity.new(
        trace_id="verifier-trace",
        correlation_id="verifier-correlation",
        task_id=task.task_id,
        run_id="verifier-run",
        claim_id="verifier-claim",
        agent_id="verifier-agent",
        session_id="verifier-session",
        idempotency_key="verifier-idempotency",
    )
    await runtime.record_execution_identity(
        verifier_identity,
        source="test-verifier",
    )
    await runtime.record_runtime_receipt(
        replace(
            _provider_receipt(
                verifier_identity,
                receipt_id="old-verifier-provider-receipt",
                provider="verifier-provider",
                model="verifier-family",
            ),
            created_at=producer_run.completed_at - timedelta(microseconds=1),
        )
    )
    await runtime.record_runtime_receipt(
        _identity_receipt(
            verifier_identity,
            receipt_id=evidence_id,
            receipt_type=VERIFIER_RESULT_RECEIPT_TYPE,
            payload={
                "actual_served_provider": "verifier-provider",
                "actual_served_model": "verifier-family",
                "producer_output_digest": candidate_output_digest(
                    "candidate output"
                ),
                "accepted": True,
            },
        )
    )
    acceptance = IndependentAcceptance.new(
        mission_id=MISSION_ID,
        task_id=task.task_id,
        producer_run_id=producer_ref.run_id,
        producer_agent_id="producer-agent",
        producer_model_family="producer-family",
        producer_output_digest=candidate_output_digest("candidate output"),
        verifier_run_id="verifier-run",
        verifier_agent_id="verifier-agent",
        verifier_model_family="verifier-family",
        oracle_kind="model",
        accepted=True,
        observed_at=utc_now(),
        rationale="Independent fixture review passed.",
        evidence_receipt_ids=(evidence_id,),
    )
    with pytest.raises(MissionControlError, match="verifier model family"):
        await supervisor.accept(acceptance)
    await runtime.record_runtime_receipt(
        replace(
            _provider_receipt(
                verifier_identity,
                receipt_id="fresh-verifier-provider-receipt",
                provider="verifier-provider",
                model="verifier-family",
            ),
            created_at=acceptance.observed_at,
        )
    )
    outside_window_acceptance = IndependentAcceptance.new(
        mission_id=acceptance.mission_id,
        task_id=acceptance.task_id,
        producer_run_id=acceptance.producer_run_id,
        producer_agent_id=acceptance.producer_agent_id,
        producer_model_family="outside-window-family",
        producer_output_digest=acceptance.producer_output_digest,
        verifier_run_id=acceptance.verifier_run_id,
        verifier_agent_id=acceptance.verifier_agent_id,
        verifier_model_family=acceptance.verifier_model_family,
        oracle_kind=acceptance.oracle_kind,
        accepted=acceptance.accepted,
        observed_at=acceptance.observed_at,
        rationale=acceptance.rationale,
        evidence_receipt_ids=acceptance.evidence_receipt_ids,
    )
    with pytest.raises(MissionControlError, match="producer model family"):
        await supervisor.accept(outside_window_acceptance)
    acceptance_receipt = await supervisor.accept(acceptance)
    assert acceptance_receipt.run_id == acceptance.verifier_run_id
    assert acceptance_receipt.causation_id == producer_ref.run_id
    producer_receipts = await runtime.list_runtime_receipts(
        run_id=producer_ref.run_id,
        limit=100,
    )
    assert acceptance_receipt.receipt_id not in {
        receipt.receipt_id for receipt in producer_receipts
    }
    with pytest.raises(ValueError, match="conflicting evidence"):
        await runtime.insert_runtime_receipt_exact(
            replace(acceptance_receipt, status="rejected")
        )

    accepted = await supervisor.status(writer_lock_held=True)
    assert accepted.accepted_task_ids == (task.task_id,)
    assert accepted.candidate_task_ids == ()
    assert accepted.canary_acceptance == "accepted"
    assert accepted.proves_semantic_acceptance is True

    await runtime.record_runtime_receipt(
        replace(acceptance_receipt, receipt_id="copied-acceptance-carrier")
    )
    copied = await supervisor.status(writer_lock_held=True)
    assert copied.accepted_task_ids == (task.task_id,)
    assert copied.invalid_acceptance_receipts == 1

    with pytest.raises(ValueError, match="immutable runtime receipt"):
        await runtime.record_runtime_receipt(
            replace(
                acceptance_receipt,
                payload={**acceptance_receipt.payload, "rationale": "tampered"},
            )
        )
    preserved = await supervisor.status(writer_lock_held=True)
    assert preserved.accepted_task_ids == (task.task_id,)
    assert preserved.invalid_acceptance_receipts == 1


def test_same_generator_verifier_is_rejected_except_held_out_oracle() -> None:
    values: dict[str, Any] = {
        "mission_id": MISSION_ID,
        "task_id": "task-alpha",
        "producer_run_id": "producer-run",
        "producer_agent_id": "same-agent",
        "producer_model_family": "same-family",
        "producer_output_digest": candidate_output_digest("candidate output"),
        "verifier_run_id": "verifier-run",
        "verifier_agent_id": "same-agent",
        "verifier_model_family": "same-family",
        "accepted": True,
        "observed_at": utc_now(),
        "rationale": "Deterministic validation result.",
        "evidence_receipt_ids": ("oracle-receipt",),
    }
    with pytest.raises(MissionControlError, match="must be independent"):
        IndependentAcceptance.new(oracle_kind="model", **values)

    held_out = IndependentAcceptance.new(
        oracle_kind="deterministic_held_out",
        oracle_digest="sha256:" + "a" * 64,
        **values,
    )
    assert held_out.oracle_kind == "deterministic_held_out"


@pytest.mark.asyncio
async def test_projection_rejects_foreign_nested_receipt_mission(tmp_path: Path) -> None:
    _, runtime, control, task, _, _, supervisor = await _stack(tmp_path)
    await supervisor.start()
    attempt = await control.start_attempt(MISSION_ID, task.task_id, "native-agent")
    identity = await runtime.get_execution_identity(attempt.attempt_id)
    assert identity is not None
    await runtime.record_runtime_receipt(
        _identity_receipt(
            identity,
            receipt_id="foreign-mission-receipt",
            receipt_type="test_observation",
            payload={"mission_id": "foreign-mission"},
        )
    )

    with pytest.raises(MissionControlError, match="foreign receipt"):
        await supervisor.status(writer_lock_held=True)


@pytest.mark.asyncio
async def test_stop_preserves_queued_work_and_restart_recovers_owner(
    tmp_path: Path,
) -> None:
    board, runtime, control, task, reader, dispatcher, supervisor = await _stack(
        tmp_path
    )
    await supervisor.start()
    await supervisor.cycle(writer_lock_held=True)
    assert dispatcher.calls == 1

    await supervisor.stop()
    stopped_session = await runtime.get_session(supervisor.config.session_id)
    assert stopped_session is not None
    stop_receipt = await runtime.get_runtime_receipt(
        stable_id("mission_campaign_control", MISSION_ID, "stop", "1")
    )
    assert stop_receipt is not None
    assert await runtime.upsert_session(stopped_session) == stopped_session
    resurrected_metadata = {**stopped_session.metadata, "stop_requested": False}
    for metadata in (
        resurrected_metadata,
        {
            key: value
            for key, value in resurrected_metadata.items()
            if key != "schema_version"
        },
    ):
        resurrection = replace(
            stopped_session,
            status="active",
            metadata=metadata,
            updated_at=stopped_session.updated_at + timedelta(microseconds=1),
        )
        with pytest.raises(ValueError, match="reserved campaign session"):
            await runtime.upsert_session(resurrection)
        with pytest.raises(ValueError, match="reserved campaign session"):
            await runtime.compare_and_swap_session(stopped_session, resurrection)
        with pytest.raises(ValueError, match="campaign"):
            await runtime.compare_and_swap_session(
                stopped_session,
                resurrection,
                atomic_receipt=stop_receipt,
            )
    cycle_receipt = await runtime.get_runtime_receipt(
        str(stopped_session.metadata["last_cycle_receipt_id"])
    )
    assert cycle_receipt is not None
    conflicting_cycle = replace(
        cycle_receipt,
        status="partial" if cycle_receipt.status == "completed" else "completed",
    )
    event = SessionEventRecord(
        event_id="campaign-event-async",
        session_id=stopped_session.session_id,
        ledger_kind="test",
        event_name="attempted_mutation",
        task_id="forged-current-task",
        created_at=stopped_session.updated_at + timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="immutable runtime receipt"):
        await runtime.record_session_event_with_runtime_receipt(
            event,
            conflicting_cycle,
        )
    with pytest.raises(ValueError, match="immutable runtime receipt"):
        runtime.record_session_event_with_runtime_receipt_sync(
            replace(event, event_id="campaign-event-sync"),
            conflicting_cycle,
        )
    await runtime.record_session_event(replace(event, event_id="campaign-event-allowed"))
    assert await runtime.get_session(stopped_session.session_id) == stopped_session
    assert await runtime.get_runtime_receipt(cycle_receipt.receipt_id) == cycle_receipt
    queued = await control.create_task(
        MISSION_ID,
        title="Queued after stop",
        idempotency_key="queued-after-stop",
    )
    stopped = await supervisor.cycle(writer_lock_held=True)
    assert stopped.supervisor_state == "stopped"
    assert dispatcher.calls == 1  # durable stop fences every later submission
    stored = await board.get(queued.task_id)
    assert stored is not None and stored.status is TaskStatus.PENDING

    restarted_dispatcher = _CompletingDispatcher(board, runtime, reader)
    restarted = CampaignSupervisor(
        supervisor.config,
        control,
        board,
        runtime,
        reader,
        dispatcher=restarted_dispatcher,
    )
    await restarted.start()
    snapshot = await restarted.cycle(writer_lock_held=True)
    assert any(item.ref.task_id == task.task_id for item in snapshot.owner_executions)
    assert restarted_dispatcher.calls == 1
    assert restarted_dispatcher.reader.refs[task.task_id].run_id == reader.refs[
        task.task_id
    ].run_id


@pytest.mark.asyncio
async def test_cycle_history_is_immutable_and_constant_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, runtime, _, _, _, _, supervisor = await _stack(tmp_path)
    await supervisor.start()

    first = await supervisor.cycle(writer_lock_held=True)
    second = await supervisor.cycle(writer_lock_held=True)

    assert (first.generation, first.cycle_sequence) == (1, 1)
    assert (second.generation, second.cycle_sequence) == (1, 2)
    rows = await runtime.list_runtime_receipts(
        correlation_id=supervisor.config.session_id,
        receipt_type=CAMPAIGN_CYCLE_RECEIPT_TYPE,
        limit=10,
    )
    assert [row.payload["sequence"] for row in rows] == [1, 2]
    assert len({row.receipt_id for row in rows}) == 2
    session = await runtime.get_session(supervisor.config.session_id)
    assert session is not None
    assert session.metadata["last_cycle_sequence"] == 2
    assert session.metadata["last_cycle_receipt_id"] == rows[-1].receipt_id
    with pytest.raises(ValueError, match="cycle receipt carrier"):
        await runtime.insert_runtime_receipt_exact(
            replace(
                rows[-1],
                receipt_id="forged-duplicate-cycle",
                idempotency_key="forged-duplicate-cycle",
                created_at=rows[-1].created_at + timedelta(microseconds=1),
            )
        )
    original_list = runtime.list_runtime_receipts
    cycle_scans = 0

    async def _synthetic_large_history(**filters: Any):
        nonlocal cycle_scans
        if filters.get("receipt_type") == CAMPAIGN_CYCLE_RECEIPT_TYPE:
            cycle_scans += 1
            return [rows[-1]] * 10_001
        return await original_list(**filters)

    monkeypatch.setattr(runtime, "list_runtime_receipts", _synthetic_large_history)
    after_large_history = await supervisor.status(writer_lock_held=True)
    assert after_large_history.cycle_sequence == 2
    assert cycle_scans == 0


@pytest.mark.asyncio
async def test_candidate_dependency_cannot_dispatch_until_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fast_gate,
) -> None:
    oracle_digest = "sha256:" + "b" * 64
    monkeypatch.setattr(
        task_board_module,
        "check_with_reflective_reroute",
        lambda **_: fast_gate,
    )
    board, runtime, control, task, _, dispatcher, supervisor = await _stack(
        tmp_path,
        held_out_oracle_digest=oracle_digest,
    )
    dependent = await control.create_task(
        MISSION_ID,
        title="Consume accepted candidate",
        depends_on=[task.task_id],
        idempotency_key="accepted-dependent",
    )
    await supervisor.start()
    candidate = await supervisor.cycle(writer_lock_held=True)
    assert dispatcher.calls == 1
    assert dependent.task_id not in dispatcher.reader.refs

    current = await board.get(task.task_id)
    assert current is not None
    await board.assign(task.task_id, "producer-agent", metadata=current.metadata)
    await board.start(task.task_id)
    await board.complete(task.task_id, result="candidate output")
    await supervisor.cycle(writer_lock_held=True)
    assert dispatcher.calls == 1

    oracle_identity = ExecutionIdentity.new(
            trace_id="oracle-trace",
            correlation_id="oracle-correlation",
            task_id=task.task_id,
            run_id="oracle-run",
            claim_id="oracle-claim",
            agent_id="oracle-agent",
            session_id="oracle-session",
            idempotency_key="oracle-idempotency",
        )
    await runtime.record_execution_identity(
        oracle_identity,
        source="test-oracle",
    )
    await runtime.record_runtime_receipt(
        _identity_receipt(
            oracle_identity,
            receipt_id="oracle-receipt",
            receipt_type=VERIFIER_RESULT_RECEIPT_TYPE,
            payload={
                "producer_output_digest": candidate_output_digest(
                    "candidate output"
                ),
                "oracle_manifest_digest": oracle_digest,
                "accepted": True,
                "oracle_evaluator": "fixture-held-out-evaluator",
                "oracle_version": "v1",
            },
        )
    )
    await runtime.record_artifact(
        ArtifactRecord(
            artifact_id="oracle-artifact",
            artifact_kind="mission_held_out_oracle_verdict",
            session_id="oracle-session",
            task_id=task.task_id,
            run_id="oracle-run",
            checksum="sha256:" + "c" * 64,
            metadata={
                "producer_output_digest": candidate_output_digest(
                    "candidate output"
                ),
                "oracle_manifest_digest": oracle_digest,
                "accepted": True,
                "oracle_evaluator": "fixture-held-out-evaluator",
                "oracle_version": "v1",
            },
        )
    )
    producer = candidate.owner_executions[0].ref
    await supervisor.accept(
        IndependentAcceptance.new(
            mission_id=MISSION_ID,
            task_id=task.task_id,
            producer_run_id=producer.run_id,
            producer_agent_id=producer.agent_id,
            producer_model_family="producer-family",
            producer_output_digest=candidate_output_digest("candidate output"),
            verifier_run_id="oracle-run",
            verifier_agent_id="oracle-agent",
            verifier_model_family="deterministic-oracle",
            oracle_kind="deterministic_held_out",
            oracle_digest=oracle_digest,
            accepted=True,
            observed_at=utc_now(),
            rationale="Held-out deterministic oracle passed.",
            evidence_receipt_ids=("oracle-receipt",),
            evidence_artifact_ids=("oracle-artifact",),
        )
    )
    await supervisor.cycle(writer_lock_held=True)
    assert dispatcher.calls == 2
    assert dependent.task_id in dispatcher.reader.refs


class _EffectExecutor:
    def __init__(self, task_id: str) -> None:
        self.calls = 0
        self.ref = OwnerExecutionRef(
            backend="fixture",
            mission_id=MISSION_ID,
            task_id=task_id,
            dispatch_key="default",
            run_id="owner-run",
            claim_id="owner-claim",
            agent_id="owner-agent",
            idempotency_key="owner-key",
            owner_session_id="owner-session",
        )

    async def dispatch(
        self, mission_id: str, task_id: str, *, dispatch_key: str = "default"
    ) -> OwnerExecutionRef:
        self.calls += 1
        return replace(
            self.ref,
            mission_id=mission_id,
            task_id=task_id,
            dispatch_key=dispatch_key,
        )


class _RevokingBoard:
    def __init__(self, board: TaskBoard, lease_root: Path, lease_id: str) -> None:
        self._board = board
        self._lease_root = lease_root
        self._lease_id = lease_id
        self.calls = 0

    async def get(self, task_id: str):
        self.calls += 1
        if self.calls == 6:
            record_lease_revocation(
                self._lease_root,
                self._lease_id,
                reason="fixture rotation before effect",
            )
        return await self._board.get(task_id)


@pytest.mark.asyncio
async def test_file_authority_reloads_revocation_before_governed_effect(
    tmp_path: Path,
) -> None:
    board = TaskBoard(tmp_path / "tasks.db")
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await board.init_db()
    await runtime.init_db()
    control = MissionControl(board, runtime)
    await control.create_mission(MISSION_ID, title="Governed Campaign")
    task = await control.create_task(
        MISSION_ID,
        title="Inspect bounded workspace",
        description="Return a local summary.",
        idempotency_key="governed-campaign-task",
        metadata={GOVERNANCE_METADATA_KEY: {"allowed_files": ["bounded/workspace"]}},
    )
    request = MissionDispatchRequest.new(
        MISSION_ID,
        task.task_id,
        claimed_principal="campaign-principal",
    )
    lease = build_execution_lease(
        issued_to=request.claimed_principal,
        task_id=task.task_id,
        correlation_id=request.request_id,
        lease_id="lease-campaign",
        allowed_actions=[LEASE_DISPATCH_ACTION, LEASE_WORKSPACE_ACTION],
        allowed_paths=["bounded/workspace"],
    )
    lease_root = tmp_path / "leases"
    write_execution_lease(lease, lease_root)
    effect = _EffectExecutor(task.task_id)
    revoking_board = _RevokingBoard(board, lease_root, str(lease["lease_id"]))
    dispatcher = GovernedMissionDispatcher(
        control,
        revoking_board,  # type: ignore[arg-type]
        effect,
        authority_verifier=FileExecutionLeaseAuthorityVerifier(lease_root),
    )
    governed = await dispatcher.canonical_governed_request(request)
    admission = await dispatcher.admit(request, governed)
    envelope = DispatchAuthorityEnvelope(
        claimed_principal=request.claimed_principal,
        mission_id=request.mission_id,
        task_id=request.task_id,
        dispatch_key=request.dispatch_key,
        authority_ref=str(lease["lease_id"]),
        authority_digest=str(lease["content_hash"]),
    )

    with pytest.raises(MissionControlError, match="revoked before effect"):
        await dispatcher.dispatch(request, governed, admission, envelope)
    assert effect.calls == 0
