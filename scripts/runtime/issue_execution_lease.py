#!/usr/bin/env python3
"""Issue a narrow local execution lease for Phase-A A2A wake loops."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.operator_core.execution_lease import (  # noqa: E402
    build_execution_lease,
    default_lease_root,
    validate_execution_lease,
    write_execution_lease,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lease-root", default=str(default_lease_root()))
    parser.add_argument("--lease-id", default="")
    parser.add_argument("--issuer", default="operator")
    parser.add_argument("--issued-to", required=True)
    parser.add_argument("--task-id", default="")
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--custody-grade", default="Q1")
    parser.add_argument("--allowed-action", action="append", default=[])
    parser.add_argument("--allowed-path", action="append", default=[])
    parser.add_argument("--forbidden-action", action="append", default=[])
    parser.add_argument("--max-seconds", type=int, default=900)
    parser.add_argument("--max-model-calls", type=int, default=3)
    parser.add_argument("--max-usd", type=float, default=0.0)
    parser.add_argument("--write", action="store_true", help="write lease to --lease-root; default is dry-run")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    lease = build_execution_lease(
        lease_id=args.lease_id,
        issuer=args.issuer,
        issued_to=args.issued_to,
        task_id=args.task_id,
        correlation_id=args.correlation_id,
        custody_grade=args.custody_grade,
        allowed_actions=args.allowed_action,
        allowed_paths=args.allowed_path,
        forbidden_actions=args.forbidden_action or None,
        max_seconds=args.max_seconds,
        max_model_calls=args.max_model_calls,
        max_usd=args.max_usd,
    )
    validation = validate_execution_lease(lease, agent_uid=args.issued_to, task_id=args.task_id)
    result = {
        "schema_version": "dharma.execution_lease.issue_result.v1",
        "dry_run": not args.write,
        "lease": lease,
        "validation": validation.to_dict(),
    }
    if not validation.valid:
        print(json.dumps(result, indent=2, sort_keys=True), file=sys.stderr)
        return 2
    if args.write:
        path = write_execution_lease(lease, args.lease_root)
        result["lease_path"] = str(path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
