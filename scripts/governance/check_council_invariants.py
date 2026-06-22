#!/usr/bin/env python3
"""check_council_invariants.py — hermetic gate for the Council's shared invariants
(spec §2, §6).

Proves the load-bearing invariants hold no matter how the Council is exercised:
  * No correctness authority: the verdict vocabulary contains no "correct"; the
    Council can verify a faithful trace of a WRONG run but never bless it.
  * dispatch_authority stays False on every receipt.
  * Untrusted / contaminated input is quarantined before it can corroborate.
  * The decorrelated moat is real: corroboration needs >=2 evaluator AND >=2
    source families.
  * Receipts replay (same request -> same verdict + inputs_hash).

Hermetic, no keys/GPU/network. Exit non-zero on any violation.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.council import (  # noqa: E402
    VALID_VERDICTS,
    Council,
    TraceVerificationRequest,
)


def _full_request(**overrides) -> TraceVerificationRequest:
    base = dict(
        genome_id="g1",
        route_receipts=[{"genome_id": "g1"}],
        trace_receipts=[{"genome_id": "g1"}],
        scorecard={"genome_id": "g1", "score": 0.9},
        promotion_claim={
            "candidate_score": 0.9,
            "baseline_score": 0.7,
            "budget_parity_logged": True,
        },
    )
    base.update(overrides)
    return TraceVerificationRequest(**base)


def check() -> list[str]:
    findings: list[str] = []
    council = Council()

    if "correct" in VALID_VERDICTS or "incorrect" in VALID_VERDICTS:
        findings.append("verdict vocabulary leaked a correctness verdict")

    corroborated = council.verify_orchestration_trace(_full_request())
    if corroborated.verdict != "corroborated":
        findings.append(f"expected corroborated, got {corroborated.verdict}")
    if corroborated.dispatch_authority is not False:
        findings.append("dispatch_authority is not False on a normal receipt")

    quarantined = council.verify_orchestration_trace(_full_request(untrusted=True))
    if quarantined.verdict != "quarantined":
        findings.append("untrusted input was not quarantined")
    if quarantined.dispatch_authority is not False:
        findings.append("dispatch_authority is not False on a quarantine receipt")

    # decorrelation: a lone source can never corroborate
    lonely = council.verify_orchestration_trace(
        TraceVerificationRequest(genome_id="g2", scorecard={"genome_id": "g2", "score": 0.5})
    )
    if lonely.verdict == "corroborated":
        findings.append("corroborated with insufficient decorrelation (single source)")

    # correctness split: a faithful trace of a WRONG (score 0.0) run is never
    # blessed as correct, and a promotion claim with no real lift is refuted.
    riding = council.verify_orchestration_trace(
        TraceVerificationRequest(
            genome_id="gw",
            route_receipts=[{"genome_id": "gw"}],
            scorecard={"genome_id": "gw", "score": 0.0},
            promotion_claim={
                "candidate_score": 0.0,
                "baseline_score": 0.0,
                "budget_parity_logged": True,
            },
        )
    )
    if riding.verdict != "refuted":
        findings.append(f"a zero-lift promotion claim was not refuted ({riding.verdict})")

    # replay
    r1 = council.verify_orchestration_trace(_full_request())
    r2 = council.verify_orchestration_trace(_full_request())
    if r1.to_dict() != r2.to_dict():
        findings.append("council receipt is not replayable")
    return findings


def main() -> int:
    findings = check()
    if findings:
        print("check_council_invariants: FAIL")
        for f in findings:
            print(f"  - {f}")
        return 1
    print("check_council_invariants: OK — verify-not-judge invariants hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
