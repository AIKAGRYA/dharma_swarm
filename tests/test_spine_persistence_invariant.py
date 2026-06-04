"""Spine persistence invariant tests (tests-only, no runtime code).

These tests prove that the *current* A2A spine dispatch path already
persists exactly one canonical ``RuntimeReceipt`` and one completed
``IdempotencyRecord`` per logical dispatch, through the inner
``A2AServer.submit()`` call. They exist to lock in the decision NOT to
add an ``EvidenceReceipt -> RuntimeReceipt`` bridge writer: such a bridge
would double-persist, because ``A2AServer.submit()`` is already the
canonical writer.

Invariants proven:
    1. One logical dispatch returns exactly one ``spine.EvidenceReceipt``.
    2. The same dispatch persists exactly one *task* ``RuntimeReceipt`` for
       the run -- the existing ``a2a_task`` receipt from
       ``A2AServer.submit()`` -- and NOT a second ``dispatch_evidence``
       receipt. (The store also records idempotency-lifecycle rows --
       ``idempotency_consumed`` / ``side_effect_intent`` /
       ``side_effect_complete`` -- in the same ``runtime_receipts`` table;
       those are bookkeeping for the ``IdempotencyRecord`` and are not task
       receipts, so the invariant is scoped to ``receipt_type='a2a_task'``.)
    3. Exactly one ``IdempotencyRecord`` exists and is ``completed`` --
       proving exactly-once lives in ``IdempotencyRecord``, not the
       receipt writer.
    4. ``trace_id`` / ``correlation_id`` / ``run_id`` / ``task_id`` /
       ``idempotency_key`` all match across ``ExecutionIdentity``, the
       returned spine ``EvidenceReceipt``, the persisted ``RuntimeReceipt``,
       and the ``IdempotencyRecord``.
    5. Retrying the same logical dispatch (same idempotency identity) does
       not create a second ``RuntimeReceipt``.
    6. The failure path still emits exactly one spine ``EvidenceReceipt``
       and one ``RuntimeReceipt`` -- no double write.
    7. ``delegation_runs.receipt_json`` being empty does NOT mean
       persistence failed: canonical persistence is ``RuntimeReceipt`` +
       ``IdempotencyRecord``; the projection/cache is not the source of
       truth.

The ONLY difference from ``tests/test_spine_adoption_dispatch.py`` is that
these tests attach a real ``RuntimeStateStore`` to the ``A2AServer`` so the
already-present persistence branch (``a2a_server.py``: guarded by
``self._runtime_state is not None``) executes. No production code changes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.a2a.a2a_bridge import A2ABridge
from dharma_swarm.a2a.a2a_server import (
    A2AMessage,
    A2AServer,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.a2a.agent_card import CardRegistry
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.receipt import EvidenceReceipt


# ---------------------------------------------------------------------------
# Deterministic identity (so persisted rows are queryable by known keys)
# ---------------------------------------------------------------------------

TASK_ID = "task-persist-inv-0001"
RUN_ID = "run-persist-inv-0001"
TRACE_ID = "trc-persist-inv-0001"
CORRELATION_ID = "corr-persist-inv-0001"
IDEMPOTENCY_KEY = "idem-persist-inv-0001"
AGENT_ID = "coder"
EXTERNAL_A2A_TASK_ID = "PERSIST-INV-0001"
CAPABILITY = "code_review"

# A2AServer.submit() builds this side-effect key:
#   f"a2a_handler:{task.id}:{task.capability or 'default'}"
SIDE_EFFECT_KEY = f"a2a_handler:{EXTERNAL_A2A_TASK_ID}:{CAPABILITY}"


def _identity_metadata() -> dict[str, str]:
    """Inject a fixed ExecutionIdentity through task metadata.

    Mirrors the proven pattern in test_runtime_truth_spine_v2_evidence.py:
    ``A2AServer._ensure_execution_identity`` reads these keys verbatim.
    """
    return {
        "source": "test",
        "task_id": TASK_ID,
        "trace_id": TRACE_ID,
        "correlation_id": CORRELATION_ID,
        "run_id": RUN_ID,
        "runtime_run_id": RUN_ID,
        "idempotency_key": IDEMPOTENCY_KEY,
        "proposal_id": "prop-persist-inv-0001",
    }


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def registry(tmp_path: Path) -> CardRegistry:
    cards = tmp_path / "cards"
    cards.mkdir()
    return CardRegistry(cards_dir=cards)


@pytest.fixture
def runtime(tmp_path: Path) -> RuntimeStateStore:
    # sqlite-backed, isolated per test (proven pattern: test_diff_applier.py)
    return RuntimeStateStore(tmp_path / "runtime.db")


def _success_handler(task: A2ATask) -> A2ATask:
    task.result = "processed"
    task.status = A2ATaskStatus.COMPLETED
    return task


def _failure_handler(task: A2ATask) -> A2ATask:
    raise RuntimeError("handler exploded")


def _make_bridge(
    registry: CardRegistry,
    runtime: RuntimeStateStore,
    handler=_success_handler,
) -> tuple[A2ABridge, A2AServer]:
    """Build a bridge whose server has a real runtime_state store attached.

    This is the only delta vs. the existing adoption-dispatch tests:
    persistence in A2AServer.submit() is guarded by
    ``self._runtime_state is not None``.
    """
    server = A2AServer(runtime_state=runtime, require_execution_identity=True)
    if handler is not None:
        server.set_default_handler(handler)
    bridge = A2ABridge(
        server=server,
        registry=registry,
        trishula_outbox=Path("/tmp/nonexistent"),
    )
    return bridge, server


def _task() -> A2ATask:
    return A2ATask(
        id=EXTERNAL_A2A_TASK_ID,
        from_agent="orchestrator",
        to_agent=AGENT_ID,
        capability=CAPABILITY,
        history=[A2AMessage.text("Review this PR")],
        trace_id=TRACE_ID,
        metadata=_identity_metadata(),
    )


# ---------------------------------------------------------------------------
# 1. One dispatch -> exactly one spine EvidenceReceipt
# ---------------------------------------------------------------------------


async def test_submit_via_spine_returns_one_spine_evidence_receipt(
    registry: CardRegistry, runtime: RuntimeStateStore
) -> None:
    bridge, _ = _make_bridge(registry, runtime)

    result, receipt = await bridge.submit_via_spine(_task())

    assert isinstance(receipt, EvidenceReceipt)
    assert receipt.operation == "invoke_agent"
    assert receipt.provider == "a2a"
    assert receipt.status == "ok"
    assert receipt.error_source == "none"
    assert result.status == A2ATaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# 2. Exactly one persisted RuntimeReceipt, of type 'a2a_task'
#    (NOT a second 'dispatch_evidence' receipt)
# ---------------------------------------------------------------------------


async def test_submit_via_spine_persists_one_runtime_receipt_via_inner_submit(
    registry: CardRegistry, runtime: RuntimeStateStore
) -> None:
    bridge, _ = _make_bridge(registry, runtime)

    await bridge.submit_via_spine(_task())

    # The canonical *task* receipt is the 'a2a_task' one. (The store also
    # writes idempotency-lifecycle rows -- idempotency_consumed /
    # side_effect_intent / side_effect_complete -- into runtime_receipts;
    # those are bookkeeping for the IdempotencyRecord, not task receipts.)
    task_receipts = await runtime.list_runtime_receipts(
        run_id=RUN_ID, receipt_type="a2a_task", limit=50
    )
    assert len(task_receipts) == 1, (
        "expected exactly one 'a2a_task' RuntimeReceipt for the run; "
        f"got {len(task_receipts)}: "
        f"{[(r.receipt_id, r.receipt_type) for r in task_receipts]}"
    )

    only = task_receipts[0]
    # It is the existing A2AServer.submit() receipt.
    assert only.receipt_id == f"rr_{RUN_ID}_a2a_{A2ATaskStatus.COMPLETED.value}"

    # No bridge wrote a second 'dispatch_evidence' runtime receipt.
    dispatch_evidence = await runtime.list_runtime_receipts(
        run_id=RUN_ID, receipt_type="dispatch_evidence", limit=50
    )
    assert dispatch_evidence == [], (
        "a 'dispatch_evidence' RuntimeReceipt was persisted -- this is the "
        "double-write a bridge would introduce; it must not exist"
    )


# ---------------------------------------------------------------------------
# 3. Exactly one completed IdempotencyRecord
# ---------------------------------------------------------------------------


async def test_submit_via_spine_records_one_completed_idempotency_record(
    registry: CardRegistry, runtime: RuntimeStateStore
) -> None:
    bridge, _ = _make_bridge(registry, runtime)

    await bridge.submit_via_spine(_task())

    record = runtime.get_idempotency_record_sync(IDEMPOTENCY_KEY, SIDE_EFFECT_KEY)

    assert record is not None, "idempotency record was not persisted"
    assert record.status == "completed"
    assert record.run_id == RUN_ID
    assert record.trace_id == TRACE_ID
    assert record.correlation_id == CORRELATION_ID
    # Exactly-once is anchored to the IdempotencyRecord, and it points at the
    # one canonical receipt -- not at a separate bridge receipt.
    assert record.result_receipt_id == (
        f"rr_{RUN_ID}_a2a_{A2ATaskStatus.COMPLETED.value}"
    )


# ---------------------------------------------------------------------------
# 4. Identity matches across identity / spine receipt / runtime receipt / idem
# ---------------------------------------------------------------------------


async def test_submit_via_spine_runtime_receipt_identity_matches_spine_receipt(
    registry: CardRegistry, runtime: RuntimeStateStore
) -> None:
    bridge, _ = _make_bridge(registry, runtime)

    result, receipt = await bridge.submit_via_spine(_task())

    # ExecutionIdentity as recorded on the result task.
    identity = result.metadata.get("execution_identity", {})
    assert identity, "ExecutionIdentity missing from result metadata"

    runtime_receipts = await runtime.list_runtime_receipts(
        run_id=RUN_ID, receipt_type="a2a_task", limit=50
    )
    assert len(runtime_receipts) == 1
    rr = runtime_receipts[0]

    idem = runtime.get_idempotency_record_sync(IDEMPOTENCY_KEY, SIDE_EFFECT_KEY)
    assert idem is not None

    # --- task_id ---
    assert identity["task_id"] == TASK_ID
    assert receipt.task_id == TASK_ID
    assert rr.task_id == TASK_ID
    assert idem.task_id == TASK_ID

    # --- run_id (spine EvidenceReceipt carries it as span_id) ---
    assert identity["run_id"] == RUN_ID
    assert receipt.span_id == RUN_ID
    assert rr.run_id == RUN_ID
    assert idem.run_id == RUN_ID

    # --- trace_id ---
    assert identity["trace_id"] == TRACE_ID
    assert receipt.trace_id == TRACE_ID
    assert rr.trace_id == TRACE_ID
    assert idem.trace_id == TRACE_ID

    # --- correlation_id (spine receipt keeps it in attributes) ---
    assert identity["correlation_id"] == CORRELATION_ID
    assert receipt.attributes["correlation_id"] == CORRELATION_ID
    assert rr.correlation_id == CORRELATION_ID
    assert idem.correlation_id == CORRELATION_ID

    # --- idempotency_key ---
    assert identity["idempotency_key"] == IDEMPOTENCY_KEY
    assert rr.idempotency_key == IDEMPOTENCY_KEY
    assert idem.idempotency_key == IDEMPOTENCY_KEY


# ---------------------------------------------------------------------------
# 5. Retry with same identity does not create a second RuntimeReceipt
# ---------------------------------------------------------------------------


async def test_submit_via_spine_retry_does_not_create_second_runtime_receipt(
    registry: CardRegistry, runtime: RuntimeStateStore
) -> None:
    bridge, _ = _make_bridge(registry, runtime)

    # Two dispatches sharing the same fixed ExecutionIdentity.
    await bridge.submit_via_spine(_task())
    await bridge.submit_via_spine(_task())

    task_receipts = await runtime.list_runtime_receipts(
        run_id=RUN_ID, receipt_type="a2a_task", limit=50
    )
    assert len(task_receipts) == 1, (
        "retry created a second 'a2a_task' RuntimeReceipt -- exactly-once "
        f"must be enforced via IdempotencyRecord; got {len(task_receipts)}"
    )

    record = runtime.get_idempotency_record_sync(IDEMPOTENCY_KEY, SIDE_EFFECT_KEY)
    assert record is not None
    assert record.status == "completed"


# ---------------------------------------------------------------------------
# 6. Failure path: still exactly one EvidenceReceipt and one RuntimeReceipt
# ---------------------------------------------------------------------------


async def test_submit_via_spine_failure_still_has_one_evidence_and_one_runtime_receipt(
    registry: CardRegistry, runtime: RuntimeStateStore
) -> None:
    bridge, _ = _make_bridge(registry, runtime, handler=_failure_handler)

    result, receipt = await bridge.submit_via_spine(_task())

    # One spine EvidenceReceipt, marked failed.
    assert isinstance(receipt, EvidenceReceipt)
    assert receipt.status == "failed"
    assert result.status == A2ATaskStatus.FAILED

    # Still exactly one persisted 'a2a_task' RuntimeReceipt, no double write.
    task_receipts = await runtime.list_runtime_receipts(
        run_id=RUN_ID, receipt_type="a2a_task", limit=50
    )
    assert len(task_receipts) == 1, (
        f"failure path persisted {len(task_receipts)} 'a2a_task' "
        "RuntimeReceipts; expected 1"
    )
    assert task_receipts[0].receipt_id == (
        f"rr_{RUN_ID}_a2a_{A2ATaskStatus.FAILED.value}"
    )

    # No 'dispatch_evidence' second write on the failure path either.
    dispatch_evidence = await runtime.list_runtime_receipts(
        run_id=RUN_ID, receipt_type="dispatch_evidence", limit=50
    )
    assert dispatch_evidence == []


# ---------------------------------------------------------------------------
# 7. receipt_json projection is not the source of truth
# ---------------------------------------------------------------------------


async def test_receipt_json_projection_is_not_source_of_truth(
    registry: CardRegistry, runtime: RuntimeStateStore
) -> None:
    """Empty delegation_runs.receipt_json must NOT imply persistence failed.

    Canonical persistence is RuntimeReceipt + IdempotencyRecord. The
    spine dispatch path persists those directly via A2AServer.submit()
    and never writes the delegation_runs.receipt_json blob, so that blob
    is absent/empty here -- yet persistence fully succeeded. If it is ever
    populated later it is a projection/cache, not the source of truth.
    """
    bridge, _ = _make_bridge(registry, runtime)

    await bridge.submit_via_spine(_task())

    # Canonical persistence succeeded.
    task_receipts = await runtime.list_runtime_receipts(
        run_id=RUN_ID, receipt_type="a2a_task", limit=50
    )
    assert len(task_receipts) == 1

    record = runtime.get_idempotency_record_sync(IDEMPOTENCY_KEY, SIDE_EFFECT_KEY)
    assert record is not None
    assert record.status == "completed"

    # The delegation_runs.receipt_json projection is NOT required for this
    # path. Read it directly; whether it is empty or absent, canonical
    # persistence above is unaffected. Absence here is correct, not a failure.
    receipt_json_value = _read_receipt_json_blob(runtime, TASK_ID)
    assert receipt_json_value in (None, "", "{}"), (
        "spine dispatch path should not treat receipt_json as source of "
        f"truth; found unexpected blob: {receipt_json_value!r}"
    )


def _read_receipt_json_blob(runtime: RuntimeStateStore, task_id: str):
    """Read delegation_runs.receipt_json directly, tolerating absence.

    Returns None if the delegation_runs table or row or column is not
    present in this path -- all of which are valid, because the canonical
    persistence is RuntimeReceipt + IdempotencyRecord, not this blob.
    """
    import sqlite3

    try:
        with sqlite3.connect(runtime.db_path) as db:
            db.row_factory = sqlite3.Row
            # Column may not exist; guard with a pragma check.
            cols = {
                row[1]
                for row in db.execute("PRAGMA table_info(delegation_runs)").fetchall()
            }
            if "receipt_json" not in cols:
                return None
            row = db.execute(
                "SELECT receipt_json FROM delegation_runs WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                return None
            return row["receipt_json"]
    except sqlite3.OperationalError:
        # delegation_runs table absent in this path -> not source of truth.
        return None
