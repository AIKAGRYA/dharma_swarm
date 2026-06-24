#!/usr/bin/env python3
"""Record reviewed activation receipts for L4 HOLON supervisor artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.holon_l4_activation import (  # noqa: E402
    activate_holon_l4_supervisor_plan,
    holon_l4_launch_artifact_status,
    install_holon_l4_supervisor_plan,
    start_installed_holon_l4_supervisor_artifact,
)
from dharma_swarm.holon_l4_supervisor import HolonL4SupervisorPlan  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    activate = sub.add_parser("supervisor-activate", help="Record or launch a reviewed L4 service command.")
    activate.add_argument("--plan-json", required=True)
    activate.add_argument("--approved-receipt-hash", required=True)
    activate.add_argument("--live", action="store_true", help="Launch the L4 service command directly.")
    activate.add_argument("--require-service-heartbeat", action="store_true")
    activate.add_argument("--service-heartbeat-fresh-after-seconds", type=int, default=3600)
    activate.add_argument("--service-heartbeat-timeout-seconds", type=float, default=0.0)
    activate.add_argument("--service-heartbeat-poll-seconds", type=float, default=0.5)
    activate.add_argument("--now", default=None)

    install = sub.add_parser("supervisor-install", help="Install a reviewed L4 launch artifact without starting it.")
    install.add_argument("--plan-json", required=True)
    install.add_argument("--approved-receipt-hash", required=True)
    install.add_argument("--install-dir", required=True)
    install.add_argument("--now", default=None)

    start = sub.add_parser("supervisor-start", help="Review or run a launch command from an installed L4 artifact.")
    start.add_argument("--activation-dir", required=True)
    start.add_argument("--install-receipt-hash", required=True)
    start.add_argument("--launchd-domain", default="gui/current")
    start.add_argument("--live", action="store_true", help="Run the launch command.")
    start.add_argument("--require-service-heartbeat", action="store_true")
    start.add_argument("--service-heartbeat-fresh-after-seconds", type=int, default=3600)
    start.add_argument("--service-heartbeat-timeout-seconds", type=float, default=0.0)
    start.add_argument("--service-heartbeat-poll-seconds", type=float, default=0.5)
    start.add_argument("--now", default=None)

    status = sub.add_parser("supervisor-launch-status", help="Inspect an installed L4 launch artifact receipt.")
    status.add_argument("--activation-dir", required=True)
    status.add_argument("--install-receipt-hash", required=True)
    status.add_argument("--now", default=None)

    return parser


def _read_plan(path: str) -> HolonL4SupervisorPlan:
    return HolonL4SupervisorPlan.model_validate_json(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "supervisor-start":
        receipt = start_installed_holon_l4_supervisor_artifact(
            activation_dir=args.activation_dir,
            install_receipt_hash=args.install_receipt_hash,
            live=args.live,
            launchd_domain=args.launchd_domain,
            require_service_heartbeat=args.require_service_heartbeat,
            service_heartbeat_fresh_after_seconds=args.service_heartbeat_fresh_after_seconds,
            service_heartbeat_timeout_seconds=args.service_heartbeat_timeout_seconds,
            service_heartbeat_poll_seconds=args.service_heartbeat_poll_seconds,
            now=args.now,
        )
        print(json.dumps(receipt.model_dump(mode="json"), sort_keys=True))
        return 0 if receipt.status in {"reviewed", "activated"} else 2
    if args.command == "supervisor-launch-status":
        status = holon_l4_launch_artifact_status(
            activation_dir=args.activation_dir,
            install_receipt_hash=args.install_receipt_hash,
            now=args.now,
        )
        print(json.dumps(status.model_dump(mode="json"), sort_keys=True))
        return 0 if status.status in {"installed", "started"} else 2

    plan = _read_plan(args.plan_json)
    if args.command == "supervisor-install":
        receipt = install_holon_l4_supervisor_plan(
            plan,
            approved_receipt_hash=args.approved_receipt_hash,
            install_dir=args.install_dir,
            now=args.now,
        )
    else:
        receipt = activate_holon_l4_supervisor_plan(
            plan,
            approved_receipt_hash=args.approved_receipt_hash,
            live=args.live,
            require_service_heartbeat=args.require_service_heartbeat,
            service_heartbeat_fresh_after_seconds=args.service_heartbeat_fresh_after_seconds,
            service_heartbeat_timeout_seconds=args.service_heartbeat_timeout_seconds,
            service_heartbeat_poll_seconds=args.service_heartbeat_poll_seconds,
            now=args.now,
        )
    print(json.dumps(receipt.model_dump(mode="json"), sort_keys=True))
    return 0 if receipt.status in {"reviewed", "installed", "activated"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
