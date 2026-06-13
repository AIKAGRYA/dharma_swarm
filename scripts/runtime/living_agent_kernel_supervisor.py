#!/usr/bin/env python3
"""Plan and inspect LivingAgentKernel service supervision."""

from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.operator_core.living_agent_kernel_supervisor import (
    build_supervisor_plan,
    supervisor_status,
    write_supervisor_plan,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Render a dry-run supervisor plan.")
    plan.add_argument("--mode", choices=["launchd", "tmux"], required=True)
    plan.add_argument("--repo-root", default=str(ROOT))
    plan.add_argument("--store-dir", default=None)
    plan.add_argument("--workspace-root", default=str(ROOT))
    plan.add_argument("--daemon-id", default="living-agent-kernel")
    plan.add_argument("--label", default="com.dharma.living-agent-kernel")
    plan.add_argument("--interval-seconds", type=int, default=60)
    plan.add_argument("--max-wakes", type=int, default=1)
    plan.add_argument("--lease-seconds", type=int, default=300)
    plan.add_argument("--latest-limit", type=int, default=20)
    plan.add_argument("--tmux-session", default="dharma_living_agent_kernel")
    plan.add_argument("--write", action="store_true", help="Write the dry-run plan artifacts under the kernel store.")

    status = sub.add_parser("status", help="Report supervisor freshness from daemon-cycle receipts.")
    status.add_argument("--store-dir", default=None)
    status.add_argument("--daemon-id", default="living-agent-kernel")
    status.add_argument("--stale-after-seconds", type=int, default=180)
    status.add_argument("--now", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "plan":
        plan = build_supervisor_plan(
            mode=args.mode,
            repo_root=args.repo_root,
            store_dir=args.store_dir,
            workspace_root=args.workspace_root,
            daemon_id=args.daemon_id,
            label=args.label,
            interval_seconds=args.interval_seconds,
            max_wakes=args.max_wakes,
            lease_seconds=args.lease_seconds,
            latest_limit=args.latest_limit,
            tmux_session=args.tmux_session,
        )
        if args.write:
            plan = write_supervisor_plan(plan)
        print(json.dumps(plan.model_dump(mode="json"), sort_keys=True))
        return 0
    status = supervisor_status(
        store_dir=args.store_dir,
        daemon_id=args.daemon_id,
        stale_after_seconds=args.stale_after_seconds,
        now=args.now,
    )
    print(json.dumps(status.model_dump(mode="json"), sort_keys=True))
    return 0 if status.status in {"recent", "never_ran"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
