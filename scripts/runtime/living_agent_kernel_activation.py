#!/usr/bin/env python3
"""Review and activate LivingAgentKernel process commands."""

from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.operator_core.living_agent_kernel_activation import (
    activate_supervisor_plan,
    activate_worker_process,
    build_worker_process_command,
    command_hash,
    install_supervisor_plan,
    launch_artifact_status,
    start_installed_supervisor_artifact,
)
from dharma_swarm.operator_core.living_agent_kernel_supervisor import KernelSupervisorPlan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    worker_plan = sub.add_parser("worker-plan", help="Render a worker process command and hash.")
    _add_worker_args(worker_plan)

    worker_launch = sub.add_parser("worker-launch", help="Record or launch a reviewed worker process command.")
    _add_worker_args(worker_launch)
    worker_launch.add_argument("--approved-command-hash", required=True)
    worker_launch.add_argument("--live", action="store_true", help="Launch the worker process command.")
    worker_launch.add_argument("--require-heartbeat", action="store_true", help="Require an online worker heartbeat after launch.")

    supervisor = sub.add_parser("supervisor-activate", help="Record or launch a reviewed supervisor plan.")
    supervisor.add_argument("--plan-json", required=True)
    supervisor.add_argument("--approved-receipt-hash", required=True)
    supervisor.add_argument("--live", action="store_true", help="Launch the supervisor service command directly.")
    supervisor.add_argument("--now", default=None)

    install = sub.add_parser("supervisor-install", help="Install a reviewed supervisor artifact without starting it.")
    install.add_argument("--plan-json", required=True)
    install.add_argument("--approved-receipt-hash", required=True)
    install.add_argument("--install-dir", required=True)
    install.add_argument("--now", default=None)

    start = sub.add_parser("supervisor-start", help="Review or run a launch command from an installed artifact receipt.")
    start.add_argument("--store-dir", default=None)
    start.add_argument("--install-receipt-hash", required=True)
    start.add_argument("--launchd-domain", default="gui/current")
    start.add_argument("--live", action="store_true", help="Run the launch command.")
    start.add_argument("--now", default=None)

    launch_status = sub.add_parser("supervisor-launch-status", help="Inspect an installed launch artifact receipt.")
    launch_status.add_argument("--store-dir", default=None)
    launch_status.add_argument("--install-receipt-hash", required=True)
    launch_status.add_argument("--now", default=None)

    return parser


def _add_worker_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--store-dir", default=None)
    parser.add_argument("--workspace-root", default=str(ROOT))
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--role", default="worker")
    parser.add_argument("--allowed-source", action="append", default=[])
    parser.add_argument("--max-lease-seconds", type=int, default=300)
    parser.add_argument("--heartbeat-interval-seconds", type=int, default=60)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--forever", action="store_true")
    parser.add_argument("--lease", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--now", default=None)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "worker-plan":
        command = build_worker_process_command(
            repo_root=args.repo_root,
            store_dir=args.store_dir,
            workspace_root=args.workspace_root,
            worker_id=args.worker_id,
            role=args.role,
            allowed_sources=args.allowed_source,
            max_lease_seconds=args.max_lease_seconds,
            heartbeat_interval_seconds=args.heartbeat_interval_seconds,
            cycles=None if args.forever else args.cycles,
            lease=args.lease,
            execute=args.execute,
            now=args.now,
        )
        payload = {
            "schema_version": "dharma_living_agent_kernel_worker_process_plan.v1",
            "command": command,
            "command_hash": command_hash(command, cwd=args.repo_root),
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    if args.command == "worker-launch":
        receipt = activate_worker_process(
            repo_root=args.repo_root,
            store_dir=args.store_dir,
            workspace_root=args.workspace_root,
            worker_id=args.worker_id,
            role=args.role,
            allowed_sources=args.allowed_source,
            max_lease_seconds=args.max_lease_seconds,
            heartbeat_interval_seconds=args.heartbeat_interval_seconds,
            cycles=None if args.forever else args.cycles,
            lease=args.lease,
            execute=args.execute,
            now=args.now,
            approved_command_hash=args.approved_command_hash,
            live=args.live,
            require_heartbeat=args.require_heartbeat,
        )
        print(json.dumps(receipt.model_dump(mode="json"), sort_keys=True))
        return 0 if receipt.status in {"reviewed", "activated"} else 2
    if args.command == "supervisor-start":
        receipt = start_installed_supervisor_artifact(
            store_dir=args.store_dir,
            install_receipt_hash=args.install_receipt_hash,
            live=args.live,
            launchd_domain=args.launchd_domain,
            now=args.now,
        )
        print(json.dumps(receipt.model_dump(mode="json"), sort_keys=True))
        return 0 if receipt.status in {"reviewed", "activated"} else 2
    if args.command == "supervisor-launch-status":
        status = launch_artifact_status(
            store_dir=args.store_dir,
            install_receipt_hash=args.install_receipt_hash,
            now=args.now,
        )
        print(json.dumps(status.model_dump(mode="json"), sort_keys=True))
        return 0 if status.status in {"installed", "started"} else 2
    plan = KernelSupervisorPlan.model_validate_json(Path(args.plan_json).read_text(encoding="utf-8"))
    if args.command == "supervisor-install":
        receipt = install_supervisor_plan(
            plan,
            approved_receipt_hash=args.approved_receipt_hash,
            install_dir=args.install_dir,
            now=args.now,
        )
    else:
        receipt = activate_supervisor_plan(
            plan,
            approved_receipt_hash=args.approved_receipt_hash,
            live=args.live,
            now=args.now,
        )
    print(json.dumps(receipt.model_dump(mode="json"), sort_keys=True))
    return 0 if receipt.status in {"reviewed", "installed", "activated"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
