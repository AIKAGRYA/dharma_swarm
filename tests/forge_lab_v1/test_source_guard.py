from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from dharma_swarm.forge_lab import source_guard


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def _release(tmp_path: Path) -> tuple[Path, Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "remote", "add", "origin", source_guard.CANONICAL_REPOSITORY)
    (source / "tracked.txt").write_text("immutable\n", encoding="utf-8")
    _git(source, "add", "tracked.txt")
    _git(
        source,
        "-c",
        "user.name=Source Guard Test",
        "-c",
        "user.email=source-guard@example.invalid",
        "commit",
        "-m",
        "fixture",
    )
    head = _git(source, "rev-parse", "HEAD")
    base = tmp_path / "releases" / head
    base.mkdir(parents=True)
    repo = base / "repo"
    shutil.move(str(source), repo)
    (base / "RELEASE_MANIFEST.json").write_text(
        json.dumps({"plan": {"commit": head}}), encoding="utf-8"
    )
    return base, repo, head


def test_exact_clean_aikagrya_release_is_admitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, repo, head = _release(tmp_path)
    monkeypatch.setenv("RSI_LAB_BASE", str(base))
    monkeypatch.setenv("RSI_LAB_REPO", str(repo))

    status = source_guard.execution_source_status()

    assert status["ready"] is True
    assert status["commit"] == head
    assert status["remote"] == "https://github.com/AIKAGRYA/dharma_swarm.git"
    assert status["reasons"] == []


def test_dirty_release_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, repo, _head = _release(tmp_path)
    monkeypatch.setenv("RSI_LAB_BASE", str(base))
    monkeypatch.setenv("RSI_LAB_REPO", str(repo))
    (repo / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    status = source_guard.execution_source_status()

    assert status["ready"] is False
    assert "source_checkout_dirty" in status["reasons"]
    with pytest.raises(RuntimeError, match="noncanonical execution source"):
        source_guard.require_execution_source()


def test_redirect_owner_and_mutable_path_are_not_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, repo, _head = _release(tmp_path)
    _git(
        repo,
        "remote",
        "set-url",
        "origin",
        "https://github.com/AmitabhainArunachala/dharma_swarm.git",
    )
    monkeypatch.setenv("RSI_LAB_BASE", str(tmp_path / "current-main"))
    monkeypatch.setenv("RSI_LAB_REPO", str(repo))

    status = source_guard.execution_source_status()

    assert status["ready"] is False
    assert "source_remote_not_canonical_AIKAGRYA" in status["reasons"]
    assert "source_not_under_resolved_RSI_LAB_BASE" in status["reasons"]
