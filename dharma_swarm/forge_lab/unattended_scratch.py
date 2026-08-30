"""Parent-owned scratch custody for one unattended EXPLORE run.

The child may be killed without running Python cleanup.  This module therefore
gives the parent an exact, marker-bound run directory and removes it through
directory file descriptors without following symlinks.
"""

from __future__ import annotations

import fcntl
import os
import stat
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.scratch_cleanup import (
    _remove_tree_fd,
    cleanup_run_scratch,
)
from dharma_swarm.forge_lab.scratch_markers import (
    SCRATCH_MARKER as SCRATCH_MARKER,
    SCRATCH_MARKER_SCHEMA as SCRATCH_MARKER_SCHEMA,
    ScratchCustodyError,
    _DIGEST_RE,
    _directory_flags,
    _error,
    _lock_run_root,
    _open_parent,
    _open_run,
    _owned_real_directory,
    _proof,
    _read_marker,
    _root_identity,
    _validated_inputs,
    _write_marker,
    list_run_scratch_ids,
)
from dharma_swarm.forge_lab.state_io import content_digest
from dharma_swarm.forge_lab.unattended_scratch_evidence import (
    SCRATCH_PROOF_SCHEMA as SCRATCH_PROOF_SCHEMA,
    exact_root_identity as _exact_root_identity,
    run_root,
    validate_parent_scratch_proofs,
    validate_scratch_proof,
)


class ScratchLease:
    """An exclusive marker lock held for the complete child lifetime."""

    def __init__(
        self,
        *,
        parent_fd: int,
        run_fd: int,
        proof: dict[str, Any],
    ) -> None:
        self._parent_fd = parent_fd
        self._run_fd = run_fd
        self.proof = proof
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            fcntl.flock(self._run_fd, fcntl.LOCK_UN)
        finally:
            os.close(self._run_fd)
            os.close(self._parent_fd)


def create_run_scratch(
    state_root: Path,
    run_id: str,
    *,
    source_commit: str,
    spec_digest: str,
    created_at: str,
) -> dict[str, Any]:
    """Exclusively create and seal one parent-owned run scratch root."""

    state_root, run_id = _validated_inputs(
        state_root, run_id, source_commit, spec_digest
    )
    scratch_root = run_root(state_root, run_id)
    parent_fd: int | None = None
    run_fd: int | None = None
    created = False
    try:
        parent_fd = _open_parent(state_root, create=True)
        os.mkdir(run_id, mode=0o700, dir_fd=parent_fd)
        created = True
        run_fd = os.open(run_id, _directory_flags(), dir_fd=parent_fd)
        os.fchmod(run_fd, 0o700)
        root_metadata = os.fstat(run_fd)
        root_identity = _root_identity(root_metadata)
        if (
            not _owned_real_directory(root_metadata)
            or stat.S_IMODE(root_metadata.st_mode) != 0o700
        ):
            raise OSError("created scratch root has invalid ownership or mode")
        marker = {
            "schema": SCRATCH_MARKER_SCHEMA,
            "run_id": run_id,
            "source_commit": source_commit,
            "spec_digest": spec_digest,
            "scratch_root": str(scratch_root),
            "created_at": created_at,
            "root_identity": root_identity,
        }
        marker["marker_digest"] = content_digest(marker)
        _write_marker(run_fd, marker)
        os.fsync(run_fd)
        os.fsync(parent_fd)
        return _proof(
            operation="create",
            ok=True,
            scratch_root=scratch_root,
            run_id=run_id,
            root_identity=root_identity,
            marker_digest=marker["marker_digest"],
        )
    except Exception as exc:
        cleanup_error: Exception | None = None
        if created and parent_fd is not None:
            try:
                if run_fd is not None:
                    _remove_tree_fd(
                        run_fd,
                        expected_device=os.fstat(run_fd).st_dev,
                        custody_marker=SCRATCH_MARKER,
                    )
                current = os.stat(run_id, dir_fd=parent_fd, follow_symlinks=False)
                if run_fd is not None:
                    opened = os.fstat(run_fd)
                    if (current.st_dev, current.st_ino) != (
                        opened.st_dev,
                        opened.st_ino,
                    ):
                        raise OSError("run scratch root changed during rollback")
                elif not stat.S_ISDIR(current.st_mode):
                    raise OSError("run scratch root changed type during rollback")
                os.rmdir(run_id, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except Exception as rollback_exc:
                cleanup_error = rollback_exc
        if isinstance(exc, ScratchCustodyError):
            raise
        code = (
            "SCRATCH_CREATE_ROLLBACK_FAILED"
            if cleanup_error is not None
            else "SCRATCH_CREATE_REFUSED"
        )
        message = (
            "scratch root creation failed and rollback was not confirmed"
            if cleanup_error is not None
            else "scratch root creation was refused before child launch"
        )
        raise _error(
            code,
            message,
            operation="create",
            scratch_root=scratch_root,
            run_id=run_id,
        ) from exc
    finally:
        if run_fd is not None:
            os.close(run_fd)
        if parent_fd is not None:
            os.close(parent_fd)


def attest_run_scratch(
    state_root: Path,
    run_id: str,
    *,
    source_commit: str,
    spec_digest: str,
    expected_root_identity: dict[str, int] | None = None,
    expected_marker_digest: str | None = None,
) -> dict[str, Any]:
    """Verify exact run-root and marker custody without changing it."""

    state_root, run_id = _validated_inputs(
        state_root, run_id, source_commit, spec_digest
    )
    scratch_root = run_root(state_root, run_id)
    parent_fd, run_fd, metadata = _open_run(
        state_root, run_id, operation="attest"
    )
    try:
        marker = _read_marker(
            run_fd,
            root_metadata=metadata,
            expected_root_identity=expected_root_identity,
            expected_marker_digest=expected_marker_digest,
            scratch_root=scratch_root,
            run_id=run_id,
            source_commit=source_commit,
            spec_digest=spec_digest,
            operation="attest",
        )
        return _proof(
            operation="attest",
            ok=True,
            scratch_root=scratch_root,
            run_id=run_id,
            root_identity=_root_identity(metadata),
            marker_digest=marker["marker_digest"],
        )
    finally:
        os.close(run_fd)
        os.close(parent_fd)


def acquire_run_scratch_lease(
    state_root: Path,
    run_id: str,
    *,
    source_commit: str,
    spec_digest: str,
    expected_root_identity: dict[str, int],
    expected_marker_digest: str,
) -> ScratchLease:
    """Attest and exclusively lock one run root for the child lifetime."""

    state_root, run_id = _validated_inputs(
        state_root, run_id, source_commit, spec_digest
    )
    scratch_root = run_root(state_root, run_id)
    if not _exact_root_identity(expected_root_identity):
        raise _error(
            "SCRATCH_IDENTITY_REQUIRED",
            "exact parent-created root identity is required",
            operation="attest",
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
            operation="attest",
            scratch_root=scratch_root,
            run_id=run_id,
            root_identity=expected_root_identity,
        )
    parent_fd, run_fd, metadata = _open_run(
        state_root, run_id, operation="attest"
    )
    locked = False
    try:
        _lock_run_root(
            run_fd,
            scratch_root=scratch_root,
            run_id=run_id,
            operation="attest",
            root_identity=_root_identity(metadata),
        )
        locked = True
        marker = _read_marker(
            run_fd,
            root_metadata=metadata,
            expected_root_identity=expected_root_identity,
            expected_marker_digest=expected_marker_digest,
            scratch_root=scratch_root,
            run_id=run_id,
            source_commit=source_commit,
            spec_digest=spec_digest,
            operation="attest",
        )
        proof = _proof(
            operation="attest",
            ok=True,
            scratch_root=scratch_root,
            run_id=run_id,
            root_identity=_root_identity(metadata),
            marker_digest=marker["marker_digest"],
        )
        return ScratchLease(
            parent_fd=parent_fd,
            run_fd=run_fd,
            proof=proof,
        )
    except Exception:
        if locked:
            fcntl.flock(run_fd, fcntl.LOCK_UN)
        os.close(run_fd)
        os.close(parent_fd)
        raise


__all__ = [
    "SCRATCH_MARKER",
    "SCRATCH_MARKER_SCHEMA",
    "SCRATCH_PROOF_SCHEMA",
    "ScratchCustodyError",
    "ScratchLease",
    "acquire_run_scratch_lease",
    "attest_run_scratch",
    "cleanup_run_scratch",
    "create_run_scratch",
    "list_run_scratch_ids",
    "run_root",
    "validate_parent_scratch_proofs",
    "validate_scratch_proof",
]
