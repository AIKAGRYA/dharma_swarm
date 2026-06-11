"""chetana.stigmergy_emit — best-effort pheromone trail for chetana operations.

Every chetana operation (ingest, promote, revive) leaves a mark on the
dharma_swarm stigmergy lattice so the runtime can SEE chetana activity. Marks
are best-effort observability — failures here MUST NOT break the underlying
chetana operation. Read/write atomicity belongs to the chetana modules; this
module is a passive observer that whispers into the runtime's mark stream.

Mirrors chetana.governance's lazy-import pattern: dharma_swarm.stigmergy is
imported on demand so chetana stays unit-testable when dharma_swarm internals
aren't on the path.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

logger = logging.getLogger(__name__)


def emit_mark(
    action: str,
    content: str,
    agent_id: str = "chetana",
    connections: list[str] | None = None,
    salience: float = 0.5,
) -> bool:
    """Leave a stigmergic mark for a chetana operation.

    Returns True on successful emit, False on any failure (import, runtime,
    or shape mismatch). Never raises — chetana operations are atomic; this
    is best-effort observability only.
    """
    try:
        from dharma_swarm.stigmergy import StigmergicMark, StigmergyStore  # type: ignore
    except Exception as e:  # ImportError or any transitive import failure
        logger.warning(
            "chetana.stigmergy_emit: dharma_swarm.stigmergy not importable (%s); "
            "skipping mark emission.",
            e,
        )
        return False

    try:
        mark = StigmergicMark(
            agent=agent_id,
            file_path=f"chetana/{action}",
            action="write",
            observation=content[:200],
            salience=max(0.0, min(1.0, salience)),
            connections=connections or [],
            channel="memory",
        )
        store = StigmergyStore()
        coro = store.leave_mark(mark)
        if inspect.isawaitable(coro):
            _run_sync_awaitable(coro)
        return True
    except Exception as e:
        logger.warning(
            "chetana.stigmergy_emit: leave_mark failed for action=%s (%s); "
            "chetana operation continues unaffected.",
            action,
            e,
        )
        return False


def _run_sync_awaitable(awaitable: Any) -> Any:
    """Run an awaitable synchronously when no event loop is active.

    Mirrors the pattern in chetana.governance — chetana's public API is sync,
    but stigmergy is async. If we're already inside a running loop, we cannot
    block, so we schedule and detach (best-effort: warning only on failure).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    # We're inside a running loop. Schedule as a task so we don't deadlock.
    # The mark will land asynchronously; chetana caller does not wait.
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(awaitable)
        return None
    except Exception:
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise
