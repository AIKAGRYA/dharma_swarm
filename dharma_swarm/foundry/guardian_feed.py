"""Guardian quorum feed — turn confirmed external receipts into the One Wire file.

This is the ONLY path by which Foundry work can ever authorize archive fitness,
and it is deliberately fail-closed:

- It counts quorum ONLY from externally-confirmed receipts (a non-author merge
  or an independent-leaderboard record — ring 3). Lab-local ring-1/2 receipts
  never count.
- It writes the guardian cycle file in the exact shape
  ``dharma_swarm.archive.read_one_wire_fitness_authority`` reads, but it NEVER
  sets ``fitness_authority_granted`` on its own — that flag is an explicit
  operator grant. Reaching quorum makes fitness *eligible*, not *granted*.

Constants mirror ``dharma_swarm.archive`` (N>=5 confirmed across M>=3 domains);
a test cross-checks them so they cannot drift. Kept stdlib-only so it runs on a
bare CI runner.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Mirror of dharma_swarm.archive.ONE_WIRE_* (cross-checked in tests).
REQUIRED_CONFIRMED = 5
REQUIRED_DOMAINS = 3
GUARDIAN_RECEIPT_RELPATH = Path("forge_measurement_guardian") / "cycle-003-fitness-quorum-guard.json"


@dataclass(frozen=True)
class QuorumCount:
    confirmed: int
    domains: int
    domain_breakdown: dict[str, int]

    @property
    def eligible(self) -> bool:
        return self.confirmed >= REQUIRED_CONFIRMED and self.domains >= REQUIRED_DOMAINS


def _is_confirmed(receipt: dict[str, Any]) -> bool:
    """Ring-3 test: an independent merge, or an independent-record leaderboard."""
    if receipt.get("externally_confirmed") is True:
        return True
    merge = receipt.get("merge_event") or {}
    if merge.get("state") == "MERGED" and merge.get("independent"):
        return True
    ci = receipt.get("external_ci") or {}
    return ci.get("status") == "independent_record"


def count_quorum(receipts: Iterable[dict[str, Any]]) -> QuorumCount:
    """Count confirmed external receipts and distinct domains among them."""
    confirmed = 0
    domains: dict[str, int] = {}
    for receipt in receipts:
        if not _is_confirmed(receipt):
            continue
        confirmed += 1
        domain = (receipt.get("stratified") or {}).get("domain", "unknown")
        domains[domain] = domains.get(domain, 0) + 1
    return QuorumCount(confirmed=confirmed, domains=len(domains), domain_breakdown=domains)


def build_guardian_receipt(
    receipts: Iterable[dict[str, Any]], *, grant_authority: bool = False
) -> dict[str, Any]:
    """Build the guardian cycle payload (schema of archive.read_one_wire_...).

    ``grant_authority`` is the explicit operator grant; even when quorum is met,
    the default is False so archive fitness stays fail-closed until a human says
    otherwise.
    """
    quorum = count_quorum(receipts)
    granted = bool(grant_authority and quorum.eligible)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "dharma_swarm.foundry.guardian_feed",
        "threshold_guard": {
            "required_confirmed_receipts": REQUIRED_CONFIRMED,
            "required_distinct_domains": REQUIRED_DOMAINS,
            "observed_confirmed_receipts": quorum.confirmed,
            "observed_distinct_domains": quorum.domains,
        },
        "authority_result": {
            "confirmed_receipt_count": quorum.confirmed,
            "domain_count": quorum.domains,
            "domain_breakdown": quorum.domain_breakdown,
            "eligible_to_set_archive_fitness": quorum.eligible,
            "fitness_authority_granted": granted,
            "archive_fitness_changed": False,
        },
    }


def write_guardian_receipt(payload: dict[str, Any], *, state_dir: Path) -> Path:
    """Write the guardian cycle file to ``<state_dir>/forge_measurement_guardian/``.

    ``state_dir`` is required and supplied by the caller (the organism's state
    root, typically ``~/.dharma``). guardian_feed deliberately does not assume a
    home path: ~/.dharma ownership stays with the caller / RuntimeStateStore
    (anti-slop Rule 1), and the module stays a pure function of its inputs.
    """
    root = Path(state_dir)
    path = root / GUARDIAN_RECEIPT_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    temp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        with temp.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)
    return path
