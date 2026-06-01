from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.a2a.a2a_server import A2AServer, A2ATask, A2ATaskStatus
from dharma_swarm.message_bus import MessageBus
from dharma_swarm.models import Task, TaskDispatch
from dharma_swarm.runtime_lifecycle import RuntimeLifecycle
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.session_ledger import SessionLedger
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


TASK_ID = "task-trcr-9999-alpha"
CHILD_TASK_ID = "task-trcr-9999-alpha-child"
RUN_ID = "run-trcr-9999-alpha"
CHILD_RUN_ID = "run-trcr-9999-alpha-child"
TRACE_ID = "trc-trcr-9999-alpha"
CORRELATION_ID = "corr-trcr-9999-alpha"
CLAIM_ID = "claim-trcr-9999-alpha"
CHILD_CLAIM_ID = "claim-trcr-9999-alpha-child"
ARTIFACT_ID = "artifact-trcr-9999-alpha"
IDEMPOTENCY_KEY = "idem-trcr-9999-alpha"
AGENT_ID = "agent-trcr-9999-alpha"
SESSION_ID = "sess-trcr-9999-alpha"
EXTERNAL_A2A_TASK_ID = "TRCR-9999-ALPHA"


SURFACE_MATRIX: tuple[dict[str, str], ...] = (
    {
        "surface": "A2A local submit",
        "status": "joined",
        "evidence": "A2AServer records ExecutionIdentity, runtime receipt, and idempotency.",
    },
    {
        "surface": "A2A HTTP node gateway",
        "status": "adapter-ready",
        "evidence": "node_gateway forwards identity fields in request/response payloads.",
    },
    {
        "surface": "RuntimeLifecycle task claim",
        "status": "joined",
        "evidence": "record_task_claim(require_identity=True) writes RuntimeStateStore identity/receipt.",
    },
    {
        "surface": "RuntimeLifecycle delegation run",
        "status": "joined",
        "evidence": "record_delegation_run(require_identity=True) writes run facts and receipt.",
    },
    {
        "surface": "RuntimeLifecycle artifact record",
        "status": "joined",
        "evidence": "record_artifact(require_identity=True) requires and persists run_id plus trace_id.",
    },
    {
        "surface": "MessageBus emit_event with idempotency_key",
        "status": "joined",
        "evidence": "emit_event checks RuntimeStateStore idempotency before inserting event row.",
    },
    {
        "surface": "Orchestrator result persistence",
        "status": "adapter-ready",
        "evidence": "_persist_result emits provenance and RuntimeLifecycle artifact metadata.",
    },
    {
        "surface": "TaskBoard task metadata",
        "status": "adapter-ready",
        "evidence": "Task metadata can carry execution_identity; mandatory enforcement is not complete.",
    },
    {
        "surface": "Checkpoint human interrupt",
        "status": "adapter-ready",
        "evidence": "Checkpoint surfaces can carry identity, but wait-state receipt saturation is pending.",
    },
    {
        "surface": "Ontology execute_action",
        "status": "missing",
        "evidence": "C2 tollbooth slice still must enforce modifies/requires_approval receipts.",
    },
    {
        "surface": "Tool registry side effects",
        "status": "missing",
        "evidence": "Tool calls need mandatory identity and side_effect_intent/complete receipts.",
    },
    {
        "surface": "Graph/workflow checkpoints",
        "status": "missing",
        "evidence": "Checkpoint identity and resume receipts are not saturated across graph paths.",
    },
    {
        "surface": "Self-modification proposals",
        "status": "missing",
        "evidence": "proposal/gate/apply/verify/promote/revert receipt chain is not saturated.",
    },
    {
        "surface": "NATS/JetStream path",
        "status": "quarantine",
        "evidence": "No live NATS path is selected for this deterministic local evidence bundle.",
    },
    {
        "surface": "MCP server/tool access",
        "status": "missing",
        "evidence": "MCP/tool boundaries need a compatibility adapter before side effects.",
    },
    {
        "surface": "Free-text file extraction",
        "status": "quarantine",
        "evidence": "Regex-driven path writes must stay quarantined until a deterministic tollbooth exists.",
    },
)


def _coverage() -> dict[str, float]:
    total = len(SURFACE_MATRIX)
    joined = sum(1 for row in SURFACE_MATRIX if row["status"] == "joined")
    adapter = sum(1 for row in SURFACE_MATRIX if row["status"] == "adapter-ready")
    classified = sum(1 for row in SURFACE_MATRIX if row["status"])
    return {
        "joined_percent": round(joined / total * 100, 2),
        "joined_or_adapter_ready_percent": round((joined + adapter) / total * 100, 2),
        "classified_percent": round(classified / total * 100, 2),
    }


def _runtime_lifecycle(tmp_path: Path) -> tuple[RuntimeLifecycle, Path]:
    runtime_db_path = tmp_path / "state" / "runtime.db"
    ledger = SessionLedger(
        base_dir=tmp_path / "ledgers",
        session_id=SESSION_ID,
        runtime_db_path=runtime_db_path,
    )
    return RuntimeLifecycle(ledger), runtime_db_path


def _identity_metadata(
    *,
    task_id: str = TASK_ID,
    run_id: str = RUN_ID,
    claim_id: str = CLAIM_ID,
    parent_run_id: str = "",
) -> dict[str, str]:
    return {
        "task_id": task_id,
        "trace_id": TRACE_ID,
        "correlation_id": CORRELATION_ID,
        "run_id": run_id,
        "runtime_run_id": run_id,
        "claim_id": claim_id,
        "idempotency_key": IDEMPOTENCY_KEY,
        "parent_run_id": parent_run_id,
    }


def _task() -> Task:
    return Task(
        id=TASK_ID,
        title="TRCR-9999-ALPHA tracer task",
        description="deterministic runtime truth tracer",
        metadata=_identity_metadata(parent_run_id="run-root-trcr"),
    )


def _dispatch() -> TaskDispatch:
    return TaskDispatch(
        task_id=TASK_ID,
        agent_id=AGENT_ID,
        metadata=_identity_metadata(parent_run_id="run-root-trcr"),
    )


def test_v2_surface_matrix_is_classified_and_quantified() -> None:
    allowed = {"joined", "adapter-ready", "quarantine", "missing"}
    statuses = {row["status"] for row in SURFACE_MATRIX}
    coverage = _coverage()

    assert statuses <= allowed
    assert len(SURFACE_MATRIX) == 16
    assert coverage["classified_percent"] == 100.0
    assert coverage["joined_percent"] == 31.25
    assert coverage["joined_or_adapter_ready_percent"] == 56.25
    assert any(row["status"] == "quarantine" for row in SURFACE_MATRIX)
    assert any(row["status"] == "missing" for row in SURFACE_MATRIX)


@pytest.mark.asyncio
async def test_v2_missing_identity_fails_selected_runtime_boundaries(tmp_path: Path) -> None:
    lifecycle, runtime_db_path = _runtime_lifecycle(tmp_path)
    await RuntimeStateStore(runtime_db_path).init_db()
    task = Task(id=TASK_ID, title="missing identity")
    dispatch = TaskDispatch(
        task_id=TASK_ID,
        agent_id=AGENT_ID,
        metadata={"claim_id": CLAIM_ID, "runtime_run_id": RUN_ID},
    )

    with pytest.raises(MissingExecutionIdentity):
        await lifecycle.record_task_claim(
            dispatch,
            task=task,
            status="claimed",
            require_identity=True,
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
        assert db.execute("SELECT COUNT(*) FROM task_claims").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM delegation_runs").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM artifact_records").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_v2_trcr_9999_alpha_reconstructs_chain_of_custody(tmp_path: Path) -> None:
    lifecycle, runtime_db_path = _runtime_lifecycle(tmp_path)
    task = _task()
    dispatch = _dispatch()

    await lifecycle.record_task_claim(dispatch, task=task, status="claimed", require_identity=True)
    await lifecycle.record_delegation_run(dispatch, task=task, status="claimed", require_identity=True)
    await lifecycle.record_delegation_run(
        dispatch,
        task=task,
        status="completed",
        result="TRACE_SUCCESS",
        require_identity=True,
    )

    child_task = Task(
        id=CHILD_TASK_ID,
        title="TRCR child tracer",
        metadata=_identity_metadata(
            task_id=CHILD_TASK_ID,
            run_id=CHILD_RUN_ID,
            claim_id=CHILD_CLAIM_ID,
            parent_run_id=RUN_ID,
        ),
    )
    child_dispatch = TaskDispatch(
        task_id=CHILD_TASK_ID,
        agent_id=AGENT_ID,
        metadata=_identity_metadata(
            task_id=CHILD_TASK_ID,
            run_id=CHILD_RUN_ID,
            claim_id=CHILD_CLAIM_ID,
            parent_run_id=RUN_ID,
        ),
    )
    await lifecycle.record_delegation_run(
        child_dispatch,
        task=child_task,
        status="completed",
        result="CHILD_TRACE_SUCCESS",
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
    receipt_types = {receipt.receipt_type for receipt in chain["receipts"]}

    assert chain["identity"].run_id == RUN_ID
    assert chain["identity"].trace_id == TRACE_ID
    assert chain["identity"].correlation_id == CORRELATION_ID
    assert chain["run"].parent_run_id == "run-root-trcr"
    assert {child.run_id for child in chain["children"]} == {CHILD_RUN_ID}
    assert chain["children"][0].parent_run_id == RUN_ID
    assert {artifact.run_id for artifact in chain["artifacts"]} == {RUN_ID}
    assert {artifact.trace_id for artifact in chain["artifacts"]} == {TRACE_ID}
    assert receipt_types >= {"task_claim", "delegation_run", "artifact"}


def test_v2_a2a_idempotency_exists_before_handler_side_effect(tmp_path: Path) -> None:
    runtime = RuntimeStateStore(tmp_path / "runtime.db")
    server = A2AServer(runtime_state=runtime, require_execution_identity=True)
    side_effects: list[str] = []
    observed_before_side_effect: list[tuple[str, str, str, str]] = []
    side_effect_key = f"a2a_handler:{EXTERNAL_A2A_TASK_ID}:default"

    def handler(task: A2ATask) -> A2ATask:
        record = runtime.get_idempotency_record_sync(IDEMPOTENCY_KEY, side_effect_key)
        assert record is not None
        observed_before_side_effect.append(
            (record.status, record.run_id, record.trace_id, record.correlation_id)
        )
        side_effects.append(task.metadata["idempotency_key"])
        task.status = A2ATaskStatus.COMPLETED
        task.result = "TRACE_SUCCESS"
        return task

    server.set_default_handler(handler)
    payload = _identity_metadata()
    first = server.submit(
        A2ATask(
            id=EXTERNAL_A2A_TASK_ID,
            to_agent=AGENT_ID,
            trace_id=TRACE_ID,
            metadata=payload,
        )
    )
    second = server.submit(
        A2ATask(
            id=EXTERNAL_A2A_TASK_ID,
            to_agent=AGENT_ID,
            trace_id=TRACE_ID,
            metadata=payload,
        )
    )

    record = runtime.get_idempotency_record_sync(IDEMPOTENCY_KEY, side_effect_key)
    identity = runtime.get_execution_identity_sync(RUN_ID)

    assert first.id == second.id == EXTERNAL_A2A_TASK_ID
    assert observed_before_side_effect == [("started", RUN_ID, TRACE_ID, CORRELATION_ID)]
    assert side_effects == [IDEMPOTENCY_KEY]
    assert record is not None
    assert record.status == "completed"
    assert record.run_id == RUN_ID
    assert record.trace_id == TRACE_ID
    assert identity is not None
    assert identity.external_a2a_task_id == EXTERNAL_A2A_TASK_ID


class SpyRuntimeStateStore(RuntimeStateStore):
    def __init__(self, db_path: Path, *, message_db_path: Path) -> None:
        super().__init__(db_path)
        self.message_db_path = message_db_path
        self.event_counts_before_idempotency: list[int] = []
        self.begin_calls: list[tuple[str, str, str]] = []

    async def try_begin_idempotent_side_effect(
        self,
        identity: ExecutionIdentity,
        side_effect_key: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        with sqlite3.connect(self.message_db_path) as db:
            count = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.event_counts_before_idempotency.append(count)
        self.begin_calls.append((identity.run_id, identity.trace_id, side_effect_key))
        return await super().try_begin_idempotent_side_effect(
            identity,
            side_effect_key,
            metadata=metadata,
        )


@pytest.mark.asyncio
async def test_v2_message_bus_idempotency_happens_before_event_insert(tmp_path: Path) -> None:
    message_db_path = tmp_path / "messages.db"
    runtime = SpyRuntimeStateStore(tmp_path / "runtime.db", message_db_path=message_db_path)
    bus = MessageBus(message_db_path, runtime_state=runtime)
    await bus.init_db()

    payload = {
        "run_id": RUN_ID,
        "trace_id": TRACE_ID,
        "correlation_id": CORRELATION_ID,
        "claim_id": CLAIM_ID,
    }
    first = await bus.emit_event(
        "TRACE_PROBE_V2",
        task_id=TASK_ID,
        agent_id=AGENT_ID,
        payload=payload,
        idempotency_key=IDEMPOTENCY_KEY,
    )
    second = await bus.emit_event(
        "TRACE_PROBE_V2",
        task_id=TASK_ID,
        agent_id=AGENT_ID,
        payload=payload,
        idempotency_key=IDEMPOTENCY_KEY,
    )
    events = await bus.consume_events("TRACE_PROBE_V2")

    assert second == first
    assert runtime.event_counts_before_idempotency == [0]
    assert runtime.begin_calls == [
        (RUN_ID, TRACE_ID, f"message_bus.emit_event:TRACE_PROBE_V2:{first}")
    ]
    assert len(events) == 1
    assert events[0]["event_id"] == first
    record = await runtime.get_idempotency_record(
        IDEMPOTENCY_KEY,
        f"message_bus.emit_event:TRACE_PROBE_V2:{first}",
    )
    assert record is not None
    assert record.status == "completed"
    assert record.run_id == RUN_ID
    assert record.trace_id == TRACE_ID
