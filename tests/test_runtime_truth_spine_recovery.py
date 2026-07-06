from __future__ import annotations

import asyncio
from pathlib import Path

from dharma_swarm.graph.checkpoint import GraphCheckpointStore
from dharma_swarm.opportunity_refill import OpportunityRefill, OpportunityRow
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity


def _identity(**overrides: str) -> ExecutionIdentity:
    payload = {
        "task_id": "task-recovery",
        "agent_id": "agent-recovery",
        "session_id": "session-recovery",
        "trace_id": "trace-recovery",
        "correlation_id": "corr-recovery",
        "run_id": "run-recovery",
        "claim_id": "claim-recovery",
        "idempotency_key": "idem-recovery",
    }
    payload.update(overrides)
    return ExecutionIdentity.new(**payload)


def test_opportunity_refill_records_runtime_stage_receipts(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    refill = OpportunityRefill(
        output_dir=tmp_path / "packets",
        runtime_state=runtime,
    )
    row = OpportunityRow(
        id="opp-runtime",
        title="Runtime opportunity",
        estimated_value_usd=10,
        metadata={"trace_id": "trace-opp", "correlation_id": "corr-opp"},
    )

    result = refill.refill(row)

    assert result.success is True
    stage = result.stages[0]
    ledger = asyncio.run(runtime.get_run_ledger(stage.run_id))
    assert ledger["identity"] is not None
    assert any(
        receipt.receipt_type == "opportunity_refill_stage"
        and receipt.status == "completed"
        for receipt in ledger["receipts"]
    )


def test_graph_checkpoint_records_checkpoint_receipt(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()
    store = GraphCheckpointStore(
        "workflow-runtime",
        persist_dir=tmp_path / "workflow",
        runtime_state=runtime,
        execution_identity=identity,
    )

    store.checkpoint(superstep=0, node_id="step-1", state_ref="state-0")

    ledger = asyncio.run(runtime.get_run_ledger(identity.run_id))
    assert ledger["identity"] is not None
    assert any(
        receipt.receipt_type == "workflow_checkpoint"
        and receipt.status == "checkpointed"
        for receipt in ledger["receipts"]
    )
