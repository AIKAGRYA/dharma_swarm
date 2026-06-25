#!/usr/bin/env python3
"""check_claim_evidence_binding.py — report the graded claim/evidence binding.

A THIN CLI over the graded evaluator in check_track_status.py. It does NOT
re-implement evaluate_track; it renders, per active track, the strongest passing
evidence grade vs the required min_evidence_grade and a binding verdict
(BOUND / UNDERGRADED / NOT-SHIPPABLE). This is the operator-facing read of the
Pudgala Forge anti-slop bar:

    A claim ships only when its strongest evidence meets the required grade.

Advisory by default (--warn-only) so it can be wired into governance-all without
gating merges while the ladder is socialised. Promotion to a hard gate is an
operator decision (raise the floor / flip --warn-only off), never automatic.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Import the single owner of the evaluation logic; never re-derive it here.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_track_status import (  # noqa: E402
    ACTIVE_TRACK_PATH,
    evaluate_track,
    grade_name,
    load_active_track,
    normalize_portfolio,
)


def _verdict(r: dict) -> str:
    if r["shippable"]:
        return "BOUND"
    if r.get("strongest_grade", 0) < r.get("min_evidence_grade", 2):
        return "UNDERGRADED"
    return "NOT-SHIPPABLE"


def run(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--warn-only", action="store_true", default=True,
                    help="advisory mode (default): always exit 0")
    ap.add_argument("--enforce", dest="warn_only", action="store_false",
                    help="exit non-zero if any active track is UNDERGRADED")
    ap.add_argument("--emit-receipt", action="store_true",
                    help="append a VerifiedMachineReceipt of this binding run "
                         "to ~/.dharma/witness/claim_evidence_receipts.jsonl")
    args = ap.parse_args(argv)

    if not ACTIVE_TRACK_PATH.exists():
        print(f"ERROR: {ACTIVE_TRACK_PATH} not found", file=sys.stderr)
        return 0 if args.warn_only else 2

    portfolio = normalize_portfolio(load_active_track(ACTIVE_TRACK_PATH))
    tracks = portfolio["active_tracks"]
    undergraded = 0

    print("Claim/Evidence binding (graded anti-slop bar)\n" + "=" * 46)
    for t in tracks:
        if str(t.get("status", "")).upper() not in {"ACTIVE", "SHIPPABLE"}:
            continue
        r = evaluate_track(t)
        verdict = _verdict(r)
        if verdict == "UNDERGRADED":
            undergraded += 1
        sg = grade_name(r.get("strongest_grade", 0))
        mg = grade_name(r.get("min_evidence_grade", 2))
        print(f"  [{verdict:>14}] {t.get('id')}")
        print(f"                   strongest={sg}  required={mg}"
              f"  rigorous={r.get('has_rigorous_evidence')}")
        for blk in r.get("ship_blocks", []):
            print(f"                   - {blk}")

    print("-" * 46)
    print(f"{len(tracks)} active track(s); {undergraded} undergraded "
          f"(below required evidence grade).")

    exit_code = 0 if args.warn_only else (1 if undergraded else 0)

    if args.emit_receipt:
        _emit_receipt(undergraded=undergraded, exit_code=exit_code)

    return exit_code


def _emit_receipt(*, undergraded: int, exit_code: int) -> None:
    """Append a hash-chained VerifiedMachineReceipt of this binding run. The
    receipt IS the proof the gate ran — verifiable by check_receipt_valid."""
    try:
        from dharma_swarm.spine.receipt import (
            VerifiedMachineReceipt,
            append_machine_receipt,
        )
    except ImportError as exc:  # advisory: never crash the gate on a missing dep
        print(f"(receipt skipped: {exc})", file=sys.stderr)
        return
    receipt = VerifiedMachineReceipt(
        claim_id="claim-evidence-binding",
        command="python3 scripts/governance/check_claim_evidence_binding.py",
        cwd=str(ACTIVE_TRACK_PATH.parent.parent.parent),
        actor="make claim-evidence",
        exit_code=exit_code,
        generated_by="check_claim_evidence_binding.py",
        attributes={"undergraded_tracks": undergraded},
    )
    chained = append_machine_receipt(receipt)
    print(f"receipt appended (digest {chained.digest[:12]}…, verify={chained.verify()})")


if __name__ == "__main__":
    raise SystemExit(run())
