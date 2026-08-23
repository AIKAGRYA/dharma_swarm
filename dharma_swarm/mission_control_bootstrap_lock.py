"""Canonical cross-process lock capability for SADHANA bootstrap owners."""

from __future__ import annotations

import asyncio
import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

BOOTSTRAP_LOCK_NAME = "sadhana-bootstrap.lock"
_LOCK_CONSTRUCTION_SENTINEL = object()


class BootstrapLockError(RuntimeError):
    """Raised when the mandatory campaign bootstrap lock is invalid or busy."""


class CampaignBootstrapLock:
    """Opaque proof that the canonical cross-process bootstrap lock is held."""

    __slots__ = ("_active", "_async_lock", "_descriptor", "path")

    def __init__(self, path: Path, descriptor: int, sentinel: object) -> None:
        if sentinel is not _LOCK_CONSTRUCTION_SENTINEL:
            raise BootstrapLockError(
                "CampaignBootstrapLock can only be created by campaign_bootstrap_lock"
            )
        self.path = path
        self._descriptor = descriptor
        self._active = True
        self._async_lock = asyncio.Lock()

    def _require_active(self, expected_path: Path) -> None:
        if not self._active or self.path != expected_path:
            raise BootstrapLockError(
                "initializer requires the active canonical campaign bootstrap lock"
            )
        details = os.fstat(self._descriptor)
        observed = os.lstat(self.path)
        if (details.st_dev, details.st_ino) != (observed.st_dev, observed.st_ino):
            raise BootstrapLockError("campaign bootstrap lock identity changed")


def absolute_lexical_path(path: Path | str) -> Path:
    """Normalize lexically without following the final path component."""
    return Path(os.path.abspath(os.fspath(Path(path).expanduser())))


def _require_safe_lock_file(descriptor: int) -> None:
    details = os.fstat(descriptor)
    if not stat.S_ISREG(details.st_mode):
        raise BootstrapLockError("bootstrap lock must be a regular file")
    if details.st_nlink != 1:
        raise BootstrapLockError("bootstrap lock must have exactly one hard link")
    if hasattr(os, "getuid") and details.st_uid != os.getuid():
        raise BootstrapLockError("bootstrap lock must be owned by the current account")
    if stat.S_IMODE(details.st_mode) & 0o022:
        raise BootstrapLockError("bootstrap lock must not be group/world writable")


@contextmanager
def campaign_bootstrap_lock(path: Path | str) -> Iterator[CampaignBootstrapLock]:
    """Acquire the mandatory canonical lock used by every bootstrap API call."""
    candidate = absolute_lexical_path(path)
    candidate.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise BootstrapLockError("bootstrap lock requires O_NOFOLLOW support")
    flags = os.O_CREAT | os.O_RDWR | nofollow | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(os.fspath(candidate), flags, 0o600)
    except OSError as exc:
        raise BootstrapLockError(f"cannot securely open bootstrap lock: {exc}") from exc
    acquired = False
    token: CampaignBootstrapLock | None = None
    try:
        _require_safe_lock_file(descriptor)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BootstrapLockError("another SADHANA bootstrap is active") from exc
        acquired = True
        token = CampaignBootstrapLock(
            candidate,
            descriptor,
            _LOCK_CONSTRUCTION_SENTINEL,
        )
        yield token
    finally:
        if token is not None:
            token._active = False
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


__all__ = [
    "BOOTSTRAP_LOCK_NAME",
    "BootstrapLockError",
    "CampaignBootstrapLock",
    "absolute_lexical_path",
    "campaign_bootstrap_lock",
]
