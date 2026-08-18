"""Per-node hard/idle timeout policy + heartbeat seam (LG25 parity slice).

Mirrors ``langgraph.types.TimeoutPolicy`` (1.2.4, ``site-packages/langgraph/
types.py:449``) field-for-field:

* ``run_timeout`` — hard wall-clock cap for ONE node attempt. Never refreshed.
* ``idle_timeout`` — maximum time one attempt may go without observable
  progress. Refreshed by :func:`heartbeat`.
* ``refresh_on`` — which signals refresh ``idle_timeout``.

Both bounds are per ATTEMPT, so a retried node gets a fresh deadline pair on
every attempt (this is what couples LG25 to LG24's ``timeout_retry``).

Recorded deviation: langgraph's ``refresh_on="auto"`` also refreshes on
internal callback/stream events. The neutral engine emits no such event bus,
so ``"auto"`` and ``"heartbeat"`` are observationally identical here — both
refresh on explicit :func:`heartbeat` calls only. The field is still validated
and carried so graphs port across engines unchanged.

Timeouts are the one place the engine consumes REAL time: they exist to bound
wall-clock work, and ``asyncio`` cancellation is the enforcement mechanism.
The clock is still read through the effects seam (``EffectsProvider.monotonic``
/ ``default_monotonic``) per the seam-ledger law; both stock providers return
wall monotonic time today. Retry backoff stays on ``effects.retry_sleep``.

claim_mode: candidate / test_only. Not wired into production dispatch.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Literal

from dharma_swarm.graph.effects import default_monotonic, monotonic_clock, wait_for_task
from dharma_swarm.graph.errors import NodeTimeoutError
from dharma_swarm.graph.retry import RetryPolicy, RetryPolicySpec, normalize_retry_policies

if TYPE_CHECKING:
    from dharma_swarm.graph.effects import EffectsProvider
    from dharma_swarm.graph.routing import Command

__all__ = [
    "IdleWatchdog",
    "TimeoutPolicy",
    "coerce_node_binding",
    "current_watchdog",
    "heartbeat",
    "pop_watchdog",
    "push_watchdog",
    "run_timed_attempt",
]

RefreshOn = Literal["auto", "heartbeat"]


def _coerce_timeout_seconds(
    value: float | timedelta | None, *, field: str
) -> float | None:
    """Positive seconds, or None (``_coerce_timeout_seconds`` parity)."""
    if value is None:
        return None
    seconds = value.total_seconds() if isinstance(value, timedelta) else float(value)
    if seconds <= 0:
        raise ValueError(f"{field} must be greater than 0")
    return seconds


@dataclass(frozen=True, kw_only=True)
class TimeoutPolicy:
    """Configuration for timing out node attempts (langgraph parity).

    Cooperative cancellation: enforcement rides ``asyncio`` cancellation, so a
    synchronous node body that blocks the event loop cannot be interrupted
    mid-call. The executor therefore dispatches timed synchronous nodes onto a
    worker thread; a timed-out thread is orphaned and its result discarded
    (same contract as the existing ``Send(timeout=...)`` path).
    """

    run_timeout: float | timedelta | None = None
    """Hard wall-clock cap (seconds) for a single node attempt; never refreshed."""

    idle_timeout: float | timedelta | None = None
    """Maximum time (seconds) one attempt may go without observable progress."""

    refresh_on: RefreshOn = "auto"
    """Which signals refresh ``idle_timeout`` (see the module deviation note)."""

    @classmethod
    def coerce(
        cls, value: float | timedelta | TimeoutPolicy | None
    ) -> TimeoutPolicy | None:
        """Normalize a timeout value to positive-second policy fields.

        A bare number/timedelta means "hard cap only" (langgraph parity). A
        policy with neither bound set is rejected: an empty policy would
        silently disable the feature the caller asked for (fail closed).
        """
        if value is None:
            return None
        if isinstance(value, TimeoutPolicy):
            run_timeout = _coerce_timeout_seconds(
                value.run_timeout, field="run_timeout"
            )
            idle_timeout = _coerce_timeout_seconds(
                value.idle_timeout, field="idle_timeout"
            )
            if value.refresh_on not in ("auto", "heartbeat"):
                raise ValueError(
                    f"refresh_on must be 'auto' or 'heartbeat', not "
                    f"{value.refresh_on!r} (fail closed)"
                )
            refresh_on: RefreshOn = value.refresh_on
        else:
            run_timeout = _coerce_timeout_seconds(value, field="run_timeout")
            idle_timeout = None
            refresh_on = "auto"
        if run_timeout is None and idle_timeout is None:
            raise ValueError(
                "TimeoutPolicy needs run_timeout, idle_timeout, or both "
                "(an empty policy would silently disable timeouts)"
            )
        return cls(
            run_timeout=run_timeout,
            idle_timeout=idle_timeout,
            refresh_on=refresh_on,
        )


def coerce_node_binding(
    retry_policy: RetryPolicySpec,
    timeout: float | timedelta | TimeoutPolicy | None,
) -> tuple[tuple[RetryPolicy, ...], TimeoutPolicy | None]:
    """Normalize ``add_node``'s ``retry_policy``/``timeout`` args together
    (compiler-side glue: both coercions are needed to build one ``NodeSpec``)."""
    return normalize_retry_policies(retry_policy), TimeoutPolicy.coerce(timeout)


class IdleWatchdog:
    """Mutable progress marker for ONE idle-timed node attempt.

    The executor installs it in a contextvar before the attempt starts, so the
    node's own coroutine (or worker thread — ``asyncio.to_thread`` copies the
    context) can refresh it via :func:`heartbeat` from arbitrary depth. The
    object is shared, not copied, so mutation is visible to the watchdog loop.
    """

    __slots__ = ("node_id", "heartbeats", "last_progress", "_clock")

    def __init__(
        self,
        node_id: str,
        clock: Callable[[], float] = default_monotonic,
    ) -> None:
        self.node_id = node_id
        self.heartbeats = 0
        self._clock = clock
        self.last_progress = clock()

    def record_progress(self) -> None:
        self.heartbeats += 1
        self.last_progress = self._clock()

    def idle_deadline(self, idle_timeout: float) -> float:
        return self.last_progress + idle_timeout


_ACTIVE_WATCHDOG: ContextVar[IdleWatchdog | None] = ContextVar(
    "dharma_graph_idle_watchdog", default=None
)


def push_watchdog(watchdog: IdleWatchdog | None) -> Token:
    """Install ``watchdog`` for the current context; returns the reset token."""
    return _ACTIVE_WATCHDOG.set(watchdog)


def pop_watchdog(token: Token) -> None:
    """Restore the previously installed watchdog."""
    _ACTIVE_WATCHDOG.reset(token)


def current_watchdog() -> IdleWatchdog | None:
    """The watchdog of the running idle-timed attempt, if any."""
    return _ACTIVE_WATCHDOG.get()


def heartbeat() -> None:
    """Record progress for the current node's ``idle_timeout``.

    Call this from long-running work that emits no natural progress signal.
    Outside an idle-timed attempt this is a no-op (``Runtime.heartbeat``
    parity), so nodes can call it unconditionally.
    """
    watchdog = _ACTIVE_WATCHDOG.get()
    if watchdog is not None:
        watchdog.record_progress()


async def run_timed_attempt(
    effects: "EffectsProvider",
    node_id: str,
    run_id: str,
    superstep: int,
    policy: TimeoutPolicy,
    execute: Callable[[], Coroutine[Any, Any, "Any | Command | None"]],
) -> "Any | Command | None":
    """Run one node attempt under its declared hard and/or idle bounds.

    ``execute`` is a zero-arg factory for the node's execution coroutine (the
    executor's own ``_execute_node`` call, closed over its arguments) so this
    function owns only the timeout envelope, not node dispatch itself.

    The node runs as its own asyncio task so the watchdog can observe it
    while it works. The HARD bound (``run_timeout``) is measured from this
    attempt's start and is never refreshed; the IDLE bound is measured from
    the last :func:`heartbeat` and IS. The watchdog re-derives both deadlines
    after every wake-up, so a heartbeat that lands during a wait extends only
    the idle deadline. Whichever bound expires first cancels the node and
    raises :class:`~dharma_swarm.graph.errors.NodeTimeoutError` — a
    ``GraphRuntimeError``, so the failed superstep keeps its normal
    fail-closed semantics.
    """
    run_timeout = policy.run_timeout
    idle_timeout = policy.idle_timeout
    clock = monotonic_clock(effects)
    started = clock()
    watchdog = (
        IdleWatchdog(node_id, clock=clock) if idle_timeout is not None else None
    )
    wd_token = push_watchdog(watchdog)
    try:
        node_task = asyncio.ensure_future(execute())
        try:
            while True:
                now = clock()
                deadlines: list[float] = []
                if run_timeout is not None:
                    deadlines.append(started + float(run_timeout))
                if idle_timeout is not None and watchdog is not None:
                    deadlines.append(watchdog.idle_deadline(float(idle_timeout)))
                budget = min(deadlines) - now
                if budget <= 0:
                    kind: str = "idle"
                    if run_timeout is not None and (
                        now - started >= float(run_timeout)
                    ):
                        kind = "run"
                    raise NodeTimeoutError(
                        node_id,
                        now - started,
                        kind=kind,  # type: ignore[arg-type]
                        run_timeout=(
                            float(run_timeout) if run_timeout is not None else None
                        ),
                        idle_timeout=(
                            float(idle_timeout) if idle_timeout is not None else None
                        ),
                        graph_run_id=run_id,
                        superstep=superstep,
                    )
                if await wait_for_task(node_task, budget):
                    return node_task.result()
                # Woke on the bound, not on completion: loop and re-derive
                # the deadlines, since a heartbeat may have moved the idle
                # one forward while we waited.
        finally:
            if not node_task.done():
                node_task.cancel()
                await wait_for_task(node_task, None)
    finally:
        pop_watchdog(wd_token)
