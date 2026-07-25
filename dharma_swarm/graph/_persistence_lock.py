"""Thread- and process-safe lock for one graph persistence file."""

from __future__ import annotations

import fcntl
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_LOCKS: dict[Path, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _process_thread_lock(path: Path) -> threading.RLock:
    key = path.resolve()
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


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
