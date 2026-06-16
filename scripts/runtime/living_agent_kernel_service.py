#!/usr/bin/env python3
"""Run LivingAgentKernel daemon cycles under a service lock."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.operator_core.living_agent_kernel_service import run_kernel_daemon_service  # noqa: E402


def _source_root(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("source roots must be SOURCE=PATH")
    source, path = value.split("=", 1)
    source = source.strip()
    path = path.strip()
    if not source or not path:
        raise argparse.ArgumentTypeError("source roots must be SOURCE=PATH")
    return source, path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-dir", default=None, help="Kernel store directory. Defaults to ~/.dharma/living_agent_kernel.")
    parser.add_argument("--workspace-root", default=".", help="Workspace root for kernel tool permissions.")
    parser.add_argument("--daemon-id", default="living-agent-kernel", help="Daemon identity used for controls and leases.")
    parser.add_argument("--cycles", type=int, default=1, help="Number of cycles to run.")
    parser.add_argument("--forever", action="store_true", help="Run until stopped or interrupted.")
    parser.add_argument("--max-wakes", type=int, default=1, help="Maximum wakes per daemon cycle.")
    parser.add_argument("--lease-seconds", type=int, default=300, help="Wake lease duration.")
    parser.add_argument("--interval-seconds", type=int, default=60, help="Sleep between cycles and next-run projection.")
    parser.add_argument("--latest-limit", type=int, default=20, help="Latest wake status rows per cycle.")
    parser.add_argument("--no-recover-expired", action="store_true", help="Disable expired wake recovery before cycles.")
    parser.add_argument("--lock-path", default=None, help="Override service lock path.")
    parser.add_argument("--source-root", action="append", type=_source_root, default=[], help="Source closeback root as SOURCE=PATH.")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_kernel_daemon_service(
        store_dir=args.store_dir,
        workspace_root=args.workspace_root,
        daemon_id=args.daemon_id,
        cycles=None if args.forever else args.cycles,
        max_wakes=args.max_wakes,
        lease_seconds=args.lease_seconds,
        interval_seconds=args.interval_seconds,
        latest_limit=args.latest_limit,
        recover_expired=not args.no_recover_expired,
        source_roots=dict(args.source_root),
        lock_path=args.lock_path,
    )
    if args.json:
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    else:
        print(
            f"{result.status}: {result.completed_cycles} cycle(s), "
            f"daemon={result.daemon_id}, {result.message}"
        )
    return 0 if result.status in {"completed", "stopped"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
