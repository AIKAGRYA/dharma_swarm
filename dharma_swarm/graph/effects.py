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

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol, Sequence, TypeVar

__all__ = [
    "EffectsProvider",
    "LiveEffects",
    "SimulatedEffects",
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
