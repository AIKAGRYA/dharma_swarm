"""Shared pytest fixtures for chetana tests.

Most tests need ~/.dharma sandboxed to a tmp dir so they don't write to the
operator's real wiki. The fixtures here patch the staging/quarantine/wiki roots,
plus the stigmergy default base path so emit_mark() calls don't pollute the
operator's real marks.jsonl during testing.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _sandbox_stigmergy(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """Redirect the dharma_swarm stigmergy base path to a per-session tmp dir.

    Applied to ALL chetana tests automatically. Without this, emit_mark() calls
    from promote/revive/ingest would append to the operator's real
    ~/.dharma/stigmergy/marks.jsonl during test runs.
    """
    try:
        from dharma_swarm import stigmergy as stigmergy_mod  # type: ignore
    except Exception:
        return  # dharma_swarm.stigmergy not importable — nothing to patch
    sandbox = tmp_path_factory.mktemp("stigmergy")
    monkeypatch.setattr(stigmergy_mod, "_DEFAULT_BASE", sandbox, raising=True)
    # Reset the module-level singleton so it re-instantiates with the sandbox
    monkeypatch.setattr(stigmergy_mod, "_default_store", None, raising=True)


@pytest.fixture(autouse=True)
def _sandbox_kernel(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """Provide a real signed kernel for fail-closed chetana governance tests."""
    from dharma_swarm import dharma_kernel as kernel_mod

    kernel_path = tmp_path_factory.mktemp("kernel") / "kernel.json"
    asyncio.run(kernel_mod.KernelGuard(kernel_path).save(kernel_mod.DharmaKernel.create_default()))
    monkeypatch.setattr(kernel_mod, "_DEFAULT_KERNEL_PATH", kernel_path, raising=True)


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
    pending_root = wiki_root / "pending"

    for d in (staging_root, quarantine_root, wiki_root, trusted_root, pending_root):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(staging_mod, "STAGING_ROOT", staging_root, raising=True)
    monkeypatch.setattr(staging_mod, "QUARANTINE_ROOT", quarantine_root, raising=True)
    monkeypatch.setattr(staging_mod, "WIKI_ROOT", wiki_root, raising=True)
    monkeypatch.setattr(staging_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(staging_mod, "WIKI_PENDING_ROOT", pending_root, raising=True)
    monkeypatch.setattr(decay_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(gap_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(palace_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)
    monkeypatch.setattr(
        palace_mod, "DEFAULT_PALACE_PATH", tmp_path / "memory_palace.canvas", raising=True
    )
    monkeypatch.setattr(revival_mod, "TRUSTED_DEFAULT", trusted_root, raising=True)

    return tmp_path
