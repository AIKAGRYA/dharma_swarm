from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import sys
import time
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

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_SCRIPT = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_service.py"


def _envelope(correlation_id: str) -> AgentRunEnvelope:
    return AgentRunEnvelope(
        agent_uid="codex_composer",
        task=KernelTask(text=f"Daemon e2e wake {correlation_id}"),
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
            verifier_commands=["pytest tests/test_living_agent_kernel_daemon_e2e.py"],
            receipt_refs=[{"kind": "context_quorum", "path": "context_manifest.latest.json"}],
        ),
    )


def _seed_store(store_dir: Path, workspace_root: Path, wake_ids: list[str]) -> None:
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=workspace_root)
    for index, wake_id in enumerate(wake_ids):
        kernel.enqueue_wake(_envelope(f"e2e-{index}"), wake_id=wake_id)


def _run_cli(
    store_dir: Path,
    workspace_root: Path,
    *,
    cycles: int = 2,
    max_wakes: int = 1,
    extra: list[str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    argv = [
        sys.executable,
        str(SERVICE_SCRIPT),
        "--store-dir",
        str(store_dir),
        "--workspace-root",
        str(workspace_root),
        "--cycles",
        str(cycles),
        "--max-wakes",
        str(max_wakes),
        "--interval-seconds",
        "0",
        "--json",
        *(extra or []),
    ]
    return subprocess.run(
        argv,
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# unit
# ---------------------------------------------------------------------------


def test_in_process_drain_without_injected_clock_writes_both_ledgers(tmp_path):
    store_dir = tmp_path / "kernel"
    _seed_store(store_dir, tmp_path, ["wake-u1", "wake-u2"])

    result = run_kernel_daemon_service(
        store_dir=store_dir,
        workspace_root=tmp_path,
        daemon_id="kernel-e2e",
        cycles=2,
        max_wakes=1,
        interval_seconds=0,
    )

    assert result.status == "completed"
    assert result.completed_cycles == 2
    assert [cycle.status for cycle in result.cycles] == ["completed", "completed"]
    assert all(cycle.tick is not None and cycle.tick.executions for cycle in result.cycles)

    fresh = KernelRunStore(store_dir)
    latest = fresh.latest_wake_records()
    assert latest["wake-u1"].status == "completed"
    assert latest["wake-u2"].status == "completed"
    assert fresh.wake_ledger_path.exists()
    assert fresh.daemon_cycles_path.exists()
    assert len(fresh.daemon_cycles()) == 2


def test_in_process_run_creates_and_releases_real_lock(tmp_path):
    store_dir = tmp_path / "kernel"
    _seed_store(store_dir, tmp_path, ["wake-lock-1"])

    result = run_kernel_daemon_service(
        store_dir=store_dir,
        workspace_root=tmp_path,
        daemon_id="kernel-e2e",
        cycles=1,
        max_wakes=1,
        interval_seconds=0,
    )

    lock_path = Path(result.lock_ref["path"])
    assert result.lock_ref["kind"] == "kernel_daemon_service_lock"
    assert lock_path == store_dir / "daemon_service.lock"
    assert lock_path.exists()
    assert "held" not in result.lock_ref
    # The lock is released after the run: a fresh non-blocking acquire succeeds.
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(handle, fcntl.LOCK_UN)


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------


def test_real_subprocess_drains_preseeded_store_and_reloads_from_disk(tmp_path):
    store_dir = tmp_path / "kernel"
    wake_ids = ["wake-i1", "wake-i2"]
    _seed_store(store_dir, tmp_path, wake_ids)

    completed = _run_cli(store_dir, tmp_path, cycles=2, max_wakes=1)
    payload = json.loads(completed.stdout)

    assert payload["status"] == "completed"
    assert payload["completed_cycles"] == 2
    for cycle in payload["cycles"]:
        assert cycle["status"] == "completed"
        assert cycle["tick"] is not None
        assert cycle["tick"]["executions"], "drain must be real, not idle"

    fresh = KernelRunStore(store_dir)
    assert fresh.wake_ledger_path.exists()
    assert fresh.daemon_cycles_path.exists()
    latest = fresh.latest_wake_records()
    for wake_id in wake_ids:
        assert latest[wake_id].status == "completed"

    cycles = fresh.daemon_cycles()
    assert len(cycles) == 2
    for cycle in cycles:
        assert cycle.tick is not None
        assert cycle.status == "completed"


def test_cross_process_hash_chain_integrity_holds_after_subprocess(tmp_path):
    store_dir = tmp_path / "kernel"
    _seed_store(store_dir, tmp_path, ["wake-h1", "wake-h2"])

    _run_cli(store_dir, tmp_path, cycles=2, max_wakes=1)

    fresh = KernelRunStore(store_dir)
    wake_ok, wake_errors = fresh.verify_wake_ledger()
    cycle_ok, cycle_errors = fresh.verify_daemon_cycle_ledger()

    assert (wake_ok, wake_errors) == (True, [])
    assert cycle_ok is True
    assert cycle_errors == []


# ---------------------------------------------------------------------------
# adversarial
# ---------------------------------------------------------------------------


def test_second_concurrent_subprocess_returns_lock_held_and_writes_no_cycles(tmp_path):
    store_dir = tmp_path / "kernel"
    lock_path = store_dir / "daemon_service.lock"
    _seed_store(store_dir, tmp_path, ["wake-adv-lock"])
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with lock_path.open("w", encoding="utf-8") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        completed = _run_cli(store_dir, tmp_path, cycles=1, max_wakes=1, check=False)
        fcntl.flock(held, fcntl.LOCK_UN)

    payload = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert payload["status"] == "lock_held"
    assert payload["completed_cycles"] == 0
    assert payload["lock_ref"]["held"] is True

    fresh = KernelRunStore(store_dir)
    assert fresh.daemon_cycles() == []
    assert fresh.latest_wake_records()["wake-adv-lock"].status == "queued"


def test_durable_stop_receipt_exits_stopped_without_losing_wake(tmp_path):
    store_dir = tmp_path / "kernel"
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    kernel.enqueue_wake(_envelope("adv-stop"), wake_id="wake-adv-stop")
    kernel.request_daemon_control(
        "stop",
        daemon_id="kernel-e2e",
        requested_by="operator",
        reason="durable stop before subprocess",
    )

    completed = _run_cli(
        store_dir,
        tmp_path,
        cycles=3,
        max_wakes=1,
        extra=["--daemon-id", "kernel-e2e"],
    )
    payload = json.loads(completed.stdout)

    assert payload["status"] == "stopped"
    assert payload["completed_cycles"] == 1
    assert payload["cycles"][0]["status"] == "stopped"
    assert payload["cycles"][0]["tick"] is None

    fresh = KernelRunStore(store_dir)
    assert fresh.latest_wake_records()["wake-adv-stop"].status == "queued"


def test_forever_without_operator_flag_is_refused(tmp_path):
    store_dir = tmp_path / "kernel"
    _seed_store(store_dir, tmp_path, ["wake-forever"])

    completed = _run_cli(
        store_dir,
        tmp_path,
        cycles=1,
        max_wakes=1,
        extra=["--forever"],
        check=False,
    )

    assert completed.returncode == 3
    assert "refused" in completed.stderr.lower()
    assert completed.stdout.strip() == ""
    # No work happened: store has neither cycles nor a completed wake.
    fresh = KernelRunStore(store_dir)
    assert fresh.daemon_cycles() == []
    assert fresh.latest_wake_records()["wake-forever"].status == "queued"


# ---------------------------------------------------------------------------
# crash
# ---------------------------------------------------------------------------


def test_sigkill_midlease_leaves_leased_wake_recovered_by_followup_run(tmp_path):
    store_dir = tmp_path / "kernel"
    store = KernelRunStore(store_dir)
    kernel = LivingAgentKernel(store=store, workspace_root=tmp_path)
    kernel.enqueue_wake(_envelope("crash"), wake_id="wake-crash")

    # Simulate a crash mid-lease: a runner leased the wake with a short lease,
    # then died (SIGKILL) before completing it. We emulate the SIGKILL on a
    # real subprocess to prove the parent survives the kill, then reproduce the
    # on-disk "leased but not completed" state the crash leaves behind.
    victim = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
    )
    os.kill(victim.pid, signal.SIGKILL)
    victim.wait(timeout=5)
    assert victim.returncode == -signal.SIGKILL

    leased = store.lease_next_wake(lease_owner="dead-runner", lease_seconds=1)
    assert leased is not None and leased.status == "leased"
    assert leased.lease_expires_at

    # Crash-safe resumption reads ONLY the on-disk ledger. Let the lease expire,
    # then a follow-up service run with recover_expired re-queues and completes.
    time.sleep(1.1)
    result = run_kernel_daemon_service(
        store_dir=store_dir,
        workspace_root=tmp_path,
        daemon_id="kernel-e2e",
        cycles=1,
        max_wakes=1,
        interval_seconds=0,
        recover_expired=True,
    )

    assert result.status == "completed"
    assert result.cycles[0].tick is not None
    assert "wake-crash" in result.cycles[0].tick.recovered_wake_ids

    fresh = KernelRunStore(store_dir)
    assert fresh.latest_wake_records()["wake-crash"].status == "completed"
    wake_ok, wake_errors = fresh.verify_wake_ledger()
    assert (wake_ok, wake_errors) == (True, [])
