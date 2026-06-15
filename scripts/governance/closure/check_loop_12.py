#!/usr/bin/env python3
"""Loop 12 closure check — Guardian fitness-quorum gate (One Wire).

Loop 12 (and 13) close only when the Forge Measurement Guardian has
countersigned an EXTERNAL acted-receipt quorum: eligible &&
fitness_authority_granted && N>=5 confirmed external acted receipts across
M>=3 distinct domains. This check ASSERTS that state from the live Guardian
receipt — it never hardcodes the verdict and never simulates the receipt.

Current live state: N=3, M=1 -> BLOCKED (correct, load-bearing).

Verdicts:
  GREEN   -> quorum met on the real Guardian receipt (archive-fitness authority granted)
  BLOCKED -> quorum unmet (the correct current state); exact shortfall reported
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit  # noqa: E402
from _guardian import read_quorum, GUARDIAN_RECEIPT  # noqa: E402


def check() -> Verdict:
    q = read_quorum()
    replay = f"LC_GUARDIAN_RECEIPT={GUARDIAN_RECEIPT} python3 scripts/governance/closure/check_loop_12.py"
    if q.quorum_met:
        return Verdict(
            12, "GREEN",
            f"One Wire quorum MET on real Guardian receipt: N={q.N}/{q.N_required}, "
            f"M={q.M}/{q.M_required} domains={q.domains}, eligible && fitness_authority_granted; "
            f"archive-fitness authority granted by external acted receipts",
            real_data=True, replay_cmd=replay,
        )
    return Verdict(
        12, "BLOCKED",
        f"One Wire quorum UNMET (correct, do NOT simulate): {q.shortfall()}",
        real_data=False, replay_cmd=replay,
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
