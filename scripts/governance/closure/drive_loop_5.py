#!/usr/bin/env python3
"""Loop 5 closure driver — exercise the REAL Zeitgeist/S4->S3 internal-pressure loop.

Loop 5 (Zeitgeist Scanner, internal-pressure variant) does NOT need a provider
key. Its closure is a real-data feedback chain through committed code:

  sense      witness gate-check outcomes written by the REAL TelosGatekeeper
             think-point path -> ~/.dharma/witness/witness_YYYYMMDD.jsonl
             (rows: {ts, phase, outcome in {PASS,WARN,BLOCKED}, action})
  interpret  InternalPressureScanner._scan_witness_pressure reads today's log
             and tallies BLOCKED/WARN/PASS
  constrain  _witness_signals: block_count >= 3 raises a 'gate_block' threat
  act        _write_gate_pressure writes ~/.dharma/meta/gate_pressure.json with
             trust_mode_override='external_strict'
  adapt      TelosGatekeeper._apply_gate_pressure reads that file on the NEXT
             gate check and tightens the resolved trust mode (S3 closes the loop)

This driver runs the REAL classes end to end. No fixtures, no mocks, no
hand-written witness rows: the BLOCKED outcomes are produced by invoking the
actual TelosGatekeeper.check() with a mandatory think-phase and an insufficient
reflection (which the real gate logic blocks).

ISOLATION (G1/G6): the whole chain anchors on ~/.dharma via Path.home(). We run
in our OWN process with HOME pointed at a SCOPED temp dir, set BEFORE importing
telos_gates / internal_pressure, so the module-level WITNESS_DIR and
_GATE_PRESSURE_PATH resolve under the scope. Production ~/.dharma is never
touched; the production daemon is never restarted.

Run:  LC_LOOP5_HOME=/tmp/lc_loop5_home python3 scripts/governance/closure/drive_loop_5.py
Then: LC_LOOP5_HOME=/tmp/lc_loop5_home python3 scripts/governance/closure/check_loop_5.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path


def _scoped_home() -> Path:
    raw = os.environ.get("LC_LOOP5_HOME") or f"/tmp/lc_loop5_home_{int(time.time())}"
    home = Path(raw)
    (home / ".dharma").mkdir(parents=True, exist_ok=True)
    os.environ["LC_LOOP5_HOME"] = str(home)  # so the check sees the same scope
    os.environ["HOME"] = str(home)
    return home


# Point HOME at the scope BEFORE any dharma import resolves Path.home().
HOME = _scoped_home()

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


async def main() -> int:
    # Imported AFTER HOME is rebound so module-level paths are scoped.
    from dharma_swarm.telos_gates import TelosGatekeeper, WITNESS_DIR
    from dharma_swarm.s4.internal_pressure import InternalPressureScanner

    # Hard isolation assertion: we must be operating under the scope, not prod.
    assert str(WITNESS_DIR).startswith(str(HOME)), (
        f"ISOLATION BREACH: WITNESS_DIR={WITNESS_DIR} not under scope {HOME}"
    )
    assert str(TelosGatekeeper._GATE_PRESSURE_PATH).startswith(str(HOME)), (
        f"ISOLATION BREACH: gate_pressure path {TelosGatekeeper._GATE_PRESSURE_PATH} "
        f"not under scope {HOME}"
    )

    gk = TelosGatekeeper()

    # --- SENSE: produce >=3 REAL BLOCKED gate-check outcomes ---------------
    # A mandatory think-phase with an insufficient reflection is BLOCKED by the
    # real gate logic, which appends an outcome='BLOCKED' row to today's witness
    # log. This is the genuine code path, not a synthetic write.
    blocked = 0
    for i in range(5):
        res = gk.check(
            action=f"rm -rf /tmp/loop5_real_block_target_{i}",
            content="",
            tool_name="Bash",
            think_phase="before_write",   # mandatory phase
            reflection="ok",               # too short -> insufficient -> BLOCKED
        )
        # The gate must actually deny on the WITNESS gate for this to be real.
        if res.decision.name in ("DENY", "BLOCK", "BLOCKED") or not res.allowed:
            blocked += 1
        else:
            # Some builds expose .decision as str; tolerate both.
            if str(getattr(res, "decision", "")).upper().find("BLOCK") >= 0:
                blocked += 1

    # Confirm the real witness log now carries the BLOCKED rows.
    today = time.strftime("%Y%m%d", time.gmtime())
    log_file = WITNESS_DIR / f"witness_{today}.jsonl"
    log_blocked = 0
    if log_file.exists():
        import json as _json
        for line in log_file.read_text(encoding="utf-8").splitlines():
            try:
                if _json.loads(line).get("outcome") == "BLOCKED":
                    log_blocked += 1
            except Exception:
                pass
    print(f"SENSE: real gate denials={blocked}  witness BLOCKED rows={log_blocked}  log={log_file}")

    # --- INTERPRET + CONSTRAIN + ACT: run the REAL scanner -----------------
    scanner = InternalPressureScanner(state_dir=HOME / ".dharma")
    signals = await scanner.scan()
    gate_signals = [s for s in signals if "gate_block" in s.keywords]
    pressure_path = HOME / ".dharma" / "meta" / "gate_pressure.json"
    print(
        f"INTERPRET/ACT: signals={len(signals)} gate_block_signals={len(gate_signals)} "
        f"gate_pressure_written={pressure_path.exists()}"
    )

    # --- ADAPT: prove the REAL S3 consumer flips the trust mode ------------
    # A fresh gatekeeper reads gate_pressure.json via _apply_gate_pressure and
    # must override internal_yolo -> external_strict. This is the loop closing.
    gk2 = TelosGatekeeper()
    resolved = gk2._apply_gate_pressure("internal_yolo")
    print(f"ADAPT: _apply_gate_pressure('internal_yolo') -> '{resolved}'")

    closed = (
        log_blocked >= 3
        and len(gate_signals) >= 1
        and pressure_path.exists()
        and resolved == "external_strict"
    )
    print(f"\nLC_LOOP5_HOME={HOME}")
    print(f"LOOP5 CHAIN CLOSED (driver view): {closed}")
    return 0 if closed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
