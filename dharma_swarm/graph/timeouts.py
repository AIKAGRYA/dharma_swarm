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

from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Literal

from dharma_swarm.graph.effects import default_monotonic

__all__ = [
    "IdleWatchdog",
    "TimeoutPolicy",
    "current_watchdog",
    "heartbeat",
    "pop_watchdog",
    "push_watchdog",
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
