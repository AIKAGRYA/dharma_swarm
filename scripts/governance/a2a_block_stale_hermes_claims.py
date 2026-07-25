#!/usr/bin/env python3
"""Block stale Hermes-claimed A2A rows with supervisor receipts.

This is intentionally not a generic stale-task sweeper. It targets claimed
rows whose claimant is one of the explicit Hermes identities, whose claim is
stale, whose claimant presence is stale/missing, and whose inbox has no valid
terminal A2A receipt for the task. The supervisor blocks the stale claim; it
does not claim the task outcome.
"""

from __future__ import annotations

import argparse
import json
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
    build_task_receipt,
    close_task,
    inbox_dir,
    queue_path,
    read_queue,
    task_lifecycle_state,
    validate_task_receipt,
)
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness  # noqa: E402

DEFAULT_AGENT_UID = "a2a_supervisor"
DEFAULT_STALE_HOURS = 24.0
DEFAULT_HEARTBEAT_STALE_HOURS = 24.0
DEFAULT_CLAIMANT_UIDS = ("hermes-m5",)


@dataclass(frozen=True)
class MatchingReceipt:
    path: str
    status: str
    validation: dict[str, Any]


@dataclass(frozen=True)
class StaleClaimAction:
    row_index: int
    task_id: str
    claimed_by: str
    claimed_at: str
    age_hours: float | None
    claimant_presence: dict[str, Any]
    checked_receipt_paths: list[str]
    a2a_receipt_id: str
    validation: dict[str, Any]
    reason: str


@dataclass(frozen=True)
class StaleClaimSkip:
    row_index: int
    task_id: str
    claimed_by: str
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
    for key in ("claimed_at", "created", "created_at", "submitted_at", "updated_at"):
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


def _receipt_candidate_paths(task_id: str, *, claimed_by: str, state_root: Path | None) -> list[Path]:
    inbox = inbox_dir(claimed_by, state_root)
    names = [
        f"receipt_{task_id}.json",
        f"claimed_{task_id}.json",
    ]
    return [inbox / name for name in names]


def _load_matching_receipt(
    path: Path,
    *,
    task_id: str,
    claimed_by: str,
) -> MatchingReceipt | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return MatchingReceipt(str(path), "unreadable", {"valid": False, "errors": ["receipt file unreadable"]})
    if not isinstance(payload, dict):
        return MatchingReceipt(str(path), "invalid", {"valid": False, "errors": ["receipt payload is not an object"]})
    receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else payload
    if not isinstance(receipt, dict) or receipt.get("schema_version") != "dharma_a2a_task_receipt.v1":
        return None
    status = str(receipt.get("status") or "").lower()
    if status not in {"completed", "failed", "blocked"}:
        return None
    validation = validate_task_receipt(
        receipt,
        task_id=task_id,
        agent_uid=claimed_by,
        status=status,  # type: ignore[arg-type]
        require_artifact_or_evidence=True,
    )
    return MatchingReceipt(str(path), status, validation)


def _matching_terminal_receipt(
    task_id: str,
    *,
    claimed_by: str,
    state_root: Path | None,
) -> tuple[MatchingReceipt | None, list[str]]:
    paths = _receipt_candidate_paths(task_id, claimed_by=claimed_by, state_root=state_root)
    checked = [str(path) for path in paths]
    invalid: MatchingReceipt | None = None
    for path in paths:
        match = _load_matching_receipt(path, task_id=task_id, claimed_by=claimed_by)
        if match is None:
            continue
        if match.validation.get("valid"):
            return match, checked
        invalid = invalid or match
    return invalid, checked


def _build_receipt(
    row: dict[str, Any],
    *,
    agent_uid: str,
    presence: AgentPresence,
    age_hours: float | None,
    stale_after_hours: float,
    heartbeat_stale_hours: float,
    checked_receipt_paths: list[str],
    timestamp: str,
) -> dict[str, Any]:
    task_id = str(row.get("id") or "")
    claimed_by = str(row.get("claimed_by") or "")
    summary = (
        "Blocked stale claimed A2A row because the Hermes claimant is stale/inactive "
        "and no valid terminal A2A receipt exists in the claimant inbox."
    )
    return build_task_receipt(
        task_id=task_id,
        agent_uid=agent_uid,
        status="blocked",
        summary=summary,
        authority="stale_hermes_claim_supervisor_block",
        completion_via="a2a_block_stale_hermes_claims",
        failure_reason="claimed_agent_inactive_without_terminal_receipt",
        evidence={
            "age_hours": age_hours,
            "body_excerpt": _body_excerpt(row),
            "checked_receipt_paths": checked_receipt_paths,
            "claimed_at": str(row.get("claimed_at") or ""),
            "claimed_by": claimed_by,
            "claimant_presence": presence.to_dict(),
            "created": str(row.get("created") or row.get("created_at") or ""),
            "heartbeat_stale_hours": heartbeat_stale_hours,
            "original_from": str(row.get("from") or ""),
            "original_status": _row_status(row),
            "original_to": str(row.get("to") or ""),
            "original_type": str(row.get("type") or ""),
            "stale_after_hours": stale_after_hours,
            "supervisor_scope": "block_only_no_task_execution_or_completion_claimed",
        },
        evaluation={
            "overall_verdict": "blocked_stale_claimed_without_terminal_receipt",
            "criteria_results": [
                {"criterion": "row_status_is_claimed", "passed": True},
                {"criterion": "row_claim_is_stale", "passed": age_hours is None or age_hours >= stale_after_hours},
                {"criterion": "claimant_identity_is_explicitly_targeted", "passed": claimed_by in DEFAULT_CLAIMANT_UIDS},
                {"criterion": "claimant_presence_is_stale_or_missing", "passed": True},
                {"criterion": "no_valid_terminal_claimant_receipt", "passed": True},
                {"criterion": "supervisor_does_not_claim_task_result", "passed": True},
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
    claimant_uids: set[str],
    presence_by_uid: dict[str, AgentPresence],
    stale_after_hours: float,
    heartbeat_stale_hours: float,
    now: datetime,
    timestamp: str,
    state_root: Path | None,
) -> tuple[StaleClaimAction | None, StaleClaimSkip | None, dict[str, Any] | None]:
    task_id = str(row.get("id") or "")
    status = _row_status(row)
    claimed_by = str(row.get("claimed_by") or "")
    lifecycle = task_lifecycle_state(row)
    if lifecycle.get("closed"):
        return None, None, None
    if status != "claimed":
        return None, None, None
    if not claimed_by:
        return (
            None,
            StaleClaimSkip(row_index, task_id, claimed_by, status, "claimed_by_missing", ""),
            None,
        )
    if claimed_by not in claimant_uids:
        return (
            None,
            StaleClaimSkip(row_index, task_id, claimed_by, status, "claimant_not_in_allowlist", claimed_by),
            None,
        )

    age = _age_hours(row, now)
    if age is not None and age < stale_after_hours:
        return None, StaleClaimSkip(row_index, task_id, claimed_by, status, "claim_not_stale", str(age)), None

    presence = presence_by_uid.get(claimed_by) or _fallback_presence(claimed_by)
    if not _presence_is_stale(presence, heartbeat_stale_hours=heartbeat_stale_hours):
        return (
            None,
            StaleClaimSkip(
                row_index,
                task_id,
                claimed_by,
                status,
                "claimant_presence_not_stale",
                json.dumps(presence.to_dict(), sort_keys=True),
            ),
            None,
        )

    matching_receipt, checked_paths = _matching_terminal_receipt(
        task_id,
        claimed_by=claimed_by,
        state_root=state_root,
    )
    if matching_receipt is not None:
        reason = "claimant_terminal_receipt_present" if matching_receipt.validation.get("valid") else "claimant_receipt_invalid"
        return (
            None,
            StaleClaimSkip(row_index, task_id, claimed_by, status, reason, json.dumps(asdict(matching_receipt))),
            None,
        )

    receipt = _build_receipt(
        row,
        agent_uid=agent_uid,
        presence=presence,
        age_hours=age,
        stale_after_hours=stale_after_hours,
        heartbeat_stale_hours=heartbeat_stale_hours,
        checked_receipt_paths=checked_paths,
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
            StaleClaimSkip(row_index, task_id, claimed_by, status, "block_receipt_invalid", "; ".join(validation["errors"])),
            None,
        )

    return (
        StaleClaimAction(
            row_index=row_index,
            task_id=task_id,
            claimed_by=claimed_by,
            claimed_at=str(row.get("claimed_at") or ""),
            age_hours=age,
            claimant_presence=presence.to_dict(),
            checked_receipt_paths=checked_paths,
            a2a_receipt_id=str(receipt.get("receipt_id") or ""),
            validation=validation,
            reason="stale_hermes_claim_without_terminal_receipt",
        ),
        None,
        receipt,
    )


def find_actions(
    rows: list[dict[str, Any]],
    *,
    state_root: Path | None,
    agent_uid: str,
    claimant_uids: set[str],
    stale_after_hours: float,
    heartbeat_stale_hours: float,
    now: datetime,
    timestamp: str,
) -> tuple[list[StaleClaimAction], list[StaleClaimSkip], dict[int, dict[str, Any]]]:
    actions: list[StaleClaimAction] = []
    skips: list[StaleClaimSkip] = []
    receipts_by_index: dict[int, dict[str, Any]] = {}
    presence_by_uid = _presence_by_uid(state_root=state_root, now=now)
    for index, row in enumerate(rows):
        action, skip, receipt = _candidate_for_row(
            row,
            row_index=index,
            agent_uid=agent_uid,
            claimant_uids=claimant_uids,
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
    claimant_uids: list[str] | None = None,
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
    allowed_claimants = set(claimant_uids or DEFAULT_CLAIMANT_UIDS)
    actions, skips, receipts_by_index = find_actions(
        rows,
        state_root=state,
        agent_uid=agent_uid,
        claimant_uids=allowed_claimants,
        stale_after_hours=stale_after_hours,
        heartbeat_stale_hours=heartbeat_stale_hours,
        now=now,
        timestamp=ts,
    )

    backup_path = ""
    applied: list[dict[str, Any]] = []
    if apply and actions:
        backup = queue.with_name(f"{queue.name}.a2a-stale-hermes-claim-block-{_safe_timestamp(ts)}.bak")
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
                closed_via="a2a_block_stale_hermes_claims",
                require_artifact_or_evidence=True,
                allow_supervisor_block=True,
                now=ts,
            )
            applied.append(
                {
                    "task_id": action.task_id,
                    "status": closed.get("status"),
                    "receipt_id": closed.get("receipt_id"),
                    "claimed_by": action.claimed_by,
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
        "claimant_uids": sorted(allowed_claimants),
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
    parser.add_argument("--claimant-uid", action="append", default=None, help="Claimant uid to target; defaults to hermes-m5.")
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
        claimant_uids=args.claimant_uid,
        stale_after_hours=args.stale_after_hours,
        heartbeat_stale_hours=args.heartbeat_stale_hours,
        timestamp=args.timestamp,
        output=args.output,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
