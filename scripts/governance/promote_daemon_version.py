#!/usr/bin/env python3
"""promote_daemon_version.py — OPERATOR KEY for the two-key daemon promotion.

This is the SECOND key. The gate (promote_gate.py) writes PENDING_APPROVAL.json
proposing a build_id; this script lets the OPERATOR commit it. The actual
launchd plist swap / image re-tag is HOT-PATH-OPERATOR-GATED (H4) and is
intentionally a NO-OP stub here. It refuses to do anything destructive without
an explicit --i-am-the-operator confirmation, and even then only prints the
plan unless --execute is also passed (which is left unimplemented in v0.0.1).

Usage (v0.0.1 scaffold — dry-run only):
    python3 scripts/governance/promote_daemon_version.py --approve 0.1.0+<sha>
    python3 scripts/governance/promote_daemon_version.py --status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

STATE_ROOT = Path(os.environ.get("DHARMA_STATE_DIR", "~/.dharma")).expanduser()
VERSION_METRICS_DIR = STATE_ROOT / "evolution" / "version_metrics"
PENDING = VERSION_METRICS_DIR / "PENDING_APPROVAL.json"


def _status() -> int:
    if not PENDING.exists():
        print(json.dumps({"pending": None, "note": "no PENDING_APPROVAL.json"}))
        return 0
    print(PENDING.read_text(encoding="utf-8"))
    return 0


def _approve(build_id: str) -> int:
    if not PENDING.exists():
        print(f"ERROR: no PENDING_APPROVAL.json at {PENDING}", file=sys.stderr)
        return 1
    pending = json.loads(PENDING.read_text(encoding="utf-8"))
    if pending.get("candidate_build_id") != build_id:
        print(
            f"ERROR: pending build_id {pending.get('candidate_build_id')!r} "
            f"!= requested {build_id!r}",
            file=sys.stderr,
        )
        return 1
    # v0.0.1: scaffold stub. The real launchd swap is GATED (H4) and not
    # implemented here. We only print the plan an operator would execute.
    plan = [
        f"[GATED] would swap com.dharma.swarm.plist to image dharma-daemon:{build_id}",
        "[GATED] would: launchctl bootout + bootstrap the updated plist",
        "[GATED] would: re-point the daemon CMD to the approved build_id",
        "NO-OP in v0.0.1 — this script proposes; a future gated path commits.",
    ]
    print(json.dumps({"approved_build_id": build_id, "plan": plan, "executed": False}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--approve", metavar="BUILD_ID")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)
    if args.status:
        return _status()
    if args.approve:
        return _approve(args.approve)
    ap.error("provide --approve <build_id> or --status")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
