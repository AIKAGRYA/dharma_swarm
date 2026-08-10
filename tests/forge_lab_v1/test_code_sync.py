"""Safety and exactness tests for the RSI Lab release synchronizer."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from dharma_swarm.forge_lab import sync_control as sync
from dharma_swarm.forge_lab import sync_orchestrator as orchestrator


RETIRED_STUB = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "forge_lab"
    / "rsi-legacy-retired"
)


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
    retired = repo / "scripts" / "forge_lab" / "rsi-legacy-retired"
    retired.parent.mkdir(parents=True, exist_ok=True)
    retired.write_text("#!/usr/bin/env bash\nexit 64\n", encoding="utf-8")
    retired.chmod(0o755)
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


def test_legacy_retirement_stub_fails_without_mutating_sourcing_shell() -> None:
    executed = subprocess.run(
        ["bash", str(RETIRED_STUB)],
        capture_output=True,
        check=False,
        text=True,
    )
    assert executed.returncode == 64
    assert "retired legacy RSI control surface" in executed.stderr

    sourced = subprocess.run(
        [
            "bash",
            "-c",
            'before="$-"; . "$1"; code=$?; after="$-"; printf "%s:%s:%s" "$code" "$before" "$after"',
            "retirement-stub-test",
            str(RETIRED_STUB),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    code, before, after = sourced.stdout.split(":")
    assert sourced.returncode == 0
    assert code == "64"
    assert after == before


def test_activation_is_atomic_idempotent_and_preserves_host_state(
    tmp_path: Path,
) -> None:
    root, release, plan = _make_release(tmp_path)
    (root / "bin").mkdir()
    (root / "bin" / "rsi-env").write_text("legacy env\n", encoding="utf-8")
    mutating = {
        "rsi-run": "legacy run\n",
        "rsi-loop": "legacy loop\n",
        "rsi-fix-substrate": "legacy mutation\n",
        "rsi-keys-refresh": "legacy live probe\n",
        "rsi-update-main": "legacy git mutation\n",
    }
    for name, content in mutating.items():
        path = root / "bin" / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
    (root / "bin" / "rsi-status").write_text("unrelated observer\n", encoding="utf-8")
    (root / "bin" / "operator-custom").write_text("unrelated\n", encoding="utf-8")

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
    retired_target = release / "repo" / "scripts" / "forge_lab" / "rsi-legacy-retired"
    for name in (*mutating, "rsi-env"):
        assert (root / "bin" / name).is_symlink()
        assert (root / "bin" / name).resolve() == retired_target
    assert (root / "bin" / "rsi-status").read_text(encoding="utf-8") == "unrelated observer\n"
    assert (root / "bin" / "operator-custom").read_text(encoding="utf-8") == "unrelated\n"
    assert (root / "bin" / "rsi-lab-env").is_symlink()

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
    assert (root / "bin" / "rsi-status").read_text(encoding="utf-8") == "unrelated observer\n"


def test_node_status_rejects_live_legacy_mutating_launcher(tmp_path: Path) -> None:
    root, _, plan = _make_release(tmp_path)
    sync.activate_release(
        plan,
        root,
        node="meghadharma",
        request_id="test-launcher-hygiene",
        expected_current=None,
        require_canonical_head=False,
    )
    legacy = root / "bin" / "rsi-run"
    legacy.unlink()
    legacy.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    legacy.chmod(0o755)

    status = sync.node_status(root, node="meghadharma")

    assert status["ready"] is False
    assert status["launcher_hygiene"]["ok"] is False
    assert any("rsi-run" in message for message in status["errors"])


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


def test_authoritative_fenced_lease_blocks_release_switch(tmp_path: Path) -> None:
    root, _, _ = _make_release(tmp_path)
    db_path = (
        root
        / "state"
        / ".dharma"
        / "forge_lab"
        / "campaigns"
        / "control.sqlite3"
    )
    db_path.parent.mkdir(parents=True)
    with sqlite3.connect(db_path) as db:
        db.execute(
            """CREATE TABLE campaigns(
            campaign_id TEXT, active_fence INTEGER, lease_holder TEXT,
            lease_mode TEXT, lease_expires TEXT)"""
        )
        db.execute(
            "INSERT INTO campaigns VALUES(?,?,?,?,?)",
            (
                "forge-lab-n30-to-1000-v1",
                7,
                "codex-rsi-lab-manager",
                "active",
                "2099-01-01T00:00:00Z",
            ),
        )

    guard = sync._campaign_guard(root)

    assert guard["ok"] is False
    assert "authoritative campaign lease count: 1" in guard["reasons"]
    assert guard["evidence"]["authoritative_active_leases"][0][
        "fencing_token"
    ] == 7


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
    # This fixture stands in for both hosts; materialize the Meghadharma-only
    # retirement aliases before asking its status contract to inspect the root.
    sync._install_wrappers(root, (root / "current").resolve(), node="meghadharma")
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
