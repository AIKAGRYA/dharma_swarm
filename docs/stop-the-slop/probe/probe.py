#!/usr/bin/env python3
"""Pramāṇa Probe — the executable runner.

The library's thesis is "route to ground truth, return clean, never manufacture."
This script makes that falsifiable: it runs the real instrument for each signal and
emits the row that instrument earned. The "Demonstration run" sections in the
prompts are regenerated from this output — so a buyer can reproduce every number.

Usage:
    python probe.py index   <path>        # composite AI-Slop Index (all signals)
    python probe.py <signal> <path>       # one signal
    python probe.py index   <path> --json # machine-readable

Signals: god_objects complexity cycles wildcard_imports silent_swallows
         broad_catches coupling dead_code duplication churn phantom_deps
         change_coupling narrative_comments

Composite discipline (scope normalization): signals are NOT summed into one number
across different denominators. The index reports a per-axis vector, the dominant
drivers (highest pressure among HIGH/MEDIUM-confidence RED signals), and the single
highest-leverage fix. LOW-confidence and UNASSESSED axes are shown but never drive
the headline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import signals as S
from _common import Confidence, Grade, SignalResult, render_table

SIGNALS = {
    "god_objects": S.god_objects,
    "complexity": S.complexity,
    "cycles": S.cycles,
    "wildcard_imports": S.wildcard_imports,
    "silent_swallows": S.silent_swallows,
    "broad_catches": S.broad_catches,
    "coupling": S.coupling,
    "dead_code": S.dead_code,
    "duplication": S.duplication,
    "churn": S.churn,
    "phantom_deps": S.phantom_deps,
    "change_coupling": S.change_coupling,
    "narrative_comments": S.narrative_comments,
}


def composite(results: list[SignalResult]) -> dict:
    """Reduce per-axis results to an honest headline without hiding scope."""
    # Drivers: RED signals the runner can actually stand behind (not LOW/proxy).
    drivers = sorted(
        (r for r in results
         if r.grade == Grade.RED and r.confidence in (Confidence.HIGH, Confidence.MEDIUM)),
        key=lambda r: r.pressure, reverse=True,
    )
    reds = [r for r in results if r.grade == Grade.RED]
    ambers = [r for r in results if r.grade == Grade.AMBER]
    greens = [r for r in results if r.grade == Grade.GREEN]
    unassessed = [r for r in results if r.grade == Grade.UNASSESSED]
    if drivers:
        headline = "ELEVATED" if len(drivers) >= 2 else "MODERATE"
    elif reds:
        headline = "ELEVATED (low-confidence \u2014 confirm before acting)"
    elif ambers:
        headline = "MODERATE"
    else:
        headline = "CLEAN"
    return {
        "headline": headline,
        # every HIGH/MEDIUM-confidence RED is a driver; do not silently truncate
        # the list (that would let a real RED axis vanish from the headline).
        "drivers": [r.signal for r in drivers],
        "counts": {"RED": len(reds), "AMBER": len(ambers),
                   "GREEN": len(greens), "UNASSESSED": len(unassessed)},
        "highest_leverage_fix": _leverage(drivers),
    }


def _leverage(drivers: list[SignalResult]) -> str:
    if not drivers:
        return "None \u2014 no high-confidence RED axis. Return clean."
    top = drivers[0]
    if top.detail:
        return f"Attack the top of '{top.signal}': {top.detail[0]}"
    return f"Reduce '{top.signal}' ({top.measured})."


def _driver_line(names: list[str], cap: int = 5) -> str:
    if not names:
        return "none"
    if len(names) <= cap:
        return ", ".join(names)
    return ", ".join(names[:cap]) + f" (+{len(names) - cap} more)"


def run_index(root: Path, as_json: bool) -> str:
    results = [fn(root) for fn in SIGNALS.values()]
    comp = composite(results)
    if as_json:
        return json.dumps({"target": str(root),
                           "signals": [r.as_dict() for r in results],
                           "composite": comp}, indent=2)
    out = [f"# AI-Slop Index \u2014 {root}", "",
           render_table(results), "",
           f"**Composite: {comp['headline']}.** "
           f"RED {comp['counts']['RED']} / AMBER {comp['counts']['AMBER']} / "
           f"GREEN {comp['counts']['GREEN']} / UNASSESSED {comp['counts']['UNASSESSED']}.",
           f"**Drivers (high-confidence RED): {_driver_line(comp['drivers'])}.**",
           f"**Highest-leverage fix:** {comp['highest_leverage_fix']}", "",
           "_Scopes (denominators) per axis:_"]
    for r in results:
        out.append(f"- {r.signal}: {r.scope} \u2014 instrument: {r.instrument}")
    return "\n".join(out)


def run_one(name: str, root: Path, as_json: bool) -> str:
    r = SIGNALS[name](root)
    if as_json:
        return json.dumps(r.as_dict(), indent=2)
    lines = [render_table([r])]
    if r.detail:
        lines += ["", f"Detail ({r.instrument}):", *(f"  {d}" for d in r.detail)]
    lines += ["", f"Scope: {r.scope}", f"Confirm with: {r.confirm_with}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pramāṇa Probe runner")
    p.add_argument("signal", choices=["index", *SIGNALS.keys()])
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--json", action="store_true")
    p.add_argument("--online", action="store_true",
                   help="allow live checks (PyPI existence for phantom_deps)")
    args = p.parse_args(argv)
    if args.online:
        S.ONLINE = True
    root = Path(args.path).resolve()
    if not root.exists():
        print(f"path not found: {root}", file=sys.stderr)
        return 2
    out = run_index(root, args.json) if args.signal == "index" else run_one(args.signal, root, args.json)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
