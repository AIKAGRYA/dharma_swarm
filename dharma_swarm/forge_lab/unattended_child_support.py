"""Process and standalone-clone support for the unattended child runtime."""

from __future__ import annotations

import os
import shutil
import signal
import stat
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.forge_lab.source_guard import require_execution_source
from dharma_swarm.forge_lab.state_io import write_json_exclusive
from dharma_swarm.forge_lab.unattended_policy import (
    RUN_USD_RESERVATION,
    UnattendedError,
)

CHILD_MODULE = "dharma_swarm.forge_lab.unattended_explore"


def lexical_path(path: Path | str) -> Path:
    """Normalize an absolute path without following a final symlink."""

    return Path(os.path.abspath(os.path.normpath(os.fspath(path))))


def lexists(path: Path | str) -> bool:
    return os.path.lexists(os.fspath(path))


def run_child_process(
    spec_path: Path,
    *,
    run_id: str,
    timeout_seconds: int,
    log_path: Path,
    halt_path: Path,
    scratch_root_identity: dict[str, int],
    scratch_marker_digest: str,
) -> tuple[int, bool, bool, int]:
    """Run the experiment in a child process with an external wall-clock fuse."""

    env = os.environ.copy()
    env.update(
        {
            "RSI_LAB_UNATTENDED_CHILD_RUN_ID": run_id,
            "RSI_LAB_UNATTENDED_SCRATCH_DEVICE": str(
                scratch_root_identity["device"]
            ),
            "RSI_LAB_UNATTENDED_SCRATCH_INODE": str(
                scratch_root_identity["inode"]
            ),
            "RSI_LAB_UNATTENDED_SCRATCH_MARKER_DIGEST": scratch_marker_digest,
            "DHARMA_MODEL_BUDGET_USD": str(RUN_USD_RESERVATION),
            "DHARMA_EVOLUTION_SHADOW": "1",
            "DHARMA_SELF_IMPROVE": "0",
            "DHARMA_ALLOW_LIVE_MUTATION": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    started = time.monotonic()
    deadline = started + timeout_seconds
    timed_out = False
    halted = False
    with os.fdopen(descriptor, "wb") as log_handle:
        process = subprocess.Popen(
            [sys.executable, "-m", CHILD_MODULE, "--child-spec", str(spec_path)],
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        returncode: int | None = None
        while returncode is None:
            if lexists(halt_path):
                halted = True
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                returncode = process.wait(timeout=min(2.0, remaining))
            except subprocess.TimeoutExpired:
                continue
        if returncode is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                returncode = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                returncode = process.wait(timeout=10)
        log_handle.flush()
        os.fsync(log_handle.fileno())
    return returncode, timed_out, halted, round(time.monotonic() - started)


def with_scratch_custody(seams: Any) -> tuple[Any, Callable[[], None]]:
    """Track child-created scratch clones and remove them on every exit path."""

    original_make = getattr(seams, "make_worktree", None)
    original_remove = getattr(seams, "remove_worktree", None)
    if not callable(original_make) or not callable(original_remove):
        raise UnattendedError(
            "SCRATCH_CUSTODY_MISSING",
            "bounded child seams must provide scratch create/remove operations",
        )

    pending: dict[Path, tuple[Path, str]] = {}

    def tracked_make(
        *,
        source_repo: Path,
        experiment_id: str,
        archive_path: Path,
        category: str,
    ) -> Path:
        repo = Path(
            original_make(
                source_repo=source_repo,
                experiment_id=experiment_id,
                archive_path=archive_path,
                category=category,
            )
        )
        pending[lexical_path(repo)] = (source_repo, experiment_id)
        return repo

    def tracked_remove(
        *, source_repo: Path, repo: Path, experiment_id: str
    ) -> None:
        resolved = lexical_path(repo)
        original_remove(
            source_repo=source_repo,
            repo=repo,
            experiment_id=experiment_id,
        )
        if lexists(resolved):
            raise UnattendedError("SCRATCH_REMOVE_UNCONFIRMED", str(resolved))
        pending.pop(resolved, None)

    def cleanup() -> None:
        errors: list[str] = []
        for repo, (source_repo, experiment_id) in list(pending.items()):
            if not lexists(repo):
                pending.pop(repo, None)
                continue
            try:
                original_remove(
                    source_repo=source_repo,
                    repo=repo,
                    experiment_id=experiment_id,
                )
                if lexists(repo):
                    raise UnattendedError("SCRATCH_REMOVE_UNCONFIRMED", str(repo))
            except Exception as exc:
                errors.append(f"{type(exc).__name__}:{repo}")
            else:
                pending.pop(repo, None)
        if errors:
            raise UnattendedError("SCRATCH_CLEANUP_FAILED", ",".join(errors))

    return (
        replace(
            seams,
            make_worktree=tracked_make,
            remove_worktree=tracked_remove,
        ),
        cleanup,
    )


def run_with_scratch_custody(
    seams: Any,
    execute: Callable[[Any], Any],
) -> Any:
    """Run one child body and confirm scratch cleanup even when it raises."""

    custodied_seams, cleanup = with_scratch_custody(seams)
    try:
        return execute(custodied_seams)
    finally:
        cleanup()


def _run_git(argv: list[str], *, cwd: Path | None = None, timeout: int = 300) -> None:
    result = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
        env={
            "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin",
            "HOME": os.environ.get("HOME", "/nonexistent"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        },
    )
    if result.returncode != 0:
        raise UnattendedError("SCRATCH_GIT_FAILED", result.stderr.strip()[:500])


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def clone_scratch(
    *,
    source_repo: Path,
    experiment_id: str,
    archive_path: Path,
    category: str,
) -> Path:
    """Clone exact release bytes without writing the immutable source Git dir."""

    from dharma_swarm.evolution_safety import EVOLUTION_MARKER, is_scratch_worktree

    if (
        not experiment_id
        or Path(experiment_id).name != experiment_id
        or experiment_id in {".", ".."}
    ):
        raise UnattendedError("SCRATCH_PATH_UNSAFE", str(experiment_id))
    scratch_root = lexical_path(os.environ["DHARMA_EVOLUTION_WORKTREE_ROOT"])
    try:
        root_mode = scratch_root.lstat().st_mode
    except OSError as exc:
        raise UnattendedError("SCRATCH_ROOT_UNAVAILABLE", str(scratch_root)) from exc
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise UnattendedError("SCRATCH_ROOT_UNSAFE", str(scratch_root))
    experiment_root = scratch_root / experiment_id
    repo = experiment_root / "repo"
    if scratch_root not in repo.parents or lexists(experiment_root):
        raise UnattendedError("SCRATCH_PATH_UNSAFE", str(repo))
    commit = str(require_execution_source(source_repo)["commit"])
    created = False
    try:
        experiment_root.mkdir(mode=0o700, parents=False, exist_ok=False)
        created = True
        _run_git(
            [
                "git",
                "clone",
                "--no-hardlinks",
                "--no-checkout",
                "--quiet",
                str(source_repo),
                str(repo),
            ]
        )
        _run_git(["git", "checkout", "--detach", "--quiet", commit], cwd=repo)
        marker = {
            "experiment_id": experiment_id,
            "git_base_sha": commit,
            "created_at": _now(),
            "archive_path": str(archive_path),
            "category": category,
            "standalone_clone": True,
        }
        marker_path = repo / EVOLUTION_MARKER
        write_json_exclusive(marker_path, marker)
        ok, _payload, reason = is_scratch_worktree(repo)
        if not ok:
            raise UnattendedError("SCRATCH_MARKER_REFUSED", str(reason))
    except Exception as exc:
        if created:
            try:
                mode = experiment_root.lstat().st_mode
                if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                    raise OSError("partial scratch root changed type")
                shutil.rmtree(experiment_root)
                if lexists(experiment_root):
                    raise OSError("partial scratch removal unconfirmed")
            except OSError as cleanup_exc:
                raise UnattendedError(
                    "SCRATCH_PARTIAL_CLEANUP_FAILED",
                    f"{experiment_root}:{type(cleanup_exc).__name__}",
                ) from exc
        raise
    return repo


def remove_clone_scratch(
    *, source_repo: Path, repo: Path, experiment_id: str
) -> None:
    del source_repo
    from dharma_swarm.evolution_safety import EVOLUTION_MARKER, is_scratch_worktree

    scratch_root = lexical_path(os.environ["DHARMA_EVOLUTION_WORKTREE_ROOT"])
    resolved = lexical_path(repo)
    expected = scratch_root / experiment_id / "repo"
    if resolved != expected or not lexists(resolved):
        raise UnattendedError("SCRATCH_REMOVE_REFUSED", str(resolved))
    try:
        root_mode = scratch_root.lstat().st_mode
        repo_mode = resolved.lstat().st_mode
    except OSError as exc:
        raise UnattendedError("SCRATCH_REMOVE_REFUSED", str(resolved)) from exc
    ok, _payload, _reason = is_scratch_worktree(resolved)
    if (
        stat.S_ISLNK(root_mode)
        or not stat.S_ISDIR(root_mode)
        or stat.S_ISLNK(repo_mode)
        or not stat.S_ISDIR(repo_mode)
        or scratch_root not in resolved.parents
        or not ok
        or not (resolved / EVOLUTION_MARKER).is_file()
    ):
        raise UnattendedError("SCRATCH_REMOVE_REFUSED", str(resolved))
    shutil.rmtree(resolved.parent)
    if lexists(resolved.parent):
        raise UnattendedError("SCRATCH_REMOVE_UNCONFIRMED", str(resolved.parent))


def child_scratch_identity() -> dict[str, int]:
    try:
        device_text = os.environ["RSI_LAB_UNATTENDED_SCRATCH_DEVICE"]
        inode_text = os.environ["RSI_LAB_UNATTENDED_SCRATCH_INODE"]
        if not device_text.isdigit() or not inode_text.isdigit():
            raise ValueError("scratch identity is not decimal")
        identity = {"device": int(device_text), "inode": int(inode_text)}
    except (KeyError, ValueError) as exc:
        raise UnattendedError(
            "CHILD_SCRATCH_IDENTITY",
            "parent-created scratch identity is absent or malformed",
        ) from exc
    if identity["device"] < 0 or identity["inode"] <= 0:
        raise UnattendedError(
            "CHILD_SCRATCH_IDENTITY",
            "parent-created scratch identity is outside its valid range",
        )
    return identity


def child_scratch_marker_digest() -> str:
    try:
        return os.environ["RSI_LAB_UNATTENDED_SCRATCH_MARKER_DIGEST"]
    except KeyError as exc:
        raise UnattendedError(
            "CHILD_SCRATCH_MARKER_DIGEST",
            "parent-created scratch marker digest is absent",
        ) from exc


def redact_secret_values(payload: Any) -> Any:
    """Keep provider credential values out of child evidence recursively."""

    from dharma_swarm.api_keys import ALL_API_KEY_ENV_KEYS

    secrets = {
        value
        for name in ALL_API_KEY_ENV_KEYS
        if len(value := os.environ.get(name, "")) >= 8
    }
    if isinstance(payload, str):
        redacted = payload
        for secret in secrets:
            redacted = redacted.replace(secret, "[REDACTED_PROVIDER_CREDENTIAL]")
        return redacted
    if isinstance(payload, list):
        return [redact_secret_values(value) for value in payload]
    if isinstance(payload, tuple):
        return tuple(redact_secret_values(value) for value in payload)
    if isinstance(payload, dict):
        return {key: redact_secret_values(value) for key, value in payload.items()}
    return payload
