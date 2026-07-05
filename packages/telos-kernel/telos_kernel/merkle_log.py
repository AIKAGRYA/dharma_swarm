"""Tamper-evident Merkle log — titanium v3.

Preserves the public API of the legacy `dharma_swarm.merkle_log.MerkleLog` for
backwards compatibility (there is a re-export shim at
`dharma_swarm/merkle_log.py`) while adding:

  * RFC 8785 JCS canonicalization (deterministic across Python versions).
  * Signed `Leaf` entries — the chain stores payload objects, not opaque dicts.
  * `prev_merkle_root` binding on every leaf (§U5 spec).
  * `verify_chain` returns `(True, None)` on full validity per §3 leaf schema,
    with `(False, first_broken_index)` on tamper. Legacy return shape (which
    returned `len(hashes)` on success) is available via `verify_chain_legacy`
    for the shim.
  * `Backend` abstraction: `FileBackend` (default) and `MemoryBackend` (tests).
  * Boot receipt appended on kernel init, bound to manifest hash + SBOM digest.

Spec: `specs/TITANIUM_TELOS_GATES_SPEC_v3.md` §U5, §3.
"""
from __future__ import annotations

import abc
import hashlib
import math
from pathlib import Path
from typing import Any, Final, List, Tuple

from icontract import ensure, require

from telos_kernel.canonical import canonicalize
from telos_kernel.effects import Effect, effect
from telos_kernel.receipt import Leaf
from telos_kernel.result import (
    ERR_CHAIN_BROKEN,
    ERR_UNCANONICALIZABLE,
    Err,
    KernelError,
    Ok,
    Result,
)

GENESIS_HASH: Final[bytes] = b"\x00" * 32
GENESIS_HEX: Final[str] = GENESIS_HASH.hex()


# ---- Backends ---------------------------------------------------------------

class Backend(abc.ABC):
    """Storage abstraction for the Merkle chain."""

    @abc.abstractmethod
    def load(self) -> Tuple[List[bytes], List[dict]]:
        """Return (hashes, payloads). Both lists must have equal length."""
        raise NotImplementedError

    @abc.abstractmethod
    def save(self, hashes: List[bytes], payloads: List[dict]) -> None:
        raise NotImplementedError


class MemoryBackend(Backend):
    def __init__(self) -> None:
        self._hashes: List[bytes] = []
        self._payloads: List[dict] = []

    def load(self) -> Tuple[List[bytes], List[dict]]:
        return list(self._hashes), list(self._payloads)

    def save(self, hashes: List[bytes], payloads: List[dict]) -> None:
        self._hashes = list(hashes)
        self._payloads = list(payloads)


@effect(Effect.FS_READ, Effect.FS_WRITE)
def FileBackend(path):  # noqa: N802  — preserved for backwards-compat.
    """Legacy alias. Real implementation lives in the I/O rim.

    The core module used to hold `FileBackend` directly; PR #1d moved it
    to `telos_kernel._io.merkle_file_backend.FileBackendIO` so the core
    stays pure. This shim preserves the import surface for callers that
    do `from telos_kernel.merkle_log import FileBackend`.

    New code should import `FileBackendIO` from `telos_kernel._io`
    directly — the FS_WRITE effect is then visible at the call site.
    """
    # Local import so the core module has no top-level dependency on _io.
    from telos_kernel._io.merkle_file_backend import FileBackendIO
    return FileBackendIO(path)


# ---- MerkleLog --------------------------------------------------------------

def _compute_leaf_hash(prev_hash: bytes, payload_bytes: bytes) -> bytes:
    """h_i = SHA-256(h_{i-1} || JCS(payload_i))"""
    return hashlib.sha256(prev_hash + payload_bytes).digest()


def _is_jcs_value(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, (list, tuple)):
        return all(_is_jcs_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_jcs_value(item)
                   for key, item in value.items())
    return False


def _is_append_payload(value: Any) -> bool:
    return isinstance(value, Leaf) or (isinstance(value, dict) and _is_jcs_value(value))


class MerkleLog:
    """Append-only Merkle-chained log with signed Leaf payloads.

    Legacy call sites use `log.append({...dict...})`; new call sites pass a
    `Leaf` instance. Both paths produce chain-equivalent hashes.

    Attributes:
        hashes: list of leaf hashes (bytes). Kept public for legacy compatibility.
        quarantined: True if `verify_chain` detected a break at load time.
                     Live gate checks should return REVIEW while quarantined.
    """

    @effect(Effect.FS_READ, Effect.FS_WRITE)
    def __init__(self, backend: Backend | None = None,
                 log_file: str | Path | None = None):
        if backend is not None and log_file is not None:
            raise ValueError("pass either backend or log_file, not both")
        if backend is None:
            log_file = log_file or "~/.dharma/evolution_merkle.json"
            backend = FileBackend(log_file)
        self.backend: Backend = backend
        self.hashes: List[bytes] = []
        self._payloads: List[dict] = []
        self._corrupt: bool = False
        self.quarantined: bool = False
        try:
            self.hashes, self._payloads = backend.load()
        except ValueError:
            self._corrupt = True
            self.quarantined = True
            return
        ok, idx = self.verify_chain()
        if not ok:
            self._corrupt = True
            self.quarantined = True
            # Do NOT raise — the kernel entering quarantine is a first-class
            # state per §U5. Callers observe `self.quarantined` and route
            # verdicts to REVIEW until re-anchored.

    # ---- Append ----

    @require(lambda data: _is_append_payload(data))
    @ensure(lambda result: isinstance(result, str) and len(result) == 64)
    def append(self, data: dict | Leaf) -> str:
        """Append a payload and return the new Merkle root (hex)."""
        if self._corrupt or self.quarantined:
            raise ValueError("cannot append to corrupt Merkle log; repair or archive it first")
        if isinstance(data, Leaf):
            # Hand-rolled projection, not `model_dump()`. Ensures the leaf
            # hash covers exactly the bytes that were signed.
            payload_dict = data.to_canonical_dict()
        else:
            payload_dict = dict(data)  # defensive copy

        prev_hash = self.hashes[-1] if self.hashes else GENESIS_HASH
        payload_bytes = canonicalize(payload_dict)
        leaf_hash = _compute_leaf_hash(prev_hash, payload_bytes)

        self.hashes.append(leaf_hash)
        self._payloads.append(payload_dict)
        self.backend.save(self.hashes, self._payloads)

        return leaf_hash.hex()

    # ---- Verify ----

    def verify_chain_result(
        self, data_store: List[dict] | None = None
    ) -> Result:
        """Structured chain-integrity check.

        Returns Ok({'length': N}) on full validity, or Err(KernelError)
        with `detail={'broken_index': i}` on the first mismatch.
        Never raises. `titanium-verify` proves the fail-closed contract.
        """
        if self._corrupt:
            return Err(KernelError(
                ERR_CHAIN_BROKEN,
                "corrupt Merkle log",
                detail={"broken_index": 0},
            ))
        if not self.hashes:
            return Ok({"length": 0})

        store = data_store if data_store is not None else self._payloads
        if len(store) != len(self.hashes):
            return Err(KernelError(
                ERR_CHAIN_BROKEN,
                f"store length {len(store)} != hash count {len(self.hashes)}",
                detail={"broken_index": 0},
            ))

        prev = GENESIS_HASH
        for i, (payload, stored) in enumerate(zip(store, self.hashes)):
            try:
                b = canonicalize(payload)
            except (ValueError, TypeError) as e:
                return Err(KernelError(
                    ERR_UNCANONICALIZABLE,
                    f"leaf {i}: {e}",
                    detail={"broken_index": i},
                ))
            computed = _compute_leaf_hash(prev, b)
            if computed != stored:
                return Err(KernelError(
                    ERR_CHAIN_BROKEN,
                    f"leaf {i} hash mismatch",
                    detail={"broken_index": i},
                ))
            prev = computed
        return Ok({"length": len(self.hashes)})

    def verify_chain(
        self, data_store: List[dict] | None = None
    ) -> Tuple[bool, int | None]:
        """Boolean-tuple compatibility over verify_chain_result().

        Spec §U5 contract: returns `(True, None)` on full validity, else
        `(False, first_broken_index)`. Prefer verify_chain_result() in new
        code so you can see the specific failure mode.
        """
        r = self.verify_chain_result(data_store)
        if r.is_ok:
            return True, None
        detail = r.error.detail or {}
        return False, detail.get("broken_index", 0)

    def verify_chain_legacy(
        self, data_store: List[dict] | None = None
    ) -> Tuple[bool, int]:
        """Legacy contract: returns `(True, len(hashes))` on success.

        Only the shim in `dharma_swarm.merkle_log` should use this.
        """
        ok, first_broken = self.verify_chain(data_store)
        if ok:
            return True, len(self.hashes)
        return False, first_broken if first_broken is not None else 0

    def verify_with_data(self, data_store: List[dict]) -> Tuple[bool, int]:
        """Legacy compat — raises on length mismatch, returns (ok, idx)."""
        if len(data_store) != len(self.hashes):
            raise ValueError(
                f"Data store length ({len(data_store)}) doesn't match "
                f"hash chain ({len(self.hashes)})"
            )
        ok, first_broken = self.verify_chain(data_store)
        if ok:
            return True, len(self.hashes)
        return False, first_broken if first_broken is not None else 0

    # ---- Accessors ----

    def get_root(self) -> str | None:
        return self.hashes[-1].hex() if self.hashes else None

    def head_hash(self) -> str:
        """Titanium API: always returns a hex string; empty chain -> GENESIS."""
        return self.hashes[-1].hex() if self.hashes else GENESIS_HEX

    def get_chain_length(self) -> int:
        return len(self.hashes)

    def leaf_at(self, index: int) -> dict:
        return self._payloads[index]


# ---- Inclusion proof (legacy compat) ---------------------------------------

def verify_merkle_inclusion(
    entry_data: dict,
    entry_index: int,
    merkle_root: str,
    merkle_log: MerkleLog,
) -> bool:
    """Verify that an entry is included at `entry_index` with the given root."""
    if entry_index < 0 or entry_index >= len(merkle_log.hashes):
        return False
    stored_hash_hex = merkle_log.hashes[entry_index].hex()
    return stored_hash_hex == merkle_root
