"""Digest-chained JSONL — the chamber's shared tamper-evident append log.

Byte-compatible with the governance checker's ``expect_chain`` mode
(scripts/governance/check_track_status.py) and the spine's
VerifiedMachineReceipt chain conventions: row digest =
sha256(canonical_json(row minus digest)); ``prev_digest`` IS covered by the
digest; row 0 carries an empty prev_digest (genesis anchor); appending to a
broken chain is refused rather than laundered.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dharma_swarm.chamber.traces import stable_digest

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX host (Windows)
    fcntl = None  # type: ignore[assignment]


class BrokenChainError(RuntimeError):
    """The existing chain fails verification; appending would launder it."""


@contextmanager
def _append_lock(target: Path):
    """Serialize read-tip -> stamp -> append so concurrent writers cannot both
    link to the same tip and fork the chain (which would brick every future
    read). Advisory ``flock`` on a sidecar lock file — host-local, mirrors
    dharma_swarm/spine/receipt.py::_append_lock. Degrades to no-op (prior
    lock-free behavior) on non-POSIX hosts rather than failing."""
    if fcntl is None:  # pragma: no cover - non-POSIX host
        yield
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_name(target.name + ".lock")
    with lock_path.open("w") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def verify_chain(rows: list[dict[str, Any]], label: str) -> None:
    prev = ""
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise BrokenChainError(f"{label} row {i}: not a JSON object")
        stored = str(row.get("digest", ""))
        if not stored or stored != stable_digest(
            {k: v for k, v in row.items() if k != "digest"}
        ):
            raise BrokenChainError(f"{label} row {i}: digest mismatch")
        link = str(row.get("prev_digest", ""))
        if i == 0 and link:
            raise BrokenChainError(f"{label} row 0: non-empty prev_digest")
        if i > 0 and link != prev:
            raise BrokenChainError(f"{label} row {i}: prev_digest broken")
        prev = stored


def read_chain(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()]
    verify_chain(rows, str(path))
    return rows


def append_chained(path: Path, body: dict[str, Any]) -> dict[str, Any]:
    """Stamp ``body`` with prev_digest + digest and append it. The read-tip →
    stamp → append critical section runs under an exclusive lock so concurrent
    appenders cannot fork the chain (the tip is re-read inside the lock)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with _append_lock(path):
        chain = read_chain(path)
        row = dict(body)
        row["prev_digest"] = chain[-1]["digest"] if chain else ""
        row["digest"] = stable_digest(
            {k: v for k, v in row.items() if k != "digest"})
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    return row


__all__ = ["BrokenChainError", "append_chained", "read_chain", "verify_chain"]
