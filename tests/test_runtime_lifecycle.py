from __future__ import annotations

import copy
import importlib.util
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.models import Task, TaskDispatch, TopologyType
from dharma_swarm.runtime_lifecycle import RuntimeLifecycle
from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore, TaskClaim
from dharma_swarm.session_ledger import SessionLedger
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


def _table_count(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as db:
        row = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0] if row else 0)


def _load_receipt_coverage_report():
    spec = importlib.util.spec_from_file_location(
        "runtime_receipt_coverage_report",
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "governance"
        / "runtime_receipt_coverage_report.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _campaign_owner_identity_metadata(identity: ExecutionIdentity) -> dict:
    authority = {
        "schema_version": "dharma.sadhana.campaign_task_authority.v5",
        "mission_id": "campaign-identity-closure",
        "dispatch_key": "dispatch-identity-closure",
        "attempt_generation": 1,
        "claimed_principal": identity.agent_id,
    }
    owner = {
        "schema_version": "dharma.mission_control.owner_execution.v2",
        "backend": "orchestrator",
        "mission_id": authority["mission_id"],
        "task_id": identity.task_id,
        "dispatch_key": authority["dispatch_key"],
        "attempt_generation": authority["attempt_generation"],
        "run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "idempotency_key": identity.idempotency_key,
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
    }
    aliases = {
        field: getattr(identity, field)
        for field in (
            "task_id",
            "agent_id",
            "session_id",
            "claim_id",
            "run_id",
            "trace_id",
            "correlation_id",
            "idempotency_key",
            "causation_id",
            "parent_run_id",
            "external_a2a_task_id",
            "message_id",
            "event_id",
            "artifact_id",
            "proposal_id",
        )
    }
    return {
        **identity.to_metadata(),
        **aliases,
        "runtime_run_id": identity.run_id,
        "attempt_generation": authority["attempt_generation"],
        "mission_campaign_authority": authority,
        "mission_control_owner_execution": owner,
    }


def test_runtime_lifecycle_rotates_identity_at_new_claim_boundary(tmp_path: Path) -> None:
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-retry-identity",
        runtime_db_path=tmp_path / "runtime.db",
    )
    lifecycle = RuntimeLifecycle(ledger)
    previous = {
        "trace_id": "trace-attempt-1",
        "correlation_id": "correlation-logical-task",
        "task_id": "task-retry",
        "run_id": "run-attempt-1",
        "claim_id": "claim-attempt-1",
        "idempotency_key": "idem-attempt-1",
        "agent_id": "agent-1",
        "session_id": "sess-retry-identity",
    }
    task = Task(
        id="task-retry",
        title="Retry with fresh custody",
        metadata={
            "execution_identity": previous,
            "runtime_run_id": previous["run_id"],
            "run_id": previous["run_id"],
            "claim_id": previous["claim_id"],
            "trace_id": previous["trace_id"],
            "correlation_id": previous["correlation_id"],
            "idempotency_key": previous["idempotency_key"],
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-1",
        metadata={"claim_id": "claim-attempt-2"},
    )

    identity = lifecycle.ensure_execution_identity(dispatch, task=task)
    replayed = lifecycle.ensure_execution_identity(dispatch, task=task)

    assert identity == replayed
    assert identity.claim_id == "claim-attempt-2"
    assert identity.run_id != previous["run_id"]
    assert identity.trace_id != previous["trace_id"]
    assert identity.idempotency_key != previous["idempotency_key"]
    assert identity.correlation_id == previous["correlation_id"]
    assert identity.parent_run_id == previous["run_id"]
    assert task.metadata["execution_identity"] == identity.to_dict()


def test_campaign_retry_lineage_requires_exact_prior_owner_authority(
    tmp_path: Path,
) -> None:
    lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="session-campaign-retry",
            runtime_db_path=tmp_path / "runtime.db",
        )
    )
    previous = ExecutionIdentity.new(
        task_id="task-campaign-retry",
        agent_id="agent-campaign-retry",
        session_id="session-prior-campaign-attempt",
        trace_id="trace-prior-campaign-attempt",
        correlation_id="correlation-campaign-task",
        causation_id="cause-prior-campaign-attempt",
        parent_run_id="run-grandparent-campaign-attempt",
        run_id="run-prior-campaign-attempt",
        claim_id="claim-prior-campaign-attempt",
        idempotency_key="idem-prior-campaign-attempt",
    )
    task = Task(
        id=previous.task_id,
        title="Rotate an authority-closed campaign attempt",
        metadata=_campaign_owner_identity_metadata(previous),
    )
    dispatch = TaskDispatch(
        task_id=previous.task_id,
        agent_id=previous.agent_id,
        metadata={"claim_id": "claim-next-campaign-attempt"},
    )

    rotated = lifecycle.ensure_execution_identity(dispatch, task=task, require=True)

    assert rotated.parent_run_id == previous.run_id
    assert rotated.correlation_id == previous.correlation_id


@pytest.mark.parametrize(
    "mutation",
    [
        "foreign_owner_run",
        "extra_owner_field",
        "foreign_owner_schema",
        "foreign_owner_backend",
        "foreign_authority_schema",
        "foreign_authority_principal",
        "foreign_authority_dispatch",
        "foreign_authority_generation",
        "boolean_owner_generation",
        "boolean_flat_generation",
    ],
)
def test_campaign_retry_rejects_self_consistent_but_foreign_prior_owner(
    tmp_path: Path,
    mutation: str,
) -> None:
    lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="session-campaign-foreign",
            runtime_db_path=tmp_path / "runtime.db",
        )
    )
    previous = ExecutionIdentity.new(
        task_id="task-campaign-foreign",
        agent_id="agent-campaign-foreign",
        session_id="session-prior-campaign-attempt",
        trace_id="trace-prior-campaign-attempt",
        correlation_id="correlation-prior-campaign-attempt",
        causation_id="cause-prior-campaign-attempt",
        parent_run_id="run-grandparent-campaign-attempt",
        run_id="run-prior-campaign-attempt",
        claim_id="claim-prior-campaign-attempt",
        idempotency_key="idem-prior-campaign-attempt",
    )
    metadata = _campaign_owner_identity_metadata(previous)
    authority = metadata["mission_campaign_authority"]
    owner = metadata["mission_control_owner_execution"]
    if mutation == "foreign_owner_run":
        owner["run_id"] = "run-foreign-owner"
    elif mutation == "extra_owner_field":
        owner["untyped_extra"] = "foreign"
    elif mutation == "foreign_owner_schema":
        owner["schema_version"] = "dharma.mission_control.owner_execution.v1"
    elif mutation == "foreign_owner_backend":
        owner["backend"] = "foreign"
    elif mutation == "foreign_authority_schema":
        authority["schema_version"] = "dharma.sadhana.campaign_task_authority.v4"
    elif mutation == "foreign_authority_principal":
        authority["claimed_principal"] = "agent-foreign-owner"
    elif mutation == "foreign_authority_dispatch":
        authority["dispatch_key"] = "dispatch-foreign-owner"
    elif mutation == "foreign_authority_generation":
        authority["attempt_generation"] = 2
    elif mutation == "boolean_owner_generation":
        owner["attempt_generation"] = True
    else:
        metadata["attempt_generation"] = True

    with pytest.raises(MissingExecutionIdentity, match="owner attempt authority"):
        lifecycle.ensure_execution_identity(
            TaskDispatch(
                task_id=previous.task_id,
                agent_id=previous.agent_id,
                metadata={"claim_id": "claim-next-campaign-attempt"},
            ),
            task=Task(
                id=previous.task_id,
                title="Reject foreign campaign attempt lineage",
                metadata=metadata,
            ),
            require=True,
        )


@pytest.mark.parametrize(
    "owner_field",
    ["mission_id", "dispatch_key", "attempt_generation"],
)
def test_campaign_same_claim_rejects_foreign_owner_authority_closure(
    tmp_path: Path,
    owner_field: str,
) -> None:
    lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="session-same-claim-foreign",
            runtime_db_path=tmp_path / "runtime.db",
        )
    )
    identity = ExecutionIdentity.new(
        task_id="task-same-claim-foreign",
        agent_id="agent-same-claim-foreign",
        session_id="session-same-claim-foreign",
        trace_id="trace-same-claim-foreign",
        correlation_id="correlation-same-claim-foreign",
        run_id="run-same-claim-foreign",
        claim_id="claim-same-claim-foreign",
        idempotency_key="idem-same-claim-foreign",
    )
    metadata = _campaign_owner_identity_metadata(identity)
    owner = metadata["mission_control_owner_execution"]
    owner[owner_field] = (
        2 if owner_field == "attempt_generation" else f"foreign-{owner_field}"
    )

    with pytest.raises(MissingExecutionIdentity, match="owner attempt authority"):
        lifecycle.ensure_execution_identity(
            TaskDispatch(
                task_id=identity.task_id,
                agent_id=identity.agent_id,
                metadata={"claim_id": identity.claim_id},
            ),
            task=Task(
                id=identity.task_id,
                title="Reject foreign same-claim authority",
                metadata=metadata,
            ),
            require=True,
        )


@pytest.mark.parametrize(
    "alias",
    [
        "task_id",
        "agent_id",
        "session_id",
        "claim_id",
        "run_id",
        "runtime_run_id",
        "trace_id",
        "correlation_id",
        "idempotency_key",
        "causation_id",
        "parent_run_id",
        "external_a2a_task_id",
        "message_id",
        "event_id",
        "artifact_id",
        "proposal_id",
    ],
)
def test_stale_retry_rejects_any_contradictory_canonical_flat_alias(
    tmp_path: Path,
    alias: str,
) -> None:
    lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="session-alias-closure",
            runtime_db_path=tmp_path / "runtime.db",
        )
    )
    previous = ExecutionIdentity.new(
        task_id="task-alias-closure",
        agent_id="agent-alias-closure",
        session_id="session-prior-alias-attempt",
        trace_id="trace-prior-alias-attempt",
        correlation_id="correlation-prior-alias-attempt",
        causation_id="cause-prior-alias-attempt",
        parent_run_id="run-parent-alias-attempt",
        run_id="run-prior-alias-attempt",
        claim_id="claim-prior-alias-attempt",
        idempotency_key="idem-prior-alias-attempt",
        external_a2a_task_id="a2a-prior-alias-attempt",
        message_id="message-prior-alias-attempt",
        event_id="event-prior-alias-attempt",
        artifact_id="artifact-prior-alias-attempt",
        proposal_id="proposal-prior-alias-attempt",
    )
    metadata = _campaign_owner_identity_metadata(previous)
    metadata[alias] = f"foreign-{alias}"

    with pytest.raises(MissingExecutionIdentity, match="claim carrier"):
        lifecycle.ensure_execution_identity(
            TaskDispatch(
                task_id=previous.task_id,
                agent_id=previous.agent_id,
                metadata={"claim_id": "claim-next-alias-attempt"},
            ),
            task=Task(
                id=previous.task_id,
                title="Reject contradictory stale alias",
                metadata=metadata,
            ),
            require=True,
        )


@pytest.mark.asyncio
async def test_runtime_lifecycle_reuses_persisted_identity_after_claim_only_restart(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "runtime.db"
    lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="sess-retry-restart",
            runtime_db_path=runtime_db_path,
        )
    )
    previous = {
        "trace_id": "trace-attempt-1",
        "correlation_id": "correlation-logical-task",
        "task_id": "task-retry",
        "run_id": "run-attempt-1",
        "claim_id": "claim-attempt-1",
        "idempotency_key": "idem-attempt-1",
        "agent_id": "agent-1",
        "session_id": "sess-retry-restart",
    }
    stale_metadata = {
        "execution_identity": previous,
        "runtime_run_id": previous["run_id"],
        "run_id": previous["run_id"],
        "claim_id": previous["claim_id"],
        "trace_id": previous["trace_id"],
        "correlation_id": previous["correlation_id"],
        "idempotency_key": previous["idempotency_key"],
    }
    dispatch = TaskDispatch(
        task_id="task-retry",
        agent_id="agent-1",
        metadata={"claim_id": "claim-attempt-2"},
    )
    first = lifecycle.ensure_execution_identity(
        dispatch,
        task=Task(
            id=dispatch.task_id,
            title="Retry before restart",
            metadata=copy.deepcopy(stale_metadata),
        ),
    )
    await lifecycle.record_task_claim(
        dispatch,
        task=Task(
            id=dispatch.task_id,
            title="Retry before restart",
            metadata=copy.deepcopy(stale_metadata),
        ),
        status="claimed",
        require_identity=True,
    )

    restarted_dispatch = TaskDispatch(
        task_id=dispatch.task_id,
        agent_id=dispatch.agent_id,
        metadata={"claim_id": "claim-attempt-2"},
    )
    restarted_lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="sess-after-process-restart",
            runtime_db_path=runtime_db_path,
        )
    )
    replayed = restarted_lifecycle.ensure_execution_identity(
        restarted_dispatch,
        task=Task(
            id=dispatch.task_id,
            title="Retry after restart",
            metadata=copy.deepcopy(stale_metadata),
        ),
    )
    restarted_task = Task(
        id=dispatch.task_id,
        title="Retry after restart",
        metadata=copy.deepcopy(stale_metadata),
    )
    await restarted_lifecycle.record_task_claim(
        restarted_dispatch,
        task=restarted_task,
        status="running",
        require_identity=True,
    )
    await restarted_lifecycle.record_delegation_run(
        restarted_dispatch,
        task=restarted_task,
        status="running",
        require_identity=True,
    )

    assert replayed == first
    assert replayed.session_id == "sess-retry-restart"
    assert replayed.claim_id == "claim-attempt-2"
    assert replayed.run_id != previous["run_id"]
    assert replayed.idempotency_key != previous["idempotency_key"]
    store = RuntimeStateStore(runtime_db_path)
    durable_claim = await store.get_task_claim(replayed.claim_id)
    durable_run = await store.get_delegation_run(replayed.run_id)
    assert durable_claim is not None
    assert durable_claim.session_id == replayed.session_id
    assert durable_run is not None
    assert durable_run.session_id == replayed.session_id


def test_persisted_claim_identity_read_does_not_contend_for_writer_lock(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "runtime.db"
    lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="sess-read-only-claim-carrier",
            runtime_db_path=runtime_db_path,
        )
    )
    identity = ExecutionIdentity.new(
        trace_id="trace-read-only-carrier",
        correlation_id="correlation-read-only-carrier",
        task_id="task-read-only-carrier",
        run_id="run-read-only-carrier",
        claim_id="claim-read-only-carrier",
        idempotency_key="idem-read-only-carrier",
        agent_id="agent-read-only-carrier",
        session_id="sess-read-only-claim-carrier",
    )
    store = lifecycle._runtime_state_store()
    assert isinstance(store, RuntimeStateStore)
    dispatch = TaskDispatch(
        task_id=identity.task_id,
        agent_id=identity.agent_id,
        metadata={"claim_id": identity.claim_id},
    )

    with sqlite3.connect(runtime_db_path) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        store.create_task_claim_sync(
            TaskClaim(
                claim_id=identity.claim_id,
                task_id=identity.task_id,
                agent_id=identity.agent_id,
                session_id=identity.session_id,
                status="running",
                metadata=identity.to_metadata(),
            )
        )
        # Keep this connection open so the newest custody carrier remains live
        # in WAL; an `immutable=1` snapshot would miss it.
        assert Path(f"{runtime_db_path}-wal").stat().st_size > 32
        writer.execute("BEGIN IMMEDIATE")
        cursor = writer.execute(
            "UPDATE task_claims SET retry_count = retry_count WHERE claim_id = ?",
            (identity.claim_id,),
        )
        assert cursor.rowcount == 1
        recovered = lifecycle.ensure_execution_identity(
            dispatch,
            task=Task(id=identity.task_id, title="Read committed claim carrier"),
            require=True,
        )

    assert recovered == identity


def test_runtime_lifecycle_reuses_task_carrier_when_caller_persists_before_claim(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "runtime.db"
    stale_metadata = {
        "execution_identity": {
            "trace_id": "trace-attempt-1",
            "correlation_id": "correlation-logical-task",
            "task_id": "task-retry",
            "run_id": "run-attempt-1",
            "claim_id": "claim-attempt-1",
            "idempotency_key": "idem-attempt-1",
            "agent_id": "agent-1",
            "session_id": "session-before",
        },
        "claim_id": "claim-attempt-1",
    }
    lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="session-before",
            runtime_db_path=runtime_db_path,
        )
    )
    dispatch = TaskDispatch(
        task_id="task-retry",
        agent_id="agent-1",
        metadata={"claim_id": "claim-attempt-2"},
    )
    board_task = Task(
        id=dispatch.task_id,
        title="Retry carrier before runtime claim",
        metadata=copy.deepcopy(stale_metadata),
    )
    first = lifecycle.ensure_execution_identity(dispatch, task=board_task)
    # RuntimeLifecycle materializes the complete carrier on the Task object.
    # Persistence belongs to the caller; the sibling orchestrator packet must
    # commit this exact snapshot in its Board assignment before any effect.
    persisted_board_metadata = copy.deepcopy(board_task.metadata)

    restarted = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="session-after",
            runtime_db_path=runtime_db_path,
        )
    )
    replayed = restarted.ensure_execution_identity(
        TaskDispatch(
            task_id=dispatch.task_id,
            agent_id=dispatch.agent_id,
            metadata={"claim_id": "claim-attempt-2"},
        ),
        task=Task(
            id=board_task.id,
            title=board_task.title,
            metadata=persisted_board_metadata,
        ),
    )

    assert replayed == first
    assert replayed.session_id == "session-before"


def test_required_identity_rejects_missing_incoming_claim(tmp_path: Path) -> None:
    lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="session-after",
            runtime_db_path=tmp_path / "runtime.db",
        )
    )
    old_identity = ExecutionIdentity.new(
        task_id="task-claimless",
        agent_id="agent-1",
        session_id="session-before",
        trace_id="trace-before",
        correlation_id="correlation-before",
        run_id="run-before",
        claim_id="claim-before",
        idempotency_key="idempotency-before",
    )

    with pytest.raises(MissingExecutionIdentity, match="incoming custody claim"):
        lifecycle.ensure_execution_identity(
            TaskDispatch(task_id=old_identity.task_id, agent_id=old_identity.agent_id),
            task=Task(
                id=old_identity.task_id,
                title="Claimless required recovery",
                metadata=old_identity.to_metadata(),
            ),
            require=True,
        )


@pytest.mark.asyncio
async def test_retry_run_row_preserves_identity_parent_lineage(tmp_path: Path) -> None:
    lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="session-retry",
            runtime_db_path=tmp_path / "runtime.db",
        )
    )
    previous = ExecutionIdentity.new(
        task_id="task-lineage",
        agent_id="agent-1",
        session_id="session-before",
        trace_id="trace-before",
        correlation_id="correlation-logical-task",
        run_id="run-before",
        claim_id="claim-before",
        idempotency_key="idempotency-before",
    )
    task = Task(
        id=previous.task_id,
        title="Retry lineage",
        metadata=previous.to_metadata(),
    )
    dispatch = TaskDispatch(
        task_id=previous.task_id,
        agent_id=previous.agent_id,
        metadata={"claim_id": "claim-after"},
    )
    identity = lifecycle.ensure_execution_identity(dispatch, task=task)

    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="running",
        require_identity=True,
    )

    stored = await RuntimeStateStore(tmp_path / "runtime.db").get_delegation_run(
        identity.run_id
    )
    assert identity.parent_run_id == previous.run_id
    assert stored is not None
    assert stored.parent_run_id == identity.parent_run_id


def test_exact_sync_run_replay_heals_missing_receipt(tmp_path: Path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = ExecutionIdentity.new(
        task_id="task-heal",
        agent_id="agent-heal",
        session_id="session-heal",
        trace_id="trace-heal",
        correlation_id="correlation-heal",
        run_id="run-heal",
        claim_id="claim-heal",
        idempotency_key="idempotency-heal",
    )
    run = DelegationRun(
        run_id=identity.run_id,
        task_id=identity.task_id,
        assigned_to=identity.agent_id,
        status="running",
        session_id=identity.session_id,
        claim_id=identity.claim_id,
        started_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        metadata=identity.to_metadata(),
    )
    store.create_delegation_run_sync(run)
    receipt_id = f"rr_{identity.run_id}_{run.status}_run"
    with sqlite3.connect(store.db_path) as db:
        db.execute("DELETE FROM runtime_receipts WHERE receipt_id = ?", (receipt_id,))
        db.commit()
        assert (
            db.execute(
                "SELECT COUNT(*) FROM runtime_receipts WHERE receipt_id = ?",
                (receipt_id,),
            ).fetchone()[0]
            == 0
        )

    replayed = store.create_delegation_run_sync(run)

    assert replayed.run_id == run.run_id
    with sqlite3.connect(store.db_path) as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM runtime_receipts WHERE receipt_id = ?",
                (receipt_id,),
            ).fetchone()[0]
            == 1
        )


def test_exact_sync_run_replay_heals_identity_without_rewriting_receipts(
    tmp_path: Path,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = ExecutionIdentity.new(
        task_id="task-heal-identity",
        agent_id="agent-heal",
        session_id="session-heal",
        trace_id="trace-heal",
        correlation_id="correlation-heal",
        parent_run_id="run-parent",
        run_id="run-heal-identity",
        claim_id="claim-heal-identity",
        idempotency_key="idempotency-heal-identity",
    )
    run = DelegationRun(
        run_id=identity.run_id,
        task_id=identity.task_id,
        assigned_to=identity.agent_id,
        status="running",
        session_id=identity.session_id,
        claim_id=identity.claim_id,
        parent_run_id=identity.parent_run_id,
        started_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        metadata=identity.to_metadata(),
    )
    store.create_delegation_run_sync(run)
    with sqlite3.connect(store.db_path) as db:
        before = db.execute(
            "SELECT * FROM runtime_receipts WHERE run_id = ? ORDER BY receipt_id",
            (identity.run_id,),
        ).fetchall()
        assert len(before) == 2
        db.execute(
            "DELETE FROM execution_identities WHERE run_id = ?",
            (identity.run_id,),
        )
        db.commit()

    store.create_delegation_run_sync(run)

    with sqlite3.connect(store.db_path) as db:
        after = db.execute(
            "SELECT * FROM runtime_receipts WHERE run_id = ? ORDER BY receipt_id",
            (identity.run_id,),
        ).fetchall()
        identity_count = db.execute(
            "SELECT COUNT(*) FROM execution_identities WHERE run_id = ?",
            (identity.run_id,),
        ).fetchone()[0]
    assert after == before
    assert identity_count == 1


@pytest.mark.parametrize(
    ("field", "delete"),
    [
        ("task_id", False),
        ("agent_id", False),
        ("claim_id", False),
        ("task_id", True),
        ("agent_id", True),
        ("session_id", True),
    ],
)
def test_runtime_lifecycle_rejects_foreign_dispatch_retry_identity(
    tmp_path: Path,
    field: str,
    delete: bool,
) -> None:
    lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="sess-retry-foreign",
            runtime_db_path=tmp_path / "runtime.db",
        )
    )
    previous = {
        "trace_id": "trace-attempt-1",
        "correlation_id": "correlation-logical-task",
        "task_id": "task-retry",
        "run_id": "run-attempt-1",
        "claim_id": "claim-attempt-1",
        "idempotency_key": "idem-attempt-1",
        "agent_id": "agent-1",
        "session_id": "sess-retry-foreign",
    }
    stale_metadata = {
        "execution_identity": previous,
        "run_id": previous["run_id"],
        "claim_id": previous["claim_id"],
        "correlation_id": previous["correlation_id"],
    }
    dispatch = TaskDispatch(
        task_id="task-retry",
        agent_id="agent-1",
        metadata={"claim_id": "claim-attempt-2"},
    )
    accepted = lifecycle.ensure_execution_identity(
        dispatch,
        task=Task(
            id=dispatch.task_id,
            title="Retry",
            metadata=copy.deepcopy(stale_metadata),
        ),
    )
    foreign_metadata = copy.deepcopy(dispatch.metadata)
    if delete:
        foreign_metadata["execution_identity"].pop(field)
    else:
        foreign_metadata["execution_identity"][field] = f"foreign-{field}"
    foreign_dispatch = TaskDispatch(
        task_id=dispatch.task_id,
        agent_id=dispatch.agent_id,
        metadata=foreign_metadata,
    )

    with pytest.raises(MissingExecutionIdentity, match="exactly bind"):
        lifecycle.ensure_execution_identity(
            foreign_dispatch,
            task=Task(
                id=dispatch.task_id,
                title="Retry reloaded",
                metadata=copy.deepcopy(stale_metadata),
            ),
        )

    assert foreign_dispatch.metadata["run_id"] == accepted.run_id


def test_required_identity_rejects_incomplete_stale_task_carrier(
    tmp_path: Path,
) -> None:
    lifecycle = RuntimeLifecycle(
        SessionLedger(
            base_dir=tmp_path / "ledgers",
            session_id="sess-incomplete-task-carrier",
            runtime_db_path=tmp_path / "runtime.db",
        )
    )
    task = Task(
        id="task-incomplete-carrier",
        title="Reject stale partial custody",
        metadata={
            "execution_identity": {
                "trace_id": "trace-old",
                "correlation_id": "correlation-old",
                "task_id": "task-incomplete-carrier",
                "run_id": "run-old",
                "idempotency_key": "idempotency-old",
                "agent_id": "agent-incomplete-carrier",
                "session_id": "sess-incomplete-task-carrier",
            },
            "run_id": "run-old",
            "idempotency_key": "idempotency-old",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-incomplete-carrier",
        metadata={
            "claim_id": "claim-new",
            "trace_id": "trace-new",
            "correlation_id": "correlation-new",
            "run_id": "run-new",
            "idempotency_key": "idempotency-new",
        },
    )

    with pytest.raises(MissingExecutionIdentity, match="TaskBoard claim carrier"):
        lifecycle.ensure_execution_identity(dispatch, task=task, require=True)


@pytest.mark.asyncio
async def test_runtime_lifecycle_preserves_structured_row_idempotence(tmp_path: Path) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-123",
        title="Write runtime extraction report",
        metadata={
            "active_claim": {
                "claimed_at": "2026-04-27T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": ["task_result"],
            "parent_run_id": "parent-run-1",
            "current_artifact_id": "artifact-upstream",
            "mission_id": "mission-runtime-lifecycle",
            "actual_provider": "openrouter",
            "actual_model": "qwen3-coder-live",
            "provider_model_truth_source": "runtime_provider.actual_served",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-1",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=180.0,
        metadata={
            "claim_id": "claim-1",
            "retry_count": 2,
            "max_retries": 4,
            "claim_timeout_seconds": 300,
        },
    )

    await lifecycle.record_task_claim(dispatch, task=task, status="claimed")
    await lifecycle.record_task_claim(dispatch, task=task, status="completed")

    run_id = lifecycle.ensure_runtime_run_id(dispatch)
    await lifecycle.record_delegation_run(dispatch, task=task, status="running")
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="completed",
        result="done",
    )

    payload_path = tmp_path / "artifact.md"
    payload_path.write_text("# Artifact\n", encoding="utf-8")
    await lifecycle.record_artifact(
        task=task,
        artifact_id="artifact-1",
        artifact_kind="task_result",
        payload_path=payload_path,
        manifest_path=tmp_path / "artifact.json",
        checksum="abc123",
        run_id=run_id,
        metadata={"source_test": "runtime_lifecycle"},
    )
    await lifecycle.record_artifact(
        task=task,
        artifact_id="artifact-1",
        artifact_kind="task_result",
        payload_path=payload_path,
        manifest_path=tmp_path / "artifact.json",
        checksum="abc123",
        run_id=run_id,
        metadata={"source_test": "runtime_lifecycle"},
    )

    assert _table_count(runtime_db_path, "task_claims") == 1
    assert _table_count(runtime_db_path, "delegation_runs") == 1
    assert _table_count(runtime_db_path, "artifact_records") == 1

    with sqlite3.connect(runtime_db_path) as db:
        claim_status = db.execute(
            "SELECT status FROM task_claims WHERE claim_id = ?",
            ("claim-1",),
        ).fetchone()[0]
        run_status, stored_run_id = db.execute(
            "SELECT status, run_id FROM delegation_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        artifact_run_id = db.execute(
            "SELECT run_id FROM artifact_records WHERE artifact_id = ?",
            ("artifact-1",),
        ).fetchone()[0]

    assert claim_status == "completed"
    assert run_status == "completed"
    assert stored_run_id == run_id
    assert artifact_run_id == run_id

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id=run_id,
        limit=20,
    )
    receipt_types = {receipt.receipt_type for receipt in receipts}
    assert {
        "delegation_run",
        "child_spawned",
        "child_completed",
        "artifact",
        "artifact_written",
    } <= receipt_types

    completed_claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "completed"
    )
    completed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "completed"
    )
    artifact_written = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "artifact_written" and receipt.status == "completed"
    )
    assert completed_claim.side_effect_key == "task_claim:claim-1:completed"
    assert completed_claim.payload["mission_id"] == "mission-runtime-lifecycle"
    assert completed_claim.payload["actual_served_provider"] == "openrouter"
    assert completed_claim.payload["actual_served_model"] == "qwen3-coder-live"
    assert "selected_provider" not in completed_claim.payload
    assert "selected_model" not in completed_claim.payload
    assert completed_claim.payload["provider_model_truth_source"] == "runtime_provider.actual_served"
    assert completed_run.side_effect_key == f"delegation_run:{run_id}:completed"
    assert completed_run.payload["mission_id"] == "mission-runtime-lifecycle"
    assert completed_run.payload["artifact_refs"] == ["artifact_records:artifact-upstream"]
    assert completed_run.payload["actual_served_provider"] == "openrouter"
    assert completed_run.payload["actual_served_model"] == "qwen3-coder-live"
    assert "selected_provider" not in completed_run.payload
    assert "selected_model" not in completed_run.payload
    assert completed_run.payload["provider_model_truth_source"] == "runtime_provider.actual_served"
    assert artifact_written.payload["mission_id"] == "mission-runtime-lifecycle"
    assert artifact_written.payload["artifact_refs"] == ["artifact_records:artifact-1"]
    assert artifact_written.payload["actual_served_provider"] == "openrouter"
    assert artifact_written.payload["actual_served_model"] == "qwen3-coder-live"
    assert "selected_provider" not in artifact_written.payload
    assert "selected_model" not in artifact_written.payload
    assert artifact_written.payload["provider_model_truth_source"] == "runtime_provider.actual_served"

    runtime_store = RuntimeStateStore(runtime_db_path)
    claim_idem = runtime_store.get_idempotency_record_sync(
        "idem_" + run_id,
        completed_claim.side_effect_key,
    )
    run_idem = runtime_store.get_idempotency_record_sync(
        "idem_" + run_id,
        completed_run.side_effect_key,
    )
    assert claim_idem is not None
    assert claim_idem.status == "completed"
    assert claim_idem.result_receipt_id == completed_claim.receipt_id
    assert run_idem is not None
    assert run_idem.status == "completed"
    assert run_idem.result_receipt_id == completed_run.receipt_id

    coverage_report = _load_receipt_coverage_report().build_report(runtime_db_path)
    assert coverage_report["summary"]["score_gate_70_to_75"] is True


@pytest.mark.asyncio
async def test_runtime_lifecycle_receipts_use_session_mission_when_task_lacks_mission_id(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-mission-fallback",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-without-mission",
        title="No explicit mission id",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-18T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "actual_served_provider": "ollama",
            "actual_served_model": "kimi-k2.5",
            "provider_model_truth_source": "runtime_provider.actual_served",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-mission-fallback",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=180.0,
        metadata={
            "claim_id": "claim-mission-fallback",
            "run_id": "run-mission-fallback",
            "runtime_run_id": "run-mission-fallback",
            "trace_id": "trace-mission-fallback",
            "correlation_id": "corr-mission-fallback",
            "idempotency_key": "idem-mission-fallback",
        },
    )

    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="claimed",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="completed",
        result="done",
        require_identity=True,
    )
    artifact_path = tmp_path / "artifact.md"
    artifact_path.write_text("done\n", encoding="utf-8")
    await lifecycle.record_artifact(
        task=task,
        artifact_id="artifact-mission-fallback",
        artifact_kind="task_result",
        payload_path=artifact_path,
        checksum="sha256:fallback",
        run_id="run-mission-fallback",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-mission-fallback",
        limit=20,
    )
    claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "claimed"
    )
    run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "completed"
    )
    artifact_written = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "artifact_written" and receipt.status == "completed"
    )

    assert claim.payload["mission_id"] == "sess-runtime-lifecycle-mission-fallback"
    assert claim.payload["mission"] == "sess-runtime-lifecycle-mission-fallback"
    assert claim.payload["mission_id_source"] == "runtime_lifecycle_fallback"
    assert run.payload["mission_id"] == "sess-runtime-lifecycle-mission-fallback"
    assert run.payload["mission"] == "sess-runtime-lifecycle-mission-fallback"
    assert run.payload["mission_id_source"] == "runtime_lifecycle_fallback"
    assert run.payload["no_artifact_refs_reason"] == (
        "delegation_run has no current_artifact_id"
    )
    assert artifact_written.payload["mission_id"] == (
        "sess-runtime-lifecycle-mission-fallback"
    )
    assert artifact_written.payload["mission_id_source"] == "runtime_lifecycle_fallback"
    assert artifact_written.payload["artifact_refs"] == [
        "artifact_records:artifact-mission-fallback"
    ]
    with sqlite3.connect(runtime_db_path) as db:
        metadata_json = db.execute(
            "SELECT metadata_json FROM delegation_runs WHERE run_id = ?",
            ("run-mission-fallback",),
        ).fetchone()[0]
    assert json.loads(metadata_json)["mission"] == (
        "sess-runtime-lifecycle-mission-fallback"
    )
    assert json.loads(metadata_json)["mission_id"] == (
        "sess-runtime-lifecycle-mission-fallback"
    )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-mission-fallback",
    )
    assert coverage_report["summary"]["score_gate_70_to_75"] is True

    from dharma_swarm.operator_core.runtime_truth import (
        runtime_truth_packets_from_runtime_db,
    )

    packets = runtime_truth_packets_from_runtime_db(
        runtime_db_path,
        observed_at="2026-06-29T16:20:00Z",
    )
    latest = next(
        packet for packet in packets if packet.surface_id == "runtime_state.latest_receipt"
    )
    assert latest.mission_id == "sess-runtime-lifecycle-mission-fallback"
    assert "mission_id" not in latest.missing_machine_fields


@pytest.mark.asyncio
async def test_runtime_lifecycle_accounts_claim_timeout_as_no_provider_execution(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-claim-timeout",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-claim-timeout",
        title="Claim timeout before worker starts",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-14T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-claim-timeout",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-claim-timeout",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=60.0,
        metadata={
            "claim_id": "claim-timeout",
            "run_id": "run-claim-timeout",
            "runtime_run_id": "run-claim-timeout",
            "trace_id": "trace-claim-timeout",
            "correlation_id": "corr-claim-timeout",
            "idempotency_key": "idem-claim-timeout",
            "claim_timeout_seconds": 90,
        },
    )

    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="failed",
        failure_code="claim_timeout",
        error="Claim expired before worker started",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="failed",
        failure_code="claim_timeout",
        error="Claim expired before worker started",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-claim-timeout",
        limit=20,
    )
    failed_claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "failed"
    )
    failed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "failed"
    )

    assert failed_claim.payload["provider_execution"] is False
    assert failed_claim.payload["provider_model_applicability"] == "not_applicable"
    assert failed_claim.payload["provider_model_truth_source"] == (
        "runtime_lifecycle.claim_timeout_no_provider_execution"
    )
    assert failed_claim.payload["no_provider_model_reason"] == (
        "claim_timeout_before_worker_execution"
    )
    assert failed_run.side_effect_key == "delegation_run:run-claim-timeout:failed"
    assert failed_run.payload["failure_code"] == "claim_timeout"
    assert failed_run.payload["provider_execution"] is False
    assert failed_run.payload["provider_model_truth_source"] == (
        "runtime_lifecycle.claim_timeout_no_provider_execution"
    )
    assert failed_run.payload["no_provider_model_reason"] == (
        "claim_timeout_before_worker_execution"
    )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-claim-timeout",
    )
    assert coverage_report["summary"]["score_gate_70_to_75"] is True
    assert coverage_report["summary"]["provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["terminal_provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["production_readiness_blockers"] == []
    assert coverage_report["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1}


@pytest.mark.asyncio
async def test_runtime_lifecycle_accounts_agent_runner_no_provider_completion(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-agent-runner-no-provider",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-agent-runner-no-provider",
        title="Complete without attached provider",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-18T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-agent-runner-no-provider",
            "provider_execution": False,
            "provider_model_applicability": "not_applicable",
            "provider_model_truth_source": "agent_runner.no_provider_execution",
            "no_provider_model_reason": "agent_runner_no_provider_attached",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-runner-no-provider",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=180.0,
        metadata={
            "claim_id": "claim-agent-runner-no-provider",
            "retry_count": 0,
            "max_retries": 0,
            "claim_timeout_seconds": 300,
            "run_id": "run-agent-runner-no-provider",
            "trace_id": "trace-agent-runner-no-provider",
            "correlation_id": "corr-agent-runner-no-provider",
            "idempotency_key": "idem-agent-runner-no-provider",
        },
    )

    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="claimed",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="completed",
        result="[mock] Agent completed without attached provider",
        require_identity=True,
    )
    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="completed",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-agent-runner-no-provider",
        limit=20,
    )
    completed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "completed"
    )
    completed_claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "completed"
    )

    assert completed_run.payload["provider_execution"] is False
    assert completed_run.payload["provider_model_applicability"] == "not_applicable"
    assert completed_run.payload["provider_model_truth_source"] == (
        "agent_runner.no_provider_execution"
    )
    assert completed_run.payload["no_provider_model_reason"] == (
        "agent_runner_no_provider_attached"
    )
    assert completed_claim.payload["provider_execution"] is False
    assert completed_claim.payload["provider_model_truth_source"] == (
        "agent_runner.no_provider_execution"
    )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-agent-runner-no-provider",
    )
    assert coverage_report["summary"]["provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["terminal_provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["production_readiness_blockers"] == []
    assert coverage_report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"no_provider_execution": 1}


@pytest.mark.asyncio
async def test_runtime_lifecycle_preserves_unproven_provider_execution_marker(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-provider-unproven",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-provider-unproven",
        title="Provider response without actual served evidence",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-18T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-provider-unproven",
            "provider_execution": True,
            "provider_model_applicability": "actual_served_unproven",
            "provider_model_truth_source": "orchestrator.provider_execution_unproven",
            "provider_model_missing_reason": (
                "provider_execution_completed_without_actual_served_runtime_evidence"
            ),
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-provider-unproven",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=180.0,
        metadata={
            "claim_id": "claim-provider-unproven",
            "retry_count": 0,
            "max_retries": 0,
            "claim_timeout_seconds": 300,
            "run_id": "run-provider-unproven",
            "trace_id": "trace-provider-unproven",
            "correlation_id": "corr-provider-unproven",
            "idempotency_key": "idem-provider-unproven",
        },
    )

    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="completed",
        result="provider-backed completion with missing actual-served evidence",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-provider-unproven",
        limit=20,
    )
    completed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "completed"
    )

    assert completed_run.payload["provider_execution"] is True
    assert completed_run.payload["provider_model_applicability"] == "actual_served_unproven"
    assert completed_run.payload["provider_model_truth_source"] == (
        "orchestrator.provider_execution_unproven"
    )
    assert completed_run.payload["provider_model_missing_reason"] == (
        "provider_execution_completed_without_actual_served_runtime_evidence"
    )
    assert "actual_served_provider" not in completed_run.payload
    assert "selected_provider" not in completed_run.payload

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-provider-unproven",
    )
    assert coverage_report["summary"]["provider_model_accounted_complete"] is False
    assert coverage_report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"missing": 1}


@pytest.mark.asyncio
async def test_runtime_lifecycle_defaults_blank_terminal_receipt_to_unproven_provider(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-default-unproven",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-default-unproven",
        title="Terminal completion without route truth",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-18T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-default-unproven",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-default-unproven",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=180.0,
        metadata={
            "claim_id": "claim-default-unproven",
            "retry_count": 0,
            "max_retries": 0,
            "claim_timeout_seconds": 300,
            "run_id": "run-default-unproven",
            "trace_id": "trace-default-unproven",
            "correlation_id": "corr-default-unproven",
            "idempotency_key": "idem-default-unproven",
        },
    )

    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="claimed",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="completed",
        result="completed without route truth",
        require_identity=True,
    )
    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="completed",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-default-unproven",
        limit=20,
    )
    completed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "completed"
    )
    completed_claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "completed"
    )
    claimed_claim = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "task_claim" and receipt.status == "claimed"
    )

    assert claimed_claim.payload["provider_execution"] == "pending"
    assert claimed_claim.payload["provider_model_applicability"] == "pending_execution"
    assert claimed_claim.payload["provider_model_truth_source"] == (
        "runtime_lifecycle.provider_execution_pending"
    )
    assert claimed_claim.payload["provider_model_pending_reason"] == (
        "worker_execution_not_terminal"
    )
    for receipt in (completed_run, completed_claim):
        assert receipt.payload["provider_execution"] is True
        assert receipt.payload["provider_model_applicability"] == "actual_served_unproven"
        assert receipt.payload["provider_model_truth_source"] == (
            "runtime_lifecycle.provider_execution_unproven"
        )
        assert receipt.payload["provider_model_missing_reason"] == (
            "terminal_receipt_missing_actual_served_or_no_provider_evidence"
        )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-default-unproven",
    )
    assert coverage_report["summary"]["provider_model_accounted_complete"] is False
    assert coverage_report["summary"]["terminal_provider_model_accounted_complete"] is False
    assert coverage_report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"missing": 1}


@pytest.mark.asyncio
async def test_runtime_lifecycle_accounts_provider_chain_execution_error_route(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-provider-chain-error",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-provider-chain-error",
        title="Provider chain fails after selected route",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-18T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-provider-chain-error",
            "selected_provider": "openrouter",
            "selected_model": "gpt-5.5",
            "provider_model_truth_source": "agent_runner.provider_chain_failure",
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-provider-chain-error",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=60.0,
        metadata={
            "claim_id": "claim-provider-chain-error",
            "run_id": "run-provider-chain-error",
            "runtime_run_id": "run-provider-chain-error",
            "trace_id": "trace-provider-chain-error",
            "correlation_id": "corr-provider-chain-error",
            "idempotency_key": "idem-provider-chain-error",
        },
    )

    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="failed",
        failure_code="execution_error",
        error="All providers failed in chain ['openrouter']",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="failed",
        failure_code="execution_error",
        error="All providers failed in chain ['openrouter']",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-provider-chain-error",
        limit=20,
    )
    failed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "failed"
    )

    assert failed_run.payload["failure_code"] == "execution_error"
    assert failed_run.payload["selected_provider"] == "openrouter"
    assert failed_run.payload["selected_model"] == "gpt-5.5"
    assert failed_run.payload["provider"] == "openrouter"
    assert failed_run.payload["model"] == "gpt-5.5"
    assert failed_run.payload["provider_model_truth_source"] == (
        "agent_runner.provider_chain_failure"
    )
    assert "actual_served_provider" not in failed_run.payload
    assert failed_run.payload["provider_execution"] is True
    assert failed_run.payload["provider_model_applicability"] == "failed_before_serve"
    assert failed_run.payload["provider_model_missing_reason"] == (
        "provider_chain_failed_before_actual_served_response"
    )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-provider-chain-error",
    )
    assert coverage_report["summary"]["score_gate_70_to_75"] is True
    assert coverage_report["summary"]["provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["terminal_provider_model_accounted_complete"] is True
    assert coverage_report["summary"]["production_readiness_blockers"] == []
    assert coverage_report["major_task_receipts"][
        "latest_provider_model_payload_class_breakdown"
    ] == {"failed_before_serve": 1}


@pytest.mark.asyncio
async def test_runtime_lifecycle_long_timeout_keeps_provider_execution_unknown(
    tmp_path: Path,
) -> None:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id="sess-runtime-lifecycle-long-timeout",
        runtime_db_path=runtime_db_path,
    )
    lifecycle = RuntimeLifecycle(ledger)

    task = Task(
        id="task-long-timeout",
        title="Long timeout during execution",
        metadata={
            "active_claim": {
                "claimed_at": "2026-06-14T00:00:00+00:00",
                "claim_expires_at_epoch": 1_800_000_000,
            },
            "requested_output": [],
            "mission_id": "mission-long-timeout",
            "timeout_seconds": 3600,
        },
    )
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id="agent-long-timeout",
        topology=TopologyType.FAN_OUT,
        timeout_seconds=3600.0,
        metadata={
            "claim_id": "claim-long-timeout",
            "run_id": "run-long-timeout",
            "runtime_run_id": "run-long-timeout",
            "trace_id": "trace-long-timeout",
            "correlation_id": "corr-long-timeout",
            "idempotency_key": "idem-long-timeout",
            "claim_timeout_seconds": 3660,
        },
    )

    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="claimed",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="running",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="failed",
        failure_code="long_timeout",
        error="Execution exceeded long timeout",
        require_identity=True,
    )

    from dharma_swarm.operator_core.runtime_truth import (
        runtime_truth_packets_from_runtime_db,
    )

    packets = runtime_truth_packets_from_runtime_db(
        runtime_db_path,
        observed_at="2026-06-29T17:45:00Z",
    )
    latest = next(
        packet for packet in packets if packet.surface_id == "runtime_state.latest_receipt"
    )
    assert latest.receipt_refs[0].startswith("runtime_receipts:")
    assert latest.metadata["no_artifact_refs_reason"] == (
        "delegation_run has no current_artifact_id"
    )
    assert "artifact_refs" not in latest.missing_machine_fields

    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="failed",
        failure_code="long_timeout",
        error="Execution exceeded long timeout",
        require_identity=True,
    )

    receipts = await RuntimeStateStore(runtime_db_path).list_runtime_receipts(
        run_id="run-long-timeout",
        limit=20,
    )
    failed_run = next(
        receipt
        for receipt in receipts
        if receipt.receipt_type == "delegation_run" and receipt.status == "failed"
    )

    assert failed_run.side_effect_key == "delegation_run:run-long-timeout:failed"
    assert failed_run.payload["failure_code"] == "long_timeout"
    assert failed_run.payload["mission_id"] == "mission-long-timeout"
    assert failed_run.payload["no_artifact_refs_reason"] == (
        "delegation_run has no current_artifact_id"
    )
    assert failed_run.payload["provider_execution"] is True
    assert failed_run.payload["provider_model_applicability"] == "actual_served_unproven"
    assert failed_run.payload["provider_model_truth_source"] == (
        "runtime_lifecycle.provider_execution_unproven"
    )
    assert failed_run.payload["provider_model_missing_reason"] == (
        "terminal_receipt_missing_actual_served_or_no_provider_evidence"
    )

    coverage_report = _load_receipt_coverage_report().build_report(
        runtime_db_path,
        run_id="run-long-timeout",
    )
    assert coverage_report["summary"]["score_gate_70_to_75"] is True
    assert coverage_report["summary"]["provider_model_accounted_complete"] is False
    assert coverage_report["major_task_receipts"][
        "latest_terminal_provider_model_payload_class_breakdown"
    ] == {"missing": 1}
