"""Shared pytest fixtures for chetana tests.

Most tests need ~/.dharma sandboxed to a tmp dir so they don't write to the
operator's real wiki. The fixtures here patch the staging/quarantine/wiki roots.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def chetana_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect chetana's staging / wiki / quarantine roots to a tmp tree."""
    from dharma_swarm.chetana import staging as staging_mod
    from dharma_swarm.chetana import decay as decay_mod
    from dharma_swarm.chetana import gap_scan as gap_mod
    from dharma_swarm.chetana import palace as palace_mod
    from dharma_swarm.chetana import revival as revival_mod

    staging_root = tmp_path / "staging"
    quarantine_root = tmp_path / "quarantine"
    wiki_root = tmp_path / "wiki"
    trusted_root = wiki_root / "concepts"

    for d in (staging_root, quarantine_root, wiki_root, trusted_root):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(staging_mod, "STAGING_ROOT", staging_root, raising=True)
    monkeypatch.setattr(staging_mod, "QUARANTINE_ROOT", quarantine_root, raising=True)
    monkeypatch.setattr(staging_mod, "WIKI_ROOT", wiki_root, raising=True)
    monkeypatch.setattr(staging_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(decay_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(decay_mod, "QUARANTINE_ROOT", quarantine_root, raising=True)
    monkeypatch.setattr(decay_mod, "WIKI_ROOT", wiki_root, raising=True)
    monkeypatch.setattr(gap_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(palace_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(
        palace_mod, "DEFAULT_PALACE_PATH", tmp_path / "memory_palace.canvas", raising=True
    )
    monkeypatch.setattr(revival_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)

    return tmp_path
