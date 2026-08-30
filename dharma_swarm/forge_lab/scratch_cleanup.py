"""Bounded inventory and removal of unattended scratch run directories.

Split out of ``unattended_scratch`` to keep both modules under the repo's
500-line budget (CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5). The parent
module re-exports every name defined here.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.state_io import validate_safe_id
from dharma_swarm.forge_lab.unattended_scratch_evidence import (
    exact_root_identity as _exact_root_identity,
    run_root,
)
from dharma_swarm.forge_lab.scratch_markers import (
    SCRATCH_MARKER,
    _DIGEST_RE,
    _directory_flags,
    _error,
    _lock_run_root,
    _open_run,
    _proof,
    _read_marker,
    _root_identity,
    _validated_inputs,
    _write_marker,
)

MAX_INVENTORY_ENTRIES = 200_000
MAX_INVENTORY_DEPTH = 64

def _inventory_run(
    run_fd: int,
    *,
    run_id: str,
    expected_device: int,
) -> dict[str, Any]:
    names = sorted(os.listdir(run_fd))
    non_marker = [name for name in names if name != SCRATCH_MARKER]
    if SCRATCH_MARKER not in names or len(non_marker) > 1:
        raise OSError("run root has an unexpected entry shape")
    if non_marker:
        try:
            validate_safe_id(non_marker[0], field="experiment_id")
        except ValueError as exc:
            raise OSError("experiment directory name is unsafe") from exc
    digest = hashlib.sha256()
    counts = {
        "entries": 0,
        "directories": 0,
        "regular_files": 0,
        "symlinks": 0,
        "bytes": 0,
    }

    def record(relative: str, metadata: os.stat_result, kind: str) -> None:
        counts["entries"] += 1
        if counts["entries"] > MAX_INVENTORY_ENTRIES:
            raise OSError("scratch inventory exceeds entry limit")
        if kind == "directory":
            counts["directories"] += 1
        elif kind == "symlink":
            counts["symlinks"] += 1
            counts["bytes"] += metadata.st_size
        else:
            counts["regular_files"] += 1
            counts["bytes"] += metadata.st_size
        row = [relative, kind, stat.S_IMODE(metadata.st_mode), metadata.st_size]
        digest.update(json.dumps(row, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")

    def walk(directory_fd: int, prefix: str, depth: int) -> None:
        if depth > MAX_INVENTORY_DEPTH:
            raise OSError("scratch inventory exceeds depth limit")
        for name in sorted(os.listdir(directory_fd)):
            metadata = os.stat(
                name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
            if metadata.st_dev != expected_device or metadata.st_uid != os.geteuid():
                raise OSError("scratch entry crosses filesystem or owner custody")
            relative = f"{prefix}/{name}" if prefix else name
            if stat.S_ISLNK(metadata.st_mode):
                # Git mode-120000 entries are ordinary repository content.
                # Record only link metadata; never open or follow the target.
                record(relative, metadata, "symlink")
            elif stat.S_ISDIR(metadata.st_mode):
                record(relative, metadata, "directory")
                child_fd = os.open(name, _directory_flags(), dir_fd=directory_fd)
                try:
                    opened = os.fstat(child_fd)
                    if (opened.st_dev, opened.st_ino) != (
                        metadata.st_dev,
                        metadata.st_ino,
                    ):
                        raise OSError("scratch directory changed during inventory")
                    walk(child_fd, relative, depth + 1)
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(metadata.st_mode):
                record(relative, metadata, "regular_file")
            else:
                raise OSError("scratch inventory contains a special file")

    walk(run_fd, "", 0)
    if non_marker:
        experiment = non_marker[0]
        experiment_fd = os.open(experiment, _directory_flags(), dir_fd=run_fd)
        try:
            if set(os.listdir(experiment_fd)) - {"repo"}:
                raise OSError("experiment root has an unexpected entry")
            if "repo" in os.listdir(experiment_fd):
                repo = os.stat("repo", dir_fd=experiment_fd, follow_symlinks=False)
                if not stat.S_ISDIR(repo.st_mode):
                    raise OSError("experiment repo entry is not a real directory")
        finally:
            os.close(experiment_fd)
    return {
        **counts,
        "inventory_digest": "sha256:" + digest.hexdigest(),
        "run_id": run_id,
    }


def _remove_tree_fd(
    directory_fd: int,
    *,
    expected_device: int,
    custody_marker: str | None = None,
) -> None:
    """Remove contents relative to an already-open, no-follow directory."""

    names = sorted(
        os.listdir(directory_fd),
        key=lambda name: (name == custody_marker, name),
    )
    for name in names:
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if metadata.st_dev != expected_device or metadata.st_uid != os.geteuid():
            raise OSError("scratch deletion refused a foreign-owner entry")
        if stat.S_ISLNK(metadata.st_mode):
            # unlink(2) removes the directory entry itself and never follows
            # the target, including for dangling and absolute links.
            os.unlink(name, dir_fd=directory_fd)
        elif stat.S_ISDIR(metadata.st_mode):
            child_fd = os.open(name, _directory_flags(), dir_fd=directory_fd)
            try:
                opened = os.fstat(child_fd)
                if (opened.st_dev, opened.st_ino) != (
                    metadata.st_dev,
                    metadata.st_ino,
                ):
                    raise OSError("scratch directory changed during deletion")
                _remove_tree_fd(child_fd, expected_device=expected_device)
            finally:
                os.close(child_fd)
            os.rmdir(name, dir_fd=directory_fd)
        elif stat.S_ISREG(metadata.st_mode):
            os.unlink(name, dir_fd=directory_fd)
        else:
            raise OSError("scratch deletion refused a special entry")


def cleanup_run_scratch(
    state_root: Path,
    run_id: str,
    *,
    source_commit: str,
    spec_digest: str,
    expected_root_identity: dict[str, int],
    expected_marker_digest: str,
) -> dict[str, Any]:
    """Attest, inventory, and remove the exact parent-owned run root."""

    state_root, run_id = _validated_inputs(
        state_root, run_id, source_commit, spec_digest
    )
    scratch_root = run_root(state_root, run_id)
    if not _exact_root_identity(expected_root_identity):
        raise _error(
            "SCRATCH_IDENTITY_REQUIRED",
            "exact parent-created root identity is required",
            operation="cleanup",
            scratch_root=scratch_root,
            run_id=run_id,
        )
    if (
        not isinstance(expected_marker_digest, str)
        or not _DIGEST_RE.fullmatch(expected_marker_digest)
    ):
        raise _error(
            "SCRATCH_MARKER_DIGEST_REQUIRED",
            "exact parent-created marker digest is required",
            operation="cleanup",
            scratch_root=scratch_root,
            run_id=run_id,
            root_identity=expected_root_identity,
        )
    parent_fd, run_fd, opened = _open_run(
        state_root, run_id, operation="cleanup"
    )
    locked = False
    marker_digest: str | None = None
    inventory: dict[str, Any] | None = None
    try:
        _lock_run_root(
            run_fd,
            scratch_root=scratch_root,
            run_id=run_id,
            operation="cleanup",
            root_identity=_root_identity(opened),
        )
        locked = True
        marker = _read_marker(
            run_fd,
            root_metadata=opened,
            expected_root_identity=expected_root_identity,
            expected_marker_digest=expected_marker_digest,
            scratch_root=scratch_root,
            run_id=run_id,
            source_commit=source_commit,
            spec_digest=spec_digest,
            operation="cleanup",
        )
        marker_digest = marker["marker_digest"]
        try:
            inventory = _inventory_run(
                run_fd,
                run_id=run_id,
                expected_device=opened.st_dev,
            )
            _remove_tree_fd(
                run_fd,
                expected_device=opened.st_dev,
                custody_marker=SCRATCH_MARKER,
            )
            current = os.stat(run_id, dir_fd=parent_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                raise OSError("run scratch root changed before final removal")
            try:
                os.rmdir(run_id, dir_fd=parent_fd)
            except OSError as remove_exc:
                try:
                    _write_marker(run_fd, marker)
                    os.fsync(run_fd)
                except Exception as restore_exc:
                    raise OSError(
                        "final run-root removal failed and marker restoration "
                        f"was unconfirmed ({type(restore_exc).__name__})"
                    ) from remove_exc
                raise OSError(
                    "final run-root removal failed; custody marker was restored"
                ) from remove_exc
            os.fsync(parent_fd)
            try:
                os.stat(run_id, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise OSError("run scratch root removal was not confirmed")
        except OSError as exc:
            raise _error(
                "SCRATCH_CLEANUP_REFUSED",
                f"parent scratch cleanup refused: {exc}",
                operation="cleanup",
                scratch_root=scratch_root,
                run_id=run_id,
                root_identity=_root_identity(opened),
                marker_digest=marker_digest,
                inventory=inventory,
            ) from exc
        return _proof(
            operation="cleanup",
            ok=True,
            scratch_root=scratch_root,
            run_id=run_id,
            root_identity=_root_identity(opened),
            marker_digest=marker_digest,
            inventory=inventory,
        )
    finally:
        if locked:
            fcntl.flock(run_fd, fcntl.LOCK_UN)
        os.close(run_fd)
        os.close(parent_fd)
