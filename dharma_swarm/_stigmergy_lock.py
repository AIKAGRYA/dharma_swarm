"""Local mutation locking for stigmergy JSONL persistence."""

from __future__ import annotations

import asyncio
import fcntl
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

_LOCAL_LOCK_POLL_SECONDS = 0.01
_PATH_WRITE_LOCKS: dict[Path, asyncio.Lock] = {}


def path_write_lock(marks_file: Path) -> asyncio.Lock:
    """Return the single-event-loop mutation lock for one canonical hot file."""
    canonical_path = marks_file.resolve()
    lock = _PATH_WRITE_LOCKS.get(canonical_path)
    if lock is None:
        lock = asyncio.Lock()
        _PATH_WRITE_LOCKS[canonical_path] = lock
    return lock


@asynccontextmanager
async def _local_file_mutation_lock(lock_path: Path) -> AsyncIterator[None]:
    """Serialize cooperating writers that share one local filesystem."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    acquired = False
    try:
        while not acquired:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                await asyncio.sleep(_LOCAL_LOCK_POLL_SECONDS)
        yield
    finally:
        if acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


@asynccontextmanager
async def local_mutation_guard(
    in_process_lock: asyncio.Lock,
    lock_path: Path,
) -> AsyncIterator[None]:
    """Compose single-loop coroutine safety with a local-filesystem lease.

    ``flock`` is advisory and its distributed-filesystem semantics vary, so this
    is deliberately a local-host/local-filesystem guarantee. Non-blocking lock
    attempts keep the event loop responsive while another coroutine or process
    owns the mutation lease.
    """
    async with in_process_lock:
        async with _local_file_mutation_lock(lock_path):
            yield
