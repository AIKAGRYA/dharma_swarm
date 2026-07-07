#!/usr/bin/env python3
"""Slop ratchet — the Stop-the-Slop probe wired into governance as a delta-ratchet.

The probe (docs/stop-the-slop/probe/) routes 13 code-health signals to real
instruments (AST, Tarjan SCC, radon, git, vulture) and returns per-axis grades
with earned confidence. This gate turns those measurements into a one-way
ratchet against a committed baseline:

  - REGRESSION (exit 1): a ratchetable signal's grade worsens
    (GREEN -> AMBER -> RED) or its finding count rises above baseline.
  - PASS (exit 0): every ratchetable signal is at or below baseline.
    Improvements are reported with a hint to re-freeze via --write-baseline.

Ratchet policy (what keeps this honest and future-proof):
  - Only HIGH/MEDIUM-confidence signals can fail the gate. LOW-confidence
    proxies and UNASSESSED axes are advisory — a proxy or an absent
    instrument must never block a merge.
  - Time-windowed signals (churn, change coupling) are advisory: their
    denominator moves with the calendar, so a delta against a frozen
    baseline is not meaningful.
  - If an instrument becomes unavailable (signal turns UNASSESSED), the
    axis is skipped and reported — availability drift must not flip verdicts.

Usage:
    python3 scripts/governance/slop_ratchet.py                  # check vs baseline
    python3 scripts/governance/slop_ratchet.py --write-baseline # freeze current state
    python3 scripts/governance/slop_ratchet.py --json           # machine-readable
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_DIR = REPO_ROOT / "docs" / "stop-the-slop" / "probe"
BASELINE_PATH = REPO_ROOT / "docs" / "governance" / "hygiene" / "slop_index_baseline.json"

# Scopes the ratchet measures. Each is probed independently (scope
# normalization: signals are never summed across denominators).
SCOPES = ("dharma_swarm", "api", "scripts")

# Signals whose window moves with the calendar — advisory, never ratcheted.
TIME_WINDOWED = {"Churn/revert", "Change coupling"}

_GRADE_RANK = {"GREEN": 0, "AMBER": 1, "RED": 2}


def _load_probe() -> ModuleType:
    """Import the probe runner by path (it is a self-contained library under
    docs/, deliberately not a package of the host repo)."""
    if str(PROBE_DIR) not in sys.path:
        sys.path.insert(0, str(PROBE_DIR))
    spec = importlib.util.spec_from_file_location("stop_the_slop_probe", PROBE_DIR / "probe.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"probe runner not importable at {PROBE_DIR}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def measure(scopes: tuple[str, ...] = SCOPES) -> dict[str, Any]:
    probe = _load_probe()
    out: dict[str, Any] = {}
    for scope in scopes:
        root = REPO_ROOT / scope
        if not root.exists():
            out[scope] = {"error": "scope path missing"}
            continue
        results = [fn(root) for fn in probe.SIGNALS.values()]
        comp = probe.composite(results)
        out[scope] = {
            "composite": comp["headline"],
            "signals": {
                r.signal: {
                    "grade": r.grade.value,
                    "confidence": r.confidence.value,
                    "count": r.count,
                    "measured": r.measured,
                }
                for r in results
            },
        }
    return out


def _digest(payload: dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k != "digest"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def evaluate(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Pure comparison: current vs baseline measurements -> verdict.

    Returns {"regressions": [...], "improvements": [...], "advisory": [...],
             "skipped": [...], "passed": bool}.
    """
    regressions: list[str] = []
    improvements: list[str] = []
    advisory: list[str] = []
    skipped: list[str] = []
    for scope, cur in current.items():
        base = baseline.get(scope)
        if not isinstance(base, dict) or "signals" not in base or "signals" not in cur:
            skipped.append(f"{scope}: no baseline for scope")
            continue
        for name, c in cur["signals"].items():
            b = base["signals"].get(name)
            label = f"{scope}/{name}"
            if b is None:
                skipped.append(f"{label}: not in baseline")
                continue
            if c["confidence"] == "UNASSESSED" or b["confidence"] == "UNASSESSED":
                skipped.append(f"{label}: UNASSESSED (instrument availability)")
                continue
            worse_grade = _GRADE_RANK.get(c["grade"], 0) > _GRADE_RANK.get(b["grade"], 0)
            worse_count = (
                c["count"] is not None and b["count"] is not None and c["count"] > b["count"]
            )
            better = (
                _GRADE_RANK.get(c["grade"], 0) < _GRADE_RANK.get(b["grade"], 0)
                or (c["count"] is not None and b["count"] is not None and c["count"] < b["count"])
            )
            msg = (f"{label}: {b['grade']}/{b['count']} -> {c['grade']}/{c['count']}"
                   f"  ({c['measured']})")
            if worse_grade or worse_count:
                # Advisory, never blocking: time-windowed axes, LOW-confidence
                # proxies (on either side), and confidence flips — a count from
                # a proxy and a count from the real instrument are incomparable.
                if (name in TIME_WINDOWED
                        or c["confidence"] == "LOW" or b["confidence"] == "LOW"
                        or c["confidence"] != b["confidence"]):
                    advisory.append(msg)
                else:
                    regressions.append(msg)
            elif better:
                improvements.append(msg)
    return {
        "regressions": regressions,
        "improvements": improvements,
        "advisory": advisory,
        "skipped": skipped,
        "passed": not regressions,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Stop-the-Slop probe delta-ratchet gate")
    p.add_argument("--write-baseline", action="store_true",
                   help="freeze the current measurement as the committed baseline")
    p.add_argument("--baseline", default=str(BASELINE_PATH))
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    baseline_path = Path(args.baseline)

    if args.write_baseline:
        current = measure()
        payload: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "probe": "docs/stop-the-slop/probe (13 signals)",
            "scopes": current,
        }
        payload["digest"] = _digest(payload)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"baseline written: {baseline_path} (digest {payload['digest'][:16]})")
        return 0

    if not baseline_path.exists():
        print(f"SLOP RATCHET CONFIG ERROR: baseline missing at {baseline_path}; "
              "run with --write-baseline to freeze one", file=sys.stderr)
        return 3
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    if payload.get("digest") != _digest(payload):
        print("SLOP RATCHET CONFIG ERROR: baseline digest mismatch (tampered or "
              "hand-edited); regenerate with --write-baseline", file=sys.stderr)
        return 3

    current = measure()
    verdict = evaluate(current, payload["scopes"])
    if args.json:
        print(json.dumps({"current": current, "verdict": verdict}, indent=2))
    else:
        status = "PASS" if verdict["passed"] else "REGRESSION"
        print(f"SLOP RATCHET -> {status}  "
              f"(regressions={len(verdict['regressions'])}, "
              f"improvements={len(verdict['improvements'])}, "
              f"advisory={len(verdict['advisory'])}, skipped={len(verdict['skipped'])})")
        for r in verdict["regressions"]:
            print(f"  REGRESSION  {r}")
        for a in verdict["advisory"]:
            print(f"  advisory    {a}")
        for i in verdict["improvements"]:
            print(f"  improved    {i}  — consider --write-baseline to lock it in")
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
