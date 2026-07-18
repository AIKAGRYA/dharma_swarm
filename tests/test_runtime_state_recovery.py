from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dharma_swarm.message_bus import MessageBus
from dharma_swarm.models import Message
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.adapters import identity_metadata
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


def _message_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as db:
        return int(db.execute("SELECT COUNT(*) FROM messages").fetchone()[0])


@pytest.mark.asyncio
async def test_idempotency_duplicate_same_operation_does_not_repeat_after_completion(tmp_path: Path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()
    side_effect_key = "unit.side_effect:alpha"
    metadata = {"operation_hash": "hash-alpha", "input": "alpha"}

    assert await store.try_begin_idempotent_side_effect(identity, side_effect_key, metadata=metadata)
    await store.complete_idempotent_side_effect(
        identity,
        side_effect_key,
        result_receipt_id="result-alpha",
        metadata={"result": "ok"},
    )

    assert not await store.try_begin_idempotent_side_effect(identity, side_effect_key, metadata=metadata)

    ledger = await store.get_run_ledger(identity.run_id)
    intents = [r for r in ledger["receipts"] if r.receipt_type == "side_effect_intent"]
    duplicates = [r for r in ledger["receipts"] if r.receipt_type == "idempotency_consumed" and r.status == "duplicate"]
    records = ledger["idempotency_records"]

    assert len(intents) == 1
    assert len(duplicates) == 1
    assert records[0].status == "completed"
    assert records[0].result_receipt_id == "result-alpha"
    assert records[0].metadata["operation_hash"] == "hash-alpha"


@pytest.mark.asyncio
async def test_idempotency_conflicting_operation_hash_fails_before_second_intent(tmp_path: Path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity(idempotency_key="idem-conflict")
    side_effect_key = "unit.side_effect:conflict"

    assert await store.try_begin_idempotent_side_effect(
        identity,
        side_effect_key,
        metadata={"operation_hash": "hash-a"},
    )

    with pytest.raises(ValueError, match="operation_hash conflict"):
        await store.try_begin_idempotent_side_effect(
            identity,
            side_effect_key,
            metadata={"operation_hash": "hash-b"},
        )

    ledger = await store.get_run_ledger(identity.run_id)
    intents = [r for r in ledger["receipts"] if r.receipt_type == "side_effect_intent"]
    conflicts = [r for r in ledger["receipts"] if r.receipt_type == "idempotency_consumed" and r.status == "conflict"]

    assert len(intents) == 1
    assert len(conflicts) == 1


@pytest.mark.asyncio
async def test_idempotency_stale_started_record_is_quarantined_without_repeat(tmp_path: Path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity(idempotency_key="idem-stale")
    side_effect_key = "unit.side_effect:stale"
    metadata = {"operation_hash": "hash-stale"}

    assert await store.try_begin_idempotent_side_effect(identity, side_effect_key, metadata=metadata)

    stale_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with sqlite3.connect(tmp_path / "runtime.db") as db:
        db.execute(
            "UPDATE idempotency_records SET updated_at = ? WHERE idempotency_key = ? AND side_effect_key = ?",
            (stale_time, identity.idempotency_key, side_effect_key),
        )
        db.commit()

    assert not await store.try_begin_idempotent_side_effect(
        identity,
        side_effect_key,
        metadata=metadata,
        stale_after_seconds=60,
    )

    record = await store.get_idempotency_record(identity.idempotency_key, side_effect_key)
    ledger = await store.get_run_ledger(identity.run_id)
    intents = [r for r in ledger["receipts"] if r.receipt_type == "side_effect_intent"]
    stale_receipts = [
        r for r in ledger["receipts"] if r.receipt_type == "idempotency_consumed" and r.status == "stale"
    ]

    assert record is not None
    assert record.status == "stale"
    assert len(intents) == 1
    assert len(stale_receipts) == 1
    assert not await store.was_side_effect_performed(identity.idempotency_key, side_effect_key)


@pytest.mark.asyncio
async def test_message_bus_conflicting_idempotency_key_does_not_insert_second_message(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    bus_path = tmp_path / "messages.db"
    bus = MessageBus(bus_path, runtime_state=runtime, require_identity=True)
    await bus.init_db()

    identity = _identity(
        run_id="run-message-conflict",
        task_id="task-message-conflict",
        idempotency_key="idem-message-conflict",
    )
    metadata = identity_metadata(identity, surface="message_bus")

    first_id = await bus.send(Message(from_agent="alice", to_agent="bob", body="first", metadata=metadata))
    with pytest.raises(ValueError, match="operation_hash conflict"):
        await bus.send(Message(from_agent="alice", to_agent="bob", body="different", metadata=metadata))

    assert _message_count(bus_path) == 1
    assert [message.id for message in await bus.receive("bob")] == [first_id]


@pytest.mark.asyncio
async def test_message_bus_staged_retry_returns_same_receipt(tmp_path: Path) -> None:
    """Retrying send_staged() with the same identity must return the recorded
    receipt instead of re-inserting and hitting the messages.id primary key."""
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    bus_path = tmp_path / "messages.db"
    bus = MessageBus(bus_path, runtime_state=runtime, require_identity=True)
    await bus.init_db()

    identity = _identity(
        run_id="run-staged-retry",
        task_id="task-staged-retry",
        idempotency_key="idem-staged-retry",
    )
    metadata = identity_metadata(identity, surface="message_bus")
    message = Message(from_agent="alice", to_agent="bob", body="staged", metadata=metadata)

    first_id = await bus.send_staged(message, deliver_at_superstep=2)
    retry_id = await bus.send_staged(message, deliver_at_superstep=2)

    assert retry_id == first_id
    assert _message_count(bus_path) == 1
    assert await bus.receive("bob", current_superstep=1) == []
    assert [m.id for m in await bus.receive("bob", current_superstep=2)] == [first_id]


@pytest.mark.asyncio
async def test_message_bus_staged_retry_resumes_insert_after_crash_before_write(tmp_path: Path) -> None:
    """A retry after a crash between begin and INSERT must write the row,
    not fabricate a receipt for a message that was never persisted."""
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    bus_path = tmp_path / "messages.db"
    bus = MessageBus(bus_path, runtime_state=runtime, require_identity=True)
    await bus.init_db()

    identity = _identity(
        run_id="run-staged-crash-insert",
        task_id="task-staged-crash-insert",
        idempotency_key="idem-staged-crash-insert",
    )
    metadata = identity_metadata(identity, surface="message_bus")
    message = Message(from_agent="alice", to_agent="bob", body="staged", metadata=metadata)

    original_retry = bus._run_with_lock_retry

    async def _crash_before_insert(fn):
        raise RuntimeError("crash before insert")

    bus._run_with_lock_retry = _crash_before_insert  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="crash before insert"):
        await bus.send_staged(message, deliver_at_superstep=2)
    bus._run_with_lock_retry = original_retry  # type: ignore[method-assign]
    assert _message_count(bus_path) == 0

    retry_id = await bus.send_staged(message, deliver_at_superstep=2)

    assert retry_id == message.id
    assert _message_count(bus_path) == 1
    assert [m.id for m in await bus.receive("bob", current_superstep=2)] == [message.id]


@pytest.mark.asyncio
async def test_message_bus_staged_retry_completes_after_crash_before_completion(tmp_path: Path) -> None:
    """A retry after a crash between INSERT and completion must return the
    receipt for the already-written row without inserting a duplicate."""
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    bus_path = tmp_path / "messages.db"
    bus = MessageBus(bus_path, runtime_state=runtime, require_identity=True)
    await bus.init_db()

    identity = _identity(
        run_id="run-staged-crash-complete",
        task_id="task-staged-crash-complete",
        idempotency_key="idem-staged-crash-complete",
    )
    metadata = identity_metadata(identity, surface="message_bus")
    message = Message(from_agent="alice", to_agent="bob", body="staged", metadata=metadata)

    original_complete = runtime.complete_idempotent_side_effect
    crashed = {"done": False}

    async def _crash_once(*args, **kwargs):
        if not crashed["done"]:
            crashed["done"] = True
            raise RuntimeError("crash before completion")
        return await original_complete(*args, **kwargs)

    runtime.complete_idempotent_side_effect = _crash_once  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="crash before completion"):
        await bus.send_staged(message, deliver_at_superstep=1)
    assert _message_count(bus_path) == 1

    retry_id = await bus.send_staged(message, deliver_at_superstep=1)

    assert retry_id == message.id
    assert _message_count(bus_path) == 1
    assert [m.id for m in await bus.receive("bob", current_superstep=1)] == [message.id]


@pytest.mark.asyncio
async def test_message_bus_staged_retry_with_regenerated_id_returns_original_row(tmp_path: Path) -> None:
    """A retry carrying the same idempotency key but a regenerated Message id
    must resume against the row recorded at begin time, not insert a duplicate."""
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    bus_path = tmp_path / "messages.db"
    bus = MessageBus(bus_path, runtime_state=runtime, require_identity=True)
    await bus.init_db()

    identity = _identity(
        run_id="run-staged-regen-id",
        task_id="task-staged-regen-id",
        idempotency_key="idem-staged-regen-id",
    )
    metadata = identity_metadata(identity, surface="message_bus")
    first = Message(from_agent="alice", to_agent="bob", body="staged", metadata=metadata)

    original_complete = runtime.complete_idempotent_side_effect
    crashed = {"done": False}

    async def _crash_once(*args, **kwargs):
        if not crashed["done"]:
            crashed["done"] = True
            raise RuntimeError("crash before completion")
        return await original_complete(*args, **kwargs)

    runtime.complete_idempotent_side_effect = _crash_once  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="crash before completion"):
        await bus.send_staged(first, deliver_at_superstep=1)
    assert _message_count(bus_path) == 1

    retry = Message(from_agent="alice", to_agent="bob", body="staged", metadata=metadata)
    assert retry.id != first.id
    retry_receipt = await bus.send_staged(retry, deliver_at_superstep=1)

    assert retry_receipt == first.id
    assert _message_count(bus_path) == 1
    assert [m.id for m in await bus.receive("bob", current_superstep=1)] == [first.id]
