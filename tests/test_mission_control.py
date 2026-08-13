from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import dharma_swarm.mission_control as mission_control_module
import dharma_swarm.runtime_state as runtime_state_module
from dharma_swarm.mission_control import (
    SCHEMA_VERSION,
    MissionControl,
    MissionControlError,
    ReconciliationState,
)
from dharma_swarm.models import TaskPriority, TaskStatus
from dharma_swarm.operator_views import OperatorViews
from dharma_swarm.runtime_state import RuntimeStateStore, TaskClaim
from dharma_swarm.task_board import TaskBoard, TaskBoardError


@pytest.fixture
async def mission_control(tmp_path: Path) -> MissionControl:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    board = TaskBoard(tmp_path / "tasks.db")
    await runtime.init_db()
    await board.init_db()
    return MissionControl(board, runtime)


async def _mission_task(control: MissionControl, mission_id: str = "m-alpha"):
    await control.create_mission(
        mission_id,
        title="Alpha",
        goal="Prove the adapter",
        metadata={"caller_schema": "ignored-as-authority"},
    )
    return await control.create_task(
        mission_id,
        title="Run proof",
        idempotency_key="task-proof",
    )


async def _active_attempt(
    control: MissionControl,
    task_id: str,
    *,
    mission_id: str = "m-alpha",
    agent_id: str = "agent-a",
    attempt_key: str = "attempt-proof",
):
    attempt = await control.start_attempt(
        mission_id,
        task_id,
        agent_id,
        attempt_key=attempt_key,
    )
    await control.heartbeat_lease(
        mission_id,
        task_id,
        agent_id,
        attempt_id=attempt.attempt_id,
    )
    return attempt


@pytest.mark.asyncio
async def test_mission_maps_to_explicit_session_without_conflating_ids(
    mission_control: MissionControl,
) -> None:
    mission = await mission_control.create_mission(
        "m-alpha",
        title="Alpha",
        goal="Prove the adapter",
        metadata={"schema_version": "foreign", "mission_id": "foreign"},
    )

    assert mission.mission_id == "m-alpha"
    assert mission.session_id == "mission:m-alpha"
    assert mission.metadata["schema_version"] == SCHEMA_VERSION
    assert mission.metadata["mission_id"] == "m-alpha"
    assert mission.goal == "Prove the adapter"
    assert await mission_control.get_mission("m-alpha") == mission


@pytest.mark.asyncio
async def test_mission_creation_is_idempotent_and_conflicts_fail_closed(
    mission_control: MissionControl,
) -> None:
    first = await mission_control.create_mission("m-alpha", title="Alpha")
    second = await mission_control.create_mission("m-alpha", title="Alpha")
    assert second.session_id == first.session_id

    with pytest.raises(MissionControlError, match="conflicting content"):
        await mission_control.create_mission("m-alpha", title="Different")


@pytest.mark.asyncio
async def test_task_binding_and_idempotency_use_taskboard_owner(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    retried = await mission_control.create_task(
        "m-alpha",
        title="Run proof",
        idempotency_key="task-proof",
    )
    assert retried.task_id == task.task_id
    assert task.metadata["mission_id"] == "m-alpha"
    assert task.metadata["schema_version"] == SCHEMA_VERSION
    assert (await mission_control.list_tasks("m-alpha")) == (task,)

    with pytest.raises(MissionControlError, match="conflicting content"):
        await mission_control.create_task(
            "m-alpha",
            title="A different task",
            idempotency_key="task-proof",
        )


@pytest.mark.asyncio
async def test_foreign_task_is_rejected(mission_control: MissionControl) -> None:
    await mission_control.create_mission("m-alpha", title="Alpha")
    foreign = await mission_control._board.create("Foreign")

    with pytest.raises(MissionControlError, match="does not belong"):
        await mission_control.start_attempt("m-alpha", foreign.id, "agent-a")


@pytest.mark.asyncio
async def test_attempt_joins_identity_claim_run_and_task_projection(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await mission_control.start_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_key="attempt-proof",
        lease_seconds=60,
    )

    identity = await mission_control._runtime.get_execution_identity(attempt.attempt_id)
    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    run = await mission_control._runtime.get_delegation_run(attempt.attempt_id)
    projected = await mission_control._board.get(task.task_id)

    assert identity is not None and identity.run_id == attempt.attempt_id
    assert identity.claim_id == attempt.claim_id
    assert identity.idempotency_key == "attempt-proof"
    assert claim is not None and claim.agent_id == "agent-a"
    assert claim.status == "claimed"
    assert claim.acked_at is None and claim.heartbeat_at is None
    assert run is not None and run.claim_id == claim.claim_id
    assert run.status == "queued"
    assert projected is not None and projected.status == TaskStatus.ASSIGNED
    assert projected.assigned_to == "agent-a"
    assert attempt.session_id == "mission:m-alpha"

    retried = await mission_control.start_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_key="attempt-proof",
    )
    assert retried.attempt_id == attempt.attempt_id

    lease = await mission_control.heartbeat_lease(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
    )
    running = await mission_control._runtime.get_delegation_run(attempt.attempt_id)
    projected = await mission_control._board.get(task.task_id)
    assert lease.active is True
    assert running is not None and running.status == "running"
    assert projected is not None and projected.status == TaskStatus.RUNNING
    assert len(
        await mission_control._runtime.list_delegation_runs(
            task_id=task.task_id, limit=100
        )
    ) == 1


@pytest.mark.asyncio
async def test_conflicting_active_claim_fails_closed(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    now = datetime.now(timezone.utc)
    await mission_control._runtime.record_task_claim(
        TaskClaim(
            claim_id="foreign-claim",
            task_id=task.task_id,
            agent_id="agent-foreign",
            status="active",
            session_id="mission:m-alpha",
            stale_after=now + timedelta(minutes=5),
        )
    )

    with pytest.raises(MissionControlError, match="active claim holder"):
        await mission_control.start_attempt(
            "m-alpha", task.task_id, "agent-a", attempt_key="attempt-proof"
        )


@pytest.mark.asyncio
async def test_heartbeat_extends_exact_lease_and_rejects_wrong_agent(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    before = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert before is not None and before.stale_after is not None

    lease = await mission_control.heartbeat_lease(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        lease_seconds=900,
    )
    assert lease.active is True
    assert lease.stale_after is not None and lease.stale_after > before.stale_after

    with pytest.raises(MissionControlError, match="foreign identity"):
        await mission_control.heartbeat_lease(
            "m-alpha",
            task.task_id,
            "agent-b",
            attempt_id=attempt.attempt_id,
        )


@pytest.mark.asyncio
async def test_expired_lease_cannot_be_resurrected_by_heartbeat(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert claim is not None
    await mission_control._runtime.record_task_claim(
        replace(claim, stale_after=datetime.now(timezone.utc) - timedelta(seconds=1))
    )

    with pytest.raises(MissionControlError, match="expired"):
        await mission_control.heartbeat_lease(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
        )


@pytest.mark.asyncio
async def test_success_receipt_precedes_completed_task_and_retry_is_idempotent(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    receipt = await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
        result="verified",
    )

    projected = await mission_control._board.get(task.task_id)
    run = await mission_control._runtime.get_delegation_run(attempt.attempt_id)
    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert receipt.status == "succeeded"
    assert projected is not None and projected.status == TaskStatus.COMPLETED
    assert run is not None and run.status == "completed"
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None and snapshot.attempts[0].status == "succeeded"
    assert claim is not None and claim.status == "completed"

    retried = await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
        result="verified",
    )
    assert retried.receipt_id == receipt.receipt_id
    terminal = await mission_control._runtime.list_runtime_receipts(
        run_id=attempt.attempt_id,
        receipt_type="mission_attempt_terminal",
        limit=100,
    )
    assert len(terminal) == 1
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.reconciliation == ReconciliationState.COHERENT
    assert snapshot.proves_executor_liveness is False


@pytest.mark.asyncio
async def test_retry_repairs_crash_after_runtime_evidence_before_task_projection(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    original_complete = mission_control._board.complete

    async def crash_before_projection(*args, **kwargs):
        raise TaskBoardError("simulated projection crash")

    monkeypatch.setattr(mission_control._board, "complete", crash_before_projection)
    with pytest.raises(MissionControlError, match="simulated projection crash"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
            result="verified",
        )

    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.reconciliation == ReconciliationState.NEEDS_TASK_PROJECTION
    monkeypatch.setattr(mission_control._board, "complete", original_complete)

    receipt = await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
        result="verified",
    )
    projected = await mission_control._board.get(task.task_id)
    assert receipt.status == "succeeded"
    assert projected is not None and projected.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_failed_receipt_projects_failed_task(mission_control: MissionControl) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    receipt = await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="failed",
        result="provider unavailable",
        failure_code="provider_unavailable",
    )
    projected = await mission_control._board.get(task.task_id)
    assert receipt.status == "failed"
    assert projected is not None and projected.status == TaskStatus.FAILED
    assert projected.result == "provider_unavailable"


@pytest.mark.asyncio
async def test_conflicting_terminal_retry_is_rejected(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
        result="first",
    )

    with pytest.raises(MissionControlError, match="conflicting terminal evidence"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
            result="different",
        )


@pytest.mark.asyncio
async def test_snapshot_reports_receipt_projection_crash_honestly(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    identity = await mission_control._runtime.get_execution_identity(attempt.attempt_id)
    assert identity is not None
    await mission_control._runtime.record_receipt_for_identity(
        identity,
        receipt_type="mission_attempt_terminal",
        status="succeeded",
        receipt_id="receipt-crash-window",
        payload={
            "schema_version": SCHEMA_VERSION,
            "mission_id": "m-alpha",
            "attempt_id": attempt.attempt_id,
        },
    )

    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.tasks[0].status == TaskStatus.RUNNING
    assert (
        snapshot.reconciliation
        == ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
    )


@pytest.mark.asyncio
async def test_snapshot_reports_terminal_run_without_receipt(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    run = await mission_control._runtime.get_delegation_run(attempt.attempt_id)
    assert run is not None
    await mission_control._runtime.record_delegation_run(
        replace(run, status="completed", completed_at=datetime.now(timezone.utc))
    )
    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert claim is not None
    await mission_control._runtime.record_task_claim(
        replace(claim, status="completed")
    )

    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.reconciliation == ReconciliationState.MISSING_TERMINAL_RECEIPT


@pytest.mark.asyncio
async def test_snapshot_reports_expired_lease(mission_control: MissionControl) -> None:
    task = await _mission_task(mission_control)
    attempt = await mission_control.start_attempt(
        "m-alpha", task.task_id, "agent-a", attempt_key="attempt-proof"
    )
    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert claim is not None
    await mission_control._runtime.record_task_claim(
        replace(claim, stale_after=datetime.now(timezone.utc) - timedelta(seconds=1))
    )

    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.reconciliation == ReconciliationState.EXPIRED_LEASE
    assert snapshot.leases[0].expired is True
    assert snapshot.leases[0].active is False


@pytest.mark.asyncio
async def test_foreign_mission_and_agent_cannot_finish_attempt(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    await mission_control.create_mission("m-beta", title="Beta")
    attempt = await _active_attempt(mission_control, task.task_id)

    with pytest.raises(MissionControlError, match="does not belong"):
        await mission_control.finish_attempt(
            "m-beta",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
        )
    with pytest.raises(MissionControlError, match="foreign identity"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-b",
            attempt_id=attempt.attempt_id,
            status="succeeded",
        )


@pytest.mark.asyncio
async def test_finish_requires_acknowledged_unexpired_lease(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await mission_control.start_attempt(
        "m-alpha", task.task_id, "agent-a", attempt_key="attempt-proof"
    )

    with pytest.raises(MissionControlError, match="active and acknowledged"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
        )

    await mission_control.heartbeat_lease(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
    )
    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert claim is not None
    await mission_control._runtime.record_task_claim(
        replace(claim, stale_after=datetime.now(timezone.utc) - timedelta(seconds=1))
    )

    with pytest.raises(MissionControlError, match="expired"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
        )
    terminal = await mission_control._runtime.list_runtime_receipts(
        run_id=attempt.attempt_id,
        receipt_type="mission_attempt_terminal",
        limit=100,
    )
    assert terminal == []


@pytest.mark.asyncio
async def test_new_claim_fences_stale_prior_finisher(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    first = await _active_attempt(
        mission_control,
        task.task_id,
        agent_id="agent-a",
        attempt_key="attempt-one",
    )
    first_claim = await mission_control._runtime.get_task_claim(first.claim_id)
    assert first_claim is not None
    await mission_control._runtime.record_task_claim(
        replace(
            first_claim,
            stale_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )

    second = await _active_attempt(
        mission_control,
        task.task_id,
        agent_id="agent-b",
        attempt_key="attempt-two",
    )
    assert second.attempt_id != first.attempt_id

    with pytest.raises(MissionControlError, match="superseded"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=first.attempt_id,
            status="succeeded",
        )


@pytest.mark.asyncio
async def test_start_retry_adopts_orphan_claim_and_snapshot_exposes_it(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    original_record_run = mission_control._runtime.record_delegation_run

    async def crash_after_claim(*args, **kwargs):
        raise RuntimeError("simulated claim-before-run crash")

    monkeypatch.setattr(
        mission_control._runtime,
        "record_delegation_run",
        crash_after_claim,
    )
    with pytest.raises(RuntimeError, match="claim-before-run"):
        await mission_control.start_attempt(
            "m-alpha", task.task_id, "agent-a", attempt_key="orphan-proof"
        )

    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.reconciliation == ReconciliationState.ACTIVE_CLAIM_WITHOUT_RUN
    assert len(snapshot.leases) == 1
    assert snapshot.leases[0].status == "claimed"
    assert snapshot.leases[0].active is False

    monkeypatch.setattr(
        mission_control._runtime,
        "record_delegation_run",
        original_record_run,
    )
    recovered = await mission_control.start_attempt(
        "m-alpha", task.task_id, "agent-a", attempt_key="orphan-proof"
    )
    projected = await mission_control._board.get(task.task_id)
    assert recovered.status == "queued"
    assert projected is not None and projected.status == TaskStatus.ASSIGNED
    assert len(
        await mission_control._runtime.list_task_claims(
            task_id=task.task_id, limit=100
        )
    ) == 1


@pytest.mark.asyncio
async def test_start_retry_repairs_queued_task_projection(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    original_assign = mission_control._board.assign

    async def crash_before_assign(*args, **kwargs):
        raise TaskBoardError("simulated queued projection crash")

    monkeypatch.setattr(mission_control._board, "assign", crash_before_assign)
    with pytest.raises(MissionControlError, match="queued projection crash"):
        await mission_control.start_attempt(
            "m-alpha", task.task_id, "agent-a", attempt_key="attempt-proof"
        )

    persisted = await mission_control._runtime.list_delegation_runs(
        task_id=task.task_id, limit=100
    )
    assert len(persisted) == 1 and persisted[0].status == "queued"
    pending = await mission_control._board.get(task.task_id)
    assert pending is not None and pending.status == TaskStatus.PENDING

    monkeypatch.setattr(mission_control._board, "assign", original_assign)
    retried = await mission_control.start_attempt(
        "m-alpha", task.task_id, "agent-a", attempt_key="attempt-proof"
    )
    projected = await mission_control._board.get(task.task_id)
    assert retried.attempt_id == persisted[0].run_id
    assert projected is not None and projected.status == TaskStatus.ASSIGNED


@pytest.mark.asyncio
async def test_heartbeat_and_finish_metadata_cannot_override_canonical_identity(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await mission_control.start_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_key="attempt-proof",
        metadata={
            "schema_version": "foreign",
            "mission_id": "foreign",
            "attempt_id": "foreign",
            "attempt_key": "foreign",
        },
    )
    await mission_control.heartbeat_lease(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        metadata={
            "schema_version": "heartbeat-foreign",
            "mission_id": "heartbeat-foreign",
            "attempt_id": "heartbeat-foreign",
            "attempt_key": "heartbeat-foreign",
            "heartbeat_note": "kept",
        },
    )
    receipt = await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
        metadata={
            "schema_version": "finish-foreign",
            "mission_id": "finish-foreign",
            "attempt_id": "finish-foreign",
            "attempt_key": "finish-foreign",
            "finish_note": "kept",
        },
    )

    run = await mission_control._runtime.get_delegation_run(attempt.attempt_id)
    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert run is not None and claim is not None
    for canonical in (run.metadata, claim.metadata, receipt.payload["metadata"]):
        assert canonical["schema_version"] == SCHEMA_VERSION
        assert canonical["mission_id"] == "m-alpha"
        assert canonical["attempt_id"] == attempt.attempt_id
        assert canonical["attempt_key"] == "attempt-proof"
    assert receipt.payload["metadata"]["finish_note"] == "kept"


@pytest.mark.asyncio
async def test_attempt_resolution_without_id_rejects_ambiguity(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    first = await mission_control.start_attempt(
        "m-alpha", task.task_id, "agent-a", attempt_key="attempt-one"
    )
    first_claim = await mission_control._runtime.get_task_claim(first.claim_id)
    assert first_claim is not None
    await mission_control._runtime.record_task_claim(
        replace(
            first_claim,
            stale_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    second = await mission_control.start_attempt(
        "m-alpha", task.task_id, "agent-a", attempt_key="attempt-two"
    )

    with pytest.raises(MissionControlError, match="ambiguous"):
        await mission_control.heartbeat_lease(
            "m-alpha", task.task_id, "agent-a"
        )
    lease = await mission_control.heartbeat_lease(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=second.attempt_id,
    )
    assert lease.active is True


@pytest.mark.parametrize(
    ("field_name", "foreign_value"),
    (
        ("run_id", "foreign-run"),
        ("task_id", "foreign-task"),
        ("trace_id", "foreign-trace"),
        ("correlation_id", "foreign-correlation"),
        ("causation_id", "foreign-causation"),
        ("parent_run_id", "foreign-parent"),
        ("agent_id", "foreign-agent"),
        ("side_effect_key", "foreign-side-effect"),
        ("receipt_type", "foreign-terminal-type"),
    ),
)
@pytest.mark.asyncio
async def test_terminal_receipt_conflict_checks_canonical_run_task_and_agent(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    foreign_value: str,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    original_complete = mission_control._board.complete

    async def crash_before_projection(*args, **kwargs):
        raise TaskBoardError("simulated terminal projection crash")

    monkeypatch.setattr(mission_control._board, "complete", crash_before_projection)
    with pytest.raises(MissionControlError, match="terminal projection crash"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
        )
    terminal = await mission_control._runtime.list_runtime_receipts(
        run_id=attempt.attempt_id,
        receipt_type="mission_attempt_terminal",
        limit=100,
    )
    assert len(terminal) == 1
    tampered = replace(terminal[0], **{field_name: foreign_value})
    original_list_receipts = mission_control._runtime.list_runtime_receipts

    async def list_with_tampered_terminal(*args, **kwargs):
        if kwargs.get("receipt_type") == "mission_attempt_terminal":
            return [tampered]
        return await original_list_receipts(*args, **kwargs)

    monkeypatch.setattr(mission_control._board, "complete", original_complete)
    monkeypatch.setattr(
        mission_control._runtime,
        "list_runtime_receipts",
        list_with_tampered_terminal,
    )
    with pytest.raises(MissionControlError, match="conflicting terminal evidence"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
        )


@pytest.mark.asyncio
async def test_create_task_fails_closed_when_idempotency_scan_saturates(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = await _mission_task(mission_control)
    backing = await mission_control._board.get(existing.task_id)
    assert backing is not None

    async def saturated_scan(*args, **kwargs):
        assert kwargs["limit"] == 10_001
        return [backing] * 10_001

    monkeypatch.setattr(mission_control._board, "list_tasks", saturated_scan)
    with pytest.raises(MissionControlError, match="scan saturated"):
        await mission_control.create_task(
            "m-alpha",
            title="Cannot prove unique",
            idempotency_key="beyond-scan-boundary",
        )


@pytest.mark.asyncio
async def test_conflicting_concurrent_finishes_publish_one_terminal_receipt(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)

    outcomes = await asyncio.gather(
        mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
            result="winner-a",
        ),
        mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="failed",
            result="winner-b",
            failure_code="conflict",
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(outcome, MissionControlError) for outcome in outcomes) == 1
    terminal = await mission_control._runtime.list_runtime_receipts(
        run_id=attempt.attempt_id,
        receipt_type="mission_attempt_terminal",
        limit=100,
    )
    assert len(terminal) == 1
    assert terminal[0].status in {"succeeded", "failed"}


@pytest.mark.asyncio
async def test_tests_use_only_explicit_state_paths(
    mission_control: MissionControl,
    tmp_path: Path,
) -> None:
    assert mission_control._runtime.db_path.name == "runtime.db"
    assert mission_control._runtime.db_path.is_relative_to(tmp_path)
    assert mission_control._runtime.db_path != Path.home() / ".dharma/state/runtime.db"


@pytest.mark.asyncio
async def test_same_instance_start_race_publishes_one_claim_and_run(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)

    outcomes = await asyncio.gather(
        mission_control.start_attempt(
            "m-alpha", task.task_id, "agent-a", attempt_key="race-a"
        ),
        mission_control.start_attempt(
            "m-alpha", task.task_id, "agent-b", attempt_key="race-b"
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(value, MissionControlError) for value in outcomes) == 1
    claims = await mission_control._runtime.list_task_claims(
        task_id=task.task_id, limit=100
    )
    runs = await mission_control._runtime.list_delegation_runs(
        task_id=task.task_id, limit=100
    )
    assert len(claims) == 1
    assert len(runs) == 1


@pytest.mark.asyncio
async def test_same_instance_heartbeat_finish_race_never_reopens_terminal_work(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)

    await asyncio.gather(
        mission_control.heartbeat_lease(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
        ),
        mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
            result="race-safe",
        ),
        return_exceptions=True,
    )

    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    run = await mission_control._runtime.get_delegation_run(attempt.attempt_id)
    assert claim is not None and claim.status == "completed"
    assert run is not None and run.status == "completed"
    with pytest.raises(MissionControlError, match="cannot heartbeat"):
        await mission_control.heartbeat_lease(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
        )


@pytest.mark.asyncio
async def test_heartbeat_rejects_terminal_task_without_mutating_lease(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    before = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert before is not None
    await mission_control._board.complete(task.task_id, result="external terminal")

    with pytest.raises(MissionControlError, match="terminal"):
        await mission_control.heartbeat_lease(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
        )

    after = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert after == before
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert (
        snapshot.reconciliation
        == ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
    )


@pytest.mark.asyncio
async def test_stale_terminal_cas_is_quarantined_reclaimed_and_completed(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    original_begin = (
        mission_control._runtime.try_begin_idempotent_side_effect_with_token
    )
    original_now = runtime_state_module._utc_now
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=2)

    async def begin_then_crash(identity, side_effect_key, **kwargs):
        monkeypatch.setattr(runtime_state_module, "_utc_now", lambda: stale_time)
        try:
            await original_begin(
                identity,
                side_effect_key,
                metadata=kwargs.get("metadata"),
            )
        finally:
            monkeypatch.setattr(runtime_state_module, "_utc_now", original_now)
        raise RuntimeError("simulated crash after terminal CAS")

    monkeypatch.setattr(
        mission_control._runtime,
        "try_begin_idempotent_side_effect_with_token",
        begin_then_crash,
    )
    with pytest.raises(MissionControlError, match="conflicting terminal evidence"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
            result="reclaimed",
        )

    monkeypatch.setattr(
        mission_control._runtime,
        "try_begin_idempotent_side_effect_with_token",
        original_begin,
    )
    receipt = await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
        result="reclaimed",
    )
    identity = await mission_control._runtime.get_execution_identity(
        attempt.attempt_id
    )
    assert identity is not None
    record = await mission_control._runtime.get_idempotency_record(
        identity.idempotency_key,
        f"mission_control:{attempt.attempt_id}:terminal",
    )
    assert record is not None and record.status == "completed"
    assert record.result_receipt_id == receipt.receipt_id


@pytest.mark.asyncio
async def test_expired_takeover_terminalizes_prior_lineage_before_reassignment(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    first = await _active_attempt(
        mission_control,
        task.task_id,
        agent_id="agent-a",
        attempt_key="takeover-one",
    )
    first_claim = await mission_control._runtime.get_task_claim(first.claim_id)
    assert first_claim is not None
    await mission_control._runtime.record_task_claim(
        replace(
            first_claim,
            stale_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )

    second = await mission_control.start_attempt(
        "m-alpha",
        task.task_id,
        "agent-b",
        attempt_key="takeover-two",
    )
    recovered_claim = await mission_control._runtime.get_task_claim(first.claim_id)
    recovered_run = await mission_control._runtime.get_delegation_run(first.attempt_id)
    recovery = await mission_control._runtime.list_runtime_receipts(
        run_id=first.attempt_id,
        receipt_type="mission_attempt_recovery",
        limit=100,
    )
    assert recovered_claim is not None and recovered_claim.status == "stale_recovered"
    assert recovered_run is not None and recovered_run.status == "stale_recovered"
    assert len(recovery) == 1 and recovery[0].status == "stale_recovered"
    assert recovery[0].created_at <= recovered_run.completed_at

    active_runs = await OperatorViews(mission_control._runtime).active_runs(
        session_id="mission:m-alpha", limit=10
    )
    assert [run.run_id for run in active_runs] == [second.attempt_id]
    with pytest.raises(MissionControlError, match="superseded"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=first.attempt_id,
            status="succeeded",
        )
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.reconciliation == ReconciliationState.COHERENT


@pytest.mark.asyncio
async def test_snapshot_reports_foreign_runtime_receipt_identity(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
    )
    terminal = await mission_control._runtime.list_runtime_receipts(
        run_id=attempt.attempt_id,
        receipt_type="mission_attempt_terminal",
        limit=100,
    )
    assert len(terminal) == 1
    await mission_control._runtime.record_runtime_receipt(
        replace(terminal[0], trace_id="foreign-trace")
    )

    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.reconciliation == ReconciliationState.FOREIGN_RUNTIME_RECORD


@pytest.mark.asyncio
async def test_snapshot_reports_multiple_terminal_receipts_as_conflict(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
    )
    identity = await mission_control._runtime.get_execution_identity(
        attempt.attempt_id
    )
    terminal = await mission_control._runtime.list_runtime_receipts(
        run_id=attempt.attempt_id,
        receipt_type="mission_attempt_terminal",
        limit=100,
    )
    assert identity is not None and len(terminal) == 1
    await mission_control._runtime.record_receipt_for_identity(
        identity,
        receipt_type="mission_attempt_terminal",
        status="succeeded",
        side_effect_key=terminal[0].side_effect_key,
        payload=terminal[0].payload,
        receipt_id="extra-terminal-receipt",
    )

    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert (
        snapshot.reconciliation
        == ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
    )


@pytest.mark.asyncio
async def test_expired_takeover_repairs_durable_terminal_without_new_attempt(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    original_record_run = mission_control._runtime.record_delegation_run

    async def crash_before_terminal_run_projection(run):
        if run.run_id == attempt.attempt_id and run.status == "completed":
            raise RuntimeError("simulated receipt-before-run crash")
        return await original_record_run(run)

    monkeypatch.setattr(
        mission_control._runtime,
        "record_delegation_run",
        crash_before_terminal_run_projection,
    )
    with pytest.raises(RuntimeError, match="receipt-before-run"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
            result="durable-result",
        )
    monkeypatch.setattr(
        mission_control._runtime,
        "record_delegation_run",
        original_record_run,
    )
    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert claim is not None and claim.status == "active"
    await mission_control._runtime.record_task_claim(
        replace(
            claim,
            stale_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )

    with pytest.raises(MissionControlError, match="cannot start from 'completed'"):
        await mission_control.start_attempt(
            "m-alpha",
            task.task_id,
            "agent-b",
            attempt_key="must-not-be-created",
        )

    repaired_run = await mission_control._runtime.get_delegation_run(
        attempt.attempt_id
    )
    repaired_claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    projected = await mission_control._board.get(task.task_id)
    recoveries = await mission_control._runtime.list_runtime_receipts(
        run_id=attempt.attempt_id,
        receipt_type="mission_attempt_recovery",
        limit=10,
    )
    runs = await mission_control._runtime.list_delegation_runs(
        task_id=task.task_id,
        limit=10,
    )
    assert repaired_run is not None and repaired_run.status == "completed"
    assert repaired_claim is not None and repaired_claim.status == "completed"
    assert projected is not None and projected.status == TaskStatus.COMPLETED
    assert recoveries == []
    assert [run.run_id for run in runs] == [attempt.attempt_id]


@pytest.mark.asyncio
async def test_terminal_projection_keeps_claim_open_until_task_is_terminal(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)

    async def crash_before_task_projection(*args, **kwargs):
        raise TaskBoardError("task projection unavailable")

    monkeypatch.setattr(
        mission_control._board, "complete", crash_before_task_projection
    )
    with pytest.raises(MissionControlError, match="task projection unavailable"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
        )
    run = await mission_control._runtime.get_delegation_run(attempt.attempt_id)
    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert run is not None and run.status == "completed"
    assert claim is not None and claim.status == "active"


@pytest.mark.asyncio
async def test_post_task_pre_claim_crash_is_projection_drift_not_coherent(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    original_record_claim = mission_control._runtime.record_task_claim

    async def crash_before_claim_close(claim):
        if claim.claim_id == attempt.claim_id and claim.status == "completed":
            raise RuntimeError("simulated task-before-claim crash")
        return await original_record_claim(claim)

    monkeypatch.setattr(
        mission_control._runtime, "record_task_claim", crash_before_claim_close
    )
    with pytest.raises(RuntimeError, match="task-before-claim"):
        await mission_control.finish_attempt(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
            status="succeeded",
        )
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.tasks[0].status == TaskStatus.COMPLETED
    assert snapshot.attempts[0].status == "succeeded"
    assert snapshot.leases[0].status == "active"
    assert snapshot.reconciliation == ReconciliationState.NEEDS_TASK_PROJECTION

    monkeypatch.setattr(
        mission_control._runtime, "record_task_claim", original_record_claim
    )
    await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
    )
    repaired = await mission_control.get_snapshot("m-alpha")
    assert repaired is not None
    assert repaired.leases[0].status == "completed"
    assert repaired.reconciliation == ReconciliationState.COHERENT


@pytest.mark.asyncio
async def test_snapshot_rejects_terminal_claim_outcome_mismatch(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
    )
    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert claim is not None
    await mission_control._runtime.record_task_claim(replace(claim, status="failed"))
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert (
        snapshot.reconciliation
        == ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
    )


@pytest.mark.asyncio
async def test_recovery_claim_close_crash_is_projection_drift_and_retry_repairs(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    first = await _active_attempt(
        mission_control,
        task.task_id,
        agent_id="agent-a",
        attempt_key="recovery-crash-one",
    )
    claim = await mission_control._runtime.get_task_claim(first.claim_id)
    assert claim is not None
    await mission_control._runtime.record_task_claim(
        replace(
            claim,
            stale_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    original_record_claim = mission_control._runtime.record_task_claim

    async def crash_before_recovery_claim_close(candidate):
        if candidate.claim_id == first.claim_id and candidate.status == "stale_recovered":
            raise RuntimeError("simulated recovery-before-claim crash")
        return await original_record_claim(candidate)

    monkeypatch.setattr(
        mission_control._runtime,
        "record_task_claim",
        crash_before_recovery_claim_close,
    )
    with pytest.raises(RuntimeError, match="recovery-before-claim"):
        await mission_control.start_attempt(
            "m-alpha",
            task.task_id,
            "agent-b",
            attempt_key="recovery-crash-two",
        )
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.attempts[0].status == "stale_recovered"
    assert snapshot.leases[0].status == "active"
    assert snapshot.reconciliation == ReconciliationState.NEEDS_TASK_PROJECTION

    monkeypatch.setattr(
        mission_control._runtime, "record_task_claim", original_record_claim
    )
    second = await mission_control.start_attempt(
        "m-alpha",
        task.task_id,
        "agent-b",
        attempt_key="recovery-crash-two",
    )
    repaired = await mission_control._runtime.get_task_claim(first.claim_id)
    assert repaired is not None and repaired.status == "stale_recovered"
    assert second.status == "queued"


@pytest.mark.asyncio
async def test_terminal_claim_without_run_never_reports_coherent(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await _active_attempt(mission_control, task.task_id)
    await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
    )

    async def missing_runs(*args, **kwargs):
        return []

    async def missing_receipts(*args, **kwargs):
        return []

    monkeypatch.setattr(
        mission_control._runtime, "list_delegation_runs", missing_runs
    )
    monkeypatch.setattr(
        mission_control._runtime, "list_runtime_receipts", missing_receipts
    )
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.leases[0].status == "completed"
    assert snapshot.attempts == ()
    assert snapshot.reconciliation == ReconciliationState.FOREIGN_RUNTIME_RECORD


@pytest.mark.asyncio
async def test_snapshot_receipt_budget_is_global_across_attempts(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    first = await _active_attempt(
        mission_control,
        task.task_id,
        agent_id="agent-a",
        attempt_key="receipt-budget-one",
    )
    claim = await mission_control._runtime.get_task_claim(first.claim_id)
    assert claim is not None
    await mission_control._runtime.record_task_claim(
        replace(
            claim,
            stale_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    second = await mission_control.start_attempt(
        "m-alpha",
        task.task_id,
        "agent-b",
        attempt_key="receipt-budget-two",
    )
    await mission_control.heartbeat_lease(
        "m-alpha",
        task.task_id,
        "agent-b",
        attempt_id=second.attempt_id,
    )
    await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-b",
        attempt_id=second.attempt_id,
        status="succeeded",
    )

    monkeypatch.setattr(mission_control_module, "RUNTIME_SCAN_LIMIT", 2)
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert len(snapshot.receipts) <= 2
    assert snapshot.reconciliation == ReconciliationState.EVIDENCE_SCAN_SATURATED


@pytest.mark.asyncio
async def test_terminal_finish_repairs_running_run_with_assigned_task(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await mission_control.start_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_key="running-projection-crash",
    )
    original_project_running = mission_control._project_running_task

    async def crash_after_running_run(*args, **kwargs):
        raise RuntimeError("simulated run-before-task crash")

    monkeypatch.setattr(
        mission_control, "_project_running_task", crash_after_running_run
    )
    with pytest.raises(RuntimeError, match="run-before-task"):
        await mission_control.heartbeat_lease(
            "m-alpha",
            task.task_id,
            "agent-a",
            attempt_id=attempt.attempt_id,
        )
    run = await mission_control._runtime.get_delegation_run(attempt.attempt_id)
    projected = await mission_control._board.get(task.task_id)
    assert run is not None and run.status == "running"
    assert projected is not None and projected.status == TaskStatus.ASSIGNED

    monkeypatch.setattr(
        mission_control, "_project_running_task", original_project_running
    )
    receipt = await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-a",
        attempt_id=attempt.attempt_id,
        status="succeeded",
        result="repaired",
    )
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert receipt.status == "succeeded"
    assert snapshot is not None
    assert snapshot.tasks[0].status == TaskStatus.COMPLETED
    assert snapshot.attempts[0].status == "succeeded"
    assert snapshot.leases[0].status == "completed"
    assert snapshot.reconciliation == ReconciliationState.COHERENT


@pytest.mark.asyncio
async def test_post_recovery_pre_replacement_crash_is_projection_drift(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    first = await _active_attempt(
        mission_control,
        task.task_id,
        agent_id="agent-a",
        attempt_key="post-recovery-one",
    )
    claim = await mission_control._runtime.get_task_claim(first.claim_id)
    assert claim is not None
    await mission_control._runtime.record_task_claim(
        replace(
            claim,
            stale_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    original_recover = mission_control._recover_expired_claim

    async def recover_then_crash(*args, **kwargs):
        repaired_terminal = await original_recover(*args, **kwargs)
        assert repaired_terminal is False
        raise RuntimeError("simulated recovery-before-replacement crash")

    monkeypatch.setattr(
        mission_control, "_recover_expired_claim", recover_then_crash
    )
    with pytest.raises(RuntimeError, match="recovery-before-replacement"):
        await mission_control.start_attempt(
            "m-alpha",
            task.task_id,
            "agent-b",
            attempt_key="post-recovery-two",
        )
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.tasks[0].status == TaskStatus.RUNNING
    assert snapshot.tasks[0].metadata["mission_attempt_id"] == first.attempt_id
    assert snapshot.attempts[0].status == "stale_recovered"
    assert snapshot.leases[0].status == "stale_recovered"
    assert snapshot.reconciliation == ReconciliationState.NEEDS_TASK_PROJECTION

    monkeypatch.setattr(
        mission_control, "_recover_expired_claim", original_recover
    )
    second = await mission_control.start_attempt(
        "m-alpha",
        task.task_id,
        "agent-b",
        attempt_key="post-recovery-two",
    )
    repaired = await mission_control.get_snapshot("m-alpha")
    assert second.status == "queued"
    assert repaired is not None
    assert repaired.tasks[0].metadata["mission_attempt_id"] == second.attempt_id
    assert repaired.reconciliation == ReconciliationState.COHERENT


@pytest.mark.asyncio
async def test_recovery_evidence_cannot_authorize_terminal_task(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    first = await _active_attempt(
        mission_control,
        task.task_id,
        agent_id="agent-a",
        attempt_key="recovery-terminal-one",
    )
    claim = await mission_control._runtime.get_task_claim(first.claim_id)
    assert claim is not None
    await mission_control._runtime.record_task_claim(
        replace(
            claim,
            stale_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    await mission_control._recover_expired_claim(
        "m-alpha", claim, recovered_at=datetime.now(timezone.utc)
    )
    await mission_control._board.complete(task.task_id, result="foreign completion")
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert (
        snapshot.reconciliation
        == ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
    )


@pytest.mark.asyncio
async def test_recovered_attempt_then_replacement_success_is_coherent(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    first = await _active_attempt(
        mission_control,
        task.task_id,
        agent_id="agent-a",
        attempt_key="replacement-success-one",
    )
    claim = await mission_control._runtime.get_task_claim(first.claim_id)
    assert claim is not None
    await mission_control._runtime.record_task_claim(
        replace(
            claim,
            stale_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    second = await mission_control.start_attempt(
        "m-alpha",
        task.task_id,
        "agent-b",
        attempt_key="replacement-success-two",
    )
    await mission_control.heartbeat_lease(
        "m-alpha",
        task.task_id,
        "agent-b",
        attempt_id=second.attempt_id,
    )
    await mission_control.finish_attempt(
        "m-alpha",
        task.task_id,
        "agent-b",
        attempt_id=second.attempt_id,
        status="succeeded",
    )
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert {attempt.status for attempt in snapshot.attempts} == {
        "stale_recovered",
        "succeeded",
    }
    assert snapshot.tasks[0].status == TaskStatus.COMPLETED
    assert snapshot.reconciliation == ReconciliationState.COHERENT


@pytest.mark.asyncio
async def test_task_projection_without_matching_run_is_never_coherent(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    await mission_control._board.assign(task.task_id, "foreign-agent")
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.tasks[0].status == TaskStatus.ASSIGNED
    assert snapshot.reconciliation == ReconciliationState.NEEDS_TASK_PROJECTION


@pytest.mark.asyncio
async def test_unknown_owner_lifecycle_status_is_foreign_runtime_state(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    attempt = await mission_control.start_attempt(
        "m-alpha", task.task_id, "agent-a", attempt_key="unknown-owner-status"
    )
    run = await mission_control._runtime.get_delegation_run(attempt.attempt_id)
    assert run is not None
    await mission_control._runtime.record_delegation_run(
        replace(run, status="mystery")
    )
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.reconciliation == ReconciliationState.FOREIGN_RUNTIME_RECORD


@pytest.mark.asyncio
async def test_creation_races_are_serialized_with_complete_content(
    mission_control: MissionControl,
) -> None:
    mission_results = await asyncio.gather(
        mission_control.create_mission(
            "race-mission", title="One", operator_id="operator-one"
        ),
        mission_control.create_mission(
            "race-mission", title="Two", operator_id="operator-two"
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(item, MissionControlError) for item in mission_results) == 1

    await mission_control.create_mission("task-race", title="Task race")
    task_results = await asyncio.gather(
        mission_control.create_task(
            "task-race",
            title="Exactly once",
            priority=TaskPriority.HIGH,
            created_by="creator",
            idempotency_key="same-key",
            metadata={"shape": "same"},
        ),
        mission_control.create_task(
            "task-race",
            title="Exactly once",
            priority=TaskPriority.HIGH,
            created_by="creator",
            idempotency_key="same-key",
            metadata={"shape": "same"},
        ),
    )
    assert task_results[0].task_id == task_results[1].task_id
    assert len(await mission_control.list_tasks("task-race")) == 1


@pytest.mark.parametrize(
    "changed",
    (
        {"priority": TaskPriority.HIGH},
        {"created_by": "different-creator"},
        {"metadata": {"shape": "different"}},
    ),
)
@pytest.mark.asyncio
async def test_task_idempotency_rejects_all_material_content_conflicts(
    mission_control: MissionControl,
    changed: dict[str, object],
) -> None:
    await mission_control.create_mission("content-check", title="Content")
    base = {
        "title": "Stable task",
        "priority": TaskPriority.NORMAL,
        "created_by": "creator",
        "idempotency_key": "content-key",
        "metadata": {"shape": "base"},
    }
    await mission_control.create_task("content-check", **base)
    with pytest.raises(MissionControlError, match="conflicting content"):
        await mission_control.create_task(
            "content-check",
            **{**base, **changed},
        )


@pytest.mark.asyncio
async def test_cross_mission_dependency_is_rejected(
    mission_control: MissionControl,
) -> None:
    await mission_control.create_mission("mission-one", title="One")
    await mission_control.create_mission("mission-two", title="Two")
    dependency = await mission_control.create_task(
        "mission-one", title="Foreign dependency"
    )
    with pytest.raises(MissionControlError, match="does not belong"):
        await mission_control.create_task(
            "mission-two",
            title="Must remain scoped",
            depends_on=[dependency.task_id],
        )


@pytest.mark.asyncio
async def test_task_idempotency_rejects_a_changed_dependency_set(
    mission_control: MissionControl,
) -> None:
    await mission_control.create_mission("dependency-content", title="Dependencies")
    first_dependency = await mission_control.create_task(
        "dependency-content", title="First dependency"
    )
    second_dependency = await mission_control.create_task(
        "dependency-content", title="Second dependency"
    )
    await mission_control.create_task(
        "dependency-content",
        title="Dependent",
        depends_on=[first_dependency.task_id],
        idempotency_key="dependency-key",
    )
    with pytest.raises(MissionControlError, match="conflicting content"):
        await mission_control.create_task(
            "dependency-content",
            title="Dependent",
            depends_on=[second_dependency.task_id],
            idempotency_key="dependency-key",
        )


@pytest.mark.asyncio
async def test_snapshot_rejects_forged_recovery_receipt_contract(
    mission_control: MissionControl,
) -> None:
    task = await _mission_task(mission_control)
    first = await _active_attempt(
        mission_control,
        task.task_id,
        agent_id="agent-a",
        attempt_key="recovery-contract-one",
    )
    claim = await mission_control._runtime.get_task_claim(first.claim_id)
    assert claim is not None
    await mission_control._runtime.record_task_claim(
        replace(
            claim,
            stale_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    await mission_control.start_attempt(
        "m-alpha",
        task.task_id,
        "agent-b",
        attempt_key="recovery-contract-two",
    )
    recovery = await mission_control._runtime.list_runtime_receipts(
        run_id=first.attempt_id,
        receipt_type="mission_attempt_recovery",
        limit=2,
    )
    assert len(recovery) == 1
    await mission_control._runtime.record_runtime_receipt(
        replace(recovery[0], side_effect_key="forged-recovery-effect")
    )
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert (
        snapshot.reconciliation
        == ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
    )


@pytest.mark.asyncio
async def test_snapshot_and_resolution_fail_closed_on_scan_saturation(
    mission_control: MissionControl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = await _mission_task(mission_control)
    backing = await mission_control._board.get(task.task_id)
    assert backing is not None
    monkeypatch.setattr(mission_control_module, "TASK_SCAN_LIMIT", 1)

    async def saturated_tasks(*args, **kwargs):
        assert kwargs["limit"] == 2
        return [backing, backing]

    monkeypatch.setattr(mission_control._board, "list_tasks", saturated_tasks)
    snapshot = await mission_control.get_snapshot("m-alpha")
    assert snapshot is not None
    assert snapshot.reconciliation == ReconciliationState.EVIDENCE_SCAN_SATURATED

    monkeypatch.undo()
    attempt = await mission_control.start_attempt(
        "m-alpha", task.task_id, "agent-a", attempt_key="scan-attempt"
    )
    run = await mission_control._runtime.get_delegation_run(attempt.attempt_id)
    claim = await mission_control._runtime.get_task_claim(attempt.claim_id)
    assert run is not None and claim is not None
    monkeypatch.setattr(mission_control_module, "RUNTIME_SCAN_LIMIT", 1)

    async def saturated_runs(*args, **kwargs):
        assert kwargs["limit"] == 2
        return [run, run]

    monkeypatch.setattr(
        mission_control._runtime, "list_delegation_runs", saturated_runs
    )
    with pytest.raises(MissionControlError, match="attempt scan saturated"):
        await mission_control.heartbeat_lease(
            "m-alpha", task.task_id, "agent-a"
        )

    async def saturated_claims(*args, **kwargs):
        assert kwargs["limit"] == 2
        return [claim, claim]

    monkeypatch.setattr(mission_control._runtime, "list_task_claims", saturated_claims)
    with pytest.raises(MissionControlError, match="claim scan saturated"):
        await mission_control._claims_for_fencing(task.task_id)


def test_public_callable_provenance_survives_module_split() -> None:
    """Keep rollback-compatible function paths across private mixin extraction."""
    import pickle

    from dharma_swarm.mission_control_mcp import MissionControlMCPService
    from dharma_swarm.mission_control_projection import reconciliation

    expected = [
        (MissionControl.start_attempt, "dharma_swarm.mission_control", "MissionControl.start_attempt"),
        (MissionControl.heartbeat_lease, "dharma_swarm.mission_control", "MissionControl.heartbeat_lease"),
        (MissionControl.finish_attempt, "dharma_swarm.mission_control", "MissionControl.finish_attempt"),
        (reconciliation, "dharma_swarm.mission_control_projection", "reconciliation"),
    ]
    expected.extend(
        (
            getattr(MissionControlMCPService, method_name),
            "dharma_swarm.mission_control_mcp",
            f"MissionControlMCPService.{method_name}",
        )
        for method_name in (
            "create_mission",
            "create_task",
            "start_attempt",
            "heartbeat_lease",
            "finish_attempt",
        )
    )
    for function, module_name, qualified_name in expected:
        assert function.__module__ == module_name
        assert function.__qualname__ == qualified_name
        assert pickle.loads(pickle.dumps(function, protocol=0)) is function
