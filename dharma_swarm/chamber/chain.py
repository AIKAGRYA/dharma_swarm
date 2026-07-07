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
from pathlib import Path
from typing import Any

from dharma_swarm.chamber.traces import stable_digest


class BrokenChainError(RuntimeError):
    """The existing chain fails verification; appending would launder it."""


def verify_chain(rows: list[dict[str, Any]], label: str) -> None:
    prev = ""
    for i, row in enumerate(rows):
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
    """Stamp ``body`` with prev_digest + digest and append it. Verifies the
    existing chain first; returns the stamped row."""
    chain = read_chain(path)
    row = dict(body)
    row["prev_digest"] = chain[-1]["digest"] if chain else ""
    row["digest"] = stable_digest({k: v for k, v in row.items() if k != "digest"})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return row


__all__ = ["BrokenChainError", "append_chained", "read_chain", "verify_chain"]
