from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.runtime_activity import (
    RuntimeActivityState,
    RuntimeIdentityState,
    RuntimeLeasePolicy,
    classify_runtime_activity,
    load_runtime_activity,
)
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity


NOW = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)


def _identity(*, claim_id: str = "claim-1", agent_id: str = "worker-1") -> ExecutionIdentity:
    return ExecutionIdentity.new(
        trace_id="trace-1",
        correlation_id="corr-1",
        task_id="task-1",
        run_id="run-1",
        claim_id=claim_id,
        idempotency_key="idem-1",
        agent_id=agent_id,
        session_id="sess-1",
    )


def _claim(**updates) -> TaskClaim:
    claim = TaskClaim(
        claim_id="claim-1",
        task_id="task-1",
        session_id="sess-1",
        agent_id="worker-1",
        status="active",
        claimed_at=NOW - timedelta(minutes=3),
        acked_at=NOW - timedelta(minutes=2),
        heartbeat_at=NOW - timedelta(minutes=1),
        stale_after=NOW + timedelta(minutes=4),
    )
    return replace(claim, **updates)


def _run(**updates) -> DelegationRun:
    run = DelegationRun(
        run_id="run-1",
        task_id="task-1",
        session_id="sess-1",
        claim_id="claim-1",
        assigned_to="worker-1",
        assigned_by="operator",
        status="running",
        started_at=NOW - timedelta(minutes=3),
    )
    return replace(run, **updates)


def test_matching_current_lease_never_proves_executor_liveness() -> None:
    observation = classify_runtime_activity(
        _run(),
        claim=_claim(),
        identity=_identity(),
        observed_at=NOW,
    )

    assert observation.state is RuntimeActivityState.CURRENT_LEASE
    assert observation.identity_state is RuntimeIdentityState.MATCHED
    assert observation.current_lease is True
    assert observation.observed_nonterminal is True
    assert observation.proves_executor_liveness is False
    assert observation.to_dict()["executor_liveness"] == "unproven"


def test_ack_and_heartbeat_are_independent_sibling_observations() -> None:
    observation = classify_runtime_activity(
        _run(),
        claim=_claim(
            heartbeat_at=NOW - timedelta(minutes=1),
            acked_at=NOW - timedelta(minutes=1) + timedelta(microseconds=4),
        ),
        identity=_identity(),
        observed_at=NOW,
    )

    assert observation.state is RuntimeActivityState.CURRENT_LEASE
    assert "heartbeat_precedes_ack" not in observation.reason_codes


def test_orchestrator_heartbeat_window_can_extend_original_deadline() -> None:
    observation = classify_runtime_activity(
        _run(metadata={"source": "orchestrator"}),
        claim=_claim(
            claimed_at=NOW - timedelta(minutes=10),
            acked_at=NOW - timedelta(minutes=9),
            heartbeat_at=NOW - timedelta(minutes=1),
            stale_after=NOW - timedelta(minutes=5),
            metadata={"source": "orchestrator"},
        ),
        identity=_identity(),
        observed_at=NOW,
    )

    assert observation.state is RuntimeActivityState.CURRENT_LEASE
    assert (
        observation.lease_policy
        is RuntimeLeasePolicy.ORCHESTRATOR_HEARTBEAT_WINDOW
    )
    assert "heartbeat_window_extends_deadline" in observation.reason_codes


def test_orchestrator_heartbeat_window_expires_at_exact_boundary() -> None:
    observation = classify_runtime_activity(
        _run(metadata={"source": "orchestrator"}),
        claim=_claim(
            claimed_at=NOW - timedelta(minutes=10),
            acked_at=NOW - timedelta(minutes=9),
            heartbeat_at=NOW - timedelta(minutes=5),
            stale_after=NOW - timedelta(minutes=5),
            metadata={"source": "orchestrator"},
        ),
        identity=_identity(),
        observed_at=NOW,
    )

    assert observation.state is RuntimeActivityState.EXPIRED_OR_UNPROVEN
    assert "heartbeat_window_expired" in observation.reason_codes


def test_mission_control_never_uses_generic_heartbeat_grace() -> None:
    observation = classify_runtime_activity(
        _run(metadata={"schema_version": "dharma.mission_control.v1"}),
        claim=_claim(
            heartbeat_at=NOW - timedelta(seconds=1),
            stale_after=NOW,
            metadata={"schema_version": "dharma.mission_control.v1"},
        ),
        identity=_identity(),
        observed_at=NOW,
    )

    assert observation.state is RuntimeActivityState.EXPIRED_OR_UNPROVEN
    assert observation.lease_policy is RuntimeLeasePolicy.MISSION_CONTROL_STRICT
    assert "lease_expired" in observation.reason_codes


@pytest.mark.parametrize(
    ("claim", "identity", "run", "reason"),
    [
        (
            _claim(stale_after=NOW - timedelta(seconds=1)),
            _identity(),
            _run(),
            "lease_expired",
        ),
        (
            _claim(acked_at=None, heartbeat_at=None),
            _identity(),
            _run(status="claimed"),
            "claim_unacknowledged",
        ),
        (_claim(), None, _run(), "execution_identity_missing"),
        (
            _claim(),
            _identity(agent_id="different-worker"),
            _run(),
            "execution_identity_conflict",
        ),
        (
            _claim(),
            _identity(),
            _run(status="mysterious"),
            "run_status_not_recognized_open",
        ),
    ],
)
def test_ambiguous_or_expired_rows_fail_closed_without_being_hidden(
    claim: TaskClaim,
    identity: ExecutionIdentity | None,
    run: DelegationRun,
    reason: str,
) -> None:
    observation = classify_runtime_activity(
        run,
        claim=claim,
        identity=identity,
        observed_at=NOW,
    )

    assert observation.state is RuntimeActivityState.EXPIRED_OR_UNPROVEN
    assert observation.current_lease is False
    assert observation.observed_nonterminal is True
    assert reason in observation.reason_codes


def test_completed_at_is_terminal_evidence_even_when_status_says_running() -> None:
    observation = classify_runtime_activity(
        _run(completed_at=NOW - timedelta(seconds=1)),
        claim=_claim(),
        identity=_identity(),
        observed_at=NOW,
    )

    assert observation.state is RuntimeActivityState.TERMINAL_EVIDENCE
    assert observation.terminal_evidence_conflict is True
    assert observation.observed_nonterminal is True
    assert observation.current_lease is False


@pytest.mark.parametrize(
    "later_status",
    ["claimed", "completed", "failed", "recovered", "stale_recovered"],
)
@pytest.mark.asyncio
async def test_later_claim_permanently_fences_an_otherwise_current_lease(
    tmp_path,
    later_status: str,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await store.record_execution_identity(_identity(), source="test")
    await store.record_task_claim(_claim())
    await store.record_delegation_run(_run())
    await store.record_task_claim(
        TaskClaim(
            claim_id="claim-2",
            task_id="task-1",
            session_id="sess-1",
            agent_id="worker-2",
            status=later_status,
            claimed_at=NOW - timedelta(seconds=30),
            stale_after=NOW + timedelta(minutes=5),
        )
    )

    snapshot = load_runtime_activity(store.db_path, observed_at=NOW)
    observation = snapshot.by_run_id["run-1"]

    assert observation.state is RuntimeActivityState.EXPIRED_OR_UNPROVEN
    assert "superseded_by_later_claim" in observation.reason_codes
    assert snapshot.summary()["expired_or_unproven_run_count"] == 1


@pytest.mark.parametrize(
    ("claimed_at", "reason"),
    [
        (NOW - timedelta(seconds=30), "superseded_by_later_claim"),
        (NOW - timedelta(minutes=3), "claim_order_ambiguous"),
    ],
)
@pytest.mark.asyncio
async def test_competing_claim_fences_task_across_sessions(
    tmp_path,
    claimed_at: datetime,
    reason: str,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await store.record_execution_identity(_identity(), source="test")
    await store.record_task_claim(_claim())
    await store.record_delegation_run(_run())
    await store.record_task_claim(
        TaskClaim(
            claim_id="claim-other-session",
            task_id="task-1",
            session_id="sess-2",
            agent_id="worker-2",
            status="recovered",
            claimed_at=claimed_at,
            stale_after=NOW + timedelta(minutes=5),
        )
    )

    snapshot = load_runtime_activity(store.db_path, observed_at=NOW)
    observation = snapshot.by_run_id["run-1"]

    assert snapshot.summary()["current_lease_run_count"] == 0
    assert observation.state is RuntimeActivityState.EXPIRED_OR_UNPROVEN
    assert reason in observation.reason_codes


@pytest.mark.asyncio
async def test_equal_time_competing_claims_fail_closed(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    claimed_at = NOW - timedelta(minutes=3)
    for suffix in ("a", "b"):
        claim_id = f"claim-{suffix}"
        run_id = f"run-{suffix}"
        agent_id = f"worker-{suffix}"
        identity = ExecutionIdentity.new(
            trace_id=f"trace-{suffix}",
            correlation_id=f"corr-{suffix}",
            task_id="task-tie",
            run_id=run_id,
            claim_id=claim_id,
            idempotency_key=f"idem-{suffix}",
            agent_id=agent_id,
            session_id="sess-tie",
        )
        await store.record_execution_identity(identity, source="test")
        await store.record_task_claim(
            TaskClaim(
                claim_id=claim_id,
                task_id="task-tie",
                session_id="sess-tie",
                agent_id=agent_id,
                status="active",
                claimed_at=claimed_at,
                acked_at=claimed_at + timedelta(seconds=1),
                heartbeat_at=NOW - timedelta(seconds=1),
                stale_after=NOW + timedelta(minutes=5),
            )
        )
        await store.record_delegation_run(
            DelegationRun(
                run_id=run_id,
                task_id="task-tie",
                session_id="sess-tie",
                claim_id=claim_id,
                assigned_to=agent_id,
                status="running",
            )
        )

    snapshot = load_runtime_activity(store.db_path, observed_at=NOW)

    assert snapshot.summary()["current_lease_run_count"] == 0
    assert all(
        "claim_order_ambiguous" in observation.reason_codes
        for observation in snapshot.observations
    )


@pytest.mark.asyncio
async def test_two_fresh_open_claims_produce_no_current_lease(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    for index, suffix in enumerate(("older", "newer")):
        claim_id = f"claim-{suffix}"
        run_id = f"run-{suffix}"
        agent_id = f"worker-{suffix}"
        claimed_at = NOW - timedelta(minutes=3 - index)
        identity = ExecutionIdentity.new(
            trace_id=f"trace-{suffix}",
            correlation_id=f"corr-{suffix}",
            task_id="task-conflict",
            run_id=run_id,
            claim_id=claim_id,
            idempotency_key=f"idem-{suffix}",
            agent_id=agent_id,
            session_id="sess-conflict",
        )
        await store.record_execution_identity(identity, source="test")
        await store.record_task_claim(
            TaskClaim(
                claim_id=claim_id,
                task_id="task-conflict",
                session_id="sess-conflict",
                agent_id=agent_id,
                status="active",
                claimed_at=claimed_at,
                acked_at=claimed_at + timedelta(seconds=1),
                heartbeat_at=NOW - timedelta(seconds=1),
                stale_after=NOW + timedelta(minutes=5),
            )
        )
        await store.record_delegation_run(
            DelegationRun(
                run_id=run_id,
                task_id="task-conflict",
                session_id="sess-conflict",
                claim_id=claim_id,
                assigned_to=agent_id,
                status="running",
            )
        )

    snapshot = load_runtime_activity(store.db_path, observed_at=NOW)

    assert snapshot.summary()["current_lease_run_count"] == 0
    older = snapshot.by_run_id["run-older"]
    newer = snapshot.by_run_id["run-newer"]
    assert "superseded_by_later_claim" in older.reason_codes
    assert "competing_open_claim" in newer.reason_codes


@pytest.mark.asyncio
async def test_identity_bound_terminal_receipt_wins_over_nonterminal_row(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity()
    await store.record_execution_identity(identity, source="test")
    await store.record_task_claim(_claim())
    await store.record_delegation_run(_run())
    await store.record_runtime_receipt(
        RuntimeReceipt(
            receipt_id="receipt-terminal",
            receipt_type="delegation_run",
            status="completed",
            run_id=identity.run_id,
            task_id=identity.task_id,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            agent_id=identity.agent_id,
            idempotency_key=identity.idempotency_key,
            created_at=NOW - timedelta(seconds=1),
        )
    )

    snapshot = load_runtime_activity(store.db_path, observed_at=NOW)
    observation = snapshot.by_run_id["run-1"]

    assert observation.state is RuntimeActivityState.TERMINAL_EVIDENCE
    assert observation.terminal_evidence_conflict is True
    assert snapshot.summary()["terminal_evidence_conflict_count"] == 1
    assert snapshot.summary()["current_lease_run_count"] == 0


@pytest.mark.asyncio
async def test_activity_snapshot_keeps_run_and_classification_from_one_read(
    tmp_path,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await store.record_execution_identity(_identity(), source="test")
    await store.record_task_claim(_claim())
    await store.record_delegation_run(_run())

    captured = load_runtime_activity(store.db_path, observed_at=NOW)
    await store.record_delegation_run(
        _run(status="completed", completed_at=NOW + timedelta(seconds=1))
    )
    refreshed = load_runtime_activity(
        store.db_path, observed_at=NOW + timedelta(seconds=2)
    )

    assert captured.current_runs[0].status == "running"
    assert captured.by_run_id["run-1"].state is RuntimeActivityState.CURRENT_LEASE
    assert refreshed.current_runs == ()
    assert (
        refreshed.by_run_id["run-1"].state
        is RuntimeActivityState.TERMINAL_EVIDENCE
    )
