from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
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
from dharma_swarm.operator_core.living_agent_kernel_activation import (
    KernelActivationStore,
    KernelProcessLaunch,
    activate_supervisor_plan,
    activate_worker_process,
    build_worker_process_command,
    command_hash,
    install_supervisor_plan,
    launch_artifact_status,
    start_installed_supervisor_artifact,
)
from dharma_swarm.operator_core.living_agent_kernel_supervisor import build_supervisor_plan, write_supervisor_plan
from dharma_swarm.operator_core.living_agent_kernel_workers import KernelExternalWorkerStore


REPO_ROOT = Path(__file__).resolve().parents[1]


def _worker_envelope(correlation_id: str) -> AgentRunEnvelope:
    return AgentRunEnvelope(
        agent_uid="codex_composer",
        task=KernelTask(text=f"Activation worker wake {correlation_id}"),
        trigger=TriggerEnvelope(source="manual", correlation_id=correlation_id),
        memory=MemoryPlan(read_namespaces=["agent:codex_composer:working"]),
        tool_request=ToolRequest(
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
        ),
        proof=ProofRequest(
            verifier_commands=["pytest tests/test_living_agent_kernel_activation.py"],
            receipt_refs=[{"kind": "context_quorum", "path": "context_manifest.latest.json"}],
        ),
    )


def test_supervisor_activation_denies_unreviewed_plan_hash(tmp_path):
    plan = build_supervisor_plan(
        mode="launchd",
        repo_root=REPO_ROOT,
        store_dir=tmp_path / "kernel",
        workspace_root=tmp_path,
        label="com.dharma.activation-test",
    )
    calls: list[list[str]] = []

    receipt = activate_supervisor_plan(
        plan,
        approved_receipt_hash="sha256:not-the-plan",
        live=True,
        launcher=lambda command, _cwd: calls.append(command) or KernelProcessLaunch(status="launched", pid=1),
        now="2026-06-06T00:00:00Z",
    )

    assert receipt.status == "denied"
    assert receipt.target_kind == "supervisor_service"
    assert receipt.approved_ref["plan_receipt_hash"] == plan.receipt_hash
    assert calls == []
    ok, errors = KernelActivationStore(tmp_path / "kernel").verify_activation_ledger()
    assert ok, errors


def test_supervisor_activation_launches_only_after_matching_plan_hash(tmp_path):
    plan = build_supervisor_plan(
        mode="launchd",
        repo_root=REPO_ROOT,
        store_dir=tmp_path / "kernel",
        workspace_root=tmp_path,
        label="com.dharma.activation-test",
    )
    calls: list[tuple[list[str], Path]] = []

    def fake_launcher(command: list[str], cwd: Path) -> KernelProcessLaunch:
        calls.append((command, cwd))
        return KernelProcessLaunch(status="launched", pid=4321, message="fake launch")

    receipt = activate_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        live=True,
        launcher=fake_launcher,
        now="2026-06-06T00:00:00Z",
    )

    assert receipt.status == "activated"
    assert receipt.process_ref["pid"] == 4321
    assert receipt.command == plan.service_command
    assert calls == [(plan.service_command, REPO_ROOT.resolve())]
    ok, errors = KernelActivationStore(tmp_path / "kernel").verify_activation_ledger()
    assert ok, errors


def test_worker_process_activation_requires_reviewed_command_hash(tmp_path):
    command = build_worker_process_command(
        repo_root=REPO_ROOT,
        store_dir=tmp_path / "kernel",
        worker_id="activation-worker",
        allowed_sources=["manual"],
        heartbeat_interval_seconds=0,
        cycles=1,
        now="2026-06-06T00:00:00Z",
    )
    receipt = activate_worker_process(
        repo_root=REPO_ROOT,
        store_dir=tmp_path / "kernel",
        worker_id="activation-worker",
        allowed_sources=["manual"],
        heartbeat_interval_seconds=0,
        cycles=1,
        now="2026-06-06T00:00:00Z",
        approved_command_hash="sha256:not-the-command",
        live=True,
        launcher=lambda _command, _cwd: KernelProcessLaunch(status="launched", pid=1),
    )

    assert receipt.status == "denied"
    assert receipt.command_hash == command_hash(command, cwd=REPO_ROOT)
    assert KernelExternalWorkerStore(tmp_path / "kernel").workers() == []


def test_worker_process_activation_launches_bounded_subprocess_and_verifies_heartbeat(tmp_path):
    store_dir = tmp_path / "kernel"
    command = build_worker_process_command(
        repo_root=REPO_ROOT,
        store_dir=store_dir,
        worker_id="activation-worker",
        role="verifier",
        allowed_sources=["manual"],
        heartbeat_interval_seconds=0,
        cycles=1,
        now="2026-06-06T00:00:00Z",
    )

    def run_launcher(command: list[str], cwd: Path) -> KernelProcessLaunch:
        completed = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True, timeout=30)
        return KernelProcessLaunch(
            status="completed",
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    receipt = activate_worker_process(
        repo_root=REPO_ROOT,
        store_dir=store_dir,
        worker_id="activation-worker",
        role="verifier",
        allowed_sources=["manual"],
        heartbeat_interval_seconds=0,
        cycles=1,
        now="2026-06-06T00:00:00Z",
        approved_command_hash=command_hash(command, cwd=REPO_ROOT),
        live=True,
        require_heartbeat=True,
        launcher=run_launcher,
    )
    states = KernelExternalWorkerStore(store_dir).worker_states(now="2026-06-06T00:00:00Z")

    assert receipt.status == "activated"
    assert receipt.worker_state_ref["status"] == "online"
    assert states[0].worker_id == "activation-worker"
    assert states[0].status == "online"
    ok, errors = KernelActivationStore(store_dir).verify_activation_ledger()
    assert ok, errors


def test_worker_process_cli_and_activation_cli_review_path(tmp_path):
    worker_process_script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_worker_process.py"
    activation_script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_activation.py"
    store_dir = tmp_path / "kernel"

    completed = subprocess.run(
        [
            sys.executable,
            str(worker_process_script),
            "--store-dir",
            str(store_dir),
            "--worker-id",
            "cli-process-worker",
            "--role",
            "verifier",
            "--allowed-source",
            "manual",
            "--heartbeat-interval-seconds",
            "0",
            "--cycles",
            "1",
            "--now",
            "2026-06-06T00:00:00Z",
            "--json",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)
    process_payload = json.loads(completed.stdout)
    assert process_payload["completed_cycles"] == 1
    assert process_payload["heartbeat_refs"][0]["record_hash"].startswith("sha256:")

    planned = subprocess.run(
        [
            sys.executable,
            str(activation_script),
            "worker-plan",
            "--repo-root",
            str(REPO_ROOT),
            "--store-dir",
            str(store_dir),
            "--worker-id",
            "review-worker",
            "--heartbeat-interval-seconds",
            "0",
            "--cycles",
            "1",
            "--now",
            "2026-06-06T00:00:00Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)
    plan_payload = json.loads(planned.stdout)
    reviewed = subprocess.run(
        [
            sys.executable,
            str(activation_script),
            "worker-launch",
            "--repo-root",
            str(REPO_ROOT),
            "--store-dir",
            str(store_dir),
            "--worker-id",
            "review-worker",
            "--heartbeat-interval-seconds",
            "0",
            "--cycles",
            "1",
            "--now",
            "2026-06-06T00:00:00Z",
            "--approved-command-hash",
            plan_payload["command_hash"],
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)
    reviewed_payload = json.loads(reviewed.stdout)

    assert reviewed_payload["status"] == "reviewed"
    assert reviewed_payload["target_kind"] == "worker_process"
    assert reviewed_payload["command_hash"] == plan_payload["command_hash"]


def test_worker_process_cli_executes_leased_wake_with_kernel_result_ref(tmp_path):
    worker_process_script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_worker_process.py"
    store_dir = tmp_path / "kernel"
    kernel = LivingAgentKernel(store=KernelRunStore(store_dir), workspace_root=tmp_path)
    kernel.enqueue_wake(_worker_envelope("execute"), wake_id="wake-execute")

    completed = subprocess.run(
        [
            sys.executable,
            str(worker_process_script),
            "--store-dir",
            str(store_dir),
            "--workspace-root",
            str(tmp_path),
            "--worker-id",
            "execute-worker",
            "--role",
            "verifier",
            "--allowed-source",
            "manual",
            "--heartbeat-interval-seconds",
            "0",
            "--cycles",
            "1",
            "--now",
            "2026-06-06T00:00:00Z",
            "--execute",
            "--json",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)
    payload = json.loads(completed.stdout)
    latest = KernelRunStore(store_dir).latest_wake_records()["wake-execute"]

    assert payload["completed_cycles"] == 1
    assert payload["lease_refs"][0]["status"] == "leased"
    assert payload["execution_refs"][0]["kind"] == "kernel_run_result"
    assert payload["result_refs"][0]["kind"] == "kernel_external_worker_result"
    assert latest.status == "completed"
    assert latest.reason == "external_worker_terminal_result"
    assert latest.result_ref["kind"] == "external_worker_result"
    assert latest.result_ref["payload_ref"]["kind"] == "kernel_run_result"
    assert latest.result_ref["payload_ref"]["provider_execution"] is False
    assert latest.result_ref["payload_ref"]["proof_entry_hash"].startswith("sha256:")


def test_supervisor_activation_cli_records_reviewed_plan(tmp_path):
    activation_script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_activation.py"
    plan = write_supervisor_plan(
        build_supervisor_plan(
            mode="launchd",
            repo_root=REPO_ROOT,
            store_dir=tmp_path / "kernel",
            workspace_root=tmp_path,
            label="com.dharma.activation-cli",
        )
    )
    plan_path = Path(plan.artifact_refs["supervisor_plan"])

    completed = subprocess.run(
        [
            sys.executable,
            str(activation_script),
            "supervisor-activate",
            "--plan-json",
            str(plan_path),
            "--approved-receipt-hash",
            plan.receipt_hash,
            "--now",
            "2026-06-06T00:00:00Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)
    payload = json.loads(completed.stdout)

    assert payload["status"] == "reviewed"
    assert payload["approved_ref"]["plan_receipt_hash"] == plan.receipt_hash


def test_supervisor_install_denies_unreviewed_plan_hash_without_writing(tmp_path):
    plan = write_supervisor_plan(
        build_supervisor_plan(
            mode="launchd",
            repo_root=REPO_ROOT,
            store_dir=tmp_path / "kernel",
            workspace_root=tmp_path,
            label="com.dharma.install-denied",
        )
    )
    install_dir = tmp_path / "LaunchAgents"

    receipt = install_supervisor_plan(
        plan,
        approved_receipt_hash="sha256:not-the-plan",
        install_dir=install_dir,
        now="2026-06-06T00:00:00Z",
    )

    assert receipt.status == "denied"
    assert receipt.target_kind == "launch_artifact"
    assert not (install_dir / "com.dharma.install-denied.plist").exists()
    ok, errors = KernelActivationStore(tmp_path / "kernel").verify_activation_ledger()
    assert ok, errors


def test_supervisor_install_writes_reviewed_launchd_artifact(tmp_path):
    plan = write_supervisor_plan(
        build_supervisor_plan(
            mode="launchd",
            repo_root=REPO_ROOT,
            store_dir=tmp_path / "kernel",
            workspace_root=tmp_path,
            label="com.dharma.install-launchd",
        )
    )
    install_dir = tmp_path / "LaunchAgents"

    receipt = install_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=install_dir,
        now="2026-06-06T00:00:00Z",
    )
    installed_path = install_dir / "com.dharma.install-launchd.plist"

    assert receipt.status == "installed"
    assert receipt.install_ref["kind"] == "launchd_plist"
    assert receipt.install_ref["path"] == str(installed_path.resolve())
    assert receipt.install_ref["launch_started"] is False
    assert installed_path.read_text(encoding="utf-8") == plan.launchd_plist
    ok, errors = KernelActivationStore(tmp_path / "kernel").verify_activation_ledger()
    assert ok, errors


def test_supervisor_install_writes_reviewed_tmux_artifact(tmp_path):
    plan = write_supervisor_plan(
        build_supervisor_plan(
            mode="tmux",
            repo_root=REPO_ROOT,
            store_dir=tmp_path / "kernel",
            workspace_root=tmp_path,
            tmux_session="lak_install_tmux",
        )
    )
    install_dir = tmp_path / "tmux"

    receipt = install_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=install_dir,
        now="2026-06-06T00:00:00Z",
    )
    installed_path = install_dir / "lak_install_tmux.sh"

    assert receipt.status == "installed"
    assert receipt.install_ref["kind"] == "tmux_script"
    assert installed_path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
    assert installed_path.stat().st_mode & 0o700 == 0o700


def test_supervisor_install_cli_writes_reviewed_artifact(tmp_path):
    activation_script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_activation.py"
    plan = write_supervisor_plan(
        build_supervisor_plan(
            mode="launchd",
            repo_root=REPO_ROOT,
            store_dir=tmp_path / "kernel",
            workspace_root=tmp_path,
            label="com.dharma.install-cli",
        )
    )
    install_dir = tmp_path / "LaunchAgents"

    completed = subprocess.run(
        [
            sys.executable,
            str(activation_script),
            "supervisor-install",
            "--plan-json",
            str(Path(plan.artifact_refs["supervisor_plan"])),
            "--approved-receipt-hash",
            plan.receipt_hash,
            "--install-dir",
            str(install_dir),
            "--now",
            "2026-06-06T00:00:00Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)
    payload = json.loads(completed.stdout)

    assert payload["status"] == "installed"
    assert Path(payload["install_ref"]["path"]).exists()
    assert payload["install_ref"]["launch_started"] is False


def test_launch_artifact_status_reports_installed_and_changed(tmp_path):
    plan = write_supervisor_plan(
        build_supervisor_plan(
            mode="launchd",
            repo_root=REPO_ROOT,
            store_dir=tmp_path / "kernel",
            workspace_root=tmp_path,
            label="com.dharma.launch-status",
        )
    )
    receipt = install_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=tmp_path / "LaunchAgents",
        now="2026-06-06T00:00:00Z",
    )

    installed = launch_artifact_status(
        store_dir=tmp_path / "kernel",
        install_receipt_hash=receipt.record_hash,
        now="2026-06-06T00:00:01Z",
    )
    Path(receipt.install_ref["path"]).write_text("changed", encoding="utf-8")
    changed = launch_artifact_status(
        store_dir=tmp_path / "kernel",
        install_receipt_hash=receipt.record_hash,
        now="2026-06-06T00:00:02Z",
    )

    assert installed.status == "installed"
    assert changed.status == "changed"


def test_supervisor_start_reviews_installed_artifact_without_launching(tmp_path):
    plan = write_supervisor_plan(
        build_supervisor_plan(
            mode="launchd",
            repo_root=REPO_ROOT,
            store_dir=tmp_path / "kernel",
            workspace_root=tmp_path,
            label="com.dharma.launch-review",
        )
    )
    install = install_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=tmp_path / "LaunchAgents",
        now="2026-06-06T00:00:00Z",
    )

    receipt = start_installed_supervisor_artifact(
        store_dir=tmp_path / "kernel",
        install_receipt_hash=install.record_hash,
        live=False,
        launchd_domain="gui/501",
        now="2026-06-06T00:00:01Z",
    )

    assert receipt.status == "reviewed"
    assert receipt.target_kind == "launch_start"
    assert receipt.command == ["launchctl", "bootstrap", "gui/501", install.install_ref["path"]]
    assert receipt.process_ref == {}
    assert receipt.install_ref["launch_started"] is False


def test_supervisor_start_live_uses_injected_launcher_and_status_started(tmp_path):
    plan = write_supervisor_plan(
        build_supervisor_plan(
            mode="launchd",
            repo_root=REPO_ROOT,
            store_dir=tmp_path / "kernel",
            workspace_root=tmp_path,
            label="com.dharma.launch-live",
        )
    )
    install = install_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=tmp_path / "LaunchAgents",
        now="2026-06-06T00:00:00Z",
    )
    calls: list[tuple[list[str], Path]] = []

    def fake_launcher(command: list[str], cwd: Path) -> KernelProcessLaunch:
        calls.append((command, cwd))
        return KernelProcessLaunch(status="completed", return_code=0, stdout="started\n")

    receipt = start_installed_supervisor_artifact(
        store_dir=tmp_path / "kernel",
        install_receipt_hash=install.record_hash,
        live=True,
        launchd_domain="gui/501",
        launcher=fake_launcher,
        now="2026-06-06T00:00:01Z",
    )
    status = launch_artifact_status(
        store_dir=tmp_path / "kernel",
        install_receipt_hash=install.record_hash,
        now="2026-06-06T00:00:02Z",
    )

    assert receipt.status == "activated"
    assert receipt.install_ref["launch_started"] is True
    assert calls == [(["launchctl", "bootstrap", "gui/501", install.install_ref["path"]], (tmp_path / "kernel").resolve())]
    assert status.status == "started"
    assert status.latest_start_ref["record_hash"] == receipt.record_hash


def test_supervisor_start_denies_unknown_install_receipt(tmp_path):
    receipt = start_installed_supervisor_artifact(
        store_dir=tmp_path / "kernel",
        install_receipt_hash="sha256:not-installed",
        live=True,
        launcher=lambda _command, _cwd: KernelProcessLaunch(status="completed", return_code=0),
        now="2026-06-06T00:00:00Z",
    )

    assert receipt.status == "denied"
    assert receipt.command == []


def test_supervisor_start_and_status_cli_review_path(tmp_path):
    activation_script = REPO_ROOT / "scripts" / "runtime" / "living_agent_kernel_activation.py"
    plan = write_supervisor_plan(
        build_supervisor_plan(
            mode="launchd",
            repo_root=REPO_ROOT,
            store_dir=tmp_path / "kernel",
            workspace_root=tmp_path,
            label="com.dharma.launch-cli",
        )
    )
    install = install_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=tmp_path / "LaunchAgents",
        now="2026-06-06T00:00:00Z",
    )

    reviewed = subprocess.run(
        [
            sys.executable,
            str(activation_script),
            "supervisor-start",
            "--store-dir",
            str(tmp_path / "kernel"),
            "--install-receipt-hash",
            install.record_hash,
            "--launchd-domain",
            "gui/501",
            "--now",
            "2026-06-06T00:00:01Z",
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
            str(activation_script),
            "supervisor-launch-status",
            "--store-dir",
            str(tmp_path / "kernel"),
            "--install-receipt-hash",
            install.record_hash,
            "--now",
            "2026-06-06T00:00:02Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
timeout=30,
)
    reviewed_payload = json.loads(reviewed.stdout)
    status_payload = json.loads(status.stdout)

    assert reviewed_payload["status"] == "reviewed"
    assert reviewed_payload["command"][0:3] == ["launchctl", "bootstrap", "gui/501"]
    assert status_payload["status"] == "installed"


def test_activation_ledger_survives_concurrent_review_receipts(tmp_path):
    store_dir = tmp_path / "kernel"
    plan = build_supervisor_plan(
        mode="launchd",
        repo_root=REPO_ROOT,
        store_dir=store_dir,
        workspace_root=tmp_path,
        label="com.dharma.activation-concurrent",
    )
    command = build_worker_process_command(
        repo_root=REPO_ROOT,
        store_dir=store_dir,
        worker_id="concurrent-worker",
        heartbeat_interval_seconds=0,
        cycles=1,
        now="2026-06-06T00:00:00Z",
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                activate_supervisor_plan,
                plan,
                approved_receipt_hash=plan.receipt_hash,
                now="2026-06-06T00:00:00Z",
            ),
            pool.submit(
                activate_worker_process,
                repo_root=REPO_ROOT,
                store_dir=store_dir,
                worker_id="concurrent-worker",
                heartbeat_interval_seconds=0,
                cycles=1,
                now="2026-06-06T00:00:00Z",
                approved_command_hash=command_hash(command, cwd=REPO_ROOT),
            ),
        ]
        receipts = [future.result() for future in futures]

    assert {receipt.target_kind for receipt in receipts} == {"supervisor_service", "worker_process"}
    ok, errors = KernelActivationStore(store_dir).verify_activation_ledger()
    assert ok, errors
