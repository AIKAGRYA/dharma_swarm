#!/usr/bin/env python3
"""Bounded-replay closure check for Stage 2 — Shakti reads the world (read-only).

Replays deterministic fixture receipts through ``world_warrant_pressure`` and
asserts the seam holds: corroborated → exactly one ADVISORY pressure with
``dispatch_authority`` False; refuted / insufficient / quarantined → none; a
receipt that claims action authority is defensively dropped. Hermetic — no
network, no keys, no owner mutation.

Writes a report under reports/sensemaking_organ/stage2/<date>/ and prints
WORLD_WARRANT_HANDOFF=pass|fail (exit 0/1).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dharma_swarm.world_radar.frontier_council import (  # noqa: E402
    EvidenceRef,
    FrontierCouncilInput,
    evaluate_boundary_signal,
)
from dharma_swarm.world_radar.warrant_handoff import world_warrant_pressure  # noqa: E402

_CORROBORATED = [EvidenceRef("arxiv", True, 0.8), EvidenceRef("repro", True, 0.7)]
_REFUTED = [EvidenceRef("audit", False, 0.9)]
_INSUFFICIENT = [EvidenceRef("blog", True, 0.95), EvidenceRef("blog", True, 0.95)]


def _receipt(refs, instruction_risk="low", safe=True):
    return evaluate_boundary_signal(
        FrontierCouncilInput(
            claim="signal", input_signal_hash="sha256:s", evidence_refs=refs,
            safe=safe, instruction_risk=instruction_risk,
        )
    )


def main() -> int:
    corroborated = _receipt(_CORROBORATED)
    poisoned_authority = {**corroborated.__dict__, "dispatch_authority": True}

    cases = [
        ("corroborated_yields_one_advisory_pressure", [corroborated], 1, False),
        ("refuted_yields_none", [_receipt(_REFUTED)], 0, False),
        ("insufficient_yields_none", [_receipt(_INSUFFICIENT)], 0, False),
        ("quarantined_high_risk_yields_none",
         [_receipt(_CORROBORATED, instruction_risk="high")], 0, False),
        ("quarantined_unsafe_yields_none",
         [_receipt(_CORROBORATED, safe=False)], 0, False),
        ("authority_claiming_receipt_dropped", [poisoned_authority], 0, False),
    ]

    results, failures = [], []
    for name, receipts, expected_n, _ in cases:
        pressures = world_warrant_pressure(receipts)
        # The invariant that must hold on EVERY projection: hands stay down.
        authority_clean = all(
            (not p.dispatch_authority) and p.no_action_authority and p.is_advisory
            for p in pressures
        )
        ok = len(pressures) == expected_n and authority_clean
        results.append({
            "case": name, "expected_pressures": expected_n,
            "got_pressures": len(pressures),
            "all_advisory_no_dispatch": authority_clean, "passed": ok,
        })
        if not ok:
            failures.append(name)

    passed = not failures
    report = {
        "check": "world_warrant_handoff",
        "stage": "seeing-organ Stage 2 — Shakti reads the world (read-only)",
        "checked_count": len(cases),
        "passed": passed,
        "failures": failures,
        "dispatch_authority_held_false": all(r["all_advisory_no_dispatch"] for r in results),
        "cases": results,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    print(json.dumps(report, indent=2))

    out = (
        Path(__file__).resolve().parents[2]
        / "reports/sensemaking_organ/stage2"
        / f"{datetime.now(timezone.utc):%Y%m%d}" / "world_warrant_handoff.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nWORLD_WARRANT_HANDOFF={'pass' if passed else 'fail'}  (report: {out})")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
