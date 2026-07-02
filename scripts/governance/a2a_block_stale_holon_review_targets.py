#!/usr/bin/env python3
"""Block stale target-seat Holon review rows with supervisor receipts.

This is intentionally narrower than a stale-row sweeper. It only targets the
two known Holon Package Consolidation adversarial review rows when the assigned
review seat is stale, the referenced plan path is missing, and the expected
seat-specific review deliverable is absent.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.a2a.agent_presence import AgentPresence, list_agent_presence  # noqa: E402
from dharma_swarm.operator_core.a2a_task_lifecycle import (  # noqa: E402
    OPEN_STATUSES,
    build_task_receipt,
    close_task,
    queue_path,
    read_queue,
    task_lifecycle_state,
    validate_task_receipt,
)
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness  # noqa: E402

DEFAULT_AGENT_UID = "a2a_supervisor"
DEFAULT_STALE_HOURS = 24.0
DEFAULT_HEARTBEAT_STALE_HOURS = 24.0
DEFAULT_TASK_IDS = (
    "holon-plan-review-opus-20260612",
    "holon-plan-review-cursor-20260612",
)
EXPECTED_TARGETS = {
    "holon-plan-review-opus-20260612": "opus_composer",
    "holon-plan-review-cursor-20260612": "fable_5_cursor",
}
PLAN_PATH_RE = re.compile(r"(/Users/dhyana/dharma_swarm/docs/sovereign_holons/08_PACKAGE_CONSOLIDATION_PLAN\.md)")


@dataclass(frozen=True)
class HolonReviewAction:
    row_index: int
    task_id: str
    target_agent: str
    age_hours: float | None
    target_presence: dict[str, Any]
    plan_path: str
    deliverable_path: str
    a2a_receipt_id: str
    validation: dict[str, Any]
    reason: str


@dataclass(frozen=True)
class HolonReviewSkip:
    row_index: int
    task_id: str
    target_agent: str
    status: str
    reason: str
    detail: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_timestamp(value: str) -> str:
    return value.replace("+00:00", "Z").replace(":", "").replace("-", "").replace(".", "")


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_hours(row: dict[str, Any], now: datetime) -> float | None:
    for key in ("created", "created_at", "submitted_at", "updated_at"):
        parsed = _parse_time(row.get(key))
        if parsed is not None:
            return round(max((now - parsed).total_seconds(), 0.0) / 3600.0, 3)
    return None


def _row_status(row: dict[str, Any]) -> str:
    return str(row.get("status") or "pending").lower()


def _body_excerpt(row: dict[str, Any], *, limit: int = 360) -> str:
    body = " ".join(str(row.get("body") or "").split())
    if len(body) <= limit:
        return body
    return f"{body[:limit]}..."


def _presence_by_uid(
    *,
    state_root: Path | None,
    now: datetime,
) -> dict[str, AgentPresence]:
    agents_root = state_root / "agents" if state_root is not None else None
    bus_root = state_root / "a2a_bus" if state_root is not None else None
    return {
        presence.agent_uid: presence
        for presence in list_agent_presence(agents_root=agents_root, a2a_bus_root=bus_root, now=now)
    }


def _fallback_presence(agent_uid: str) -> AgentPresence:
    return AgentPresence(
        agent_uid=agent_uid,
        status="missing",
        heartbeat_status="RED",
        last_seen_at="",
        age_hours=None,
        source_path="agent_presence_projection_missing",
    )


def _presence_is_stale(presence: AgentPresence, *, heartbeat_stale_hours: float) -> bool:
    if presence.heartbeat_status != "RED":
        return False
    return presence.age_hours is None or presence.age_hours >= heartbeat_stale_hours


def _plan_path(row: dict[str, Any]) -> Path | None:
    match = PLAN_PATH_RE.search(str(row.get("body") or ""))
    if not match:
        return None
    return Path(match.group(1))


def _deliverable_path(target_agent: str, *, state_root: Path | None) -> Path:
    if state_root is not None:
        return state_root / "a2a_bus" / "collab" / "convergence" / f"HOLON_PLAN_REVIEW_{target_agent}.md"
    return Path.home() / ".dharma" / "a2a_bus" / "collab" / "convergence" / f"HOLON_PLAN_REVIEW_{target_agent}.md"


def _build_receipt(
    row: dict[str, Any],
    *,
    agent_uid: str,
    target_agent: str,
    presence: AgentPresence,
    age_hours: float | None,
    stale_after_hours: float,
    heartbeat_stale_hours: float,
    plan_path: Path,
    deliverable_path: Path,
    timestamp: str,
) -> dict[str, Any]:
    task_id = str(row.get("id") or "")
    summary = (
        "Blocked stale Holon review row because the assigned review seat is stale, "
        "the referenced plan path is missing, and the expected review deliverable is absent."
    )
    return build_task_receipt(
        task_id=task_id,
        agent_uid=agent_uid,
        status="blocked",
        summary=summary,
        authority="stale_holon_review_target_supervisor_block",
        completion_via="a2a_block_stale_holon_review_targets",
        failure_reason="target_review_seat_stale_and_source_plan_missing",
        evidence={
            "age_hours": age_hours,
            "body_excerpt": _body_excerpt(row),
            "created": str(row.get("created") or row.get("created_at") or ""),
            "deliverable_path": str(deliverable_path),
            "deliverable_path_exists": deliverable_path.exists(),
            "heartbeat_stale_hours": heartbeat_stale_hours,
            "original_from": str(row.get("from") or ""),
            "original_status": _row_status(row),
            "original_to": str(row.get("to") or ""),
            "original_type": str(row.get("type") or ""),
            "plan_path": str(plan_path),
            "plan_path_exists": plan_path.exists(),
            "stale_after_hours": stale_after_hours,
            "supervisor_scope": "block_only_no_review_completion_or_target_impersonation",
            "target_presence": presence.to_dict(),
        },
        evaluation={
            "overall_verdict": "blocked_stale_target_review_without_source_plan_or_deliverable",
            "criteria_results": [
                {"criterion": "row_is_known_holon_review_task", "passed": task_id in DEFAULT_TASK_IDS},
                {"criterion": "row_is_open_unclaimed", "passed": True},
                {"criterion": "row_is_stale", "passed": age_hours is None or age_hours >= stale_after_hours},
                {"criterion": "assigned_target_matches_task", "passed": target_agent == EXPECTED_TARGETS.get(task_id)},
                {"criterion": "target_presence_is_stale_or_missing", "passed": True},
                {"criterion": "referenced_plan_path_missing", "passed": not plan_path.exists()},
                {"criterion": "target_deliverable_missing", "passed": not deliverable_path.exists()},
                {"criterion": "supervisor_does_not_claim_review_result", "passed": True},
            ],
            "gate_results": [],
        },
        timestamp=timestamp,
    )


def _candidate_for_row(
    row: dict[str, Any],
    *,
    row_index: int,
    agent_uid: str,
    task_ids: set[str],
    presence_by_uid: dict[str, AgentPresence],
    stale_after_hours: float,
    heartbeat_stale_hours: float,
    now: datetime,
    timestamp: str,
    state_root: Path | None,
) -> tuple[HolonReviewAction | None, HolonReviewSkip | None, dict[str, Any] | None]:
    task_id = str(row.get("id") or "")
    status = _row_status(row)
    target_agent = str(row.get("to") or "")
    lifecycle = task_lifecycle_state(row)
    if lifecycle.get("closed"):
        return None, None, None
    if task_id not in task_ids:
        return None, None, None
    if status not in OPEN_STATUSES:
        return None, HolonReviewSkip(row_index, task_id, target_agent, status, "unsupported_status", status), None
    expected_target = EXPECTED_TARGETS.get(task_id)
    if target_agent != expected_target:
        return (
            None,
            HolonReviewSkip(row_index, task_id, target_agent, status, "target_agent_mismatch", str(expected_target)),
            None,
        )

    age = _age_hours(row, now)
    if age is not None and age < stale_after_hours:
        return None, HolonReviewSkip(row_index, task_id, target_agent, status, "row_not_stale", str(age)), None

    presence = presence_by_uid.get(target_agent) or _fallback_presence(target_agent)
    if not _presence_is_stale(presence, heartbeat_stale_hours=heartbeat_stale_hours):
        return (
            None,
            HolonReviewSkip(
                row_index,
                task_id,
                target_agent,
                status,
                "target_presence_not_stale",
                json.dumps(presence.to_dict(), sort_keys=True),
            ),
            None,
        )

    plan_path = _plan_path(row)
    if plan_path is None:
        return None, HolonReviewSkip(row_index, task_id, target_agent, status, "plan_path_not_found_in_body", ""), None
    if plan_path.exists():
        return None, HolonReviewSkip(row_index, task_id, target_agent, status, "plan_path_exists", str(plan_path)), None

    deliverable = _deliverable_path(target_agent, state_root=state_root)
    if deliverable.exists():
        return (
            None,
            HolonReviewSkip(row_index, task_id, target_agent, status, "target_deliverable_present", str(deliverable)),
            None,
        )

    receipt = _build_receipt(
        row,
        agent_uid=agent_uid,
        target_agent=target_agent,
        presence=presence,
        age_hours=age,
        stale_after_hours=stale_after_hours,
        heartbeat_stale_hours=heartbeat_stale_hours,
        plan_path=plan_path,
        deliverable_path=deliverable,
        timestamp=timestamp,
    )
    validation = validate_task_receipt(
        receipt,
        task_id=task_id,
        agent_uid=agent_uid,
        status="blocked",
        require_artifact_or_evidence=True,
    )
    if not validation["valid"]:
        return (
            None,
            HolonReviewSkip(row_index, task_id, target_agent, status, "block_receipt_invalid", "; ".join(validation["errors"])),
            None,
        )

    return (
        HolonReviewAction(
            row_index=row_index,
            task_id=task_id,
            target_agent=target_agent,
            age_hours=age,
            target_presence=presence.to_dict(),
            plan_path=str(plan_path),
            deliverable_path=str(deliverable),
            a2a_receipt_id=str(receipt.get("receipt_id") or ""),
            validation=validation,
            reason="stale_holon_target_review_without_source_plan_or_deliverable",
        ),
        None,
        receipt,
    )


def find_actions(
    rows: list[dict[str, Any]],
    *,
    state_root: Path | None,
    agent_uid: str,
    task_ids: set[str],
    stale_after_hours: float,
    heartbeat_stale_hours: float,
    now: datetime,
    timestamp: str,
) -> tuple[list[HolonReviewAction], list[HolonReviewSkip], dict[int, dict[str, Any]]]:
    actions: list[HolonReviewAction] = []
    skips: list[HolonReviewSkip] = []
    receipts_by_index: dict[int, dict[str, Any]] = {}
    presence_by_uid = _presence_by_uid(state_root=state_root, now=now)
    for index, row in enumerate(rows):
        action, skip, receipt = _candidate_for_row(
            row,
            row_index=index,
            agent_uid=agent_uid,
            task_ids=task_ids,
            presence_by_uid=presence_by_uid,
            stale_after_hours=stale_after_hours,
            heartbeat_stale_hours=heartbeat_stale_hours,
            now=now,
            timestamp=timestamp,
            state_root=state_root,
        )
        if action is not None and receipt is not None:
            actions.append(action)
            receipts_by_index[index] = receipt
        if skip is not None:
            skips.append(skip)
    return actions, skips, receipts_by_index


def build_report(
    state_root: Path | str | None = None,
    *,
    apply: bool = False,
    agent_uid: str = DEFAULT_AGENT_UID,
    task_ids: list[str] | None = None,
    stale_after_hours: float = DEFAULT_STALE_HOURS,
    heartbeat_stale_hours: float = DEFAULT_HEARTBEAT_STALE_HOURS,
    timestamp: str | None = None,
    output: Path | None = None,
) -> dict[str, Any]:
    ts = timestamp or _utc_now()
    now = _parse_time(ts) or datetime.now(timezone.utc)
    state = Path(state_root) if state_root is not None else None
    queue = queue_path(state)
    rows = read_queue(state)
    target_task_ids = set(task_ids or DEFAULT_TASK_IDS)
    actions, skips, receipts_by_index = find_actions(
        rows,
        state_root=state,
        agent_uid=agent_uid,
        task_ids=target_task_ids,
        stale_after_hours=stale_after_hours,
        heartbeat_stale_hours=heartbeat_stale_hours,
        now=now,
        timestamp=ts,
    )

    backup_path = ""
    applied: list[dict[str, Any]] = []
    if apply and actions:
        backup = queue.with_name(f"{queue.name}.a2a-stale-holon-review-block-{_safe_timestamp(ts)}.bak")
        shutil.copy2(queue, backup)
        backup_path = str(backup)
        for action in actions:
            receipt = receipts_by_index[action.row_index]
            closed = close_task(
                action.task_id,
                agent_uid=agent_uid,
                status="blocked",
                receipt=receipt,
                state_root=state,
                closed_via="a2a_block_stale_holon_review_targets",
                require_artifact_or_evidence=True,
                now=ts,
            )
            applied.append(
                {
                    "task_id": action.task_id,
                    "status": closed.get("status"),
                    "receipt_id": closed.get("receipt_id"),
                    "target_agent": action.target_agent,
                }
            )

    readiness = evaluate_a2a_readiness(state)
    report = {
        "schema_version": 1,
        "generated_at": ts,
        "queue_path": str(queue),
        "applied": apply,
        "backup_path": backup_path,
        "agent_uid": agent_uid,
        "task_ids": sorted(target_task_ids),
        "stale_after_hours": stale_after_hours,
        "heartbeat_stale_hours": heartbeat_stale_hours,
        "candidate_count": len(actions),
        "applied_count": len(applied),
        "skip_count": len(skips),
        "actions": [asdict(action) for action in actions],
        "skips": [asdict(skip) for skip in skips],
        "applied_rows": applied,
        "post_readiness": {
            "ready": readiness.ready,
            "open_tasks": readiness.open_tasks,
            "unknown_status_tasks": readiness.unknown_status_tasks,
            "unverified_closed_tasks": readiness.unverified_closed_tasks,
            "reasons": list(readiness.reasons),
        },
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Mutate the live queue after writing a backup.")
    parser.add_argument("--state-root", type=Path, default=None, help="Override DHARMA state root.")
    parser.add_argument("--agent-uid", default=DEFAULT_AGENT_UID, help="Supervisor identity to stamp on receipts.")
    parser.add_argument("--task-id", action="append", default=None, help="Task id to target; defaults to the two Holon rows.")
    parser.add_argument("--stale-after-hours", type=float, default=DEFAULT_STALE_HOURS)
    parser.add_argument("--heartbeat-stale-hours", type=float, default=DEFAULT_HEARTBEAT_STALE_HOURS)
    parser.add_argument("--timestamp", default=None, help="Receipt/report timestamp.")
    parser.add_argument("--output", type=Path, default=None, help="Optional report JSON path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = build_report(
        state_root=args.state_root,
        apply=args.apply,
        agent_uid=args.agent_uid,
        task_ids=args.task_id,
        stale_after_hours=args.stale_after_hours,
        heartbeat_stale_hours=args.heartbeat_stale_hours,
        timestamp=args.timestamp,
        output=args.output,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
