#!/usr/bin/env python3
"""Manage LivingAgentKernel external worker lifecycle receipts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.operator_core.living_agent_kernel_workers import KernelExternalWorkerStore  # noqa: E402


def _json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"invalid JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("value must decode to a JSON object")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-dir", default=None, help="Kernel store directory. Defaults to ~/.dharma/living_agent_kernel.")
    sub = parser.add_subparsers(dest="command", required=True)

    register = sub.add_parser("register", help="Register or update an external worker.")
    register.add_argument("--worker-id", required=True)
    register.add_argument("--role", default="worker")
    register.add_argument("--allowed-source", action="append", default=[])
    register.add_argument("--max-lease-seconds", type=int, default=300)
    register.add_argument("--metadata", type=_json_object, default={})
    register.add_argument("--now", default=None)

    heartbeat = sub.add_parser("heartbeat", help="Append a worker heartbeat.")
    heartbeat.add_argument("--worker-id", required=True)
    heartbeat.add_argument("--status", choices=["online", "offline"], default="online")
    heartbeat.add_argument("--metadata", type=_json_object, default={})
    heartbeat.add_argument("--now", default=None)

    status = sub.add_parser("status", help="Project worker freshness state.")
    status.add_argument("--stale-after-seconds", type=int, default=120)
    status.add_argument("--offline-after-seconds", type=int, default=3600)
    status.add_argument("--now", default=None)

    lease = sub.add_parser("lease", help="Lease the next eligible wake to a fresh worker.")
    lease.add_argument("--worker-id", required=True)
    lease.add_argument("--lease-seconds", type=int, default=300)
    lease.add_argument("--heartbeat-max-age-seconds", type=int, default=120)
    lease.add_argument("--now", default=None)

    complete = sub.add_parser("complete", help="Record an external worker result and terminal wake state.")
    complete.add_argument("--worker-id", required=True)
    complete.add_argument("--wake-id", required=True)
    complete.add_argument("--status", choices=["completed", "review", "blocked", "failed"], required=True)
    complete.add_argument("--summary", default="")
    complete.add_argument("--result-ref", type=_json_object, default={})
    complete.add_argument("--now", default=None)

    recover = sub.add_parser("recover", help="Requeue expired wakes leased by stale/offline workers.")
    recover.add_argument("--stale-after-seconds", type=int, default=120)
    recover.add_argument("--offline-after-seconds", type=int, default=3600)
    recover.add_argument("--now", default=None)

    verify = sub.add_parser("verify", help="Verify external worker receipt ledgers.")
    verify.set_defaults(command="verify")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = KernelExternalWorkerStore(args.store_dir)
    if args.command == "register":
        result = store.register_worker(
            args.worker_id,
            role=args.role,
            allowed_sources=args.allowed_source,
            max_lease_seconds=args.max_lease_seconds,
            metadata=args.metadata,
            now=args.now,
        )
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
        return 0
    if args.command == "heartbeat":
        result = store.heartbeat_worker(
            args.worker_id,
            status=args.status,
            metadata=args.metadata,
            now=args.now,
        )
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
        return 0
    if args.command == "status":
        result = store.worker_states(
            stale_after_seconds=args.stale_after_seconds,
            offline_after_seconds=args.offline_after_seconds,
            now=args.now,
        )
        print(json.dumps([state.model_dump(mode="json") for state in result], sort_keys=True))
        return 0
    if args.command == "lease":
        result = store.lease_worker_wake(
            args.worker_id,
            lease_seconds=args.lease_seconds,
            heartbeat_max_age_seconds=args.heartbeat_max_age_seconds,
            now=args.now,
        )
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
        return 0 if result.status in {"leased", "idle"} else 2
    if args.command == "complete":
        result = store.complete_worker_wake(
            args.worker_id,
            args.wake_id,
            status=args.status,
            summary=args.summary,
            result_ref=args.result_ref,
            now=args.now,
        )
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
        return 0
    if args.command == "recover":
        result = store.recover_stale_worker_leases(
            stale_after_seconds=args.stale_after_seconds,
            offline_after_seconds=args.offline_after_seconds,
            now=args.now,
        )
        print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
        return 0
    ok, errors = store.verify_worker_ledgers()
    print(json.dumps({"ok": ok, "errors": errors}, sort_keys=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
