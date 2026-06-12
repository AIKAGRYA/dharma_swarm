#!/usr/bin/env python3
"""Classify A2A quorum red blockers against current machine receipts.

Reviewer records are append-only evidence. When the substrate changes, old red
blocker text can become stale, but the quorum gate should not be cleared by
editing old reviews by hand. This tool reports which blockers still match the
current receipts and which need a fresh reviewer pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dharma.a2a.quorum_blocker_status.v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.runtime import a2a_prod_readiness_quorum  # noqa: E402

DEFAULT_DATE = "2026-06-13"
DEFAULT_QUORUM_ROOT = REPO_ROOT / "reports" / "a2a" / "prod_readiness_quorum"
DEFAULT_RECORD_DIR = DEFAULT_QUORUM_ROOT / DEFAULT_DATE
DEFAULT_QUORUM_PATH = DEFAULT_QUORUM_ROOT / "latest.json"
DEFAULT_DELIVERY_STATUS_PATH = DEFAULT_QUORUM_ROOT / "latest_delivery_status.json"
DEFAULT_REPAIR_PLAN_PATH = (
    REPO_ROOT
    / "reports"
    / "a2a"
    / "nats_reset"
    / DEFAULT_DATE
    / "A2A_LIVE_HANDLER_REPAIR_PLAN.json"
)
DEFAULT_FILE_BUS_GUARD_PATH = (
    REPO_ROOT
    / "reports"
    / "a2a"
    / "nats_reset"
    / DEFAULT_DATE
    / "FILE_BUS_GUARD_AFTER_HERMES_DISABLE.json"
)
DEFAULT_HERMES_GUARD_PATH = (
    REPO_ROOT
    / "reports"
    / "a2a"
    / "hermes_broadcast_guard"
    / DEFAULT_DATE
    / "HERMES_ALERT_ROUTER_BROADCAST_GUARD_APPLIED.json"
)
DEFAULT_RECEIPT_PATH = DEFAULT_RECORD_DIR / "QUORUM_BLOCKER_STATUS.json"
DEFAULT_LATEST_PATH = DEFAULT_QUORUM_ROOT / "latest_blocker_status.json"

CURRENT_STATUSES = {"current", "partially_resolved", "unclassified_current"}
RESOLVED_STATUSES = {"resolved"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _status_is(payload: dict[str, Any] | None, expected: str) -> bool:
    return bool(payload and payload.get("status") == expected)


def _target_map(delivery_status: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not delivery_status:
        return {}
    targets = delivery_status.get("targets")
    if not isinstance(targets, list):
        return {}
    return {
        str(target.get("target_agent_id")): target
        for target in targets
        if isinstance(target, dict) and target.get("target_agent_id")
    }


def _target_record_present(targets: dict[str, dict[str, Any]], agent_id: str) -> bool:
    target = targets.get(agent_id)
    return bool(target and target.get("reviewer_record_present") is True)


def _target_delivery_status(targets: dict[str, dict[str, Any]], agent_id: str) -> str:
    target = targets.get(agent_id) or {}
    return str(target.get("delivery_status") or "UNKNOWN")


def _pending_delivery_targets(delivery_status: dict[str, Any] | None) -> list[str]:
    summary = delivery_status.get("summary") if delivery_status else None
    if not isinstance(summary, dict):
        return []
    targets = summary.get("pending_delivery_targets")
    return [str(target) for target in targets] if isinstance(targets, list) else []


def build_current_facts(
    *,
    quorum: dict[str, Any] | None,
    delivery_status: dict[str, Any] | None,
    repair_plan: dict[str, Any] | None,
    file_bus_guard: dict[str, Any] | None,
    hermes_guard: dict[str, Any] | None,
) -> dict[str, Any]:
    targets = _target_map(delivery_status)
    model_families = quorum.get("model_families") if quorum else []
    agent_ids = quorum.get("agent_ids") if quorum else []
    red_records = quorum.get("red_blocker_records") if quorum else []
    median = quorum.get("readiness_percent_median") if quorum else 0
    pending_targets = _pending_delivery_targets(delivery_status)
    missing_reviewer_records = repair_plan.get("missing_reviewer_records") if repair_plan else []
    missing_targets = [
        str(item.get("target_agent_id"))
        for item in missing_reviewer_records
        if isinstance(item, dict) and item.get("target_agent_id")
    ]
    if not missing_targets:
        missing_targets = [
            agent_id
            for agent_id, target in targets.items()
            if target.get("reviewer_record_present") is not True
        ]
    return {
        "agent_id_count": len(agent_ids) if isinstance(agent_ids, list) else 0,
        "model_family_count": len(model_families) if isinstance(model_families, list) else 0,
        "median_readiness": median if isinstance(median, (int, float)) else 0,
        "red_blocker_records": red_records if isinstance(red_records, list) else [],
        "zero_red_blockers": not red_records,
        "fable_record_present": _target_record_present(targets, "fable_composer"),
        "hermes_record_present": _target_record_present(targets, "hermes_m5"),
        "fable_delivery_status": _target_delivery_status(targets, "fable_composer"),
        "hermes_delivery_status": _target_delivery_status(targets, "hermes_m5"),
        "pending_delivery_targets": pending_targets,
        "missing_reviewer_targets": sorted(set(missing_targets)),
        "repair_plan_ready_to_mutate": _status_is(repair_plan, "READY_TO_MUTATE"),
        "file_bus_guard_pass": _status_is(file_bus_guard, "PASS"),
        "hermes_broadcast_disabled": bool(hermes_guard and hermes_guard.get("broadcast_disabled") is True),
    }


def _classification(
    status: str,
    reason: str,
    evidence: list[str],
    next_action: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "evidence_refs": evidence,
        "next_action": next_action,
    }


def classify_blocker(text: str, facts: dict[str, Any], evidence: dict[str, str]) -> dict[str, Any]:
    lower = text.lower()
    enough_agents = facts["agent_id_count"] >= 2
    enough_models = facts["model_family_count"] >= 3
    missing_targets = set(facts["missing_reviewer_targets"])
    fable_or_hermes = "fable" in lower or "hermes" in lower
    mentions_pending = "pending" in lower or "unprocessed" in lower or "backlog" in lower
    mentions_missing_review = (
        "missing" in lower
        or "no hermes" in lower
        or "no fable" in lower
        or "no handler" in lower
        or "no reviewer" in lower
        or "reviewer json" in lower
        or "target-owned" in lower
        or "has been received" in lower
    )

    if (
        "only one reviewer" in lower
        or "two persistent" in lower
        or "three model" in lower
        or "before this qwen review only codex" in lower
    ):
        if enough_agents and enough_models:
            return _classification(
                "resolved",
                "Current quorum aggregate has at least two agent IDs and three model families.",
                [evidence["quorum"]],
                "Do not preserve this as a current blocker; ask reviewers to refresh against latest quorum.",
            )
        return _classification(
            "current",
            "Current quorum aggregate still lacks required reviewer/model diversity.",
            [evidence["quorum"]],
            "Collect additional independent reviewer records before claiming readiness.",
        )

    if "median" in lower or "below the 80" in lower or "80%" in lower:
        if facts["median_readiness"] >= 80:
            return _classification(
                "resolved",
                "Current quorum median readiness is at or above 80.",
                [evidence["quorum"]],
                "Ask reviewers to refresh the record if the old median appears in red blockers.",
            )
        return _classification(
            "current",
            "Current quorum median readiness is below 80.",
            [evidence["quorum"]],
            "Collect fresh reviewer records after target-owned handler evidence exists.",
        )

    if "red blocker" in lower or "zero red" in lower:
        if facts["zero_red_blockers"]:
            return _classification(
                "resolved",
                "Current quorum aggregate has no red-blocker records.",
                [evidence["quorum"]],
                "No action for this blocker.",
            )
        return _classification(
            "current",
            "Current quorum aggregate still lists reviewer records with red blockers.",
            [evidence["quorum"]],
            "Do not edit old reviews; collect fresh reviews after current blockers are cleared.",
        )

    if "alert_router" in lower or "broadcast" in lower or "file inbox" in lower or "filesystem inbox" in lower:
        if facts["file_bus_guard_pass"] and facts["hermes_broadcast_disabled"]:
            return _classification(
                "resolved",
                "Hermes legacy broadcast is disabled and the file-bus guard currently passes.",
                [evidence["file_bus_guard"], evidence["hermes_guard"]],
                "Keep both guards green; ask reviewers to refresh this stale blocker.",
            )
        return _classification(
            "current",
            "Hermes broadcast/file-bus guard evidence is missing or not green.",
            [evidence["file_bus_guard"], evidence["hermes_guard"]],
            "Restore the Hermes broadcast guard and file-bus guard before any readiness claim.",
        )

    if fable_or_hermes and mentions_pending and mentions_missing_review:
        if missing_targets:
            pending_targets = set(facts["pending_delivery_targets"])
            if pending_targets:
                return _classification(
                    "current",
                    "Target-owned reviewer records are missing and current delivery status still has pending targets.",
                    [evidence["delivery_status"], evidence["repair_plan"]],
                    "Attach target-owned handlers or reset as non-peer evidence; then collect reviewer records.",
                )
            return _classification(
                "partially_resolved",
                "The old pending/backlog claim is resolved, but target-owned Fable/Hermes reviewer records are still missing.",
                [evidence["delivery_status"], evidence["repair_plan"]],
                "Attach or wake target-owned Fable/Hermes handlers and produce the missing reviewer JSON receipts.",
            )
        return _classification(
            "resolved",
            "Target-owned reviewer records are present and no pending delivery target remains.",
            [evidence["delivery_status"], evidence["repair_plan"]],
            "Ask reviewers to refresh if this old blocker still appears.",
        )

    if fable_or_hermes and mentions_missing_review:
        if missing_targets:
            return _classification(
                "current",
                "Target-owned Fable/Hermes reviewer records are still missing.",
                [evidence["delivery_status"], evidence["repair_plan"]],
                "Produce fable_composer.json and hermes_m5.json from target-owned handlers or reviewers.",
            )
        return _classification(
            "resolved",
            "Target-owned Fable/Hermes reviewer records are present.",
            [evidence["delivery_status"], evidence["repair_plan"]],
            "Ask reviewers to refresh if this stale blocker remains in old records.",
        )

    if "publish ack" in lower or "publish_accepted" in lower or "jetstream" in lower:
        if missing_targets:
            return _classification(
                "current",
                "The system still has publish-only evidence for missing target-owned reviewer records.",
                [evidence["delivery_status"], evidence["repair_plan"]],
                "Require handler/domain/reviewer receipts; do not treat publish ack as live contact.",
            )
        return _classification(
            "resolved",
            "The cited publish-only gap no longer maps to missing target-owned reviewer records.",
            [evidence["delivery_status"], evidence["repair_plan"]],
            "Ask reviewers to refresh against current receipts.",
        )

    if "synthetic" in lower or "codex-owned" in lower or "independent" in lower:
        if missing_targets:
            return _classification(
                "current",
                "Independent target-owned Fable/Hermes evidence is still missing.",
                [evidence["delivery_status"], evidence["repair_plan"]],
                "Collect target-owned reviewer/domain receipts before claiming production readiness.",
            )
        return _classification(
            "resolved",
            "Independent target-owned reviewer evidence is now present.",
            [evidence["delivery_status"], evidence["repair_plan"]],
            "Refresh old reviewer records if they still cite this blocker.",
        )

    return _classification(
        "unclassified_current",
        "No deterministic rule proved this blocker stale; keep it blocking until a reviewer refreshes it.",
        [evidence["quorum"]],
        "Ask the reviewer to refresh or replace this blocker with a receipt-specific claim.",
    )


def build_blocker_status(
    *,
    record_dir: Path,
    quorum_path: Path,
    delivery_status_path: Path,
    repair_plan_path: Path,
    file_bus_guard_path: Path,
    hermes_guard_path: Path,
    created_at: str | None = None,
) -> dict[str, Any]:
    records, record_errors = a2a_prod_readiness_quorum.load_reviewer_records(record_dir)
    quorum = read_json(quorum_path)
    delivery_status = read_json(delivery_status_path)
    repair_plan = read_json(repair_plan_path)
    file_bus_guard = read_json(file_bus_guard_path)
    hermes_guard = read_json(hermes_guard_path)
    evidence = {
        "quorum": str(quorum_path),
        "delivery_status": str(delivery_status_path),
        "repair_plan": str(repair_plan_path),
        "file_bus_guard": str(file_bus_guard_path),
        "hermes_guard": str(hermes_guard_path),
    }
    facts = build_current_facts(
        quorum=quorum,
        delivery_status=delivery_status,
        repair_plan=repair_plan,
        file_bus_guard=file_bus_guard,
        hermes_guard=hermes_guard,
    )

    blocker_records: list[dict[str, Any]] = []
    for record in records:
        red_blockers = record.get("red_blockers")
        red_blockers = red_blockers if isinstance(red_blockers, list) else []
        classified: list[dict[str, Any]] = []
        for blocker in red_blockers:
            blocker_text = str(blocker)
            classification = classify_blocker(blocker_text, facts, evidence)
            classified.append({"text": blocker_text, **classification})
        counts = Counter(item["status"] for item in classified)
        blocker_records.append(
            {
                "agent_id": record.get("agent_id"),
                "model_family": record.get("model_family"),
                "role": record.get("role"),
                "source": record.get("_source"),
                "readiness_percent": record.get("readiness_percent"),
                "red_blocker_count": len(classified),
                "classification_counts": dict(sorted(counts.items())),
                "blockers": classified,
            }
        )

    all_blockers = [blocker for record in blocker_records for blocker in record["blockers"]]
    status_counts = Counter(blocker["status"] for blocker in all_blockers)
    current_count = sum(status_counts.get(status, 0) for status in CURRENT_STATUSES)
    resolved_count = sum(status_counts.get(status, 0) for status in RESOLVED_STATUSES)
    if current_count:
        status = "BLOCKED_BY_CURRENT_EVIDENCE"
    elif all_blockers:
        status = "BLOCKED_BY_STALE_REVIEW_RECORDS"
    else:
        status = "NO_REVIEWER_RED_BLOCKERS"

    recommended_actions: list[str] = []
    if facts["missing_reviewer_targets"]:
        recommended_actions.append(
            "Produce target-owned reviewer records for: "
            + ", ".join(facts["missing_reviewer_targets"])
        )
    if resolved_count:
        recommended_actions.append(
            "Ask reviewers with stale blockers to refresh records; do not hand-edit old reviewer JSON."
        )
    if facts["median_readiness"] < 80:
        recommended_actions.append(
            "Collect fresh readiness percentages after target-owned handler/domain receipts exist."
        )
    if not facts["zero_red_blockers"]:
        recommended_actions.append(
            "Keep latest.json NOT_READY until all reviewer red_blockers are cleared by fresh records."
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at or utc_now(),
        "status": status,
        "production_claim": False,
        "record_dir": str(record_dir),
        "inputs": evidence,
        "current_facts": facts,
        "summary": {
            "reviewer_record_count": len(records),
            "reviewer_record_errors": record_errors,
            "red_blocker_count": len(all_blockers),
            "current_or_unclassified_blocker_count": current_count,
            "resolved_stale_blocker_count": resolved_count,
            "classification_counts": dict(sorted(status_counts.items())),
        },
        "reviewer_records": blocker_records,
        "recommended_next_actions": recommended_actions,
        "interpretation": (
            "This receipt classifies old reviewer red blockers against current "
            "machine receipts. It does not clear the quorum gate and does not "
            "claim production readiness."
        ),
    }


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-dir", type=Path, default=DEFAULT_RECORD_DIR)
    parser.add_argument("--quorum-path", type=Path, default=DEFAULT_QUORUM_PATH)
    parser.add_argument("--delivery-status-path", type=Path, default=DEFAULT_DELIVERY_STATUS_PATH)
    parser.add_argument("--repair-plan-path", type=Path, default=DEFAULT_REPAIR_PLAN_PATH)
    parser.add_argument("--file-bus-guard-path", type=Path, default=DEFAULT_FILE_BUS_GUARD_PATH)
    parser.add_argument("--hermes-guard-path", type=Path, default=DEFAULT_HERMES_GUARD_PATH)
    parser.add_argument("--receipt-path", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--latest-path", type=Path, default=DEFAULT_LATEST_PATH)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-latest", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when current evidence still blocks production.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    payload = build_blocker_status(
        record_dir=args.record_dir.expanduser(),
        quorum_path=args.quorum_path.expanduser(),
        delivery_status_path=args.delivery_status_path.expanduser(),
        repair_plan_path=args.repair_plan_path.expanduser(),
        file_bus_guard_path=args.file_bus_guard_path.expanduser(),
        hermes_guard_path=args.hermes_guard_path.expanduser(),
    )
    if args.write:
        write_receipt(args.receipt_path.expanduser(), payload)
    if args.write_latest:
        write_receipt(args.latest_path.expanduser(), payload)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = payload["summary"]
        print(
            f"{payload['status']} current={summary['current_or_unclassified_blocker_count']} "
            f"resolved_stale={summary['resolved_stale_blocker_count']} "
            f"red_blockers={summary['red_blocker_count']}"
        )
    if args.check and payload["status"] == "BLOCKED_BY_CURRENT_EVIDENCE":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
