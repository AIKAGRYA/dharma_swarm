from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from dharma_swarm.holon_service_liveness import record_service_heartbeat
from dharma_swarm.holon_l4_activation import (
    HolonL4ActivationStore,
    HolonL4ProcessLaunch,
    activate_holon_l4_supervisor_plan,
    activation_dir_for_plan,
    holon_l4_launch_artifact_status,
    install_holon_l4_supervisor_plan,
    start_installed_holon_l4_supervisor_artifact,
)
from dharma_swarm.holon_l4_supervisor import (
    build_holon_l4_supervisor_plan,
    write_holon_l4_supervisor_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _launchd_plan(tmp_path: Path):
    return write_holon_l4_supervisor_plan(
        build_holon_l4_supervisor_plan(
            name="codex_composer",
            mode="launchd",
            repo_root=REPO_ROOT,
            agents_root=tmp_path / "agents",
            output_dir=tmp_path / "supervisor",
            label="com.dharma.test-l4-activation",
            python_executable=sys.executable,
        )
    )


def _tmux_plan(tmp_path: Path):
    return write_holon_l4_supervisor_plan(
        build_holon_l4_supervisor_plan(
            name="codex_composer",
            mode="tmux",
            repo_root=REPO_ROOT,
            agents_root=tmp_path / "agents",
            output_dir=tmp_path / "supervisor-tmux",
            tmux_session="holon_l4_activation_test",
            python_executable=sys.executable,
        )
    )


def _make_agent(root: Path, name: str = "codex_composer") -> Path:
    agent_dir = root / name
    (agent_dir / "prompt_variants").mkdir(parents=True)
    (agent_dir / "identity.json").write_text(
        json.dumps(
            {
                "model": "identity-model",
                "provider": "ollama",
                "system_prompt": "fallback prompt",
            }
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt_variants" / "active.txt").write_text(
        "I am codex_composer.",
        encoding="utf-8",
    )
    return root


def test_activation_denies_unreviewed_plan_hash_without_launching(tmp_path: Path) -> None:
    plan = _launchd_plan(tmp_path)
    calls: list[list[str]] = []

    receipt = activate_holon_l4_supervisor_plan(
        plan,
        approved_receipt_hash="sha256:not-the-plan",
        live=True,
        launcher=lambda command, _cwd: calls.append(command) or HolonL4ProcessLaunch(status="launched", pid=1),
        now="2026-06-18T00:00:00Z",
    )

    assert receipt.status == "denied"
    assert receipt.target_kind == "supervisor_service"
    assert receipt.approved_ref["plan_receipt_hash"] == plan.receipt_hash
    assert calls == []
    ok, errors = HolonL4ActivationStore(activation_dir_for_plan(plan)).verify_activation_ledger()
    assert ok, errors


def test_install_writes_reviewed_launchd_artifact_without_start(tmp_path: Path) -> None:
    plan = _launchd_plan(tmp_path)
    install_dir = tmp_path / "LaunchAgents"

    receipt = install_holon_l4_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=install_dir,
        now="2026-06-18T00:00:00Z",
    )
    installed_path = install_dir / "com.dharma.test-l4-activation.plist"

    assert receipt.status == "installed"
    assert receipt.install_ref["kind"] == "launchd_plist"
    assert receipt.install_ref["path"] == str(installed_path.resolve())
    assert receipt.install_ref["launch_started"] is False
    assert installed_path.read_text(encoding="utf-8") == plan.launchd_plist
    ok, errors = HolonL4ActivationStore(activation_dir_for_plan(plan)).verify_activation_ledger()
    assert ok, errors


def test_install_writes_reviewed_tmux_artifact_without_start(tmp_path: Path) -> None:
    plan = _tmux_plan(tmp_path)
    install_dir = tmp_path / "tmux"

    receipt = install_holon_l4_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=install_dir,
        now="2026-06-18T00:00:00Z",
    )
    installed_path = install_dir / "holon_l4_activation_test.sh"

    assert receipt.status == "installed"
    assert receipt.install_ref["kind"] == "tmux_script"
    assert receipt.install_ref["launch_started"] is False
    assert installed_path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
    assert installed_path.stat().st_mode & 0o700 == 0o700


def test_launch_artifact_status_tracks_changed_and_started(tmp_path: Path) -> None:
    plan = _launchd_plan(tmp_path)
    install = install_holon_l4_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=tmp_path / "LaunchAgents",
        now="2026-06-18T00:00:00Z",
    )
    activation_dir = activation_dir_for_plan(plan)

    installed = holon_l4_launch_artifact_status(
        activation_dir=activation_dir,
        install_receipt_hash=install.record_hash,
        now="2026-06-18T00:00:01Z",
    )
    assert installed.status == "installed"

    calls: list[tuple[list[str], Path]] = []

    def fake_launcher(command: list[str], cwd: Path) -> HolonL4ProcessLaunch:
        calls.append((command, cwd))
        return HolonL4ProcessLaunch(status="completed", return_code=0, stdout="started\n")

    start = start_installed_holon_l4_supervisor_artifact(
        activation_dir=activation_dir,
        install_receipt_hash=install.record_hash,
        live=True,
        launchd_domain="gui/501",
        launcher=fake_launcher,
        now="2026-06-18T00:00:02Z",
    )
    started = holon_l4_launch_artifact_status(
        activation_dir=activation_dir,
        install_receipt_hash=install.record_hash,
        now="2026-06-18T00:00:03Z",
    )
    Path(install.install_ref["path"]).write_text("changed", encoding="utf-8")
    changed = holon_l4_launch_artifact_status(
        activation_dir=activation_dir,
        install_receipt_hash=install.record_hash,
        now="2026-06-18T00:00:04Z",
    )

    assert start.status == "activated"
    assert start.install_ref["launch_started"] is True
    assert calls == [(["launchctl", "bootstrap", "gui/501", install.install_ref["path"]], activation_dir)]
    assert started.status == "started"
    assert started.latest_start_ref["record_hash"] == start.record_hash
    assert changed.status == "changed"


def test_start_reviews_installed_artifact_without_launching(tmp_path: Path) -> None:
    plan = _launchd_plan(tmp_path)
    install = install_holon_l4_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=tmp_path / "LaunchAgents",
        now="2026-06-18T00:00:00Z",
    )

    receipt = start_installed_holon_l4_supervisor_artifact(
        activation_dir=activation_dir_for_plan(plan),
        install_receipt_hash=install.record_hash,
        live=False,
        launchd_domain="gui/501",
        now="2026-06-18T00:00:01Z",
    )

    assert receipt.status == "reviewed"
    assert receipt.target_kind == "launch_start"
    assert receipt.command == ["launchctl", "bootstrap", "gui/501", install.install_ref["path"]]
    assert receipt.process_ref == {}
    assert receipt.install_ref["launch_started"] is False


def test_holon_l4_activation_cli_install_start_status_review_path(tmp_path: Path) -> None:
    activation_script = REPO_ROOT / "scripts" / "holon_l4_activation.py"
    plan = _launchd_plan(tmp_path)
    install_dir = tmp_path / "LaunchAgents"

    installed = subprocess.run(
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
            "2026-06-18T00:00:00Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    install_payload = json.loads(installed.stdout)
    reviewed = subprocess.run(
        [
            sys.executable,
            str(activation_script),
            "supervisor-start",
            "--activation-dir",
            str(activation_dir_for_plan(plan)),
            "--install-receipt-hash",
            install_payload["record_hash"],
            "--launchd-domain",
            "gui/501",
            "--now",
            "2026-06-18T00:00:01Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        [
            sys.executable,
            str(activation_script),
            "supervisor-launch-status",
            "--activation-dir",
            str(activation_dir_for_plan(plan)),
            "--install-receipt-hash",
            install_payload["record_hash"],
            "--now",
            "2026-06-18T00:00:02Z",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    reviewed_payload = json.loads(reviewed.stdout)
    status_payload = json.loads(status.stdout)
    assert install_payload["status"] == "installed"
    assert Path(install_payload["install_ref"]["path"]).exists()
    assert reviewed_payload["status"] == "reviewed"
    assert reviewed_payload["install_ref"]["launch_started"] is False
    assert status_payload["status"] == "installed"


def test_direct_activation_can_require_service_heartbeat_after_bounded_run(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path / "agents")
    plan = write_holon_l4_supervisor_plan(
        build_holon_l4_supervisor_plan(
            name="codex_composer",
            mode="launchd",
            repo_root=REPO_ROOT,
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "reports" / "l4_memory_write_receipts.jsonl",
            output_dir=tmp_path / "supervisor",
            label="com.dharma.test-l4-direct-activation",
            session_id="l4-direct-activation-test",
            forever=False,
            cycles=1,
            interval_seconds=0,
            lock_path=tmp_path / "service.lock",
            transport_heartbeat_path=tmp_path / "missing_transport.json",
            python_executable=sys.executable,
        )
    )

    def run_launcher(command: list[str], cwd: Path) -> HolonL4ProcessLaunch:
        completed = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
        return HolonL4ProcessLaunch(
            status="completed" if completed.returncode == 0 else "failed",
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    receipt = activate_holon_l4_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        live=True,
        require_service_heartbeat=True,
        service_heartbeat_fresh_after_seconds=3600,
        launcher=run_launcher,
        now="2026-06-18T00:00:00Z",
    )

    assert receipt.status == "activated"
    assert receipt.process_ref["return_code"] == 0
    assert receipt.service_state_ref["service_alive"] is True
    assert receipt.service_state_ref["latest_service_id"] == "holon-l4-service"
    assert receipt.service_state_ref["latest_session_id"] == "l4-direct-activation-test"
    assert receipt.service_state_ref["status"] == "idle"
    ok, errors = HolonL4ActivationStore(activation_dir_for_plan(plan)).verify_activation_ledger()
    assert ok, errors


def test_installed_tmux_launch_artifact_can_require_service_heartbeat_after_bounded_start(
    tmp_path: Path,
) -> None:
    agents_root = _make_agent(tmp_path / "agents")
    plan = write_holon_l4_supervisor_plan(
        build_holon_l4_supervisor_plan(
            name="codex_composer",
            mode="tmux",
            repo_root=REPO_ROOT,
            agents_root=agents_root,
            memory_receipt_path=tmp_path / "reports" / "l4_memory_write_receipts.jsonl",
            output_dir=tmp_path / "supervisor-tmux",
            tmux_session="holon_l4_launch_artifact_test",
            session_id="l4-launch-artifact-test",
            forever=False,
            cycles=1,
            interval_seconds=0,
            lock_path=tmp_path / "service.lock",
            transport_heartbeat_path=tmp_path / "missing_transport.json",
            python_executable=sys.executable,
        )
    )
    install = install_holon_l4_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=tmp_path / "tmux-bin",
        now="2026-06-18T00:00:00Z",
    )
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_tmux = fake_bin / "tmux"
    fake_tmux.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nlast=\"${@: -1}\"\nbash -lc \"$last\"\n",
        encoding="utf-8",
    )
    fake_tmux.chmod(0o700)

    def run_with_fake_tmux(command: list[str], cwd: Path) -> HolonL4ProcessLaunch:
        env = os.environ.copy()
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        return HolonL4ProcessLaunch(
            status="completed" if completed.returncode == 0 else "failed",
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    start = start_installed_holon_l4_supervisor_artifact(
        activation_dir=activation_dir_for_plan(plan),
        install_receipt_hash=install.record_hash,
        live=True,
        require_service_heartbeat=True,
        service_heartbeat_fresh_after_seconds=3600,
        launcher=run_with_fake_tmux,
        now="2026-06-18T00:00:01Z",
    )
    status = holon_l4_launch_artifact_status(
        activation_dir=activation_dir_for_plan(plan),
        install_receipt_hash=install.record_hash,
        now="2026-06-18T00:00:02Z",
    )

    assert start.status == "activated"
    assert start.target_kind == "launch_start"
    assert start.install_ref["kind"] == "tmux_script"
    assert start.install_ref["launch_started"] is True
    assert start.process_ref["return_code"] == 0
    assert start.service_state_ref["service_alive"] is True
    assert start.service_state_ref["latest_service_id"] == "holon-l4-service"
    assert start.service_state_ref["latest_session_id"] == "l4-launch-artifact-test"
    assert start.service_state_ref["status"] == "idle"
    assert status.status == "started"
    assert status.latest_start_ref["record_hash"] == start.record_hash
    assert status.latest_start_ref["service_state_ref"]["service_alive"] is True
    ok, errors = HolonL4ActivationStore(activation_dir_for_plan(plan)).verify_activation_ledger()
    assert ok, errors


def test_launch_start_waits_for_delayed_service_heartbeat(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path / "agents")
    plan = write_holon_l4_supervisor_plan(
        build_holon_l4_supervisor_plan(
            name="codex_composer",
            mode="tmux",
            repo_root=REPO_ROOT,
            agents_root=agents_root,
            output_dir=tmp_path / "supervisor-tmux",
            tmux_session="holon_l4_delayed_heartbeat_test",
            python_executable=sys.executable,
        )
    )
    install = install_holon_l4_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=tmp_path / "tmux-bin",
        now="2026-06-18T00:00:00Z",
    )

    def launcher(_command: list[str], _cwd: Path) -> HolonL4ProcessLaunch:
        def delayed_write() -> None:
            time.sleep(0.15)
            record_service_heartbeat(
                "codex_composer",
                agents_root=agents_root,
                session_id="l4-delayed-heartbeat-test",
                service_id="holon-l4-service",
                status="idle",
                runtime_ref={"kind": "delayed_test"},
                proof_ref={"kind": "delayed_test"},
                claim_scope={"service_alive": True},
            )

        thread = threading.Thread(target=delayed_write)
        thread.start()
        return HolonL4ProcessLaunch(status="completed", return_code=0, stdout="started\n")

    start = start_installed_holon_l4_supervisor_artifact(
        activation_dir=activation_dir_for_plan(plan),
        install_receipt_hash=install.record_hash,
        live=True,
        require_service_heartbeat=True,
        service_heartbeat_fresh_after_seconds=3600,
        service_heartbeat_timeout_seconds=2.0,
        service_heartbeat_poll_seconds=0.05,
        launcher=launcher,
        now="2026-06-18T00:00:01Z",
    )

    assert start.status == "activated"
    assert start.service_state_ref["service_alive"] is True
    assert start.service_state_ref["latest_session_id"] == "l4-delayed-heartbeat-test"
    ok, errors = HolonL4ActivationStore(activation_dir_for_plan(plan)).verify_activation_ledger()
    assert ok, errors


def test_launch_start_rejects_stale_preexisting_service_heartbeat(tmp_path: Path) -> None:
    agents_root = _make_agent(tmp_path / "agents")
    record_service_heartbeat(
        "codex_composer",
        agents_root=agents_root,
        session_id="old-session",
        service_id="holon-l4-service",
        status="idle",
        runtime_ref={"kind": "old"},
        proof_ref={"kind": "old"},
        claim_scope={"service_alive": True},
    )
    plan = write_holon_l4_supervisor_plan(
        build_holon_l4_supervisor_plan(
            name="codex_composer",
            mode="tmux",
            repo_root=REPO_ROOT,
            agents_root=agents_root,
            output_dir=tmp_path / "supervisor-tmux",
            tmux_session="holon_l4_stale_heartbeat_test",
            session_id="new-session",
            python_executable=sys.executable,
        )
    )
    install = install_holon_l4_supervisor_plan(
        plan,
        approved_receipt_hash=plan.receipt_hash,
        install_dir=tmp_path / "tmux-bin",
        now="2026-06-18T00:00:00Z",
    )

    start = start_installed_holon_l4_supervisor_artifact(
        activation_dir=activation_dir_for_plan(plan),
        install_receipt_hash=install.record_hash,
        live=True,
        require_service_heartbeat=True,
        service_heartbeat_fresh_after_seconds=3600,
        service_heartbeat_timeout_seconds=0.1,
        service_heartbeat_poll_seconds=0.05,
        launcher=lambda _command, _cwd: HolonL4ProcessLaunch(status="completed", return_code=0),
        now="2026-06-18T00:00:01Z",
    )

    assert start.status == "failed"
    assert start.process_ref["return_code"] == 0
    assert start.service_state_ref["latest_session_id"] == "old-session"
    assert start.service_state_ref["required_session_id"] == "new-session"
    assert start.service_state_ref["required_session_id_matched"] is False
    assert start.service_state_ref["required_new_record_observed"] is False
    ok, errors = HolonL4ActivationStore(activation_dir_for_plan(plan)).verify_activation_ledger()
    assert ok, errors
