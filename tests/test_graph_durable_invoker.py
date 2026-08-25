"""Phase 0b durable invoker: exactly-once dispatch on the spine's invoke path.

Verifies dharma_swarm/graph/durable_invoker.py (dharmagraph-engine-2026-07,
spec §3 Phase 0b): memo hit returns the prior EvidenceReceipt with zero
provider calls; concurrent double-begin loses one cleanly; inner exceptions
never falsely complete the idempotency record (retry re-executes); the
graph-run key form is stable; the A2A path is untouched.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from dharma_swarm.graph.durable_invoker import (
    DuplicateDispatchInFlight,
    claim_idempotency_key,
    derive_graph_side_effect_key,
    persist_evidence_receipt,
    receipt_from_dict,
    wrap_invoker,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision

TASK_ID = "task-durable-1"
AGENT_ID = "agent-durable-1"
KEY = f"invoke_agent:{TASK_ID}:{AGENT_ID}"
CLAIM_KEY = claim_idempotency_key(KEY)


def _identity(run_suffix: str = "a") -> ExecutionIdentity:
    return ExecutionIdentity.new(
        task_id=TASK_ID,
        agent_id=AGENT_ID,
        trace_id=f"trace-{run_suffix}",
        run_id=f"run-{run_suffix}",
        claim_id=f"claim-{run_suffix}",
        idempotency_key=f"idem-{run_suffix}",
    )


def _routing() -> RoutingDecision:
    return RoutingDecision(agent_id=AGENT_ID, task_id=TASK_ID)


class StubInner:
    """Counting inner invoker; optionally raises, blocks, or fails softly."""

    def __init__(
        self,
        *,
        raise_exc: Exception | None = None,
        receipt_status: str = "ok",
        gate: asyncio.Event | None = None,
    ) -> None:
        self.calls = 0
        self._raise_exc = raise_exc
        self._receipt_status = receipt_status
        self._gate = gate

    async def __call__(self, task, agent_id, context_id, routing):
        self.calls += 1
        if self._gate is not None:
            await self._gate.wait()
        if self._raise_exc is not None:
            raise self._raise_exc
        return EvidenceReceipt(
            task_id=str(task.get("id", "")),
            agent_id=agent_id,
            operation="invoke_agent",
            provider_attempted=True,
            status=self._receipt_status,
            error_source="none" if self._receipt_status == "ok" else "provider_failed",
            attributes={"side_effect_key": KEY},
        )


async def _invoke(invoker):
    return await invoker(
        task={"id": TASK_ID, "agent_id": AGENT_ID},
        agent_id=AGENT_ID,
        context_id="ctx-1",
        routing=_routing(),
    )


async def _wait_for_claim_losers(tasks, inners) -> None:
    """Keep the winner blocked until every overlapping contender settles."""
    for _ in range(200):
        if sum(inner.calls for inner in inners) == 1 and sum(
            task.done() for task in tasks
        ) == len(tasks) - 1:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("concurrent claim losers did not settle behind the live lease")


@pytest.fixture
def store(tmp_path: Path) -> RuntimeStateStore:
    return RuntimeStateStore(tmp_path / "runtime.db")


async def test_first_call_executes_and_completes_record(store):
    inner = StubInner()
    invoker = wrap_invoker(inner, store=store, identity=_identity(), side_effect_key=KEY)
    receipt = await _invoke(invoker)
    assert inner.calls == 1
    assert receipt.status == "ok"
    assert invoker.memo_hit is False
    record = await store.get_idempotency_record(CLAIM_KEY, KEY)
    assert record is not None and record.status == "completed"
    assert record.result_receipt_id == str(receipt.receipt_id)
    assert receipt.attributes["idempotency_key"] == record.idempotency_key == CLAIM_KEY
    assert receipt.attributes["dispatch_idempotency_key"] == _identity().idempotency_key
    assert receipt.attributes["run_id"] == record.run_id
    # The receipt is memoized in the record so a replay can return it.
    assert record.metadata["receipt"]["receipt_id"] == str(receipt.receipt_id)


async def test_memo_hit_returns_prior_receipt_with_zero_inner_calls(store):
    first_inner = StubInner()
    first = wrap_invoker(
        first_inner,
        store=store,
        identity=_identity(),
        side_effect_key=KEY,
        result_provider=lambda: "PRIOR_RESULT",
    )
    prior = await _invoke(first)
    assert first_inner.calls == 1

    replay_inner = StubInner()
    replay = wrap_invoker(
        replay_inner, store=store, identity=_identity(), side_effect_key=KEY
    )
    receipt = await _invoke(replay)
    assert replay_inner.calls == 0, "memo hit must not call the provider"
    assert replay.memo_hit is True
    assert replay.memo_result == "PRIOR_RESULT"
    assert str(receipt.receipt_id) == str(prior.receipt_id)
    assert receipt.task_id == TASK_ID


async def test_memo_hit_preserves_structured_result_type(store):
    """A dict/list result must replay with its original TYPE, not str(...)
    (dispatch return contract holds across memo hits)."""
    structured = {"answer": 42, "items": ["a", "b"], "nested": {"ok": True}}
    first = wrap_invoker(
        StubInner(),
        store=store,
        identity=_identity(),
        side_effect_key=KEY,
        result_provider=lambda: structured,
    )
    await _invoke(first)

    replay = wrap_invoker(
        StubInner(), store=store, identity=_identity(), side_effect_key=KEY
    )
    await _invoke(replay)
    assert replay.memo_hit is True
    assert replay.memo_result == structured
    assert isinstance(replay.memo_result, dict)
    assert replay.audit_failures == 0


async def test_memo_hit_survives_reminted_identity(store):
    """Crash-requeue: the requeued dispatch arrives with a NEW ExecutionIdentity
    (new run/idempotency key) but the SAME deterministic side_effect_key —
    the memo must still hit."""
    first = wrap_invoker(
        StubInner(),
        store=store,
        identity=_identity("a"),
        side_effect_key=KEY,
        result_provider=lambda: "RESULT_A",
    )
    prior = await _invoke(first)

    replay_inner = StubInner()
    replay = wrap_invoker(
        replay_inner, store=store, identity=_identity("b"), side_effect_key=KEY
    )
    receipt = await _invoke(replay)
    assert replay_inner.calls == 0
    assert replay.memo_hit is True
    assert replay.memo_result == "RESULT_A"
    assert str(receipt.receipt_id) == str(prior.receipt_id)


async def test_concurrent_double_begin_loses_one_cleanly(store):
    gate = asyncio.Event()
    winner_inner = StubInner(gate=gate)
    winner = wrap_invoker(
        winner_inner, store=store, identity=_identity(), side_effect_key=KEY
    )
    loser_inner = StubInner()
    loser = wrap_invoker(
        loser_inner, store=store, identity=_identity(), side_effect_key=KEY
    )

    winner_task = asyncio.create_task(_invoke(winner))
    # Let the winner reach its begin + provider call before the loser starts.
    for _ in range(50):
        await asyncio.sleep(0.01)
        if winner_inner.calls:
            break
    assert winner_inner.calls == 1

    with pytest.raises(DuplicateDispatchInFlight):
        await _invoke(loser)
    assert loser_inner.calls == 0, "the loser must not double-call the provider"

    gate.set()
    receipt = await winner_task
    assert receipt.status == "ok"
    assert winner_inner.calls == 1


async def test_inner_exception_marks_failed_and_retry_reexecutes(store):
    boom_inner = StubInner(raise_exc=RuntimeError("boom"))
    first = wrap_invoker(
        boom_inner, store=store, identity=_identity(), side_effect_key=KEY
    )
    with pytest.raises(RuntimeError, match="boom"):
        await _invoke(first)
    record = await store.get_idempotency_record(CLAIM_KEY, KEY)
    assert record is not None
    assert record.status == "failed", "an inner exception must never complete the record"

    retry_inner = StubInner()
    retry = wrap_invoker(
        retry_inner, store=store, identity=_identity(), side_effect_key=KEY
    )
    receipt = await _invoke(retry)
    assert retry_inner.calls == 1, "a failed attempt must be retryable"
    assert receipt.status == "ok"
    record = await store.get_idempotency_record(CLAIM_KEY, KEY)
    assert record is not None and record.status == "completed"


async def test_non_ok_receipt_is_retryable_not_memoized(store):
    failed_inner = StubInner(receipt_status="failed")
    first = wrap_invoker(
        failed_inner, store=store, identity=_identity(), side_effect_key=KEY
    )
    receipt = await _invoke(first)
    assert receipt.status == "failed"
    record = await store.get_idempotency_record(CLAIM_KEY, KEY)
    assert record is not None and record.status == "failed"

    retry_inner = StubInner()
    retry = wrap_invoker(
        retry_inner, store=store, identity=_identity(), side_effect_key=KEY
    )
    receipt = await _invoke(retry)
    assert retry_inner.calls == 1
    assert receipt.status == "ok"


def _claim(identity):
    return identity.with_updates(idempotency_key=CLAIM_KEY)


async def test_stale_started_record_is_taken_over(store):
    """A record stuck 'started' by a dead process (crash mid-provider-call)
    is taken over once it ages past stale_after_seconds — crash-resume."""
    identity = _identity()
    await store.try_begin_idempotent_side_effect(_claim(identity), KEY, metadata={})
    # Age the record far past any stale threshold.
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE idempotency_records SET updated_at = '2020-01-01T00:00:00+00:00'"
            " WHERE side_effect_key = ?",
            (KEY,),
        )
        db.commit()

    inner = StubInner()
    invoker = wrap_invoker(
        inner,
        store=store,
        identity=identity,
        side_effect_key=KEY,
        stale_after_seconds=1.0,
    )
    receipt = await _invoke(invoker)
    assert inner.calls == 1, "a stale in-flight record must be taken over"
    assert receipt.status == "ok"
    record = await store.get_idempotency_record(CLAIM_KEY, KEY)
    assert record is not None and record.status == "completed"


async def test_fresh_started_record_blocks_without_stale_config(store):
    identity = _identity()
    await store.try_begin_idempotent_side_effect(_claim(identity), KEY, metadata={})
    inner = StubInner()
    invoker = wrap_invoker(
        inner, store=store, identity=identity, side_effect_key=KEY
    )
    with pytest.raises(DuplicateDispatchInFlight):
        await _invoke(invoker)
    assert inner.calls == 0


async def test_concurrent_stale_takeover_reclaims_atomically(store):
    """Greptile P1 regression: N recovery workers hitting the same stale
    'started' row must NOT all fall through — the CAS re-claim lets exactly
    one execute; the rest lose cleanly."""
    identity = _identity()
    await store.try_begin_idempotent_side_effect(_claim(identity), KEY, metadata={})
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "UPDATE idempotency_records SET updated_at = '2020-01-01T00:00:00+00:00'"
            " WHERE side_effect_key = ?",
            (KEY,),
        )
        db.commit()
    stale_snapshot = await store.get_idempotency_record(CLAIM_KEY, KEY)
    assert stale_snapshot is not None

    gate = asyncio.Event()
    inners = [StubInner(gate=gate) for _ in range(3)]
    invokers = [
        wrap_invoker(
            inner,
            store=store,
            identity=_identity(f"w{i}"),
            side_effect_key=KEY,
            stale_after_seconds=60.0,
        )
        for i, inner in enumerate(inners)
    ]
    tasks = [asyncio.create_task(_invoke(inv)) for inv in invokers]
    await _wait_for_claim_losers(tasks, inners)
    assert not await store._mark_idempotency_record_stale(stale_snapshot)
    # Reclaim transfers the row to the winning recovery identity, so the
    # superseded owner now fails the stronger identity fence before its stale
    # ownership token is considered.
    with pytest.raises(ValueError, match="identity conflicts"):
        await store.complete_idempotent_side_effect(
            _claim(identity),
            KEY,
            expected_updated_at=stale_snapshot.updated_at,
        )
    gate.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)

    receipts = [r for r in results if not isinstance(r, BaseException)]
    losers = [r for r in results if isinstance(r, DuplicateDispatchInFlight)]
    unexpected = [
        r for r in results
        if isinstance(r, BaseException) and not isinstance(r, DuplicateDispatchInFlight)
    ]
    assert unexpected == []
    assert sum(inner.calls for inner in inners) == 1, "exactly one provider call"
    assert len(receipts) == 1 and len(losers) == 2
    record = await store.get_idempotency_record(CLAIM_KEY, KEY)
    assert record is not None and record.status == "completed"
    assert record.updated_at > stale_snapshot.updated_at


async def test_concurrent_cross_identity_double_begin_loses_one(store):
    """Codex P1 regression: two concurrent dispatches with DIFFERENT
    (re-minted) identities share one deterministic claim row — exactly one
    executes the provider; the other loses cleanly."""
    gate = asyncio.Event()
    winner_inner = StubInner(gate=gate)
    winner = wrap_invoker(
        winner_inner, store=store, identity=_identity("a"), side_effect_key=KEY
    )
    loser_inner = StubInner()
    loser = wrap_invoker(
        loser_inner, store=store, identity=_identity("b"), side_effect_key=KEY
    )

    winner_task = asyncio.create_task(_invoke(winner))
    for _ in range(50):
        await asyncio.sleep(0.01)
        if winner_inner.calls:
            break
    assert winner_inner.calls == 1

    with pytest.raises(DuplicateDispatchInFlight):
        await _invoke(loser)
    assert loser_inner.calls == 0, "re-minted identity must not double-execute"

    gate.set()
    receipt = await winner_task
    assert receipt.status == "ok"
    assert winner_inner.calls == 1


async def test_value_error_foreign_live_owner_never_calls_provider(store):
    """A re-minted identity rejected by the store must inspect the live row
    and stop before the provider, never reinterpret authority as an outage."""
    owner = _claim(_identity("live-owner"))
    operation_hash = hashlib.sha256(
        f"invoke_agent:{TASK_ID}:{AGENT_ID}".encode("utf-8")
    ).hexdigest()
    assert await store.try_begin_idempotent_side_effect(
        owner,
        KEY,
        metadata={"operation_hash": operation_hash, "task_id": TASK_ID},
    )
    live_record = await store.get_idempotency_record(CLAIM_KEY, KEY)
    assert live_record is not None and live_record.status == "started"

    inner = StubInner()
    retry = wrap_invoker(
        inner,
        store=store,
        identity=_identity("foreign-live"),
        side_effect_key=KEY,
    )
    with pytest.raises(DuplicateDispatchInFlight):
        await _invoke(retry)

    assert inner.calls == 0, "a foreign live owner must fence the provider"
    assert await store.get_idempotency_record(CLAIM_KEY, KEY) == live_record


async def test_reminted_failed_retry_operation_hash_conflict_never_calls_provider(
    store,
):
    """Bypassing duplicate-begin via retry CAS must not bypass its operation
    fingerprint check."""
    owner = _claim(_identity("operation-owner"))
    metadata = {"operation_hash": "foreign-operation", "task_id": TASK_ID}
    assert await store.try_begin_idempotent_side_effect(
        owner,
        KEY,
        metadata=metadata,
    )
    started = await store.get_idempotency_record(CLAIM_KEY, KEY)
    assert started is not None
    failed = await store.complete_idempotent_side_effect(
        owner,
        KEY,
        status="failed",
        metadata=metadata,
        expected_updated_at=started.updated_at,
    )

    inner = StubInner()
    retry = wrap_invoker(
        inner,
        store=store,
        identity=_identity("operation-retry"),
        side_effect_key=KEY,
    )
    with pytest.raises(ValueError, match="operation_hash conflict"):
        await _invoke(retry)

    assert inner.calls == 0, "an operation conflict must fence the provider"
    assert await store.get_idempotency_record(CLAIM_KEY, KEY) == failed


async def test_oversized_result_declines_memo_and_reexecutes(store):
    """Codex + greptile regression: a result over the memo cap is NEVER
    replayed truncated or as None on a completed task — the replay declines
    the memo (reason observable) and re-executes the provider."""
    huge = "x" * 200_000
    first = wrap_invoker(
        StubInner(),
        store=store,
        identity=_identity(),
        side_effect_key=KEY,
        result_provider=lambda: huge,
    )
    await _invoke(first)

    replay_inner = StubInner()
    replay = wrap_invoker(
        replay_inner,
        store=store,
        identity=_identity(),
        side_effect_key=KEY,
        result_provider=lambda: "RECOVERED",
    )
    receipt = await _invoke(replay)
    assert replay.memo_hit is False, "unmemoizable result must decline replay"
    assert replay.memo_result_omitted == "exceeds_result_cap"
    assert replay_inner.calls == 1, "provider re-executes for the real result"
    assert receipt.status == "ok"

    memo_inner = StubInner()
    memo = wrap_invoker(
        memo_inner, store=store, identity=_identity("memo"), side_effect_key=KEY
    )
    await _invoke(memo)
    assert memo_inner.calls == 0, "replacement result must memoize normally"
    assert memo.memo_hit is True and memo.memo_result == "RECOVERED"


async def test_concurrent_declined_memo_replays_reclaim_atomically(store):
    """Greptile P1 regression: two concurrent replays of a completed-but-
    unmemoizable (oversized) result both decline the memo — the CAS re-claim
    on the completed row must let exactly one re-execute the provider."""
    huge = "x" * 200_000
    first = wrap_invoker(
        StubInner(),
        store=store,
        identity=_identity(),
        side_effect_key=KEY,
        result_provider=lambda: huge,
    )
    await _invoke(first)
    completed_snapshot = await store.get_idempotency_record(CLAIM_KEY, KEY)
    assert completed_snapshot is not None and completed_snapshot.status == "completed"

    gate = asyncio.Event()
    inners = [StubInner(gate=gate) for _ in range(3)]
    invokers = [
        wrap_invoker(
            inner,
            store=store,
            identity=_identity(f"r{i}"),
            side_effect_key=KEY,
            result_provider=lambda: huge,
        )
        for i, inner in enumerate(inners)
    ]
    tasks = [asyncio.create_task(_invoke(inv)) for inv in invokers]
    await _wait_for_claim_losers(tasks, inners)
    gate.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)

    receipts = [r for r in results if not isinstance(r, BaseException)]
    losers = [r for r in results if isinstance(r, DuplicateDispatchInFlight)]
    unexpected = [
        r for r in results
        if isinstance(r, BaseException) and not isinstance(r, DuplicateDispatchInFlight)
    ]
    assert unexpected == []
    assert sum(inner.calls for inner in inners) == 1, (
        "declined memo re-execution must be exactly-once"
    )
    assert len(receipts) == 1 and len(losers) == 2
    completed_after = await store.get_idempotency_record(CLAIM_KEY, KEY)
    assert completed_after is not None
    assert completed_after.updated_at > completed_snapshot.updated_at
    stale_reclaim = await store.try_reclaim_idempotent_side_effect(
        _claim(_identity("late")),
        KEY,
        expected_status="completed",
        expected_updated_at=completed_snapshot.updated_at,
    )
    assert stale_reclaim is False, "an old completed token must not survive ABA"


async def test_fallback_receipt_requires_matching_side_effect_key(store):
    """Codex P2 regression: a delegation_runs receipt with missing/malformed
    attributes must NOT be accepted by task_id alone — it may belong to a
    different dispatch of the same task."""
    import json as _json

    identity = _identity()
    claim = _claim(identity)
    # Simulate a completed claim row whose record metadata lost the receipt
    # (so the fallback path is consulted)...
    await store.try_begin_idempotent_side_effect(claim, KEY, metadata={})
    await store.complete_idempotent_side_effect(claim, KEY, status="completed")
    # ...and a delegation_runs receipt that does NOT name our side_effect_key.
    foreign = EvidenceReceipt(
        task_id=TASK_ID,
        agent_id="someone-else",
        status="ok",
        attributes={
            "run_id": identity.run_id,
            "idempotency_key": CLAIM_KEY,
            "side_effect_key": "invoke_agent:foreign-task:someone-else",
        },
    )
    await store.init_db()
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs (run_id, task_id, assigned_to, status,"
            " started_at, receipt_json) VALUES (?, ?, 'someone-else',"
            " 'completed', '2026-07-05T00:00:00+00:00', ?)",
            (identity.run_id, TASK_ID, _json.dumps(foreign.to_dict(), default=str)),
        )
        db.commit()

    inner = StubInner()
    invoker = wrap_invoker(inner, store=store, identity=_identity("b"), side_effect_key=KEY)
    receipt = await _invoke(invoker)
    # No trustworthy prior receipt -> memo refused -> provider re-executed.
    assert invoker.memo_hit is False
    assert inner.calls == 1
    assert receipt.agent_id == AGENT_ID


async def test_fail_open_without_store_executes_inner():
    inner = StubInner()
    invoker = wrap_invoker(inner, store=None, identity=_identity(), side_effect_key=KEY)
    receipt = await _invoke(invoker)
    assert inner.calls == 1
    assert receipt.status == "ok"
    assert invoker.memo_hit is False


async def test_fail_open_receipt_is_marked_unprotected():
    """A fail-open (unfenced) dispatch must TAG its receipt so the fleet can
    COUNT how often a consequential call runs without idempotency protection —
    the observable prerequisite to a data-driven fail-closed decision
    (pre-1004 hardening: observe blind spots before fencing them)."""
    inner = StubInner()
    invoker = wrap_invoker(inner, store=None, identity=_identity(), side_effect_key=KEY)
    receipt = await _invoke(invoker)
    assert inner.calls == 1
    assert receipt.attributes.get("unprotected_dispatch") is True
    assert receipt.attributes.get("unprotected_reason") == "no_capable_store"


class BeginLostStore:
    """Capable-shaped store whose atomic begin LOSES the claim (returns None)
    and whose record fetch cannot recover it (returns None or raises)."""

    def __init__(self, db_path: Path, *, record_fetch_raises: bool = False) -> None:
        self.db_path = db_path
        self._record_fetch_raises = record_fetch_raises

    async def init_db(self) -> None:
        return None

    async def try_begin_idempotent_side_effect_with_token(self, *args, **kwargs):
        return None

    async def try_reclaim_idempotent_side_effect_with_token(self, *args, **kwargs):
        raise AssertionError("reclaim must not be attempted without a record")

    async def complete_idempotent_side_effect(self, *args, **kwargs):
        raise AssertionError("unfenced completion must be refused before the store")

    async def get_idempotency_record(self, *args, **kwargs):
        if self._record_fetch_raises:
            raise RuntimeError("record fetch failed")
        return None


@pytest.mark.parametrize("record_fetch_raises", [False, True])
async def test_begin_lost_unreclaimed_dispatch_is_marked_unprotected(
    tmp_path: Path, record_fetch_raises: bool
):
    """Begin loses the race (returns None) AND the record is unrecoverable:
    the dispatch still executes (fail-open) but ran with no idempotency fence
    and its completion is refused. That unfenced call must be stamped like the
    other three fail-open branches or the fleet count undercounts exactly the
    store-failure/race blind spots it exists to measure."""
    inner = StubInner()
    store = BeginLostStore(
        tmp_path / "runtime.db", record_fetch_raises=record_fetch_raises
    )
    invoker = wrap_invoker(inner, store=store, identity=_identity(), side_effect_key=KEY)
    receipt = await _invoke(invoker)
    assert inner.calls == 1
    assert receipt.attributes.get("unprotected_dispatch") is True
    assert receipt.attributes.get("unprotected_reason") == "begin_lost_unreclaimed"
    # The unfenced completion was refused and counted, never sent to the store.
    assert invoker.audit_failures == 1


def test_graph_side_effect_key_stability_and_retry_increment():
    base = derive_graph_side_effect_key("run-1", 3, "node-a", 0)
    assert base == derive_graph_side_effect_key("run-1", 3, "node-a", 0)
    assert base.startswith("invoke_agent:graph:")
    # Each retry is its own side effect: retry_count derives a NEW key.
    retry = derive_graph_side_effect_key("run-1", 3, "node-a", 1)
    assert retry != base
    assert derive_graph_side_effect_key("run-2", 3, "node-a", 0) != base
    assert derive_graph_side_effect_key("run-1", 4, "node-a", 0) != base
    assert derive_graph_side_effect_key("run-1", 3, "node-b", 0) != base


def test_receipt_round_trips_through_dict():
    receipt = EvidenceReceipt(
        task_id=TASK_ID,
        agent_id=AGENT_ID,
        status="ok",
        attributes={"side_effect_key": KEY},
    )
    rebuilt = receipt_from_dict(json.loads(json.dumps(receipt.to_dict(), default=str)))
    assert str(rebuilt.receipt_id) == str(receipt.receipt_id)
    assert rebuilt.task_id == receipt.task_id
    assert rebuilt.started_at == receipt.started_at
    assert rebuilt.attributes["side_effect_key"] == KEY


async def test_persist_evidence_receipt_fail_open_and_success(store, caplog, tmp_path):
    import logging

    receipt = EvidenceReceipt(
        task_id=TASK_ID,
        claim_id="claim-a",
        agent_id=AGENT_ID,
        status="ok",
        attributes={"run_id": "run-a"},
    )
    failed_chain = tmp_path / "failed-chain.jsonl"
    # No delegation_runs row yet: persist_receipt raises on 0-row match; the
    # helper fails open with a loud warning, never breaking dispatch.
    await store.init_db()
    with caplog.at_level(logging.WARNING):
        assert (
            await persist_evidence_receipt(
                receipt,
                store,
                task_id=TASK_ID,
                machine_receipt_path=failed_chain,
            )
            is False
        )
    assert any("NOT persisted" in rec.message for rec in caplog.records)
    assert failed_chain.exists()

    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO delegation_runs (run_id, task_id, claim_id, assigned_to,"
            " status, started_at) VALUES ('run-a', ?, 'claim-a', ?, 'running',"
            " '2026-07-05T00:00:00+00:00')",
            (TASK_ID, AGENT_ID),
        )
        db.commit()
    success_chain = tmp_path / "success-chain.jsonl"
    assert (
        await persist_evidence_receipt(
            receipt,
            store,
            task_id=TASK_ID,
            machine_receipt_path=success_chain,
        )
        is True
    )
    with sqlite3.connect(store.db_path) as db:
        row = db.execute(
            "SELECT receipt_json FROM delegation_runs WHERE task_id = ?", (TASK_ID,)
        ).fetchone()
    assert row is not None and json.loads(row[0])["receipt_id"] == str(receipt.receipt_id)
    assert success_chain.exists()


def test_a2a_spine_adapter_untouched():
    """Regression: the A2A invoker has its own idempotency path; the durable
    invoker must not be wired into it."""
    source = (
        Path(__file__).resolve().parents[1]
        / "dharma_swarm"
        / "a2a"
        / "spine_adapter.py"
    ).read_text(encoding="utf-8")
    assert "durable_invoker" not in source
    assert "wrap_invoker" not in source
