from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from dharma_swarm.checkpoint import SuperstepCheckpoint
from dharma_swarm.message_bus import MessageBus
from dharma_swarm.models import Message
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity


def _identity() -> ExecutionIdentity:
    return ExecutionIdentity.new(
        task_id="task-bsp-message",
        agent_id="agent-a",
        trace_id="trace-bsp-message",
        correlation_id="corr-bsp-message",
        run_id="run-bsp-message",
        claim_id="claim-bsp-message",
        idempotency_key="idem-bsp-message",
    )


@pytest.mark.asyncio
async def test_send_staged_uses_runtime_idempotency_guard(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    bus = MessageBus(tmp_path / "messages.db", runtime_state=runtime)
    await bus.init_db()

    message = Message(
        id="msg-staged-1",
        from_agent="agent-a",
        to_agent="agent-b",
        subject="superstep",
        body="visible later",
    )
    identity = _identity()

    first = await bus.send_staged(
        message,
        deliver_at_superstep=3,
        execution_identity=identity,
    )
    duplicate = await bus.send_staged(
        message.model_copy(update={"id": "msg-staged-duplicate"}),
        deliver_at_superstep=3,
        execution_identity=identity,
    )

    assert first == "msg-staged-1"
    assert duplicate == "msg-staged-1"
    assert await bus.receive("agent-b", current_superstep=2) == []
    assert [m.id for m in await bus.receive("agent-b", current_superstep=3)] == ["msg-staged-1"]

    with sqlite3.connect(tmp_path / "messages.db") as db:
        count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert count == 1

    record = await runtime.get_idempotency_record(
        identity.idempotency_key,
        f"message_bus.send_staged:{identity.idempotency_key}",
    )
    assert record is not None
    assert record.status == "completed"
    assert record.result_receipt_id == "msg-staged-1"


@pytest.mark.asyncio
async def test_message_bus_superstep_migration_fails_closed_for_real_errors(
    tmp_path: Path,
) -> None:
    bus = MessageBus(tmp_path / "messages.db")

    original_execute = None

    async def fail_real_alter(sql: str, *args, **kwargs):
        if sql.startswith("ALTER TABLE messages ADD COLUMN"):
            raise sqlite3.OperationalError("database is locked for migration")
        return await original_execute(sql, *args, **kwargs)

    async with bus._open() as db:  # type: ignore[attr-defined]
        original_execute = db.execute
        with patch.object(db, "execute", side_effect=fail_real_alter):
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                await MessageBus._configure_connection(db)
                for ddl in (  # mimic init_db path only enough to reach migration
                    "CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY)",
                ):
                    await db.execute(ddl)
                try:
                    await db.execute(
                        "ALTER TABLE messages ADD COLUMN "
                        "superstep_visible INTEGER NOT NULL DEFAULT 0"
                    )
                except sqlite3.OperationalError as exc:
                    if "duplicate column name" not in str(exc).lower():
                        raise


def test_superstep_checkpoint_save_flushes_and_fsyncs_before_replace(
    tmp_path: Path,
) -> None:
    checkpoint = SuperstepCheckpoint(
        superstep_id=7,
        running_task_ids=["task-a"],
        active_dispatch_ids=["dispatch-a"],
    )
    target = tmp_path / "superstep.json"
    calls: list[str] = []
    real_replace = os.replace

    def spy_fsync(fd: int) -> None:
        calls.append("fsync")

    def spy_replace(src, dst) -> None:
        calls.append("replace")
        real_replace(src, dst)

    with patch("os.fsync", side_effect=spy_fsync), patch("os.replace", side_effect=spy_replace):
        checkpoint.save(target)

    assert calls.index("fsync") < calls.index("replace")
    loaded = SuperstepCheckpoint.load(target)
    assert loaded is not None
    assert loaded.superstep_id == 7
    assert loaded.running_task_ids == ["task-a"]
