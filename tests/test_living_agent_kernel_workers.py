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
from dharma_swarm.operator_core.living_agent_kernel_workers import KernelExternalWorkerStore


REPO_ROOT = Path(__file__).resolve().parents[1]


def _envelope(correlation_id: str, *, source: str = "manual") -> AgentRunEnvelope:
    return AgentRunEnvelope(
        agent_uid="codex_composer",
        task=KernelTask(text=f"Worker wake {correlation_id}"),
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
            verifier_commands=["pytest tests/test_living_agent_kernel_workers.py"],
            receipt_refs=[{"kind": "context_quorum", "path": "context_manifest.latest.json"}],
        ),
    )


def test_registered_fresh_worker_leases_existing_wake(tmp_path):
    store_dir = tmp_path / "kernel"
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    workers = KernelExternalWorkerStore(store_dir)
    kernel.enqueue_wake(_envelope("worker-lease"), wake_id="wake-worker-lease")
    registered = workers.register_worker(
        "worker-a",
        role="verifier",
        allowed_sources=["manual"],
        max_lease_seconds=30,
        now="2026-06-05T00:00:00Z",
    )
    heartbeat = workers.heartbeat_worker("worker-a", now="2026-06-05T00:00:01Z")

    lease = workers.lease_worker_wake(
        "worker-a",
        lease_seconds=300,
        heartbeat_max_age_seconds=10,
        now="2026-06-05T00:00:02Z",
    )
    latest = KernelRunStore(store_dir).latest_wake_records()["wake-worker-lease"]
    states = workers.worker_states(now="2026-06-05T00:00:02Z")

    assert registered.record_hash.startswith("sha256:")
    assert heartbeat.record_hash.startswith("sha256:")
    assert lease.status == "leased"
    assert lease.wake_id == "wake-worker-lease"
    assert lease.wake_record is not None
    assert latest.status == "leased"
    assert latest.lease_owner == "worker-a"
    assert latest.lease_expires_at == "2026-06-05T00:00:32Z"
    assert states[0].status == "online"


def test_worker_lease_is_denied_without_fresh_heartbeat(tmp_path):
    store_dir = tmp_path / "kernel"
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    workers = KernelExternalWorkerStore(store_dir)
    kernel.enqueue_wake(_envelope("worker-denied"), wake_id="wake-worker-denied")
    workers.register_worker("worker-no-heartbeat", now="2026-06-05T00:00:00Z")

    lease = workers.lease_worker_wake(
        "worker-no-heartbeat",
        heartbeat_max_age_seconds=10,
        now="2026-06-05T00:00:02Z",
    )
    latest = KernelRunStore(store_dir).latest_wake_records()["wake-worker-denied"]

    assert lease.status == "denied"
    assert lease.reason == "worker_heartbeat_missing_or_stale"
    assert latest.status == "queued"


def test_worker_source_filter_does_not_lease_ineligible_wake(tmp_path):
    store_dir = tmp_path / "kernel"
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    workers = KernelExternalWorkerStore(store_dir)
    kernel.enqueue_wake(_envelope("worker-source-filter", source="manual"), wake_id="wake-manual")
    workers.register_worker("worker-a2a", allowed_sources=["a2a"], now="2026-06-05T00:00:00Z")
    workers.heartbeat_worker("worker-a2a", now="2026-06-05T00:00:01Z")

    lease = workers.lease_worker_wake("worker-a2a", now="2026-06-05T00:00:02Z")
    latest = KernelRunStore(store_dir).latest_wake_records()["wake-manual"]

    assert lease.status == "idle"
    assert lease.reason == "no_eligible_queued_wake"
    assert latest.status == "queued"


def test_external_worker_completion_marks_wake_terminal_with_result_receipt(tmp_path):
    store_dir = tmp_path / "kernel"
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    workers = KernelExternalWorkerStore(store_dir)
    kernel.enqueue_wake(_envelope("worker-complete"), wake_id="wake-worker-complete")
    workers.register_worker("worker-a", now="2026-06-05T00:00:00Z")
    workers.heartbeat_worker("worker-a", now="2026-06-05T00:00:01Z")
    workers.lease_worker_wake("worker-a", now="2026-06-05T00:00:02Z")

    result = workers.complete_worker_wake(
        "worker-a",
        "wake-worker-complete",
        status="completed",
        summary="External worker finished the wake.",
        result_ref={"artifact": "worker-output.json"},
        now="2026-06-05T00:00:03Z",
    )
    latest = KernelRunStore(store_dir).latest_wake_records()["wake-worker-complete"]
    worker_ok, worker_errors = workers.verify_worker_ledgers()
    wake_ok, wake_errors = KernelRunStore(store_dir).verify_wake_ledger()

    assert result.record_hash.startswith("sha256:")
    assert latest.status == "completed"
    assert latest.result_status == "completed"
    assert latest.reason == "external_worker_terminal_result"
    assert latest.result_ref["kind"] == "external_worker_result"
    assert latest.result_ref["worker_id"] == "worker-a"
    assert latest.result_ref["worker_result_hash"] == result.record_hash
    assert latest.result_ref["payload_ref"] == {"artifact": "worker-output.json"}
    assert worker_ok, worker_errors
    assert wake_ok, wake_errors


def test_stale_worker_recovery_only_requeues_expired_stale_leases(tmp_path):
    store_dir = tmp_path / "kernel"
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    workers = KernelExternalWorkerStore(store_dir)
    kernel.enqueue_wake(_envelope("worker-stale"), wake_id="wake-worker-stale")
    kernel.enqueue_wake(_envelope("worker-fresh"), wake_id="wake-worker-fresh")
    workers.register_worker("stale-worker", now="2026-06-05T00:00:00Z")
    workers.register_worker("fresh-worker", now="2026-06-05T00:00:00Z")
    workers.heartbeat_worker("stale-worker", now="2026-06-05T00:00:00Z")
    workers.heartbeat_worker("fresh-worker", now="2026-06-05T00:00:00Z")
    workers.lease_worker_wake("stale-worker", lease_seconds=1, now="2026-06-05T00:00:00Z")
    workers.lease_worker_wake("fresh-worker", lease_seconds=1, now="2026-06-05T00:00:00Z")
    workers.heartbeat_worker("fresh-worker", now="2026-06-05T00:00:02Z")

    recovery = workers.recover_stale_worker_leases(
        stale_after_seconds=1,
        offline_after_seconds=100,
        now="2026-06-05T00:00:03Z",
    )
    latest = KernelRunStore(store_dir).latest_wake_records()

    assert recovery.stale_worker_ids == ["stale-worker"]
    assert recovery.recovered_wake_ids == ["wake-worker-stale"]
    assert latest["wake-worker-stale"].status == "queued"
    assert latest["wake-worker-stale"].reason == "leased_wake_expired_and_requeued"
    assert latest["wake-worker-fresh"].status == "leased"
    assert latest["wake-worker-fresh"].lease_owner == "fresh-worker"


def test_worker_cli_register_heartbeat_status_and_verify(tmp_path):
    script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_worker.py"
    store_dir = tmp_path / "kernel"

    registered = subprocess.run(
        [
            sys.executable,
            str(script),
            "--store-dir",
            str(store_dir),
            "register",
            "--worker-id",
            "cli-worker",
            "--role",
            "verifier",
            "--allowed-source",
            "manual",
            "--now",
            "2026-06-05T00:00:00Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--store-dir",
            str(store_dir),
            "heartbeat",
            "--worker-id",
            "cli-worker",
            "--now",
            "2026-06-05T00:00:01Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)
    status = subprocess.run(
        [
            sys.executable,
            str(script),
            "--store-dir",
            str(store_dir),
            "status",
            "--now",
            "2026-06-05T00:00:02Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)
    verified = subprocess.run(
        [
            sys.executable,
            str(script),
            "--store-dir",
            str(store_dir),
            "verify",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)

    registered_payload = json.loads(registered.stdout)
    status_payload = json.loads(status.stdout)
    verified_payload = json.loads(verified.stdout)
    assert registered_payload["record_hash"].startswith("sha256:")
    assert status_payload[0]["worker_id"] == "cli-worker"
    assert status_payload[0]["status"] == "online"
    assert verified_payload == {"errors": [], "ok": True}
