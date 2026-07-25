"""Tests for fail-closed live-runtime provenance admission."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.runtime_admission import (
    RuntimeAdmissionError,
    assess_runtime_admission,
    runtime_admission_or_exit,
)


def _git(repo: Path, *args: str) -> str:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _commit(repo: Path, text: str) -> str:
    (repo / "runtime.txt").write_text(text, encoding="utf-8")
    _git(repo, "add", "runtime.txt")
    _git(
        repo,
        "-c",
        "user.name=Runtime Admission Test",
        "-c",
        "user.email=runtime-admission@example.invalid",
        "commit",
        "-m",
        text,
    )
    return _git(repo, "rev-parse", "HEAD")


def _runtime_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "runtime"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    head = _commit(repo, "base")
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    return repo, head


def test_clean_exact_main_checkout_is_admitted(tmp_path: Path) -> None:
    repo, head = _runtime_repo(tmp_path)

    admission = assess_runtime_admission(repo)

    assert admission.head == head
    assert admission.origin_main == head
    assert admission.expected_commit is None
    assert (admission.ahead, admission.behind) == (0, 0)


def test_untracked_path_is_rejected_because_it_can_change_imports(
    tmp_path: Path,
) -> None:
    repo, _head = _runtime_repo(tmp_path)
    (repo / "sitecustomize.py").write_text("raise SystemExit(1)", encoding="utf-8")

    with pytest.raises(RuntimeAdmissionError, match="uncommitted paths"):
        assess_runtime_admission(repo)


def test_tracked_dirty_checkout_is_rejected(tmp_path: Path) -> None:
    repo, _head = _runtime_repo(tmp_path)
    (repo / "runtime.txt").write_text("mutated", encoding="utf-8")

    with pytest.raises(RuntimeAdmissionError, match="uncommitted paths"):
        assess_runtime_admission(repo)


def test_unpinned_ahead_branch_is_rejected_but_exact_release_pin_is_admitted(
    tmp_path: Path,
) -> None:
    repo, base = _runtime_repo(tmp_path)
    release_head = _commit(repo, "release fix")

    with pytest.raises(RuntimeAdmissionError, match="must equal origin/main"):
        assess_runtime_admission(repo)

    admission = assess_runtime_admission(
        repo,
        expected_commit=release_head,
    )
    assert admission.origin_main == base
    assert admission.head == release_head
    assert admission.expected_commit == release_head
    assert (admission.ahead, admission.behind) == (1, 0)


def test_stale_checkout_is_rejected_even_when_pinned_to_its_old_head(
    tmp_path: Path,
) -> None:
    repo, old_head = _runtime_repo(tmp_path)
    current_main = _commit(repo, "new main")
    _git(repo, "update-ref", "refs/remotes/origin/main", current_main)
    _git(repo, "checkout", "--detach", old_head)

    with pytest.raises(RuntimeAdmissionError, match="must equal origin/main"):
        assess_runtime_admission(repo)
    with pytest.raises(RuntimeAdmissionError, match="not a current-main descendant"):
        assess_runtime_admission(repo, expected_commit=old_head)


def test_release_pin_must_match_head_and_use_full_sha(tmp_path: Path) -> None:
    repo, head = _runtime_repo(tmp_path)

    with pytest.raises(RuntimeAdmissionError, match="full 40-character"):
        assess_runtime_admission(repo, expected_commit=head[:12])
    with pytest.raises(RuntimeAdmissionError, match="does not match pinned"):
        assess_runtime_admission(repo, expected_commit="0" * 40)


def test_non_git_runtime_root_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(RuntimeAdmissionError, match="git provenance probe failed"):
        assess_runtime_admission(tmp_path)


def test_command_boundary_exits_with_configuration_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, old_head = _runtime_repo(tmp_path)
    current_main = _commit(repo, "new main")
    _git(repo, "update-ref", "refs/remotes/origin/main", current_main)
    _git(repo, "checkout", "--detach", old_head)

    with pytest.raises(SystemExit) as exc:
        runtime_admission_or_exit(repo, environ={})

    assert exc.value.code == 78
    assert "admission denied" in capsys.readouterr().err
