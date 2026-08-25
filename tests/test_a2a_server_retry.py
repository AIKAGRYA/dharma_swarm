from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dharma_swarm.a2a.a2a_server import A2AServer, A2ATask, A2ATaskStatus
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


TASK_ID = "task-a2a-context-retry"
EXTERNAL_TASK_ID = "a2a-context-retry"
RUN_ID = "run-a2a-context-retry"
TRACE_ID = "trace-a2a-context-retry"
CORRELATION_ID = "correlation-a2a-context-retry"
CLAIM_ID = "claim-a2a-context-retry"
IDEMPOTENCY_KEY = "idem-a2a-context-retry"
CAPABILITY = "context_retry"
CONTEXT_ID = "context-a2a-durable"
SIDE_EFFECT_KEY = f"a2a_handler:{EXTERNAL_TASK_ID}:{CAPABILITY}"


def _identity(*, context_id: str = CONTEXT_ID) -> ExecutionIdentity:
    return ExecutionIdentity.new(
        task_id=TASK_ID,
        agent_id="worker",
        trace_id=TRACE_ID,
        correlation_id=CORRELATION_ID,
        run_id=RUN_ID,
        claim_id=CLAIM_ID,
        idempotency_key=IDEMPOTENCY_KEY,
        external_a2a_task_id=EXTERNAL_TASK_ID,
        metadata={"context_id": context_id, "capability": CAPABILITY},
    )


def _metadata(
    identity: ExecutionIdentity,
    *,
    top_level_context: str = "",
    nested_context: str = "",
) -> dict[str, object]:
    nested_identity = identity.to_dict()
    nested_identity["metadata"] = (
        {"context_id": nested_context, "capability": CAPABILITY}
        if nested_context
        else {}
    )
    metadata: dict[str, object] = {
        "execution_identity": nested_identity,
        "trace_id": identity.trace_id,
        "correlation_id": identity.correlation_id,
        "run_id": identity.run_id,
        "runtime_run_id": identity.run_id,
        "claim_id": identity.claim_id,
        "idempotency_key": identity.idempotency_key,
    }
    if top_level_context:
        metadata["context_id"] = top_level_context
    return metadata


def _task(
    identity: ExecutionIdentity,
    *,
    context_id: str = "",
    top_level_context: str = "",
    nested_context: str = "",
) -> A2ATask:
    return A2ATask(
        id=EXTERNAL_TASK_ID,
        context_id=context_id,
        to_agent=identity.agent_id,
        capability=CAPABILITY,
        trace_id=identity.trace_id,
        metadata=_metadata(
            identity,
            top_level_context=top_level_context,
            nested_context=nested_context,
        ),
    )


def _idempotency_count(runtime_db: Path) -> int:
    with sqlite3.connect(runtime_db) as db:
        row = db.execute("SELECT COUNT(*) FROM idempotency_records").fetchone()
    assert row is not None
    return int(row[0])


def _failed_once_server(
    tmp_path: Path,
) -> tuple[RuntimeStateStore, A2AServer, ExecutionIdentity, list[str]]:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    server = A2AServer(
        runtime_state=runtime,
        persist=False,
        require_execution_identity=True,
    )
    identity = _identity()
    observed_contexts: list[str] = []

    def handler(task: A2ATask) -> A2ATask:
        observed_contexts.append(task.context_id)
        if len(observed_contexts) == 1:
            raise RuntimeError("seed one retryable handler failure")
        task.status = A2ATaskStatus.COMPLETED
        return task

    server.register_handler(CAPABILITY, handler)
    first = server.submit(_task(identity, context_id=CONTEXT_ID))
    assert first.status == A2ATaskStatus.FAILED
    assert observed_contexts == [CONTEXT_ID]
    return runtime, server, identity, observed_contexts


def test_retry_without_wire_context_recovers_exact_run_durable_context(
    tmp_path: Path,
) -> None:
    runtime, server, identity, observed_contexts = _failed_once_server(tmp_path)

    retried = server.submit(_task(identity))

    assert retried.status == A2ATaskStatus.COMPLETED
    assert retried.context_id == CONTEXT_ID
    assert retried.metadata["context_id"] == CONTEXT_ID
    assert retried.metadata["idempotency_status"] == "retry"
    assert observed_contexts == [CONTEXT_ID, CONTEXT_ID]
    durable = runtime.get_execution_identity_sync(RUN_ID)
    assert durable is not None
    assert durable.metadata["context_id"] == CONTEXT_ID
    assert _idempotency_count(runtime.db_path) == 2


def test_retry_accepts_one_context_repeated_across_every_carrier(
    tmp_path: Path,
) -> None:
    runtime, server, identity, observed_contexts = _failed_once_server(tmp_path)

    retried = server.submit(
        _task(
            identity,
            context_id=CONTEXT_ID,
            top_level_context=CONTEXT_ID,
            nested_context=CONTEXT_ID,
        )
    )

    assert retried.status == A2ATaskStatus.COMPLETED
    assert observed_contexts == [CONTEXT_ID, CONTEXT_ID]
    assert _idempotency_count(runtime.db_path) == 2


def test_context_mismatch_rejected_before_handler_or_retry_mutation(
    tmp_path: Path,
) -> None:
    runtime, server, identity, observed_contexts = _failed_once_server(tmp_path)
    count_before = _idempotency_count(runtime.db_path)

    with pytest.raises(MissingExecutionIdentity) as exc_info:
        server.submit(
            _task(
                identity,
                context_id="context-explicit-conflict",
                top_level_context="context-top-level-conflict",
                nested_context="context-nested-conflict",
            )
        )

    message = str(exc_info.value)
    assert "task.context_id" in message
    assert "metadata.context_id" in message
    assert "metadata.execution_identity.metadata.context_id" in message
    assert "durable_execution_identity.metadata.context_id" in message
    assert observed_contexts == [CONTEXT_ID]
    assert _idempotency_count(runtime.db_path) == count_before == 1
    assert runtime.get_idempotency_record_sync(
        IDEMPOTENCY_KEY, SIDE_EFFECT_KEY
    ).status == "failed"
