"""Tamper-evident receipt primitives for the bounded RSI supervisor.

The unattended control plane has several closure layers (run, budget, lease,
and safety).  Each layer owns its own receipt chain, while this module owns the
single byte-level chain format and validation implementation shared by them.
"""

from __future__ import annotations

import json
import fcntl
import math
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.state_io import (
    _fsync_directory,
    canonical_json,
    content_digest,
)


class UnattendedError(RuntimeError):
    """Typed fail-closed unattended-control refusal."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@contextmanager
def _append_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise UnattendedError("CHAIN_LOCK_UNSAFE", str(path)) from exc
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise UnattendedError("CHAIN_LOCK_UNSAFE", str(path))
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        _fsync_directory(path.parent)
        yield
    finally:
        os.close(descriptor)


def _chain_digest(payload: dict[str, Any], digest_field: str) -> str:
    return content_digest({key: value for key, value in payload.items() if key != digest_field})


def _reject_nonfinite(value: Any, *, location: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise UnattendedError("CHAIN_NUMERIC_INVALID", location)
    if isinstance(value, dict):
        for key, nested in value.items():
            _reject_nonfinite(nested, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_nonfinite(nested, location=f"{location}[{index}]")


def read_chain(
    path: Path,
    *,
    schema: str,
    digest_field: str,
) -> list[dict[str, Any]]:
    """Read and verify one owner-only, newline-terminated JSONL hash chain."""

    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file():
        raise UnattendedError("CHAIN_PATH_UNSAFE", f"unsafe chain path: {path}")
    if path.stat().st_mode & 0o077:
        raise UnattendedError("CHAIN_MODE_UNSAFE", f"chain must be owner-only: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise UnattendedError("CHAIN_UNREADABLE", f"cannot read {path}: {exc}") from exc
    if len(raw) > 16 * 1024 * 1024:
        raise UnattendedError("CHAIN_TOO_LARGE", f"chain exceeds 16 MiB: {path}")
    if raw and not raw.endswith(b"\n"):
        raise UnattendedError("CHAIN_TRUNCATED", f"chain lacks final newline: {path}")
    rows: list[dict[str, Any]] = []
    previous: str | None = None
    for index, line in enumerate(raw.splitlines(), start=1):
        try:
            row = json.loads(line)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise UnattendedError(
                "CHAIN_MALFORMED", f"invalid JSON at {path}:{index}"
            ) from exc
        if not isinstance(row, dict):
            raise UnattendedError("CHAIN_MALFORMED", f"non-object at {path}:{index}")
        _reject_nonfinite(row, location=f"{path}:{index}")
        if (
            row.get("schema") != schema
            or type(row.get("sequence")) is not int
            or row.get("sequence") != index
        ):
            raise UnattendedError("CHAIN_SEQUENCE", f"schema/sequence mismatch at {path}:{index}")
        if row.get("previous_digest") != previous:
            raise UnattendedError("CHAIN_PREVIOUS", f"previous digest mismatch at {path}:{index}")
        if row.get(digest_field) != _chain_digest(row, digest_field):
            raise UnattendedError("CHAIN_DIGEST", f"digest mismatch at {path}:{index}")
        previous = str(row[digest_field])
        rows.append(row)
    return rows


def append_chain(
    path: Path,
    payload: dict[str, Any],
    *,
    schema: str,
    digest_field: str,
) -> dict[str, Any]:
    """Verify and fsync one append-only chain row."""

    lock_path = path.with_name(f".{path.name}.append.lock")
    with _append_lock(lock_path):
        rows = read_chain(path, schema=schema, digest_field=digest_field)
        return _append_chain_locked(
            path,
            payload,
            rows=rows,
            schema=schema,
            digest_field=digest_field,
        )


def _append_chain_locked(
    path: Path,
    payload: dict[str, Any],
    *,
    rows: list[dict[str, Any]],
    schema: str,
    digest_field: str,
) -> dict[str, Any]:
    """Append under the chain's already-held transaction lock."""

    row = {
        **payload,
        "schema": schema,
        "sequence": len(rows) + 1,
        "previous_digest": rows[-1][digest_field] if rows else None,
    }
    row[digest_field] = _chain_digest(row, digest_field)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "ab", closefd=True) as handle:
        handle.write(canonical_json(row) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(path.parent)
    return row


@contextmanager
def chain_transaction(
    path: Path,
    *,
    schema: str,
    digest_field: str,
):
    """Hold one stable lock across validation, policy checks, and append."""

    lock_path = path.with_name(f".{path.name}.append.lock")
    with _append_lock(lock_path):
        yield read_chain(path, schema=schema, digest_field=digest_field)


__all__ = [
    "UnattendedError",
    "_append_chain_locked",
    "_chain_digest",
    "append_chain",
    "chain_transaction",
    "read_chain",
]
