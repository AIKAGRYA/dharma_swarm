#!/usr/bin/env python3
"""Run or inspect the real ds-goal supervisor loop."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.operator_core.ds_goal_supervisor import (  # noqa: E402
    run_supervisor_loop,
    run_supervisor_cycle,
    stop_tmux_supervisor,
    supervisor_status_payload,
)


def _json_default(value: Any) -> str:
    return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the supervisor loop until deadline or stop condition.")
    _common(run)
    run.add_argument("--duration-hours", type=float, default=0.0)
    run.add_argument("--lease-seconds", type=int, default=300)
    run.add_argument("--interval-seconds", type=float, default=5.0)
    run.add_argument("--max-tasks-per-cycle", type=int, default=1)
    run.add_argument("--worker-id", default="ds-goal-supervisor")
    run.add_argument("--tmux-session", default="")
    run.add_argument("--live-provider-requested", action="store_true")
    run.add_argument("--provider", default="")
    run.add_argument("--model", default="")
    run.add_argument("--verifier-timeout-seconds", type=int, default=120)
    run.add_argument("--max-cycles", type=int, default=0)

    cycle = sub.add_parser("cycle", help="Run one supervisor cycle.")
    _common(cycle)
    cycle.add_argument("--lease-seconds", type=int, default=300)
    cycle.add_argument("--max-tasks", type=int, default=1)
    cycle.add_argument("--worker-id", default="ds-goal-supervisor")
    cycle.add_argument("--live-provider-requested", action="store_true")
    cycle.add_argument("--provider", default="")
    cycle.add_argument("--model", default="")
    cycle.add_argument("--verifier-timeout-seconds", type=int, default=120)

    status = sub.add_parser("status", help="Report supervisor liveness and mission task counts.")
    _common(status)
    status.add_argument("--tmux-session", default="")
    status.add_argument("--stale-after-seconds", type=int, default=180)

    stop = sub.add_parser("stop", help="Stop the mission tmux supervisor session.")
    _common(stop)
    stop.add_argument("--tmux-session", default="")

    return parser


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mission-id", required=True)
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".dharma" / "ds_goals")
    parser.add_argument("--kernel-store", type=Path, default=Path.home() / ".dharma" / "living_agent_kernel")
    parser.add_argument("--runtime-db", type=Path, default=None)
    parser.add_argument("--workspace-root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        payload = run_supervisor_loop(
            state_root=args.state_root,
            mission_id=args.mission_id,
            kernel_store=args.kernel_store,
            workspace_root=args.workspace_root,
            duration_hours=args.duration_hours,
            lease_seconds=args.lease_seconds,
            interval_seconds=args.interval_seconds,
            max_tasks_per_cycle=args.max_tasks_per_cycle,
            worker_id=args.worker_id,
            tmux_session=args.tmux_session,
            live_provider_requested=args.live_provider_requested,
            provider=args.provider,
            model=args.model,
            verifier_timeout_seconds=args.verifier_timeout_seconds,
            max_cycles=args.max_cycles,
        )
    elif args.command == "cycle":
        payload = run_supervisor_cycle(
            state_root=args.state_root,
            mission_id=args.mission_id,
            kernel_store=args.kernel_store,
            workspace_root=args.workspace_root,
            lease_seconds=args.lease_seconds,
            max_tasks=args.max_tasks,
            worker_id=args.worker_id,
            live_provider_requested=args.live_provider_requested,
            provider=args.provider,
            model=args.model,
            verifier_timeout_seconds=args.verifier_timeout_seconds,
        )
    elif args.command == "status":
        payload = supervisor_status_payload(
            state_root=args.state_root,
            mission_id=args.mission_id,
            session_name=args.tmux_session,
            stale_after_seconds=args.stale_after_seconds,
        )
    else:
        payload = stop_tmux_supervisor(
            state_root=args.state_root,
            mission_id=args.mission_id,
            session_name=args.tmux_session,
        )
    if args.json:
        print(json.dumps(payload, sort_keys=True, default=_json_default))
    else:
        print(f"{payload.get('status')}: {payload.get('mission_id')}")
    return 0 if str(payload.get("status")) in {"idle", "running", "completed", "stopped"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
