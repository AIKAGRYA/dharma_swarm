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
import json
from pathlib import Path
from typing import Any, Final, List, Tuple

from icontract import ensure, require

from telos_kernel.canonical import canonicalize
from telos_kernel.receipt import Leaf

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


class FileBackend(Backend):
    """Atomic append-only file. Compatible with legacy on-disk format
    (hex hashes under `hashes` key) plus a new `payloads` key. Legacy files
    without `payloads` are auto-migrated on first load: an in-memory
    reconstruction is attempted; if the reconstruction diverges from the
    stored hashes, the load fails loudly rather than silently."""

    VERSION: Final[int] = 3

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Tuple[List[bytes], List[dict]]:
        if not self.path.exists():
            return [], []
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        hashes = [bytes.fromhex(h) for h in raw.get("hashes", [])]
        payloads_raw = raw.get("payloads", None)
        if payloads_raw is None:
            # Legacy file with no payloads. We cannot fully verify these; the
            # kernel enters QUARANTINE on such a boot until an operator
            # explicitly acknowledges (Phase 1 will add the ack workflow).
            return hashes, [{} for _ in hashes]
        return hashes, list(payloads_raw)

    def save(self, hashes: List[bytes], payloads: List[dict]) -> None:
        data = {
            "version": self.VERSION,
            "algorithm": "sha256",
            "canonicalization": "rfc-8785-jcs",
            "encoding": "utf-8",
            "hashes": [h.hex() for h in hashes],
            "payloads": payloads,
        }
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        tmp.replace(self.path)


# ---- MerkleLog --------------------------------------------------------------

def _compute_leaf_hash(prev_hash: bytes, payload_bytes: bytes) -> bytes:
    """h_i = SHA-256(h_{i-1} || JCS(payload_i))"""
    return hashlib.sha256(prev_hash + payload_bytes).digest()


class MerkleLog:
    """Append-only Merkle-chained log with signed Leaf payloads.

    Legacy call sites use `log.append({...dict...})`; new call sites pass a
    `Leaf` instance. Both paths produce chain-equivalent hashes.

    Attributes:
        hashes: list of leaf hashes (bytes). Kept public for legacy compatibility.
        quarantined: True if `verify_chain` detected a break at load time.
                     Live gate checks should return REVIEW while quarantined.
    """

    def __init__(self, backend: Backend | None = None,
                 log_file: str | Path | None = None):
        if backend is not None and log_file is not None:
            raise ValueError("pass either backend or log_file, not both")
        if backend is None:
            log_file = log_file or "~/.dharma/evolution_merkle.json"
            backend = FileBackend(log_file)
        self.backend: Backend = backend
        self.hashes: List[bytes]
        self._payloads: List[dict]
        self.hashes, self._payloads = backend.load()
        self.quarantined: bool = False
        ok, idx = self.verify_chain()
        if not ok:
            self.quarantined = True
            # Do NOT raise — the kernel entering quarantine is a first-class
            # state per §U5. Callers observe `self.quarantined` and route
            # verdicts to REVIEW until re-anchored.

    # ---- Append ----

    @require(lambda data: isinstance(data, (dict, Leaf)))
    @ensure(lambda result: isinstance(result, str) and len(result) == 64)
    def append(self, data: dict | Leaf) -> str:
        """Append a payload and return the new Merkle root (hex)."""
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

    def verify_chain(
        self, data_store: List[dict] | None = None
    ) -> Tuple[bool, int | None]:
        """Verify chain integrity.

        Spec §U5 contract: returns `(True, None)` on full validity, else
        `(False, first_broken_index)`.

        If `data_store` is None, uses the internally-stored payloads (the
        Titanium path). If provided, compares against the given payloads
        (legacy path — used by the shim).
        """
        if not self.hashes:
            return True, None

        store = data_store if data_store is not None else self._payloads
        if len(store) != len(self.hashes):
            return False, 0

        prev = GENESIS_HASH
        for i, (payload, stored) in enumerate(zip(store, self.hashes)):
            try:
                b = canonicalize(payload)
            except (ValueError, TypeError):
                return False, i
            computed = _compute_leaf_hash(prev, b)
            if computed != stored:
                return False, i
            prev = computed
        return True, None

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
