#!/usr/bin/env python3
"""Run all 13 loop-closure checks, aggregate a ledger, report the floor.

Each check_loop_N runs in its OWN subprocess with a per-loop scoped env from
scoped_env.json. This is required because several checks read the same env var
(LC_RUNTIME_DB) but expect different scoped databases (Loop 1 vs Loop 9), so
they cannot share one process env. Per-loop subprocesses also make every GREEN
verdict independently replayable by a fresh agent from the recorded env alone.

Exit:
  0  -> all 13 GREEN (full closure)
  1  -> any RED remains (honest current floor)
  2  -> only BLOCKED (correctly-gated) loops are non-GREEN

Reads only declared owner surfaces + /tmp snapshots. Never restarts the
daemon, never mocks a provider, never writes archive fitness.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _common import GREEN, RED, BLOCKED  # noqa: E402

_LINE_RE = re.compile(r"^(?:LOOP \d+|ONE WIRE ENFORCEMENT): (GREEN|RED|BLOCKED) \+ (.*)$")


def _scoped_env() -> dict:
    cfg = HERE / "scoped_env.json"
    if not cfg.exists():
        return {}
    return {k: v for k, v in json.loads(cfg.read_text()).items() if not k.startswith("_")}


def _run_check(script: str, extra_env: dict) -> tuple[str, str]:
    """Run a check script in a subprocess; return (verdict, reason) from its line."""
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (extra_env or {}).items()})
    proc = subprocess.run(
        [sys.executable, str(HERE / script)],
        capture_output=True, text=True, env=env, timeout=120,
    )
    out = (proc.stdout or "").strip().splitlines()
    for line in out:
        m = _LINE_RE.match(line.strip())
        if m:
            return m.group(1), m.group(2)
    # Could not parse — treat as RED (infra failure is never silently GREEN).
    tail = (proc.stdout + proc.stderr).strip()[-300:]
    return RED, f"check produced no parseable verdict line (exit={proc.returncode}): {tail}"


def run() -> dict:
    scoped = _scoped_env()
    loops = []
    counts = {GREEN: 0, RED: 0, BLOCKED: 0}
    for n in range(1, 14):
        verdict, reason = _run_check(f"check_loop_{n}.py", scoped.get(str(n), {}))
        counts[verdict] += 1
        loops.append({"loop": n, "verdict": verdict, "reason": reason,
                      "real_data": verdict == GREEN, "scoped_env": scoped.get(str(n), {})})
        print(f"LOOP {n}: {verdict} + {reason}")

    ow_verdict, ow_reason = _run_check("check_one_wire_enforcement.py", {})
    print(f"ONE WIRE ENFORCEMENT: {ow_verdict} + {ow_reason}")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "one_wire_enforcement": {"verdict": ow_verdict, "reason": ow_reason},
        "loops": loops,
    }


def main() -> int:
    ledger = run()
    out_dir = HERE.parents[2] / "reports" / "loop_closure" / datetime.now().strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "closure_ledger.json").write_text(json.dumps(ledger, indent=2))
    c = ledger["counts"]
    print(f"\nSUMMARY: GREEN={c[GREEN]} RED={c[RED]} BLOCKED={c[BLOCKED]}  "
          f"ONE_WIRE={ledger['one_wire_enforcement']['verdict']}  -> {out_dir/'closure_ledger.json'}")
    if c[RED]:
        return 1
    if c[BLOCKED]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
