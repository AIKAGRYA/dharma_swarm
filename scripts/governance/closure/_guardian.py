#!/usr/bin/env python3
"""Shared reader for the Forge Measurement Guardian fitness-quorum receipt.

The One Wire invariant: internal artifacts NEVER set archive fitness. Only an
EXTERNAL acted-receipt quorum, countersigned by the Guardian, may grant
archive-fitness authority. Loops 12/13 are unblocked only when that receipt
shows eligible && fitness_authority_granted && N>=5 confirmed external acted
receipts across M>=3 distinct domains.

This reader NEVER writes and NEVER simulates the receipt. It reads the live
Guardian surface read-only and reports the exact quorum shortfall.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# Live Guardian surface (override via env for replay against a snapshot copy).
GUARDIAN_RECEIPT = os.environ.get(
    "LC_GUARDIAN_RECEIPT",
    str(Path.home() / ".dharma" / "forge_measurement_guardian" / "cycle-003-fitness-quorum-guard.json"),
)


@dataclass
class QuorumState:
    receipt_path: str
    exists: bool
    N: int            # confirmed external acted receipts
    M: int            # distinct domains
    N_required: int
    M_required: int
    eligible: bool
    authority_granted: bool
    domains: list
    raw_reason: str

    @property
    def quorum_met(self) -> bool:
        return (
            self.exists
            and self.eligible
            and self.authority_granted
            and self.N >= self.N_required
            and self.M >= self.M_required
        )

    def shortfall(self) -> str:
        if not self.exists:
            return f"Guardian receipt absent at {self.receipt_path} — no external quorum has ever been countersigned"
        parts = []
        if self.N < self.N_required:
            parts.append(f"N={self.N}/{self.N_required} confirmed external acted receipts (need {self.N_required - self.N} more)")
        if self.M < self.M_required:
            parts.append(f"M={self.M}/{self.M_required} distinct domains (need {self.M_required - self.M} more; have {self.domains})")
        if not self.eligible:
            parts.append("eligible_to_set_archive_fitness=false")
        if not self.authority_granted:
            parts.append("fitness_authority_granted=false")
        return "; ".join(parts) if parts else "quorum met"


def read_quorum(path: str = GUARDIAN_RECEIPT) -> QuorumState:
    p = Path(path)
    if not p.exists():
        return QuorumState(str(p), False, 0, 0, 5, 3, False, False, [], "receipt absent")
    d = json.loads(p.read_text())
    ar = d.get("authority_result", {})
    tg = d.get("threshold_guard", {})
    N = int(ar.get("confirmed_receipt_count", tg.get("observed_confirmed_receipts", 0)) or 0)
    M = int(ar.get("domain_count", tg.get("observed_distinct_domains", 0)) or 0)
    N_req = int(tg.get("required_confirmed_receipts", 5) or 5)
    M_req = int(tg.get("required_distinct_domains", 3) or 3)
    return QuorumState(
        receipt_path=str(p),
        exists=True,
        N=N,
        M=M,
        N_required=N_req,
        M_required=M_req,
        eligible=bool(ar.get("eligible_to_set_archive_fitness", False)),
        authority_granted=bool(ar.get("fitness_authority_granted", False)),
        domains=list(ar.get("domains", tg.get("observed_domains", []))),
        raw_reason=str(ar.get("reason_fitness_blocked", "")),
    )
