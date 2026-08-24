"""Regression fixtures for the Board-commit/runtime-create crash window."""

from __future__ import annotations

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

from dharma_swarm.graph.reconcile_board_intent import (
    build_task_board_completion_binding,
    prepare_task_board_projection_snapshot,
    terminal_task_board_projection_metadata,
)
from dharma_swarm.graph.reconcile_board_only import (
    BOARD_ONLY_HOLD_TABLE,
    BOARD_ONLY_LINEAGE_TABLE,
    BOARD_ONLY_RESOLUTION_TABLE,
)
from dharma_swarm.graph.reconcile_board_replay import settle_task_board
from dharma_swarm.graph.reconciler import GraphReconciler, ReconcileReport
from dharma_swarm.mission_control_executor_guard import campaign_principal
from dharma_swarm.mission_control_task_attempts import (
    GOVERNANCE_SCHEMA_V4,
    _GOVERNANCE_FIELDS,
)
from dharma_swarm.models import TaskStatus
from dharma_swarm.runtime_lifecycle_identity import valid_board_campaign_authority
from dharma_swarm.runtime_state import DelegationRun, RuntimeStateStore, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard
from dharma_swarm.task_board_effect_commit import (
    NON_PRODUCTION_PROJECTION_COMMIT_MODE,
)
from dharma_swarm.task_board_campaign_guard import runtime_campaign_fence_metadata
from dharma_swarm.task_board_projection_intent import GRAPH_PROJECTION_KEY

NOW = datetime(2026, 8, 24, 0, 42, tzinfo=timezone.utc)


def _exact_campaign_metadata(
    *,
    task_id: str,
    runtime_path: Path,
) -> tuple[dict, ExecutionIdentity]:
    principal = "campaign-seat"
    identity = ExecutionIdentity(
        trace_id="trace-board-only",
        correlation_id="correlation-board-only",
        task_id=task_id,
        run_id="run-board-only",
        claim_id="claim-board-only",
        idempotency_key="dispatch-board-only",
        agent_id=principal,
        session_id="session-board-only",
        metadata={"source": "board_only_crash_fixture"},
    )
    campaign_id = "campaign-board-only"
    goal_id = "goal-board-only"
    portfolio = "sha256:" + "a" * 64
    goal = "sha256:" + "b" * 64
    observed_content = "Observed Board-only recovery fixture; verify independently.\n"
    content_sha256 = "sha256:" + hashlib.sha256(observed_content.encode()).hexdigest()
    observed_manifest = "sha256:" + "3" * 64
    observed_ref = {
        "receipt_id": "observed-board-only-receipt",
        "receipt_sha256": "sha256:" + "4" * 64,
        "artifact_id": "observed-board-only-artifact",
        "artifact_record_sha256": "sha256:" + "5" * 64,
        "content_sha256": content_sha256,
    }
    authority = {
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
        "agent_name": principal,
        "claimed_principal": principal,
        "dispatch_key": "default",
        "request_id": "request-board-only",
        "workspace_path": "workspaces/goal-board-only",
        "allowed_files": ["workspaces/goal-board-only/**"],
        "max_usd": 0.0,
        "authority_ref": "lease-board-only",
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
    }
    owner = {
        "schema_version": "dharma.mission_control.owner_execution.v2",
        "backend": "orchestrator",
        "mission_id": campaign_id,
        "task_id": task_id,
        "dispatch_key": authority["dispatch_key"],
        "attempt_generation": 0,
        "run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "idempotency_key": identity.idempotency_key,
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
    }
    metadata = {
        **identity.to_metadata(),
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "task_id": identity.task_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "idempotency_key": identity.idempotency_key,
        "runtime_db_path": str(runtime_path),
        "active_claim": {
            "claim_id": identity.claim_id,
            "agent_id": identity.agent_id,
        },
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
            "content": observed_content,
            "content_sha256": content_sha256,
            "observed_input_ref": observed_ref,
        },
        "campaign_effect_mode": "read_only",
        "requires_tooling": False,
        "allow_provider_routing": False,
        "provider_allowlist": ["local"],
        "preferred_provider": "local",
        "preferred_model": "fixture-model",
        "mission_campaign_authority": authority,
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
    return metadata, identity


def _ordinary_owner_metadata(task_id: str) -> dict:
    identity = ExecutionIdentity(
        trace_id="trace-ordinary",
        correlation_id="correlation-ordinary",
        task_id=task_id,
        run_id="run-ordinary",
        claim_id="claim-ordinary",
        idempotency_key="dispatch-ordinary",
        agent_id="ordinary-seat",
        session_id="session-ordinary",
    )
    return {
        **identity.to_metadata(),
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "task_id": identity.task_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "agent_id": identity.agent_id,
        "session_id": identity.session_id,
        "idempotency_key": identity.idempotency_key,
        "mission_control_owner_execution": {
            "schema_version": "dharma.mission_control.owner_execution.v1",
            "backend": "orchestrator",
            "mission_id": "ordinary-mission",
            "task_id": task_id,
            "dispatch_key": "default",
            "run_id": identity.run_id,
            "idempotency_key": identity.idempotency_key,
            "trace_id": identity.trace_id,
            "correlation_id": identity.correlation_id,
        },
    }


async def _stores(tmp_path: Path) -> tuple[RuntimeStateStore, TaskBoard]:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    await runtime.init_db()
    board = TaskBoard(tmp_path / "tasks.db")
    await board.init_db()
    return runtime, board


def _force_board_state(
    board: TaskBoard,
    *,
    task_id: str,
    status: str,
    assigned_to: str,
    metadata: dict,
) -> None:
    with sqlite3.connect(board._db_path) as db:
        db.execute(
            "UPDATE tasks SET status = ?, assigned_to = ?, metadata = ?, updated_at = ?"
            " WHERE id = ?",
            (status, assigned_to, json.dumps(metadata), NOW.isoformat(), task_id),
        )
        db.commit()


def _runtime_authority_counts(runtime: RuntimeStateStore) -> dict[str, int]:
    tables = (
        "task_claims",
        "delegation_runs",
        "execution_identities",
        "runtime_receipts",
        "idempotency_records",
    )
    with sqlite3.connect(runtime.db_path) as db:
        return {
            table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }


def _runtime_metadata(metadata: dict, identity: ExecutionIdentity) -> dict:
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
        **runtime_campaign_fence_metadata(identity.task_id, metadata),
    }


async def _seed_live_runtime_attempt(
    runtime: RuntimeStateStore,
    *,
    metadata: dict,
    identity: ExecutionIdentity,
) -> None:
    runtime_metadata = _runtime_metadata(metadata, identity)
    await runtime.record_execution_identity(identity, source="late_exact_test")
    await runtime.record_task_claim(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            session_id=identity.session_id,
            status="running",
            claimed_at=NOW,
            acked_at=NOW,
            heartbeat_at=NOW,
            stale_after=NOW + timedelta(minutes=30),
            metadata=runtime_metadata,
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
            started_at=NOW,
            metadata=runtime_metadata,
        )
    )


async def _seed_terminal_runtime_projection(
    runtime: RuntimeStateStore,
    *,
    metadata: dict,
    identity: ExecutionIdentity,
    result: str,
) -> None:
    receipt_id = str(uuid4())
    side_effect_key = f"invoke_agent:{identity.task_id}:{identity.agent_id}"
    dispatch = SimpleNamespace(
        task_id=identity.task_id,
        agent_id=identity.agent_id,
        metadata={
            "execution_identity": identity.to_dict(),
            "evidence_receipt_id": receipt_id,
        },
    )
    binding = build_task_board_completion_binding(dispatch, result=result)
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
            "idempotency_key": binding["idempotency_key"],
            "dispatch_idempotency_key": identity.idempotency_key,
            "side_effect_key": side_effect_key,
        },
    }
    with sqlite3.connect(runtime.db_path) as db:
        db.execute(
            "INSERT INTO idempotency_records"
            " (idempotency_key, side_effect_key, run_id, task_id, trace_id,"
            " correlation_id, status, result_receipt_id, metadata_json, created_at,"
            " updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                binding["idempotency_key"],
                side_effect_key,
                identity.run_id,
                identity.task_id,
                identity.trace_id,
                identity.correlation_id,
                "completed",
                receipt_id,
                json.dumps(
                    {
                        "operation_hash": hashlib.sha256(
                            side_effect_key.encode()
                        ).hexdigest(),
                        "task_id": identity.task_id,
                        "receipt": receipt,
                        "result_json": json.dumps(result),
                    }
                ),
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        db.commit()
    runtime_metadata = {
        **_runtime_metadata(metadata, identity),
        "status": "completed",
        "error": "",
    }
    runtime_metadata = terminal_task_board_projection_metadata(
        runtime_metadata,
        task_id=identity.task_id,
        run_id=identity.run_id,
        run_status="completed",
        board_result=result,
        completion_binding=binding,
        now=NOW,
        source="test_graph_board_only_recovery.terminal_race",
        board_metadata_set={"projection_delta": "exact"},
        board_metadata_remove=["active_claim"],
    )
    await runtime.record_execution_identity(identity, source="terminal_race_test")
    await runtime.record_task_claim(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            session_id=identity.session_id,
            status="completed",
            claimed_at=NOW - timedelta(minutes=1),
            acked_at=NOW - timedelta(minutes=1),
            heartbeat_at=NOW,
            stale_after=NOW + timedelta(minutes=30),
            metadata=_runtime_metadata(metadata, identity),
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
            status="completed",
            started_at=NOW - timedelta(minutes=1),
            completed_at=NOW,
            metadata=runtime_metadata,
        )
    )
    async with aiosqlite.connect(runtime.db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        assert await prepare_task_board_projection_snapshot(
            db,
            run_id=identity.run_id,
        )
        await db.commit()


async def test_exact_assigned_campaign_without_runtime_rows_persists_hold(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    task = await board.create("exact assigned campaign crash")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    observed = await board.get(task.id)
    assert campaign_principal(observed) == (True, identity.agent_id)
    assert valid_board_campaign_authority(metadata, task_id=task.id)
    reconciler = GraphReconciler(runtime, task_board=board)

    first = await reconciler.reconcile(now=NOW)
    replay = await reconciler.reconcile(now=NOW + timedelta(seconds=1))

    expected_error = (
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    )
    assert first.errors == [expected_error]
    assert replay.errors == [expected_error]
    assert reconciler.boot_census_succeeded is False
    assert reconciler.boot_recovery_completed is False
    assert _runtime_authority_counts(runtime) == {
        "task_claims": 0,
        "delegation_runs": 0,
        "execution_identities": 0,
        "runtime_receipts": 0,
        "idempotency_records": 0,
    }
    with sqlite3.connect(runtime.db_path) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(f"SELECT * FROM {BOARD_ONLY_HOLD_TABLE}").fetchall()
        assert len(rows) == 1
        hold = rows[0]
        assert hold["state"] == "effect_indeterminate"
        assert hold["retry_authorized"] == 0
        assert hold["cessation_proven"] == 0
        assert hold["owner_run_id"] == identity.run_id
        assert hold["owner_claim_id"] == identity.claim_id
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute(
                f"UPDATE {BOARD_ONLY_HOLD_TABLE} SET retry_authorized = 1"
                " WHERE hold_id = ?",
                (hold["hold_id"],),
            )
    preserved = await board.get(task.id)
    assert preserved is not None
    assert preserved.status is TaskStatus.ASSIGNED
    assert preserved.assigned_to == identity.agent_id
    assert preserved.metadata == metadata


async def test_terminal_campaign_without_projection_outbox_remains_held(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(minutes=1))).errors == []
    task = await board.create("terminal runtime without Board outbox")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    terminal_metadata = _runtime_metadata(metadata, identity)
    await runtime.record_execution_identity(
        identity,
        source="terminal_without_projection_outbox_test",
    )
    await runtime.record_task_claim(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            agent_id=identity.agent_id,
            session_id=identity.session_id,
            status="completed",
            claimed_at=NOW - timedelta(minutes=1),
            acked_at=NOW - timedelta(minutes=1),
            heartbeat_at=NOW,
            stale_after=NOW + timedelta(minutes=30),
            metadata=terminal_metadata,
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
            status="completed",
            started_at=NOW - timedelta(minutes=1),
            completed_at=NOW,
            metadata=terminal_metadata,
        )
    )

    expected = (
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    )
    first = await reconciler.reconcile(now=NOW, stale_only=True)
    replay = await reconciler.reconcile(
        now=NOW + timedelta(seconds=1),
        stale_only=True,
    )

    assert first.errors == [expected]
    assert replay.errors == [expected]
    preserved = await board.get(task.id)
    assert preserved is not None and preserved.status is TaskStatus.ASSIGNED
    assert preserved.assigned_to == identity.agent_id
    with sqlite3.connect(runtime.db_path) as db:
        db.row_factory = sqlite3.Row
        run = db.execute(
            "SELECT status, metadata_json FROM delegation_runs WHERE run_id = ?",
            (identity.run_id,),
        ).fetchone()
        claim = db.execute(
            "SELECT status, recovered_at, retry_count FROM task_claims"
            " WHERE claim_id = ?",
            (identity.claim_id,),
        ).fetchone()
        hold = db.execute(
            f"SELECT retry_authorized, cessation_proven FROM {BOARD_ONLY_HOLD_TABLE}"
            " WHERE task_id = ?",
            (task.id,),
        ).fetchone()
        assert run is not None
        assert "task_board_projection_intent" not in json.loads(run["metadata_json"])
        assert tuple(run)[0] == "completed"
        assert tuple(claim) == ("completed", None, 0)
        assert tuple(hold) == (0, 0)
        assert db.execute(
            f"SELECT COUNT(*) FROM {BOARD_ONLY_RESOLUTION_TABLE}"
        ).fetchone()[0] == 0


async def test_terminal_run_with_missing_claim_cannot_evade_board_only_hold(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(minutes=1))).errors == []
    task = await board.create("partial terminal runtime remains held")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    terminal_metadata = _runtime_metadata(metadata, identity)
    await runtime.record_execution_identity(
        identity,
        source="terminal_missing_claim_test",
    )
    await runtime.record_delegation_run(
        DelegationRun(
            run_id=identity.run_id,
            task_id=identity.task_id,
            assigned_to=identity.agent_id,
            session_id=identity.session_id,
            claim_id=identity.claim_id,
            assigned_by="orchestrator",
            status="completed",
            started_at=NOW - timedelta(minutes=1),
            completed_at=NOW,
            metadata=terminal_metadata,
        )
    )

    report = await reconciler.reconcile(now=NOW, stale_only=True)

    expected = (
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    )
    assert report.errors == [expected]
    assert reconciler.boot_census_succeeded is False
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_claims WHERE claim_id = ?",
            (identity.claim_id,),
        ).fetchone()[0] == 0
        hold = db.execute(
            f"SELECT retry_authorized, cessation_proven"
            f" FROM {BOARD_ONLY_HOLD_TABLE} WHERE task_id = ?",
            (task.id,),
        ).fetchone()
        assert hold == (0, 0)
    preserved = await board.get(task.id)
    assert preserved is not None and preserved.status is TaskStatus.ASSIGNED


async def test_mismatched_inflight_runtime_cannot_resolve_board_only_hold(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(minutes=1))).errors == []
    task = await board.create("mismatched live runtime remains held")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    expected = (
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    )
    assert (await reconciler.reconcile(now=NOW, stale_only=True)).errors == [
        expected
    ]
    await _seed_live_runtime_attempt(
        runtime,
        metadata=metadata,
        identity=identity,
    )
    with sqlite3.connect(runtime.db_path) as db:
        db.execute(
            "UPDATE task_claims SET status = 'claimed' WHERE claim_id = ?",
            (identity.claim_id,),
        )
        db.commit()

    report = await reconciler.reconcile(
        now=NOW + timedelta(seconds=1),
        stale_only=True,
    )

    assert report.errors == [expected]
    assert reconciler.boot_census_succeeded is False
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            f"SELECT COUNT(*) FROM {BOARD_ONLY_RESOLUTION_TABLE}"
        ).fetchone()[0] == 0


async def test_malformed_running_campaign_shape_persists_indeterminate_hold(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    task = await board.create("malformed running campaign crash")
    malformed = {
        "mission_campaign_authority": {"schema_version": "malformed"},
        "attempt_generation": "not-an-integer",
    }
    _force_board_state(
        board,
        task_id=task.id,
        status="running",
        assigned_to="claimed-seat",
        metadata=malformed,
    )

    reconciler = GraphReconciler(runtime, task_board=board)
    report = await reconciler.reconcile(now=NOW)

    assert report.errors == [
        f"board_only_campaign:{task.id}:malformed_campaign_shape:effect_indeterminate"
    ]
    assert reconciler.boot_census_succeeded is False
    assert _runtime_authority_counts(runtime)["delegation_runs"] == 0
    with sqlite3.connect(runtime.db_path) as db:
        row = db.execute(
            f"SELECT classification, retry_authorized, cessation_proven"
            f" FROM {BOARD_ONLY_HOLD_TABLE}"
        ).fetchone()
    assert row == ("malformed_campaign_shape", 0, 0)
    preserved = await board.get(task.id)
    assert preserved is not None and preserved.status is TaskStatus.RUNNING
    assert preserved.metadata == malformed


async def test_late_exact_runtime_attempt_resolves_hold_without_authorizing_retry(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(minutes=1))).errors == []
    assert reconciler.boot_recovery_completed is True
    task = await board.create("live assignment crossing periodic census")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    held = await reconciler.reconcile(now=NOW, stale_only=True)
    assert held.errors == [
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    ]

    await _seed_live_runtime_attempt(
        runtime,
        metadata=metadata,
        identity=identity,
    )

    adopted = await reconciler.reconcile(
        now=NOW + timedelta(seconds=1),
        stale_only=True,
    )

    assert adopted.errors == []
    assert reconciler.boot_census_succeeded is True
    with sqlite3.connect(runtime.db_path) as db:
        resolution = db.execute(
            f"SELECT reason, state, retry_authorized, cessation_proven,"
            " owner_run_id, owner_claim_id"
            f" FROM {BOARD_ONLY_RESOLUTION_TABLE}"
        ).fetchone()
    assert resolution == (
        "exact_runtime_attempt_adopted",
        "exact_runtime_authority_observed",
        0,
        0,
        identity.run_id,
        identity.claim_id,
    )


async def test_late_runtime_attempt_cannot_resolve_changed_board_snapshot(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(minutes=1))).errors == []
    task = await board.create("changed assignment crossing periodic census")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    held = await reconciler.reconcile(now=NOW, stale_only=True)
    expected = (
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    )
    assert held.errors == [expected]

    changed = {**metadata, "concurrent_nonprotocol_write": "changed"}
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=changed,
    )
    await _seed_live_runtime_attempt(
        runtime,
        metadata=metadata,
        identity=identity,
    )

    rejected = await reconciler.reconcile(
        now=NOW + timedelta(seconds=1),
        stale_only=True,
    )

    assert rejected.errors == [expected]
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            f"SELECT COUNT(*) FROM {BOARD_ONLY_RESOLUTION_TABLE}"
        ).fetchone()[0] == 0


async def test_same_attempt_running_lineage_resolves_terminal_projection(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(minutes=1))).errors == []
    task = await board.create("same attempt advances after Board-only hold")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    hold_error = (
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    )
    assert (await reconciler.reconcile(now=NOW, stale_only=True)).errors == [
        hold_error
    ]
    await _seed_live_runtime_attempt(
        runtime,
        metadata=metadata,
        identity=identity,
    )
    assert (
        await reconciler.reconcile(
            now=NOW + timedelta(seconds=1), stale_only=True
        )
    ).errors == []

    running = await board.start(task.id)
    assert running.status is TaskStatus.RUNNING
    observed_running = await reconciler.reconcile(
        now=NOW + timedelta(seconds=2), stale_only=True
    )

    assert observed_running.errors == []
    with sqlite3.connect(runtime.db_path) as db:
        db.row_factory = sqlite3.Row
        edge = db.execute(f"SELECT * FROM {BOARD_ONLY_LINEAGE_TABLE}").fetchone()
        assert edge is not None
        assert edge["transition"] == "assigned_to_running"
        assert edge["owner_run_id"] == identity.run_id
        assert edge["owner_claim_id"] == identity.claim_id
        assert edge["retry_authorized"] == 0
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute(
                f"UPDATE {BOARD_ONLY_LINEAGE_TABLE} SET retry_authorized = 1"
                " WHERE lineage_id = ?",
                (edge["lineage_id"],),
            )

    result = "same-attempt terminal result"
    await _seed_terminal_runtime_projection(
        runtime,
        metadata=metadata,
        identity=identity,
        result=result,
    )
    settlement = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=settlement,
        now=NOW + timedelta(seconds=3),
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )
    assert settlement.errors == []
    completed = await board.get(task.id)
    assert completed is not None and completed.status is TaskStatus.COMPLETED

    proven = await reconciler.reconcile(
        now=NOW + timedelta(seconds=4), stale_only=True
    )

    assert proven.errors == []
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            f"SELECT COUNT(*) FROM {BOARD_ONLY_RESOLUTION_TABLE}"
            " WHERE reason = 'exact_terminal_projection_proven'"
        ).fetchone()[0] == 1


async def test_atomic_receipt_closes_skipped_running_census_lineage(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(minutes=1))).errors == []
    task = await board.create("terminal projection outruns RUNNING census")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    hold_error = (
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    )
    assert (await reconciler.reconcile(now=NOW, stale_only=True)).errors == [
        hold_error
    ]
    await _seed_live_runtime_attempt(
        runtime,
        metadata=metadata,
        identity=identity,
    )
    assert (
        await reconciler.reconcile(
            now=NOW + timedelta(seconds=1), stale_only=True
        )
    ).errors == []

    running = await board.start(task.id)
    assert running.status is TaskStatus.RUNNING
    await _seed_terminal_runtime_projection(
        runtime,
        metadata=metadata,
        identity=identity,
        result="fast terminal result",
    )
    settlement = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=settlement,
        now=NOW + timedelta(seconds=2),
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )
    assert settlement.errors == []
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            f"SELECT COUNT(*) FROM {BOARD_ONLY_LINEAGE_TABLE}"
        ).fetchone()[0] == 0

    proven = await reconciler.reconcile(
        now=NOW + timedelta(seconds=3), stale_only=True
    )

    assert proven.errors == []
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            f"SELECT COUNT(*) FROM {BOARD_ONLY_LINEAGE_TABLE}"
        ).fetchone()[0] == 1
        assert db.execute(
            f"SELECT COUNT(*) FROM {BOARD_ONLY_RESOLUTION_TABLE}"
            " WHERE reason = 'exact_terminal_projection_proven'"
        ).fetchone()[0] == 1


async def test_terminal_board_projection_requires_exact_witness_and_ack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dharma_swarm.graph import reconcile_board_replay

    runtime, board = await _stores(tmp_path)
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(minutes=1))).errors == []
    task = await board.create("terminal completion crossing periodic census")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    expected = (
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    )
    assert (await reconciler.reconcile(now=NOW, stale_only=True)).errors == [expected]
    await _seed_terminal_runtime_projection(
        runtime,
        metadata=metadata,
        identity=identity,
        result="exact terminal provider result",
    )

    real_append_ack = reconcile_board_replay._append_projection_ack

    async def crash_before_ack(*args, **kwargs) -> None:
        raise RuntimeError("process died after exact Board readback")

    monkeypatch.setattr(
        reconcile_board_replay,
        "_append_projection_ack",
        crash_before_ack,
    )
    interrupted = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=interrupted,
        now=NOW + timedelta(seconds=1),
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )
    assert interrupted.errors == [f"projection:{identity.run_id}:RuntimeError"]
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_target_witnesses"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_atomic_projection_witnesses"
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_acks"
        ).fetchone()[0] == 0
    with sqlite3.connect(board._db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_effect_commits"
        ).fetchone()[0] == 1

    monkeypatch.setattr(
        reconcile_board_replay,
        "_append_projection_ack",
        real_append_ack,
    )
    ack_pass = await reconciler.reconcile(
        now=NOW + timedelta(seconds=2),
        stale_only=True,
    )
    assert ack_pass.errors == []
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_acks"
        ).fetchone()[0] == 1

    proven = await reconciler.reconcile(
        now=NOW + timedelta(seconds=3),
        stale_only=True,
    )
    assert proven.errors == []
    with sqlite3.connect(runtime.db_path) as db:
        resolution = db.execute(
            f"SELECT reason, state, retry_authorized, cessation_proven"
            f" FROM {BOARD_ONLY_RESOLUTION_TABLE}"
            " WHERE reason = 'exact_terminal_projection_proven'"
        ).fetchone()
    assert resolution == (
        "exact_terminal_projection_proven",
        "exact_terminal_effect_observed",
        0,
        0,
    )


async def test_forged_atomic_projection_witness_cannot_resolve_board_only_hold(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(minutes=1))).errors == []
    task = await board.create("forged atomic witness remains held")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    hold_error = (
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    )
    assert (await reconciler.reconcile(now=NOW, stale_only=True)).errors == [
        hold_error
    ]
    await _seed_terminal_runtime_projection(
        runtime,
        metadata=metadata,
        identity=identity,
        result="atomic proof tamper fixture",
    )
    settlement = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=settlement,
        now=NOW + timedelta(seconds=1),
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )
    assert settlement.errors == []

    with sqlite3.connect(runtime.db_path) as db:
        db.execute("DROP TRIGGER task_board_atomic_projection_witness_no_update")
        db.execute(
            "UPDATE task_board_atomic_projection_witnesses"
            " SET board_receipt_json = '{}' WHERE run_id = ?",
            (identity.run_id,),
        )
        db.commit()

    rejected = await reconciler.reconcile(
        now=NOW + timedelta(seconds=2),
        stale_only=True,
    )

    assert hold_error in rejected.errors
    assert f"projection:{identity.run_id}:unproven_ack" in rejected.errors
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            f"SELECT COUNT(*) FROM {BOARD_ONLY_RESOLUTION_TABLE}"
        ).fetchone()[0] == 0


async def test_nonproduction_readback_ack_cannot_resolve_canonical_board_hold(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(minutes=1))).errors == []
    task = await board.create("legacy readback cannot authorize canonical Board")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    hold_error = (
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    )
    assert (await reconciler.reconcile(now=NOW, stale_only=True)).errors == [
        hold_error
    ]
    await _seed_terminal_runtime_projection(
        runtime,
        metadata=metadata,
        identity=identity,
        result="nonproduction-only terminal result",
    )
    canonical = await board.get(task.id)
    assert canonical is not None and canonical.status is TaskStatus.ASSIGNED
    state = {"task": canonical.model_copy(deep=True)}

    async def get_task(task_id: str):
        assert task_id == task.id
        return state["task"].model_copy(deep=True)

    async def project(expected, *, metadata, result, **_kwargs):
        assert state["task"] == expected
        marker = metadata[GRAPH_PROJECTION_KEY]
        state["task"] = expected.model_copy(
            update={
                "status": (
                    TaskStatus.COMPLETED
                    if marker["run_status"] == "completed"
                    else TaskStatus.FAILED
                ),
                "result": result,
                "metadata": dict(metadata),
            },
            deep=True,
        )
        return state["task"].model_copy(deep=True)

    nonproduction_board = SimpleNamespace(
        projection_commit_mode=NON_PRODUCTION_PROJECTION_COMMIT_MODE,
        get=get_task,
        compare_and_swap_terminal_projection=project,
    )
    legacy_settlement = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=nonproduction_board,
        report=legacy_settlement,
        now=NOW + timedelta(seconds=1),
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )
    assert legacy_settlement.errors == []
    preserved = await board.get(task.id)
    assert preserved is not None and preserved.status is TaskStatus.ASSIGNED
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_target_witnesses"
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_atomic_projection_witnesses"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_acks"
        ).fetchone()[0] == 1

    rejected = await reconciler.reconcile(
        now=NOW + timedelta(seconds=2),
        stale_only=True,
    )
    assert hold_error in rejected.errors
    assert f"projection:{identity.run_id}:unproven_ack" in rejected.errors
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            f"SELECT COUNT(*) FROM {BOARD_ONLY_RESOLUTION_TABLE}"
        ).fetchone()[0] == 0


async def test_forged_receipt_transition_and_mutation_cannot_resolve_hold(
    tmp_path: Path,
) -> None:
    from dharma_swarm.graph.reconcile_board_proof import (
        validate_atomic_graph_projection_commit,
    )
    from dharma_swarm.graph.reconcile_board_replay import (
        _projection_marker,
        _target_metadata,
    )
    from dharma_swarm.task_board_effect_commit import (
        EFFECT_COMMIT_SCHEMA,
        EFFECT_MUTATION_SCHEMA,
        EFFECT_TRANSITION_SCHEMA,
        GRAPH_PROJECTION_EFFECT_KIND,
        GRAPH_PROJECTION_PAYLOAD_SCHEMA,
        graph_projection_effect_id,
    )
    from dharma_swarm.task_board_projection_intent import stable_sha256

    runtime, board = await _stores(tmp_path)
    reconciler = GraphReconciler(runtime, task_board=board)
    assert (await reconciler.reconcile(now=NOW - timedelta(minutes=1))).errors == []
    task = await board.create("receipt-only projection remains held")
    metadata, identity = _exact_campaign_metadata(
        task_id=task.id,
        runtime_path=runtime.db_path.resolve(),
    )
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to=identity.agent_id,
        metadata=metadata,
    )
    hold_error = (
        f"board_only_campaign:{task.id}:exact_campaign_attempt:effect_indeterminate"
    )
    assert (await reconciler.reconcile(now=NOW, stale_only=True)).errors == [
        hold_error
    ]
    result = "exact receipt-only forgery"
    await _seed_terminal_runtime_projection(
        runtime,
        metadata=metadata,
        identity=identity,
        result=result,
    )
    current = await board.get(task.id)
    assert current is not None and current.status is TaskStatus.ASSIGNED
    with sqlite3.connect(runtime.db_path) as db:
        run_metadata = json.loads(
            db.execute(
                "SELECT metadata_json FROM delegation_runs WHERE run_id = ?",
                (identity.run_id,),
            ).fetchone()[0]
        )
    intent = run_metadata["task_board_projection_intent"]
    marker = _projection_marker(intent)
    target = current.model_copy(
        update={
            "status": TaskStatus.COMPLETED,
            "result": result,
            "metadata": _target_metadata(current.metadata, intent, marker),
            "updated_at": NOW,
        },
        deep=True,
    )
    expected_snapshot = current.model_dump(mode="json")
    target_snapshot = target.model_dump(mode="json")
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

    def canonical(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    def db_time(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()

    def mutation_side(snapshot):
        return (
            snapshot["title"],
            snapshot["description"],
            snapshot["status"],
            snapshot["priority"],
            snapshot["assigned_to"],
            snapshot["created_by"],
            db_time(snapshot["created_at"]),
            db_time(snapshot["updated_at"]),
            snapshot["result"],
            canonical(snapshot["metadata"]),
        )

    with sqlite3.connect(board._db_path) as db:
        mutation_id = "forged-direct-mutation"
        mutation_values = (
            mutation_id,
            task.id,
            *mutation_side(expected_snapshot),
            *mutation_side(target_snapshot),
            EFFECT_MUTATION_SCHEMA,
        )
        db.execute(
            "INSERT INTO task_board_effect_mutations"
            " (mutation_id, task_id, old_title, old_description, old_status,"
            " old_priority, old_assigned_to, old_created_by, old_created_at,"
            " old_updated_at, old_result, old_metadata, new_title,"
            " new_description, new_status, new_priority, new_assigned_to,"
            " new_created_by, new_created_at, new_updated_at, new_result,"
            " new_metadata, schema_version) VALUES ("
            + ",".join("?" for _ in mutation_values)
            + ")",
            mutation_values,
        )
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
                mutation_id,
            ),
        )
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
        db.commit()

    settlement = ReconcileReport()
    await settle_task_board(
        runtime_state=runtime,
        task_board=board,
        report=settlement,
        now=NOW + timedelta(seconds=1),
        logger=logging.getLogger(__name__),
        run_id=identity.run_id,
    )
    assert settlement.errors == [f"projection:{identity.run_id}:ValueError"]
    preserved = await board.get(task.id)
    assert preserved is not None and preserved.status is TaskStatus.ASSIGNED
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_atomic_projection_witnesses"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM task_board_projection_acks"
        ).fetchone()[0] == 0

    rejected = await reconciler.reconcile(
        now=NOW + timedelta(seconds=2),
        stale_only=True,
    )
    assert hold_error in rejected.errors
    assert f"projection:{identity.run_id}:ValueError" in rejected.errors
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            f"SELECT COUNT(*) FROM {BOARD_ONLY_RESOLUTION_TABLE}"
        ).fetchone()[0] == 0


async def test_exact_ordinary_board_only_owner_does_not_create_campaign_hold(
    tmp_path: Path,
) -> None:
    runtime, board = await _stores(tmp_path)
    task = await board.create("ordinary Board-only assignment")
    metadata = _ordinary_owner_metadata(task.id)
    _force_board_state(
        board,
        task_id=task.id,
        status="assigned",
        assigned_to="ordinary-seat",
        metadata=metadata,
    )

    reconciler = GraphReconciler(runtime, task_board=board)
    report = await reconciler.reconcile(now=NOW)

    assert report.errors == []
    assert reconciler.boot_census_succeeded is True
    assert reconciler.boot_recovery_completed is True
    assert _runtime_authority_counts(runtime)["task_claims"] == 0
    with sqlite3.connect(runtime.db_path) as db:
        assert db.execute(
            f"SELECT COUNT(*) FROM {BOARD_ONLY_HOLD_TABLE}"
        ).fetchone()[0] == 0
    preserved = await board.get(task.id)
    assert preserved is not None and preserved.status is TaskStatus.ASSIGNED
    assert preserved.metadata == metadata
