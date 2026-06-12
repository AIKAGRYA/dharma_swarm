#!/usr/bin/env python3
"""Build a non-mutating repair plan for A2A live-handler gaps.

This script joins the daemon-wiring audit with production-quorum delivery
status. It does not load, unload, start, stop, pull, ack, publish, reset, or
delete anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dharma.a2a.live_handler_repair_plan.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATE = "2026-06-13"
DEFAULT_RESET_DIR = REPO_ROOT / "reports" / "a2a" / "nats_reset" / DEFAULT_DATE
DEFAULT_QUORUM_DIR = REPO_ROOT / "reports" / "a2a" / "prod_readiness_quorum" / DEFAULT_DATE
DEFAULT_AUDIT = DEFAULT_RESET_DIR / "A2A_DAEMON_WIRING_AUDIT.json"
DEFAULT_DELIVERY_STATUS = DEFAULT_QUORUM_DIR / "QUORUM_DELIVERY_STATUS.json"
DEFAULT_RECEIPT = DEFAULT_RESET_DIR / "A2A_LIVE_HANDLER_REPAIR_PLAN.json"

ENTRYPOINT_ISSUES = {
    "import_error",
    "missing_module_target",
    "missing_python_module",
    "missing_script_file",
    "missing_script_target",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def issue_types(candidate: dict[str, Any]) -> set[str]:
    issues = candidate.get("issues")
    if not isinstance(issues, list):
        return set()
    return {
        str(issue.get("type"))
        for issue in issues
        if isinstance(issue, dict) and issue.get("type")
    }


def action_for_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    types = issue_types(candidate)
    actions: list[str] = []
    if types & ENTRYPOINT_ISSUES:
        actions.append(
            "Replace or repoint the LaunchAgent entrypoint to a repo-owned live script/module."
        )
    if "broker_scope_mismatch" in types:
        actions.append(
            "Set the daemon broker scope explicitly to the intended AGNI context or remove it from production routing."
        )
    if not actions:
        actions.append("Keep observing; no deterministic repair action was inferred.")
    return {
        "label": candidate.get("label"),
        "status": candidate.get("status"),
        "path": candidate.get("path"),
        "working_directory": candidate.get("working_directory"),
        "program_arguments": candidate.get("program_arguments"),
        "issue_types": sorted(types),
        "repair_actions": actions,
        "must_not_claim": [
            "Do not treat a running local HTTP server as AGNI durable-consumer proof.",
            "Do not treat filesystem inbox files as peer-agent response.",
        ],
    }


def delivery_gap_for_target(target: dict[str, Any]) -> dict[str, Any] | None:
    status = str(target.get("delivery_status") or "")
    if status == "REVIEW_RECORD_PRESENT":
        return None
    consumer_info = target.get("consumer_info")
    consumer_info = consumer_info if isinstance(consumer_info, dict) else {}
    pending = consumer_info.get("num_pending")
    ack_pending = consumer_info.get("num_ack_pending")
    if status == "CONSUMER_EMPTY_NO_DELIVERY" and not pending and not ack_pending:
        return None
    return {
        "target_agent_id": target.get("target_agent_id"),
        "subject": target.get("subject"),
        "consumer": target.get("consumer"),
        "delivery_status": status,
        "num_pending": pending,
        "num_ack_pending": ack_pending,
        "next_required_receipt": target.get("next_required_receipt"),
        "repair_actions": [
            "Attach a real target-owned AGNI pull handler and let it write the reviewer/domain receipt.",
            "Or reset the consumer as an explicit inbox reset with backup and receipt; do not call it peer review.",
        ],
        "must_not_claim": [
            "PUBLISH_ACCEPTED is not live contact.",
            "Pending durable messages are not semantic agreement.",
        ],
    }


def missing_reviewer_record_for_target(target: dict[str, Any]) -> dict[str, Any] | None:
    status = str(target.get("delivery_status") or "")
    if status == "REVIEW_RECORD_PRESENT":
        return None
    consumer_info = target.get("consumer_info")
    consumer_info = consumer_info if isinstance(consumer_info, dict) else {}
    return {
        "target_agent_id": target.get("target_agent_id"),
        "subject": target.get("subject"),
        "consumer": target.get("consumer"),
        "delivery_status": status,
        "num_pending": consumer_info.get("num_pending"),
        "num_ack_pending": consumer_info.get("num_ack_pending"),
        "next_required_receipt": target.get("next_required_receipt"),
        "blocks_production_quorum": True,
        "must_not_claim": [
            "An empty durable consumer is not a target-owned reviewer record.",
            "READY_TO_MUTATE is not production readiness.",
        ],
    }


def build_plan(
    *,
    audit_path: Path,
    delivery_status_path: Path,
    created_at: str | None = None,
) -> dict[str, Any]:
    audit = read_json(audit_path)
    delivery_status = read_json(delivery_status_path)

    candidates = audit.get("candidates")
    candidates = candidates if isinstance(candidates, list) else []
    failing_candidates = [
        action_for_candidate(candidate)
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("status") != "PASS"
    ]

    targets = delivery_status.get("targets")
    targets = targets if isinstance(targets, list) else []
    delivery_gaps = [
        gap
        for target in targets
        if isinstance(target, dict)
        for gap in [delivery_gap_for_target(target)]
        if gap is not None
    ]
    missing_reviewer_records = [
        gap
        for target in targets
        if isinstance(target, dict)
        for gap in [missing_reviewer_record_for_target(target)]
        if gap is not None
    ]

    issue_counter = Counter(
        issue_type
        for candidate in failing_candidates
        for issue_type in candidate.get("issue_types", [])
    )
    delivery_counter = Counter(str(gap["delivery_status"]) for gap in missing_reviewer_records)
    status = "READY_TO_MUTATE" if not failing_candidates and not delivery_gaps else "REPAIR_REQUIRED"
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at or utc_now(),
        "status": status,
        "production_claim": False,
        "audit_path": str(audit_path),
        "delivery_status_path": str(delivery_status_path),
        "daemon_audit_status": audit.get("status"),
        "delivery_status": delivery_status.get("status"),
        "summary": {
            "failing_daemon_count": len(failing_candidates),
            "delivery_gap_count": len(delivery_gaps),
            "missing_reviewer_record_count": len(missing_reviewer_records),
            "daemon_issue_counts": dict(sorted(issue_counter.items())),
            "delivery_status_counts": dict(sorted(delivery_counter.items())),
        },
        "failing_daemons": failing_candidates,
        "delivery_gaps": delivery_gaps,
        "missing_reviewer_records": missing_reviewer_records,
        "safe_execution_order": [
            "Back up current LaunchAgent plists and current AGNI consumer info.",
            "Decide for each pending consumer whether the target-owned handler exists now or whether this is a reset.",
            "If resetting, reset consumers with an explicit reset receipt and no peer-review claim.",
            "If repairing handlers, repoint LaunchAgents to repo-owned AGNI-aware handlers and rerun the daemon audit.",
            "When daemon audit passes and delivery gaps are empty, attach or re-solicit target-owned handlers.",
            "Do not claim production readiness until reviewer/domain receipts exist and quorum validates READY.",
        ],
        "check_commands": [
            "python3 scripts/runtime/a2a_daemon_wiring_audit.py --write --json",
            "python3 scripts/runtime/a2a_prod_readiness_delivery_status.py --date 2026-06-13 --probe-live --write --write-latest --json",
            "python3 scripts/runtime/a2a_live_handler_repair_plan.py --write --json",
        ],
        "interpretation": (
            "This receipt is a repair plan only. It is not proof of peer review, "
            "handler ack, domain receipt, or production readiness."
        ),
    }


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-path", default=str(DEFAULT_AUDIT))
    parser.add_argument("--delivery-status-path", default=str(DEFAULT_DELIVERY_STATUS))
    parser.add_argument("--receipt-path", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--write", action="store_true", help="Write the JSON receipt.")
    parser.add_argument("--json", action="store_true", help="Print full JSON output.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when repair is still required.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    payload = build_plan(
        audit_path=Path(args.audit_path).expanduser(),
        delivery_status_path=Path(args.delivery_status_path).expanduser(),
    )
    if args.write:
        write_receipt(Path(args.receipt_path).expanduser(), payload)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{payload['status']} failing_daemons="
            f"{payload['summary']['failing_daemon_count']} "
            f"delivery_gaps={payload['summary']['delivery_gap_count']}"
        )
    if args.check and payload["status"] != "READY_TO_MUTATE":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
