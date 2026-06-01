import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from dharma_swarm.artifact_store import RuntimeArtifactStore
from dharma_swarm.message_bus import MessageBus
from dharma_swarm.models import Message
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.adapters import identity_metadata
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity
from dharma_swarm.task_board import TaskBoard
from dharma_swarm.tool_registry import ToolRegistry


def _identity(**overrides: str) -> ExecutionIdentity:
    payload = {
        "task_id": "task-spine-adoption",
        "agent_id": "agent-spine-adoption",
        "session_id": "session-spine-adoption",
        "trace_id": "trace-spine-adoption",
        "correlation_id": "corr-spine-adoption",
        "run_id": "run-spine-adoption",
        "claim_id": "claim-spine-adoption",
        "idempotency_key": "idem-spine-adoption",
    }
    payload.update(overrides)
    return ExecutionIdentity.new(**payload)


def _count_rows(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as db:
        return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


@pytest.mark.asyncio
async def test_task_board_required_identity_fails_closed_and_records_ledger(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    board = TaskBoard(tmp_path / "tasks.db", runtime_state=runtime, require_identity=True)
    await board.init_db()

    with pytest.raises(MissingExecutionIdentity):
        await board.create("missing identity")
    assert await board.get_by_title("missing identity") is None

    identity = _identity()
    task = await board.create(
        "identity-backed task",
        created_by=identity.agent_id,
        metadata=identity_metadata(identity, surface="task_board"),
    )

    loaded_identity = await runtime.get_execution_identity(identity.run_id)
    assert loaded_identity is not None
    assert loaded_identity.task_id == task.id
    assert loaded_identity.trace_id == identity.trace_id

    ledger = await runtime.get_run_ledger(identity.run_id)
    assert any(
        receipt.receipt_type == "task_created"
        and receipt.status == "created"
        and receipt.task_id == task.id
        for receipt in ledger["receipts"]
    )


@pytest.mark.asyncio
async def test_task_board_create_batch_preflights_identity_before_any_insert(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    board = TaskBoard(tmp_path / "tasks.db", runtime_state=runtime, require_identity=True)
    await board.init_db()

    identity = _identity(run_id="run-batch-good", idempotency_key="idem-batch-good")
    with pytest.raises(MissingExecutionIdentity):
        await board.create_batch(
            [
                {
                    "title": "valid batch task",
                    "created_by": identity.agent_id,
                    "metadata": identity_metadata(identity, surface="task_board"),
                },
                {"title": "invalid batch task"},
            ],
        )

    assert _count_rows(tmp_path / "tasks.db", "tasks") == 0


@pytest.mark.asyncio
async def test_message_bus_required_identity_dedupes_before_send_side_effect(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    bus = MessageBus(tmp_path / "messages.db", runtime_state=runtime, require_identity=True)
    await bus.init_db()

    with pytest.raises(MissingExecutionIdentity):
        await bus.send(Message(from_agent="alice", to_agent="bob", body="missing"))

    identity = _identity(
        run_id="run-message",
        task_id="task-message",
        idempotency_key="idem-message-once",
    )
    metadata = identity_metadata(identity, surface="message_bus")
    first = Message(from_agent="alice", to_agent="bob", body="first", metadata=metadata)
    second = Message(from_agent="alice", to_agent="bob", body="second", metadata=metadata)

    first_id = await bus.send(first)
    second_id = await bus.send(second)

    assert second_id == first_id
    messages = await bus.receive("bob")
    assert [message.id for message in messages] == [first_id]

    ledger = await runtime.get_run_ledger(identity.run_id)
    records = ledger["idempotency_records"]
    assert len(records) == 1
    assert records[0].result_receipt_id == first_id


@pytest.mark.asyncio
async def test_message_bus_consume_events_requires_identity_and_records_receipts(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    bus = MessageBus(tmp_path / "events.db", runtime_state=runtime)
    await bus.init_db()
    event_id = await bus.emit_event("spine.test", payload={"ok": True})

    with pytest.raises(MissingExecutionIdentity):
        await bus.consume_events("spine.test", require_identity=True)

    identity = _identity(run_id="run-consume", idempotency_key="idem-consume")
    consumed = await bus.consume_events(
        "spine.test",
        execution_identity=identity,
        require_identity=True,
    )

    assert [event["event_id"] for event in consumed] == [event_id]
    receipts = (await runtime.get_run_ledger(identity.run_id))["receipts"]
    assert any(
        receipt.receipt_type == "message_consumed"
        and receipt.side_effect_key == f"event:{event_id}"
        for receipt in receipts
    )


def test_tool_registry_required_identity_blocks_handler_and_records_side_effect(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    registry = ToolRegistry(runtime_state=runtime, require_identity=True)
    calls: list[dict] = []

    def handler(args: dict) -> str:
        calls.append(args)
        return json.dumps({"ok": True})

    registry.register(
        "safe_probe",
        "test",
        {"name": "safe_probe", "description": "probe", "parameters": {}},
        handler,
    )

    missing = registry.dispatch("safe_probe", {})
    assert json.loads(missing)["error"].startswith("Tool execution failed: MissingExecutionIdentity")
    assert calls == []

    identity = _identity(run_id="run-tool", task_id="task-tool", idempotency_key="idem-tool")
    result = registry.dispatch(
        "safe_probe",
        {"value": 1},
        execution_identity=identity,
    )

    assert json.loads(result) == {"ok": True}
    assert calls[0]["value"] == 1
    ledger = asyncio.run(runtime.get_run_ledger(identity.run_id))
    receipt_types = {receipt.receipt_type for receipt in ledger["receipts"]}
    assert {"side_effect_intent", "side_effect_complete"} <= receipt_types


@pytest.mark.asyncio
async def test_runtime_artifact_store_requires_identity_before_file_write(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    store = RuntimeArtifactStore(
        tmp_path / "workspace",
        runtime_state=runtime,
        require_identity=True,
    )

    with pytest.raises(MissingExecutionIdentity):
        await store.create_text_artifact_async(
            session_id="session-artifact",
            artifact_type="research",
            artifact_kind="report",
            content="missing identity",
            created_by="agent-artifact",
        )
    assert not (tmp_path / "workspace" / "session-artifact").exists()

    identity = _identity(
        run_id="run-artifact",
        task_id="task-artifact",
        idempotency_key="idem-artifact",
    )
    stored = await store.create_text_artifact_async(
        session_id=identity.session_id,
        artifact_type="research",
        artifact_kind="report",
        content="identity backed",
        created_by=identity.agent_id,
        metadata=identity_metadata(identity, surface="artifact_store"),
    )

    assert stored.record.run_id == identity.run_id
    assert stored.record.trace_id == identity.trace_id
    assert Path(stored.ref.path).exists()
    ledger = await runtime.get_run_ledger(identity.run_id)
    assert any(artifact.artifact_id == stored.record.artifact_id for artifact in ledger["artifacts"])
    assert any(
        receipt.receipt_type == "artifact_written"
        and receipt.run_id == identity.run_id
        and receipt.trace_id == identity.trace_id
        for receipt in ledger["receipts"]
    )
