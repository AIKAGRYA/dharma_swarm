from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm.operator_views import OperatorViews
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    SessionEventRecord,
    SessionState,
    TopologyStateRecord,
)


async def _seed_runtime_graph(store: RuntimeStateStore) -> None:
    base_time = datetime(2026, 6, 30, 21, 0, tzinfo=timezone.utc)
    await store.upsert_session(
        SessionState(
            session_id="sess-graph",
            operator_id="operator",
            status="active",
            current_task_id="task-graph",
            active_bundle_id="bundle-graph",
            metadata={"surface": "phase7-runtime-platform"},
        )
    )
    await store.record_delegation_run(
        DelegationRun(
            run_id="run-parent",
            session_id="sess-graph",
            task_id="task-graph",
            assigned_to="supervisor",
            assigned_by="operator",
            status="in_progress",
        )
    )
    await store.record_delegation_run(
        DelegationRun(
            run_id="run-child",
            session_id="sess-graph",
            task_id="task-graph",
            assigned_to="worker-a",
            assigned_by="supervisor",
            parent_run_id="run-parent",
            status="completed",
        )
    )
    await store.record_topology_state(
        TopologyStateRecord(
            run_id="run-parent",
            session_id="sess-graph",
            task_id="task-graph",
            topology="supervisor",
            active_agent="worker-a",
            current_node="worker-a",
            checkpoint_id="task-graph:supervisor:checkpoint-1",
            child_run_ids=["run-child"],
            allowed_handoffs={"supervisor": ["worker-a"]},
            handoff_receipts=[
                {
                    "status": "accepted",
                    "from_agent": "supervisor",
                    "to_agent": "worker-a",
                    "reason": "delegate scoped worker task",
                }
            ],
            state={"status": "in_progress", "visible_output_policy": "supervisor_final"},
        )
    )
    await store.record_runtime_receipt(
        RuntimeReceipt(
            receipt_id="receipt-topology",
            receipt_type="topology_state",
            run_id="run-parent",
            task_id="task-graph",
            agent_id="worker-a",
            status="persisted",
            payload={"checkpoint_id": "task-graph:supervisor:checkpoint-1"},
        )
    )
    await store.record_session_event(
        SessionEventRecord(
            event_id="event-runtime-started",
            session_id="sess-graph",
            ledger_kind="runtime",
            event_name="run_started",
            task_id="task-graph",
            run_id="run-parent",
            agent_id="supervisor",
            summary="Supervisor runtime started",
            event_text="Supervisor runtime started from seeded runtime graph test.",
            payload={"checkpoint_id": "task-graph:supervisor:checkpoint-1"},
            created_at=base_time,
        )
    )
    await store.record_session_event(
        SessionEventRecord(
            event_id="event-interrupt-requested",
            session_id="sess-graph",
            ledger_kind="runtime",
            event_name="interrupt_requested",
            task_id="task-graph",
            run_id="run-parent",
            agent_id="supervisor",
            summary="Supervisor paused for human approval",
            event_text="Supervisor requested human approval before resuming.",
            payload={
                "approval_id": "approval-1",
                "checkpoint_id": "task-graph:supervisor:checkpoint-1",
                "interrupt_id": "interrupt-1",
                "requires_human": True,
                "resume_token": "resume-run-parent",
                "status": "pending",
            },
            created_at=base_time + timedelta(seconds=1),
        )
    )
    await store.record_session_event(
        SessionEventRecord(
            event_id="event-human-approval-granted",
            session_id="sess-graph",
            ledger_kind="runtime",
            event_name="human_approval_granted",
            task_id="task-graph",
            run_id="run-parent",
            agent_id="operator",
            summary="Human approval granted",
            event_text="Operator granted approval to resume the supervisor run.",
            payload={
                "approval_id": "approval-1",
                "approval_status": "approved",
                "checkpoint_id": "task-graph:supervisor:checkpoint-1",
                "interrupt_id": "interrupt-1",
            },
            created_at=base_time + timedelta(seconds=2),
        )
    )


@pytest.mark.asyncio
async def test_operator_views_runtime_graph_surfaces_live_topology_state(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await _seed_runtime_graph(store)

    snapshot = await OperatorViews(store).runtime_graph(
        session_id="sess-graph",
        task_id="task-graph",
        limit=10,
        receipt_limit=10,
    )

    assert snapshot["schema_version"] == "runtime_graph_snapshot.v1"
    assert snapshot["summary"]["topology_state_count"] == 1
    assert snapshot["summary"]["run_count"] == 2
    assert snapshot["summary"]["active_run_count"] == 1
    assert snapshot["active_agents"] == ["worker-a"]
    assert snapshot["checkpoints"][0]["checkpoint_id"] == "task-graph:supervisor:checkpoint-1"
    assert snapshot["topology_states"][0]["handoff_receipts"][0]["status"] == "accepted"
    assert snapshot["receipts"][0]["receipt_id"] == "receipt-topology"

    node_kinds = {node["kind"] for node in snapshot["nodes"]}
    edge_kinds = {edge["kind"] for edge in snapshot["edges"]}
    assert {"run", "agent", "topology", "checkpoint", "receipt"} <= node_kinds
    assert {"active_agent", "handoff", "parent_child", "checkpoint", "receipt"} <= edge_kinds


@pytest.mark.asyncio
async def test_operator_views_runtime_platform_surfaces_use_runtime_state(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await _seed_runtime_graph(store)
    views = OperatorViews(store)

    sessions = await views.runtime_sessions(status="active", limit=10)
    runs = await views.runtime_runs(session_id="sess-graph", limit=10)
    detail = await views.runtime_run_detail("run-parent")
    checkpoints = await views.runtime_checkpoints(session_id="sess-graph", limit=10)
    events = await views.runtime_events(session_id="sess-graph", ledger_kind="runtime")
    interrupts = await views.runtime_interrupts(session_id="sess-graph", limit=10)

    assert sessions["schema_version"] == "runtime_sessions_snapshot.v1"
    assert sessions["summary"]["session_count"] == 1
    assert sessions["sessions"][0]["current_task_id"] == "task-graph"
    assert sessions["sessions"][0]["metadata"]["surface"] == "phase7-runtime-platform"

    assert runs["schema_version"] == "runtime_runs_snapshot.v1"
    assert runs["summary"]["run_count"] == 2
    parent = next(run for run in runs["runs"] if run["run_id"] == "run-parent")
    assert parent["checkpoint_id"] == "task-graph:supervisor:checkpoint-1"
    assert parent["active_agent"] == "worker-a"

    assert detail["schema_version"] == "runtime_run_detail.v1"
    assert detail["found"] is True
    assert detail["summary"]["receipt_count"] == 1
    assert detail["summary"]["child_run_count"] == 1
    assert detail["detail"]["run"]["run_id"] == "run-parent"

    assert checkpoints["schema_version"] == "runtime_checkpoint_history.v1"
    assert checkpoints["summary"]["checkpoint_count"] == 1
    assert checkpoints["checkpoints"][0]["current_node"] == "worker-a"
    assert checkpoints["checkpoints"][0]["state"]["visible_output_policy"] == "supervisor_final"

    assert events["schema_version"] == "runtime_events_snapshot.v1"
    assert events["summary"]["event_count"] == 3
    assert {event["event_name"] for event in events["events"]} >= {
        "run_started",
        "interrupt_requested",
        "human_approval_granted",
    }

    assert interrupts["schema_version"] == "runtime_interrupts_snapshot.v1"
    assert interrupts["summary"]["control_event_count"] == 2
    assert interrupts["summary"]["pending_interrupt_count"] == 1
    assert interrupts["summary"]["human_approval_required_count"] == 1
    assert interrupts["summary"]["approved_count"] == 1
    pending = next(
        event for event in interrupts["control_events"] if event["status"] == "pending"
    )
    assert pending["interrupt_id"] == "interrupt-1"
    assert pending["approval_id"] == "approval-1"
    assert pending["resume_token"] == "resume-run-parent"
    assert pending["checkpoint_id"] == "task-graph:supervisor:checkpoint-1"


@pytest.mark.asyncio
async def test_runtime_graph_api_uses_configured_runtime_db(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "runtime.db"
    store = RuntimeStateStore(db_path, include_memory_plane=False)
    await _seed_runtime_graph(store)
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(db_path))

    from api.routers.runtime import runtime_graph

    response = await runtime_graph(
        session_id="sess-graph",
        task_id=None,
        topology=None,
        limit=10,
        receipt_limit=10,
    )

    assert response.status == "ok"
    assert response.error == ""
    assert response.data["runtime_db"] == str(db_path)
    assert response.data["topology_states"][0]["active_agent"] == "worker-a"


@pytest.mark.asyncio
async def test_runtime_platform_api_uses_configured_runtime_db(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "runtime.db"
    store = RuntimeStateStore(db_path, include_memory_plane=False)
    await _seed_runtime_graph(store)
    monkeypatch.setenv("DHARMA_RUNTIME_DB", str(db_path))

    from api.routers.runtime import (
        runtime_checkpoints,
        runtime_events,
        runtime_events_stream,
        runtime_interrupts,
        runtime_run_detail,
        runtime_runs,
        runtime_sessions,
    )

    sessions = await runtime_sessions(status="active", limit=10)
    runs = await runtime_runs(
        session_id="sess-graph",
        task_id=None,
        status=None,
        limit=10,
    )
    detail = await runtime_run_detail(run_id="run-parent")
    checkpoints = await runtime_checkpoints(
        session_id="sess-graph",
        task_id=None,
        topology=None,
        limit=10,
    )
    events = await runtime_events(
        session_id="sess-graph",
        ledger_kind="runtime",
        event_name=None,
        limit=10,
    )
    interrupts = await runtime_interrupts(
        session_id="sess-graph",
        status=None,
        limit=10,
    )
    stream = await runtime_events_stream(
        session_id="sess-graph",
        ledger_kind="runtime",
        event_name="interrupt_requested",
        limit=10,
        poll_seconds=0.01,
        max_events=1,
    )

    assert sessions.status == "ok"
    assert sessions.data["runtime_db"] == str(db_path)
    assert sessions.data["sessions"][0]["session_id"] == "sess-graph"

    assert runs.status == "ok"
    assert runs.data["summary"]["run_count"] == 2
    assert {run["run_id"] for run in runs.data["runs"]} == {"run-parent", "run-child"}

    assert detail.status == "ok"
    assert detail.data["summary"]["child_run_count"] == 1
    assert detail.data["detail"]["topology_state"]["checkpoint_id"].endswith("checkpoint-1")

    assert checkpoints.status == "ok"
    assert checkpoints.data["checkpoints"][0]["checkpoint_id"] == "task-graph:supervisor:checkpoint-1"

    assert events.status == "ok"
    assert events.data["events"][0]["payload"]["checkpoint_id"] == "task-graph:supervisor:checkpoint-1"

    assert interrupts.status == "ok"
    assert interrupts.data["summary"]["control_event_count"] == 2
    assert interrupts.data["control_events"][0]["event_name"] == "human_approval_granted"

    assert stream.media_type == "text/event-stream"
    chunks: list[str] = []
    async for chunk in stream.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    body = "".join(chunks)
    assert body.startswith("event: runtime_event\n")
    event_payload = json.loads(body.split("data: ", 1)[1].strip())
    assert event_payload["event_id"] == "event-interrupt-requested"
    assert event_payload["payload"]["resume_token"] == "resume-run-parent"


def test_runtime_graph_router_is_registered() -> None:
    from api.main import app

    paths = set(app.openapi().get("paths", {}))
    assert "/api/runtime/graph" in paths
    assert "/api/runtime/sessions" in paths
    assert "/api/runtime/runs" in paths
    assert "/api/runtime/runs/{run_id}" in paths
    assert "/api/runtime/checkpoints" in paths
    assert "/api/runtime/events" in paths
    assert "/api/runtime/events/stream" in paths
    assert "/api/runtime/interrupts" in paths
