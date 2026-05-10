"""Parent selection strategies for the evolution engine.

Ported from ~/DHARMIC_GODEL_CLAW/src/dgm/selector.py into dharma_swarm
conventions: async functions, type hints, no singletons.

Four strategies balance exploration vs. exploitation when choosing
which archive entries to evolve from:

- **tournament**: random k-way tournament (default, good balance)
- **roulette**: fitness-proportional (exploitation-heavy)
- **rank**: rank-based probability (smoother than roulette)
- **elite**: top-n deterministic (pure exploitation)

All four route through :func:`_novelty_weight`, which optionally applies
a Kauffman-style **catalytic boost** when an entry's ``component`` lies
inside an autocatalytic set in the catalytic graph (closes spine §9 gap:
"autocatalytic-closure scores do not feed parent selection"). Pass the
node set via the ``autocatalytic_nodes`` kwarg or leave it ``None`` to
preserve legacy behaviour exactly.
"""

from __future__ import annotations

import os
import random
from typing import Any

from dharma_swarm.archive import ArchiveEntry, EvolutionArchive


def _catalytic_boost_factor() -> float:
    """Read the catalytic boost multiplier from env (default 1.25).

    Set ``CATALYTIC_BOOST_FACTOR=1.0`` to disable without code change.
    Returns 1.0 on parse failure (fail-safe).
    """
    raw = os.getenv("CATALYTIC_BOOST_FACTOR", "1.25").strip()
    try:
        value = float(raw)
    except ValueError:
        return 1.0
    return max(1.0, value)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_applied(archive: EvolutionArchive) -> list[ArchiveEntry]:
    """Return all entries with status ``"applied"``.

    Uses ``archive.get_best()`` with a very large *n* so the archive's own
    filtering logic is reused.  The result is sorted by descending fitness,
    which several strategies rely on.
    """
    return await archive.get_best(n=999_999)


async def _count_children(archive: EvolutionArchive) -> dict[str, int]:
    """Count direct children for each entry in the archive.

    Returns:
        Mapping from entry_id to number of direct children.
    """
    counts: dict[str, int] = {}
    for entry in archive._entries.values():
        if entry.parent_id:
            counts[entry.parent_id] = counts.get(entry.parent_id, 0) + 1
    return counts


def _novelty_weight(
    entry: ArchiveEntry,
    child_counts: dict[str, int],
    weights: dict[str, float] | None = None,
    autocatalytic_nodes: set[str] | None = None,
) -> float:
    """Compute novelty-adjusted weight with ouroboros + catalytic bias.

    Formula: fitness * novelty * behavioral_modifier * catalytic_boost
    - novelty = 1/(1+n_children) — exploration vs exploitation
    - behavioral_modifier: entries whose test_results contain
      genuine recognition get a 1.1x boost; mimicry gets 0.8x penalty.
      This connects the ouroboros behavioral metrics to selection pressure.
    - catalytic_boost: entries whose ``component`` is inside an
      autocatalytic SCC get a multiplicative boost (default 1.25×, env
      ``CATALYTIC_BOOST_FACTOR``). Closes spine §9 gap and rewards
      mutations that strengthen self-sustaining feedback loops.

    Args:
        entry: The archive entry to weight.
        child_counts: Mapping from entry_id to child count.
        weights: Optional fitness-dimension weights.
        autocatalytic_nodes: Optional set of node ids inside autocatalytic
            sets in the catalytic graph. ``None`` → no catalytic boost
            applied (legacy behaviour).

    Returns:
        Novelty-adjusted weight (always >= 0).
    """
    fitness = entry.fitness.weighted(weights=weights)
    n_children = child_counts.get(entry.id, 0)
    novelty = 1.0 / (1.0 + n_children)

    # Behavioral modifier from ouroboros (stored by evolution.py)
    behavioral = 1.0
    if entry.test_results:
        if entry.test_results.get("gaia_drifting"):
            behavioral *= 0.85  # Goodhart drift penalty
        # Future: check for L4 behavioral tags when stored in test_results

    catalytic = 1.0
    if autocatalytic_nodes and entry.component:
        component = entry.component.strip()
        if component and component in autocatalytic_nodes:
            catalytic = _catalytic_boost_factor()

    return fitness * novelty * behavioral * catalytic


# ---------------------------------------------------------------------------
# Selection strategies
# ---------------------------------------------------------------------------


async def tournament_select(
    archive: EvolutionArchive,
    k: int = 3,
    weights: dict[str, float] | None = None,
    autocatalytic_nodes: set[str] | None = None,
) -> ArchiveEntry | None:
    """Pick *k* random applied entries and return the fittest.

    If the archive has fewer than *k* applied entries, all available
    entries participate in the tournament.  Returns ``None`` when the
    archive contains no applied entries.

    Args:
        archive: The evolution archive to draw from.
        k: Tournament size.  Larger *k* increases selection pressure.
        autocatalytic_nodes: Forwarded to :func:`_novelty_weight`.

    Returns:
        The winning ``ArchiveEntry``, or ``None`` if no candidates exist.
    """
    candidates = await _get_applied(archive)
    if not candidates:
        return None

    pool_size = min(k, len(candidates))
    pool = random.sample(candidates, pool_size)
    child_counts = await _count_children(archive)
    return max(
        pool,
        key=lambda e: _novelty_weight(
            e, child_counts, weights=weights, autocatalytic_nodes=autocatalytic_nodes
        ),
    )


async def roulette_select(
    archive: EvolutionArchive,
    weights: dict[str, float] | None = None,
    autocatalytic_nodes: set[str] | None = None,
) -> ArchiveEntry | None:
    """Fitness-proportional (roulette wheel) selection.

    Each applied entry's probability of being selected equals its
    weighted fitness divided by the total fitness of all candidates.
    When all fitnesses are zero, falls back to uniform random choice.

    Args:
        archive: The evolution archive to draw from.
        autocatalytic_nodes: Forwarded to :func:`_novelty_weight`.

    Returns:
        A single ``ArchiveEntry``, or ``None`` if no candidates exist.
    """
    candidates = await _get_applied(archive)
    if not candidates:
        return None

    child_counts = await _count_children(archive)
    candidate_weights = [
        _novelty_weight(
            e, child_counts, weights=weights, autocatalytic_nodes=autocatalytic_nodes
        )
        for e in candidates
    ]
    total = sum(candidate_weights)

    if total == 0.0:
        return random.choice(candidates)

    return random.choices(candidates, weights=candidate_weights, k=1)[0]


async def rank_select(
    archive: EvolutionArchive,
    weights: dict[str, float] | None = None,
    autocatalytic_nodes: set[str] | None = None,
) -> ArchiveEntry | None:
    """Rank-based selection.

    Applied entries are sorted by ascending fitness and assigned integer
    rank weights (worst=1, best=N).  Selection uses rank-based
    probability, which compresses the fitness scale and avoids
    domination by a single super-fit individual.

    Args:
        archive: The evolution archive to draw from.
        autocatalytic_nodes: Forwarded to :func:`_novelty_weight`.

    Returns:
        A single ``ArchiveEntry``, or ``None`` if no candidates exist.
    """
    candidates = await _get_applied(archive)
    if not candidates:
        return None

    # Sort ascending so rank 1 = worst, rank N = best.
    child_counts = await _count_children(archive)
    sorted_asc = sorted(
        candidates,
        key=lambda e: _novelty_weight(
            e, child_counts, weights=weights, autocatalytic_nodes=autocatalytic_nodes
        ),
    )
    rank_weights = list(range(1, len(sorted_asc) + 1))

    return random.choices(sorted_asc, weights=rank_weights, k=1)[0]


async def elite_select(
    archive: EvolutionArchive,
    n: int = 3,
    weights: dict[str, float] | None = None,
    autocatalytic_nodes: set[str] | None = None,  # noqa: ARG001 (accepted for API parity, see docstring)
) -> list[ArchiveEntry]:
    """Return the top *n* entries by weighted fitness.

    This is a thin wrapper around ``archive.get_best(n)`` that provides
    a consistent interface with the other selectors.

    Note: ``autocatalytic_nodes`` is accepted for API parity with the
    other selectors but is **ignored** — elite is "pure exploitation" by
    design, and its weighting is delegated to ``archive.get_best``.

    Args:
        archive: The evolution archive to draw from.
        n: How many elite entries to return.
        autocatalytic_nodes: Accepted for API parity, ignored here.

    Returns:
        A list of up to *n* ``ArchiveEntry`` objects, sorted by
        descending fitness.  May be empty if no applied entries exist.
    """
    return await archive.get_best(n=n, weights=weights)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_STRATEGIES: dict[str, str] = {
    "tournament": "tournament_select",
    "roulette": "roulette_select",
    "rank": "rank_select",
    "elite": "elite_select",
}


async def select_parent(
    archive: EvolutionArchive,
    strategy: str = "tournament",
    **kwargs: Any,
) -> ArchiveEntry | None:
    """Unified dispatch for parent selection.

    Args:
        archive: The evolution archive to draw from.
        strategy: One of ``"tournament"``, ``"roulette"``, ``"rank"``,
            or ``"elite"``.
        **kwargs: Forwarded to the chosen strategy function. Common
            kwargs:

            - ``k=5`` for tournament size,
            - ``n=3`` for elite count,
            - ``weights=`` fitness-dimension weights,
            - ``autocatalytic_nodes=`` set of node ids inside
              autocatalytic SCCs in the catalytic graph; entries whose
              ``component`` matches receive a boost (env
              ``CATALYTIC_BOOST_FACTOR``, default 1.25×).

    Returns:
        A single ``ArchiveEntry``, or ``None`` when the archive is empty.

    Raises:
        ValueError: If *strategy* is not recognised.
    """
    if strategy not in _STRATEGIES:
        raise ValueError(
            f"Unknown selection strategy {strategy!r}. "
            f"Choose from: {', '.join(sorted(_STRATEGIES))}"
        )

    if strategy == "elite":
        entries = await elite_select(archive, **kwargs)
        return entries[0] if entries else None

    if strategy == "tournament":
        return await tournament_select(archive, **kwargs)

    if strategy == "roulette":
        return await roulette_select(archive, **kwargs)

    # rank
    return await rank_select(archive, **kwargs)
