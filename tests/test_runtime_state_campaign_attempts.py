from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity


NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
MISSION = "campaign-attempts"
TASK = "task-attempts"
RUN = "run-attempts"
CLAIM = "claim-attempts"
AGENT = "agent-attempts"
IDEMPOTENCY = "idem-attempts"
GENERATION = 1


async def _runtime(tmp_path: Path) -> tuple[RuntimeStateStore, ExecutionIdentity]:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = ExecutionIdentity.new(
        trace_id="trace-attempts",
        correlation_id="correlation-attempts",
        causation_id="causation-attempts",
        parent_run_id="parent-attempts",
        task_id=TASK,
        run_id=RUN,
        claim_id=CLAIM,
        idempotency_key=IDEMPOTENCY,
        agent_id=AGENT,
        session_id="session-attempts",
        metadata={"mission_id": MISSION, "attempt_generation": GENERATION},
    )
    await runtime.record_execution_identity(identity, source="fixture")
    return runtime, identity


async def _open_attempt(
    runtime: RuntimeStateStore,
    identity: ExecutionIdentity,
) -> None:
    metadata = {
        "mission_id": MISSION,
        "attempt_generation": GENERATION,
    }
    await runtime.record_task_claim(
        TaskClaim(
            claim_id=CLAIM,
            task_id=TASK,
            agent_id=AGENT,
            session_id=identity.session_id,
            status="running",
            metadata=metadata,
            claimed_at=NOW,
        )
    )
    await runtime.record_delegation_run(
        DelegationRun(
            run_id=RUN,
            task_id=TASK,
            claim_id=CLAIM,
            assigned_by="orchestrator",
            assigned_to=AGENT,
            session_id=identity.session_id,
            parent_run_id=identity.parent_run_id,
            status="running",
            metadata=metadata,
            started_at=NOW,
        )
    )


async def _resolve(runtime: RuntimeStateStore) -> str:
    return await runtime.resolve_campaign_dispatch_indeterminate(
        mission_id=MISSION,
        task_id=TASK,
        run_id=RUN,
        claim_id=CLAIM,
        agent_id=AGENT,
        idempotency_key=IDEMPOTENCY,
        attempt_generation=GENERATION,
    )


async def _inspect(runtime: RuntimeStateStore) -> str:
    return await runtime.inspect_campaign_dispatch_indeterminate(
        mission_id=MISSION,
        task_id=TASK,
        run_id=RUN,
        claim_id=CLAIM,
        agent_id=AGENT,
        idempotency_key=IDEMPOTENCY,
        attempt_generation=GENERATION,
    )


@pytest.mark.asyncio
async def test_campaign_indeterminate_terminalization_is_restart_idempotent(
    tmp_path: Path,
) -> None:
    runtime, identity = await _runtime(tmp_path)
    await _open_attempt(runtime, identity)

    assert await _inspect(runtime) == "recoverable"
    open_run = await runtime.get_delegation_run(RUN)
    assert open_run is not None and open_run.status == "running"
    assert await _resolve(runtime) == "terminalized"
    assert await _inspect(runtime) == "already_terminal"
    assert await _resolve(runtime) == "already_terminal"

    reopened = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    assert await _resolve(reopened) == "already_terminal"
    run = await reopened.get_delegation_run(RUN)
    claim = await reopened.get_task_claim(CLAIM)
    receipts = await reopened.list_runtime_receipts(run_id=RUN, limit=20)
    assert run is not None and run.failure_code == "dispatch_indeterminate"
    assert claim is not None and claim.status == "failed"
    assert [r.receipt_type for r in receipts].count("mission_dispatch_indeterminate") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "failed"])
async def test_campaign_indeterminate_never_relabels_other_terminal_run(
    tmp_path: Path,
    status: str,
) -> None:
    runtime, identity = await _runtime(tmp_path)
    await _open_attempt(runtime, identity)
    run = await runtime.get_delegation_run(RUN)
    assert run is not None
    await runtime.record_delegation_run(
        replace(
            run,
            status=status,
            failure_code="semantic_rejection" if status == "failed" else "",
            completed_at=NOW,
        )
    )

    assert await _resolve(runtime) == "effect_observed"
    unchanged = await runtime.get_delegation_run(RUN)
    assert unchanged is not None and unchanged.status == status


@pytest.mark.asyncio
async def test_campaign_indeterminate_rejects_foreign_same_prefix_receipt(
    tmp_path: Path,
) -> None:
    runtime, identity = await _runtime(tmp_path)
    await _open_attempt(runtime, identity)
    await runtime.record_runtime_receipt(
        RuntimeReceipt(
            receipt_id="foreign-prefix",
            receipt_type="provider_result",
            status="completed",
            run_id=RUN,
            task_id=TASK,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            causation_id=identity.causation_id,
            parent_run_id=identity.parent_run_id,
            agent_id=AGENT,
            idempotency_key=IDEMPOTENCY,
            side_effect_key=f"delegation_run:{RUN}:completed",
            payload={
                "mission_id": MISSION,
                "attempt_generation": GENERATION,
                "receipt_status": "completed",
            },
            created_at=NOW,
        )
    )

    assert await _resolve(runtime) == "effect_observed"
    run = await runtime.get_delegation_run(RUN)
    assert run is not None and run.status == "running"


@pytest.mark.asyncio
async def test_campaign_indeterminate_rejects_provider_truth_on_running_receipt(
    tmp_path: Path,
) -> None:
    runtime, identity = await _runtime(tmp_path)
    await _open_attempt(runtime, identity)
    await runtime.record_runtime_receipt(
        RuntimeReceipt(
            receipt_id="forged-running",
            receipt_type="delegation_run",
            status="running",
            run_id=RUN,
            task_id=TASK,
            trace_id=identity.trace_id,
            correlation_id=identity.correlation_id,
            causation_id=identity.causation_id,
            parent_run_id=identity.parent_run_id,
            agent_id=AGENT,
            idempotency_key=IDEMPOTENCY,
            side_effect_key=f"delegation_run:{RUN}:running",
            payload={
                "mission_id": MISSION,
                "attempt_generation": GENERATION,
                "receipt_status": "running",
                "actual_served_model": "foreign-model",
            },
            created_at=NOW,
        )
    )

    assert await _resolve(runtime) == "effect_observed"


@pytest.mark.asyncio
async def test_campaign_indeterminate_absent_runtime_is_not_synthetic_success(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    assert await _resolve(runtime) == "absent"
    assert await runtime.list_runtime_receipts(run_id=RUN, limit=20) == []


@pytest.mark.asyncio
async def test_atomic_finalizer_rejects_foreign_receipt_carrier_and_rolls_back(
    tmp_path: Path,
) -> None:
    runtime, identity = await _runtime(tmp_path)
    await _open_attempt(runtime, identity)
    running = await runtime.get_delegation_run(RUN)
    assert running is not None
    foreign = RuntimeReceipt(
        receipt_id="foreign-finalizer-carrier",
        receipt_type="test_evidence",
        status="completed",
        run_id=RUN,
        task_id=TASK,
        trace_id="foreign-trace",
        correlation_id=identity.correlation_id,
        causation_id=identity.causation_id,
        parent_run_id=identity.parent_run_id,
        agent_id=identity.agent_id,
        idempotency_key=identity.idempotency_key,
        side_effect_key=f"test:{RUN}",
        payload={"fixture": True},
        created_at=NOW,
    )

    with pytest.raises(ValueError, match="receipt carrier is foreign"):
        await runtime.finalize_delegation_run_evidence_exact(
            expected_running=running,
            completed=replace(running, status="completed", completed_at=NOW),
            receipts=(foreign,),
        )

    assert await runtime.get_delegation_run(RUN) == running
    assert await runtime.get_runtime_receipt(foreign.receipt_id) is None
