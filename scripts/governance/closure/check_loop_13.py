#!/usr/bin/env python3
"""Loop 13 closure check — free-evolution grind, Guardian-quorum gated (One Wire).

Loop 13 (the free-evolution / DarwinEngine archive-fitness grind) is the
terminal consumer of the One Wire invariant: it may only write archive fitness
when the Guardian has granted authority via an EXTERNAL acted-receipt quorum
(N>=5 across M>=3 domains). This check ASSERTS that authority from the live
Guardian receipt; it never hardcodes the verdict and never simulates it.

Current live state: N=3, M=1, fitness_authority_granted=false -> BLOCKED
(correct — internal evolution may run, but it CANNOT set archive fitness).

Verdicts:
  GREEN   -> Guardian granted archive-fitness authority (quorum met)
  BLOCKED -> authority not granted (the correct current state)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit  # noqa: E402
from _guardian import read_quorum, GUARDIAN_RECEIPT  # noqa: E402


def check() -> Verdict:
    q = read_quorum()
    replay = f"LC_GUARDIAN_RECEIPT={GUARDIAN_RECEIPT} python3 scripts/governance/closure/check_loop_13.py"
    if q.quorum_met:
        return Verdict(
            13, "GREEN",
            f"Free-evolution archive-fitness authority GRANTED by Guardian on real external quorum: "
            f"N={q.N}/{q.N_required}, M={q.M}/{q.M_required}; One Wire satisfied",
            real_data=True, replay_cmd=replay,
        )
    return Verdict(
        13, "BLOCKED",
        f"Free-evolution archive-fitness authority NOT granted — gated on external acted receipts "
        f"(correct, do NOT simulate): {q.shortfall()}",
        real_data=False, replay_cmd=replay,
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
