"""Parent-owned scratch custody for one unattended EXPLORE run.

The child may be killed without running Python cleanup.  This module therefore
gives the parent an exact, marker-bound run directory and removes it through
directory file descriptors without following symlinks.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.state_io import content_digest, validate_safe_id
from dharma_swarm.forge_lab.unattended_scratch_evidence import (
    SCRATCH_PROOF_SCHEMA,
    exact_root_identity as _exact_root_identity,
    run_root,
    validate_parent_scratch_proofs,
    validate_scratch_proof,
)

SCRATCH_MARKER_SCHEMA = "rsi_lab.unattended_scratch_marker.v1"
SCRATCH_MARKER = ".rsi_unattended_scratch.json"
MAX_MARKER_BYTES = 64 * 1024
MAX_INVENTORY_ENTRIES = 200_000
MAX_INVENTORY_DEPTH = 64

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ScratchCustodyError(RuntimeError):
    """Typed refusal carrying JSON-safe failure evidence."""

    def __init__(self, code: str, message: str, proof: dict[str, Any]) -> None:
        super().__init__(message)
        self.code = code
        self.proof = proof


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


def _proof(
    *,
    operation: str,
    ok: bool,
    scratch_root: Path,
    run_id: str,
    root_identity: dict[str, int] | None = None,
    marker_digest: str | None = None,
    inventory: dict[str, Any] | None = None,
    code: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": SCRATCH_PROOF_SCHEMA,
        "operation": operation,
        "ok": ok,
        "scratch_root": str(scratch_root),
        "run_id": run_id,
        "root_identity": root_identity,
        "marker_digest": marker_digest,
        "inventory": inventory,
        "code": code,
        "message": message,
    }
    payload["proof_digest"] = content_digest(payload)
    return payload


def _error(
    code: str,
    message: str,
    *,
    operation: str,
    scratch_root: Path,
    run_id: str,
    marker_digest: str | None = None,
    inventory: dict[str, Any] | None = None,
    root_identity: dict[str, int] | None = None,
) -> ScratchCustodyError:
    return ScratchCustodyError(
        code,
        message,
        _proof(
            operation=operation,
            ok=False,
            scratch_root=scratch_root,
            run_id=run_id,
            root_identity=root_identity,
            marker_digest=marker_digest,
            inventory=inventory,
            code=code,
            message=message,
        ),
    )


def _root_identity(metadata: os.stat_result) -> dict[str, int]:
    return {"device": int(metadata.st_dev), "inode": int(metadata.st_ino)}


def _owned_real_directory(metadata: os.stat_result) -> bool:
    return bool(
        stat.S_ISDIR(metadata.st_mode)
        and metadata.st_uid == os.geteuid()
        and stat.S_IMODE(metadata.st_mode) & 0o022 == 0
    )


def _validated_state_root(state_root: Path) -> Path:
    raw_state = state_root.expanduser()
    if not raw_state.is_absolute() or raw_state == Path("/"):
        raise ValueError("state_root must be an absolute non-root path")
    try:
        metadata = raw_state.lstat()
        resolved = raw_state.resolve(strict=True)
    except OSError as exc:
        raise ValueError("state_root must be an existing real directory") from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not _owned_real_directory(metadata)
        or resolved != raw_state
    ):
        raise ValueError("state_root must be a canonical real directory")
    return resolved


def _validated_inputs(
    state_root: Path,
    run_id: str,
    source_commit: str,
    spec_digest: str,
) -> tuple[Path, str]:
    try:
        safe_run_id = validate_safe_id(run_id, field="run_id")
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    resolved = _validated_state_root(state_root)
    if not _COMMIT_RE.fullmatch(source_commit):
        raise ValueError("source_commit must be one lowercase 40-hex commit")
    if not _DIGEST_RE.fullmatch(spec_digest):
        raise ValueError("spec_digest must be one sha256 digest")
    return resolved, safe_run_id


def _directory_flags() -> int:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    return flags


def _open_parent(state_root: Path, *, create: bool) -> int:
    current = os.open(state_root, _directory_flags())
    try:
        if not _owned_real_directory(os.fstat(current)):
            raise OSError("state root is not owner-only writable")
        for component in (".dharma", "evolution_worktrees", "unattended"):
            if create:
                try:
                    os.mkdir(component, mode=0o700, dir_fd=current)
                except FileExistsError:
                    pass
            next_fd = os.open(component, _directory_flags(), dir_fd=current)
            metadata = os.fstat(next_fd)
            if not _owned_real_directory(metadata):
                os.close(next_fd)
                raise OSError(
                    f"scratch ancestor is not owner-only writable: {component}"
                )
            os.close(current)
            current = next_fd
        return current
    except Exception:
        os.close(current)
        raise


def list_run_scratch_ids(state_root: Path) -> list[str]:
    """List exact prior run roots without following or adopting unknown paths."""

    state_root = _validated_state_root(state_root)
    base = state_root / ".dharma" / "evolution_worktrees" / "unattended"
    if not os.path.lexists(base):
        return []
    try:
        parent_fd = _open_parent(state_root, create=False)
    except OSError as exc:
        raise _error(
            "SCRATCH_AUDIT_REFUSED",
            "unattended scratch parent is not safely owned",
            operation="audit",
            scratch_root=base,
            run_id="scratch-audit",
        ) from exc
    try:
        run_ids: list[str] = []
        for name in sorted(os.listdir(parent_fd)):
            try:
                validate_safe_id(name, field="run_id")
                metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except (OSError, ValueError) as exc:
                raise _error(
                    "SCRATCH_AUDIT_REFUSED",
                    "unattended scratch contains an unknown entry",
                    operation="audit",
                    scratch_root=base,
                    run_id="scratch-audit",
                ) from exc
            if (
                not _owned_real_directory(metadata)
                or stat.S_IMODE(metadata.st_mode) != 0o700
            ):
                raise _error(
                    "SCRATCH_AUDIT_REFUSED",
                    "unattended scratch run root has unsafe ownership or mode",
                    operation="audit",
                    scratch_root=base,
                    run_id=name,
                    root_identity=_root_identity(metadata),
                )
            run_ids.append(name)
        return run_ids
    finally:
        os.close(parent_fd)


def _write_marker(run_fd: int, marker: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(SCRATCH_MARKER, flags, 0o600, dir_fd=run_fd)
    try:
        encoded = json.dumps(
            marker,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8") + b"\n"
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short marker write")
            view = view[written:]
        os.fsync(descriptor)
    except Exception:
        try:
            os.unlink(SCRATCH_MARKER, dir_fd=run_fd)
        except OSError:
            pass
        raise
    finally:
        os.close(descriptor)


def _read_marker(
    run_fd: int,
    *,
    root_metadata: os.stat_result,
    expected_root_identity: dict[str, int] | None,
    expected_marker_digest: str | None,
    scratch_root: Path,
    run_id: str,
    source_commit: str,
    spec_digest: str,
    operation: str,
    descriptor: int | None = None,
) -> dict[str, Any]:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    owns_descriptor = descriptor is None
    if descriptor is None:
        try:
            descriptor = os.open(SCRATCH_MARKER, flags, dir_fd=run_fd)
        except OSError as exc:
            raise _error(
                "SCRATCH_MARKER_MISSING",
                "scratch custody marker is missing or unsafe",
                operation=operation,
                scratch_root=scratch_root,
                run_id=run_id,
            ) from exc
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_size > MAX_MARKER_BYTES
        ):
            raise _error(
                "SCRATCH_MARKER_UNSAFE",
                "scratch custody marker type, mode, or size is invalid",
                operation=operation,
                scratch_root=scratch_root,
                run_id=run_id,
            )
        raw = b""
        while len(raw) <= MAX_MARKER_BYTES:
            chunk = os.read(descriptor, min(8192, MAX_MARKER_BYTES + 1 - len(raw)))
            if not chunk:
                break
            raw += chunk
        if len(raw) > MAX_MARKER_BYTES:
            raise ValueError("marker exceeds size limit")
        payload = json.loads(raw.decode("utf-8"))
    except ScratchCustodyError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise _error(
            "SCRATCH_MARKER_INVALID",
            "scratch custody marker is not valid bounded JSON",
            operation=operation,
            scratch_root=scratch_root,
            run_id=run_id,
        ) from exc
    finally:
        if owns_descriptor:
            os.close(descriptor)
    if not isinstance(payload, dict):
        raise _error(
            "SCRATCH_MARKER_INVALID",
            "scratch custody marker must be a JSON object",
            operation=operation,
            scratch_root=scratch_root,
            run_id=run_id,
        )
    expected_keys = {
        "schema",
        "run_id",
        "source_commit",
        "spec_digest",
        "scratch_root",
        "created_at",
        "root_identity",
        "marker_digest",
    }
    actual_root_identity = _root_identity(root_metadata)
    unsigned = {key: value for key, value in payload.items() if key != "marker_digest"}
    if (
        set(payload) != expected_keys
        or payload.get("schema") != SCRATCH_MARKER_SCHEMA
        or payload.get("run_id") != run_id
        or payload.get("source_commit") != source_commit
        or payload.get("spec_digest") != spec_digest
        or payload.get("scratch_root") != str(scratch_root)
        or not _exact_root_identity(payload.get("root_identity"))
        or payload.get("root_identity") != actual_root_identity
        or (
            expected_root_identity is not None
            and payload.get("root_identity") != expected_root_identity
        )
        or not isinstance(payload.get("created_at"), str)
        or not payload.get("created_at")
        or payload.get("marker_digest") != content_digest(unsigned)
        or (
            expected_marker_digest is not None
            and payload.get("marker_digest") != expected_marker_digest
        )
    ):
        raise _error(
            "SCRATCH_MARKER_MISMATCH",
            "scratch custody marker does not match the admitted run",
            operation=operation,
            scratch_root=scratch_root,
            run_id=run_id,
            root_identity=actual_root_identity,
        )
    return payload


def _lock_run_root(
    run_fd: int,
    *,
    scratch_root: Path,
    run_id: str,
    operation: str,
    root_identity: dict[str, int],
) -> None:
    try:
        fcntl.flock(run_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise _error(
            "SCRATCH_ROOT_BUSY",
            "run scratch root is held by a live child",
            operation=operation,
            scratch_root=scratch_root,
            run_id=run_id,
            root_identity=root_identity,
        ) from exc
    except OSError as exc:
        raise _error(
            "SCRATCH_MARKER_MISSING",
            "run scratch root cannot be locked safely",
            operation=operation,
            scratch_root=scratch_root,
            run_id=run_id,
            root_identity=root_identity,
        ) from exc


def _open_run(
    state_root: Path,
    run_id: str,
    *,
    operation: str,
) -> tuple[int, int, os.stat_result]:
    scratch_root = run_root(state_root, run_id)
    try:
        parent_fd = _open_parent(state_root, create=False)
        try:
            run_fd = os.open(run_id, _directory_flags(), dir_fd=parent_fd)
        except Exception:
            os.close(parent_fd)
            raise
        metadata = os.fstat(run_fd)
        if (
            not _owned_real_directory(metadata)
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            os.close(run_fd)
            os.close(parent_fd)
            raise OSError("run scratch root has invalid type or mode")
        return parent_fd, run_fd, metadata
    except OSError as exc:
        raise _error(
            "SCRATCH_ROOT_UNSAFE",
            "run scratch root is missing, linked, or has invalid custody",
            operation=operation,
            scratch_root=scratch_root,
            run_id=run_id,
        ) from exc


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
