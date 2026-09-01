"""Safety and exactness tests for the RSI Lab release synchronizer."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from dharma_swarm.forge_lab import sync_control as sync
from dharma_swarm.forge_lab import sync_node
from dharma_swarm.forge_lab import sync_orchestrator as orchestrator


@pytest.fixture(autouse=True)
def _isolate_host_campaign_process_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep temp-root activation tests independent of host tmux/process state."""

    real_run = subprocess.run

    def isolated_run(
        command: list[str], *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["tmux", "list-sessions"]:
            return subprocess.CompletedProcess(command, 1, "", "")
        if command[:3] == ["ps", "-eo", "pid=,args="]:
            return subprocess.CompletedProcess(command, 0, "", "")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", isolated_run)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def _make_release(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    root = tmp_path / "lab"
    repo = root / "release-source"
    repo.mkdir(parents=True)
    for relative in sync.CRITICAL_FILES:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "dharma_swarm/forge_lab/version.py":
            content = 'PACKAGE_VERSION = "0.1.0-test"\n'
        elif relative.startswith("scripts/"):
            content = "#!/usr/bin/env bash\nexit 0\n"
        else:
            content = f"fixture:{relative}\n"
        path.write_text(content, encoding="utf-8")
    _git(repo, "init")
    _git(repo, "add", ".")
    _git(
        repo,
        "-c",
        "user.name=RSI Sync Test",
        "-c",
        "user.email=rsi-sync@example.invalid",
        "commit",
        "-m",
        "fixture",
    )

    identity = sync._checkout_identity(repo)
    plan: dict[str, object] = {
        "schema": sync.PLAN_SCHEMA,
        "created_at": "2026-07-15T00:00:00Z",
        "canonical_repository": sync.CANONICAL_REPOSITORY,
        "canonical_ref": sync.CANONICAL_REF,
        "commit": identity["commit"],
        "tree": identity["tree"],
        "uv_lock_sha256": identity["uv_lock_sha256"],
        "critical_files": identity["critical_files"],
        "forge_package_version": identity["forge_package_version"],
        "targets": {"mac": str(root), "meghadharma": "/root/rsi-lab"},
        "exactness_contract": {},
        "verification_tests": list(sync.VERIFICATION_TESTS),
    }
    plan["plan_digest"] = sync.plan_digest(plan)

    release = root / "releases" / str(plan["commit"])
    release.parent.mkdir(parents=True)
    os.replace(repo, release / "repo") if release.exists() else None
    if not release.exists():
        release.mkdir()
        os.replace(repo, release / "repo")

    state = root / "state"
    state.mkdir(parents=True)
    (state / "do-not-copy.txt").write_text("host-owned", encoding="utf-8")
    runtime = root / "runtime"
    runtime.mkdir()
    fixture_venv = root / "fixture-venv"
    (fixture_venv / "bin").mkdir(parents=True)
    os.symlink(str(Path(sys.executable).resolve()), fixture_venv / "bin" / "python")
    os.symlink(str(fixture_venv), runtime / ".venv")
    (runtime / "pydeps").mkdir()
    sync._ensure_release_links(release, root)
    sync._atomic_json(
        release / "RELEASE_MANIFEST.json",
        {
            "schema": sync.RELEASE_SCHEMA,
            "plan_digest": plan["plan_digest"],
            "plan": plan,
        },
    )
    return root, release, plan


def test_plan_digest_detects_any_manifest_tampering(tmp_path: Path) -> None:
    _, _, plan = _make_release(tmp_path)
    sync.validate_plan(plan)
    tampered = json.loads(json.dumps(plan))
    tampered["forge_package_version"] = "9.9.9"

    with pytest.raises(sync.SyncError, match="digest") as error:
        sync.validate_plan(tampered)

    assert error.value.code == "PLAN_TAMPERED"


def test_activation_is_atomic_idempotent_and_preserves_host_state(
    tmp_path: Path,
) -> None:
    root, release, plan = _make_release(tmp_path)
    (root / "bin").mkdir()
    (root / "bin" / "rsi-env").write_text("legacy env\n", encoding="utf-8")

    first = sync.activate_release(
        plan,
        root,
        node="meghadharma",
        request_id="test-first-activation",
        expected_current=None,
        require_canonical_head=False,
    )
    assert (root / "current").is_symlink()
    assert (root / "current").resolve() == release
    assert (root / "state" / "do-not-copy.txt").read_text() == "host-owned"
    assert Path(first["receipt"]).is_file()
    assert (root / "bin" / "rsi").resolve() == (
        release / "repo" / "scripts" / "forge_lab" / "rsi"
    )
    assert (root / "bin" / "RSILAB").resolve() == (
        release / "repo" / "scripts" / "forge_lab" / "rsi"
    )
    assert (root / "bin" / "rsi-env").read_text(encoding="utf-8") == "legacy env\n"
    assert not (root / "bin" / "rsi-env").is_symlink()
    assert (root / "bin" / "rsi-lab-env").is_symlink()
    assert (root / "bin" / "rsi-provider-refresh").resolve() == (
        release / "repo" / "scripts" / "forge_lab" / "rsi-provider-refresh"
    )
    assert (root / "bin" / "rsi-provider-refresh-install").resolve() == (
        release
        / "repo"
        / "scripts"
        / "forge_lab"
        / "rsi-provider-refresh-install"
    )
    assert (root / "bin" / "rsi-unattended-explore").resolve() == (
        release
        / "repo"
        / "scripts"
        / "forge_lab"
        / "rsi-unattended-explore"
    )

    second = sync.activate_release(
        plan,
        root,
        node="meghadharma",
        request_id="test-idempotent-activation",
        expected_current=str(plan["commit"]),
        require_canonical_head=False,
    )
    assert second["previous_commit"] == plan["commit"]
    assert (root / "state" / "do-not-copy.txt").read_text() == "host-owned"


def test_dirty_or_changed_release_is_never_activated(tmp_path: Path) -> None:
    root, release, plan = _make_release(tmp_path)
    version = release / "repo" / "dharma_swarm" / "forge_lab" / "version.py"
    version.write_text('PACKAGE_VERSION = "changed"\n', encoding="utf-8")

    with pytest.raises(sync.SyncError) as error:
        sync.activate_release(
            plan,
            root,
            node="test",
            request_id="test-dirty-refusal",
            expected_current=None,
            require_canonical_head=False,
        )

    assert error.value.code == "RELEASE_IDENTITY_MISMATCH"
    assert not (root / "current").exists()


def test_campaign_block_refuses_switch_without_touching_current(tmp_path: Path) -> None:
    root, _, plan = _make_release(tmp_path)
    (root / "DEPLOYMENT_BLOCK").write_text("campaign active\n", encoding="utf-8")

    with pytest.raises(sync.SyncError) as error:
        sync.activate_release(
            plan,
            root,
            node="test",
            request_id="test-campaign-refusal",
            expected_current=None,
            require_canonical_head=False,
        )

    assert error.value.code == "ACTIVE_CAMPAIGN"
    assert not (root / "current").exists()


@pytest.mark.parametrize(
    "argv",
    [
        "101 python -m dharma_swarm.forge_lab.experiment --generations 1",
        "102 python -m dharma_swarm.forge_lab.cli run --mode shadow",
        "103 python -m dharma_swarm.forge_lab newrun --preset fast --execute",
        "104 python -m dharma_swarm.forge_lab.rsi_cli newrun --execute --preset fast",
        "105 python -m dharma_swarm.forge_lab campaign run --manifest sha256:abc",
        "106 /root/rsi-lab/bin/rsi campaign pause campaign-1",
        "107 /root/rsi-lab/bin/RSILAB campaign stop campaign-1",
        "108 /root/rsi-lab/bin/RSILAB - NEWRUN --preset fast --execute",
        "109 python /root/rsi-lab/current/repo/dharma_swarm/forge_lab/experiment.py",
        "110 rsi-manager-overnight",
    ],
)
def test_campaign_guard_recognizes_every_canonical_foreground_argv(argv: str) -> None:
    assert sync._foreground_campaign_argv(argv) is True


@pytest.mark.parametrize(
    "argv",
    [
        "201 rsi campaign list",
        "202 rsi campaign status campaign-1",
        "203 rsi doctor",
        "204 rsi provider selftest --profile staged --live",
        "205 python -m dharma_swarm.forge_lab newrun --preset fast",
    ],
)
def test_campaign_guard_allows_read_only_foreground_argv(argv: str) -> None:
    assert sync._foreground_campaign_argv(argv) is False


def test_campaign_guard_treats_idle_operator_tmux_as_observation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    real_run = subprocess.run

    def operator_console_only(
        command: list[str], *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["tmux", "list-sessions"]:
            return subprocess.CompletedProcess(
                command,
                0,
                "RSI-LAB\nCODEX_MANAGED_RSI_LAB\n",
                "",
            )
        if command[:3] == ["ps", "-eo", "pid=,args="]:
            return subprocess.CompletedProcess(command, 0, "", "")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", operator_console_only)

    guard = sync._campaign_guard(tmp_path)

    assert guard["ok"] is True
    assert guard["reasons"] == []
    assert guard["evidence"]["tmux_sessions"] == [
        "RSI-LAB",
        "CODEX_MANAGED_RSI_LAB",
    ]
    assert guard["evidence"]["tmux_sessions_are_observational_only"] is True


def test_campaign_guard_still_blocks_a_real_runner_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    real_run = subprocess.run

    def active_runner(
        command: list[str], *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["tmux", "list-sessions"]:
            return subprocess.CompletedProcess(command, 0, "RSI-LAB\n", "")
        if command[:3] == ["ps", "-eo", "pid=,args="]:
            return subprocess.CompletedProcess(
                command,
                0,
                "123 python -m dharma_swarm.forge_lab campaign run --manifest x\n",
                "",
            )
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", active_runner)

    guard = sync._campaign_guard(tmp_path)

    assert guard["ok"] is False
    assert guard["reasons"] == ["active RSI process count: 1"]
    assert guard["evidence"]["active_process_count"] == 1


def test_exact_release_identity_covers_foundation_execution_semantics() -> None:
    required = {
        "dharma_swarm/forge_lab/agent_bundle.py",
        "dharma_swarm/forge_lab/genome_spec.py",
        "dharma_swarm/forge_lab/unattended_accounting.py",
        "dharma_swarm/forge_v1/forge_v2/arms.py",
    }

    assert required <= set(sync.CRITICAL_FILES)


def test_nonterminal_active_manifest_blocks_release_switch(tmp_path: Path) -> None:
    root, _, plan = _make_release(tmp_path)
    active = root / "state" / ".dharma" / "forge_lab" / "active_campaign.json"
    active.parent.mkdir(parents=True)
    active.write_text(
        json.dumps({"campaign_id": "campaign-1", "state": "PREFLIGHTING"}),
        encoding="utf-8",
    )

    with pytest.raises(sync.SyncError) as error:
        sync.activate_release(
            plan,
            root,
            node="test",
            request_id="test-active-manifest",
            expected_current=None,
            require_canonical_head=False,
        )

    assert error.value.code == "ACTIVE_CAMPAIGN"
    assert not (root / "current").exists()


def test_wrapper_failure_rolls_back_initial_current_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, plan = _make_release(tmp_path)

    def fail_wrappers(*args: object, **kwargs: object) -> dict[str, str]:
        raise sync.SyncError("WRAPPER_TEST_FAILURE", "simulated wrapper failure")

    monkeypatch.setattr(sync, "_install_wrappers", fail_wrappers)
    with pytest.raises(sync.SyncError) as error:
        sync.activate_release(
            plan,
            root,
            node="test",
            request_id="test-wrapper-rollback",
            expected_current=None,
            require_canonical_head=False,
        )

    assert error.value.code == "WRAPPER_TEST_FAILURE"
    assert not (root / "current").exists()


def test_node_status_rejects_tampered_release_manifest(tmp_path: Path) -> None:
    root, release, plan = _make_release(tmp_path)
    sync.activate_release(
        plan,
        root,
        node="test",
        request_id="test-manifest-status",
        expected_current=None,
        require_canonical_head=False,
    )
    manifest_path = release / "RELEASE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["plan"]["forge_package_version"] = "tampered"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    status = sync.node_status(root, node="test")

    assert status["ready"] is False
    assert status["release_manifest_digest"] is None
    assert any("manifest" in message for message in status["errors"])


def test_status_proves_github_mac_and_remote_identity_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _, plan = _make_release(tmp_path)
    sync.activate_release(
        plan,
        root,
        node="test",
        request_id="test-status-activation",
        expected_current=None,
        require_canonical_head=False,
    )
    monkeypatch.setattr(sync, "_remote_head", lambda: plan["commit"])
    monkeypatch.setattr(
        orchestrator,
        "_ssh_node",
        lambda *args, **kwargs: sync.node_status(root, node="meghadharma"),
    )

    status = orchestrator.sync_status(root=root)

    assert status["in_sync"] is True
    assert status["failures"] == []
    assert status["mac"]["identity"]["commit"] == plan["commit"]
    assert status["meghadharma"]["identity"]["commit"] == plan["commit"]


def test_strict_ssh_and_sync_exclusion_contract_are_load_bearing() -> None:
    options = " ".join(sync.SSH_OPTIONS)
    assert "BatchMode=yes" in options
    assert "StrictHostKeyChecking=yes" in options
    assert "IdentitiesOnly=yes" in options
    assert "PasswordAuthentication=no" in options
    assert "KbdInteractiveAuthentication=no" in options
    assert "ForwardAgent=no" in options
    assert not any(
        item in sync.CRITICAL_FILES for item in ("state", "secrets", "*.db", "*.db-wal")
    )


def test_remote_node_bundle_is_self_contained(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update(
        {
            "RSI_SYNC_NODE_ACTION": "status",
            "RSI_SYNC_ROOT": str(tmp_path / "remote-lab"),
            "RSI_SYNC_NODE": "test-remote",
        }
    )
    result = subprocess.run(
        [sys.executable, "-I", "-"],
        input=orchestrator._node_source(),
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["result"]["node"] == "test-remote"
    assert envelope["result"]["ready"] is False


def test_shallow_cache_materializes_the_release_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, source_release, plan = _make_release(tmp_path / "source")
    source_repo = source_release / "repo"
    _git(source_repo, "branch", "rsi-lab/canonical", str(plan["commit"]))
    target_root = tmp_path / "target"
    repository = str(source_repo)
    monkeypatch.setattr(sync, "CANONICAL_REPOSITORY", repository)
    monkeypatch.setattr(sync, "_remote_head", lambda: plan["commit"])
    monkeypatch.setattr(
        sync,
        "_run_offline_verification",
        lambda *args, **kwargs: {"network_or_provider_calls": False},
    )
    plan["canonical_repository"] = repository
    plan["plan_digest"] = sync.plan_digest(plan)

    result = sync.prepare_release(
        plan,
        target_root,
        node="test",
        local_venv=source_release.parents[1] / "fixture-venv",
    )

    checkout = Path(result["release"]) / "repo"
    assert _git(checkout, "rev-parse", "HEAD") == plan["commit"]
    assert _git(checkout, "rev-parse", "HEAD^{tree}") == plan["tree"]
    assert sync._checkout_identity(checkout)["repo_clean"] is True


def test_arbitrary_remote_and_non_atomic_current_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(sync.SyncError) as remote_error:
        sync._validate_remote("surprise-host")
    assert remote_error.value.code == "REMOTE_NOT_ALLOWED"

    current = tmp_path / "current"
    current.mkdir()
    with pytest.raises(sync.SyncError) as current_error:
        sync._atomic_symlink(tmp_path / "release", current)
    assert current_error.value.code == "CURRENT_NOT_ATOMIC"


def test_swebench_runtime_import_root_is_unique_and_venv_owned(
    tmp_path: Path,
) -> None:
    root = tmp_path / "lab"
    python_abi = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = (
        root / "runtime" / "swebench-venv" / "lib" / python_abi / "site-packages"
    )
    for package in ("swebench", "docker", "datasets"):
        (site_packages / package).mkdir(parents=True, exist_ok=True)

    runtime_python = root / "runtime" / "swebench-venv" / "bin" / "python"
    runtime_python.parent.mkdir(parents=True)
    os.symlink(Path(sys.executable).resolve(), runtime_python)
    assert sync_node._swebench_import_root(
        root,
        release_python=Path(sys.executable),
    ) == site_packages.resolve()

    other_abi = "python9.99"
    second = root / "runtime" / "swebench-venv" / "lib" / other_abi / "site-packages"
    for package in ("swebench", "docker", "datasets"):
        (second / package).mkdir(parents=True, exist_ok=True)
    with pytest.raises(sync.SyncError) as duplicate_error:
        sync_node._swebench_import_root(root, release_python=Path(sys.executable))
    assert duplicate_error.value.code == "RUNTIME_INCOMPATIBLE"

    for package in ("swebench", "docker", "datasets"):
        (second / package).rmdir()
    second.rmdir()
    outside = tmp_path / "outside-site-packages"
    for package in ("swebench", "docker", "datasets"):
        (outside / package).mkdir(parents=True, exist_ok=True)
    site_packages.rename(site_packages.with_name("site-packages-real"))
    os.symlink(outside, site_packages, target_is_directory=True)
    with pytest.raises(sync.SyncError) as escape_error:
        sync_node._swebench_import_root(root, release_python=Path(sys.executable))
    assert escape_error.value.code == "RUNTIME_INCOMPATIBLE"


def test_offline_verification_sanitizes_imports_and_uses_explicit_smoke_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "lab"
    release = root / "releases" / ("a" * 40)
    repo = release / "repo"
    python = release / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    repo.mkdir(parents=True)
    (release / "pydeps").mkdir()
    swebench_root = root / "runtime" / "swebench-venv" / "site-packages"
    swebench_root.mkdir(parents=True)
    calls: list[tuple[list[str], dict[str, str]]] = []

    def run(command: list[str], **kwargs: object) -> SimpleNamespace:
        env = dict(kwargs["env"])
        calls.append((command, env))
        if command[1:2] == ["-c"]:
            return SimpleNamespace(
                stdout=json.dumps(
                    {
                        "ready": True,
                        "version": "4.1.0",
                        "record_digests": {},
                        "tree_digests": {},
                        "tree_file_counts": {},
                    }
                )
            )
        return SimpleNamespace(stdout="1 passed\n")

    monkeypatch.setenv("PYTHONPATH", "/untrusted/inherited")
    monkeypatch.setenv("PYTHONHOME", "/untrusted/home")
    monkeypatch.setattr(
        sync_node,
        "_swebench_import_root",
        lambda *_args, **_kwargs: swebench_root,
    )
    monkeypatch.setattr(sync_node, "_run", run)
    monkeypatch.setattr(
        sync_node,
        "_checkout_identity",
        lambda _repo: {"repo_clean": True},
    )

    receipt = sync_node._run_offline_verification(
        release,
        root,
        {"verification_tests": ["tests/forge_lab_v1"]},
    )

    smoke_command, smoke_env = calls[0]
    assert "assert result['ready']" not in smoke_command[-1]
    assert "sys.exit(0 if result['ready'] else 9)" in smoke_command[-1]
    assert "/untrusted/inherited" not in smoke_env["PYTHONPATH"]
    assert "PYTHONHOME" not in smoke_env
    assert smoke_env["HF_DATASETS_OFFLINE"] == "1"
    assert smoke_env["PYTHONNOUSERSITE"] == "1"
    assert receipt["swebench_runtime"]["version"] == "4.1.0"


def test_canonical_linux_sync_requires_dedicated_swebench_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "canonical-linux"
    release = root / "release"
    (release / ".venv" / "bin").mkdir(parents=True)
    (release / "repo").mkdir()
    (release / "pydeps").mkdir()
    monkeypatch.setattr(sync_node.platform, "system", lambda: "Linux")
    monkeypatch.setattr(sync_node, "DEFAULT_REMOTE_ROOT", root)
    monkeypatch.setattr(
        sync_node,
        "_swebench_import_root",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(sync.SyncError) as error:
        sync_node._run_offline_verification(
            release,
            root,
            {"verification_tests": []},
        )
    assert error.value.code == "RUNTIME_INCOMPATIBLE"
