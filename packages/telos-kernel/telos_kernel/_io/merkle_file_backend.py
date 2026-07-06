"""Filesystem-backed Merkle log storage.

The core `merkle_log.py` provides `MerkleLog` (pure logic) and
`MemoryBackend` (pure in-memory storage). This module provides
`FileBackendIO`, which persists to a JSON file. Kept out of core because:

  - Every method touches the filesystem (Effect.FS_READ / FS_WRITE).
  - The atomic-write dance (tempfile + os.replace) is not verifiable by
    titanium-verify \u2014 it depends on kernel-level POSIX semantics.

Callers get a `FileBackend`-shaped object; the core `MerkleLog`
constructor doesn't need to know it came from the rim.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable

from telos_kernel.effects import Effect, effect
from telos_kernel.merkle_log import Backend


class FileBackendIO(Backend):
    """Atomic-write JSON file backend for MerkleLog.

    Superset of the in-tree FileBackend: adds atomic swap via tempfile +
    os.replace so a crashed process cannot leave a partial log on disk.
    """

    VERSION = 3

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @effect(Effect.FS_READ)
    def load(self) -> tuple[list[bytes], list[dict]]:
        if not self.path.exists():
            return [], []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("corrupt Merkle log: unreadable JSON") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("hashes"), list):
            raise ValueError("corrupt Merkle log: expected object with hashes list")
        try:
            hashes = [bytes.fromhex(h) for h in raw["hashes"]]
        except (TypeError, ValueError) as exc:
            raise ValueError("corrupt Merkle log: bad hash encoding") from exc
        if any(len(h) != 32 for h in hashes):
            raise ValueError("corrupt Merkle log: bad hash length")
        stored_count = raw.get("count")
        if stored_count is not None and stored_count != len(hashes):
            raise ValueError("corrupt Merkle log: stored count mismatch")
        payloads = raw.get("payloads")
        if payloads is None:
            # Legacy files without payloads cannot be deeply verified; the
            # core log will enter quarantine if reconstructed payloads diverge.
            return hashes, [{} for _ in hashes]
        if not isinstance(payloads, list) or len(payloads) != len(hashes):
            raise ValueError("corrupt Merkle log: payload count mismatch")
        return hashes, list(payloads)

    @effect(Effect.FS_WRITE)
    def save(self, hashes: Iterable[bytes], payloads: Iterable[dict]) -> None:
        hashes_list = list(hashes)
        payloads_list = list(payloads)
        data = {
            "version": self.VERSION,
            "algorithm": "sha256",
            "canonicalization": "rfc-8785-jcs",
            "encoding": "utf-8",
            "hashes": [h.hex() for h in hashes_list],
            "count": len(hashes_list),
            "payloads": payloads_list,
        }
        # Atomic write: tempfile in the same directory + os.replace.
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(self.path.parent),
            prefix=self.path.name + ".", suffix=".tmp",
            delete=False,
        ) as tmp:
            json.dump(data, tmp, indent=2, sort_keys=True)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_name = tmp.name
        os.replace(tmp_name, self.path)
