#!/usr/bin/env python3
"""Bounded-replay closure check for the Frontier Council verifier (Stage 1).

Runs deterministic fixture cases through the verifier and asserts each produces
the expected verdict with NO action authority. Hermetic — no network, no keys.
Writes a report under reports/sensemaking_organ/stage0_1/<date>/ and prints
FRONTIER_COUNCIL_REPLAY=pass|fail (exit 0/1).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dharma_swarm.world_radar.frontier_council import (  # noqa: E402
    CORROBORATED,
    INSUFFICIENT,
    QUARANTINED,
    REFUTED,
    EvidenceRef,
    FrontierCouncilInput,
    evaluate_boundary_signal,
)

_CASES = [
    ("two_decorrelated_supports", CORROBORATED, FrontierCouncilInput(
        claim="claim A", input_signal_hash="sha256:a", evidence_refs=[
            EvidenceRef("arxiv", True, 0.8), EvidenceRef("repro", True, 0.7)])),
    ("high_quality_refutation", REFUTED, FrontierCouncilInput(
        claim="claim B", input_signal_hash="sha256:b", evidence_refs=[
            EvidenceRef("audit", False, 0.9)])),
    ("single_family_only", INSUFFICIENT, FrontierCouncilInput(
        claim="claim C", input_signal_hash="sha256:c", evidence_refs=[
            EvidenceRef("blog", True, 0.95), EvidenceRef("blog", True, 0.95)])),
    ("poisoned_high_risk", QUARANTINED, FrontierCouncilInput(
        claim="claim D", input_signal_hash="sha256:d", instruction_risk="high",
        evidence_refs=[EvidenceRef("x", True, 0.9)])),
]


def main() -> int:
    results, failures = [], []
    for name, expected, inp in _CASES:
        r = evaluate_boundary_signal(inp)
        ok = r.verdict == expected and r.no_action_authority and not r.dispatch_authority
        results.append({
            "case": name, "expected": expected, "verdict": r.verdict,
            "corroboration_count": r.corroboration_count,
            "source_family_count": r.source_family_count,
            "no_action_authority": r.no_action_authority,
            "dispatch_authority": r.dispatch_authority, "passed": ok,
        })
        if not ok:
            failures.append(name)

    passed = not failures
    report = {
        "check": "frontier_council_replay",
        "stage": "seeing-organ Stage 1 — Frontier Council verifier",
        "checked_count": len(_CASES),
        "passed": passed,
        "failures": failures,
        "all_receipts_no_authority": all(r["no_action_authority"] and not r["dispatch_authority"] for r in results),
        "cases": results,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    print(json.dumps(report, indent=2))

    out = (
        Path(__file__).resolve().parents[2]
        / "reports/sensemaking_organ/stage0_1"
        / f"{datetime.now(timezone.utc):%Y%m%d}" / "frontier_council_replay.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nFRONTIER_COUNCIL_REPLAY={'pass' if passed else 'fail'}  (report: {out})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
