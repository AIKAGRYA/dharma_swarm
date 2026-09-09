"""Installer recovery must preserve user edits and refuse receipt-controlled paths."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dharma_swarm.helm_desktop import install
from dharma_swarm.helm_desktop.config import DesktopConfig, DesktopError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config(tmp_path: Path) -> DesktopConfig:
    return DesktopConfig(ROOT, tmp_path / "state with spaces")


def test_install_restore_and_installed_launcher_end_to_end(config: DesktopConfig) -> None:
    assert install.preview(config)["ready"]
    assert not config.state_dir.exists()
    first = install.apply(config)
    assert first["outcome"] == "installed"
    wrapper = config.state_dir / "bin/helm-desktop"
    result = subprocess.run([str(wrapper), "catalog", "--json"], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["grants_execution_authority"] is False
    assert all(item["action"] == "unchanged" for item in install.apply(config)["files"])
    unrelated = config.state_dir / "my_notes.txt"
    unrelated.write_text("keep my work")
    planned = install.restore(config)
    assert wrapper.exists()
    assert all(item["action"] == "remove_installed" for item in planned["files"])
    restored = install.restore(config, apply_changes=True)
    assert restored["outcome"] == "restored"
    assert not wrapper.exists()
    assert unrelated.read_text() == "keep my work"
    assert install.restore(config, apply_changes=True)["files"] == []


def test_restore_preserves_later_user_edit_and_only_retains_needed_backup(config: DesktopConfig) -> None:
    install.apply(config)
    custom = config.state_dir / "config/aerospace.toml"
    custom.write_text("# operator's later edits\n")
    result = install.restore(config, apply_changes=True)
    assert result["outcome"] == "partial"
    assert result["preserved_count"] == 1
    assert custom.read_text() == "# operator's later edits\n"
    assert not (config.state_dir / "bin/helm-desktop").exists()
    manifest = json.loads((config.state_dir / install.MANIFEST).read_text())
    assert list(manifest["files"]) == ["config/aerospace.toml"]


def test_existing_matching_file_is_restored_with_original_mode(config: DesktopConfig) -> None:
    data, _ = install.artifacts(config)["config/aerospace.toml"]
    target = config.state_dir / "config/aerospace.toml"
    target.parent.mkdir(parents=True)
    target.write_bytes(data)
    target.chmod(0o640)
    install.apply(config)
    assert target.stat().st_mode & 0o777 == 0o600
    install.restore(config, apply_changes=True)
    assert target.read_bytes() == data
    assert target.stat().st_mode & 0o777 == 0o640


def test_conflicting_file_prevents_all_install_mutations(config: DesktopConfig) -> None:
    target = config.state_dir / "bin/helm-desktop"
    target.parent.mkdir(parents=True)
    target.write_text("user's existing launcher\n")
    assert not install.preview(config)["ready"]
    with pytest.raises(DesktopError, match="conflicts"):
        install.apply(config)
    assert target.read_text() == "user's existing launcher\n"
    assert not (config.state_dir / install.MANIFEST).exists()
    assert not (config.state_dir / "profiles").exists()


def test_install_will_not_overwrite_user_profile_edits(config: DesktopConfig) -> None:
    install.apply(config)
    profile = config.state_dir / "profiles/research.json"
    value = json.loads(profile.read_text())
    value["label"] = "My Research"
    profile.write_text(json.dumps(value))
    with pytest.raises(DesktopError, match="conflicts"):
        install.apply(config)
    assert json.loads(profile.read_text())["label"] == "My Research"


@pytest.mark.parametrize("relative", ["../outside", "/tmp/outside", "bin/../../outside", "unrelated.txt"])
def test_restore_refuses_manifest_paths_outside_allowlist(config: DesktopConfig, relative: str) -> None:
    install.apply(config)
    manifest_path = config.state_dir / install.MANIFEST
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][relative] = next(iter(manifest["files"].values()))
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(DesktopError, match="unsupported path"):
        install.restore(config, apply_changes=True)
    assert (config.state_dir / "bin/helm-desktop").exists()


def test_install_refuses_symlink_directory(config: DesktopConfig, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    config.state_dir.mkdir()
    (config.state_dir / "bin").symlink_to(outside, target_is_directory=True)
    with pytest.raises(DesktopError, match="symlink"):
        install.apply(config)
    assert not list(outside.iterdir())
    assert not (config.state_dir / install.MANIFEST).exists()


def test_restore_refuses_replaced_symlink_without_following_it(config: DesktopConfig, tmp_path: Path) -> None:
    install.apply(config)
    outside = tmp_path / "outside.txt"
    outside.write_text("operator work")
    target = config.state_dir / "config/aerospace.toml"
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(DesktopError, match="symlink"):
        install.restore(config, apply_changes=True)
    assert outside.read_text() == "operator work"
    assert (config.state_dir / "bin/helm-desktop").exists()


def test_installer_cli_roundtrip_from_other_directory(config: DesktopConfig, tmp_path: Path) -> None:
    argv = [sys.executable, str(ROOT / "scripts/helm_desktop.py"), "--state-dir", str(config.state_dir), "--json"]
    for command in (["install", "apply", "--apply"], ["uninstall", "--apply"]):
        result = subprocess.run([*argv, *command], cwd=tmp_path, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)["ok"]
    assert not (config.state_dir / "bin/helm-desktop").exists()


def test_deleted_managed_file_is_not_recreated_and_names_recovery(config: DesktopConfig, tmp_path: Path) -> None:
    argv = [sys.executable, str(ROOT / "scripts/helm_desktop.py"), "--state-dir", str(config.state_dir), "--json"]
    assert subprocess.run([*argv, "install", "apply", "--apply"], cwd=tmp_path, capture_output=True,
                          text=True, timeout=10).returncode == 0
    launcher = config.state_dir / "bin/helm-desktop"
    launcher.unlink()

    preview = subprocess.run([*argv, "install", "preview"], cwd=tmp_path, capture_output=True, text=True, timeout=10)
    payload = json.loads(preview.stdout)
    assert payload["ready"] is False
    deleted = [item for item in payload["files"] if item["relative_path"] == "bin/helm-desktop"][0]
    assert deleted["action"] == "conflict"
    assert "deleted after installation" in deleted["reason"] and "restore --apply" in deleted["reason"]

    applied = subprocess.run([*argv, "install", "apply", "--apply"], cwd=tmp_path, capture_output=True,
                             text=True, timeout=10)
    assert applied.returncode == 1
    assert json.loads(applied.stdout)["ok"] is False
    assert not launcher.exists()


def test_restore_preview_succeeds_while_reporting_preserved_edits(config: DesktopConfig, tmp_path: Path) -> None:
    argv = [sys.executable, str(ROOT / "scripts/helm_desktop.py"), "--state-dir", str(config.state_dir), "--json"]
    subprocess.run([*argv, "install", "apply", "--apply"], cwd=tmp_path, capture_output=True, text=True, timeout=10)
    edited = config.state_dir / "config/aerospace.toml"
    edited.write_text(edited.read_text() + "# operator note\n")

    result = subprocess.run([*argv, "uninstall"], cwd=tmp_path, capture_output=True, text=True, timeout=10)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True and payload["outcome"] == "preview" and payload["mutates"] is False
    assert payload["restores_fully"] is False
    assert payload["preserved_count"] == 1 and payload["preserved_paths"] == ["config/aerospace.toml"]

    applied = subprocess.run([*argv, "uninstall", "--apply"], cwd=tmp_path, capture_output=True, text=True, timeout=10)
    applied_payload = json.loads(applied.stdout)
    assert applied.returncode == 1
    assert applied_payload["ok"] is False and applied_payload["outcome"] == "partial"
    assert edited.exists()
