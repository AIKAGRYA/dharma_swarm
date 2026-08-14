"""Thread- and process-safe lock for one graph persistence file."""

from __future__ import annotations

import errno
import fcntl
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_LOCKS: dict[Path, threading.RLock] = {}
_LEASE_LOCKS: dict[Path, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


class PersistenceFileBusy(RuntimeError):
    """A non-blocking persistence lease is already held."""


def _process_thread_lock(path: Path) -> threading.RLock:
    key = path.resolve()
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def _process_lease_lock(path: Path) -> threading.Lock:
    key = path.resolve()
    with _LOCKS_GUARD:
        return _LEASE_LOCKS.setdefault(key, threading.Lock())


@contextmanager
def locked_persistence_file(target: Path) -> Iterator[None]:
    """Serialize one target across threads and processes.

    ``flock`` locks are process-scoped on supported hosts, so the per-path
    ``RLock`` is required for two kernel instances in the same interpreter.
    The lock file is retained to keep the cross-process lock inode stable.
    """
    lock_path = target.with_suffix(f"{target.suffix}.lock")
    with _process_thread_lock(lock_path):
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def try_locked_persistence_file(target: Path) -> Iterator[None]:
    """Acquire one target exclusively without waiting.

    The retained lock inode gives the lease process scope, while the local
    lock closes the same-process gap in flock semantics. A process crash
    closes the file descriptor and releases the lease; there is no stale
    timestamp or owner record to reclaim.
    """

    lock_path = target.with_suffix(f"{target.suffix}.lock")
    # Deliberately non-reentrant: concurrent asyncio tasks share an OS thread,
    # so an RLock would admit both and collapse the task-level lease boundary.
    local_lock = _process_lease_lock(lock_path)
    if not local_lock.acquire(blocking=False):
        raise PersistenceFileBusy(f"persistence lease is busy: {lock_path}")
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno in {errno.EACCES, errno.EAGAIN}:
                    raise PersistenceFileBusy(
                        f"persistence lease is busy: {lock_path}"
                    ) from exc
                raise
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        local_lock.release()
