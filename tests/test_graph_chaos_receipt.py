"""JOINT chaos receipt — Phase 0b gate (dharmagraph-engine-2026-07, spec §3).

kill -9 -> reboot -> reconcile -> ZERO double provider calls, end-to-end
across BOTH Phase 0b halves on main:

- the reconciler lane (#798): ``graph.reconciler.GraphReconciler`` boot scan
  classifies orphans with the existing failure_code vocabulary
  (``claim_timeout`` / ``dispatch_dropoff``), quarantines retry-exhausted
  rows (tally never hidden), settles torn windows FROM the receipt, and
  stamps ``recovered_at``;
- the invoker lane (#799/#800): ``graph.durable_invoker.wrap_invoker``
  guarantees the requeued dispatch re-executes exactly once (CAS takeover of
  the dead holder's claim row) and a replay after success memoizes with zero
  provider calls even though crash-requeue RE-MINTS the ExecutionIdentity.

Deterministic per the DST seed discipline: the scenario is driven through
``graph.effects.SimulatedEffects`` and a fixed base time; the same seed on a
fresh database replays the exact semantic trace.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm.graph.durable_invoker import (
    claim_idempotency_key,
    persist_evidence_receipt,
    wrap_invoker,
)
from dharma_swarm.graph.effects import SimulatedEffects
from dharma_swarm.graph.reconciler import (
    FAILURE_CODE_DIED_MID_DISPATCH,
    FAILURE_CODE_NEVER_STARTED,
    QUARANTINE_REASON,
    GraphReconciler,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision

NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)
AGENT = "agent-chaos"


def _key(task_id: str) -> str:
    return f"invoke_agent:{task_id}:{AGENT}"


def _identity(task_id: str, mint: str) -> ExecutionIdentity:
    """Each crash-requeue re-mints run/idempotency ids — the memo contract
    must survive this."""
    return ExecutionIdentity.new(
        task_id=task_id,
        agent_id=AGENT,
        run_id=f"run-{task_id}-{mint}",
        claim_id=f"claim-{task_id}-{mint}",
        idempotency_key=f"idem-{task_id}-{mint}",
    )


def _insert_run(
    store: RuntimeStateStore,
    run_id: str,
    task_id: str,
    *,
    status: str = "running",
    claim_id: str = "",
    receipt_json: str | None = None,
) -> None:
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs (run_id, task_id, claim_id, assigned_to,"
            " status, started_at, metadata_json, receipt_json)"
            " VALUES (?, ?, ?, ?, ?, ?, '{}', ?)",
            (
                run_id,
                task_id,
                claim_id,
                AGENT,
                status,
                (NOW - timedelta(minutes=10)).isoformat(),
                receipt_json,
            ),
        )
        db.commit()


def _insert_claim(
    store: RuntimeStateStore,
    claim_id: str,
    task_id: str,
    *,
    status: str = "running",
    acked: bool = True,
    retry_count: int = 0,
) -> None:
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO task_claims (claim_id, task_id, agent_id, status,"
            " claimed_at, acked_at, heartbeat_at, stale_after, retry_count)"
            " VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)",
            (
                claim_id,
                task_id,
                AGENT,
                status,
                (NOW - timedelta(minutes=10)).isoformat(),
                (NOW - timedelta(minutes=9)).isoformat() if acked else None,
                (NOW - timedelta(minutes=5)).isoformat(),  # stale_after < NOW
                retry_count,
            ),
        )
        db.commit()


def _row(store: RuntimeStateStore, table: str, key_col: str, key: str) -> sqlite3.Row:
    with sqlite3.connect(store.db_path) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            f"SELECT * FROM {table} WHERE {key_col} = ?", (key,)  # noqa: S608 — test-only, fixed identifiers
        ).fetchone()


class _CountingInner:
    def __init__(self, task_id: str) -> None:
        self.calls = 0
        self._task_id = task_id

    async def __call__(self, task, agent_id, context_id, routing):
        self.calls += 1
        return EvidenceReceipt(
            task_id=self._task_id,
            agent_id=agent_id,
            provider_attempted=True,
            status="ok",
            attributes={"side_effect_key": _key(self._task_id)},
        )


async def _dispatch(
    store: RuntimeStateStore,
    effects: SimulatedEffects,
    inner: _CountingInner,
    task_id: str,
    mint: str,
):
    invoker = wrap_invoker(
        inner,
        store=store,
        identity=_identity(task_id, mint),
        side_effect_key=_key(task_id),
        stale_after_seconds=60.0,
        effects=effects,
    )
    receipt = await invoker(
        task={"id": task_id, "agent_id": AGENT},
        agent_id=AGENT,
        context_id="ctx-chaos",
        routing=RoutingDecision(agent_id=AGENT, task_id=task_id),
    )
    return invoker, receipt


async def _chaos_scenario(seed: int, db_path: Path) -> list[tuple]:
    """One full kill-9 -> reboot -> reconcile -> retry -> replay run.

    Returns the semantic event trace (statuses, failure codes, call counts —
    no timestamps) so two same-seed runs compare equal.
    """
    trace: list[tuple] = [("seed", seed)]
    store = RuntimeStateStore(db_path)
    chain_path = db_path.with_name(f"{db_path.stem}-machine-chain.jsonl")
    store.init_db_sync()
    # Simulated clock starts at the wall-clock the store stamps rows with,
    # then jumps an hour: the dead holder's claim rows are stale by the
    # injected clock, deterministically.
    effects = SimulatedEffects(seed, start=datetime.now(timezone.utc))
    effects.advance(3600)

    dropoff_inner = _CountingInner("task-dropoff")
    torn_inner = _CountingInner("task-torn")

    # ---- crash snapshot (what kill -9 leaves behind) -----------------------
    # V1 died-mid-dispatch: in-flight rows + a 'started' idempotency claim
    # row, NO receipt — the process died inside the provider call.
    _insert_run(store, "run-dropoff", "task-dropoff", claim_id="claim-dropoff")
    _insert_claim(store, "claim-dropoff", "task-dropoff", acked=True)
    dead = _identity("task-dropoff", "boot1").with_updates(
        idempotency_key=claim_idempotency_key(_key("task-dropoff"))
    )
    await store.try_begin_idempotent_side_effect(dead, _key("task-dropoff"), metadata={})

    # V2 torn window: the provider SUCCEEDED and the receipt was persisted,
    # but the crash hit before run/claim bookkeeping completed. Produce the
    # receipt through the real wrapped invoker (provider call #1 for this
    # task), persist it, then leave run/claim in-flight.
    _insert_run(
        store,
        "run-task-torn-boot1",
        "task-torn",
        claim_id="claim-task-torn-boot1",
    )
    _insert_claim(store, "claim-task-torn-boot1", "task-torn", acked=True)
    _, torn_receipt = await _dispatch(store, effects, torn_inner, "task-torn", "boot1")
    assert await persist_evidence_receipt(
        torn_receipt,
        store,
        task_id="task-torn",
        machine_receipt_path=chain_path,
    )

    # V3 never-started: claimed but no ack/heartbeat before the crash.
    _insert_run(store, "run-ns", "task-ns", status="claimed", claim_id="claim-ns")
    _insert_claim(store, "claim-ns", "task-ns", status="claimed", acked=False)

    # V4 retry-exhausted: died mid-dispatch with retries used up.
    _insert_run(store, "run-q", "task-q", claim_id="claim-q")
    _insert_claim(store, "claim-q", "task-q", acked=True, retry_count=3)

    # ---- boot 2: reconcile (the reconciler lane, #798) ----------------------
    report = await GraphReconciler(store, max_retries=3).reconcile(now=NOW)
    trace.append(("reconcile", tuple(sorted(report.summary().items()))))
    trace.append(("requeued", tuple(sorted(report.requeued_runs))))
    trace.append(("quarantined", tuple(sorted(report.quarantined_runs))))
    trace.append(("from_receipt", tuple(sorted(report.completed_from_receipt))))
    assert report.errors == []

    for run_id, claim_id, want_status, want_code in (
        ("run-dropoff", "claim-dropoff", "failed", FAILURE_CODE_DIED_MID_DISPATCH),
        ("run-ns", "claim-ns", "failed", FAILURE_CODE_NEVER_STARTED),
    ):
        run = _row(store, "delegation_runs", "run_id", run_id)
        claim = _row(store, "task_claims", "claim_id", claim_id)
        assert run["status"] == want_status and run["failure_code"] == want_code
        assert claim["recovered_at"], f"{claim_id} must be stamped recovered_at"
        assert claim["status"] == "recovered"
        trace.append((run_id, run["status"], run["failure_code"], "recovered"))

    q_run = _row(store, "delegation_runs", "run_id", "run-q")
    assert q_run["quarantined_at"] and q_run["quarantine_reason"] == QUARANTINE_REASON
    assert _row(store, "task_claims", "claim_id", "claim-q")["recovered_at"]
    trace.append(("run-q", "quarantined", QUARANTINE_REASON))

    torn_run = _row(store, "delegation_runs", "run_id", "run-task-torn-boot1")
    torn_claim = _row(
        store, "task_claims", "claim_id", "claim-task-torn-boot1"
    )
    assert torn_run["status"] == "completed", "receipt is ground truth"
    assert torn_claim["recovered_at"] and torn_claim["status"] == "completed"
    trace.append(("run-torn", torn_run["status"], "receipt_settled"))

    # ---- retry after requeue (the invoker lane, #799) ------------------------
    # The requeued dropoff dispatch arrives with a RE-MINTED identity. The
    # dead holder's 'started' claim row is stale by the injected clock, so
    # the CAS takeover admits exactly this one retry.
    retry_invoker, retry_receipt = await _dispatch(
        store, effects, dropoff_inner, "task-dropoff", "boot2"
    )
    assert retry_invoker.memo_hit is False
    assert retry_receipt.status == "ok"
    assert dropoff_inner.calls == 1, "retry must execute the provider exactly once"
    _insert_run(
        store,
        "run-task-dropoff-boot2",
        "task-dropoff",
        claim_id="claim-task-dropoff-boot2",
    )
    assert await persist_evidence_receipt(
        retry_receipt,
        store,
        task_id="task-dropoff",
        machine_receipt_path=chain_path,
    )
    trace.append(("retry", "executed_once", dropoff_inner.calls))

    # ---- replays (memo across re-minted identity => ZERO double calls) -------
    replay_invoker, replay_receipt = await _dispatch(
        store, effects, dropoff_inner, "task-dropoff", "boot3"
    )
    assert replay_invoker.memo_hit is True
    assert str(replay_receipt.receipt_id) == str(retry_receipt.receipt_id)
    assert dropoff_inner.calls == 1, "replay must NOT double-call the provider"

    torn_replay_invoker, torn_replay_receipt = await _dispatch(
        store, effects, torn_inner, "task-torn", "boot2"
    )
    assert torn_replay_invoker.memo_hit is True
    assert str(torn_replay_receipt.receipt_id) == str(torn_receipt.receipt_id)
    assert torn_inner.calls == 1, "settled torn window must NOT re-execute"
    trace.append(
        ("provider_calls_total", dropoff_inner.calls + torn_inner.calls)  # == 2
    )
    trace.append(("memo_hits", replay_invoker.memo_hit, torn_replay_invoker.memo_hit))

    # ---- receipts intact ------------------------------------------------------
    for task_id, wanted_receipt in (
        ("task-dropoff", retry_receipt),
        ("task-torn", torn_receipt),
    ):
        with sqlite3.connect(store.db_path) as db:
            blobs = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT receipt_json FROM delegation_runs WHERE task_id = ?"
                    " AND receipt_json IS NOT NULL AND receipt_json != ''",
                    (task_id,),
                ).fetchall()
            ]
        assert blobs, f"{task_id}: persisted receipt must survive the chaos"
        assert any(b["receipt_id"] == str(wanted_receipt.receipt_id) for b in blobs)
        assert all(
            b["attributes"]["side_effect_key"] == _key(task_id) for b in blobs
        )
        trace.append((task_id, "receipts_intact", len(blobs)))

    return trace


@pytest.mark.parametrize("seed", [42, 7])
async def test_chaos_receipt_kill9_reconcile_zero_double_calls(seed, tmp_path):
    """THE Phase 0b chaos receipt: kill -9 -> reboot -> reconcile -> retry ->
    replay, with requeue-or-quarantine per the failure_code vocabulary,
    recovered_at stamped, zero double provider calls, receipts intact — and
    the whole trace replays exactly from the seed."""
    first = await _chaos_scenario(seed, tmp_path / "runtime_a.db")
    second = await _chaos_scenario(seed, tmp_path / "runtime_b.db")
    assert first == second, "same seed + fresh db must replay the exact chaos trace"
    assert ("provider_calls_total", 2) in first  # one per task, ever


async def test_chaos_receipt_concurrent_requeue_still_single_execution(tmp_path):
    """Belt-and-braces: TWO requeued dispatch attempts race after the boot
    reconcile (e.g. tick reconcile + operator retry) — the claim CAS admits
    exactly one provider call."""
    import asyncio

    store = RuntimeStateStore(tmp_path / "runtime.db")
    store.init_db_sync()
    effects = SimulatedEffects(1, start=datetime.now(timezone.utc))
    effects.advance(3600)

    _insert_run(store, "run-race", "task-race", claim_id="claim-race")
    _insert_claim(store, "claim-race", "task-race", acked=True)
    dead = _identity("task-race", "boot1").with_updates(
        idempotency_key=claim_idempotency_key(_key("task-race"))
    )
    await store.try_begin_idempotent_side_effect(dead, _key("task-race"), metadata={})
    await GraphReconciler(store).reconcile(now=NOW)

    inner = _CountingInner("task-race")
    results = await asyncio.gather(
        _dispatch(store, effects, inner, "task-race", "retry-a"),
        _dispatch(store, effects, inner, "task-race", "retry-b"),
        return_exceptions=True,
    )
    winners = [r for r in results if not isinstance(r, BaseException)]
    # Sequenced retries may both succeed (second memoizes); a true race loses
    # one cleanly. Either way the provider ran exactly once.
    assert inner.calls == 1, "exactly one provider execution across racing retries"
    assert 1 <= len(winners) <= 2
    for _invoker, receipt in winners:
        assert receipt.status == "ok"
