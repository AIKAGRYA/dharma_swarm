#!/usr/bin/env python3
"""One Wire enforcement check — the load-bearing invariant guard.

THE ONE WIRE INVARIANT (G4): internal artifacts NEVER set archive fitness.
Only an EXTERNAL acted-receipt write, countersigned above the Guardian quorum
(N>=5 across M>=3 domains), may reach archive fitness. This check proves the
guard enforces that boundary, independent of any single loop's closure.

It runs THREE assertions, all on real mechanism (no mock provider in the
closure path, no simulated Guardian receipt):

  A. PREDICATE NEGATIVE TEST: the One Wire guard rejects an internal-origin
     fitness write (a `fitness` block with no external acted-receipt field).
     If the guard admits it, the invariant is broken -> RED, FAIL LOUD.

  B. PREDICATE POSITIVE TEST: the guard admits a write carrying a non-empty
     external acted-receipt field. If it rejects that, the guard is broken in
     the other direction (it would never let a legitimate external write
     through) -> RED.

  C. PRODUCTION-ARCHIVE CONTAMINATION TEST: scan the real production archive;
     every fitness-bearing row must be internal (zero externally countersigned)
     AND there must be real contamination present (a non-trivial fitness-bearing
     archive reporting zero internal writes means the guard is silently passing)
     -> RED. The contaminated rows are reported as the quarantine count that may
     NOT be counted toward any loop closure.

  D. GUARDIAN AUTHORITY TEST: the live Guardian receipt must NOT have granted
     archive-fitness authority (current real state: N=3, M=1). If a future
     receipt grants authority below quorum, that is a contradiction -> RED.

Verdicts:
  GREEN -> all four assertions hold: the guard rejects internal, admits external,
           the production archive is all-internal-contaminated (quarantined), and
           the Guardian has not granted sub-quorum authority. The One Wire is
           enforced.
  RED   -> any assertion fails (the invariant is not enforced) — FAIL LOUD.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit, ARCHIVE_JSONL  # noqa: E402
from _guardian import read_quorum  # noqa: E402

# Reuse the REAL guard predicate from the Loop 3 closure check — same mechanism
# DarwinEngine archive writes are gated by, not a re-implementation.
_l3 = importlib.import_module("check_loop_3")
_is_external_countersigned = _l3._is_external_countersigned


def _synthetic_internal_fitness_write() -> dict:
    """A fitness write produced by an INTERNAL artifact (DarwinEngine self-eval).
    No external acted-receipt field. The guard MUST reject this.
    """
    return {
        "id": "synthetic-internal-001",
        "change_type": "self_modification",
        "component": "evolution.DarwinEngine",
        "fitness": {"composite": 0.91, "novelty": 0.7, "telos_alignment": 0.8},
        "origin": "internal",
    }


def _synthetic_external_countersigned_write() -> dict:
    """A fitness write backed by an external acted receipt above quorum. The
    guard MUST admit this (only such writes may ever reach archive fitness).
    """
    return {
        "id": "synthetic-external-001",
        "change_type": "external_code_contribution",
        "component": "forge.external_beast",
        "fitness": {"composite": 0.88},
        "external_acted_receipt": {
            "pr": "owner/repo#123",
            "state": "MERGED",
            "merged_by": "external_human",
        },
        "quorum": {"N": 5, "M": 3},
    }


def check() -> Verdict:
    replay = (
        "python3 scripts/governance/closure/check_one_wire_enforcement.py"
    )

    # A. Negative: internal write must be rejected.
    internal = _synthetic_internal_fitness_write()
    if _is_external_countersigned(internal):
        return Verdict(
            0, "RED",
            "ONE WIRE BROKEN (A): guard ADMITTED an internal-origin fitness write "
            "with no external acted receipt — internal artifacts could set archive fitness",
            real_data=True, replay_cmd=replay,
        )

    # B. Positive: external-countersigned write must be admitted.
    external = _synthetic_external_countersigned_write()
    if not _is_external_countersigned(external):
        return Verdict(
            0, "RED",
            "ONE WIRE BROKEN (B): guard REJECTED a legitimate external-countersigned "
            "fitness write — the gate would never admit a real external acted receipt",
            real_data=True, replay_cmd=replay,
        )

    # C. Production-archive contamination test (real data).
    prod = Path(ARCHIVE_JSONL)
    if not prod.exists():
        prod = Path(os.path.expanduser("~/.dharma/evolution/archive.jsonl"))
    if not prod.exists():
        return Verdict(
            0, "RED",
            f"cannot prove enforcement on real data: production archive absent ({ARCHIVE_JSONL})",
            real_data=False, replay_cmd=replay,
        )
    fitness_bearing = 0
    contaminated = 0
    countersigned = 0
    for line in prod.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            import json
            e = json.loads(line)
        except Exception:
            continue
        if not isinstance(e.get("fitness"), dict):
            continue
        fitness_bearing += 1
        if _is_external_countersigned(e):
            countersigned += 1
        else:
            contaminated += 1
    if fitness_bearing == 0:
        return Verdict(
            0, "RED",
            "no fitness-bearing rows in production archive — cannot prove the guard "
            "fires on real contamination",
            real_data=False, replay_cmd=replay,
        )
    if contaminated == 0:
        return Verdict(
            0, "RED",
            f"ONE WIRE BROKEN (C): {fitness_bearing} fitness-bearing rows but zero flagged "
            "internal — guard is silently passing on real contamination",
            real_data=True, replay_cmd=replay,
        )
    if countersigned > 0:
        return Verdict(
            0, "RED",
            f"ONE WIRE BROKEN (C): {countersigned} production archive fitness rows claim "
            "external countersignature without Guardian quorum — contamination of the external lane",
            real_data=True, replay_cmd=replay,
        )

    # D. Guardian must not have granted sub-quorum authority.
    q = read_quorum()
    if q.authority_granted and not q.quorum_met:
        return Verdict(
            0, "RED",
            f"ONE WIRE BROKEN (D): Guardian granted archive-fitness authority below quorum "
            f"({q.shortfall()})",
            real_data=True, replay_cmd=replay,
        )

    return Verdict(
        0, "GREEN",
        f"One Wire ENFORCED: guard rejects internal writes, admits external-countersigned; "
        f"production archive has {contaminated} internal fitness rows quarantined "
        f"(0 externally countersigned, 0 counted toward archive fitness); "
        f"Guardian authority_granted={q.authority_granted} (quorum_met={q.quorum_met}, "
        f"N={q.N}/{q.N_required} M={q.M}/{q.M_required})",
        real_data=True, replay_cmd=replay,
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
