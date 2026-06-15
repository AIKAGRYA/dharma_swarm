#!/usr/bin/env python3
"""Inspect or recover LivingAgentKernel crash-resume state."""

from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.operator_core.living_agent_kernel_recovery import (
    build_kernel_crash_resume_snapshot,
    recover_kernel_after_crash,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    snapshot = sub.add_parser("snapshot", help="Project cross-ledger restart state without mutation.")
    _add_common_args(snapshot)

    recover = sub.add_parser("recover", help="Explicitly recover expired leases after crash-resume preflight.")
    _add_common_args(recover)

    return parser


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--store-dir", default=None)
    parser.add_argument("--daemon-id", default="living-agent-kernel")
    parser.add_argument("--latest-limit", type=int, default=20)
    parser.add_argument("--stale-after-seconds", type=int, default=120)
    parser.add_argument("--offline-after-seconds", type=int, default=3600)
    parser.add_argument("--now", default=None)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    common = {
        "store_dir": args.store_dir,
        "daemon_id": args.daemon_id,
        "latest_limit": args.latest_limit,
        "stale_after_seconds": args.stale_after_seconds,
        "offline_after_seconds": args.offline_after_seconds,
        "now": args.now,
    }
    if args.command == "snapshot":
        result = build_kernel_crash_resume_snapshot(**common)
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
        return 0 if result.status in {"ready", "needs_recovery"} else 2
    result = recover_kernel_after_crash(**common)
    print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    return 0 if result.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
