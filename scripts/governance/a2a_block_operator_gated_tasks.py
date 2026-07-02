#!/usr/bin/env python3
"""Block stale A2A rows that explicitly require operator action.

This is intentionally not a generic stale-task sweeper.  It only targets
non-terminal queue rows whose body contains an explicit operator gate phrase
such as ``operator-gated`` or ``operator sign-off``.  Stale claimed work without
an explicit gate remains open for task-specific execution or a separate proof.
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

DEFAULT_STALE_HOURS = 24.0
DEFAULT_AGENT_UID = "a2a_supervisor"
EXPLICIT_GATE_PHRASES = (
    "operator-gated",
    "operator gated",
    "operator approval required",
    "operator sign-off",
    "operator signoff",
    "operator sign off",
    "dhyana sign-off",
    "dhyana signoff",
)


@dataclass(frozen=True)
class OperatorGateAction:
    row_index: int
    task_id: str
    status: str
    claimed_by: str
    claimed_at: str
    age_hours: float | None
    matched_phrase: str
    a2a_receipt_id: str
    validation: dict[str, Any]
    reason: str


@dataclass(frozen=True)
class OperatorGateSkip:
    row_index: int
    task_id: str
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


def _matched_gate_phrase(row: dict[str, Any]) -> str:
    body = str(row.get("body") or "").lower()
    for phrase in EXPLICIT_GATE_PHRASES:
        if phrase in body:
            return phrase
    return ""


def _row_status(row: dict[str, Any]) -> str:
    return str(row.get("status") or "pending").lower()


def _body_excerpt(row: dict[str, Any], *, limit: int = 360) -> str:
    body = " ".join(str(row.get("body") or "").split())
    if len(body) <= limit:
        return body
    return f"{body[:limit]}..."


def _build_receipt(
    row: dict[str, Any],
    *,
    agent_uid: str,
    matched_phrase: str,
    age_hours: float | None,
    stale_after_hours: float,
    timestamp: str,
) -> dict[str, Any]:
    task_id = str(row.get("id") or "")
    claimed_by = str(row.get("claimed_by") or "")
    claimed_at = str(row.get("claimed_at") or "")
    status = _row_status(row)
    summary = (
        "Blocked stale A2A row because its task body explicitly requires "
        f"operator action ({matched_phrase!r}) and no terminal receipt exists."
    )
    return build_task_receipt(
        task_id=task_id,
        agent_uid=agent_uid,
        status="blocked",
        summary=summary,
        authority="operator_gated_stale_task_supervisor_block",
        completion_via="a2a_block_operator_gated_tasks",
        failure_reason="explicit_operator_gate_without_terminal_receipt",
        evidence={
            "age_hours": age_hours,
            "body_excerpt": _body_excerpt(row),
            "claimed_at": claimed_at,
            "claimed_by": claimed_by,
            "created": str(row.get("created") or row.get("created_at") or ""),
            "matched_gate_phrase": matched_phrase,
            "original_status": status,
            "original_to": str(row.get("to") or ""),
            "row_index_scope": "single_non_terminal_row",
            "stale_after_hours": stale_after_hours,
            "supervisor_scope": "block_only_no_task_execution_claimed",
        },
        evaluation={
            "overall_verdict": "blocked_pending_operator_action",
            "criteria_results": [
                {"criterion": "row_is_non_terminal", "passed": True},
                {"criterion": "row_is_stale", "passed": age_hours is None or age_hours >= stale_after_hours},
                {"criterion": "explicit_operator_gate_phrase_present", "passed": bool(matched_phrase)},
                {"criterion": "no_embedded_terminal_receipt", "passed": not isinstance(row.get("receipt"), dict)},
                {"criterion": "ordinary_stale_work_not_swept", "passed": True},
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
    stale_after_hours: float,
    now: datetime,
    timestamp: str,
) -> tuple[OperatorGateAction | None, OperatorGateSkip | None, dict[str, Any] | None]:
    task_id = str(row.get("id") or "")
    status = _row_status(row)
    lifecycle = task_lifecycle_state(row)
    if lifecycle.get("closed"):
        return None, None, None
    if status != "claimed" and status not in OPEN_STATUSES:
        return (
            None,
            OperatorGateSkip(row_index, task_id, status, "unsupported_non_terminal_status", status),
            None,
        )

    matched_phrase = _matched_gate_phrase(row)
    if not matched_phrase:
        return None, None, None
    age = _age_hours(row, now)
    if age is not None and age < stale_after_hours:
        return None, OperatorGateSkip(row_index, task_id, status, "not_stale", str(age)), None
    if isinstance(row.get("receipt"), dict):
        return None, OperatorGateSkip(row_index, task_id, status, "embedded_receipt_present", ""), None

    receipt = _build_receipt(
        row,
        agent_uid=agent_uid,
        matched_phrase=matched_phrase,
        age_hours=age,
        stale_after_hours=stale_after_hours,
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
            OperatorGateSkip(row_index, task_id, status, "block_receipt_invalid", "; ".join(validation["errors"])),
            None,
        )

    return (
        OperatorGateAction(
            row_index=row_index,
            task_id=task_id,
            status=status,
            claimed_by=str(row.get("claimed_by") or ""),
            claimed_at=str(row.get("claimed_at") or ""),
            age_hours=age,
            matched_phrase=matched_phrase,
            a2a_receipt_id=str(receipt.get("receipt_id") or ""),
            validation=validation,
            reason="explicit_operator_gate_stale_without_terminal_receipt",
        ),
        None,
        receipt,
    )


def find_actions(
    rows: list[dict[str, Any]],
    *,
    agent_uid: str,
    stale_after_hours: float,
    now: datetime,
    timestamp: str,
) -> tuple[list[OperatorGateAction], list[OperatorGateSkip], dict[int, dict[str, Any]]]:
    actions: list[OperatorGateAction] = []
    skips: list[OperatorGateSkip] = []
    receipts_by_index: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        action, skip, receipt = _candidate_for_row(
            row,
            row_index=index,
            agent_uid=agent_uid,
            stale_after_hours=stale_after_hours,
            now=now,
            timestamp=timestamp,
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
    stale_after_hours: float = DEFAULT_STALE_HOURS,
    timestamp: str | None = None,
    output: Path | None = None,
) -> dict[str, Any]:
    ts = timestamp or _utc_now()
    now = _parse_time(ts) or datetime.now(timezone.utc)
    state = Path(state_root) if state_root is not None else None
    queue = queue_path(state)
    rows = read_queue(state)
    actions, skips, receipts_by_index = find_actions(
        rows,
        agent_uid=agent_uid,
        stale_after_hours=stale_after_hours,
        now=now,
        timestamp=ts,
    )

    backup_path = ""
    applied: list[dict[str, Any]] = []
    if apply and actions:
        backup = queue.with_name(f"{queue.name}.a2a-operator-gated-block-{_safe_timestamp(ts)}.bak")
        shutil.copy2(queue, backup)
        backup_path = str(backup)
        for action in actions:
            receipt = receipts_by_index[action.row_index]
            row = rows[action.row_index]
            claimed_by = str(row.get("claimed_by") or "")
            closed = close_task(
                action.task_id,
                agent_uid=agent_uid,
                status="blocked",
                receipt=receipt,
                state_root=state,
                closed_via="a2a_block_operator_gated_tasks",
                require_artifact_or_evidence=True,
                allow_supervisor_block=bool(claimed_by and claimed_by != agent_uid),
                now=ts,
            )
            applied.append(
                {
                    "task_id": action.task_id,
                    "status": closed.get("status"),
                    "receipt_id": closed.get("receipt_id"),
                    "claimed_by": claimed_by,
                    "matched_phrase": action.matched_phrase,
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
        "stale_after_hours": stale_after_hours,
        "explicit_gate_phrases": list(EXPLICIT_GATE_PHRASES),
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
    parser.add_argument("--stale-after-hours", type=float, default=DEFAULT_STALE_HOURS)
    parser.add_argument("--timestamp", default=None, help="Receipt/report timestamp.")
    parser.add_argument("--output", type=Path, default=None, help="Optional report JSON path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = build_report(
        state_root=args.state_root,
        apply=args.apply,
        agent_uid=args.agent_uid,
        stale_after_hours=args.stale_after_hours,
        timestamp=args.timestamp,
        output=args.output,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
