#!/usr/bin/env python3
"""Report route health for A2A production-readiness reviewers.

This verifier is non-mutating. It reads reviewer solicitation packets, reviewer
records, delivery status, live-handler repair plans, local persistent-agent
identity/state files, and reviewer-attempt receipts. It does not send messages,
pull messages, ack consumers, start daemons, or claim production readiness.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "reports" / "a2a" / "prod_readiness_quorum"
DEFAULT_DATE = "2026-06-13"
DEFAULT_RECORD_DIR = DEFAULT_ROOT / DEFAULT_DATE
DEFAULT_DELIVERY_STATUS = DEFAULT_ROOT / "latest_delivery_status.json"
DEFAULT_REPAIR_PLAN = (
    REPO_ROOT
    / "reports"
    / "a2a"
    / "nats_reset"
    / DEFAULT_DATE
    / "A2A_LIVE_HANDLER_REPAIR_PLAN.json"
)
DEFAULT_RECEIPT = DEFAULT_RECORD_DIR / "REVIEWER_ROUTE_HEALTH.json"
DEFAULT_LATEST = DEFAULT_ROOT / "latest_route_health.json"
DEFAULT_AGENTS_ROOT = Path.home() / ".dharma" / "agents"
DEFAULT_STATE_ROOT = Path.home() / ".dharma" / "a2a_bus" / "state"

SCHEMA_VERSION = "dharma.a2a.reviewer_route_health.v1"

COMMANDS_BY_AGENT = {
    "fable_composer": ["claude"],
    "hermes_m5": ["hermes"],
    "codex_composer": ["codex"],
    "qwen_code": ["qwen", "qwen-code"],
    "gemini_reviewer": ["gemini"],
}

MISSING_REVIEWER_STATUSES = {
    "CONSUMER_EMPTY_NO_DELIVERY",
    "DELIVERED_NO_REVIEW_RECORD",
    "DELIVERY_IN_PROGRESS_ACK_PENDING",
    "PENDING_DELIVERY",
    "PUBLISH_ACCEPTED_NOT_DELIVERY_VERIFIED",
}
PROVIDER_BLOCKING_FAILURES = {
    "PROVIDER_CREDIT_EXHAUSTED",
    "PROVIDER_QUOTA_EXHAUSTED",
    "PROVIDER_AUTH_MISSING",
    "PROVIDER_AUTH_FAILED",
}
TIMEOUT_FAILURES = {"PROVIDER_TIMEOUT", "CLI_TIMEOUT", "TIMEOUT"}

CommandLookup = Callable[[str], str | None]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def safe_read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return read_json(path), None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def load_requests(record_dir: Path) -> dict[str, dict[str, Any]]:
    requests: dict[str, dict[str, Any]] = {}
    for path in sorted((record_dir / "requests").glob("*.json")):
        payload = read_json(path)
        agent_id = str(payload.get("target_agent_id") or path.stem)
        payload["_source"] = str(path)
        requests[agent_id] = payload
    return requests


def reviewer_record_path(record_dir: Path, agent_id: str) -> Path:
    return record_dir / f"{agent_id}.json"


def load_delivery_targets(path: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(path)
    targets = payload.get("targets")
    if not isinstance(targets, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for target in targets:
        if not isinstance(target, dict):
            continue
        agent_id = target.get("target_agent_id")
        if isinstance(agent_id, str) and agent_id:
            out[agent_id] = target
    return out


def load_repair_targets(path: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(path)
    targets = payload.get("missing_reviewer_records")
    if not isinstance(targets, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for target in targets:
        if not isinstance(target, dict):
            continue
        agent_id = target.get("target_agent_id")
        if isinstance(agent_id, str) and agent_id:
            out[agent_id] = target
    return out


def infer_failure_class(path: Path, attempt: dict[str, Any]) -> str | None:
    explicit = attempt.get("failure_class")
    if isinstance(explicit, str) and explicit:
        return explicit
    haystack = " ".join(
        str(value)
        for value in (
            path.name,
            attempt.get("status"),
            attempt.get("stderr_summary"),
            attempt.get("stdout_summary"),
            attempt.get("error"),
        )
        if value
    ).lower()
    if "credit" in haystack:
        return "PROVIDER_CREDIT_EXHAUSTED"
    if "quota" in haystack:
        return "PROVIDER_QUOTA_EXHAUSTED"
    if "auth" in haystack or "credential" in haystack:
        return "PROVIDER_AUTH_FAILED"
    if "timeout" in haystack or "timed out" in haystack:
        return "PROVIDER_TIMEOUT"
    if "failed" in haystack:
        return "UNKNOWN_FAILURE"
    return None


def attempt_timestamp(path: Path, attempt: dict[str, Any]) -> str:
    for key in ("created_at", "attempted_at", "timestamp"):
        value = attempt.get(key)
        if isinstance(value, str) and value:
            return value
    return path.name


def load_attempts(record_dir: Path) -> dict[str, list[dict[str, Any]]]:
    attempts: dict[str, list[dict[str, Any]]] = {}
    for path in sorted((record_dir / "reviewer_attempts").glob("*.json")):
        payload, error = safe_read_json(path)
        if payload is None:
            payload = {"status": "UNREADABLE", "error": error}
        agent_id = payload.get("agent_id") or payload.get("target_agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            parts = path.stem.split("-")
            agent_id = parts[1] if len(parts) > 1 else path.stem
        payload["_source"] = str(path)
        payload["_sort_key"] = attempt_timestamp(path, payload)
        payload["failure_class"] = infer_failure_class(path, payload)
        attempts.setdefault(agent_id, []).append(payload)
    for agent_attempts in attempts.values():
        agent_attempts.sort(key=lambda item: str(item.get("_sort_key") or ""))
    return attempts


def state_name_candidates(agent_id: str) -> list[str]:
    names = [agent_id]
    swapped = agent_id.replace("_", "-")
    if swapped not in names:
        names.append(swapped)
    return names


def agent_file_candidates(
    agent_id: str,
    *,
    agents_root: Path,
    state_root: Path,
) -> list[Path]:
    candidates = [
        agents_root / agent_id / "identity.json",
        agents_root / agent_id / "living_agent.json",
        agents_root / agent_id / "identity_invariant.json",
    ]
    for name in state_name_candidates(agent_id):
        candidates.append(state_root / f"{name}.json")
    return candidates


def _dig(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def summarize_agent_file(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "agent_uid": payload.get("agent_uid") or payload.get("agent"),
        "address": payload.get("address"),
        "provider": payload.get("provider") or _dig(payload, ("current_embodiment", "provider")),
        "model": (
            payload.get("model")
            or payload.get("model_identity")
            or _dig(payload, ("current_embodiment", "model"))
        ),
        "harness": payload.get("harness") or _dig(payload, ("current_embodiment", "harness")),
        "status": payload.get("status"),
        "process_running": payload.get("process_running"),
        "process_status": payload.get("process_status"),
        "wake_loop_active": payload.get("wake_loop_active"),
        "last_heartbeat": payload.get("last_heartbeat"),
        "route_status": _dig(payload, ("model_route", "route_status")),
        "preferred_channel": payload.get("preferred_channel"),
    }
    return {
        "path": str(path),
        "observed_fields": {
            key: value for key, value in fields.items() if value not in (None, "")
        },
    }


def summarize_agent_state(
    agent_id: str,
    *,
    agents_root: Path,
    state_root: Path,
) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in agent_file_candidates(
        agent_id,
        agents_root=agents_root,
        state_root=state_root,
    ):
        if not path.exists():
            continue
        payload, error = safe_read_json(path)
        if payload is None:
            errors.append(f"{path}: {error}")
            continue
        summaries.append(summarize_agent_file(path, payload))
    return {
        "agent_files_found": len(summaries),
        "agent_files": summaries,
        "read_errors": errors,
    }


def command_health(
    agent_id: str,
    *,
    command_lookup: CommandLookup = shutil.which,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for command in COMMANDS_BY_AGENT.get(agent_id, []):
        path = command_lookup(command)
        checks.append({"command": command, "path": path, "available": path is not None})
    return checks


def route_status_from_agent_state(agent_state: dict[str, Any]) -> str:
    text = json.dumps(agent_state, sort_keys=True).lower()
    if "standing wake loop pending" in text or "session_borne" in text:
        return "SESSION_BORNE_STANDING_LOOP_PENDING"
    if '"wake_loop_active": false' in text:
        return "WAKE_LOOP_INACTIVE"
    if "operational" in text:
        return "REGISTERED_OR_OPERATIONAL"
    if agent_state.get("agent_files_found"):
        return "REGISTERED_STATE_FOUND"
    return "NO_LOCAL_AGENT_STATE_FOUND"


def classify_route(
    *,
    reviewer_record_present: bool,
    delivery_target: dict[str, Any] | None,
    latest_attempt: dict[str, Any] | None,
    agent_state: dict[str, Any],
) -> tuple[str, str, str]:
    if reviewer_record_present:
        return (
            "REVIEW_RECORD_PRESENT",
            "Target reviewer record exists; route health no longer blocks quorum.",
            "Rerun the production quorum aggregate.",
        )

    failure = (
        latest_attempt.get("failure_class")
        if isinstance(latest_attempt, dict)
        else None
    )
    if isinstance(failure, str) and failure in PROVIDER_BLOCKING_FAILURES:
        return (
            "PROVIDER_BLOCKED",
            f"Latest target-owned attempt failed with {failure}.",
            "Restore provider/credit/auth route, then rerun the target-owned reviewer.",
        )
    if isinstance(failure, str) and failure in TIMEOUT_FAILURES:
        return (
            "PROVIDER_TIMEOUT_OR_HANDLER_STALLED",
            f"Latest target-owned attempt failed with {failure}.",
            "Rerun with a bounded receipt or repair the live handler before claiming review.",
        )

    delivery_status = str((delivery_target or {}).get("delivery_status") or "")
    if delivery_status == "PENDING_DELIVERY":
        return (
            "PENDING_DELIVERY_NO_TARGET_RECEIPT",
            "Durable consumer still has pending messages and no reviewer record.",
            "Attach the target-owned handler or explicitly reset with a receipt.",
        )
    if delivery_status in MISSING_REVIEWER_STATUSES:
        state_status = route_status_from_agent_state(agent_state)
        if state_status in {
            "SESSION_BORNE_STANDING_LOOP_PENDING",
            "WAKE_LOOP_INACTIVE",
        }:
            return (
                "UNATTENDED_TARGET_HANDLER_MISSING",
                f"Delivery status is {delivery_status}; agent state is {state_status}.",
                "Build or wake the unattended target handler, then collect its receipt.",
            )
        return (
            "EMPTY_OR_UNVERIFIED_TARGET_ROUTE",
            f"Delivery status is {delivery_status}; no target-owned record exists.",
            "Run a target-owned route that writes the reviewer/domain receipt.",
        )

    if latest_attempt is None:
        return (
            "NO_TARGET_OWNED_ATTEMPT_RECORDED",
            "No reviewer record and no target-owned attempt receipt were found.",
            "Create a bounded target-owned attempt receipt for this reviewer.",
        )

    return (
        "TARGET_ROUTE_UNPROVEN",
        "A prior attempt exists, but no deterministic route-health rule clears it.",
        "Refresh the target-owned attempt and write a machine-readable result.",
    )


def build_route_health(
    *,
    record_dir: Path,
    delivery_status_path: Path,
    repair_plan_path: Path,
    agents_root: Path = DEFAULT_AGENTS_ROOT,
    state_root: Path = DEFAULT_STATE_ROOT,
    command_lookup: CommandLookup = shutil.which,
    created_at: str | None = None,
) -> dict[str, Any]:
    requests = load_requests(record_dir)
    delivery_targets = load_delivery_targets(delivery_status_path)
    repair_targets = load_repair_targets(repair_plan_path)
    attempts = load_attempts(record_dir)
    routes: list[dict[str, Any]] = []

    for agent_id in sorted(requests):
        request = requests[agent_id]
        record_path = reviewer_record_path(record_dir, agent_id)
        reviewer_record_present = record_path.exists()
        agent_state = summarize_agent_state(
            agent_id,
            agents_root=agents_root,
            state_root=state_root,
        )
        agent_attempts = attempts.get(agent_id, [])
        latest_attempt = agent_attempts[-1] if agent_attempts else None
        classification, reason, next_action = classify_route(
            reviewer_record_present=reviewer_record_present,
            delivery_target=delivery_targets.get(agent_id),
            latest_attempt=latest_attempt,
            agent_state=agent_state,
        )
        delivery_target = delivery_targets.get(agent_id) or {}
        routes.append(
            {
                "target_agent_id": agent_id,
                "requested_role": request.get("requested_role"),
                "model_family_hint": request.get("model_family_hint"),
                "route": request.get("route"),
                "request_path": request.get("_source"),
                "reviewer_record_path": str(record_path),
                "reviewer_record_present": reviewer_record_present,
                "delivery_status": delivery_target.get("delivery_status"),
                "consumer": delivery_target.get("consumer"),
                "subject": delivery_target.get("subject"),
                "repair_plan_entry": repair_targets.get(agent_id),
                "target_owned_attempt_count": len(agent_attempts),
                "latest_attempt": latest_attempt,
                "command_health": command_health(agent_id, command_lookup=command_lookup),
                "agent_state": agent_state,
                "route_classification": classification,
                "blocks_production_quorum": not reviewer_record_present,
                "reason": reason,
                "next_action": next_action,
            }
        )

    counts = Counter(route["route_classification"] for route in routes)
    blocking = [
        route["target_agent_id"]
        for route in routes
        if route["blocks_production_quorum"]
    ]
    status = "ROUTE_HEALTH_BLOCKED" if blocking else "ALL_REVIEWER_ROUTES_SATISFIED"
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at or utc_now(),
        "status": status,
        "production_claim": False,
        "record_dir": str(record_dir),
        "inputs": {
            "delivery_status": str(delivery_status_path),
            "repair_plan": str(repair_plan_path),
            "agents_root": str(agents_root),
            "state_root": str(state_root),
        },
        "summary": {
            "request_count": len(routes),
            "reviewer_records_present": sum(
                1 for route in routes if route["reviewer_record_present"]
            ),
            "reviewer_records_missing": len(blocking),
            "blocking_targets": blocking,
            "route_classification_counts": dict(sorted(counts.items())),
        },
        "routes": routes,
        "recommended_next_actions": [
            route["next_action"]
            for route in routes
            if route["blocks_production_quorum"]
        ],
        "interpretation": (
            "This receipt explains whether requested reviewer routes can currently "
            "produce target-owned records. It does not replace reviewer records, "
            "clear red blockers, or claim A2A production readiness."
        ),
    }


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-dir", type=Path, default=DEFAULT_RECORD_DIR)
    parser.add_argument("--delivery-status-path", type=Path, default=DEFAULT_DELIVERY_STATUS)
    parser.add_argument("--repair-plan-path", type=Path, default=DEFAULT_REPAIR_PLAN)
    parser.add_argument("--agents-root", type=Path, default=DEFAULT_AGENTS_ROOT)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--receipt-path", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--latest-path", type=Path, default=DEFAULT_LATEST)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-latest", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when any requested reviewer route is still blocked.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    payload = build_route_health(
        record_dir=args.record_dir.expanduser(),
        delivery_status_path=args.delivery_status_path.expanduser(),
        repair_plan_path=args.repair_plan_path.expanduser(),
        agents_root=args.agents_root.expanduser(),
        state_root=args.state_root.expanduser(),
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
            f"{payload['status']} missing={summary['reviewer_records_missing']} "
            f"blocking={','.join(summary['blocking_targets']) or 'none'}"
        )
    if args.check and payload["status"] == "ROUTE_HEALTH_BLOCKED":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
