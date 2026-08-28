"""Tests for dharma_swarm.graph.reconciler -- orphaned dispatch reconciliation.

Fixture-DB style: rows are fabricated directly in a temp runtime.db, then the
reconciler runs against it and the resulting rows are asserted.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import aiosqlite
import pytest

# AgentOps negative controls intentionally run without project site-packages.
# This file exercises reconciler behavior, not icontract itself, so provide the
# decorator surface needed by the eagerly imported telos_kernel package when
# that otherwise-required dependency is absent from the isolated control jail.
try:
    import icontract  # noqa: F401
except ModuleNotFoundError:
    icontract_stub = ModuleType("icontract")

    def _passthrough_contract(*args, **kwargs):
        del args, kwargs

        def decorate(function):
            return function

        return decorate

    icontract_stub.ensure = _passthrough_contract
    icontract_stub.require = _passthrough_contract
    sys.modules["icontract"] = icontract_stub

from dharma_swarm.graph.reconciler import (
    FAILURE_CODE_DIED_MID_DISPATCH,
    FAILURE_CODE_NEVER_STARTED,
    QUARANTINE_REASON,
    ReconcileReport,
)
from dharma_swarm.graph.receipt_authority import has_runtime_completion
from dharma_swarm.runtime_state import (
    RuntimeAuthorityReconcilerMixin,
    RuntimeReceipt,
    RuntimeStateStore,
)
from dharma_swarm.spine.identity import ExecutionIdentity

NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)


def GraphReconciler(*args, **kwargs):
    from dharma_swarm.swarm import build_runtime_authority_reconciler

    return build_runtime_authority_reconciler(*args, **kwargs)


def test_runtime_authority_reconciler_factory_precedes_frozen_graph(runtime):
    from dharma_swarm.graph.reconciler import GraphReconciler as FrozenGraphReconciler
    from dharma_swarm.swarm import (
        build_runtime_authority_reconciler,
        get_runtime_authority_reconciler_type,
    )

    reconciler_type = get_runtime_authority_reconciler_type()
    assert get_runtime_authority_reconciler_type() is reconciler_type
    assert reconciler_type.__bases__ == (
        RuntimeAuthorityReconcilerMixin,
        FrozenGraphReconciler,
    )
    for method_name in (
        "reconcile",
        "_reconcile_run_row",
        "_complete_from_receipt",
        "_requeue_run",
        "_fetch_claim",
        "_recover_stale_claims",
        "heartbeat_live_claims",
    ):
        assert getattr(reconciler_type, method_name) is getattr(
            RuntimeAuthorityReconcilerMixin, method_name
        )
    reconciler = build_runtime_authority_reconciler(runtime)
    assert type(reconciler) is reconciler_type
    assert isinstance(reconciler, FrozenGraphReconciler)


@pytest.mark.parametrize(
    "imports",
    (
        "import dharma_swarm.runtime_state; import dharma_swarm.graph.reconciler",
        "import dharma_swarm.graph.reconciler; import dharma_swarm.runtime_state",
        "import dharma_swarm.swarm",
    ),
)
def test_runtime_authority_reconciler_import_order_is_cycle_free(imports):
    code = (
        f"{imports}; "
        "from dharma_swarm.swarm import get_runtime_authority_reconciler_type; "
        "assert get_runtime_authority_reconciler_type() is "
        "get_runtime_authority_reconciler_type()"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.fixture
def runtime(tmp_path: Path) -> RuntimeStateStore:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    store.init_db_sync()
    return store


def _record_identity(
    store: RuntimeStateStore,
    *,
    run_id: str,
    claim_id: str,
    task_id: str = "task-1",
    agent_id: str = "agent-1",
    session_id: str = "",
) -> ExecutionIdentity:
    identity = ExecutionIdentity(
        trace_id=f"trace-{run_id}",
        correlation_id=f"corr-{run_id}",
        task_id=task_id,
        run_id=run_id,
        claim_id=claim_id,
        idempotency_key=f"idem-{run_id}",
        agent_id=agent_id,
        session_id=session_id,
    )
    return store.record_execution_identity_sync(identity)


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
    with_identity: bool = True,
) -> None:
    with sqlite3.connect(store.db_path) as db:
        try:
            db.execute("ALTER TABLE delegation_runs ADD COLUMN quarantined_at TEXT")
            db.execute("ALTER TABLE delegation_runs ADD COLUMN quarantine_reason TEXT")
        except sqlite3.Error:
            pass
        db.execute(
            "INSERT INTO delegation_runs (run_id, task_id, claim_id, assigned_to,"
            " status, started_at, metadata_json, receipt_json, quarantined_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                task_id,
                claim_id,
                assigned_to,
                status,
                (NOW - timedelta(minutes=10)).isoformat(),
                json.dumps(metadata or {}),
                receipt_json,
                quarantined_at,
            ),
        )
        db.commit()
    if (
        with_identity
        and claim_id
        and store.get_execution_identity_sync(run_id) is None
    ):
        _record_identity(
            store,
            run_id=run_id,
            claim_id=claim_id,
            task_id=task_id,
            agent_id=assigned_to,
        )


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
    with_identity: bool = True,
) -> None:
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO task_claims (claim_id, task_id, agent_id, status,"
            " claimed_at, acked_at, heartbeat_at, stale_after, recovered_at,"
            " retry_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                claim_id,
                task_id,
                agent_id,
                status,
                claimed_at or (NOW - timedelta(minutes=10)).isoformat(),
                acked_at,
                heartbeat_at,
                stale_after,
                recovered_at,
                retry_count,
            ),
        )
        db.commit()
    if with_identity:
        with sqlite3.connect(store.db_path) as db:
            identity_exists = db.execute(
                "SELECT 1 FROM execution_identities WHERE claim_id = ? LIMIT 1",
                (claim_id,),
            ).fetchone()
        if identity_exists is None:
            _record_identity(
                store,
                run_id=f"run-for-{claim_id}",
                claim_id=claim_id,
                task_id=task_id,
                agent_id=agent_id,
            )


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


def _get_runtime_receipts(
    store: RuntimeStateStore, run_id: str
) -> list[sqlite3.Row]:
    with sqlite3.connect(store.db_path) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "SELECT * FROM runtime_receipts WHERE run_id = ? ORDER BY receipt_id",
            (run_id,),
        ).fetchall()


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


async def test_recovery_writes_deterministic_typed_terminal_receipts(runtime):
    _record_identity(runtime, run_id="run-typed", claim_id="claim-typed")
    _insert_run(runtime, "run-typed", status="running", claim_id="claim-typed")
    _insert_claim(
        runtime,
        "claim-typed",
        status="running",
        acked_at=(NOW - timedelta(minutes=9)).isoformat(),
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.errors == []
    receipts = _get_runtime_receipts(runtime, "run-typed")
    assert [row["receipt_id"] for row in receipts] == [
        "rr_run-typed_failed_run",
        "rr_run-typed_recovered_claim",
    ]
    assert [(row["receipt_type"], row["status"]) for row in receipts] == [
        ("delegation_run", "failed"),
        ("task_claim", "recovered"),
    ]
    assert all(row["trace_id"] == "trace-run-typed" for row in receipts)
    assert all(row["created_at"] == NOW.isoformat() for row in receipts)


async def test_terminal_row_updates_roll_back_if_receipt_insert_fails(
    runtime, monkeypatch
):
    _record_identity(runtime, run_id="run-atomic", claim_id="claim-atomic")
    _insert_run(runtime, "run-atomic", status="running", claim_id="claim-atomic")
    _insert_claim(runtime, "claim-atomic", status="running")

    async def fail_receipt_insert(db, receipt):
        raise aiosqlite.OperationalError("fixture receipt failure")

    monkeypatch.setattr(
        runtime,
        "record_runtime_receipt_in_transaction",
        fail_receipt_insert,
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.requeued_runs == []
    assert report.recovered_claims == []
    assert report.errors == ["run:run-atomic:TerminalReceiptPersistenceError"]
    assert _get_run(runtime, "run-atomic")["status"] == "running"
    assert _get_claim(runtime, "claim-atomic")["status"] == "running"
    assert _get_runtime_receipts(runtime, "run-atomic") == []


async def test_conflicting_terminal_receipt_is_preserved_and_rolls_back(runtime):
    identity = _record_identity(
        runtime,
        run_id="run-proof-collision",
        claim_id="claim-proof-collision",
    )
    _insert_run(
        runtime,
        "run-proof-collision",
        status="running",
        claim_id="claim-proof-collision",
    )
    _insert_claim(runtime, "claim-proof-collision", status="running")
    prior_proof = runtime.build_runtime_receipt(
        identity,
        receipt_id="rr_run-proof-collision_failed_run",
        receipt_type="delegation_run",
        status="completed",
        side_effect_key="prior-proof",
        payload={"proof": "must-not-be-replaced"},
        created_at=NOW,
    )
    runtime.record_runtime_receipt_sync(prior_proof)

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.requeued_runs == []
    assert report.recovered_claims == []
    assert report.errors == [
        "run:run-proof-collision:TerminalReceiptPersistenceError"
    ]
    assert _get_run(runtime, "run-proof-collision")["status"] == "running"
    assert _get_claim(runtime, "claim-proof-collision")["status"] == "running"
    receipts = _get_runtime_receipts(runtime, "run-proof-collision")
    assert len(receipts) == 1
    assert receipts[0]["status"] == "completed"
    assert receipts[0]["side_effect_key"] == "prior-proof"
    assert json.loads(receipts[0]["payload_json"]) == {
        "proof": "must-not-be-replaced"
    }


async def test_exact_terminal_receipt_replay_is_idempotent(runtime):
    identity = _record_identity(
        runtime,
        run_id="run-proof-replay",
        claim_id="claim-proof-replay",
    )
    _insert_run(
        runtime,
        "run-proof-replay",
        status="running",
        claim_id="claim-proof-replay",
    )
    _insert_claim(runtime, "claim-proof-replay", status="running")
    exact_receipts: list[RuntimeReceipt] = [
        runtime.build_runtime_receipt(
            identity,
            receipt_id="rr_run-proof-replay_failed_run",
            receipt_type="delegation_run",
            status="failed",
            payload={
                "claim_id": "claim-proof-replay",
                "failure_code": FAILURE_CODE_NEVER_STARTED,
                "reconciled": True,
                "reconciliation_reason": FAILURE_CODE_NEVER_STARTED,
            },
            created_at=NOW,
        ),
        runtime.build_runtime_receipt(
            identity,
            receipt_id="rr_run-proof-replay_recovered_claim",
            receipt_type="task_claim",
            status="recovered",
            payload={
                "claim_id": "claim-proof-replay",
                "reconciled": True,
                "reconciliation_reason": FAILURE_CODE_NEVER_STARTED,
            },
            created_at=NOW,
        ),
    ]
    for receipt in exact_receipts:
        runtime.record_runtime_receipt_sync(receipt)

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.errors == []
    assert report.requeued_runs == ["run-proof-replay"]
    assert report.recovered_claims == ["claim-proof-replay"]
    receipts = _get_runtime_receipts(runtime, "run-proof-replay")
    assert len(receipts) == 2
    assert {row["receipt_id"] for row in receipts} == {
        receipt.receipt_id for receipt in exact_receipts
    }


async def test_incomplete_legacy_identity_reports_error_without_receipt(runtime):
    with sqlite3.connect(runtime.db_path) as db:
        db.execute(
            "INSERT INTO execution_identities (run_id, trace_id, correlation_id,"
            " task_id, claim_id, idempotency_key, agent_id, metadata_json,"
            " created_at, updated_at) VALUES (?, '', '', ?, ?, '', ?, '{}', ?, ?)",
            (
                "run-legacy",
                "task-1",
                "claim-legacy",
                "agent-1",
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
        db.commit()
    _insert_run(
        runtime,
        "run-legacy",
        status="running",
        claim_id="claim-legacy",
        with_identity=False,
    )
    _insert_claim(
        runtime,
        "claim-legacy",
        status="running",
        with_identity=False,
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.requeued_runs == []
    assert report.recovered_claims == []
    assert any(
        error.startswith("identity:run-legacy:incomplete:")
        for error in report.errors
    )
    assert _get_run(runtime, "run-legacy")["status"] == "running"
    assert _get_claim(runtime, "claim-legacy")["status"] == "running"
    assert _get_runtime_receipts(runtime, "run-legacy") == []


async def test_missing_execution_identity_rolls_back_and_reports_error(runtime):
    _insert_run(
        runtime,
        "run-missing-identity",
        status="running",
        claim_id="claim-missing-identity",
        with_identity=False,
    )
    _insert_claim(
        runtime,
        "claim-missing-identity",
        status="running",
        with_identity=False,
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.requeued_runs == []
    assert report.recovered_claims == []
    assert report.errors == [
        "identity:run-missing-identity:missing_execution_identity"
    ]
    assert _get_run(runtime, "run-missing-identity")["status"] == "running"
    assert _get_claim(runtime, "claim-missing-identity")["status"] == "running"
    assert _get_runtime_receipts(runtime, "run-missing-identity") == []


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
    _record_identity(runtime, run_id="run-torn", claim_id="claim-torn")
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
    typed = _get_runtime_receipts(runtime, "run-torn")
    assert [(row["receipt_type"], row["status"]) for row in typed] == [
        ("task_claim", "completed"),
        ("delegation_run", "completed"),
    ]


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


async def test_standalone_stale_claim_rolls_back_if_receipt_insert_fails(
    runtime, monkeypatch
):
    _insert_claim(
        runtime,
        "claim-atomic-standalone",
        status="claimed",
        stale_after=(NOW - timedelta(minutes=5)).isoformat(),
    )

    async def fail_receipt_insert(db, receipt):
        raise aiosqlite.OperationalError("fixture standalone receipt failure")

    monkeypatch.setattr(
        runtime,
        "record_runtime_receipt_in_transaction",
        fail_receipt_insert,
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.recovered_claims == []
    assert report.errors == [
        "claim:claim-atomic-standalone:TerminalReceiptPersistenceError"
    ]
    claim = _get_claim(runtime, "claim-atomic-standalone")
    assert claim["status"] == "claimed"
    assert claim["recovered_at"] is None
    assert _get_runtime_receipts(runtime, "run-for-claim-atomic-standalone") == []


@pytest.mark.parametrize("legacy_status", ["assigned", "active"])
async def test_legacy_claim_status_is_outside_graph_reconciler(
    runtime, legacy_status
):
    claim_id = f"claim-legacy-{legacy_status}"
    _insert_claim(
        runtime,
        claim_id,
        status=legacy_status,
        stale_after=(NOW - timedelta(minutes=5)).isoformat(),
        with_identity=False,
    )

    report = await GraphReconciler(runtime).reconcile(now=NOW)

    assert report.recovered_claims == []
    assert report.errors == []
    claim = _get_claim(runtime, claim_id)
    assert claim["status"] == legacy_status
    assert claim["recovered_at"] is None


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


async def test_requeued_run_requeues_task_on_board(runtime):
    board = _StubBoard()
    _insert_run(
        runtime, "run-board", status="claimed", claim_id="claim-board", task_id="task-b"
    )
    _insert_claim(runtime, "claim-board", status="claimed", task_id="task-b")

    report = await GraphReconciler(runtime, task_board=board).reconcile(now=NOW)

    assert report.requeued_runs == ["run-board"]
    assert board.requeued == ["task-b"]


async def test_persisted_heartbeat_cannot_leave_board_pending_graph_active(
    runtime, tmp_path: Path
):
    """Regression for heartbeat -> board requeue -> active-run split brain."""
    from dharma_swarm.models import TaskStatus
    from dharma_swarm.task_board import TaskBoard

    board = TaskBoard(tmp_path / "split-tasks.db")
    await board.init_db()
    task = await board.create("prior-process orphan")
    async with board._open() as db:
        await db.execute(
            "UPDATE tasks SET status = 'running', assigned_to = 'agent-1',"
            " updated_at = ? WHERE id = ?",
            ((NOW - timedelta(hours=1)).isoformat(), task.id),
        )
        await db.commit()

    original_heartbeat = (NOW - timedelta(minutes=20)).isoformat()
    _insert_run(
        runtime,
        "run-split",
        status="running",
        claim_id="claim-split",
        task_id=task.id,
    )
    _insert_claim(
        runtime,
        "claim-split",
        status="running",
        task_id=task.id,
        acked_at=(NOW - timedelta(minutes=20)).isoformat(),
        heartbeat_at=original_heartbeat,
        stale_after=(NOW - timedelta(minutes=5)).isoformat(),
    )
    reconciler = GraphReconciler(runtime, task_board=board)

    assert reconciler.heartbeat_live_claims(now=NOW) == 0
    report = await reconciler.reconcile(now=NOW, stale_only=True)

    assert report.requeued_runs == ["run-split"]
    assert _get_run(runtime, "run-split")["status"] == "failed"
    assert _get_claim(runtime, "claim-split")["status"] == "recovered"
    refreshed = await board.get(task.id)
    assert refreshed is not None
    assert refreshed.status == TaskStatus.PENDING


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


def test_heartbeat_live_claims_beats_due_claims(runtime):
    stale = NOW + timedelta(minutes=20)  # window = 10 min
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

    beaten = GraphReconciler(runtime).heartbeat_live_claims(
        {"claim-due", "claim-recent", "claim-recovered"},
        now=NOW,
    )

    assert beaten == 1
    due = _get_claim(runtime, "claim-due")
    assert due["heartbeat_at"] != (NOW - timedelta(minutes=11)).isoformat()
    recent = _get_claim(runtime, "claim-recent")
    assert recent["heartbeat_at"] == (NOW - timedelta(seconds=10)).isoformat()


def test_heartbeat_requires_explicit_live_claim_authority(runtime):
    original_heartbeat = (NOW - timedelta(minutes=11)).isoformat()
    _insert_claim(
        runtime,
        "claim-persisted-only",
        status="running",
        stale_after=(NOW + timedelta(minutes=20)).isoformat(),
        heartbeat_at=original_heartbeat,
    )

    beaten = GraphReconciler(runtime).heartbeat_live_claims(now=NOW)

    assert beaten == 0
    assert _get_claim(runtime, "claim-persisted-only")["heartbeat_at"] == original_heartbeat


def test_heartbeat_live_claims_updates_only_explicit_live_subset(runtime):
    original_heartbeat = (NOW - timedelta(minutes=11)).isoformat()
    for claim_id in ("claim-live-local", "claim-orphan-other-boot"):
        _insert_claim(
            runtime,
            claim_id,
            status="running",
            stale_after=(NOW + timedelta(minutes=20)).isoformat(),
            heartbeat_at=original_heartbeat,
        )

    beaten = GraphReconciler(runtime).heartbeat_live_claims(
        {"claim-live-local"},
        now=NOW,
    )

    assert beaten == 1
    assert _get_claim(runtime, "claim-live-local")["heartbeat_at"] == NOW.isoformat()
    assert (
        _get_claim(runtime, "claim-orphan-other-boot")["heartbeat_at"]
        == original_heartbeat
    )


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
    assert src.index("reconcile_graph_runs") < src.index("if self._read_only_boot"), (
        "read-only boot must still reconcile prior-process graph rows"
    )
    assert "boot_graph_reconcile_succeeded = not boot_report.errors" in src
    assert src.index("if boot_graph_reconcile_succeeded") < src.index(
        "reaped = await self._reap_stale_running_tasks()"
    )


def test_tick_reconciles_graph_before_board_orphan_reaper_source_order():
    import inspect

    from dharma_swarm.swarm import SwarmManager

    src = inspect.getsource(SwarmManager.tick)
    assert src.index("reconcile_graph_runs(stale_only=True)") < src.index(
        "self.reap_orphaned_tasks()"
    )
    assert "graph_reconcile_succeeded = not tick_report.errors" in src
    assert "graph_reconcile_not_confirmed" in src


async def test_live_claim_authority_survives_active_dispatch_cleanup(tmp_path: Path):
    """A running task retains explicit claim identity during terminal writes."""
    from dharma_swarm.swarm import SwarmManager

    class StableClaimBoard:
        async def get(self, task_id):
            assert task_id == "task-terminal-window"
            return SimpleNamespace(
                metadata={"last_claim": {"claim_id": "claim-terminal-window"}}
            )

    background = SimpleNamespace(done=lambda: False)
    orchestrator = SimpleNamespace(
        _running_tasks={"task-terminal-window": background},
        _active_dispatches={},
    )
    manager = SwarmManager(state_dir=tmp_path / ".dharma")
    manager._task_board = StableClaimBoard()
    manager._orchestrator = orchestrator

    assert await manager._current_process_live_claim_ids() == {
        "claim-terminal-window"
    }


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
    async with board._open() as db:
        await db.execute(
            "UPDATE tasks SET status = 'running', updated_at = ? WHERE id = ?",
            (stale.isoformat(), task.id),
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
