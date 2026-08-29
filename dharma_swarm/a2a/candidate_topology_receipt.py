"""Private, crash-reconcilable journal for candidate topology provisioning."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from fcntl import LOCK_EX, LOCK_UN, flock
from pathlib import Path
from typing import Any, Mapping

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256

TOPOLOGY_OPERATION_SCHEMA = "forge_lab.nats_topology_operation.v1"
_FIELDS = {
    "schema",
    "operation_id",
    "endpoint",
    "topology_sha256",
    "provisioner_public_nkey",
    "nkey_identity_proof_sha256",
    "pre_state",
    "created_resources",
    "removed_resources",
    "state",
    "events",
    "live_promotion_attempted",
    "snapshot_sha256",
}


class TopologyReceiptError(RuntimeError):
    """The operation journal is unsafe, corrupted, or for another operation."""


class TopologyOperationLock:
    """Process-wide lease over one durable topology operation journal.

    The lock inode is deliberately retained.  Unlinking a lock file after use
    permits a second process to lock a replacement inode while the first still
    holds the old one.  Callers performing broker mutations must hold this lock
    across inspection, mutation, reconciliation, and every journal write.
    """

    def __init__(self, receipt_path: Path | str) -> None:
        self.receipt_path = Path(receipt_path)
        self.path = self.receipt_path.with_name(f".{self.receipt_path.name}.lock")
        self.descriptor: int | None = None

    def acquire(self) -> "TopologyOperationLock":
        if self.descriptor is not None:
            raise TopologyReceiptError("topology operation lock is already held")
        _safe_path(
            self.receipt_path,
            existing=self.receipt_path.exists() or self.receipt_path.is_symlink(),
        )
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        descriptor: int | None = None
        try:
            descriptor = os.open(self.path, flags, 0o600)
            metadata = os.fstat(descriptor)
            link_metadata = self.path.lstat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != 0
                or metadata.st_nlink != 1
                or metadata.st_mode & 0o077
                or (metadata.st_dev, metadata.st_ino)
                != (link_metadata.st_dev, link_metadata.st_ino)
            ):
                raise TopologyReceiptError(
                    "topology operation lock must be a root-owned private regular file"
                )
            flock(descriptor, LOCK_EX)
        except (OSError, TopologyReceiptError) as exc:
            if descriptor is not None:
                os.close(descriptor)
            if isinstance(exc, TopologyReceiptError):
                raise
            raise TopologyReceiptError("topology operation lock acquisition failed") from exc
        self.descriptor = descriptor
        return self

    def release(self) -> None:
        descriptor, self.descriptor = self.descriptor, None
        if descriptor is None:
            return
        try:
            flock(descriptor, LOCK_UN)
        finally:
            os.close(descriptor)

    def assert_for(self, receipt_path: Path | str) -> None:
        if self.descriptor is None or Path(receipt_path) != self.receipt_path:
            raise TopologyReceiptError("topology operation lock does not bind this receipt")

    def __enter__(self) -> "TopologyOperationLock":
        return self.acquire()

    def __exit__(self, *_: object) -> None:
        self.release()


def _safe_path(path: Path, *, existing: bool) -> None:
    parent = path.parent
    try:
        parent_meta = parent.lstat()
    except OSError as exc:
        raise TopologyReceiptError("topology receipt parent is unavailable") from exc
    if (
        stat.S_ISLNK(parent_meta.st_mode)
        or not stat.S_ISDIR(parent_meta.st_mode)
        or parent_meta.st_uid != 0
        or parent_meta.st_mode & 0o022
    ):
        raise TopologyReceiptError("topology receipt parent must be a safe root-owned directory")
    if not existing:
        return
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise TopologyReceiptError("topology receipt is unavailable") from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != 0
        or metadata.st_nlink != 1
        or metadata.st_mode & 0o077
    ):
        raise TopologyReceiptError("topology receipt must be a root-owned private regular file")


def _snapshot(body: Mapping[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in body.items() if key != "snapshot_sha256"})


def read_topology_receipt(
    path: Path | str,
    *,
    operation_lock: TopologyOperationLock | None = None,
) -> dict[str, Any]:
    target = Path(path)
    if operation_lock is not None:
        operation_lock.assert_for(target)
    _safe_path(target, existing=True)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TopologyReceiptError("topology receipt is not valid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise TopologyReceiptError("topology receipt fields are invalid")
    if payload.get("schema") != TOPOLOGY_OPERATION_SCHEMA:
        raise TopologyReceiptError("topology receipt schema is invalid")
    if payload.get("snapshot_sha256") != _snapshot(payload):
        raise TopologyReceiptError("topology receipt content hash is invalid")
    if not isinstance(payload.get("pre_state"), dict) or not isinstance(payload.get("events"), list):
        raise TopologyReceiptError("topology receipt state is invalid")
    return payload


def write_topology_receipt(
    path: Path | str,
    payload: Mapping[str, Any],
    *,
    operation_lock: TopologyOperationLock | None = None,
) -> dict[str, Any]:
    """Atomically replace one journal snapshot while retaining its event history."""

    target = Path(path)
    if operation_lock is None:
        raise TopologyReceiptError("topology receipt writes require an operation lock")
    operation_lock.assert_for(target)
    _safe_path(target, existing=target.exists() or target.is_symlink())
    body = dict(payload)
    body["snapshot_sha256"] = _snapshot(body)
    if set(body) != _FIELDS or body.get("schema") != TOPOLOGY_OPERATION_SCHEMA:
        raise TopologyReceiptError("topology receipt write fields are invalid")
    encoded = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode()
    # A process can be killed after creating a temporary.  A fresh unique name
    # makes that orphan inert on reconciliation instead of permanently blocking
    # the operation as a deterministic O_EXCL name would.
    temporary_name = ""
    descriptor: int | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.{body['operation_id']}.",
            suffix=".tmp",
            dir=target.parent,
        )
        os.fchmod(descriptor, 0o600)
        offset = 0
        while offset < len(encoded):
            offset += os.write(descriptor, encoded[offset:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary_name, target)
        os.chmod(target, 0o600, follow_symlinks=False)
        parent_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except OSError as exc:
        raise TopologyReceiptError("topology receipt atomic write failed") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            if temporary_name:
                Path(temporary_name).unlink()
        except FileNotFoundError:
            pass
    return body


__all__ = [
    "TOPOLOGY_OPERATION_SCHEMA",
    "TopologyOperationLock",
    "TopologyReceiptError",
    "read_topology_receipt",
    "write_topology_receipt",
]
