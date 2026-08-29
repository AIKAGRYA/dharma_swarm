"""Static deployment contract tests; never touch systemd."""

from __future__ import annotations

import shutil
import fcntl
import threading
import time
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from dharma_swarm.foundry.daemon import DaemonState
from scripts.foundry import foundry_daemon
from scripts.foundry import foundry_alert
from scripts.foundry import foundry_status_job
from scripts.foundry import verify_deployment
from scripts.foundry import deploy_transaction

REPO = Path(__file__).resolve().parents[1]


def test_systemd_unit_restarts_crashes_but_not_terminal_kill():
    unit = (
        REPO / "scripts/foundry/systemd/sublimation-foundry.service.in"
    ).read_text()
    assert "Restart=on-failure" in unit
    assert "RestartPreventExitStatus=42" in unit
    assert "--mode campaign" in unit
    assert "--state-root @@STATE_ROOT@@" in unit
    assert "--idle-on-stop" in unit
    assert "Type=notify" in unit
    assert "WatchdogSec=180" in unit
    assert "OnFailure=sublimation-foundry-alert@%n.service" in unit
    assert "ExecStartPre=" in unit
    assert "sublimation-foundry-verify-deployment.py verify" in unit
    assert "--expected-sha @@EXPECTED_SHA@@" in unit
    assert "PYTHONDONTWRITEBYTECODE=1" in unit
    assert "Conflicts=foundry-campaign.service foundry-daemon.service" in unit
    assert "StandardOutput=append:/var/log/sublimation-foundry/foundry.log" in unit
    assert "ProtectSystem=strict" in unit
    assert "NoNewPrivileges=true" in unit
    for directive in (
        "CapabilityBoundingSet=",
        "AmbientCapabilities=",
        "ProtectKernelLogs=true",
        "RestrictRealtime=true",
        "SystemCallArchitectures=native",
        "MemoryMax=2G",
        "TasksMax=256",
        "LimitNOFILE=4096",
        "LimitFSIZE=1G",
        "--cycle-budget 5",
    ):
        assert directive in unit


def test_install_and_status_shell_are_syntax_valid():
    for path in (
        REPO / "scripts/foundry/install_service.sh",
        REPO / "scripts/foundry/foundry-status.sh",
    ):
        proc = subprocess.run(["sh", "-n", str(path)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr


def test_installer_is_inert_and_release_identity_is_fail_closed():
    installer = (REPO / "scripts/foundry/install_service.sh").read_text()
    assert 'start_service=0' in installer
    assert '--start) start_service=1' in installer
    assert '--expected-sha)' in installer
    assert 'status --porcelain --untracked-files=normal' in installer
    assert 'https://github.com/AIKAGRYA/dharma_swarm.git' in installer
    assert 'ProviderPool(env=values).routes' in installer
    assert 'verified tariff provenance' in installer
    assert '--environment-file)' in installer
    assert 'grep -Eq' in installer
    assert 'service_user" = "root' in installer
    assert 'cp "$environment_file"' not in installer
    assert 'install "$environment_file"' not in installer
    assert '--trusted-resume-public-key)' in installer
    assert 'ssh-keygen -l -f "$trusted_resume_public_key"' in installer
    assert 'systemctl is-active --quiet "$legacy_unit"' in installer
    assert 'systemctl is-enabled "$legacy_unit"' in installer
    assert 'systemctl disable --now "$legacy_unit"' not in installer
    assert 'service_transition_attempted=1' in installer
    assert 'systemctl disable --now sublimation-foundry.service' in installer
    assert 'authoritative unresolved halt evidence' in installer
    assert 'sublimation-foundry-alert@.service.in' in installer
    assert '/etc/logrotate.d/sublimation-foundry' in installer
    assert '--binding "$status_tmp=/etc/dharma-foundry/status.env"' in installer
    assert '--binding "$cron_tmp=/etc/cron.d/sublimation-foundry-status"' in installer
    assert '--symlink "/usr/local/bin/foundry-status.sh=' in installer
    assert '/usr/local/bin/sublimation-foundry-verify-deployment.py' in installer
    assert '/usr/local/bin/sublimation-foundry-alert.py' in installer
    assert '/usr/local/bin/sublimation-foundry-status-job.py' in installer
    assert '--secret-file "$environment_file"' in installer
    assert '--runtime-executable "$python_bin"' in installer
    assert 'foundry_status_job.py' in installer
    assert 'deploy_transaction.py" apply' in installer
    assert 'deploy_transaction.py" rollback' in installer
    assert 'deploy_transaction.py" commit' in installer
    assert 'state root must be explicitly pre-created' in installer
    assert 'install -d -m 0750 -o "$service_user"' not in installer
    assert 'QUARANTINE.json' in installer
    assert 'systemd-analyze verify "$unit_tmp"' in installer


def test_onfailure_alert_and_log_rotation_are_versioned():
    alert_unit = (
        REPO / "scripts/foundry/systemd/sublimation-foundry-alert@.service.in"
    ).read_text()
    alert_script = (REPO / "scripts/foundry/foundry_alert.py").read_text()
    rotation = (
        REPO / "scripts/foundry/logrotate/sublimation-foundry"
    ).read_text()
    assert "sublimation-foundry-alert.py" in alert_unit
    assert "foundry_failure_alert.v1" in alert_script
    assert "rotate 14" in rotation and "size 25M" in rotation


def test_alert_script_appends_a_sealed_local_receipt(tmp_path):
    assert foundry_alert.main([
        "--state-root", str(tmp_path),
        "--unit", "sublimation-foundry.service",
        "--category", "watchdog",
        "--exit-code", "1",
    ]) == 0
    alerts = list((tmp_path / "alerts").glob("*.json"))
    assert len(alerts) == 1
    payload = json.loads(alerts[0].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "foundry_failure_alert.v1"
    assert payload["category"] == "watchdog"
    assert payload["digest"].startswith("sha256:")


def test_alert_script_deduplicates_health_and_fails_closed_at_bound(
    tmp_path, monkeypatch
):
    common = [
        "--state-root", str(tmp_path),
        "--unit", "sublimation-foundry-status.cron",
        "--category", "progress_health",
        "--exit-code", "1",
        "--fingerprint", "sha256:" + "a" * 64,
    ]
    assert foundry_alert.main(common) == 0
    assert foundry_alert.main(common) == 0
    assert len(list((tmp_path / "alerts").glob("*.json"))) == 1

    monkeypatch.setattr(foundry_alert, "_MAX_ALERT_FILES", 1)
    novel = [*common[:-1], "sha256:" + "b" * 64]
    assert foundry_alert.main(novel) == 3
    assert len(list((tmp_path / "alerts").glob("*.json"))) == 1


def test_alert_refuses_a_symlinked_state_root(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    link = tmp_path / "state-link"
    link.symlink_to(state, target_is_directory=True)
    with pytest.raises(SystemExit):
        foundry_alert.main([
            "--state-root", str(link),
            "--unit", "sublimation-foundry.service",
        ])


def test_status_job_alerts_only_on_nonhealthy_exit(tmp_path):
    calls = []

    def healthy(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    assert foundry_status_job.run_status_job(
        repo_root=REPO,
        state_root=tmp_path,
        python=Path("/usr/bin/python3"),
        expected_sha="a" * 40,
        runner=healthy,
    ) == 0
    assert len(calls) == 2
    assert "verify-deployment" in calls[0][2]

    responses = iter((
        SimpleNamespace(returncode=0),
        SimpleNamespace(returncode=1),
        SimpleNamespace(returncode=0),
    ))
    calls.clear()

    def degraded(command, **kwargs):
        calls.append(command)
        return next(responses)

    assert foundry_status_job.run_status_job(
        repo_root=REPO,
        state_root=tmp_path,
        python=Path("/usr/bin/python3"),
        expected_sha="a" * 40,
        runner=degraded,
    ) == 1
    assert len(calls) == 3
    assert "progress_health" in calls[2]


@pytest.mark.parametrize(
    ("failure", "category"),
    [
        (subprocess.TimeoutExpired(["status"], 120), "status_timeout"),
        (OSError("launch failed"), "status_launch_failure"),
    ],
)
def test_status_job_receipts_typed_probe_launch_failures(
    tmp_path, failure, category
):
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if len(calls) == 2:
            raise failure
        return SimpleNamespace(returncode=0)

    assert foundry_status_job.run_status_job(
        repo_root=REPO,
        state_root=tmp_path,
        python=Path("/usr/bin/python3"),
        expected_sha="a" * 40,
        runner=runner,
    ) == 4
    assert len(calls) == 3
    assert category in calls[2]


def test_status_job_receipts_checkout_or_manifest_drift(tmp_path):
    calls = []
    responses = iter((
        SimpleNamespace(returncode=1, stdout="", stderr="drift"),
        SimpleNamespace(returncode=0, stdout="", stderr=""),
    ))

    def runner(command, **kwargs):
        calls.append(command)
        return next(responses)

    assert foundry_status_job.run_status_job(
        repo_root=REPO,
        state_root=tmp_path,
        python=Path("/usr/bin/python3"),
        expected_sha="a" * 40,
        runner=runner,
    ) == 1
    assert len(calls) == 2
    assert "deployment_integrity" in calls[1]
    assert "foundry_status.py" not in " ".join(calls[0])
    source = (REPO / "scripts/foundry/foundry_status_job.py").read_text()
    assert "from dharma_swarm" not in source


def test_status_job_singleton_skips_an_overlapping_probe(tmp_path):
    calls = []
    with (tmp_path / ".status-job.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert foundry_status_job.run_status_job(
            repo_root=REPO,
            state_root=tmp_path,
            python=Path("/usr/bin/python3"),
            expected_sha="a" * 40,
            runner=lambda command, **kwargs: calls.append(command),
        ) == 0
    assert calls == []


def test_deployment_manifest_verifies_exact_installed_hashes(tmp_path, monkeypatch):
    source = tmp_path / "rendered.service"
    installed = tmp_path / "installed.service"
    source.write_text("[Service]\nType=oneshot\n", encoding="utf-8")
    installed.write_bytes(source.read_bytes())
    link = tmp_path / "status-link"
    link.symlink_to(source)
    secret = tmp_path / "provider.env"
    secret.write_text("PROVIDER_API_KEY=not-a-real-key\n", encoding="utf-8")
    secret.chmod(0o600)
    sha = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    args = SimpleNamespace(
        repo=str(REPO),
        expected_sha=sha,
        manifest=str(tmp_path / "deployment.json"),
        binding=[f"{source}={installed}"],
        symlink=[f"{link}={source}"],
        secret_file=[str(secret)],
        public_file=[str(source)],
        template=[str(REPO / "scripts/foundry/systemd/sublimation-foundry.service.in")],
    )
    inventory = [{"path": "dharma_swarm/foundry/runtime.py", "sha256": "sha256:test"}]
    monkeypatch.setattr(
        verify_deployment,
        "_verify_release_identity",
        lambda repo, expected_sha: inventory,
    )
    assert verify_deployment.record(args) == 0
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "foundry_deployment_manifest.v2"
    assert manifest["runtime_inventory"] == inventory
    assert {entry["kind"] for entry in manifest["installed"]} == {"file", "symlink"}
    secret_evidence = manifest["external_secret_dependencies"][0]
    assert secret_evidence["path"] == str(secret)
    assert secret_evidence["content_digest_recorded"] is False
    assert "sha256" not in secret_evidence
    assert "not-a-real-key" not in Path(args.manifest).read_text(encoding="utf-8")
    assert manifest["external_public_dependencies"][0]["sha256"].startswith("sha256:")
    installed.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="installed deployment hash mismatch"):
        verify_deployment.verify(args)


def _clean_release_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "release"
    (repo / "dharma_swarm/foundry").mkdir(parents=True)
    (repo / "scripts/foundry").mkdir(parents=True)
    (repo / "dharma_swarm/foundry/runtime.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    (repo / "scripts/foundry/runner.py").write_text(
        "print('runner')\n", encoding="utf-8"
    )
    (repo / "dharma_swarm/model_pool.py").write_text(
        "MODELS = ()\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Foundry Test"],
        check=True,
    )
    subprocess.run(
        [
            "git", "-C", str(repo), "remote", "add", "origin",
            "https://github.com/AIKAGRYA/dharma_swarm.git",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "release"], check=True
    )
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return repo, sha


def test_release_identity_rejects_dirty_runtime_and_untracked_bytes(tmp_path):
    repo, sha = _clean_release_repo(tmp_path)
    inventory = verify_deployment._verify_release_identity(repo, sha)
    assert {entry["path"] for entry in inventory} == {
        "dharma_swarm/foundry/runtime.py",
        "dharma_swarm/model_pool.py",
        "scripts/foundry/runner.py",
    }
    (repo / "dharma_swarm/foundry/runtime.py").write_text(
        "VALUE = 2\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="not clean"):
        verify_deployment._verify_release_identity(repo, sha)
    subprocess.run(
        ["git", "-C", str(repo), "restore", "dharma_swarm/foundry/runtime.py"],
        check=True,
    )
    (repo / "dharma_swarm/foundry/injected.py").write_text(
        "MALICIOUS = True\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="not clean"):
        verify_deployment._verify_release_identity(repo, sha)


def test_release_identity_rejects_ignored_runtime_shadow_file(tmp_path):
    repo, sha = _clean_release_repo(tmp_path)
    subprocess.run(
        ["git", "-C", str(repo), "config", "status.showUntrackedFiles", "no"],
        check=True,
    )
    (repo / ".git/info/exclude").write_text(
        "dharma_swarm/foundry/ignored.py\n", encoding="utf-8"
    )
    (repo / "dharma_swarm/foundry/ignored.py").write_text(
        "SHADOW = True\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="inventory"):
        verify_deployment._verify_release_identity(repo, sha)


def test_release_identity_rejects_ignored_package_bytecode_shadow(tmp_path):
    repo, sha = _clean_release_repo(tmp_path)
    cache = repo / "dharma_swarm/__pycache__"
    cache.mkdir()
    shadow = cache / "model_pool.cpython-312.pyc"
    (repo / ".git/info/exclude").write_text(
        "dharma_swarm/__pycache__/\n", encoding="utf-8"
    )
    shadow.write_bytes(b"ignored-bytecode-shadow")
    with pytest.raises(RuntimeError, match="inventory"):
        verify_deployment._verify_release_identity(repo, sha)


def test_release_identity_covers_repo_native_imports_outside_foundry(tmp_path):
    repo, sha = _clean_release_repo(tmp_path)
    inventory = verify_deployment._verify_release_identity(repo, sha)
    assert any(
        entry["path"] == "dharma_swarm/model_pool.py" for entry in inventory
    )
    (repo / "dharma_swarm/model_pool.py").write_text(
        "MODELS = ('drift',)\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="not clean"):
        verify_deployment._verify_release_identity(repo, sha)


def test_deployment_manifest_binds_python_executable_bytes(tmp_path, monkeypatch):
    source = tmp_path / "unit"
    installed = tmp_path / "installed-unit"
    source.write_text("unit\n", encoding="utf-8")
    installed.write_bytes(source.read_bytes())
    runtime = tmp_path / "python-runtime"
    runtime.write_bytes(b"runtime-v1\n")
    runtime.chmod(0o755)
    monkeypatch.setattr(
        verify_deployment,
        "_verify_release_identity",
        lambda repo, expected_sha: [],
    )
    args = SimpleNamespace(
        repo=str(REPO),
        expected_sha="a" * 40,
        manifest=str(tmp_path / "deployment.json"),
        binding=[f"{source}={installed}"],
        symlink=[],
        secret_file=[],
        public_file=[],
        runtime_executable=[str(runtime)],
        template=[],
    )
    verify_deployment.record(args)
    runtime.write_bytes(b"runtime-v2\n")
    runtime.chmod(0o755)
    with pytest.raises(RuntimeError, match="runtime executable provenance"):
        verify_deployment.verify(args)


def test_deployment_transaction_restores_every_prior_artifact_on_failure(
    tmp_path, monkeypatch
):
    host = tmp_path / "host"
    host.mkdir()
    monkeypatch.setattr(deploy_transaction, "_ALLOWED_DESTINATIONS", (host,))
    prior = host / "unit.service"
    prior.write_text("old-unit\n", encoding="utf-8")
    source = tmp_path / "new-unit"
    source.write_text("new-unit\n", encoding="utf-8")
    link = host / "status"
    transaction_root = host / "transactions"
    args = SimpleNamespace(
        transaction_root=str(transaction_root),
        file=[f"{source}={prior}"],
        symlink=[f"{link}={source}"],
    )
    transaction = deploy_transaction.apply_new(args)
    assert prior.read_text(encoding="utf-8") == "new-unit\n"
    assert link.is_symlink()

    manifest_source = tmp_path / "manifest"
    manifest_source.write_text("manifest-v2\n", encoding="utf-8")
    manifest_destination = host / "deployment.json"
    deploy_transaction.add_file(
        transaction, f"{manifest_source}={manifest_destination}"
    )
    assert manifest_destination.exists()

    deploy_transaction.rollback(transaction)
    assert prior.read_text(encoding="utf-8") == "old-unit\n"
    assert not link.exists() and not link.is_symlink()
    assert not manifest_destination.exists()
    journal = json.loads(
        (transaction / "transaction.json").read_text(encoding="utf-8")
    )
    assert journal["state"] == "rolled_back"
    assert journal["digest"].startswith("sha256:")


def test_partial_transaction_failure_rolls_back_prior_files(tmp_path, monkeypatch):
    host = tmp_path / "host"
    host.mkdir()
    monkeypatch.setattr(deploy_transaction, "_ALLOWED_DESTINATIONS", (host,))
    destination = host / "unit.service"
    destination.write_text("before\n", encoding="utf-8")
    source = tmp_path / "source"
    source.write_text("after\n", encoding="utf-8")
    missing = tmp_path / "missing"
    args = SimpleNamespace(
        transaction_root=str(host / "transactions"),
        file=[f"{source}={destination}", f"{missing}={host / 'cron'}"],
        symlink=[],
    )
    with pytest.raises((OSError, ValueError)):
        deploy_transaction.apply_new(args)
    assert destination.read_text(encoding="utf-8") == "before\n"


def test_deployment_transaction_global_lock_prevents_concurrent_apply_race(
    tmp_path, monkeypatch
):
    host = tmp_path / "host"
    host.mkdir()
    monkeypatch.setattr(deploy_transaction, "_ALLOWED_DESTINATIONS", (host,))
    source = tmp_path / "source"
    source.write_text("installed\n", encoding="utf-8")
    args = SimpleNamespace(
        transaction_root=str(host / "transactions"),
        file=[f"{source}={host / 'unit.service'}"],
        symlink=[],
    )
    entered = threading.Event()
    release = threading.Event()
    original = deploy_transaction._install_file
    calls = {"count": 0}

    def held_install(*install_args, **install_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            entered.set()
            assert release.wait(timeout=5)
        return original(*install_args, **install_kwargs)

    monkeypatch.setattr(deploy_transaction, "_install_file", held_install)
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(deploy_transaction.apply_new, args)
        assert entered.wait(timeout=5)
        second = pool.submit(deploy_transaction.apply_new, args)
        time.sleep(0.05)
        assert not second.done()
        release.set()
        transaction = first.result(timeout=5)
        with pytest.raises(RuntimeError, match="unresolved prior"):
            second.result(timeout=5)
    deploy_transaction.rollback(transaction)


def test_systemd_analyze_accepts_rendered_unit_when_available(tmp_path):
    analyzer = shutil.which("systemd-analyze")
    if analyzer is None:
        pytest.skip("systemd-analyze is unavailable on this host")
    unit = (
        REPO / "scripts/foundry/systemd/sublimation-foundry.service.in"
    ).read_text()
    rendered = (
        unit.replace("@@USER@@", "nobody")
        .replace("@@REPO@@", str(REPO))
        .replace("@@PYTHON@@", "/usr/bin/python3")
        .replace("@@STATE_ROOT@@", str(tmp_path / "state"))
        .replace("@@ENVIRONMENT_FILE@@", str(tmp_path / "provider.env"))
        .replace("@@EXPECTED_SHA@@", "a" * 40)
    )
    path = tmp_path / "sublimation-foundry.service"
    path.write_text(rendered, encoding="utf-8")
    proc = subprocess.run(
        [analyzer, "verify", str(path)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr


def test_cli_returns_restart_preventing_nonzero_for_terminal_kill(monkeypatch):
    monkeypatch.setattr(
        foundry_daemon,
        "run_daemon",
        lambda config: DaemonState(terminal_kill=True, stopped_reason="KILL"),
    )
    assert foundry_daemon.main(["--max-cycles", "1"]) == 42
