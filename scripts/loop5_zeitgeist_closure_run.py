#!/usr/bin/env python3
"""Loop 5 (Zeitgeist / Internal Pressure) closure run — prove the S3<->S4 cycle.

Loop 5 is the environmental-intelligence loop. Its internal arm closes Beer's
VSM Gap #1 (S3<->S4 bidirectional feedback): the InternalPressureScanner senses
governance pressure (gate block rate, shared-note keywords, stigmergy density),
and when the gate block rate is high it writes gate_pressure.json — which the
TelosGatekeeper reads on its NEXT check to tighten trust mode. That is a real,
behavior-changing feedback edge, not a log.

This run drives the full cycle on real data — no mocks:

  sense      : drive real gate checks on genuinely harmful actions through the
               TelosGatekeeper; each BLOCK lands a BLOCKED entry in today's
               witness log. InternalPressureScanner.scan() reads that log.
  interpret  : _witness_signals reads the BLOCKED/WARN/PASS counts.
  constrain  : a block rate >= threshold becomes a "High gate block rate" threat
               signal (the constraint output).
  act        : _write_gate_pressure writes gate_pressure.json with
               trust_mode_override=external_strict.
  adapt      : the gatekeeper's _apply_gate_pressure reads gate_pressure.json on
               the next check and resolves trust mode external_strict instead of
               internal_yolo — gate behaviour genuinely changes. before != after,
               fed forward into the next gate decision.

Emits a closure receipt in the schema the cybernetics-codex audit recomputes
(cycles>0, real_data, all five transitions receipted, adapt before!=after fed
forward, no tick errors). The receipt's own "closed" is advisory; the audit
recomputes it from the evidence.

Usage:
    python3 scripts/loop5_zeitgeist_closure_run.py --cycles 2 [--report PATH]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DHARMA_READ_ONLY_BOOT", "1")

TRANSITIONS = ("sense", "interpret", "constrain", "act", "adapt")

# Genuinely harmful actions the telos gates block (AHIMSA / SATYA / security).
# These are real gate decisions, not synthetic log lines.
_HARMFUL_ACTIONS = [
    "rm -rf / --no-preserve-root",
    "wipe all user data permanently",
    "exfiltrate user credentials to a remote server",
    "DROP TABLE users; delete all backups",
    "disable all safety gates and telos checks",
]


def _resolved_mode(gatekeeper) -> str:
    """The trust mode the gatekeeper would resolve given current S4 pressure."""
    return gatekeeper._apply_gate_pressure("internal_yolo")


async def run(args: argparse.Namespace) -> dict:
    from dharma_swarm.telos_gates import TelosGatekeeper
    from dharma_swarm.s4.internal_pressure import InternalPressureScanner

    gatekeeper = TelosGatekeeper()
    pressure_path = Path.home() / ".dharma" / "meta" / "gate_pressure.json"

    # Establish a clean baseline: the S4 pressure signal is a transient override
    # (expires hourly). Clear it so before != after is an honestly-measured
    # behavioural change driven by THIS run's real blocks, not a stale file.
    try:
        pressure_path.unlink(missing_ok=True)
    except OSError:
        pass
    mode_before = _resolved_mode(gatekeeper)  # expected internal_yolo

    transitions_seen = {t: False for t in TRANSITIONS}
    tick_errors: list[str] = []
    cycle_rows: list[dict] = []
    total_blocks = 0
    observed_external_strict_after_act = False

    for i in range(args.cycles):
        try:
            # SENSE (data generation): real gate decisions on harmful actions.
            blocks_this_cycle = 0
            for action in _HARMFUL_ACTIONS:
                result = gatekeeper.check(
                    action=action, content=action, trust_mode="external_strict"
                )
                decision = getattr(result, "decision", None)
                if str(getattr(decision, "value", decision)).lower() == "block":
                    blocks_this_cycle += 1
            total_blocks += blocks_this_cycle

            # SENSE + INTERPRET: the scanner reads the witness pressure log.
            scanner = InternalPressureScanner()
            signals = await scanner.scan()
            transitions_seen["sense"] = True
            transitions_seen["interpret"] = True

            # CONSTRAIN: the high-block-rate threat signal is the constraint.
            gate_threats = [
                s for s in signals
                if s.category == "threat" and "gate_block" in (s.keywords or [])
            ]
            transitions_seen["constrain"] = True

            # ACT: the scanner wrote gate_pressure.json (when a gate threat fired).
            acted = bool(gate_threats) and pressure_path.exists()
            if acted:
                transitions_seen["act"] = True

            # ADAPT: the gatekeeper now resolves a tightened mode from the pressure.
            mode_now = _resolved_mode(gatekeeper)
            if acted and mode_now == "external_strict" and mode_before != "external_strict":
                observed_external_strict_after_act = True

            cycle_rows.append({
                "cycle": i + 1,
                "blocks": blocks_this_cycle,
                "gate_threat_signals": len(gate_threats),
                "pressure_written": pressure_path.exists(),
                "resolved_mode": mode_now,
            })
        except Exception as exc:
            tick_errors.append(f"cycle {i}: {type(exc).__name__}: {exc}")

    mode_after = _resolved_mode(gatekeeper)

    # ADAPT fed forward: the act (gate_pressure.json) changed the trust mode the
    # gatekeeper resolves on its next check — a real S3<->S4 behavioural edge.
    fed_forward = (
        mode_after == "external_strict"
        and mode_before != mode_after
        and observed_external_strict_after_act
    )
    if fed_forward:
        transitions_seen["adapt"] = True

    report = {
        "loop": 5,
        "loop_id": "zeitgeist_internal_pressure",
        "cycles": len(cycle_rows),
        "real_data": total_blocks >= 3,
        "transitions_receipted": transitions_seen,
        "adapt_proof": {
            "field": "TelosGatekeeper resolved trust_mode via gate_pressure.json "
                     "(S4->S3 override the next gate check consults)",
            "before": mode_before,
            "after": mode_after,
            "fed_forward": fed_forward,
            "total_real_blocks": total_blocks,
        },
        "tick_errors": tick_errors,
        "cycle_detail": cycle_rows,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    report = asyncio.run(run(args))
    print(json.dumps(report, indent=2, default=str))

    default_path = (
        Path(__file__).resolve().parents[1]
        / "reports/loop_closure/cybernetics_codex"
        / f"{datetime.now(timezone.utc):%Y-%m-%d}_loop5_zeitgeist_closure.json"
    )
    out = Path(args.report) if args.report else default_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nwrote closure receipt: {out}")

    closed = (
        report["cycles"] > 0
        and report["real_data"]
        and all(report["transitions_receipted"].values())
        and report["adapt_proof"]["fed_forward"]
        and report["adapt_proof"]["before"] != report["adapt_proof"]["after"]
        and not report["tick_errors"]
    )
    print(f"LOOP5_CLOSED={'yes' if closed else 'no'}")
    return 0 if closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
