"""Backwards-compat shim.

The canonical ``MerkleLog`` implementation lives in ``telos_kernel.merkle_log``
under ``packages/telos-kernel/``. This module re-exports the public surface so
legacy callers (``from dharma_swarm.merkle_log import MerkleLog``) keep working
without modification.

The kernel version is a strict superset: it adds JCS canonicalization, signed
``Leaf`` payloads, ``MemoryBackend``, and a titanium ``verify_chain`` return
shape. Legacy callers get the legacy ``verify_chain`` return shape
(``(True, N)`` on success) via the facade below.

See ``specs/TITANIUM_TELOS_GATES_SPEC_v3.md`` section U5.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_KERNEL_PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "packages" / "telos-kernel"
if _KERNEL_PACKAGE_ROOT.exists() and str(_KERNEL_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_KERNEL_PACKAGE_ROOT))

from telos_kernel.merkle_log import (  # noqa: E402,F401
    FileBackend,
    MemoryBackend,
    MerkleLog as _KernelMerkleLog,
    verify_merkle_inclusion,
)


class MerkleLog(_KernelMerkleLog):
    """Legacy-compatible facade over the kernel MerkleLog.

    Legacy call sites expect ``MerkleLog(path)`` and
    ``verify_chain(data_store=None)`` to return ``(True, len(hashes))`` on
    success. The kernel constructor separates backend from log file and returns
    ``(True, None)`` per Titanium section U5, so this subclass preserves the
    original ``dharma_swarm`` contract.
    """

    def __init__(
        self,
        log_file: str | Path | Any = "~/.dharma/evolution_merkle.json",
        *,
        backend: Any | None = None,
    ) -> None:
        if backend is not None:
            super().__init__(backend=backend)
            return
        if hasattr(log_file, "load") and hasattr(log_file, "save"):
            super().__init__(backend=log_file)
            return
        super().__init__(log_file=log_file)

    def verify_chain(self, data_store=None):  # type: ignore[override]
        ok, first_broken = _KernelMerkleLog.verify_chain(self, data_store)
        if ok:
            return True, len(self.hashes)
        return False, first_broken if first_broken is not None else 0


__all__ = ["MerkleLog", "FileBackend", "MemoryBackend", "verify_merkle_inclusion"]
