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

from telos_kernel._io.effect import Effect, effect
from telos_kernel.merkle_log import Backend


class FileBackendIO(Backend):
    """Atomic-write JSON file backend for MerkleLog.

    Superset of the in-tree FileBackend: adds atomic swap via tempfile +
    os.replace so a crashed process cannot leave a partial log on disk.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @effect(Effect.FS_READ)
    def load(self) -> tuple[list[bytes], list[dict]]:
        if not self.path.exists():
            return [], []
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        hashes = [bytes.fromhex(h) for h in raw.get("hashes", [])]
        payloads = raw.get("payloads")
        if payloads is None:
            # Legacy files without payloads \u2014 chain hashes-only, no
            # deep verify possible.
            return hashes, [{} for _ in hashes]
        return hashes, payloads

    @effect(Effect.FS_WRITE)
    def save(self, hashes: Iterable[bytes], payloads: Iterable[dict]) -> None:
        data = {
            "hashes": [h.hex() for h in hashes],
            "payloads": list(payloads),
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
