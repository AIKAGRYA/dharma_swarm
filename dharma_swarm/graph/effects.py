"""Injectable effect providers — the DST (deterministic simulation testing) seam.

Phase 1 seed of the DharmaGraph DST harness (dharmagraph-engine-2026-07, spec
§3 Phase 1): virtualize time, randomness, and dispatch order behind one
protocol so a recorded fault sequence replays exactly from a seed
(FoundationDB/Antithesis discipline). This module is deliberately minimal —
the full fault menu (torn checkpoint, interrupt-during-retry) is later work.

``durable_invoker`` consumes ``EffectsProvider.now()`` for staleness
decisions; simulated runs advance a deterministic clock instead of reading
the wall clock.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol, Sequence, TypeVar

__all__ = [
    "EffectsProvider",
    "LiveEffects",
    "SimulatedEffects",
    "default_monotonic",
    "monotonic_clock",
    "provider_retry_sleep",
    "wait_for_task",
]

T = TypeVar("T")

_SIM_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


class EffectsProvider(Protocol):
    """Ambient effects a graph component may consume.

    Components take a provider instead of calling ``datetime.now`` /
    ``random`` / iterating in arrival order, so a simulated provider can
    replay a fault sequence deterministically.
    """

    def now(self) -> datetime:
        """Current UTC time."""
        ...

    def random(self) -> random.Random:
        """The run's random source (seeded under simulation)."""
        ...

    def dispatch_order(self, items: Sequence[T]) -> list[T]:
        """The order in which concurrent work is dispatched."""
        ...

    async def retry_sleep(self, seconds: float) -> None:
        """Wait out a node's retry backoff."""
        ...

    def monotonic(self) -> float:
        """Monotonic clock consumed by timeout deadlines (seam ledger law:
        every clock the executor reads flows through the provider)."""
        ...


def default_monotonic() -> float:
    """The seam's monotonic primitive — the one place it is read raw."""
    return time.monotonic()


def monotonic_clock(provider: object) -> Callable[[], float]:
    """Resolve a provider's monotonic seam, falling back for duck-typed
    providers that predate it (same contract as ``retry_sleep``)."""
    seam = getattr(provider, "monotonic", None)
    if seam is None:
        return default_monotonic
    return seam


async def provider_retry_sleep(provider: object, seconds: float) -> None:
    """Route a retry backoff through the provider's ``retry_sleep`` seam,
    sleeping for real only for duck-typed providers that predate it."""
    seam = getattr(provider, "retry_sleep", None)
    if seam is None:
        await asyncio.sleep(seconds)
        return
    await seam(seconds)


async def wait_for_task(
    task: "asyncio.Future[T]", timeout: float | None
) -> bool:
    """Wait on ``task`` up to ``timeout`` seconds; True iff it finished.

    Lives in the seam module so the executor's watchdog waits are mediated
    ordering/time primitives, not ambient ``asyncio.wait`` bypasses.
    """
    done, _pending = await asyncio.wait({task}, timeout=timeout)
    return bool(done)


@dataclass(frozen=True)
class LiveEffects:
    """Production provider: wall clock, OS entropy, arrival order."""

    _rng: random.Random = field(default_factory=random.Random, repr=False)

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def random(self) -> random.Random:
        return self._rng

    def dispatch_order(self, items: Sequence[T]) -> list[T]:
        return list(items)

    async def retry_sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    def monotonic(self) -> float:
        return time.monotonic()


class SimulatedEffects:
    """Seeded provider: deterministic clock, rng, and dispatch shuffle.

    Every observable this provider hands out is a pure function of
    ``seed`` and the call sequence, so a failing run replays exactly.
    """

    def __init__(
        self,
        seed: int,
        *,
        start: datetime = _SIM_EPOCH,
        tick_seconds: float = 1.0,
    ) -> None:
        self.seed = seed
        self._clock = start
        self._tick = timedelta(seconds=tick_seconds)
        self._rng = random.Random(seed)
        self.retry_sleeps: list[float] = []

    def now(self) -> datetime:
        current = self._clock
        self._clock = self._clock + self._tick
        return current

    def advance(self, seconds: float) -> None:
        """Jump the simulated clock forward (e.g. past a stale threshold)."""
        self._clock = self._clock + timedelta(seconds=seconds)

    def random(self) -> random.Random:
        return self._rng

    def dispatch_order(self, items: Sequence[T]) -> list[T]:
        ordered = list(items)
        self._rng.shuffle(ordered)
        return ordered

    async def retry_sleep(self, seconds: float) -> None:
        """Record a retry backoff and jump the clock — never really wait.

        Retry-heavy scenarios stay instantaneous and the recorded sequence is a
        pure function of the seed, so a failing retry ladder replays exactly.
        """
        self.retry_sleeps.append(seconds)
        self.advance(seconds)

    def monotonic(self) -> float:
        """Wall monotonic time, for now: node timeouts must actually elapse
        in both arms today. A virtual deadline clock is later DST work."""
        return time.monotonic()
