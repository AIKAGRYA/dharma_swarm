#!/usr/bin/env python3
"""Prove the runtime cockpit can inspect a live running graph in real time."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.models import AgentRole, AgentState, Task, TaskStatus, TopologyType  # noqa: E402
from dharma_swarm.orchestrator import Orchestrator  # noqa: E402
from dharma_swarm.runtime_state import RuntimeStateStore  # noqa: E402


class ProbeTaskBoard:
    def __init__(self, task: Task) -> None:
        self.tasks = [task]
        self.updates: list[tuple[str, dict[str, Any]]] = []

    async def get_ready_tasks(self) -> list[Task]:
        return [task for task in self.tasks if task.status == TaskStatus.PENDING]

    async def update_task(self, task_id: str, **fields: Any) -> None:
        self.updates.append((task_id, dict(fields)))
        for task in self.tasks:
            if task.id != task_id:
                continue
            if "status" in fields:
                task.status = fields["status"]
            if "assigned_to" in fields:
                task.assigned_to = fields["assigned_to"]
            if "result" in fields:
                task.result = fields["result"]
            if isinstance(fields.get("metadata"), dict):
                task.metadata = dict(fields["metadata"])
            return

    async def get(self, task_id: str) -> Task | None:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None


class ProbeAgentPool:
    def __init__(self, agents: list[AgentState]) -> None:
        self._agents = agents
        self._runners: dict[str, Any] = {}
        self.assignments: list[tuple[str, str]] = []
        self.releases: list[str] = []

    async def list_agents(self) -> list[AgentState]:
        return list(self._agents)

    async def get_idle_agents(self) -> list[AgentState]:
        return list(self._agents)

    async def assign(self, agent_id: str, task_id: str) -> None:
        self.assignments.append((agent_id, task_id))

    async def release(self, agent_id: str) -> None:
        self.releases.append(agent_id)

    async def get_result(self, agent_id: str) -> str | None:
        return None

    async def get(self, agent_id: str) -> Any:
        return self._runners.get(agent_id)

    def set_runner(self, agent_id: str, runner: Any) -> None:
        self._runners[agent_id] = runner


class BlockingRunner:
    """Local runner that keeps the graph in progress until the probe releases it."""

    def __init__(self, result: str = "live cockpit proof complete") -> None:
        self._config = None
        self._result = result
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def run_task(self, task: Task) -> str:
        self.started.set()
        await self.release.wait()
        return self._result


async def _wait_for(
    predicate: Any,
    *,
    timeout_seconds: float = 5.0,
    poll_seconds: float = 0.025,
) -> Any:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_value: Any = None
    while asyncio.get_running_loop().time() < deadline:
        last_value = await predicate()
        if last_value:
            return last_value
        await asyncio.sleep(poll_seconds)
    raise TimeoutError(f"condition was not met before timeout; last_value={last_value!r}")


async def _drain_running_tasks(orchestrator: Orchestrator) -> None:
    await _wait_for(
        lambda: _collect_done(orchestrator),
        timeout_seconds=10.0,
    )


async def _collect_done(orchestrator: Orchestrator) -> bool:
    await orchestrator._collect_completed()
    return not orchestrator._running_tasks


def _api_data(response: Any) -> dict[str, Any]:
    assert response.status == "ok", response.error
    assert isinstance(response.data, dict)
    return response.data


async def _runtime_api_snapshot(
    *,
    runtime_db: Path,
    session_id: str,
    task_id: str,
    run_id: str,
) -> dict[str, Any]:
    previous_runtime_db = os.environ.get("DHARMA_RUNTIME_DB")
    os.environ["DHARMA_RUNTIME_DB"] = str(runtime_db)
    try:
        from api.routers.runtime import (
            runtime_checkpoints,
            runtime_events,
            runtime_graph,
            runtime_run_detail,
            runtime_runs,
            runtime_sessions,
        )

        graph = _api_data(
            await runtime_graph(
                session_id=session_id,
                task_id=task_id,
                topology=None,
                limit=20,
                receipt_limit=50,
            )
        )
        runs = _api_data(
            await runtime_runs(
                session_id=session_id,
                task_id=task_id,
                status=None,
                limit=20,
            )
        )
        detail = _api_data(await runtime_run_detail(run_id=run_id))
        checkpoints = _api_data(
            await runtime_checkpoints(
                session_id=session_id,
                task_id=task_id,
                topology=None,
                limit=20,
            )
        )
        events = _api_data(
            await runtime_events(
                session_id=session_id,
                ledger_kind=None,
                event_name=None,
                limit=20,
            )
        )
        sessions = _api_data(await runtime_sessions(status=None, limit=20))
        return {
            "graph": graph,
            "runs": runs,
            "run_detail": detail,
            "checkpoints": checkpoints,
            "events": events,
            "sessions": sessions,
        }
    finally:
        if previous_runtime_db is None:
            os.environ.pop("DHARMA_RUNTIME_DB", None)
        else:
            os.environ["DHARMA_RUNTIME_DB"] = previous_runtime_db


def _running_graph_ready(store: RuntimeStateStore, *, session_id: str, task_id: str) -> Any:
    async def _predicate() -> dict[str, Any] | None:
        from dharma_swarm.operator_views import OperatorViews

        snapshot = await OperatorViews(store).runtime_graph(
            session_id=session_id,
            task_id=task_id,
            limit=20,
            receipt_limit=50,
        )
        if (
            snapshot["summary"]["active_run_count"] >= 1
            and snapshot["topology_states"]
            and snapshot["topology_states"][0]["state"].get("status") == "running"
        ):
            return snapshot
        return None

    return _predicate


def _assert_running_snapshot(
    *,
    snapshot: dict[str, Any],
    task_id: str,
    run_id: str,
) -> None:
    graph = snapshot["graph"]
    runs = snapshot["runs"]
    detail = snapshot["run_detail"]
    checkpoints = snapshot["checkpoints"]
    events = snapshot["events"]

    assert graph["summary"]["active_run_count"] >= 1
    assert graph["summary"]["active_agent_count"] >= 1
    assert graph["topology_states"][0]["run_id"] == run_id
    assert graph["topology_states"][0]["task_id"] == task_id
    assert graph["topology_states"][0]["topology"] == "supervisor"
    assert graph["topology_states"][0]["active_agent"] == "lead"
    assert graph["topology_states"][0]["state"]["status"] == "running"
    assert graph["topology_states"][0]["state"]["supervisor_final_output_only"] is True
    assert "lead" in graph["active_agents"]

    run_statuses = {run["run_id"]: run["status"] for run in runs["runs"]}
    assert run_statuses[run_id] == "running"
    assert detail["found"] is True
    assert detail["detail"]["run"]["status"] == "running"
    assert detail["detail"]["topology_state"]["state"]["status"] == "running"
    assert checkpoints["summary"]["checkpoint_count"] >= 1
    assert checkpoints["checkpoints"][0]["run_id"] == run_id
    assert events["summary"]["event_count"] >= 1


async def run_probe(
    *,
    runtime_db: Path,
    ledger_dir: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    task_id = "phase7-live-cockpit-task"
    session_id = "phase7-live-cockpit-session"
    task = Task(
        id=task_id,
        title="Phase 7 live cockpit proof",
        description="Dispatch a real in-progress supervisor graph for cockpit/API inspection.",
        metadata={
            "active_agent": "lead",
            "requested_output": ["runtime_cockpit_proof"],
            "assistant_id": "phase7-live-cockpit",
            "assistant_name": "Phase 7 Live Cockpit",
            "configuration_id": "phase7-live-cockpit-local",
            "provider": "orchestrator",
            "model": "blocking-local-runner",
        },
    )
    board = ProbeTaskBoard(task)
    pool = ProbeAgentPool(
        [
            AgentState(id="lead", name="lead", role=AgentRole.GENERAL),
            AgentState(id="worker-a", name="worker-a", role=AgentRole.CODER),
            AgentState(id="worker-b", name="worker-b", role=AgentRole.TESTER),
        ]
    )
    runner = BlockingRunner()
    pool.set_runner("lead", runner)
    orchestrator = Orchestrator(
        task_board=board,
        agent_pool=pool,
        ledger_dir=ledger_dir,
        runtime_db_path=runtime_db,
        session_id=session_id,
    )
    store = RuntimeStateStore(runtime_db, include_memory_plane=False)

    previous_fast_boot = os.environ.get("DHARMA_FAST_BOOT")
    os.environ["DHARMA_FAST_BOOT"] = "1"
    try:
        dispatches = await orchestrator.dispatch(task, topology=TopologyType.SUPERVISOR)
        assert len(dispatches) == 1
        dispatch = dispatches[0]
        run_id = str(dispatch.metadata["runtime_run_id"])

        await asyncio.wait_for(runner.started.wait(), timeout=5.0)
        operator_running_graph = await _wait_for(
            _running_graph_ready(store, session_id=session_id, task_id=task_id),
            timeout_seconds=5.0,
        )
        running_api = await _runtime_api_snapshot(
            runtime_db=runtime_db,
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
        )
        _assert_running_snapshot(snapshot=running_api, task_id=task_id, run_id=run_id)
        still_running_before_release = bool(orchestrator._running_tasks)
        assert still_running_before_release is True

        runner.release.set()
        await _drain_running_tasks(orchestrator)
        completed_api = await _runtime_api_snapshot(
            runtime_db=runtime_db,
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
        )
        completed_detail = completed_api["run_detail"]["detail"]["run"]
        assert completed_detail["status"] == "completed"

        proof = {
            "schema_version": "dharma.langgraph_parity.phase7_live_cockpit_probe.v1",
            "runtime_db": str(runtime_db),
            "session_id": session_id,
            "task_id": task_id,
            "run_id": run_id,
            "topology": "supervisor",
            "dispatches": [
                {
                    "task_id": item.task_id,
                    "agent_id": item.agent_id,
                    "topology": item.topology.value,
                    "runtime_run_id": item.metadata.get("runtime_run_id"),
                }
                for item in dispatches
            ],
            "observed_while_runner_blocked": still_running_before_release,
            "operator_running_summary": operator_running_graph["summary"],
            "api_running_summary": running_api["graph"]["summary"],
            "running_graph_assertions": {
                "active_agent": running_api["graph"]["topology_states"][0]["active_agent"],
                "run_status": running_api["run_detail"]["detail"]["run"]["status"],
                "topology_state_status": running_api["graph"]["topology_states"][0]["state"]["status"],
                "checkpoint_id": running_api["checkpoints"]["checkpoints"][0]["checkpoint_id"],
                "event_count": running_api["events"]["summary"]["event_count"],
            },
            "completed_summary": {
                "run_status": completed_detail["status"],
                "active_run_count": completed_api["graph"]["summary"]["active_run_count"],
            },
            "claim": (
                "A real Orchestrator SUPERVISOR dispatch stayed in progress while "
                "OperatorViews and the RuntimeStateStore-backed API read the same "
                "running graph, active agent, checkpoint, run detail, and event state."
            ),
        }
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
        return proof
    finally:
        runner.release.set()
        for task_obj in list(orchestrator._running_tasks.values()):
            if not task_obj.done():
                task_obj.cancel()
        if previous_fast_boot is None:
            os.environ.pop("DHARMA_FAST_BOOT", None)
        else:
            os.environ["DHARMA_FAST_BOOT"] = previous_fast_boot


async def _main_async(args: argparse.Namespace) -> None:
    if args.runtime_db:
        runtime_db = Path(args.runtime_db)
        ledger_dir = Path(args.ledger_dir or runtime_db.parent / "ledgers")
        runtime_db.parent.mkdir(parents=True, exist_ok=True)
    else:
        temp_root = Path(tempfile.mkdtemp(prefix="dharma-live-cockpit-"))
        runtime_db = temp_root / "runtime.db"
        ledger_dir = temp_root / "ledgers"
    proof = await run_probe(
        runtime_db=runtime_db,
        ledger_dir=ledger_dir,
        output_path=Path(args.output) if args.output else None,
    )
    print(json.dumps(proof, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-db", help="Runtime DB path to use for the proof.")
    parser.add_argument("--ledger-dir", help="Session ledger directory for the proof.")
    parser.add_argument("--output", help="Optional JSON proof output path.")
    args = parser.parse_args()
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
