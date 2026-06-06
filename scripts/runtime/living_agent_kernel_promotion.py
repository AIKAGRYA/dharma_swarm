#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.living_agent_kernel_promotion import KernelPromotionStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage LivingAgentKernel promotion receipts.")
    parser.add_argument("--store-dir", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    promote = subparsers.add_parser("promote")
    promote.add_argument("--agent-uid", required=True)
    promote.add_argument(
        "--level",
        required=True,
        choices=["observer", "worker", "executor", "provider_executor"],
    )
    promote.add_argument("--allowed-source", action="append", default=[])
    promote.add_argument("--allowed-tool", action="append", default=[])
    promote.add_argument(
        "--allowed-work-kind",
        action="append",
        default=[],
        choices=[
            "read_only",
            "code_write",
            "long_running",
            "a2a_claim",
            "self_evolution",
            "promotion",
            "provider_execution",
        ],
    )
    promote.add_argument("--max-lease-seconds", type=int, default=300)
    promote.add_argument("--expires-at", default="")
    promote.add_argument("--reviewer", default="operator")
    promote.add_argument("--reason", default="")
    promote.add_argument("--evidence-kind", action="append", default=[])
    promote.add_argument("--evidence-json", action="append", default=[])
    promote.add_argument("--now", default=None)

    revoke = subparsers.add_parser("revoke")
    revoke.add_argument("--agent-uid", required=True)
    revoke.add_argument("--reviewer", default="operator")
    revoke.add_argument("--reason", default="promotion_revoked")
    revoke.add_argument("--now", default=None)

    status = subparsers.add_parser("status")
    status.add_argument("--agent-uid", default="")

    subparsers.add_parser("verify")

    args = parser.parse_args()
    store = KernelPromotionStore(args.store_dir)

    if args.command == "promote":
        receipt = store.append_promotion(
            agent_uid=args.agent_uid,
            level=args.level,
            allowed_sources=args.allowed_source,
            allowed_tools=args.allowed_tool,
            allowed_work_kinds=args.allowed_work_kind,
            max_lease_seconds=args.max_lease_seconds,
            expires_at=args.expires_at,
            reviewer=args.reviewer,
            reason=args.reason,
            evidence_refs=_evidence_refs(args.evidence_kind, args.evidence_json),
            now=args.now,
        )
        print(json.dumps(receipt.model_dump(mode="json"), sort_keys=True))
        return 0

    if args.command == "revoke":
        receipt = store.revoke_promotion(
            agent_uid=args.agent_uid,
            reviewer=args.reviewer,
            reason=args.reason,
            now=args.now,
        )
        print(json.dumps(receipt.model_dump(mode="json"), sort_keys=True))
        return 0

    if args.command == "status":
        if args.agent_uid:
            receipt = store.latest_for_agent(args.agent_uid)
            payload: Any = receipt.model_dump(mode="json") if receipt is not None else {}
        else:
            payload = [receipt.model_dump(mode="json") for receipt in store.promotions()]
        print(json.dumps(payload, sort_keys=True))
        return 0

    if args.command == "verify":
        ok, errors = store.verify_promotion_ledger()
        print(json.dumps({"ok": ok, "errors": errors}, sort_keys=True))
        return 0 if ok else 1

    return 2


def _evidence_refs(kinds: list[str], raw_json: list[str]) -> list[dict[str, Any]]:
    refs = [{"kind": kind} for kind in kinds if kind]
    for raw in raw_json:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("--evidence-json must decode to an object")
        refs.append(parsed)
    return refs


if __name__ == "__main__":
    raise SystemExit(main())
