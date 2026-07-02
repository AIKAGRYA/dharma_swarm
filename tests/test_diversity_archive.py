"""Tests for the retired dharma_swarm.diversity_archive deprecation shim.

The standalone DiversityArchive was consolidated onto
dharma_swarm.archive.MAPElitesGrid (organism-rewire-2026-07, D6a). The
former capability tests now live in tests/test_archive.py. These tests only
assert the shim warns on import and re-exports the canonical types.
"""

from __future__ import annotations

import importlib
import warnings


def test_import_emits_deprecation_warning():
    import dharma_swarm.diversity_archive as shim

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.reload(shim)

    messages = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert messages, "shim import must emit a DeprecationWarning"
    assert "MAPElitesGrid" in str(messages[0].message)


def test_shim_reexports_canonical_types():
    from dharma_swarm import archive
    from dharma_swarm import diversity_archive as shim

    assert shim.MAPElitesGrid is archive.MAPElitesGrid
    assert shim.ArchiveEntry is archive.ArchiveEntry
    assert shim.FitnessScore is archive.FitnessScore


def test_shim_does_not_reexport_removed_class():
    from dharma_swarm import diversity_archive as shim

    assert not hasattr(shim, "DiversityArchive")
    assert not hasattr(shim, "BehaviorDescriptor")
