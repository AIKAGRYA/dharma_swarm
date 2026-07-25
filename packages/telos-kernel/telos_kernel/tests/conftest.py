"""Shared fixtures for telos-kernel tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the kernel package is importable when tests are run standalone.
_PKG_ROOT = Path(__file__).resolve().parents[2]
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

# The manifest sits at <repo_root>/kernel/manifest.yaml; kernel loader looks
# there by default (via telos_kernel.manifest.DEFAULT_MANIFEST_PATH).


@pytest.fixture
def tmp_log(tmp_path):
    """Fresh MerkleLog on a tmp path (FileBackend)."""
    from telos_kernel.merkle_log import FileBackend, MerkleLog
    return MerkleLog(backend=FileBackend(tmp_path / "chain.json"))


@pytest.fixture
def memory_log():
    """Fresh MerkleLog with in-memory backend (fastest for unit tests)."""
    from telos_kernel.merkle_log import MemoryBackend, MerkleLog
    return MerkleLog(backend=MemoryBackend())


@pytest.fixture
def loaded_manifest():
    """Manifest loaded from kernel/manifest.yaml."""
    from telos_kernel.manifest import load_manifest
    return load_manifest()
