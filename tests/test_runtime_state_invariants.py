from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dharma_swarm.opportunity_dispatcher import OPPORTUNITY_STAGES, OpportunityDispatcher
from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


def _identity(
    *,
    task_id: str = "task-spine-a",
    run_id: str = "run-spine-a",
    claim_id: str = "claim-spine-a",
    parent_run_id: str = "",
) -> ExecutionIdentity:
    return ExecutionIdentity.new(
        task_id=task_id,
        run_id=run_id,
        claim_id=claim_id,
        trace_id="trace-spine-a",
        correlation_id="corr-spine-a",
        idempotency_key="idem-spine-a",
        agent_id="agent-spine-a",
        session_id="session-spine-a",
        parent_run_id=parent_run_id,
    )


@pytest.mark.asyncio
async def test_sync_legacy_helpers_fail_closed_without_identity_unless_flagged(
    tmp_path: Path,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    claim = TaskClaim(
        claim_id="claim-legacy",
        task_id="task-legacy",
        agent_id="agent-legacy",
        status="claimed",
        session_id="session-legacy",
    )

    with pytest.raises(MissingExecutionIdentity):
        store.create_task_claim_sync(claim)

    legacy_claim = store.create_task_claim_sync(
        claim,
        legacy_no_identity_allowed=True,
    )
    assert legacy_claim.metadata["legacy_no_identity_allowed"] is True

    run = DelegationRun(
        run_id="run-legacy",
        task_id="task-legacy",
        assigned_to="agent-legacy",
        status="running",
        session_id="session-legacy",
        claim_id="claim-legacy",
    )

    with pytest.raises(MissingExecutionIdentity):
        store.create_delegation_run_sync(run)

    legacy_run = store.create_delegation_run_sync(
        run,
        legacy_no_identity_allowed=True,
    )
    ledger = await store.get_run_ledger(run.run_id)

    assert legacy_run.metadata["legacy_no_identity_allowed"] is True
    assert ledger["identity"] is None
    assert ledger["receipts"] == []


@pytest.mark.asyncio
async def test_sync_helpers_record_identity_trace_and_receipts(tmp_path: Path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity(parent_run_id="run-parent-spine-a")

    stored_claim = store.create_task_claim_sync(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            status="claimed",
            session_id=identity.session_id,
            metadata=identity.to_metadata(),
        )
    )
    stored_run = store.create_delegation_run_sync(
        DelegationRun(
            run_id=identity.run_id,
            task_id=identity.task_id,
            assigned_to=identity.agent_id,
            status="running",
            session_id=identity.session_id,
            claim_id=identity.claim_id,
            metadata=identity.to_metadata(),
        )
    )
    ledger = await store.get_run_ledger(identity.run_id)
    receipt_types = {receipt.receipt_type for receipt in ledger["receipts"]}

    with sqlite3.connect(tmp_path / "runtime.db") as db:
        claim_trace = db.execute(
            "SELECT trace_id FROM task_claims WHERE claim_id = ?",
            (identity.claim_id,),
        ).fetchone()[0]
        run_trace = db.execute(
            "SELECT trace_id FROM delegation_runs WHERE run_id = ?",
            (identity.run_id,),
        ).fetchone()[0]

    assert stored_claim.metadata["execution_identity"]["run_id"] == identity.run_id
    assert stored_run.metadata["execution_identity"]["trace_id"] == identity.trace_id
    assert claim_trace == identity.trace_id
    assert run_trace == identity.trace_id
    assert ledger["identity"].run_id == identity.run_id
    assert ledger["identity"].trace_id == identity.trace_id
    assert ledger["run"].run_id == identity.run_id
    assert receipt_types >= {"task_claim", "delegation_run", "child_spawned"}


@pytest.mark.asyncio
async def test_opportunity_dispatcher_creates_canonical_identity_per_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DHARMA_STATE_DIR", str(tmp_path))
    store = RuntimeStateStore(tmp_path / "runtime.db")
    observed_telic_tasks: list[dict[str, object]] = []

    class TelicProbe:
        def record_dispatch(self, task, agent_id: str, topology: str) -> str:
            observed_telic_tasks.append(dict(task.metadata))
            return f"proposal-{task.metadata['stage']}"

    dispatcher = OpportunityDispatcher(
        state_store=store,
        telic_seam=TelicProbe(),
        session_id="session-opp",
    )

    results = dispatcher.dispatch_opportunity_sync(
        {
            "id": "opp-spine-a",
            "title": "Spine A Opportunity",
            "type": "external_revenue",
            "trace_id": "trace-opp-spine-a",
            "correlation_id": "corr-opp-spine-a",
        }
    )

    assert len(results) == len(OPPORTUNITY_STAGES)
    assert all(result.success for result in results)

    for result in results:
        ledger = await store.get_run_ledger(result.run_id)
        receipt_types = {receipt.receipt_type for receipt in ledger["receipts"]}

        assert ledger["identity"] is not None
        assert ledger["identity"].run_id == result.run_id
        assert ledger["identity"].claim_id == result.claim_id
        assert ledger["identity"].task_id == result.task_id
        assert ledger["identity"].trace_id == "trace-opp-spine-a"
        assert ledger["identity"].proposal_id == result.proposal_id
        assert ledger["run"].metadata.get("legacy_no_identity_allowed") is None
        assert receipt_types >= {"task_claim", "delegation_run"}

    assert len(observed_telic_tasks) == len(OPPORTUNITY_STAGES)
    assert all("execution_identity" in metadata for metadata in observed_telic_tasks)
    assert all(metadata["trace_id"] == "trace-opp-spine-a" for metadata in observed_telic_tasks)

    with sqlite3.connect(tmp_path / "runtime.db") as db:
        legacy_claims = db.execute(
            "SELECT COUNT(*) FROM task_claims WHERE metadata_json LIKE '%legacy_no_identity_allowed%'"
        ).fetchone()[0]
        legacy_runs = db.execute(
            "SELECT COUNT(*) FROM delegation_runs WHERE metadata_json LIKE '%legacy_no_identity_allowed%'"
        ).fetchone()[0]

    assert legacy_claims == 0
    assert legacy_runs == 0
