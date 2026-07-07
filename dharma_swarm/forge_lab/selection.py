"""Parent selection: one parent per child slot, sampled from the FULL archive.

The Sakana-DGM weight (ported formula — never import dgm_loop):

    w(e) = fitness(e)^(1-p) * (1 / (1 + n_children(e)))^p

with p = novelty_pressure in [0, 1]: p=0 is pure hill-climb, p=1 ignores
fitness entirely (pure stepping-stone exploration). Zero-fitness entries stay
sampleable forever at p>0 (0**0 == 1), and when every weight is zero
(cold start) selection falls back to uniform — a graded candidate is never
unreachable.
"""

from __future__ import annotations

import random
from typing import Any, Sequence


def parent_weight(fitness: float, n_children: int, novelty_pressure: float) -> float:
    p = max(0.0, min(1.0, float(novelty_pressure)))
    fit = max(0.0, float(fitness))
    novelty = 1.0 / (1.0 + max(0, int(n_children)))
    return (fit ** (1.0 - p)) * (novelty**p)


def sample_parent(
    entries: Sequence[Any],
    child_counts: dict[str, int],
    *,
    novelty_pressure: float = 0.7,
    rng: random.Random,
) -> Any:
    """Weighted draw over graded archive entries (ArchiveEntry-like: .id, .fitness.weighted())."""
    if not entries:
        raise ValueError("cannot sample a parent from an empty archive")
    weights = [
        parent_weight(e.fitness.weighted(), child_counts.get(e.id, 0), novelty_pressure)
        for e in entries
    ]
    total = sum(weights)
    if total <= 0.0:
        return rng.choice(list(entries))
    return rng.choices(list(entries), weights=weights, k=1)[0]


__all__ = ["parent_weight", "sample_parent"]
