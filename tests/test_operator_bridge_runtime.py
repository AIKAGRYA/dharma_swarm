"""Tests for operator bridge mirroring into runtime_state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.message_bus import MessageBus
from dharma_swarm.operator_bridge import OperatorBridge
from dharma_swarm.runtime_state import RuntimeStateStore


@pytest.fixture
async def bridge_runtime_env(tmp_path):
    bus = MessageBus(tmp_path / "bridge.db")
    runtime_state = RuntimeStateStore(tmp_path / "runtime.db")
    bridge = OperatorBridge(
        message_bus=bus,
        ledger_dir=tmp_path / "ledgers",
        session_id="sess_bridge_runtime",
        runtime_state=runtime_state,
    )
    await bridge.init_db()
    return bridge, runtime_state


@pytest.mark.asyncio
async def test_bridge_runtime_mirror_tracks_claim_ack_heartbeat_and_artifact(bridge_runtime_env):
    bridge, runtime_state = bridge_runtime_env
    record = await bridge.enqueue_task(
        task="Implement checkpoint semantics",
        sender="operator",
        output=["patch", "report"],
    )
    claimed = await bridge.claim_task(claimed_by="codex-runner", task_id=record.id)
    assert claimed is not None

    acknowledged = await bridge.acknowledge_task_claim(
        task_id=record.id,
        acknowledged_by="codex-runner",
        note="work order parsed",
    )
    artifact_path = "/tmp/checkpoint.md"
    partial = await bridge.record_partial_artifact(
        task_id=record.id,
        artifact_kind="checkpoint_report",
        path=artifact_path,
        summary="Checkpoint summary",
        promotion_state="shared",
    )
    heartbeated = await bridge.heartbeat_task(
        task_id=record.id,
        heartbeat_by="codex-runner",
        summary="halfway done",
        progress=0.5,
        current_artifact_id=partial.metadata["current_artifact_id"],
    )
    responded = await bridge.respond_task(
        task_id=record.id,
        status="done",
        summary="Completed the checkpoint protocol.",
        patch_path="/tmp/final.patch",
    )

    claim_id = acknowledged.metadata["runtime_claim_id"]
    run_id = acknowledged.metadata["runtime_run_id"]
    claim = await runtime_state.get_task_claim(claim_id)
    run = await runtime_state.get_delegation_run(run_id)
    artifacts = await runtime_state.list_artifacts(task_id=record.id, limit=10)
    actions = await runtime_state.list_operator_actions(task_id=record.id, limit=20)
    session = await runtime_state.get_session("sess_bridge_runtime")

    assert claim is not None
    assert claim.status == "completed"
    assert claim.acked_at is not None
    assert claim.metadata["summary"] == "halfway done"
    assert run is not None
    assert run.status == "completed"
    assert run.current_artifact_id == heartbeated.metadata["current_artifact_id"]
    assert {artifact.artifact_kind for artifact in artifacts} >= {"checkpoint_report", "patch"}
    assert any(action.action_name == "bridge_task_acknowledged" for action in actions)
    assert any(action.action_name == "bridge_task_heartbeat" for action in actions)
    assert session is not None
    assert session.current_task_id == ""
    assert responded.status == "done"


@pytest.mark.asyncio
async def test_bridge_runtime_mirror_marks_recovered_claims(bridge_runtime_env):
    bridge, runtime_state = bridge_runtime_env
    record = await bridge.enqueue_task(
        task="Recover stale bridge claim",
        sender="operator",
        claim_timeout_seconds=30,
    )
    claimed = await bridge.claim_task(
        claimed_by="codex-runner",
        task_id=record.id,
        now=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    assert claimed is not None

    recovered = await bridge.recover_stale_tasks(now=datetime.now(timezone.utc))
    claim_id = claimed.metadata["runtime_claim_id"]
    run_id = claimed.metadata["runtime_run_id"]
    claim = await runtime_state.get_task_claim(claim_id)
    run = await runtime_state.get_delegation_run(run_id)

    assert [task.id for task in recovered] == [record.id]
    assert claim is not None
    assert claim.status == "recovered"
    assert claim.recovered_at is not None
    assert run is not None
    assert run.status == "stale_recovered"


@pytest.mark.asyncio
async def test_operator_bridge_claim_persists_execution_identity_and_reconciles_orphan(
    bridge_runtime_env,
):
    from dharma_swarm.swarm import build_runtime_authority_reconciler

    bridge, runtime_state = bridge_runtime_env
    first_claimed_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    record = await bridge.enqueue_task(
        task="Recover an authority-bound bridge attempt",
        sender="operator",
        claim_timeout_seconds=30,
    )
    first = await bridge.claim_task(
        claimed_by="worker-one",
        task_id=record.id,
        now=first_claimed_at,
    )
    assert first is not None

    first_claim_id = first.metadata["runtime_claim_id"]
    first_run_id = first.metadata["runtime_run_id"]
    first_identity = await runtime_state.get_execution_identity(first_run_id)
    assert first_identity is not None
    assert (
        first_identity.task_id,
        first_identity.run_id,
        first_identity.claim_id,
        first_identity.agent_id,
        first_identity.session_id,
    ) == (
        record.id,
        first_run_id,
        first_claim_id,
        "worker-one",
        "sess_bridge_runtime",
    )

    first_report = await build_runtime_authority_reconciler(runtime_state).reconcile(
        now=datetime.now(timezone.utc)
    )
    assert first_report.errors == []
    assert first_report.requeued_runs == [first_run_id]
    assert first_report.recovered_claims == [first_claim_id]
    first_receipts = await runtime_state.list_runtime_receipts(
        run_id=first_run_id,
        limit=20,
    )
    assert {receipt.receipt_type for receipt in first_receipts} >= {
        "delegation_run",
        "task_claim",
    }
    assert all(receipt.trace_id == first_identity.trace_id for receipt in first_receipts)

    recovered = await bridge.recover_stale_tasks(now=datetime.now(timezone.utc))
    assert [task.id for task in recovered] == [record.id]
    second = await bridge.claim_task(
        claimed_by="worker-two",
        task_id=record.id,
        now=datetime.now(timezone.utc),
    )
    assert second is not None
    second_claim_id = second.metadata["runtime_claim_id"]
    second_run_id = second.metadata["runtime_run_id"]
    assert second_claim_id != first_claim_id
    assert second_run_id != first_run_id
    assert second.metadata["runtime_parent_run_id"] == first_run_id

    second_identity = await runtime_state.get_execution_identity(second_run_id)
    assert second_identity is not None
    assert second_identity.agent_id == "worker-two"
    assert second_identity.claim_id == second_claim_id
    assert second_identity.parent_run_id == first_run_id

    second_report = await build_runtime_authority_reconciler(runtime_state).reconcile(
        now=datetime.now(timezone.utc)
    )
    assert second_report.errors == []
    assert second_report.requeued_runs == [second_run_id]
    assert second_report.recovered_claims == [second_claim_id]
    second_receipts = await runtime_state.list_runtime_receipts(
        run_id=second_run_id,
        limit=20,
    )
    assert {receipt.receipt_type for receipt in second_receipts} >= {
        "delegation_run",
        "task_claim",
    }
    assert all(receipt.trace_id == second_identity.trace_id for receipt in second_receipts)
