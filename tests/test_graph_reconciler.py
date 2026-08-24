"""Tests for dharma_swarm.graph.reconciler -- orphaned dispatch reconciliation.

Fixture-DB style: rows are fabricated directly in a temp runtime.db, then the
reconciler runs against it and the resulting rows are asserted.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import aiosqlite
import pytest

from dharma_swarm.graph.reconciler import (
    FAILURE_CODE_DIED_MID_DISPATCH,
    FAILURE_CODE_NEVER_STARTED,
    QUARANTINE_REASON,
    ClaimHeartbeatError,
    GraphReconciler,
    ReconcileReport,
)
from dharma_swarm.graph.reconcile_board import (
    build_task_board_completion_binding,
    settle_task_board,
    terminal_task_board_projection_metadata,
)
from dharma_swarm.graph.receipt_authority import has_runtime_completion
from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity

NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def runtime(tmp_path: Path) -> RuntimeStateStore:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    store.init_db_sync()
    return store


def _insert_run(
    store: RuntimeStateStore,
    run_id: str,
    *,
    status: str = "running",
    claim_id: str = "",
    task_id: str = "task-1",
    receipt_json: str | None = None,
    metadata: dict | None = None,
    quarantined_at: str | None = None,
    assigned_to: str = "agent-1",
    assigned_by: str = "",
    session_id: str = "",
    parent_run_id: str = "",
    legacy_compatibility: bool = True,
) -> None:
    runtime_metadata = (
        {
            "legacy_no_identity_allowed": True,
            "runtime_spine_status": "legacy_no_identity",
        }
        if legacy_compatibility
        else {}
    )
    runtime_metadata.update(metadata or {})
    with sqlite3.connect(store.db_path) as db:
        try:
            db.execute("ALTER TABLE delegation_runs ADD COLUMN quarantined_at TEXT")
            db.execute("ALTER TABLE delegation_runs ADD COLUMN quarantine_reason TEXT")
        except sqlite3.Error:
            pass
        db.execute(
            "INSERT INTO delegation_runs (run_id, session_id, task_id, claim_id,"
            " parent_run_id, assigned_by, assigned_to, status, started_at,"
            " metadata_json, receipt_json, quarantined_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                session_id,
                task_id,
                claim_id,
                parent_run_id,
                assigned_by,
                assigned_to,
                status,
                (NOW - timedelta(minutes=10)).isoformat(),
                json.dumps(runtime_metadata),
                receipt_json,
                quarantined_at,
            ),
        )
        db.commit()


def _insert_claim(
    store: RuntimeStateStore,
    claim_id: str,
    *,
    status: str = "running",
    task_id: str = "task-1",
    acked_at: str | None = None,
    claimed_at: str | None = None,
    heartbeat_at: str | None = None,
    stale_after: str | None = None,
    recovered_at: str | None = None,
    retry_count: int = 0,
    agent_id: str = "agent-1",
    session_id: str = "",
    metadata: dict | None = None,
    legacy_compatibility: bool = True,
) -> None:
    claim_metadata = (
        {
            "legacy_no_identity_allowed": True,
            "runtime_spine_status": "legacy_no_identity",
        }
        if legacy_compatibility
        else {}
    )
    claim_metadata.update(metadata or {})
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO task_claims (claim_id, task_id, session_id, agent_id, status,"
            " claimed_at, acked_at, heartbeat_at, stale_after, recovered_at,"
            " retry_count, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                claim_id,
                task_id,
                session_id,
                agent_id,
                status,
                claimed_at or (NOW - timedelta(minutes=10)).isoformat(),
                acked_at,
                heartbeat_at,
                stale_after,
                recovered_at,
                retry_count,
                json.dumps(claim_metadata),
            ),
        )
        db.commit()


def _bound_receipt(
    store: RuntimeStateStore,
    *,
    run_id: str,
    claim_id: str,
    task_id: str = "task-1",
    status: str = "ok",
    error_source: str = "none",
    agent_id: str | None = "agent-1",
) -> str:
    receipt_id = str(uuid4())
    side_effect_key = f"fixture:{task_id}:{receipt_id}"
    idempotency_key = f"fixture:{receipt_id}"
    receipt = {
        "receipt_id": receipt_id,
        "task_id": task_id,
        "claim_id": claim_id,
        "agent_id": agent_id,
        "status": status,
        "error_source": error_source,
        "attributes": {
            "run_id": run_id,
            "idempotency_key": idempotency_key,
            "side_effect_key": side_effect_key,
        },
    }
    record_status = "completed" if status == "ok" else "failed"
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO idempotency_records (idempotency_key, side_effect_key,"
            " run_id, task_id, status, result_receipt_id, metadata_json, created_at,"
            " updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                idempotency_key,
                side_effect_key,
                run_id,
                task_id,
                record_status,
                receipt_id,
                json.dumps({"receipt": receipt}),
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        db.commit()
    return json.dumps(receipt)


def _get_run(store: RuntimeStateStore, run_id: str) -> sqlite3.Row:
    with sqlite3.connect(store.db_path) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "SELECT * FROM delegation_runs WHERE run_id = ?", (run_id,)
        ).fetchone()


def _get_claim(store: RuntimeStateStore, claim_id: str) -> sqlite3.Row:
    with sqlite3.connect(store.db_path) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "SELECT * FROM task_claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()


async def _seed_exact_terminal_projection(
    store: RuntimeStateStore,
    tmp_path: Path,
    *,
    run_id: str = "run-exact-projection",
    status: str = "completed",
    result: str = "exact provider result",
    durable_result: str | None = None,
    error_source: str = "internal_error",
):
    """Create one real V4 terminal outbox and its exact running Board attempt."""
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / f"{run_id}-tasks.db")
    await board.init_db()
    task = await board.create(f"projection fixture {run_id}")
    identity = ExecutionIdentity(
        trace_id=f"trace-{run_id}",
        correlation_id=f"correlation-{run_id}",
        task_id=task.id,
        run_id=run_id,
        claim_id=f"claim-{run_id}",
        idempotency_key=f"dispatch-{run_id}",
        agent_id="agent-exact",
        session_id="session-exact",
        metadata={"source": "test_graph_reconciler"},
    )
    board_metadata = {
        **identity.to_metadata(),
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "task_id": identity.task_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "parent_run_id": identity.parent_run_id,
        "causation_id": identity.causation_id,
        "idempotency_key": identity.idempotency_key,
        "runtime_db_path": str(store.db_path),
        "active_claim": {
            "claim_id": identity.claim_id,
            "agent_id": identity.agent_id,
        },
        "fixture_owner": "preserved",
    }
    with sqlite3.connect(board._db_path) as db:
        db.execute(
            "UPDATE tasks SET status = 'running', assigned_to = ?, metadata = ?"
            " WHERE id = ?",
            (identity.agent_id, json.dumps(board_metadata), task.id),
        )
        db.commit()

    receipt_id = str(uuid4())
    side_effect_key = f"invoke_agent:{task.id}:{identity.agent_id}"
    receipt_status = "ok" if status == "completed" else "failed"
    receipt = {
        "receipt_id": receipt_id,
        "trace_id": identity.trace_id,
        "context_id": identity.session_id,
        "task_id": task.id,
        "claim_id": identity.claim_id,
        "agent_id": identity.agent_id,
        "operation": "invoke_agent",
        "provider_attempted": True,
        "status": receipt_status,
        "error_source": "none" if status == "completed" else error_source,
        "error_detail": None if status == "completed" else result,
        "attributes": {
            "run_id": identity.run_id,
            "idempotency_key": "sek_"
            + hashlib.sha256(side_effect_key.encode()).hexdigest(),
            "dispatch_idempotency_key": identity.idempotency_key,
            "side_effect_key": side_effect_key,
        },
    }
    dispatch = SimpleNamespace(
        task_id=task.id,
        agent_id=identity.agent_id,
        metadata={
            "execution_identity": identity.to_dict(),
            "evidence_receipt_id": receipt_id,
        },
    )
    binding = build_task_board_completion_binding(dispatch, result=result)
    record_metadata = {
        "operation_hash": hashlib.sha256(side_effect_key.encode()).hexdigest(),
        "task_id": task.id,
        "receipt": receipt,
        "result_json": json.dumps(
            result if durable_result is None else durable_result
        )
        if status == "completed"
        else None,
    }
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, metadata_json,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                binding["idempotency_key"],
                side_effect_key,
                identity.run_id,
                task.id,
                identity.trace_id,
                identity.correlation_id,
                status,
                receipt_id,
                json.dumps(record_metadata),
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        db.commit()

    # Match the RuntimeLifecycle carrier: the nested identity plus the flat
    # aliases it historically guarantees.  Prepare must derive the other
    # three aliases inside the terminal transaction before sealing.
    run_metadata = {
        **identity.to_metadata(),
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "idempotency_key": identity.idempotency_key,
        "status": status,
        "error": result if status == "failed" else "",
    }
    run_metadata = terminal_task_board_projection_metadata(
        run_metadata,
        task_id=task.id,
        run_id=identity.run_id,
        run_status=status,
        board_result=result,
        completion_binding=binding,
        now=NOW,
        source="test_graph_reconciler.exact_outbox",
        board_metadata_set={"projection_delta": "exact"},
        board_metadata_remove=["active_claim"],
    )
    run = await store.record_delegation_run(
        DelegationRun(
            run_id=identity.run_id,
            task_id=task.id,
            assigned_to=identity.agent_id,
            status=status,
            session_id=identity.session_id,
            claim_id=identity.claim_id,
            parent_run_id=identity.parent_run_id,
            assigned_by="orchestrator",
            started_at=NOW - timedelta(minutes=1),
            completed_at=NOW,
            failure_code="" if status == "completed" else error_source,
            metadata=run_metadata,
        )
    )
    return board, task, identity, run


def _canonical_runtime_metadata(
    identity: ExecutionIdentity,
    extra: dict | None = None,
) -> dict:
    """Return the flat carrier RuntimeState writes for RuntimeLifecycle."""
    return {
        **identity.to_metadata(),
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "idempotency_key": identity.idempotency_key,
        **dict(extra or {}),
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", "foreign-run"),
        ("idempotency_key", "foreign-idempotency"),
        ("trace_id", "foreign-trace"),
        ("correlation_id", "foreign-correlation"),
        ("claim_id", "unexpected-v1-field"),
    ],
)
def test_legacy_mission_owner_stamp_must_match_exact_runtime_attempt(
    field: str,
    value: str,
) -> None:
    from dharma_swarm.task_board_campaign_guard import _exact_board_execution_attempt

    identity = ExecutionIdentity(
        trace_id="trace-legacy-owner",
        correlation_id="correlation-legacy-owner",
        task_id="task-legacy-owner",
        run_id="run-legacy-owner",
        claim_id="claim-legacy-owner",
        idempotency_key="dispatch-legacy-owner",
        agent_id="agent-legacy-owner",
        session_id="session-legacy-owner",
    )
    metadata = {
        **_canonical_runtime_metadata(identity),
        "task_id": identity.task_id,
        "mission_control_owner_execution": {
            "schema_version": "dharma.mission_control.owner_execution.v1",
            "backend": "orchestrator",
            "mission_id": "mission-legacy-owner",
            "task_id": identity.task_id,
            "dispatch_key": "default",
            "run_id": identity.run_id,
            "idempotency_key": identity.idempotency_key,
            "trace_id": identity.trace_id,
            "correlation_id": identity.correlation_id,
        },
    }
    assert _exact_board_execution_attempt(
        metadata,
        task_id=identity.task_id,
        assigned_to=identity.agent_id,
    ) is not None

    forged = copy.deepcopy(metadata)
    forged["mission_control_owner_execution"][field] = value

    assert _exact_board_execution_attempt(
        forged,
        task_id=identity.task_id,
        assigned_to=identity.agent_id,
    ) is None


def _validated_campaign_metadata(principal: str, task_id: str) -> dict:
    campaign_id = "campaign-exact"
    goal_id = "goal-exact"
    portfolio = "sha256:" + "a" * 64
    goal = "sha256:" + "b" * 64
    content = "Observed execution fixture; verify independently.\n"
    content_sha = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
    observed_manifest = "sha256:" + "3" * 64
    observed_ref = {
        "receipt_id": "observed-receipt-fixture",
        "receipt_sha256": "sha256:" + "4" * 64,
        "artifact_id": "observed-artifact-fixture",
        "artifact_record_sha256": "sha256:" + "5" * 64,
        "content_sha256": content_sha,
    }
    return {
        "campaign_id": campaign_id,
        "goal_id": goal_id,
        "portfolio_contract_sha256": portfolio,
        "goal_contract_sha256": goal,
        "attempt_ceiling": 3,
        "attempt_generation": 0,
        "mission_task_id": task_id,
        "mission_observed_input": {
            "schema_version": "dharma.sadhana.observed_input_prompt.v1",
            "campaign_id": campaign_id,
            "mission_id": campaign_id,
            "goal_id": goal_id,
            "task_id": task_id,
            "manifest_digest": observed_manifest,
            "goal_contract_sha256": goal,
            "task_creation_hash": "6" * 64,
            "observed_at": "2026-08-23T00:00:00+00:00",
            "epistemic_state": "observed_unverified",
            "authority_scope": "prompt_context_only",
            "media_type": "text/markdown; charset=utf-8",
            "content": content,
            "content_sha256": content_sha,
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
            "campaign_id": campaign_id,
            "mission_id": campaign_id,
            "goal_id": goal_id,
            "portfolio_contract_sha256": portfolio,
            "goal_contract_sha256": goal,
            "manifest_digest": "sha256:" + "c" * 64,
            "observed_input_manifest_digest": observed_manifest,
            "held_out_oracle_manifest_digest": "sha256:" + "7" * 64,
            "operator_control_semantics_sha256": "sha256:" + "8" * 64,
            "operator_control_authority_binding_sha256": "sha256:" + "9" * 64,
            "deployment_authority_topology_sha256": "sha256:" + "0" * 64,
            "deployment_authority_credential_clarification_sha256": (
                "sha256:" + "1" * 64
            ),
            "observed_input_ref": observed_ref,
            "agent_roster_sha256": "d" * 64,
            "effect_mode": "read_only",
            "campaign_end": "2026-09-02T00:00:00+00:00",
            "agent_name": "campaign-seat",
            "claimed_principal": principal,
            "dispatch_key": "default",
            "request_id": "request-fixture",
            "workspace_path": "workspaces/goal-exact",
            "allowed_files": ["workspaces/goal-exact/**"],
            "max_usd": 0.0,
            "authority_ref": "lease-fixture",
            "authority_digest": "sha256:" + "e" * 64,
            "attempt_generation": 0,
            "max_attempts": 3,
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


def _campaign_fence(
    identity: ExecutionIdentity,
    authority: dict | None = None,
) -> dict:
    authority = authority or _validated_campaign_metadata(
        identity.agent_id, identity.task_id
    )["mission_campaign_authority"]
    return {
        "campaign_runtime_recovery_fence": {
            "schema_version": "dharma.sadhana.campaign_runtime_recovery_fence.v1",
            "task_id": identity.task_id,
            "campaign_id": authority["campaign_id"],
            "goal_id": authority["goal_id"],
            "claimed_principal": identity.agent_id,
            "authority_digest": authority["authority_digest"],
            "attempt_generation": authority["attempt_generation"],
        }
    }


async def _seed_running_campaign(
    store: RuntimeStateStore,
    tmp_path: Path,
    *,
    run_id: str,
    stale: bool,
    board=None,
):
    from dharma_swarm.mission_control_executor_guard import campaign_principal
    from dharma_swarm.mission_control_task_attempts import (
        GOVERNANCE_SCHEMA_V4,
        _GOVERNANCE_FIELDS,
    )
    from dharma_swarm.task_board import TaskBoard
    from dharma_swarm.task_board_campaign_guard import valid_board_campaign_authority

    if board is None:
        board = TaskBoard(tmp_path / f"{run_id}-campaign-tasks.db")
        await board.init_db()
    task = await board.create(f"campaign fixture {run_id}")
    identity = ExecutionIdentity(
        trace_id=f"trace-{run_id}",
        correlation_id=f"correlation-{run_id}",
        task_id=task.id,
        run_id=run_id,
        claim_id=f"claim-{run_id}",
        idempotency_key=f"dispatch-{run_id}",
        agent_id="campaign-agent",
        session_id="campaign-session",
        metadata={"source": "RuntimeLifecycle.fixture"},
    )
    campaign = _validated_campaign_metadata(identity.agent_id, task.id)
    authority = campaign["mission_campaign_authority"]
    fence = _campaign_fence(identity, authority)
    owner = {
        "schema_version": "dharma.mission_control.owner_execution.v2",
        "backend": "orchestrator",
        "mission_id": authority["mission_id"],
        "task_id": task.id,
        "dispatch_key": authority["dispatch_key"],
        "attempt_generation": authority["attempt_generation"],
        "run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "idempotency_key": identity.idempotency_key,
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
    }
    board_metadata = {
        **_canonical_runtime_metadata(identity),
        "task_id": identity.task_id,
        "parent_run_id": identity.parent_run_id,
        "causation_id": identity.causation_id,
        "runtime_db_path": str(store.db_path),
        "active_claim": {
            "claim_id": identity.claim_id,
            "agent_id": identity.agent_id,
        },
        **campaign,
        "mission_control_governance": {
            key: GOVERNANCE_SCHEMA_V4
            if key == "schema_version"
            else []
            if key == "forbidden_files"
            else authority[key]
            for key in _GOVERNANCE_FIELDS
        },
        "mission_control_owner_execution": owner,
        "campaign_dispatch_attempt_history": [],
    }
    with sqlite3.connect(board._db_path) as db:
        db.execute(
            "UPDATE tasks SET status = 'running', assigned_to = ?, metadata = ?"
            " WHERE id = ?",
            (identity.agent_id, json.dumps(board_metadata), task.id),
        )
        db.commit()

    claimed_at = NOW - timedelta(minutes=30)
    heartbeat_at = NOW - timedelta(minutes=21)
    stale_after = (
        NOW - timedelta(minutes=1) if stale else NOW + timedelta(minutes=30)
    )
    claim = await store.record_task_claim(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=task.id,
            agent_id=identity.agent_id,
            status="running",
            session_id=identity.session_id,
            claimed_at=claimed_at,
            acked_at=claimed_at,
            heartbeat_at=heartbeat_at,
            stale_after=stale_after,
            metadata={**identity.to_metadata(), **fence},
        )
    )
    run = await store.record_delegation_run(
        DelegationRun(
            run_id=identity.run_id,
            task_id=task.id,
            assigned_to=identity.agent_id,
            status="running",
            session_id=identity.session_id,
            claim_id=identity.claim_id,
            assigned_by="orchestrator",
            started_at=claimed_at,
            metadata={
                **identity.to_metadata(),
                **fence,
                "status": "running",
            },
        )
    )
    # These are the three intentionally absent aliases in the real running
    # carrier; canonical classification must use the nested/SQL authority.
    assert all(
        key not in run.metadata for key in ("task_id", "parent_run_id", "causation_id")
    )
    observed = await board.get(task.id)
    assert campaign_principal(observed) == (True, identity.agent_id)
    assert valid_board_campaign_authority(board_metadata, task_id=task.id)
    return board, task, identity, claim, run


def _attach_exact_runtime_receipt(
    store: RuntimeStateStore,
    identity: ExecutionIdentity,
    *,
    result: str,
) -> dict:
    receipt_id = str(uuid4())
    side_effect_key = f"invoke_agent:{identity.task_id}:{identity.agent_id}"
    idempotency_key = "sek_" + hashlib.sha256(side_effect_key.encode()).hexdigest()
    receipt = {
        "receipt_id": receipt_id,
        "trace_id": identity.trace_id,
        "context_id": identity.session_id,
        "task_id": identity.task_id,
        "claim_id": identity.claim_id,
        "agent_id": identity.agent_id,
        "operation": "invoke_agent",
        "provider_attempted": True,
        "status": "ok",
        "error_source": "none",
        "error_detail": None,
        "attributes": {
            "run_id": identity.run_id,
            "idempotency_key": idempotency_key,
            "dispatch_idempotency_key": identity.idempotency_key,
            "side_effect_key": side_effect_key,
        },
    }
    record_metadata = {
        "operation_hash": hashlib.sha256(side_effect_key.encode()).hexdigest(),
        "task_id": identity.task_id,
        "receipt": receipt,
        "result_json": json.dumps(result),
    }
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, metadata_json,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?)",
            (
                idempotency_key,
                side_effect_key,
                identity.run_id,
                identity.task_id,
                identity.trace_id,
                identity.correlation_id,
                receipt_id,
                json.dumps(record_metadata),
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        db.execute(
            "UPDATE delegation_runs SET receipt_json = ? WHERE run_id = ?",
            (json.dumps(receipt), identity.run_id),
        )
        db.commit()
    return receipt


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


async def test_never_started_orphan_requeued_as_claim_timeout(runtime):
    _insert_run(runtime, "run-ns", status="claimed", claim_id="claim-ns")
    _insert_claim(runtime, "claim-ns", status="claimed")

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.requeued_runs == ["run-ns"]
    run = _get_run(runtime, "run-ns")
    assert run["status"] == "failed"
    assert run["failure_code"] == FAILURE_CODE_NEVER_STARTED
    claim = _get_claim(runtime, "claim-ns")
    assert claim["status"] == "recovered"
    assert claim["recovered_at"] == NOW.isoformat()


async def test_started_and_died_with_retries_left_requeued(runtime):
    _insert_run(runtime, "run-died", status="running", claim_id="claim-died")
    _insert_claim(
        runtime,
        "claim-died",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
        heartbeat_at=(NOW - timedelta(minutes=5)).isoformat(),
        retry_count=1,
    )

    report = await GraphReconciler(runtime, max_retries=3).reconcile(now=NOW)

    assert report.requeued_runs == ["run-died"]
    run = _get_run(runtime, "run-died")
    assert run["status"] == "failed"
    assert run["failure_code"] == FAILURE_CODE_DIED_MID_DISPATCH
    assert json.loads(run["metadata_json"])["retry_count"] == 2
    claim = _get_claim(runtime, "claim-died")
    assert claim["retry_count"] == 2
    assert claim["recovered_at"] == NOW.isoformat()


async def test_retry_exhausted_orphan_quarantined(runtime):
    _insert_run(runtime, "run-exh", status="running", claim_id="claim-exh")
    _insert_claim(
        runtime,
        "claim-exh",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
        retry_count=3,
    )

    report = await GraphReconciler(runtime, max_retries=3).reconcile(now=NOW)

    assert report.quarantined_runs == ["run-exh"]
    assert report.summary()["quarantined_runs"] == 1
    run = _get_run(runtime, "run-exh")
    assert run["status"] == "failed"
    assert run["quarantined_at"] == NOW.isoformat()
    assert run["quarantine_reason"] == QUARANTINE_REASON
    claim = _get_claim(runtime, "claim-exh")
    assert claim["recovered_at"] == NOW.isoformat()


# ---------------------------------------------------------------------------
# Torn window: bound receipt + runtime completion are ground truth
# ---------------------------------------------------------------------------


async def test_torn_window_completes_run_and_claim_from_receipt(runtime):
    receipt = _bound_receipt(runtime, run_id="run-torn", claim_id="claim-torn")
    _insert_run(
        runtime,
        "run-torn",
        status="running",
        claim_id="claim-torn",
        receipt_json=receipt,
    )
    _insert_claim(
        runtime,
        "claim-torn",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == ["run-torn"]
    assert report.requeued_runs == []
    run = _get_run(runtime, "run-torn")
    assert run["status"] == "completed"
    assert run["failure_code"] == ""
    claim = _get_claim(runtime, "claim-torn")
    assert claim["status"] == "completed"
    assert claim["recovered_at"] == NOW.isoformat()


async def test_torn_window_failed_receipt_marks_failed(runtime):
    receipt = _bound_receipt(
        runtime,
        run_id="run-tf",
        claim_id="claim-tf",
        status="failed",
        error_source="provider",
    )
    _insert_run(
        runtime, "run-tf", status="running", claim_id="claim-tf", receipt_json=receipt
    )
    _insert_claim(
        runtime,
        "claim-tf",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == ["run-tf"]
    run = _get_run(runtime, "run-tf")
    assert run["status"] == "failed"
    assert run["failure_code"] == "provider"
    claim = _get_claim(runtime, "claim-tf")
    assert claim["status"] == "failed"
    assert claim["recovered_at"] == NOW.isoformat()


async def test_status_only_receipt_cannot_promote_run(runtime):
    receipt = json.dumps(
        {
            "receipt_id": str(uuid4()),
            "status": "ok",
            "task_id": "task-1",
            "attributes": {"side_effect_key": "fixture:unbound"},
        }
    )
    _insert_run(
        runtime,
        "run-status-only",
        status="running",
        claim_id="claim-status-only",
        receipt_json=receipt,
    )
    _insert_claim(
        runtime,
        "claim-status-only",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == []
    assert report.requeued_runs == ["run-status-only"]
    assert _get_run(runtime, "run-status-only")["status"] == "failed"


async def test_completion_for_different_retry_cannot_promote_stale_run(runtime):
    """A task-level match is not authority when two retries share a task."""
    receipt_id = str(uuid4())
    side_effect_key = f"fixture:task-1:{receipt_id}"
    receipt = {
        "receipt_id": receipt_id,
        "task_id": "task-1",
        "claim_id": "claim-current",
        "status": "ok",
        "error_source": "none",
        "attributes": {
            "run_id": "run-current",
            "idempotency_key": f"fixture:{receipt_id}",
            "side_effect_key": side_effect_key,
        },
    }
    with sqlite3.connect(runtime.db_path) as db:
        db.execute(
            "INSERT INTO idempotency_records (idempotency_key, side_effect_key,"
            " run_id, task_id, status, result_receipt_id, metadata_json, created_at,"
            " updated_at) VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?)",
            (
                f"fixture:{receipt_id}",
                side_effect_key,
                "run-current",
                "task-1",
                receipt_id,
                json.dumps({"receipt": receipt}),
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        db.commit()
    _insert_run(
        runtime,
        "run-stale",
        status="running",
        claim_id="claim-stale",
        receipt_json=json.dumps(receipt),
    )
    _insert_claim(
        runtime,
        "claim-stale",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == []
    assert report.requeued_runs == ["run-stale"]
    assert _get_run(runtime, "run-stale")["status"] == "failed"


async def test_declared_idempotency_key_must_match_completion_row(runtime):
    receipt_id = str(uuid4())
    side_effect_key = f"fixture:task-1:{receipt_id}"
    receipt = {
        "receipt_id": receipt_id,
        "task_id": "task-1",
        "claim_id": "claim-key-mismatch",
        "status": "ok",
        "error_source": "none",
        "attributes": {
            "run_id": "run-key-mismatch",
            "idempotency_key": "fixture:declared-key",
            "side_effect_key": side_effect_key,
        },
    }
    with sqlite3.connect(runtime.db_path) as db:
        db.execute(
            "INSERT INTO idempotency_records (idempotency_key, side_effect_key,"
            " run_id, task_id, status, result_receipt_id, metadata_json, created_at,"
            " updated_at) VALUES ('fixture:database-key', ?, ?, 'task-1',"
            " 'completed', ?, ?, ?, ?)",
            (
                side_effect_key,
                "run-key-mismatch",
                receipt_id,
                json.dumps({"receipt": receipt}),
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        db.commit()
    _insert_run(
        runtime,
        "run-key-mismatch",
        claim_id="claim-key-mismatch",
        receipt_json=json.dumps(receipt),
    )
    _insert_claim(runtime, "claim-key-mismatch", acked_at=NOW.isoformat())

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == []
    assert report.requeued_runs == ["run-key-mismatch"]


async def test_completion_cannot_promote_claim_owned_by_different_task(runtime):
    """A claim ID cannot confer authority across its durable task boundary."""
    receipt = _bound_receipt(
        runtime,
        run_id="run-task-one",
        claim_id="claim-cross-task",
        task_id="task-one",
    )
    _insert_run(
        runtime,
        "run-task-one",
        task_id="task-one",
        claim_id="claim-cross-task",
        receipt_json=receipt,
    )
    _insert_claim(
        runtime,
        "claim-cross-task",
        task_id="task-two",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == []
    assert report.requeued_runs == ["run-task-one"]
    assert _get_run(runtime, "run-task-one")["status"] == "failed"
    claim = _get_claim(runtime, "claim-cross-task")
    assert claim["task_id"] == "task-two"
    assert claim["status"] == "running"


async def test_agentless_receipt_cannot_promote_canonical_run(runtime):
    """Regression: the old helper false-greened this fully bound receipt."""
    receipt = _bound_receipt(
        runtime,
        run_id="run-agentless",
        claim_id="claim-agentless",
        agent_id=None,
    )
    _insert_run(
        runtime,
        "run-agentless",
        claim_id="claim-agentless",
        receipt_json=receipt,
    )
    _insert_claim(runtime, "claim-agentless", acked_at=NOW.isoformat())

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == []
    assert report.requeued_runs == ["run-agentless"]
    assert _get_run(runtime, "run-agentless")["status"] == "failed"


async def test_receipt_agent_must_match_run_and_claim_agents(runtime):
    receipt = _bound_receipt(
        runtime,
        run_id="run-receipt-agent",
        claim_id="claim-receipt-agent",
        agent_id="agent-forged",
    )
    _insert_run(
        runtime,
        "run-receipt-agent",
        claim_id="claim-receipt-agent",
        receipt_json=receipt,
        assigned_to="agent-owner",
    )
    _insert_claim(
        runtime,
        "claim-receipt-agent",
        agent_id="agent-owner",
        acked_at=NOW.isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == []
    assert report.requeued_runs == ["run-receipt-agent"]


async def test_cross_agent_claim_is_not_promoted_or_recovered_for_run(runtime):
    """A run must not mutate a real claim owned by a different agent."""
    receipt = _bound_receipt(
        runtime,
        run_id="run-cross-agent",
        claim_id="claim-cross-agent",
        agent_id="agent-run",
    )
    _insert_run(
        runtime,
        "run-cross-agent",
        claim_id="claim-cross-agent",
        receipt_json=receipt,
        assigned_to="agent-run",
    )
    _insert_claim(
        runtime,
        "claim-cross-agent",
        agent_id="agent-claim",
        acked_at=NOW.isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == []
    assert report.requeued_runs == ["run-cross-agent"]
    assert report.recovered_claims == []
    claim = _get_claim(runtime, "claim-cross-agent")
    assert claim["agent_id"] == "agent-claim"
    assert claim["status"] == "running"
    assert claim["recovered_at"] is None


async def test_cross_agent_run_does_not_recover_claim_matching_receipt(runtime):
    """The durable run assignee is an equal member of the authority triple."""
    receipt = _bound_receipt(
        runtime,
        run_id="run-other-assignee",
        claim_id="claim-matching-receipt",
        agent_id="agent-claim",
    )
    _insert_run(
        runtime,
        "run-other-assignee",
        claim_id="claim-matching-receipt",
        receipt_json=receipt,
        assigned_to="agent-run",
    )
    _insert_claim(
        runtime,
        "claim-matching-receipt",
        agent_id="agent-claim",
        acked_at=NOW.isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.completed_from_receipt == []
    assert report.requeued_runs == ["run-other-assignee"]
    assert report.recovered_claims == []
    claim = _get_claim(runtime, "claim-matching-receipt")
    assert claim["status"] == "running"
    assert claim["recovered_at"] is None


async def test_agentless_receipt_remains_compatible_when_schema_has_no_agent_fields():
    """Legacy schemas can bind every authority dimension they can express."""
    receipt_id = str(uuid4())
    receipt = {
        "receipt_id": receipt_id,
        "task_id": "legacy-task",
        "claim_id": "legacy-claim",
        "status": "ok",
        "attributes": {
            "run_id": "legacy-run",
            "idempotency_key": "legacy-key",
            "side_effect_key": "legacy-effect",
        },
    }
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "CREATE TABLE task_claims (claim_id TEXT PRIMARY KEY, task_id TEXT)"
        )
        await db.execute(
            "CREATE TABLE delegation_runs (run_id TEXT PRIMARY KEY, task_id TEXT,"
            " claim_id TEXT)"
        )
        await db.execute(
            "CREATE TABLE idempotency_records (idempotency_key TEXT,"
            " side_effect_key TEXT, run_id TEXT, task_id TEXT, status TEXT,"
            " result_receipt_id TEXT, metadata_json TEXT)"
        )
        await db.execute(
            "INSERT INTO task_claims VALUES ('legacy-claim', 'legacy-task')"
        )
        await db.execute(
            "INSERT INTO delegation_runs VALUES"
            " ('legacy-run', 'legacy-task', 'legacy-claim')"
        )
        await db.execute(
            "INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "legacy-key",
                "legacy-effect",
                "legacy-run",
                "legacy-task",
                "completed",
                receipt_id,
                json.dumps({"receipt": receipt}),
            ),
        )

        assert await has_runtime_completion(
            db,
            run_id="legacy-run",
            task_id="legacy-task",
            claim_id="legacy-claim",
            receipt=receipt,
        )


# ---------------------------------------------------------------------------
# Stale claims scan (tz-aware compare, 'Z' drift trap)
# ---------------------------------------------------------------------------


async def test_stale_claim_with_z_suffix_recovered(runtime):
    stale = (NOW - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _insert_claim(runtime, "claim-z", status="claimed", stale_after=stale)

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert "claim-z" in report.recovered_claims
    claim = _get_claim(runtime, "claim-z")
    assert claim["status"] == "recovered"
    assert claim["recovered_at"] == NOW.isoformat()


async def test_unexpired_claim_not_recovered(runtime):
    stale = (NOW + timedelta(minutes=30)).isoformat()
    _insert_claim(runtime, "claim-fresh", status="claimed", stale_after=stale)

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.recovered_claims == []
    claim = _get_claim(runtime, "claim-fresh")
    assert claim["status"] == "claimed"
    assert claim["recovered_at"] is None


# ---------------------------------------------------------------------------
# stale_only (tick-time) gating
# ---------------------------------------------------------------------------


async def test_stale_only_skips_live_run(runtime):
    _insert_run(runtime, "run-live", status="running", claim_id="claim-live")
    _insert_claim(
        runtime,
        "claim-live",
        status="running",
        acked_at=(NOW - timedelta(minutes=1)).isoformat(),
        stale_after=(NOW + timedelta(minutes=30)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW, stale_only=True)

    assert report.total_reconciled == 0
    assert _get_run(runtime, "run-live")["status"] == "running"


async def test_stale_only_settles_expired_claim_run(runtime):
    _insert_run(runtime, "run-exp", status="running", claim_id="claim-exp")
    _insert_claim(
        runtime,
        "claim-exp",
        status="running",
        acked_at=(NOW - timedelta(minutes=20)).isoformat(),
        stale_after=(NOW - timedelta(minutes=5)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW, stale_only=True)

    assert report.requeued_runs == ["run-exp"]
    assert _get_run(runtime, "run-exp")["status"] == "failed"


async def test_stale_only_still_completes_from_receipt(runtime):
    receipt = _bound_receipt(runtime, run_id="run-sr", claim_id="claim-sr")
    _insert_run(
        runtime, "run-sr", status="running", claim_id="claim-sr", receipt_json=receipt
    )
    _insert_claim(
        runtime,
        "claim-sr",
        status="running",
        stale_after=(NOW + timedelta(minutes=30)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW, stale_only=True)

    assert report.completed_from_receipt == ["run-sr"]
    assert _get_run(runtime, "run-sr")["status"] == "completed"


# ---------------------------------------------------------------------------
# Idempotency and live-row predicate
# ---------------------------------------------------------------------------


async def test_second_pass_is_noop(runtime):
    _insert_run(runtime, "run-once", status="claimed", claim_id="claim-once")
    _insert_claim(runtime, "claim-once", status="claimed")

    first = await GraphReconciler(runtime).reconcile(now=NOW)
    second = await GraphReconciler(runtime).reconcile(now=NOW + timedelta(minutes=1))

    assert first.total_reconciled == 1
    assert second.total_reconciled == 0
    assert second.recovered_claims == []


async def test_quarantined_and_terminal_rows_skipped(runtime):
    _insert_run(
        runtime,
        "run-q",
        status="running",
        quarantined_at=(NOW - timedelta(days=1)).isoformat(),
    )
    _insert_run(runtime, "run-done", status="completed")

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.total_reconciled == 0
    assert _get_run(runtime, "run-q")["status"] == "running"
    assert _get_run(runtime, "run-done")["status"] == "completed"


# ---------------------------------------------------------------------------
# Task board requeue wiring
# ---------------------------------------------------------------------------


class _StubBoard:
    legacy_settlement_test_mode = "explicit_nonproduction_test_double.v1"

    def __init__(self) -> None:
        self.requeued: list[str] = []
        self.completed: list[str] = []
        self.failed: list[str] = []

    async def requeue(self, task_id: str, reason: str = "", metadata=None):
        self.requeued.append(task_id)

    async def complete(self, task_id: str, result: str = "", metadata=None):
        self.completed.append(task_id)

    async def fail(self, task_id: str, error: str = "", metadata=None):
        self.failed.append(task_id)


class _ReplayableLegacyBoard:
    legacy_settlement_test_mode = "explicit_nonproduction_test_double.v1"

    def __init__(self, task_id: str, *, fail_first_requeue: bool = False) -> None:
        self.task = SimpleNamespace(
            id=task_id,
            status=SimpleNamespace(value="running"),
            assigned_to="agent-1",
            result=None,
            metadata={"fixture_owner": "preserved"},
        )
        self.fail_first_requeue = fail_first_requeue
        self.requeue_calls = 0

    async def get(self, task_id: str):
        return self.task if task_id == self.task.id else None

    async def requeue(self, task_id: str, reason: str = "", metadata=None):
        self.requeue_calls += 1
        if self.fail_first_requeue and self.requeue_calls == 1:
            raise RuntimeError("injected legacy Board outage")
        assert task_id == self.task.id
        self.task = SimpleNamespace(
            id=task_id,
            status=SimpleNamespace(value="pending"),
            assigned_to=None,
            result=reason,
            metadata=dict(metadata or {}),
        )
        return self.task


async def test_requeued_run_requeues_task_on_board(runtime):
    board = _StubBoard()
    _insert_run(
        runtime, "run-board", status="claimed", claim_id="claim-board", task_id="task-b"
    )
    _insert_claim(runtime, "claim-board", status="claimed", task_id="task-b")

    report = await GraphReconciler(runtime, task_board=board).reconcile(now=NOW)

    assert report.requeued_runs == ["run-board"]
    assert board.requeued == ["task-b"]


async def test_legacy_board_failure_remains_durable_until_replay(runtime):
    board = _ReplayableLegacyBoard("task-legacy-replay", fail_first_requeue=True)
    _insert_run(
        runtime,
        "run-legacy-replay",
        status="claimed",
        claim_id="claim-legacy-replay",
        task_id=board.task.id,
    )
    _insert_claim(
        runtime,
        "claim-legacy-replay",
        status="claimed",
        task_id=board.task.id,
    )
    reconciler = GraphReconciler(runtime, task_board=board)

    first = await reconciler.reconcile(now=NOW)

    assert first.requeued_runs == ["run-legacy-replay"]
    assert first.errors == ["legacy_projection:run-legacy-replay:RuntimeError"]
    assert reconciler.boot_census_succeeded is False
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM legacy_task_board_settlement_intents"
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM legacy_task_board_settlement_acks"
        ).fetchone()[0] == 0

    replay = await reconciler.reconcile(now=NOW + timedelta(seconds=1))

    assert replay.errors == []
    assert replay.total_reconciled == 0
    assert board.requeue_calls == 2
    assert board.task.status.value == "pending"
    assert board.task.metadata["fixture_owner"] == "preserved"
    assert reconciler.boot_census_succeeded is True
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM legacy_task_board_settlement_acks"
        ).fetchone()[0] == 1


async def test_legacy_board_commit_before_ack_replays_without_second_mutation(
    runtime,
    monkeypatch,
):
    from dharma_swarm.graph import reconcile_board_legacy

    board = _ReplayableLegacyBoard("task-legacy-commit")
    _insert_run(
        runtime,
        "run-legacy-commit",
        status="claimed",
        claim_id="claim-legacy-commit",
        task_id=board.task.id,
    )
    _insert_claim(
        runtime,
        "claim-legacy-commit",
        status="claimed",
        task_id=board.task.id,
    )
    reconciler = GraphReconciler(runtime, task_board=board)
    append_ack = reconcile_board_legacy._append_ack

    async def crash_before_ack(*args, **kwargs):
        raise RuntimeError("injected process loss after legacy Board commit")

    monkeypatch.setattr(reconcile_board_legacy, "_append_ack", crash_before_ack)
    first = await reconciler.reconcile(now=NOW)

    assert first.errors == ["legacy_projection:run-legacy-commit:RuntimeError"]
    assert board.requeue_calls == 1
    assert board.task.status.value == "pending"

    monkeypatch.setattr(reconcile_board_legacy, "_append_ack", append_ack)
    replay = await reconciler.reconcile(now=NOW + timedelta(seconds=1))

    assert replay.errors == []
    assert board.requeue_calls == 1
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM legacy_task_board_settlement_acks"
        ).fetchone()[0] == 1


async def test_terminal_reconciliations_settle_task_board(runtime):
    board = _StubBoard()
    receipt = _bound_receipt(
        runtime, run_id="run-rc", claim_id="claim-rc", task_id="task-rc"
    )
    _insert_run(
        runtime,
        "run-rc",
        status="running",
        claim_id="claim-rc",
        task_id="task-rc",
        receipt_json=receipt,
    )
    _insert_claim(runtime, "claim-rc", status="running", task_id="task-rc")
    _insert_run(
        runtime, "run-qb", status="running", claim_id="claim-qb", task_id="task-qb"
    )
    _insert_claim(
        runtime,
        "claim-qb",
        status="running",
        task_id="task-qb",
        acked_at=(NOW - timedelta(minutes=20)).isoformat(),
        retry_count=3,
    )

    report = await GraphReconciler(runtime, task_board=board).reconcile(now=NOW)

    assert report.completed_from_receipt == ["run-rc"]
    assert report.quarantined_runs == ["run-qb"]
    assert board.completed == ["task-rc"]
    assert board.failed == ["task-qb"]


# ---------------------------------------------------------------------------
# V4 runtime-first ProjectionIntent outbox
# ---------------------------------------------------------------------------


async def test_projection_replays_after_board_commit_then_process_failure(
    runtime,
    tmp_path: Path,
    monkeypatch,
):
    from dharma_swarm.graph import reconcile_board_replay
    from dharma_swarm.models import TaskStatus

    board, task, identity, _run = await _seed_exact_terminal_projection(
        runtime,
        tmp_path,
        run_id="run-commit-crash",
    )
    real_append = reconcile_board_replay._append_projection_ack

    async def crash_before_ack(*args, **kwargs):
        raise RuntimeError("process died after Board commit")

    monkeypatch.setattr(
        reconcile_board_replay,
        "_append_projection_ack",
        crash_before_ack,
    )
    first = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=first,
        now=NOW,
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )

    committed = await board.get(task.id)
    assert committed is not None and committed.status is TaskStatus.COMPLETED
    assert first.errors == [f"projection:{identity.run_id}:RuntimeError"]
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_acks"
        ).fetchone()[0] == 0

    monkeypatch.setattr(
        reconcile_board_replay,
        "_append_projection_ack",
        real_append,
    )
    replay = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=replay,
        now=NOW + timedelta(seconds=1),
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )

    assert replay.errors == []
    with sqlite3.connect(runtime.db_path) as db:
        ack = db.execute(
            "SELECT task_id FROM task_board_projection_acks WHERE run_id = ?",
            (identity.run_id,),
        ).fetchone()
    assert ack == (task.id,)


async def test_projection_refuses_board_mutation_without_exact_readback(
    runtime,
    tmp_path: Path,
):
    from dharma_swarm.models import TaskStatus

    board, task, identity, _run = await _seed_exact_terminal_projection(
        runtime,
        tmp_path,
        run_id="run-corrupt-readback",
    )

    class CorruptingReadbackBoard:
        projection_commit_mode = "non_production_exact_readback.v1"

        def __init__(self, delegate):
            self._delegate = delegate

        async def get(self, task_id):
            return await self._delegate.get(task_id)

        async def compare_and_swap_terminal_projection(self, expected, **kwargs):
            projected = await self._delegate.compare_and_swap_terminal_projection(
                expected,
                **kwargs,
            )
            assert projected is not None
            corrupted = {**projected.metadata, "concurrent_nonprotocol_write": True}
            with sqlite3.connect(self._delegate._db_path) as db:
                db.execute(
                    "UPDATE tasks SET metadata = ? WHERE id = ?",
                    (json.dumps(corrupted), projected.id),
                )
                db.commit()
            return await self._delegate.get(projected.id)

    report = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=CorruptingReadbackBoard(board),
        report=report,
        now=NOW,
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )

    observed = await board.get(task.id)
    assert observed is not None and observed.status is TaskStatus.COMPLETED
    assert report.errors == [f"projection:{identity.run_id}:RuntimeError"]
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_acks"
        ).fetchone()[0] == 0


async def test_production_projection_retries_fresh_after_board_cas_loss(
    runtime,
    tmp_path: Path,
    monkeypatch,
):
    board, task, identity, _run = await _seed_exact_terminal_projection(
        runtime,
        tmp_path,
        run_id="run-board-cas-loss",
    )
    real_project = board.compare_and_swap_terminal_projection
    raced = False

    async def race_before_cas(expected, **kwargs):
        nonlocal raced
        if not raced:
            raced = True
            current = await board.get(expected.id)
            assert current is not None
            changed = {**current.metadata, "concurrent_board_note": "preserve"}
            with sqlite3.connect(board._db_path) as db:
                db.execute(
                    "UPDATE tasks SET metadata = ?, updated_at = ? WHERE id = ?",
                    (
                        json.dumps(changed),
                        (NOW + timedelta(microseconds=1)).isoformat(),
                        expected.id,
                    ),
                )
                db.commit()
        return await real_project(expected, **kwargs)

    monkeypatch.setattr(board, "compare_and_swap_terminal_projection", race_before_cas)
    first = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=first,
        now=NOW,
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )

    assert first.errors == [f"projection:{identity.run_id}:RuntimeError"]
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_targets"
        ).fetchone()[0] == 0
    with sqlite3.connect(board._db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_effect_commits"
        ).fetchone()[0] == 0

    monkeypatch.setattr(board, "compare_and_swap_terminal_projection", real_project)
    replay = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=replay,
        now=NOW + timedelta(seconds=1),
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )

    projected = await board.get(task.id)
    assert replay.errors == []
    assert projected is not None and projected.status.value == "completed"
    assert projected.metadata["concurrent_board_note"] == "preserve"
    with sqlite3.connect(board._db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_effect_commits"
        ).fetchone()[0] == 1


async def test_atomic_board_commit_replays_after_board_advances(
    runtime,
    tmp_path: Path,
    monkeypatch,
):
    from dharma_swarm.graph import reconcile_board_replay

    board, task, identity, _run = await _seed_exact_terminal_projection(
        runtime,
        tmp_path,
        run_id="run-board-commit-advance",
    )
    real_import = reconcile_board_replay.append_atomic_projection_witness

    async def crash_before_runtime_witness(*args, **kwargs):
        raise RuntimeError("process died after atomic Board commit")

    monkeypatch.setattr(
        reconcile_board_replay,
        "append_atomic_projection_witness",
        crash_before_runtime_witness,
    )
    first = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=first,
        now=NOW,
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )

    assert first.errors == [f"projection:{identity.run_id}:RuntimeError"]
    committed = await board.get(task.id)
    assert committed is not None and committed.status.value == "completed"
    advanced_metadata = {**committed.metadata, "later_board_advance": True}
    with sqlite3.connect(board._db_path) as db:
        db.execute(
            "UPDATE tasks SET status = 'failed', result = ?, metadata = ?,"
            " updated_at = ? WHERE id = ?",
            (
                "later attempt outcome",
                json.dumps(advanced_metadata),
                (NOW + timedelta(seconds=2)).isoformat(),
                task.id,
            ),
        )
        db.commit()

    monkeypatch.setattr(
        reconcile_board_replay,
        "append_atomic_projection_witness",
        real_import,
    )
    replay = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=replay,
        now=NOW + timedelta(seconds=3),
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )

    assert replay.errors == []
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_atomic_projection_witnesses"
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_acks"
        ).fetchone()[0] == 1


@pytest.mark.parametrize("registry_attack", ["delete", "mismatch"])
async def test_projection_requires_locked_exact_execution_registry(
    runtime,
    tmp_path: Path,
    registry_attack: str,
):
    board, task, identity, _run = await _seed_exact_terminal_projection(
        runtime,
        tmp_path,
        run_id=f"run-registry-{registry_attack}",
    )
    with sqlite3.connect(runtime.db_path) as db:
        if registry_attack == "delete":
            db.execute(
                "DELETE FROM execution_identities WHERE run_id = ?",
                (identity.run_id,),
            )
        else:
            db.execute(
                "UPDATE execution_identities SET trace_id = ? WHERE run_id = ?",
                ("foreign-trace", identity.run_id),
            )
        db.commit()

    report = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=report,
        now=NOW,
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )

    preserved = await board.get(task.id)
    assert report.errors == [f"projection:{identity.run_id}:TaskBoardError"]
    assert preserved is not None and preserved.status.value == "running"
    with sqlite3.connect(board._db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_effect_commits"
        ).fetchone()[0] == 0
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_acks"
        ).fetchone()[0] == 0


async def test_forged_board_local_commit_cannot_witness_projection(
    runtime,
    tmp_path: Path,
):
    from dharma_swarm.graph.reconcile_board_replay import (
        _projection_marker,
        _target_metadata,
    )
    from dharma_swarm.graph.reconcile_board_proof import (
        validate_atomic_graph_projection_commit,
    )
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.task_board_effect_commit import (
        EFFECT_COMMIT_SCHEMA,
        EFFECT_TRANSITION_SCHEMA,
        GRAPH_PROJECTION_EFFECT_KIND,
        GRAPH_PROJECTION_PAYLOAD_SCHEMA,
        graph_projection_effect_id,
    )
    from dharma_swarm.task_board_projection_intent import stable_sha256

    board, task, identity, run = await _seed_exact_terminal_projection(
        runtime,
        tmp_path,
        run_id="run-forged-board-commit",
    )
    current = await board.get(task.id)
    assert current is not None
    intent = run.metadata["task_board_projection_intent"]
    marker = _projection_marker(intent)
    forged_metadata = _target_metadata(current.metadata, intent, marker)
    forged_target = current.model_copy(
        update={
            "status": TaskStatus.COMPLETED,
            "result": intent["result"],
            "metadata": forged_metadata,
            "updated_at": NOW,
        },
        deep=True,
    )
    expected_snapshot = current.model_dump(mode="json")
    target_snapshot = forged_target.model_dump(mode="json")
    payload = {
        "schema_version": GRAPH_PROJECTION_PAYLOAD_SCHEMA,
        "intent_sha256": intent["intent_sha256"],
        "marker": marker,
    }
    effect_id = graph_projection_effect_id(identity.run_id)
    unsigned = {
        "schema_version": EFFECT_COMMIT_SCHEMA,
        "effect_id": effect_id,
        "effect_kind": GRAPH_PROJECTION_EFFECT_KIND,
        "task_id": task.id,
        "authority_sha256": intent["intent_sha256"],
        "expected_snapshot": expected_snapshot,
        "target_snapshot": target_snapshot,
        "effect_payload": payload,
        "committed_at": target_snapshot["updated_at"],
    }
    receipt = {**unsigned, "receipt_sha256": stable_sha256(unsigned)}
    assert validate_atomic_graph_projection_commit(
        receipt,
        intent=intent,
        marker=marker,
    ) == receipt
    canonical = lambda value: json.dumps(  # noqa: E731 - compact corruption fixture
        value, sort_keys=True, separators=(",", ":")
    )
    with sqlite3.connect(board._db_path) as db:
        db.execute(
            "INSERT INTO task_board_effect_commits"
            " (effect_id, effect_kind, task_id, authority_sha256,"
            " expected_snapshot_sha256, expected_snapshot_json,"
            " target_snapshot_sha256, target_snapshot_json,"
            " effect_payload_sha256, effect_payload_json, committed_at,"
            " receipt_sha256, receipt_json, schema_version)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                effect_id,
                GRAPH_PROJECTION_EFFECT_KIND,
                task.id,
                intent["intent_sha256"],
                stable_sha256(expected_snapshot),
                canonical(expected_snapshot),
                stable_sha256(target_snapshot),
                canonical(target_snapshot),
                stable_sha256(payload),
                canonical(payload),
                target_snapshot["updated_at"],
                receipt["receipt_sha256"],
                canonical(receipt),
                EFFECT_COMMIT_SCHEMA,
            ),
        )
        with pytest.raises(
            sqlite3.IntegrityError,
            match="transition lacks task mutation",
        ):
            db.execute(
                "INSERT INTO task_board_effect_transitions"
                " (effect_id, task_id, expected_snapshot_sha256,"
                " target_snapshot_sha256, receipt_sha256, transitioned_at,"
                " schema_version, mutation_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    effect_id,
                    task.id,
                    stable_sha256(expected_snapshot),
                    stable_sha256(target_snapshot),
                    receipt["receipt_sha256"],
                    target_snapshot["updated_at"],
                    EFFECT_TRANSITION_SCHEMA,
                    "tbm_forged_without_task_update",
                ),
            )
        # Even an external writer that removes the insertion guard and forces
        # both formerly sufficient rows into place still lacks the trigger-
        # minted OLD/NEW task mutation consumed by the loader.
        db.execute("DROP TRIGGER task_board_effect_transition_requires_mutation")
        db.execute(
            "INSERT INTO task_board_effect_transitions"
            " (effect_id, task_id, expected_snapshot_sha256,"
            " target_snapshot_sha256, receipt_sha256, transitioned_at,"
            " schema_version, mutation_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                effect_id,
                task.id,
                stable_sha256(expected_snapshot),
                stable_sha256(target_snapshot),
                receipt["receipt_sha256"],
                target_snapshot["updated_at"],
                EFFECT_TRANSITION_SCHEMA,
                "tbm_forged_without_task_update",
            ),
        )
        db.commit()

    report = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=report,
        now=NOW + timedelta(seconds=1),
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )

    assert report.errors == [f"projection:{identity.run_id}:ValueError"]
    assert (await board.get(task.id)).status.value == "running"
    with sqlite3.connect(board._db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_effect_transitions"
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_effect_mutations"
        ).fetchone()[0] == 0
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_atomic_projection_witnesses"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_acks"
        ).fetchone()[0] == 0


async def test_forged_projection_cannot_terminalize_running_task(
    runtime,
    tmp_path: Path,
):
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.task_board_projection_intent import stable_sha256

    board, task, identity, _run = await _seed_exact_terminal_projection(
        runtime,
        tmp_path,
        run_id="run-forged-intent",
        result="durable original",
    )
    forged_result = "forged terminal value"
    with sqlite3.connect(runtime.db_path) as db:
        raw = db.execute(
            "SELECT metadata_json FROM delegation_runs WHERE run_id = ?",
            (identity.run_id,),
        ).fetchone()[0]
        metadata = json.loads(raw)
        intent = metadata["task_board_projection_intent"]
        intent["result"] = forged_result
        intent["result_sha256"] = hashlib.sha256(forged_result.encode()).hexdigest()
        intent["completion_binding"]["result_sha256"] = intent["result_sha256"]
        intent["intent_sha256"] = stable_sha256(
            {key: value for key, value in intent.items() if key != "intent_sha256"}
        )
        db.execute(
            "UPDATE delegation_runs SET metadata_json = ? WHERE run_id = ?",
            (json.dumps(metadata), identity.run_id),
        )
        db.commit()

    report = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=report,
        now=NOW,
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )

    preserved = await board.get(task.id)
    assert preserved is not None and preserved.status is TaskStatus.RUNNING
    assert report.errors
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_acks"
        ).fetchone()[0] == 0


async def test_pending_projection_without_board_fences_readiness(
    runtime,
    tmp_path: Path,
):
    _board, _task, identity, _run = await _seed_exact_terminal_projection(
        runtime,
        tmp_path,
        run_id="run-board-unavailable",
    )
    reconciler = GraphReconciler(runtime, task_board=None)

    report = await reconciler.reconcile(now=NOW)

    assert report.errors == [
        f"projection:{identity.run_id}:task_board_unavailable"
    ]
    assert reconciler.boot_census_succeeded is False


async def test_success_projection_cannot_synthesize_result_from_witness(
    runtime,
    tmp_path: Path,
):
    with pytest.raises(RuntimeError, match="projection prepare failed"):
        await _seed_exact_terminal_projection(
            runtime,
            tmp_path,
            run_id="run-synthetic-success",
            result="witness value",
            durable_result="different durable value",
        )


async def test_failed_projection_requires_exact_non_none_error_source(
    runtime,
    tmp_path: Path,
):
    with pytest.raises(RuntimeError, match="projection prepare failed"):
        await _seed_exact_terminal_projection(
            runtime,
            tmp_path,
            run_id="run-source-less-failure",
            status="failed",
            result="provider failed",
            error_source="none",
        )


# ---------------------------------------------------------------------------
# V4 owner selection and campaign readiness
# ---------------------------------------------------------------------------


async def test_foreign_runtime_owner_is_untouched_and_fences_readiness(runtime):
    identity = ExecutionIdentity(
        trace_id="trace-foreign",
        correlation_id="correlation-foreign",
        task_id="task-foreign",
        run_id="run-foreign",
        claim_id="claim-foreign",
        idempotency_key="dispatch-foreign",
        agent_id="agent-foreign",
        session_id="session-foreign",
    )
    metadata = _canonical_runtime_metadata(identity)
    _insert_run(
        runtime,
        identity.run_id,
        claim_id=identity.claim_id,
        task_id=identity.task_id,
        assigned_to=identity.agent_id,
        assigned_by="foreign-scheduler",
        session_id=identity.session_id,
        metadata=metadata,
        legacy_compatibility=False,
    )
    _insert_claim(
        runtime,
        identity.claim_id,
        task_id=identity.task_id,
        agent_id=identity.agent_id,
        session_id=identity.session_id,
        stale_after=(NOW - timedelta(minutes=1)).isoformat(),
        metadata=metadata,
        legacy_compatibility=False,
    )
    reconciler = GraphReconciler(runtime)

    report = await reconciler.reconcile(now=NOW)

    assert _get_run(runtime, identity.run_id)["status"] == "running"
    assert _get_claim(runtime, identity.claim_id)["status"] == "running"
    assert report.total_reconciled == 0
    assert report.errors
    assert reconciler.boot_census_succeeded is False


async def test_foreign_owner_cannot_opt_into_legacy_mutation(runtime):
    _insert_run(
        runtime,
        "run-foreign-legacy-flags",
        claim_id="claim-foreign-legacy-flags",
        assigned_by="foreign-scheduler",
    )
    _insert_claim(
        runtime,
        "claim-foreign-legacy-flags",
        stale_after=(NOW - timedelta(minutes=1)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert _get_run(runtime, "run-foreign-legacy-flags")["status"] == "running"
    assert _get_claim(runtime, "claim-foreign-legacy-flags")["status"] == "running"
    assert report.requeued_runs == []
    assert report.errors


async def test_orchestrator_owner_with_incomplete_identity_is_untouched(runtime):
    _insert_run(
        runtime,
        "run-incomplete-owner",
        claim_id="claim-incomplete-owner",
        task_id="task-incomplete-owner",
        assigned_by="orchestrator",
        metadata={"trace_id": "trace-only"},
        legacy_compatibility=False,
    )
    _insert_claim(
        runtime,
        "claim-incomplete-owner",
        task_id="task-incomplete-owner",
        stale_after=(NOW - timedelta(minutes=1)).isoformat(),
        legacy_compatibility=False,
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert _get_run(runtime, "run-incomplete-owner")["status"] == "running"
    assert _get_claim(runtime, "claim-incomplete-owner")["status"] == "running"
    assert "run:run-incomplete-owner:unknown_runtime_owner" in report.errors


async def test_canonical_run_rejects_forged_claim_identity(runtime):
    identity = ExecutionIdentity(
        trace_id="trace-forged-claim",
        correlation_id="correlation-forged-claim",
        task_id="task-forged-claim",
        run_id="run-forged-claim",
        claim_id="claim-forged-claim",
        idempotency_key="dispatch-forged-claim",
        agent_id="agent-forged-claim",
        session_id="session-forged-claim",
    )
    await runtime.record_task_claim(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            session_id=identity.session_id,
            status="running",
            stale_after=NOW - timedelta(minutes=1),
            metadata=identity.to_metadata(),
        )
    )
    await runtime.record_delegation_run(
        DelegationRun(
            run_id=identity.run_id,
            task_id=identity.task_id,
            assigned_to=identity.agent_id,
            session_id=identity.session_id,
            claim_id=identity.claim_id,
            assigned_by="orchestrator",
            status="running",
            metadata=identity.to_metadata(),
        )
    )
    with sqlite3.connect(runtime.db_path) as db:
        raw = db.execute(
            "SELECT metadata_json FROM task_claims WHERE claim_id = ?",
            (identity.claim_id,),
        ).fetchone()[0]
        metadata = json.loads(raw)
        metadata["execution_identity"]["session_id"] = "forged-session"
        db.execute(
            "UPDATE task_claims SET metadata_json = ? WHERE claim_id = ?",
            (json.dumps(metadata), identity.claim_id),
        )
        db.commit()

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert _get_run(runtime, identity.run_id)["status"] == "running"
    assert _get_claim(runtime, identity.claim_id)["status"] == "running"
    assert any("attempt_identity_mismatch" in item for item in report.errors)


async def test_malformed_board_campaign_namespace_fences_generic_recovery(
    runtime,
    tmp_path: Path,
):
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / "malformed-board-campaign.db")
    await board.init_db()
    task = await board.create("malformed Board campaign authority")
    with sqlite3.connect(board._db_path) as db:
        db.execute(
            "UPDATE tasks SET status = 'running', assigned_to = 'agent-1',"
            " metadata = ? WHERE id = ?",
            (json.dumps({"mission_campaign_authority": {}}), task.id),
        )
        db.commit()
    _insert_run(
        runtime,
        "run-malformed-board-campaign",
        claim_id="claim-malformed-board-campaign",
        task_id=task.id,
    )
    _insert_claim(
        runtime,
        "claim-malformed-board-campaign",
        task_id=task.id,
        stale_after=(NOW - timedelta(minutes=1)).isoformat(),
    )

    report = await GraphReconciler(runtime, task_board=board).reconcile(now=NOW)

    preserved = await board.get(task.id)
    assert preserved is not None and preserved.status is TaskStatus.RUNNING
    assert _get_run(runtime, "run-malformed-board-campaign")["status"] == "running"
    assert report.requeued_runs == []
    assert report.errors


async def test_malformed_campaign_fence_never_falls_into_generic_recovery(runtime):
    identity = ExecutionIdentity(
        trace_id="trace-malformed-fence",
        correlation_id="correlation-malformed-fence",
        task_id="task-malformed-fence",
        run_id="run-malformed-fence",
        claim_id="claim-malformed-fence",
        idempotency_key="dispatch-malformed-fence",
        agent_id="agent-malformed-fence",
        session_id="session-malformed-fence",
    )
    malformed = {
        "campaign_runtime_recovery_fence": {
            "schema_version": "dharma.sadhana.campaign_runtime_recovery_fence.v1",
            "task_id": identity.task_id,
        }
    }
    metadata = _canonical_runtime_metadata(identity, malformed)
    _insert_run(
        runtime,
        identity.run_id,
        claim_id=identity.claim_id,
        task_id=identity.task_id,
        assigned_to=identity.agent_id,
        assigned_by="orchestrator",
        session_id=identity.session_id,
        metadata=metadata,
        legacy_compatibility=False,
    )
    _insert_claim(
        runtime,
        identity.claim_id,
        task_id=identity.task_id,
        agent_id=identity.agent_id,
        session_id=identity.session_id,
        stale_after=(NOW - timedelta(minutes=1)).isoformat(),
        metadata=metadata,
        legacy_compatibility=False,
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert _get_run(runtime, identity.run_id)["status"] == "running"
    assert _get_claim(runtime, identity.claim_id)["status"] == "running"
    assert any("malformed_runtime_recovery_fence" in item for item in report.errors)
    assert report.requeued_runs == []
    assert report.quarantined_runs == []


async def test_boot_census_fails_closed_on_unbound_campaign_claim(
    runtime,
    tmp_path: Path,
):
    from dharma_swarm.mission_control_executor_guard import campaign_principal
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / "unbound-campaign-tasks.db")
    await board.init_db()
    task = await board.create("campaign claim without canonical run")
    identity = ExecutionIdentity(
        trace_id="trace-unbound-campaign",
        correlation_id="correlation-unbound-campaign",
        task_id=task.id,
        run_id="run-missing-campaign",
        claim_id="claim-unbound-campaign",
        idempotency_key="dispatch-unbound-campaign",
        agent_id="campaign-agent",
        session_id="campaign-session",
    )
    campaign = _validated_campaign_metadata(identity.agent_id, task.id)
    board_metadata = {
        **_canonical_runtime_metadata(identity),
        "runtime_db_path": str(runtime.db_path),
        **campaign,
    }
    with sqlite3.connect(board._db_path) as db:
        db.execute(
            "UPDATE tasks SET status = 'running', assigned_to = ?, metadata = ?"
            " WHERE id = ?",
            (identity.agent_id, json.dumps(board_metadata), task.id),
        )
        db.commit()
    await runtime.record_task_claim(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            session_id=identity.session_id,
            status="running",
            stale_after=NOW + timedelta(minutes=30),
            metadata={
                **identity.to_metadata(),
                **_campaign_fence(
                    identity,
                    campaign["mission_campaign_authority"],
                ),
            },
        )
    )
    assert campaign_principal(await board.get(task.id)) == (True, identity.agent_id)
    reconciler = GraphReconciler(runtime, task_board=board)

    report = await reconciler.reconcile(now=NOW)

    assert report.errors == [
        f"campaign_claim:{identity.claim_id}:missing_canonical_run",
        f"board_only_campaign:{task.id}:malformed_campaign_shape:effect_indeterminate",
    ]
    assert _get_claim(runtime, identity.claim_id)["status"] == "running"
    assert reconciler.boot_census_succeeded is False


async def test_periodic_reconcile_does_not_hold_live_campaign_claim(
    runtime,
    tmp_path: Path,
):
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / "live-campaign-tasks.db")
    await board.init_db()
    reconciler = GraphReconciler(runtime, task_board=board)
    boot = await reconciler.reconcile(now=NOW - timedelta(hours=1))
    assert boot.errors == [] and reconciler.boot_census_succeeded
    board, _task, identity, _claim, _run = await _seed_running_campaign(
        runtime,
        tmp_path,
        run_id="run-campaign-live",
        stale=False,
        board=board,
    )
    report = await reconciler.reconcile(now=NOW, stale_only=True)

    run_metadata = json.loads(_get_run(runtime, identity.run_id)["metadata_json"])
    claim_metadata = json.loads(
        _get_claim(runtime, identity.claim_id)["metadata_json"]
    )
    assert report.errors == []
    assert "campaign_recovery_hold" not in run_metadata
    assert "campaign_recovery_hold" not in claim_metadata
    assert reconciler.boot_census_succeeded is True
    assert reconciler.heartbeat_live_claims(now=NOW) == 1


@pytest.mark.parametrize("registry_corruption", ["delete", "mismatch"])
async def test_campaign_heartbeat_requires_exact_identity_registry_row(
    runtime,
    tmp_path: Path,
    registry_corruption: str,
):
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / f"registry-{registry_corruption}-tasks.db")
    await board.init_db()
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(hours=1))).errors == []
    board, _task, identity, _claim, _run = await _seed_running_campaign(
        runtime,
        tmp_path,
        run_id=f"run-registry-{registry_corruption}",
        stale=False,
        board=board,
    )
    with sqlite3.connect(runtime.db_path) as db:
        if registry_corruption == "delete":
            db.execute(
                "DELETE FROM execution_identities WHERE run_id = ?",
                (identity.run_id,),
            )
        else:
            db.execute(
                "UPDATE execution_identities SET trace_id = ? WHERE run_id = ?",
                ("trace-conflicting-registry-row", identity.run_id),
            )
        db.commit()
    previous = _get_claim(runtime, identity.claim_id)["heartbeat_at"]

    with pytest.raises(ClaimHeartbeatError, match="authority is incomplete"):
        reconciler.heartbeat_live_claims(now=NOW)

    assert _get_claim(runtime, identity.claim_id)["heartbeat_at"] == previous
    assert reconciler.boot_census_succeeded is False


async def test_campaign_heartbeat_observes_board_change_inside_writer_fence(
    runtime,
    tmp_path: Path,
    monkeypatch,
):
    from dharma_swarm.graph import reconcile_board_campaign
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / "heartbeat-board-fence-tasks.db")
    await board.init_db()
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(hours=1))).errors == []
    board, task, identity, _claim, _run = await _seed_running_campaign(
        runtime,
        tmp_path,
        run_id="run-heartbeat-board-fence",
        stale=False,
        board=board,
    )
    previous = _get_claim(runtime, identity.claim_id)["heartbeat_at"]
    snapshot = reconcile_board_campaign._board_attempt_snapshots_locked

    def advance_generation_before_snapshot(board_db, task_ids):
        assert board_db is not None and board_db.in_transaction
        raw = board_db.execute(
            "SELECT metadata FROM tasks WHERE id = ?", (task.id,)
        ).fetchone()[0]
        metadata = json.loads(raw)
        metadata["mission_campaign_authority"]["attempt_generation"] = 1
        board_db.execute(
            "UPDATE tasks SET metadata = ? WHERE id = ?",
            (json.dumps(metadata), task.id),
        )
        return snapshot(board_db, task_ids)

    monkeypatch.setattr(
        reconcile_board_campaign,
        "_board_attempt_snapshots_locked",
        advance_generation_before_snapshot,
    )

    with pytest.raises(ClaimHeartbeatError, match="Board attempt changed"):
        reconciler.heartbeat_live_claims(now=NOW)

    assert _get_claim(runtime, identity.claim_id)["heartbeat_at"] == previous
    assert reconciler.boot_census_succeeded is False


async def test_malformed_campaign_hold_key_does_not_suppress_generic_heartbeat(
    runtime,
):
    reconciler = GraphReconciler(runtime)
    await reconciler.reconcile(now=NOW - timedelta(hours=1))
    identity = ExecutionIdentity(
        trace_id="trace-malformed-hold",
        correlation_id="correlation-malformed-hold",
        task_id="task-malformed-hold",
        run_id="run-malformed-hold",
        claim_id="claim-malformed-hold",
        idempotency_key="dispatch-malformed-hold",
        agent_id="agent-malformed-hold",
        session_id="session-malformed-hold",
    )
    malformed_hold = {
        "campaign_recovery_hold": {
            "schema_version": "dharma.sadhana.campaign_recovery_hold.v1",
            "state": "effect_indeterminate",
            "retry_authorized": False,
            "cessation_proven": False,
            "observed_at": NOW.isoformat(),
            "task_id": identity.task_id,
            "claim_id": identity.claim_id,
            "run_id": "",
        }
    }
    metadata = {**identity.to_metadata(), **malformed_hold}
    await runtime.record_task_claim(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            session_id=identity.session_id,
            status="running",
            claimed_at=NOW - timedelta(minutes=30),
            heartbeat_at=NOW - timedelta(minutes=21),
            stale_after=NOW + timedelta(minutes=30),
            metadata=metadata,
        )
    )
    await runtime.record_delegation_run(
        DelegationRun(
            run_id=identity.run_id,
            task_id=identity.task_id,
            assigned_to=identity.agent_id,
            session_id=identity.session_id,
            claim_id=identity.claim_id,
            assigned_by="orchestrator",
            status="running",
            metadata=metadata,
        )
    )

    assert reconciler.heartbeat_live_claims(now=NOW) == 1
    assert _get_claim(runtime, identity.claim_id)["heartbeat_at"] == NOW.isoformat()


async def test_foreign_owner_claim_is_never_heartbeated(runtime):
    reconciler = GraphReconciler(runtime)
    await reconciler.reconcile(now=NOW - timedelta(hours=1))
    identity = ExecutionIdentity(
        trace_id="trace-foreign-heartbeat",
        correlation_id="correlation-foreign-heartbeat",
        task_id="task-foreign-heartbeat",
        run_id="run-foreign-heartbeat",
        claim_id="claim-foreign-heartbeat",
        idempotency_key="dispatch-foreign-heartbeat",
        agent_id="agent-foreign-heartbeat",
        session_id="session-foreign-heartbeat",
    )
    metadata = _canonical_runtime_metadata(identity)
    _insert_run(
        runtime,
        identity.run_id,
        claim_id=identity.claim_id,
        task_id=identity.task_id,
        assigned_to=identity.agent_id,
        assigned_by="foreign-scheduler",
        session_id=identity.session_id,
        metadata=metadata,
        legacy_compatibility=False,
    )
    previous = (NOW - timedelta(minutes=21)).isoformat()
    _insert_claim(
        runtime,
        identity.claim_id,
        task_id=identity.task_id,
        agent_id=identity.agent_id,
        session_id=identity.session_id,
        claimed_at=(NOW - timedelta(minutes=30)).isoformat(),
        heartbeat_at=previous,
        stale_after=(NOW + timedelta(minutes=30)).isoformat(),
        metadata=metadata,
        legacy_compatibility=False,
    )

    with pytest.raises(ClaimHeartbeatError, match="runtime owner is unknown"):
        reconciler.heartbeat_live_claims(now=NOW)
    assert _get_claim(runtime, identity.claim_id)["heartbeat_at"] == previous
    assert reconciler.boot_census_succeeded is False


async def test_board_only_campaign_authority_never_heartbeats_as_ordinary(
    runtime,
    tmp_path: Path,
):
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / "board-only-campaign-tasks.db")
    await board.init_db()
    reconciler = GraphReconciler(runtime, task_board=board)
    await reconciler.reconcile(now=NOW - timedelta(hours=1))
    _board, _task, identity, _claim, _run = await _seed_running_campaign(
        runtime,
        tmp_path,
        run_id="run-board-only-campaign",
        stale=False,
        board=board,
    )
    with sqlite3.connect(runtime.db_path) as db:
        for table, key in (
            ("delegation_runs", "run_id"),
            ("task_claims", "claim_id"),
        ):
            identifier = identity.run_id if key == "run_id" else identity.claim_id
            raw = db.execute(
                f"SELECT metadata_json FROM {table} WHERE {key} = ?",
                (identifier,),
            ).fetchone()[0]
            metadata = json.loads(raw)
            metadata.pop("campaign_runtime_recovery_fence", None)
            db.execute(
                f"UPDATE {table} SET metadata_json = ? WHERE {key} = ?",
                (json.dumps(metadata), identifier),
            )
        db.commit()
    previous = _get_claim(runtime, identity.claim_id)["heartbeat_at"]

    with pytest.raises(ClaimHeartbeatError, match="surface is incomplete"):
        reconciler.heartbeat_live_claims(now=NOW)

    assert _get_claim(runtime, identity.claim_id)["heartbeat_at"] == previous
    assert reconciler.boot_census_succeeded is False


async def test_late_bound_receipt_resolves_campaign_hold_and_board(
    runtime,
    tmp_path: Path,
):
    from dharma_swarm.models import TaskStatus

    board, task, identity, _claim, _run = await _seed_running_campaign(
        runtime,
        tmp_path,
        run_id="run-campaign-late",
        stale=True,
    )
    reconciler = GraphReconciler(runtime, task_board=board)

    first = await reconciler.reconcile(now=NOW)
    assert any("effect_indeterminate" in item for item in first.errors)
    assert "campaign_recovery_hold" in json.loads(
        _get_run(runtime, identity.run_id)["metadata_json"]
    )

    result = "late exact campaign receipt"
    _attach_exact_runtime_receipt(runtime, identity, result=result)
    second = await reconciler.reconcile(now=NOW + timedelta(minutes=1))

    projected = await board.get(task.id)
    assert second.errors == []
    assert second.completed_from_receipt == [identity.run_id]
    assert projected is not None and projected.status is TaskStatus.COMPLETED
    assert projected.result == result
    assert "campaign_recovery_hold" not in json.loads(
        _get_run(runtime, identity.run_id)["metadata_json"]
    )


async def test_heartbeated_claim_past_stale_after_not_stale(runtime):
    _insert_run(runtime, "run-hb", status="running", claim_id="claim-hb")
    _insert_claim(
        runtime,
        "claim-hb",
        status="running",
        acked_at=(NOW - timedelta(minutes=20)).isoformat(),
        claimed_at=(NOW - timedelta(minutes=20)).isoformat(),
        stale_after=(NOW - timedelta(minutes=5)).isoformat(),
        heartbeat_at=(NOW - timedelta(seconds=30)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW, stale_only=True)

    assert report.total_reconciled == 0
    assert _get_run(runtime, "run-hb")["status"] == "running"
    assert _get_claim(runtime, "claim-hb")["recovered_at"] is None


# ---------------------------------------------------------------------------
# Heartbeat wiring
# ---------------------------------------------------------------------------


async def test_heartbeat_live_claims_beats_due_claims(runtime):
    stale = NOW + timedelta(minutes=20)  # window = 10 min
    _insert_run(runtime, "run-due", status="running", claim_id="claim-due")
    _insert_run(runtime, "run-recent", status="running", claim_id="claim-recent")
    _insert_claim(
        runtime,
        "claim-due",
        status="running",
        stale_after=stale.isoformat(),
        heartbeat_at=(NOW - timedelta(minutes=11)).isoformat(),
    )
    _insert_claim(
        runtime,
        "claim-recent",
        status="running",
        stale_after=stale.isoformat(),
        heartbeat_at=(NOW - timedelta(seconds=10)).isoformat(),
    )
    _insert_claim(
        runtime,
        "claim-recovered",
        status="running",
        stale_after=stale.isoformat(),
        recovered_at=NOW.isoformat(),
    )

    reconciler = GraphReconciler(runtime)
    reconciler._boot_recovery_completed = True
    await reconciler.reconcile(now=NOW, stale_only=True)
    beaten = reconciler.heartbeat_live_claims(now=NOW)

    assert beaten == 1
    due = _get_claim(runtime, "claim-due")
    assert due["heartbeat_at"] != (NOW - timedelta(minutes=11)).isoformat()
    recent = _get_claim(runtime, "claim-recent")
    assert recent["heartbeat_at"] == (NOW - timedelta(seconds=10)).isoformat()


async def test_heartbeat_refuses_ownerless_legacy_claim(runtime):
    stale = NOW + timedelta(minutes=20)
    old_heartbeat = (NOW - timedelta(minutes=11)).isoformat()
    _insert_claim(
        runtime,
        "claim-ownerless",
        status="running",
        stale_after=stale.isoformat(),
        heartbeat_at=old_heartbeat,
    )
    reconciler = GraphReconciler(runtime)
    reconciler._boot_recovery_completed = True
    await reconciler.reconcile(now=NOW, stale_only=True)

    with pytest.raises(ClaimHeartbeatError, match="owner is unknown"):
        reconciler.heartbeat_live_claims(now=NOW)

    assert reconciler.boot_census_succeeded is False
    assert _get_claim(runtime, "claim-ownerless")["heartbeat_at"] == old_heartbeat


async def test_heartbeat_rejects_run_inserted_after_census(
    runtime,
    monkeypatch,
):
    from dharma_swarm.graph import reconcile_board_campaign

    old_heartbeat = (NOW - timedelta(minutes=11)).isoformat()
    _insert_run(runtime, "run-first", status="running", claim_id="claim-race")
    _insert_claim(
        runtime,
        "claim-race",
        status="running",
        stale_after=(NOW + timedelta(minutes=20)).isoformat(),
        heartbeat_at=old_heartbeat,
    )
    reconciler = GraphReconciler(runtime)
    reconciler._boot_recovery_completed = True
    await reconciler.reconcile(now=NOW, stale_only=True)
    original_snapshot = reconcile_board_campaign._board_attempt_snapshots_locked
    inserted = False

    def _insert_duplicate_after_runtime_read(board_db, task_ids):
        nonlocal inserted
        snapshots = original_snapshot(board_db, task_ids)
        if not inserted:
            inserted = True
            _insert_run(
                runtime,
                "run-second",
                status="running",
                claim_id="claim-race",
            )
        return snapshots

    monkeypatch.setattr(
        reconcile_board_campaign,
        "_board_attempt_snapshots_locked",
        _insert_duplicate_after_runtime_read,
    )

    with pytest.raises(ClaimHeartbeatError, match="changed after census"):
        reconciler.heartbeat_live_claims(now=NOW)

    assert reconciler.boot_census_succeeded is False
    assert _get_claim(runtime, "claim-race")["heartbeat_at"] == old_heartbeat


def test_reconcile_report_summary_shape():
    report = ReconcileReport(requeued_runs=["a"], quarantined_runs=["b", "c"])
    assert report.total_reconciled == 3
    assert report.summary() == {
        "requeued_runs": 1,
        "quarantined_runs": 2,
        "completed_from_receipt": 0,
        "recovered_claims": 0,
        "errors": 0,
    }


# ---------------------------------------------------------------------------
# Boot ordering: reconciler must settle receipted runs BEFORE the stale reaper
# ---------------------------------------------------------------------------


def test_init_reconciles_before_stale_reaper_source_order():
    import inspect

    from dharma_swarm.swarm import SwarmManager

    src = inspect.getsource(SwarmManager.init)
    assert src.index("reconcile_graph_runs") < src.index("_reap_stale_running_tasks"), (
        "boot reconcile must run before the stale-task reaper"
    )


async def test_boot_sequence_receipted_crash_task_ends_completed(
    runtime, tmp_path: Path
):
    """Crash + stale RUNNING task + success receipt -> board ends COMPLETED.

    Replays the SwarmManager.init() boot sequence (reconcile, then stale
    reaper): the receipt settles the board task COMPLETED first, so the
    reaper never board-FAILs it and runtime truth matches the board.
    """
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.swarm import SwarmManager
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / "tasks.db")
    await board.init_db()
    task = await board.create("crashed task with persisted success receipt")
    stale = datetime.now(timezone.utc) - timedelta(hours=7)
    board_metadata = {
        "run_id": "run-order",
        "runtime_run_id": "run-order",
        "claim_id": "claim-order",
        "agent_id": "agent-1",
        "active_claim": {
            "claim_id": "claim-order",
            "agent_id": "agent-1",
            "claimed_at": (NOW - timedelta(minutes=10)).isoformat(),
        },
    }
    async with board._open() as db:
        await db.execute(
            "UPDATE tasks SET status = 'running', assigned_to = ?, metadata = ?,"
            " updated_at = ? WHERE id = ?",
            (
                "agent-1",
                json.dumps(board_metadata),
                stale.isoformat(),
                task.id,
            ),
        )
        await db.commit()

    _insert_run(
        runtime,
        "run-order",
        status="running",
        claim_id="claim-order",
        task_id=task.id,
        receipt_json=_bound_receipt(
            runtime, run_id="run-order", claim_id="claim-order", task_id=task.id
        ),
    )
    _insert_claim(runtime, "claim-order", status="running", task_id=task.id)

    sm = SwarmManager(state_dir=tmp_path / ".dharma")
    sm._task_board = board
    sm._graph_reconciler = GraphReconciler(runtime, task_board=board)

    await sm.reconcile_graph_runs()
    await sm._reap_stale_running_tasks()

    refreshed = await board.get(task.id)
    assert refreshed is not None
    assert refreshed.status == TaskStatus.COMPLETED
