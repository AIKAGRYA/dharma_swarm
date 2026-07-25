"""DEPRECATED — MAP-Elites is consolidated on :mod:`dharma_swarm.archive`.

This module is a retirement shim kept only so stale imports fail loudly
rather than silently. The live, wired quality-diversity implementation is
``dharma_swarm.archive.MAPElitesGrid`` (used by ``DarwinEngine`` via
``EvolutionArchive.grid`` / ``get_diverse`` / ``get_diverse_parents``).

Retired 2026-07-02 by the organism-rewire-2026-07 track, item D6a
(doctrine: docs/plans/ORGANISM_REWIRE_DOCTRINE_2026-07-02.md §6). The old
standalone ``DiversityArchive`` had ZERO non-test callers.

Use instead
-----------
- ``DiversityArchive``            -> ``dharma_swarm.archive.MAPElitesGrid``
- ``ArchiveCell`` / candidate     -> ``dharma_swarm.archive.ArchiveEntry``
- fitness scalar                  -> ``dharma_swarm.archive.FitnessScore``
- ``.add(...)``                   -> ``MAPElitesGrid.try_insert(entry)``
- ``.sample_diverse(n)``          -> ``MAPElitesGrid.sample_diverse(n)``  (ABSORBED)
- ``.get_diverse_parents(...)``   -> ``MAPElitesGrid.get_diverse_parents(n)``
- ``.coverage()``                 -> ``MAPElitesGrid.coverage()``

Absorbed into archive.MAPElitesGrid
-----------------------------------
- ``sample_diverse(n)`` — greedy farthest-point behavioral-spread sampling
  (distinct from the fitness-ranked ``get_diverse_parents``). Ported with tests
  (see ``tests/test_archive.py::test_map_elites_sample_diverse*``).

NOT ported (intentionally dropped — architecturally coupled to the standalone
design, and unused in production)
---------------------------------------------------------------------------
- Arbitrary user-defined N-dimensional ``BehaviorDescriptor`` grids.
  ``MAPElitesGrid`` uses the fixed 3-axis (dharmic_alignment, elegance,
  complexity) feature space over ``ArchiveEntry``.
- Standalone candidate payloads decoupled from ``ArchiveEntry``.
- JSON serialization lifecycle (``to_dict``/``from_dict``/``persist``/``load``).
  ``MAPElitesGrid`` is rebuilt from the ``EvolutionArchive`` JSONL, so it needs
  no independent persistence.
- ``best_per_dimension(dim)`` and the ``diversity_score`` in ``stats()``.
  Re-derive from ``MAPElitesGrid`` if a future caller needs them; the arena's
  descriptor variant lives in ``dharma_swarm/coordination/genome.py``.
"""

from __future__ import annotations

import warnings

from dharma_swarm.archive import (  # noqa: F401  (re-export canonical types)
    ArchiveEntry,
    FitnessScore,
    MAPElitesGrid,
)

warnings.warn(
    "dharma_swarm.diversity_archive is deprecated and retired; use "
    "dharma_swarm.archive.MAPElitesGrid (see this module's docstring for the "
    "capability mapping).",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["MAPElitesGrid", "ArchiveEntry", "FitnessScore"]
