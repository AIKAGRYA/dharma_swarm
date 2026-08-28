"""Pinned Git and registered-worktree inspection for governed patch effects."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.evolution_safety import EVOLUTION_MARKER

_TIMEOUT = 10


class EffectGitError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GitExecutableBinding:
    path: Path
    sha256: str
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class GitRepositoryBinding:
    common_dir_path: str
    common_dir_device: int
    common_dir_inode: int
    worktree_registration_sha256: str
    index_sha256: str
    canonical_repo_identity: str


@dataclass(frozen=True, slots=True)
class _Result:
    code: int
    stdout: bytes
    stderr: bytes


def _identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_ctime_ns,
        value.st_mtime_ns,
    )


def _hash_owned_regular(path: Path, *, executable: bool = False) -> tuple[str, os.stat_result]:
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
    except OSError as exc:
        raise EffectGitError(f"pinned Git file is unavailable: {path}") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or (executable and before.st_uid != 0)
            or stat.S_IMODE(before.st_mode) & 0o022
            or before.st_size <= 0
            or before.st_size > 256 * 1024 * 1024
        ):
            raise EffectGitError(f"pinned Git file custody is unsafe: {path}")
        digest = hashlib.sha256()
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
        if remaining or _identity(before) != _identity(after):
            raise EffectGitError(f"pinned Git file changed while read: {path}")
        return digest.hexdigest(), before
    finally:
        os.close(descriptor)


def inspect_git_executable(supplied: Path) -> GitExecutableBinding:
    if not supplied.is_absolute():
        raise EffectGitError("pinned Git executable must be absolute")
    try:
        path = supplied.resolve(strict=True)
    except OSError as exc:
        raise EffectGitError("pinned Git executable is unavailable") from exc
    cursor = path.parent
    while True:
        metadata = cursor.stat(follow_symlinks=False)
        if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022:
            raise EffectGitError("pinned Git executable ancestry is writable/untrusted")
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    digest, metadata = _hash_owned_regular(path, executable=True)
    return GitExecutableBinding(path, digest, metadata.st_dev, metadata.st_ino)


def _environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"HOME", "LOGNAME", "SYSTEMROOT", "TMPDIR", "USER"}
    }
    environment.update(
        {
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_COUNT": "0",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        }
    )
    return environment


def _run(root: Path, executable: GitExecutableBinding, *args: str) -> _Result:
    if inspect_git_executable(executable.path) != executable:
        raise EffectGitError("pinned Git executable identity drifted")
    try:
        process = subprocess.run(
            [
                str(executable.path),
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.filemode=true",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "core.attributesFile=/dev/null",
                "-c",
                "diff.external=",
                "-C",
                str(root),
                *args,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=_TIMEOUT,
            check=False,
            env=_environment(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise EffectGitError("pinned Git command is unavailable") from exc
    return _Result(process.returncode, process.stdout, process.stderr)


def _git(root: Path, executable: GitExecutableBinding, *args: str) -> bytes:
    result = _run(root, executable, *args)
    if result.code:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[:200]
        raise EffectGitError(f"pinned Git check failed: {detail or result.code}")
    return result.stdout


def _line(raw: bytes, field: str) -> str:
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EffectGitError(f"Git {field} is malformed") from exc
    if not value.endswith("\n") or "\n" in value[:-1] or not value[:-1]:
        raise EffectGitError(f"Git {field} is malformed")
    return value[:-1]


def _resolved_git_path(
    repo: Path, executable: GitExecutableBinding, *args: str
) -> Path:
    raw = Path(_line(_git(repo, executable, *args), "path"))
    if not raw.is_absolute():
        raw = repo / raw
    try:
        return raw.resolve(strict=True)
    except OSError as exc:
        raise EffectGitError("Git metadata path is unavailable") from exc


def _registration_valid(raw: bytes, *, root: Path, base_sha: str) -> bool:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    for block in text.strip().split("\n\n"):
        lines = block.splitlines()
        if (
            f"worktree {root}" in lines
            and f"HEAD {base_sha}" in lines
            and "detached" in lines
        ):
            return True
    return False


def _inventory(
    root: Path,
    executable: GitExecutableBinding,
    *,
    source_path: str,
    target_state: str,
    allowed_temp_path: str | None,
) -> None:
    flags = _git(root, executable, "ls-files", "-v", "-z")
    if any(not record.startswith(b"H ") for record in flags.split(b"\x00") if record):
        raise EffectGitError("Git index has non-default tracked-file flags")
    stage_records = list(
        filter(
            None,
            _git(root, executable, "ls-files", "--stage", "-z", "--", source_path).split(
                b"\x00"
            ),
        )
    )
    stage_pattern = re.compile(
        rb"^(100644|100755) [0-9a-f]{40,64} 0\t" + re.escape(source_path.encode()) + rb"$"
    )
    if len(stage_records) != 1 or stage_pattern.fullmatch(stage_records[0]) is None:
        raise EffectGitError("authorized source is not one stage-0 regular Git blob")
    untracked = set(
        filter(
            None,
            _git(root, executable, "ls-files", "--others", "--exclude-standard", "-z").split(
                b"\x00"
            ),
        )
    )
    ignored = set(
        filter(
            None,
            _git(
                root,
                executable,
                "ls-files",
                "--others",
                "--ignored",
                "--exclude-standard",
                "-z",
            ).split(b"\x00"),
        )
    )
    marker = EVOLUTION_MARKER.encode("utf-8")
    allowed = {marker}
    if allowed_temp_path:
        allowed.add(allowed_temp_path.encode("utf-8"))
    observed = untracked | ignored
    if untracked & ignored or marker not in observed or not observed <= allowed:
        raise EffectGitError("Git ignored/untracked inventory exceeds the exact allowlist")
    diff_flags = ("--no-ext-diff", "--no-textconv", "--name-only", "-z")
    staged = _git(root, executable, "diff", "--cached", *diff_flags, "--")
    unstaged = set(
        filter(
            None,
            _git(root, executable, "diff", *diff_flags, "--").split(b"\x00"),
        )
    )
    expected = set() if target_state == "preimage" else {source_path.encode("utf-8")}
    if staged or unstaged != expected:
        raise EffectGitError("Git staged/unstaged diff is not the exact effect state")


def inspect_registered_worktree(
    root: Path,
    canonical_repo: Path,
    *,
    executable_path: Path,
    base_sha: str,
    source_path: str,
    target_state: str,
    allowed_temp_path: str | None = None,
) -> tuple[GitExecutableBinding, GitRepositoryBinding]:
    executable = inspect_git_executable(executable_path)
    top = Path(_line(_git(root, executable, "rev-parse", "--show-toplevel"), "root"))
    if top.resolve(strict=True) != root:
        raise EffectGitError("effect target is not the exact Git worktree root")
    if _line(_git(root, executable, "rev-parse", "HEAD"), "HEAD") != base_sha:
        raise EffectGitError("scratch Git HEAD does not match the exact base")
    symbolic = _run(root, executable, "symbolic-ref", "-q", "HEAD")
    if symbolic.code != 1 or symbolic.stdout or symbolic.stderr:
        raise EffectGitError("scratch worktree is not detached")
    common = _resolved_git_path(root, executable, "rev-parse", "--git-common-dir")
    canonical_common = _resolved_git_path(
        canonical_repo, executable, "rev-parse", "--git-common-dir"
    )
    if common != canonical_common:
        raise EffectGitError("scratch worktree is not registered to the trusted repo")
    common_metadata = common.stat(follow_symlinks=False)
    if not stat.S_ISDIR(common_metadata.st_mode):
        raise EffectGitError("trusted Git common directory is malformed")
    registration = _git(canonical_repo, executable, "worktree", "list", "--porcelain")
    if not _registration_valid(registration, root=root, base_sha=base_sha):
        raise EffectGitError("scratch worktree registration is absent or mismatched")
    index = _resolved_git_path(root, executable, "rev-parse", "--git-path", "index")
    index_sha, _ = _hash_owned_regular(index)
    _inventory(
        root,
        executable,
        source_path=source_path,
        target_state=target_state,
        allowed_temp_path=allowed_temp_path,
    )
    identity_body = {
        "canonical_repo": str(canonical_repo),
        "common_dir": str(common),
        "common_device": common_metadata.st_dev,
        "common_inode": common_metadata.st_ino,
        "base_sha": base_sha,
    }
    canonical_identity = "sha256:" + hashlib.sha256(
        json.dumps(identity_body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return executable, GitRepositoryBinding(
        str(common),
        common_metadata.st_dev,
        common_metadata.st_ino,
        hashlib.sha256(registration).hexdigest(),
        index_sha,
        canonical_identity,
    )


__all__ = [
    "EffectGitError",
    "GitExecutableBinding",
    "GitRepositoryBinding",
    "inspect_registered_worktree",
]
