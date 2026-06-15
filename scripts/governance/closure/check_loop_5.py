#!/usr/bin/env python3
"""Loop 5 (Zeitgeist Scanner / S4->S3 internal pressure) closure check.

GREEN only when the REAL feedback chain is closed on REAL data, replayable by a
fresh agent from artifacts alone:

  (1) SENSE/INTERPRET: today's witness log under the scope carries >=3 REAL
      gate-check rows with outcome='BLOCKED' (written by the real TelosGatekeeper
      think-point path, not hand-authored).
  (2) ACT: gate_pressure.json exists under the scope, is UNEXPIRED, and carries
      trust_mode_override='external_strict' (the real _write_gate_pressure output).
  (3) ADAPT: the REAL S3 consumer TelosGatekeeper._apply_gate_pressure flips
      'internal_yolo' -> 'external_strict' when reading that file (loop closing).

G4 (One Wire): this loop touches NO archive fitness. The internal-pressure
scanner writes only ~/.dharma/meta/* and ~/.dharma/witness/* — never
archive.jsonl. We assert no archive write occurred under the scope as a guard.

Honest floor: if the driver has not run (no scoped artifacts), this is RED with
the real blocker named — NOT a provider key. Loop 5 needs real gate-check
outcomes flowing, which the driver produces by exercising the live gate.

Replay:
  LC_LOOP5_HOME=/tmp/lc_loop5_home python3 scripts/governance/closure/drive_loop_5.py
  LC_LOOP5_HOME=/tmp/lc_loop5_home python3 scripts/governance/closure/check_loop_5.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Verdict, emit  # noqa: E402

REPLAY = (
    "LC_LOOP5_HOME=/tmp/lc_loop5_home python3 scripts/governance/closure/drive_loop_5.py && "
    "LC_LOOP5_HOME=/tmp/lc_loop5_home python3 scripts/governance/closure/check_loop_5.py"
)


def _scope() -> Path | None:
    raw = os.environ.get("LC_LOOP5_HOME")
    if not raw:
        return None
    home = Path(raw)
    return home if (home / ".dharma").exists() else None


def check() -> Verdict:
    home = _scope()
    if home is None:
        return Verdict(
            5,
            "RED",
            "no scoped Loop-5 artifacts (set LC_LOOP5_HOME and run drive_loop_5.py). "
            "Real blocker: real gate-check outcomes must flow through the live "
            "TelosGatekeeper think-point path so InternalPressureScanner writes "
            "gate_pressure.json (NOT a provider key).",
            real_data=False,
            replay_cmd=REPLAY,
        )

    dharma = home / ".dharma"

    # (1) SENSE/INTERPRET: >=3 real BLOCKED witness rows in today's log.
    today = time.strftime("%Y%m%d", time.gmtime())
    log_file = dharma / "witness" / f"witness_{today}.jsonl"
    blocked = 0
    if log_file.exists():
        for line in log_file.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("outcome") == "BLOCKED" and rec.get("phase") and rec.get("ts"):
                blocked += 1
    if blocked < 3:
        return Verdict(
            5,
            "RED",
            f"only {blocked} real BLOCKED witness rows in {log_file} (need >=3). "
            "Drive more real gate denials through TelosGatekeeper.check(think_phase=...).",
            real_data=False,
            replay_cmd=REPLAY,
        )

    # G4 guard: One Wire intact — no archive fitness was written under the scope.
    archive = dharma / "archive.jsonl"
    if archive.exists() and archive.stat().st_size > 0:
        return Verdict(
            5,
            "RED",
            f"ONE-WIRE VIOLATION: {archive} written under the Loop-5 scope. "
            "Internal pressure must never touch archive fitness.",
            real_data=True,
            replay_cmd=REPLAY,
        )

    # (2) ACT: gate_pressure.json exists, unexpired, external_strict.
    pressure_path = dharma / "meta" / "gate_pressure.json"
    if not pressure_path.exists():
        return Verdict(
            5,
            "RED",
            f"gate_pressure.json absent at {pressure_path} despite "
            f"{blocked} BLOCKED rows; _write_gate_pressure did not fire.",
            real_data=False,
            replay_cmd=REPLAY,
        )
    try:
        pdata = json.loads(pressure_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return Verdict(5, "RED", f"gate_pressure.json unreadable: {e}", real_data=False, replay_cmd=REPLAY)
    override = str(pdata.get("trust_mode_override", "")).strip().lower()
    expires = float(pdata.get("expires", 0) or 0)
    if override != "external_strict":
        return Verdict(
            5,
            "RED",
            f"gate_pressure override='{override}' (expected 'external_strict').",
            real_data=True,
            replay_cmd=REPLAY,
        )
    if expires < time.time():
        return Verdict(
            5,
            "RED",
            f"gate_pressure expired (expires={expires} < now). Re-run driver.",
            real_data=True,
            replay_cmd=REPLAY,
        )

    # (3) ADAPT: the REAL S3 consumer must flip the mode reading this file.
    # Bind HOME to the scope BEFORE importing telos_gates so its module-level
    # _GATE_PRESSURE_PATH resolves under the scope.
    os.environ["HOME"] = str(home)
    repo = Path(__file__).resolve().parents[3]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from dharma_swarm.telos_gates import TelosGatekeeper  # noqa: E402

    if not str(TelosGatekeeper._GATE_PRESSURE_PATH).startswith(str(home)):
        return Verdict(
            5,
            "BLOCKED",
            "consumer gate-pressure path not under scope; cannot verify S3 flip "
            "in-process (telos_gates imported before HOME was scoped). "
            "Re-run the check in a fresh process.",
            real_data=True,
            replay_cmd=REPLAY,
        )
    resolved = TelosGatekeeper()._apply_gate_pressure("internal_yolo")
    if resolved != "external_strict":
        return Verdict(
            5,
            "RED",
            f"S3 consumer did not flip mode: _apply_gate_pressure('internal_yolo') "
            f"-> '{resolved}' (expected 'external_strict'). S4->S3 channel broken.",
            real_data=True,
            replay_cmd=REPLAY,
        )

    return Verdict(
        5,
        "GREEN",
        f"S4->S3 closed on real data: {blocked} real BLOCKED gate-checks -> "
        f"gate_pressure(external_strict, reason={str(pdata.get('reason',''))[:50]!r}) -> "
        f"S3 consumer flipped internal_yolo->external_strict. One Wire intact.",
        real_data=True,
        replay_cmd=REPLAY,
    )


if __name__ == "__main__":
    sys.exit(emit(check()))
