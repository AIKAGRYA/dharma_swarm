"""Parent selection: one parent per child slot, sampled from the FULL archive.

The Sakana-DGM weight (ported formula — never import dgm_loop):

    w(e) = fitness(e)^(1-p) * (1 / (1 + n_children(e)))^p

with p = novelty_pressure in [0, 1]: p=0 is pure hill-climb, p=1 ignores
fitness entirely (pure stepping-stone exploration). At p>0 the final product
has a tiny positive floor, so zero-fitness stepping stones remain reachable in
a mixed archive. At p=0, zero fitness remains exactly zero. If every pure-
fitness weight is zero, selection falls back to uniform — a graded candidate
is never unreachable.
"""

from __future__ import annotations

import random
from typing import Any, Sequence


MIN_STEPPING_STONE_WEIGHT = 1e-6


def parent_weight(fitness: float, n_children: int, novelty_pressure: float) -> float:
    p = max(0.0, min(1.0, float(novelty_pressure)))
    fit = max(0.0, float(fitness))
    novelty = 1.0 / (1.0 + max(0, int(n_children)))
    weight = (fit ** (1.0 - p)) * (novelty**p)
    # At p=0 selection is intentionally pure fitness.  For any exploratory
    # pressure, keep a graded zero-fitness stepping stone reachable even when
    # a positive-fitness entry is present (the all-zero fallback alone cannot
    # provide that guarantee).
    return weight if p == 0.0 else max(weight, MIN_STEPPING_STONE_WEIGHT)


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


__all__ = ["MIN_STEPPING_STONE_WEIGHT", "parent_weight", "sample_parent"]
