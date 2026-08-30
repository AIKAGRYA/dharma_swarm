"""Marker-bound run-directory custody primitives for unattended EXPLORE.

Split out of ``unattended_scratch`` to keep both modules under the repo's
500-line budget (CLAUDE.md law; SOVEREIGN_MANIFEST axiom A5). The parent
module re-exports every name defined here; ``scratch_cleanup`` builds on
these primitives. Lowest layer — import nothing from the parent.
"""

from __future__ import annotations

import fcntl
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
)


SCRATCH_MARKER_SCHEMA = "rsi_lab.unattended_scratch_marker.v1"
SCRATCH_MARKER = ".rsi_unattended_scratch.json"
MAX_MARKER_BYTES = 64 * 1024

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ScratchCustodyError(RuntimeError):
    """Typed refusal carrying JSON-safe failure evidence."""

    def __init__(self, code: str, message: str, proof: dict[str, Any]) -> None:
        super().__init__(message)
        self.code = code
        self.proof = proof


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
