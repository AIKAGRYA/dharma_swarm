from __future__ import annotations

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
from dharma_swarm.operator_core.living_agent_kernel_activation import install_supervisor_plan
from dharma_swarm.operator_core.living_agent_kernel_recovery import (
    build_kernel_crash_resume_snapshot,
    recover_kernel_after_crash,
)
from dharma_swarm.operator_core.living_agent_kernel_supervisor import build_supervisor_plan, write_supervisor_plan
from dharma_swarm.operator_core.living_agent_kernel_workers import KernelExternalWorkerStore


REPO_ROOT = Path(__file__).resolve().parents[1]


def _envelope(correlation_id: str, *, source: str = "manual") -> AgentRunEnvelope:
    return AgentRunEnvelope(
        agent_uid="codex_composer",
        task=KernelTask(text=f"Recovery wake {correlation_id}"),
        trigger=TriggerEnvelope(source=source, correlation_id=correlation_id),
        memory=MemoryPlan(
            read_namespaces=["agent:codex_composer:working"],
            write_namespaces=["agent:codex_composer:lessons"],
        ),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
        proof=ProofRequest(
            verifier_commands=["pytest tests/test_living_agent_kernel_recovery.py"],
            receipt_refs=[{"kind": "context_quorum", "path": "context_manifest.latest.json"}],
        ),
    )


def _install_launch_artifact(store_dir: Path, workspace_root: Path):
    plan = write_supervisor_plan(
        build_supervisor_plan(
            mode="launchd",
            repo_root=REPO_ROOT,
            store_dir=store_dir,
            workspace_root=workspace_root,
            label="com.dharma.recovery-test",
        )
    )
    return install_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=store_dir / "LaunchAgents",
        now="2026-06-06T00:00:00Z",
    )


def test_crash_resume_snapshot_reconstructs_cross_ledger_state(tmp_path):
    store_dir = tmp_path / "kernel"
    store = KernelRunStore(store_dir)
    kernel = LivingAgentKernel(store=store, workspace_root=tmp_path)
    workers = KernelExternalWorkerStore(store_dir)
    _install_launch_artifact(store_dir, tmp_path)
    kernel.run_daemon_cycle(max_wakes=0, now="2026-06-06T00:00:00Z")
    store.enqueue_wake(_envelope("queued", source="manual"), wake_id="wake-queued", now="2026-06-06T00:00:01Z")
    store.enqueue_wake(_envelope("stale", source="stale-source"), wake_id="wake-stale", now="2026-06-06T00:00:01Z")
    store.enqueue_wake(_envelope("done", source="done-source"), wake_id="wake-done", now="2026-06-06T00:00:01Z")
    workers.register_worker("stale-worker", allowed_sources=["stale-source"], now="2026-06-06T00:00:00Z")
    workers.heartbeat_worker("stale-worker", now="2026-06-06T00:00:00Z")
    workers.lease_worker_wake("stale-worker", lease_seconds=1, now="2026-06-06T00:00:01Z")
    workers.register_worker("done-worker", allowed_sources=["done-source"], now="2026-06-06T00:00:00Z")
    workers.heartbeat_worker("done-worker", now="2026-06-06T00:00:04Z")
    workers.lease_worker_wake("done-worker", lease_seconds=30, now="2026-06-06T00:00:02Z")
    workers.complete_worker_wake(
        "done-worker",
        "wake-done",
        status="completed",
        result_ref={"artifact": "done.json"},
        now="2026-06-06T00:00:03Z",
    )

    snapshot = build_kernel_crash_resume_snapshot(
        store_dir=store_dir,
        now="2026-06-06T00:00:05Z",
        stale_after_seconds=1,
        offline_after_seconds=100,
    )

    assert snapshot.status == "needs_recovery"
    assert snapshot.integrity_ok is True
    assert "wake-stale" in snapshot.expired_worker_lease_wake_ids
    assert "wake-queued" in snapshot.queued_wake_ids
    assert snapshot.supervisor_ref["status"] == "recent"
    assert snapshot.launch_status_refs[0]["status"] == "installed"
    assert snapshot.worker_result_refs[0]["wake_id"] == "wake-done"
    assert {state["status"] for state in snapshot.worker_states} == {"online", "stale"}
    assert "recover_stale_worker_leases" in snapshot.next_actions


def test_crash_recovery_requeues_stale_worker_lease_without_stealing_fresh_worker(tmp_path):
    store_dir = tmp_path / "kernel"
    store = KernelRunStore(store_dir)
    workers = KernelExternalWorkerStore(store_dir)
    store.enqueue_wake(_envelope("stale"), wake_id="wake-stale", now="2026-06-06T00:00:00Z")
    store.enqueue_wake(_envelope("fresh"), wake_id="wake-fresh", now="2026-06-06T00:00:00Z")
    workers.register_worker("stale-worker", allowed_sources=["manual"], now="2026-06-06T00:00:00Z")
    workers.register_worker("fresh-worker", allowed_sources=["manual"], now="2026-06-06T00:00:00Z")
    workers.heartbeat_worker("stale-worker", now="2026-06-06T00:00:00Z")
    workers.heartbeat_worker("fresh-worker", now="2026-06-06T00:00:00Z")
    workers.lease_worker_wake("stale-worker", lease_seconds=1, now="2026-06-06T00:00:00Z")
    workers.lease_worker_wake("fresh-worker", lease_seconds=1, now="2026-06-06T00:00:00Z")
    workers.heartbeat_worker("fresh-worker", now="2026-06-06T00:00:02Z")

    result = recover_kernel_after_crash(
        store_dir=store_dir,
        now="2026-06-06T00:00:03Z",
        stale_after_seconds=1,
        offline_after_seconds=100,
    )
    latest = KernelRunStore(store_dir).latest_wake_records()

    assert result.status == "completed"
    assert result.before.expired_worker_lease_wake_ids == ["wake-stale"]
    assert result.worker_recovery_ref["recovered_wake_ids"] == ["wake-stale"]
    assert result.direct_recovered_wake_ids == []
    assert latest["wake-stale"].status == "queued"
    assert latest["wake-fresh"].status == "leased"
    assert latest["wake-fresh"].lease_owner == "fresh-worker"
    assert result.after is not None
    assert result.after.expired_worker_lease_wake_ids == []


def test_crash_recovery_blocks_when_wake_ledger_is_tampered(tmp_path):
    store_dir = tmp_path / "kernel"
    store = KernelRunStore(store_dir)
    store.enqueue_wake(_envelope("tamper"), wake_id="wake-tamper", now="2026-06-06T00:00:00Z")
    ledger = store_dir / "wake_ledger.jsonl"
    rows = ledger.read_text(encoding="utf-8").splitlines()
    payload = json.loads(rows[0])
    payload["reason"] = "tampered"
    ledger.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

    result = recover_kernel_after_crash(store_dir=store_dir, now="2026-06-06T00:00:03Z")

    assert result.status == "blocked"
    assert result.after is None
    assert result.before.status == "blocked"
    assert any(ref.name == "wake_ledger" and not ref.ok for ref in result.before.integrity_refs)


def test_recovery_cli_snapshot_and_recover(tmp_path):
    script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_recovery.py"
    store_dir = tmp_path / "kernel"
    store = KernelRunStore(store_dir)
    workers = KernelExternalWorkerStore(store_dir)
    store.enqueue_wake(_envelope("cli"), wake_id="wake-cli", now="2026-06-06T00:00:00Z")
    workers.register_worker("cli-worker", allowed_sources=["manual"], now="2026-06-06T00:00:00Z")
    workers.heartbeat_worker("cli-worker", now="2026-06-06T00:00:00Z")
    workers.lease_worker_wake("cli-worker", lease_seconds=1, now="2026-06-06T00:00:00Z")

    snapshot = subprocess.run(
        [
            sys.executable,
            str(script),
            "snapshot",
            "--store-dir",
            str(store_dir),
            "--now",
            "2026-06-06T00:00:03Z",
            "--stale-after-seconds",
            "1",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    recovered = subprocess.run(
        [
            sys.executable,
            str(script),
            "recover",
            "--store-dir",
            str(store_dir),
            "--now",
            "2026-06-06T00:00:03Z",
            "--stale-after-seconds",
            "1",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    snapshot_payload = json.loads(snapshot.stdout)
    recovered_payload = json.loads(recovered.stdout)

    assert snapshot_payload["status"] == "needs_recovery"
    assert snapshot_payload["expired_worker_lease_wake_ids"] == ["wake-cli"]
    assert recovered_payload["status"] == "completed"
    assert recovered_payload["worker_recovery_ref"]["recovered_wake_ids"] == ["wake-cli"]
