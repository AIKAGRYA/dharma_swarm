from __future__ import annotations

import asyncio
import importlib
import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

from dharma_swarm import cron_scheduler
from dharma_swarm.operator_views import OperatorViews
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    RuntimeStateStore,
    SessionEventRecord,
    SessionState,
    TaskClaim,
    TopologyStateRecord,
)
from dharma_swarm.spine.identity import ExecutionIdentity


async def _seed_runtime_graph(store: RuntimeStateStore) -> None:
    base_time = datetime(2026, 6, 30, 21, 0, tzinfo=timezone.utc)
    lease_now = datetime.now(timezone.utc)
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
    identity = ExecutionIdentity.new(
        trace_id="trace-parent",
        correlation_id="corr-parent",
        task_id="task-graph",
        run_id="run-parent",
        claim_id="claim-parent",
        idempotency_key="idem-parent",
        agent_id="supervisor",
        session_id="sess-graph",
    )
    await store.record_execution_identity(identity, source="test")
    await store.record_task_claim(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            session_id=identity.session_id,
            agent_id=identity.agent_id,
            status="active",
            claimed_at=lease_now - timedelta(minutes=3),
            acked_at=lease_now - timedelta(minutes=2),
            heartbeat_at=lease_now - timedelta(minutes=1),
            stale_after=lease_now + timedelta(minutes=5),
        )
    )
    await store.record_delegation_run(
        DelegationRun(
            run_id="run-parent",
            session_id="sess-graph",
            task_id="task-graph",
            claim_id=identity.claim_id,
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


def _redirect_cron_storage(tmp_path, monkeypatch) -> None:
    cron_dir = tmp_path / "cron"
    monkeypatch.setattr(cron_scheduler, "DHARMA_DIR", tmp_path)
    monkeypatch.setattr(cron_scheduler, "CRON_DIR", cron_dir)
    monkeypatch.setattr(cron_scheduler, "JOBS_FILE", cron_dir / "jobs.json")
    monkeypatch.setattr(cron_scheduler, "OUTPUT_DIR", cron_dir / "output")
    monkeypatch.setattr(cron_scheduler, "LOCK_FILE", cron_dir / ".tick.lock")


async def _seed_agent_server_platform(store: RuntimeStateStore) -> None:
    base_time = datetime(2026, 6, 30, 22, 0, tzinfo=timezone.utc)
    lease_now = datetime.now(timezone.utc)
    await store.upsert_session(
        SessionState(
            session_id="sess-agent-server",
            operator_id="operator",
            status="active",
            current_task_id="task-background",
            metadata={
                "assistant_id": "ops-assistant",
                "assistant_name": "Ops Assistant",
                "configuration_id": "ops-assistant-config",
                "provider": "openrouter",
                "model": "openai/gpt-5.4",
                "tools": ["runtime_graph", "cron_tick"],
            },
        )
    )
    identity = ExecutionIdentity.new(
        trace_id="trace-background",
        correlation_id="corr-background",
        task_id="task-background",
        run_id="run-background",
        claim_id="claim-background",
        idempotency_key="idem-background",
        agent_id="ops-assistant",
        session_id="sess-agent-server",
    )
    await store.record_execution_identity(identity, source="test")
    await store.record_task_claim(
        TaskClaim(
            claim_id=identity.claim_id,
            task_id=identity.task_id,
            session_id=identity.session_id,
            agent_id=identity.agent_id,
            status="active",
            claimed_at=lease_now - timedelta(minutes=3),
            acked_at=lease_now - timedelta(minutes=2),
            heartbeat_at=lease_now - timedelta(minutes=1),
            stale_after=lease_now + timedelta(minutes=5),
        )
    )
    await store.record_delegation_run(
        DelegationRun(
            run_id="run-background",
            session_id="sess-agent-server",
            task_id="task-background",
            claim_id=identity.claim_id,
            assigned_to="ops-assistant",
            assigned_by="cron_scheduler",
            status="in_progress",
            metadata={
                "assistant_id": "ops-assistant",
                "assistant_name": "Ops Assistant",
                "configuration_id": "ops-assistant-config",
                "provider": "openrouter",
                "model": "openai/gpt-5.4",
                "run_kind": "background",
                "cron_job_id": "cron-nightly",
                "tools": ["runtime_graph", "cron_tick"],
            },
        )
    )
    await store.record_session_event(
        SessionEventRecord(
            event_id="event-cron-fired",
            session_id="sess-agent-server",
            ledger_kind="background",
            event_name="cron_job_started",
            task_id="task-background",
            run_id="run-background",
            agent_id="ops-assistant",
            summary="Nightly background job started",
            event_text="Cron scheduler started the background runtime job.",
            payload={"cron_job_id": "cron-nightly", "schedule_id": "nightly"},
            created_at=base_time,
        )
    )


def _seed_cron_job() -> None:
    cron_scheduler.save_jobs(
        [
            {
                "id": "cron-nightly",
                "name": "Nightly runtime sweep",
                "prompt": "Inspect runtime graph and checkpoint drift.",
                "schedule": {"kind": "interval", "minutes": 60, "display": "every 60m"},
                "schedule_display": "every 60m",
                "repeat": {"times": None, "completed": 3},
                "enabled": True,
                "urgent": False,
                "created_at": "2026-06-30T21:00:00+00:00",
                "next_run_at": "2026-06-30T23:00:00+00:00",
                "last_run_at": "2026-06-30T22:00:00+00:00",
                "last_status": "ok",
                "last_error": None,
                "deliver": "local",
            }
        ]
    )
    cron_scheduler.save_job_output("cron-nightly", "# Nightly runtime sweep\n")


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
    assert snapshot["summary"]["observed_nonterminal_run_count"] == 1
    assert snapshot["summary"]["expired_or_unproven_run_count"] == 0
    assert snapshot["summary"]["proves_executor_liveness"] is False
    assert snapshot["active_agents"] == ["supervisor"]
    assert snapshot["topology_active_agents"] == ["worker-a"]
    parent_run = next(run for run in snapshot["runs"] if run["run_id"] == "run-parent")
    assert parent_run["activity"]["state"] == "current_lease"
    assert parent_run["activity"]["proves_executor_liveness"] is False
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
    assert sessions["summary"]["active_session_count"] == 1
    assert sessions["summary"]["stored_active_session_count"] == 1
    assert sessions["summary"]["proves_executor_liveness"] is False
    assert sessions["sessions"][0]["current_task_id"] == "task-graph"
    assert sessions["sessions"][0]["activity"]["current_lease"] is True
    assert sessions["sessions"][0]["metadata"]["surface"] == "phase7-runtime-platform"

    assert runs["schema_version"] == "runtime_runs_snapshot.v1"
    assert runs["summary"]["run_count"] == 2
    assert runs["summary"]["current_lease_run_count"] == 1
    assert runs["summary"]["proves_executor_liveness"] is False
    parent = next(run for run in runs["runs"] if run["run_id"] == "run-parent")
    assert parent["checkpoint_id"] == "task-graph:supervisor:checkpoint-1"
    assert parent["active_agent"] == "worker-a"
    assert parent["activity"]["state"] == "current_lease"

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
async def test_operator_views_runtime_agent_server_surfaces(tmp_path, monkeypatch) -> None:
    _redirect_cron_storage(tmp_path, monkeypatch)
    _seed_cron_job()
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await _seed_agent_server_platform(store)
    views = OperatorViews(store)

    assistants = await views.runtime_assistants(limit=10)
    background = await views.runtime_background_jobs(limit=10)

    assert assistants["schema_version"] == "runtime_assistants_snapshot.v1"
    assert assistants["summary"]["assistant_count"] == 1
    assert assistants["summary"]["configuration_count"] == 1
    assert assistants["summary"]["active_assistant_count"] == 1
    assert assistants["summary"]["observed_nonterminal_run_count"] == 1
    assert assistants["summary"]["proves_executor_liveness"] is False
    assert assistants["assistants"][0]["assistant_id"] == "ops-assistant"
    assert assistants["assistants"][0]["active_run_count"] == 1
    assert assistants["configurations"][0]["configuration_id"] == "ops-assistant-config"
    assert assistants["configurations"][0]["tool_count"] == 2

    assert background["schema_version"] == "runtime_background_jobs_snapshot.v1"
    assert background["summary"]["cron_job_count"] == 1
    assert background["summary"]["enabled_cron_job_count"] == 1
    assert background["summary"]["background_run_count"] == 1
    assert background["summary"]["active_background_run_count"] == 1
    assert background["summary"]["observed_nonterminal_run_count"] == 1
    assert background["summary"]["proves_executor_liveness"] is False
    assert background["summary"]["background_event_count"] == 1
    assert background["cron_jobs"][0]["job_id"] == "cron-nightly"
    assert background["cron_jobs"][0]["output_count"] == 1
    assert background["background_runs"][0]["cron_job_id"] == "cron-nightly"
    assert background["background_runs"][0]["activity"]["state"] == "current_lease"
    assert background["background_events"][0]["event_id"] == "event-cron-fired"


@pytest.mark.asyncio
async def test_operator_views_runtime_control_actions_record_canonical_state(
    tmp_path,
    monkeypatch,
) -> None:
    checkpoint = importlib.import_module("dharma_swarm.checkpoint")
    monkeypatch.setattr(checkpoint, "INTERRUPT_DIR", tmp_path / "interrupts")
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await _seed_runtime_graph(store)
    views = OperatorViews(store)

    result = await views.runtime_control_action(
        action="approve",
        session_id="sess-graph",
        approval_id="approval-1",
        interrupt_id="interrupt-1",
        actor="operator",
        reason="Approved through runtime API",
        payload={"note": "continue"},
    )

    assert result["schema_version"] == "runtime_control_action_result.v1"
    assert result["action"] == "approve"
    assert result["status"] == "approved"
    assert result["target_found"] is True
    assert result["target_control_event"]["event_id"] == "event-interrupt-requested"
    assert result["operator_action"]["action_name"] == "runtime_control.approve"
    assert result["event"]["event_name"] == "human_approval_approved"
    assert result["event"]["payload"]["runtime_action_id"] == result["operator_action"]["action_id"]
    assert result["interrupt_transport"]["attempted"] is True
    assert result["interrupt_transport"]["response_path"].endswith(
        "interrupt-1.response.json"
    )

    response = checkpoint.read_interrupt_response("interrupt-1")
    assert response is not None
    assert response.decision.value == "approve"

    actions = await store.list_operator_actions(session_id="sess-graph", limit=10)
    assert actions[0].action_name == "runtime_control.approve"
    interrupts = await views.runtime_interrupts(session_id="sess-graph", limit=10)
    assert interrupts["summary"]["control_event_count"] == 3
    assert interrupts["summary"]["approved_count"] == 2
    assert interrupts["control_events"][0]["event_name"] == "human_approval_approved"


@pytest.mark.asyncio
async def test_runtime_resume_action_survives_fresh_python_process(tmp_path) -> None:
    db_path = tmp_path / "runtime.db"
    store = RuntimeStateStore(db_path, include_memory_plane=False)
    await _seed_runtime_graph(store)

    child_code = """
import asyncio
import json
import os
import sys

from api.routers.runtime import RuntimeControlActionRequest, runtime_interrupt_resume


async def main() -> None:
    os.environ["DHARMA_RUNTIME_DB"] = sys.argv[1]
    response = await runtime_interrupt_resume(
        RuntimeControlActionRequest(
            session_id="sess-graph",
            run_id="run-parent",
            resume_token="resume-run-parent",
            actor="operator",
            reason="resume from child process",
            payload={"multiprocess_probe": True},
        )
    )
    result = response.data
    print(json.dumps({
        "api_status": response.status,
        "runtime_db": result["runtime_db"],
        "status": result["status"],
        "target_found": result["target_found"],
        "target_event_id": result["target_control_event"]["event_id"],
        "event_name": result["event"]["event_name"],
        "runtime_action_id": result["event"]["payload"]["runtime_action_id"],
    }, sort_keys=True))


asyncio.run(main())
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        child_code,
        str(db_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    assert process.returncode == 0, stderr.decode()
    child_payload = json.loads(stdout.decode().strip().splitlines()[-1])

    assert child_payload["api_status"] == "ok"
    assert child_payload["runtime_db"] == str(db_path)
    assert child_payload["status"] == "resumed"
    assert child_payload["target_found"] is True
    assert child_payload["target_event_id"] == "event-interrupt-requested"
    assert child_payload["event_name"] == "runtime_resume_requested"

    reopened_store = RuntimeStateStore(db_path, include_memory_plane=False)
    reopened_views = OperatorViews(reopened_store)
    interrupts = await reopened_views.runtime_interrupts(session_id="sess-graph", limit=10)
    detail = await reopened_views.runtime_run_detail("run-parent")
    actions = await reopened_store.list_operator_actions(session_id="sess-graph", limit=10)

    assert interrupts["summary"]["control_event_count"] == 3
    assert interrupts["summary"]["resumed_count"] == 1
    assert interrupts["control_events"][0]["event_name"] == "runtime_resume_requested"
    assert interrupts["control_events"][0]["resume_token"] == "resume-run-parent"
    assert detail["detail"]["topology_state"]["checkpoint_id"] == (
        "task-graph:supervisor:checkpoint-1"
    )
    assert actions[0].action_id == child_payload["runtime_action_id"]
    assert actions[0].action_name == "runtime_control.resume"
    assert actions[0].payload["multiprocess_probe"] is True


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
        RuntimeControlActionRequest,
        runtime_assistants,
        runtime_background_jobs,
        runtime_checkpoints,
        runtime_events,
        runtime_events_stream,
        runtime_interrupt_approve,
        runtime_interrupt_reject,
        runtime_interrupt_resume,
        runtime_interrupts,
        runtime_run_detail,
        runtime_runs,
        runtime_sessions,
    )
    _redirect_cron_storage(tmp_path, monkeypatch)
    _seed_cron_job()
    await _seed_agent_server_platform(store)

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
    assistants = await runtime_assistants(limit=10)
    background = await runtime_background_jobs(limit=10)
    approval = await runtime_interrupt_approve(
        RuntimeControlActionRequest(
            session_id="sess-graph",
            approval_id="approval-1",
            interrupt_id="interrupt-1",
            actor="operator",
            reason="approved from api test",
        )
    )
    rejection = await runtime_interrupt_reject(
        RuntimeControlActionRequest(
            session_id="sess-graph",
            run_id="run-parent",
            actor="operator",
            reason="rejected from api test",
        )
    )
    resume = await runtime_interrupt_resume(
        RuntimeControlActionRequest(
            session_id="sess-graph",
            run_id="run-parent",
            resume_token="resume-run-parent",
            actor="operator",
            reason="resume from api test",
        )
    )

    assert sessions.status == "ok"
    assert sessions.data["runtime_db"] == str(db_path)
    assert {session["session_id"] for session in sessions.data["sessions"]} >= {
        "sess-graph",
        "sess-agent-server",
    }

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

    assert assistants.status == "ok"
    assert assistants.data["summary"]["assistant_count"] >= 1
    assert {item["assistant_id"] for item in assistants.data["assistants"]} >= {
        "ops-assistant"
    }
    assert background.status == "ok"
    assert background.data["summary"]["cron_job_count"] == 1
    assert background.data["background_runs"][0]["run_id"] == "run-background"

    assert approval.status == "ok"
    assert approval.data["action"] == "approve"
    assert approval.data["operator_action"]["action_name"] == "runtime_control.approve"
    assert rejection.status == "ok"
    assert rejection.data["status"] == "rejected"
    assert resume.status == "ok"
    assert resume.data["event"]["event_name"] == "runtime_resume_requested"


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
    assert "/api/runtime/interrupts/approve" in paths
    assert "/api/runtime/interrupts/reject" in paths
    assert "/api/runtime/interrupts/resume" in paths
    assert "/api/runtime/assistants" in paths
    assert "/api/runtime/background-jobs" in paths
