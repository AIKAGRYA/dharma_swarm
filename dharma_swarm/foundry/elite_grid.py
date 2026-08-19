"""Foundry-local MAP-Elites grid (diversity-preserving selection).

A minimal, stdlib elite grid: one champion per behavior niche, so the search
keeps stepping stones instead of collapsing to a single global best. It is
deliberately foundry-local and separate from ``dharma_swarm.archive.MAPElitesGrid``
— foundry fitness stays lab-local until the One Wire guardian quorum is real, at
which point :mod:`dharma_swarm.foundry.guardian_feed` bridges confirmed receipts
into the organism archive. Keeping them separate is what prevents an unproven
foundry win from silently moving archive fitness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Hashable


@dataclass(frozen=True)
class Elite:
    descriptor: tuple[Hashable, ...]
    candidate_id: str
    fitness: float
    payload: dict[str, Any] = field(default_factory=dict)


class EliteGrid:
    """One fittest entry per behavior-descriptor bin."""

    def __init__(self) -> None:
        self._bins: dict[tuple[Hashable, ...], Elite] = {}

    def add(
        self,
        descriptor: tuple[Hashable, ...],
        candidate_id: str,
        fitness: float,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        """Insert a candidate; keep it only if it beats its niche's champion."""
        current = self._bins.get(descriptor)
        if current is not None and fitness <= current.fitness:
            return False
        self._bins[descriptor] = Elite(
            descriptor=descriptor,
            candidate_id=candidate_id,
            fitness=fitness,
            payload=dict(payload or {}),
        )
        return True

    def elites(self) -> list[Elite]:
        return sorted(self._bins.values(), key=lambda e: e.fitness, reverse=True)

    def best(self) -> Elite | None:
        elites = self.elites()
        return elites[0] if elites else None

    def coverage(self) -> int:
        return len(self._bins)

    def mean_fitness(self) -> float:
        if not self._bins:
            return 0.0
        return sum(e.fitness for e in self._bins.values()) / len(self._bins)

    def parents(self, k: int) -> list[Elite]:
        """Top-k elites as breeding parents (diversity-preserving sample)."""
        return self.elites()[:k]
