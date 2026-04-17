"""Sync → async bridge helper that is safe under Python 3.14 thread-pool reuse.

Background
----------
Sprint 1.5 Fix A (2026-04-18). The dharma_swarm daemon has several synchronous
functions (e.g. ``dharma_swarm.pulse.pulse()``, ``WebSearchBackend.search()``,
``tool_registry.dispatch()``) that internally need to run an async coroutine.
The daemon invokes those sync functions via ``asyncio.to_thread(...)`` from an
async loop, i.e. they execute on a worker thread of the default thread-pool
executor.

Prior pattern (``asyncio.run(coro)``) broke after 2026-04-14 with Python 3.14:

    RuntimeError: This event loop is already running
    + RuntimeWarning: coroutine '...' was never awaited

Python 3.14 tightened ``asyncio.run()``: it now refuses to start if ``any``
running loop is detected in the current thread. The default ``ThreadPoolExecutor``
reuses threads, so loop-state residue from a prior ``asyncio.run()`` on the same
thread can leak into the next call (especially after the loop is closed but
before Python fully reaps thread-local state).

Observed failure chain:
    1. RTN fires → sync ``execute_brief`` → sync ``WebSearchBackend.search``
    2. ``search`` calls ``asyncio.run(self._async_search(...))``
    3. ``asyncio.run`` sees stale/running loop state → RuntimeError
    4. The coroutine created in the call args is never awaited (warning)
    5. The shared asyncio loop in the daemon is corrupted enough that
       sibling loops (cc_tool_marks, R_V, DGM shadow) silently stop cycling.

Fix
---
Create an explicit fresh event loop with ``asyncio.new_event_loop()`` and drive
it with ``loop.run_until_complete``. This path does not consult thread-local
state the way ``asyncio.run`` does, so it is safe under thread-pool reuse.

Rollback
--------
There is no env flag — this is a correctness fix. If the fix regresses, revert
the calling sites individually.
"""

from __future__ import annotations

import asyncio
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


def run_coroutine_in_new_loop(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine synchronously in a freshly-created event loop.

    Safe to call from a thread-pool worker that may have stale loop state
    from a prior ``asyncio.run``. Always creates, drives, and closes its own
    event loop — does not inspect or reuse thread-local state.

    Args:
        coro: Coroutine object (e.g. ``backend._async_search(brief, queries)``).

    Returns:
        The coroutine's return value.

    Raises:
        Whatever the coroutine raises. Exceptions propagate unwrapped.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except Exception:
            pass
