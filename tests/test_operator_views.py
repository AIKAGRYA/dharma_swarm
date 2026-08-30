from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.message_bus import MessageBus
from dharma_swarm.operator_bridge import OperatorBridge
from dharma_swarm.operator_views import OperatorViews
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeStateStore,
    SessionState,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity


@pytest.mark.asyncio
async def test_operator_views_surface_bridge_queue_and_runtime_overview(tmp_path) -> None:
    bus = MessageBus(tmp_path / "bridge.db")
    runtime_state = RuntimeStateStore(tmp_path / "runtime.db")
    bridge = OperatorBridge(
        message_bus=bus,
        ledger_dir=tmp_path / "ledgers",
        session_id="sess_views",
        runtime_state=runtime_state,
    )
    await bridge.init_db()
    record = await bridge.enqueue_task(
        task="Surface queue state in operator cockpit",
        sender="operator",
    )
    await bridge.claim_task(claimed_by="codex-runner", task_id=record.id)
    await bridge.acknowledge_task_claim(
        task_id=record.id,
        acknowledged_by="codex-runner",
    )
    await bridge.heartbeat_task(
        task_id=record.id,
        heartbeat_by="codex-runner",
        summary="working",
        progress=0.25,
    )
    await bridge.respond_task(
        task_id=record.id,
        status="done",
        summary="Delivered.",
        metadata={"ack_timeout_seconds": 1},
    )

    views = OperatorViews(runtime_state, bridge=bridge)
    queue = await views.bridge_queue(
        limit=10,
        now=datetime.now(timezone.utc) + timedelta(seconds=5),
    )
    overview = await views.runtime_overview(session_id="sess_views")
    overdue = await views.overdue_response_acks(
        limit=10,
        now=datetime.now(timezone.utc) + timedelta(seconds=5),
    )
    actions = await views.recent_operator_actions(session_id="sess_views", limit=10)

    assert len(queue) == 1
    assert queue[0].task_id == record.id
    assert queue[0].has_claim_ack is True
    assert queue[0].overdue_response_ack is True
    assert queue[0].last_heartbeat_at is not None
    assert len(overdue) == 1
    assert overdue[0].task_id == record.id
    assert overview.sessions == 1
    assert overview.claims == 1
    assert overview.runs == 1
    assert overview.operator_actions >= 4
    assert any(action["action_name"] == "bridge_task_responded" for action in actions)


@pytest.mark.asyncio
async def test_operator_activity_counts_only_identity_bound_current_leases(
    tmp_path,
    monkeypatch,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    now = datetime.now(timezone.utc)
    await store.upsert_session(SessionState(session_id="sess-activity", status="active"))

    async def seed_run(
        suffix: str,
        *,
        acked: bool,
        expired: bool,
    ) -> None:
        run_id = f"run-{suffix}"
        claim_id = f"claim-{suffix}"
        identity = ExecutionIdentity.new(
            trace_id=f"trace-{suffix}",
            correlation_id=f"corr-{suffix}",
            task_id=f"task-{suffix}",
            run_id=run_id,
            claim_id=claim_id,
            idempotency_key=f"idem-{suffix}",
            agent_id=f"worker-{suffix}",
            session_id="sess-activity",
        )
        await store.record_execution_identity(identity, source="test")
        await store.record_task_claim(
            TaskClaim(
                claim_id=claim_id,
                task_id=identity.task_id,
                session_id=identity.session_id,
                agent_id=identity.agent_id,
                status="active" if acked else "claimed",
                claimed_at=now - timedelta(minutes=3),
                acked_at=now - timedelta(minutes=2) if acked else None,
                heartbeat_at=now - timedelta(minutes=1) if acked else None,
                stale_after=(
                    now - timedelta(seconds=1)
                    if expired
                    else now + timedelta(minutes=5)
                ),
            )
        )
        await store.record_delegation_run(
            DelegationRun(
                run_id=run_id,
                task_id=identity.task_id,
                session_id=identity.session_id,
                claim_id=claim_id,
                assigned_to=identity.agent_id,
                status="running" if acked else "claimed",
            )
        )

    await seed_run("current", acked=True, expired=False)
    await seed_run("expired", acked=True, expired=True)
    await seed_run("unacked", acked=False, expired=False)

    views = OperatorViews(store)

    async def _unexpected_refetch(run_id: str):
        raise AssertionError(f"active run was re-fetched: {run_id}")

    monkeypatch.setattr(store, "get_delegation_run", _unexpected_refetch)
    overview, active_runs = await views.operator_activity_snapshot(
        session_id="sess-activity", limit=10
    )

    assert overview.sessions == 1
    assert overview.claims == 3
    assert overview.runs == 3
    assert overview.active_sessions == 1
    assert overview.active_claims == 1
    assert overview.current_lease_claims == 1
    assert overview.active_runs == 1
    assert overview.acknowledged_claims == 2
    assert overview.observed_nonterminal_claims == 3
    assert overview.observed_nonterminal_runs == 3
    assert overview.expired_or_unproven_runs == 2
    assert overview.proves_executor_liveness is False
    assert [run.run_id for run in active_runs] == ["run-current"]
