from __future__ import annotations

import fcntl
import json
import subprocess
import sys
from pathlib import Path

from dharma_swarm.operator_core.living_agent_kernel import (
    AgentRunEnvelope,
    KernelRunStore,
    KernelTask,
    LivingAgentKernel,
    MemoryPlan,
    ProofRequest,
    ToolRequest,
    TriggerEnvelope,
)
from dharma_swarm.operator_core.living_agent_kernel_service import run_kernel_daemon_service


def _envelope(correlation_id: str) -> AgentRunEnvelope:
    return AgentRunEnvelope(
        agent_uid="codex_composer",
        task=KernelTask(text=f"Service wake {correlation_id}"),
        trigger=TriggerEnvelope(source="manual", correlation_id=correlation_id),
        memory=MemoryPlan(
            read_namespaces=["agent:codex_composer:working"],
            write_namespaces=["agent:codex_composer:lessons"],
        ),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
        proof=ProofRequest(
            verifier_commands=["pytest tests/test_living_agent_kernel_service.py"],
            receipt_refs=[{"kind": "context_quorum", "path": "context_manifest.latest.json"}],
        ),
    )


def test_service_runner_runs_bounded_cycles_under_lock(tmp_path):
    store_dir = tmp_path / "kernel"
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    kernel.enqueue_wake(_envelope("service-1"), wake_id="wake-service-1")
    kernel.enqueue_wake(_envelope("service-2"), wake_id="wake-service-2")
    observed_sleeps: list[float] = []
    observed_times = iter([
        "2026-06-05T00:00:00Z",
        "2026-06-05T00:00:05Z",
    ])

    result = run_kernel_daemon_service(
        store_dir=store_dir,
        workspace_root=tmp_path,
        daemon_id="kernel-service",
        cycles=2,
        max_wakes=1,
        interval_seconds=5,
        sleep_fn=observed_sleeps.append,
        now_fn=lambda: next(observed_times),
    )
    latest = KernelRunStore(store_dir).latest_wake_records()
    cycles = KernelRunStore(store_dir).daemon_cycles()

    assert result.status == "completed"
    assert result.completed_cycles == 2
    assert [cycle.status for cycle in result.cycles] == ["completed", "completed"]
    assert latest["wake-service-1"].status == "completed"
    assert latest["wake-service-2"].status == "completed"
    assert observed_sleeps == [5.0]
    assert len(cycles) == 2
    assert cycles[0].heartbeat_ref["cycle_id"] == result.cycles[0].cycle_id


def test_service_runner_stops_on_durable_stop_without_losing_wake(tmp_path):
    store_dir = tmp_path / "kernel"
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    kernel.enqueue_wake(_envelope("service-stop"), wake_id="wake-service-stop")
    kernel.request_daemon_control(
        "stop",
        daemon_id="kernel-service",
        requested_by="operator",
        reason="stop service",
        now="2026-06-05T00:00:00Z",
    )

    result = run_kernel_daemon_service(
        store_dir=store_dir,
        workspace_root=tmp_path,
        daemon_id="kernel-service",
        cycles=5,
        max_wakes=1,
        now_fn=lambda: "2026-06-05T00:00:01Z",
    )
    latest = KernelRunStore(store_dir).latest_wake_records()["wake-service-stop"]

    assert result.status == "stopped"
    assert result.completed_cycles == 1
    assert result.cycles[0].status == "stopped"
    assert result.cycles[0].tick is None
    assert latest.status == "queued"


def test_service_runner_lock_prevents_split_brain(tmp_path):
    store_dir = tmp_path / "kernel"
    lock_path = tmp_path / "kernel-service.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = run_kernel_daemon_service(
            store_dir=store_dir,
            workspace_root=tmp_path,
            daemon_id="kernel-service",
            cycles=1,
            lock_path=lock_path,
        )
        fcntl.flock(lock_handle, fcntl.LOCK_UN)

    assert result.status == "lock_held"
    assert result.completed_cycles == 0
    assert KernelRunStore(store_dir).daemon_cycles() == []


def test_service_cli_json_runs_one_cycle(tmp_path):
    store_dir = tmp_path / "kernel"
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "runtime" / "living_agent_kernel_service.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--store-dir",
            str(store_dir),
            "--workspace-root",
            str(tmp_path),
            "--cycles",
            "1",
            "--interval-seconds",
            "1",
            "--json",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["status"] == "completed"
    assert payload["completed_cycles"] == 1
    assert payload["cycles"][0]["status"] == "idle"
