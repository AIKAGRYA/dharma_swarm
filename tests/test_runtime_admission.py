"""Tests for fail-closed live-runtime provenance admission."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from dharma_swarm import runtime_admission as runtime_admission_module
from dharma_swarm.runtime_admission import (
    ContainerRuntimeAdmission,
    RuntimeAdmissionError,
    assess_container_runtime_admission,
    assess_runtime_admission,
    require_runtime_admission,
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


def test_git_probe_ignores_ambient_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, head = _runtime_repo(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text("#!/bin/sh\necho fabricated\nexit 0\n", encoding="utf-8")
    fake_git.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin))

    admission = assess_runtime_admission(repo)

    assert admission.head == head


def test_missing_trusted_git_binary_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _ = _runtime_repo(tmp_path)
    monkeypatch.setattr(
        runtime_admission_module,
        "_TRUSTED_GIT_BINARY",
        str(tmp_path / "missing-git"),
    )

    with pytest.raises(RuntimeAdmissionError, match="trusted Git executable"):
        assess_runtime_admission(repo)


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


def test_ignored_import_bytecode_is_rejected(tmp_path: Path) -> None:
    repo, _head = _runtime_repo(tmp_path)
    (repo / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(
        repo,
        "-c",
        "user.name=Runtime Admission Test",
        "-c",
        "user.email=runtime-admission@example.invalid",
        "commit",
        "-m",
        "ignore bytecode",
    )
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    (repo / "sitecustomize.pyc").write_bytes(b"ignored startup bytecode")

    with pytest.raises(RuntimeAdmissionError, match="ignored import bytecode"):
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
    with pytest.raises(RuntimeAdmissionError, match="full 40-character"):
        assess_runtime_admission(repo, expected_commit="   ")
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


def _container_source(tmp_path: Path) -> tuple[Path, Path, str]:
    app = tmp_path / "app"
    source = app / "dharma_swarm"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text('"""sealed"""', encoding="utf-8")
    (source / "worker.py").write_text("VALUE = 1\n", encoding="utf-8")
    lines = []
    for path in sorted(item for item in source.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  ./{path.relative_to(source).as_posix()}")
    manifest = app / ".dharma-runtime-source.sha256"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    return source, manifest, manifest_digest


def test_container_image_source_manifest_is_a_distinct_admission(
    tmp_path: Path,
) -> None:
    source, manifest, digest = _container_source(tmp_path)

    admission = assess_container_runtime_admission(
        source,
        manifest=manifest,
        expected_digest=digest,
    )

    assert isinstance(admission, ContainerRuntimeAdmission)
    assert admission.source_root == source
    assert admission.source_digest == digest


def test_container_image_admission_rejects_tampering_and_mixed_git_pin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, manifest, digest = _container_source(tmp_path)
    environment = {
        "DHARMA_RUNTIME_PROVENANCE_MODE": "container-image",
        "DHARMA_RUNTIME_SOURCE_ROOT": str(source),
        "DHARMA_RUNTIME_SOURCE_MANIFEST": str(manifest),
        "DHARMA_RUNTIME_SOURCE_DIGEST": digest,
    }
    monkeypatch.setattr(
        runtime_admission_module,
        "_loaded_package_root",
        lambda: source,
    )

    assert isinstance(
        require_runtime_admission(environ=environment),
        ContainerRuntimeAdmission,
    )
    with pytest.raises(RuntimeAdmissionError, match="cannot be combined"):
        require_runtime_admission(
            expected_commit="a" * 40,
            environ=environment,
        )

    (source / "worker.py").write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(RuntimeAdmissionError, match="does not match"):
        require_runtime_admission(environ=environment)


def test_container_image_admission_is_execution_bound(tmp_path: Path) -> None:
    source, manifest, digest = _container_source(tmp_path)
    environment = {
        "DHARMA_RUNTIME_PROVENANCE_MODE": "container-image",
        "DHARMA_RUNTIME_SOURCE_ROOT": str(source),
        "DHARMA_RUNTIME_SOURCE_MANIFEST": str(manifest),
        "DHARMA_RUNTIME_SOURCE_DIGEST": digest,
    }

    with pytest.raises(
        RuntimeAdmissionError,
        match="does not supply the loaded runtime",
    ):
        require_runtime_admission(environ=environment)
