"""Read-only release snapshot and disposable replay for Foundry refusal runs."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from dharma_swarm.foundry.patches import (
    PatchReplayError,
    apply_unified_diff,
    read_regular_nofollow,
)
from dharma_swarm.foundry.runner_isolation import (
    IsolationLevel,
    IsolationPolicy,
    RunResult,
    run_isolated,
)
from dharma_swarm.governed_patch_candidate_bundle import CandidateBundle
from dharma_swarm.governed_patch_evidence import GovernedPatchEvidenceError

_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
_MAX_ARCHIVE_MEMBERS = 20_000


class FoundryWorkspaceError(RuntimeError):
    """The admitted release could not be reproduced in disposable storage."""


def _git_environment() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": "/nonexistent",
    }


def _git(repo: Path, *args: str, timeout: float = 30.0) -> str:
    executable = shutil.which("git", path="/usr/bin:/bin")
    if not executable:
        raise FoundryWorkspaceError("trusted Git executable is unavailable")
    try:
        result = subprocess.run(
            [executable, "-c", "core.fsmonitor=false", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_git_environment(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FoundryWorkspaceError("Git provenance command failed") from exc
    if result.returncode != 0:
        raise FoundryWorkspaceError("Git provenance command was rejected")
    if len(result.stdout.encode("utf-8")) > 1024 * 1024:
        raise FoundryWorkspaceError("Git provenance output exceeded its bound")
    return result.stdout.rstrip("\n")


def repo_snapshot(repo: Path, expected_commit: str) -> dict[str, Any]:
    """Return one exact clean release observation or fail closed."""

    head = _git(repo, "rev-parse", "HEAD")
    origin_main = _git(repo, "rev-parse", "refs/remotes/origin/main")
    status = _git(
        repo,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )
    ahead_behind = _git(
        repo,
        "rev-list",
        "--left-right",
        "--count",
        "HEAD...refs/remotes/origin/main",
    ).split()
    if (
        head != expected_commit
        or origin_main != expected_commit
        or status
        or ahead_behind != ["0", "0"]
    ):
        raise FoundryWorkspaceError("release Git state is not the exact clean base")
    return {
        "head": head,
        "tree": _git(repo, "rev-parse", "HEAD^{tree}"),
        "origin_main": origin_main,
        "ahead": 0,
        "behind": 0,
        "clean": True,
        "status_sha256": hashlib.sha256(status.encode("utf-8")).hexdigest(),
    }


def _git_archive(repo: Path, base_sha: str, destination: Path) -> None:
    executable = shutil.which("git", path="/usr/bin:/bin")
    if not executable:
        raise FoundryWorkspaceError("trusted Git executable is unavailable")
    try:
        with destination.open("xb") as output:
            result = subprocess.run(
                [
                    executable,
                    "-c",
                    "core.fsmonitor=false",
                    "-C",
                    str(repo),
                    "archive",
                    "--format=tar",
                    base_sha,
                ],
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=120.0,
                env=_git_environment(),
                check=False,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FoundryWorkspaceError("base archive creation failed") from exc
    if result.returncode != 0 or destination.stat().st_size > _MAX_ARCHIVE_BYTES:
        raise FoundryWorkspaceError("base archive is unavailable or exceeds its bound")


def _safe_extract_archive(archive_path: Path, destination: Path) -> None:
    total = 0
    try:
        with tarfile.open(archive_path, mode="r:") as archive:
            for index, member in enumerate(archive, start=1):
                if index > _MAX_ARCHIVE_MEMBERS:
                    raise FoundryWorkspaceError("base archive has too many members")
                relative = PurePosixPath(member.name)
                if (
                    member.name.startswith("/")
                    or any(part in {"", ".", ".."} for part in relative.parts)
                    or not (member.isdir() or member.isreg())
                ):
                    raise FoundryWorkspaceError("base archive contains an unsafe member")
                target = destination.joinpath(*relative.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True, mode=0o755)
                    os.chmod(target, stat.S_IMODE(member.mode) & 0o755 or 0o755)
                    continue
                total += member.size
                if total > _MAX_ARCHIVE_BYTES:
                    raise FoundryWorkspaceError("extracted base exceeds its size bound")
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                source = archive.extractfile(member)
                if source is None:
                    raise FoundryWorkspaceError("base archive member is unreadable")
                flags = (
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_NOFOLLOW", 0)
                )
                descriptor = os.open(target, flags, 0o600)
                try:
                    with os.fdopen(descriptor, "wb") as output:
                        shutil.copyfileobj(source, output, length=64 * 1024)
                        output.flush()
                        os.fsync(output.fileno())
                    descriptor = -1
                finally:
                    if descriptor >= 0:
                        os.close(descriptor)
                    source.close()
                os.chmod(target, stat.S_IMODE(member.mode) & 0o755 or 0o600)
    except (tarfile.TarError, OSError) as exc:
        raise FoundryWorkspaceError("base archive extraction failed") from exc


def _prepare_private_scratch_parent(path: Path) -> Path:
    """Create/validate a composition-owned, no-symlink scratch directory."""

    parent = path.parent
    if not parent.exists():
        try:
            parent.mkdir(mode=0o700)
        except OSError as exc:
            raise FoundryWorkspaceError("scratch parent owner is unavailable") from exc
    for candidate, label in ((parent, "scratch owner"), (path, "scratch directory")):
        if candidate == path and not candidate.exists():
            try:
                candidate.mkdir(mode=0o700)
            except OSError as exc:
                raise FoundryWorkspaceError("scratch directory cannot be created") from exc
        try:
            metadata = candidate.lstat()
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise FoundryWorkspaceError(f"{label} cannot be validated") from exc
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or resolved != candidate
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise FoundryWorkspaceError(
                f"{label} must be an owner-only canonical directory"
            )
    return path


def _blocked_result(reason: str) -> RunResult:
    return RunResult(
        exit_code=-1,
        stdout="",
        stderr="",
        duration_s=0.0,
        isolation_level=IsolationLevel.BLOCKED.value,
        blocked=True,
        blocked_reason=reason,
    )


def replay_candidate(
    bundle: CandidateBundle,
    policy: IsolationPolicy,
    *,
    scratch_parent: Path,
) -> tuple[RunResult, dict[str, Any]]:
    """Replay in a bounded snapshot and run only the candidate's exact argv."""

    replay = {
        "attempted": True,
        "applied": False,
        "patched_source_sha256": "",
        "error": "",
    }
    try:
        scratch_parent = _prepare_private_scratch_parent(scratch_parent)
        with tempfile.TemporaryDirectory(
            prefix="dharma-foundry-refusal-",
            dir=scratch_parent,
        ) as raw:
            temporary = Path(raw)
            archive = temporary / "base.tar"
            evaluation_root = temporary / "tree"
            evaluation_root.mkdir(mode=0o755)
            _git_archive(bundle.repo_root, bundle.bindings.base_sha, archive)
            _safe_extract_archive(archive, evaluation_root)
            source = read_regular_nofollow(
                evaluation_root / bundle.authorized_source_path,
                field="archived authorized source",
                error_type=PatchReplayError,
            )
            if hashlib.sha256(source).hexdigest() != bundle.source_sha256:
                raise FoundryWorkspaceError(
                    "archived source does not match candidate base"
                )
            try:
                diff = bundle.diff_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise FoundryWorkspaceError(
                    "verified candidate diff snapshot is not UTF-8"
                ) from exc
            patched = apply_unified_diff(
                evaluation_root,
                diff,
                allowed_paths=(bundle.authorized_source_path,),
            )
            replay["applied"] = True
            replay["patched_source_sha256"] = hashlib.sha256(
                read_regular_nofollow(patched, field="patched source")
            ).hexdigest()
            result = run_isolated(bundle.oracle_argv, str(evaluation_root), policy)
    except (
        FoundryWorkspaceError,
        GovernedPatchEvidenceError,
        PatchReplayError,
        OSError,
    ) as exc:
        replay["error"] = type(exc).__name__
        result = _blocked_result("disposable candidate replay failed")
    return result, replay


__all__ = ["FoundryWorkspaceError", "repo_snapshot", "replay_candidate"]
