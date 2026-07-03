"""Backwards-compat shim.

The canonical `MerkleLog` implementation lives in `telos_kernel.merkle_log`
under `packages/telos-kernel/`. This module re-exports the public surface so
legacy callers (`from dharma_swarm.merkle_log import MerkleLog`, etc.) keep
working without modification.

The kernel version is a strict superset — it adds JCS canonicalization, signed
`Leaf` payloads, `MemoryBackend`, and a titanium `verify_chain()` return shape.
Legacy callers get the legacy `verify_chain` return shape (`(True, N)` on
success) via the `MerkleLog.verify_chain_legacy` alias below.

See `specs/TITANIUM_TELOS_GATES_SPEC_v3.md` §U5.
"""
from __future__ import annotations

from telos_kernel.merkle_log import (  # noqa: F401
    FileBackend,
    MemoryBackend,
    MerkleLog as _KernelMerkleLog,
    verify_merkle_inclusion,
)


class MerkleLog(_KernelMerkleLog):
    """Legacy-compatible façade over the kernel MerkleLog.

    Legacy call sites expect `verify_chain(data_store=None)` to return
    `(True, len(hashes))` on success. The kernel returns `(True, None)` per
    spec §U5. We route legacy behavior through `verify_chain_legacy` when
    called via this subclass, preserving the exact prior contract.
    """

    def verify_chain(self, data_store=None):  # type: ignore[override]
        # Call the kernel's titanium verify_chain directly and re-shape the
        # result to the legacy contract. Do NOT call self.verify_chain_legacy
        # here — that method delegates back to verify_chain and would recurse.
        ok, first_broken = _KernelMerkleLog.verify_chain(self, data_store)
        if ok:
            return True, len(self.hashes)
        return False, first_broken if first_broken is not None else 0


__all__ = ["MerkleLog", "FileBackend", "MemoryBackend", "verify_merkle_inclusion"]
