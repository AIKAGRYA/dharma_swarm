from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dharma_swarm.a2a.a2a_server import A2AServer, A2ATask, A2ATaskStatus
from dharma_swarm.message_bus import MessageBus
from dharma_swarm.models import Task, TaskDispatch
from dharma_swarm.runtime_lifecycle import RuntimeLifecycle
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.session_ledger import SessionLedger
from dharma_swarm.spine.identity import MissingExecutionIdentity


TASK_ID = "task-trcr-9999-alpha"
RUN_ID = "run-trcr-9999-alpha"
TRACE_ID = "trc-trcr-9999-alpha"
CORRELATION_ID = "corr-trcr-9999-alpha"
CLAIM_ID = "claim-trcr-9999-alpha"
ARTIFACT_ID = "artifact-trcr-9999-alpha"
IDEMPOTENCY_KEY = "idem-trcr-9999-alpha"
AGENT_ID = "agent-trcr-9999-alpha"
SESSION_ID = "sess-trcr-9999-alpha"
EXTERNAL_A2A_TASK_ID = "TRCR-9999-ALPHA"


def _runtime_lifecycle(tmp_path: Path) -> tuple[RuntimeLifecycle, Path]:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id=SESSION_ID,
        runtime_db_path=runtime_db_path,
    )
    return RuntimeLifecycle(ledger), runtime_db_path


def _task() -> Task:
    return Task(
        id=TASK_ID,
        title="TRCR-9999-ALPHA tracer task",
        description="deterministic runtime truth tracer",
        metadata={
            "trace_id": TRACE_ID,
            "correlation_id": CORRELATION_ID,
            "run_id": RUN_ID,
            "runtime_run_id": RUN_ID,
            "claim_id": CLAIM_ID,
            "idempotency_key": IDEMPOTENCY_KEY,
            "parent_run_id": "run-parent-trcr",
        },
    )


def _dispatch() -> TaskDispatch:
    return TaskDispatch(
        task_id=TASK_ID,
        agent_id=AGENT_ID,
        metadata={
            "trace_id": TRACE_ID,
            "correlation_id": CORRELATION_ID,
            "run_id": RUN_ID,
            "runtime_run_id": RUN_ID,
            "claim_id": CLAIM_ID,
            "idempotency_key": IDEMPOTENCY_KEY,
            "parent_run_id": "run-parent-trcr",
        },
    )


@pytest.mark.asyncio
async def test_trcr_9999_alpha_missing_identity_fails(tmp_path: Path) -> None:
    lifecycle, runtime_db_path = _runtime_lifecycle(tmp_path)
    await RuntimeStateStore(runtime_db_path).init_db()
    task = Task(id=TASK_ID, title="missing identity")
    dispatch = TaskDispatch(
        task_id=TASK_ID,
        agent_id=AGENT_ID,
        metadata={"claim_id": CLAIM_ID, "runtime_run_id": RUN_ID},
    )

    with pytest.raises(MissingExecutionIdentity):
        await lifecycle.record_delegation_run(
            dispatch,
            task=task,
            status="running",
            require_identity=True,
        )

    artifact_path = tmp_path / "artifact.md"
    artifact_path.write_text("artifact", encoding="utf-8")
    with pytest.raises(MissingExecutionIdentity):
        await lifecycle.record_artifact(
            task=task,
            artifact_id=ARTIFACT_ID,
            artifact_kind="task_result",
            payload_path=artifact_path,
            checksum="abc123",
            run_id=RUN_ID,
            require_identity=True,
        )

    with sqlite3.connect(runtime_db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM delegation_runs").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM artifact_records").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_trcr_9999_alpha_lifecycle_artifact_and_run_reconstruct(tmp_path: Path) -> None:
    lifecycle, runtime_db_path = _runtime_lifecycle(tmp_path)
    task = _task()
    dispatch = _dispatch()

    await lifecycle.record_task_claim(
        dispatch,
        task=task,
        status="claimed",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="claimed",
        require_identity=True,
    )
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="completed",
        result="TRACE_SUCCESS",
        require_identity=True,
    )

    artifact_path = tmp_path / "artifact.md"
    artifact_path.write_text("TRACE_SUCCESS", encoding="utf-8")
    await lifecycle.record_artifact(
        task=task,
        artifact_id=ARTIFACT_ID,
        artifact_kind="task_result",
        payload_path=artifact_path,
        checksum="abc123",
        run_id=RUN_ID,
        require_identity=True,
    )

    store = RuntimeStateStore(runtime_db_path)
    chain = await store.get_run_ledger(RUN_ID)

    assert chain["identity"].run_id == RUN_ID
    assert chain["identity"].trace_id == TRACE_ID
    assert chain["identity"].correlation_id == CORRELATION_ID
    assert chain["run"].run_id == RUN_ID
    assert chain["run"].parent_run_id == "run-parent-trcr"
    assert chain["artifacts"][0].run_id == RUN_ID
    assert chain["artifacts"][0].trace_id == TRACE_ID
    assert chain["artifacts"][0].metadata["correlation_id"] == CORRELATION_ID
    assert {receipt.receipt_type for receipt in chain["receipts"]} >= {
        "task_claim",
        "delegation_run",
        "artifact",
    }

    with sqlite3.connect(runtime_db_path) as db:
        run_trace, run_claim = db.execute(
            "SELECT trace_id, claim_id FROM delegation_runs WHERE run_id = ?",
            (RUN_ID,),
        ).fetchone()
        artifact_run, artifact_trace, artifact_meta = db.execute(
            "SELECT run_id, trace_id, metadata_json FROM artifact_records WHERE artifact_id = ?",
            (ARTIFACT_ID,),
        ).fetchone()

    assert run_trace == TRACE_ID
    assert run_claim == CLAIM_ID
    assert artifact_run == RUN_ID
    assert artifact_trace == TRACE_ID
    assert CORRELATION_ID in artifact_meta


def test_trcr_9999_alpha_a2a_ingress_maps_ids_and_dedupes(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    side_effects: list[str] = []
    server = A2AServer(runtime_state=runtime, require_execution_identity=True)

    def handler(task: A2ATask) -> A2ATask:
        side_effects.append(task.metadata["idempotency_key"])
        task.status = A2ATaskStatus.COMPLETED
        task.result = "TRACE_SUCCESS"
        return task

    server.set_default_handler(handler)
    task = A2ATask(
        id=EXTERNAL_A2A_TASK_ID,
        to_agent=AGENT_ID,
        trace_id=TRACE_ID,
        metadata={
            "task_id": TASK_ID,
            "run_id": RUN_ID,
            "correlation_id": CORRELATION_ID,
            "claim_id": CLAIM_ID,
            "idempotency_key": IDEMPOTENCY_KEY,
        },
    )
    first = server.submit(task)
    second = server.submit(
        A2ATask(
            id=EXTERNAL_A2A_TASK_ID,
            to_agent=AGENT_ID,
            trace_id=TRACE_ID,
            metadata={
                "task_id": TASK_ID,
                "run_id": RUN_ID,
                "correlation_id": CORRELATION_ID,
                "claim_id": CLAIM_ID,
                "idempotency_key": IDEMPOTENCY_KEY,
            },
        )
    )

    identity = runtime.get_execution_identity_sync(RUN_ID)
    record = runtime.get_idempotency_record_sync(
        IDEMPOTENCY_KEY,
        f"a2a_handler:{EXTERNAL_A2A_TASK_ID}:default",
    )

    assert first.id == second.id == EXTERNAL_A2A_TASK_ID
    assert side_effects == [IDEMPOTENCY_KEY]
    assert identity is not None
    assert identity.external_a2a_task_id == EXTERNAL_A2A_TASK_ID
    assert identity.task_id == TASK_ID
    assert identity.trace_id == TRACE_ID
    assert identity.correlation_id == CORRELATION_ID
    assert record is not None
    assert record.status == "completed"


@pytest.mark.asyncio
async def test_trcr_9999_alpha_message_bus_idempotency_suppresses_duplicate_event(
    tmp_path: Path,
) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    bus = MessageBus(tmp_path / "messages.db", runtime_state=runtime)
    await bus.init_db()

    payload = {
        "run_id": RUN_ID,
        "trace_id": TRACE_ID,
        "correlation_id": CORRELATION_ID,
        "claim_id": CLAIM_ID,
    }
    first = await bus.emit_event(
        "TRACE_PROBE",
        task_id=TASK_ID,
        agent_id=AGENT_ID,
        payload=payload,
        idempotency_key=IDEMPOTENCY_KEY,
    )
    second = await bus.emit_event(
        "TRACE_PROBE",
        task_id=TASK_ID,
        agent_id=AGENT_ID,
        payload=payload,
        idempotency_key=IDEMPOTENCY_KEY,
    )
    events = await bus.consume_events("TRACE_PROBE")

    assert second == first
    assert len(events) == 1
    assert events[0]["event_id"] == first
    assert await runtime.was_side_effect_performed(
        IDEMPOTENCY_KEY,
        f"message_bus.emit_event:TRACE_PROBE:{first}",
    )
