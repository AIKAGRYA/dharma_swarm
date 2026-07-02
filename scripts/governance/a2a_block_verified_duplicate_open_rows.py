#!/usr/bin/env python3
"""Block open A2A duplicate rows when the same task id is already verified.

This is intentionally narrower than a stale-task sweeper.  It only targets
open, unclaimed rows whose exact task id appears in another terminal queue row
with a valid embedded ``dharma_a2a_task_receipt.v1`` receipt and substantive
artifact/evidence.  It never infers across different task ids and it does not
touch claimed work.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
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
    queue_path,
    task_lifecycle_state,
    validate_task_receipt,
)
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness  # noqa: E402

DEFAULT_AGENT_UID = "a2a_supervisor"


@dataclass(frozen=True)
class VerifiedDuplicateAction:
    row_index: int
    task_id: str
    original_status: str
    duplicate_terminal_row_index: int
    terminal_status: str
    terminal_agent_uid: str
    terminal_receipt_id: str
    terminal_authority: str
    a2a_receipt_id: str
    validation: dict[str, Any]
    reason: str


@dataclass(frozen=True)
class VerifiedDuplicateSkip:
    row_index: int
    task_id: str
    status: str
    reason: str
    detail: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_timestamp(value: str) -> str:
    return value.replace("+00:00", "Z").replace(":", "").replace("-", "").replace(".", "")


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number}: queue row must be an object")
        rows.append(row)
    return rows


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(row, ensure_ascii=True, sort_keys=True) for row in rows)
    if payload:
        payload += "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        tmp = Path(handle.name)
        handle.write(payload)
    tmp.replace(path)


def _row_status(row: dict[str, Any]) -> str:
    return str(row.get("status") or "pending").lower()


def _row_agent(row: dict[str, Any]) -> str:
    return str(
        row.get("closed_by")
        or row.get("completed_by")
        or row.get("blocked_by")
        or row.get("failed_by")
        or row.get("claimed_by")
        or ""
    )


def _body_excerpt(row: dict[str, Any], *, limit: int = 360) -> str:
    body = " ".join(str(row.get("body") or row.get("closure_note") or "").split())
    if len(body) <= limit:
        return body
    return f"{body[:limit]}..."


def _receipt_artifacts(receipt: dict[str, Any]) -> list[str]:
    artifacts: list[str] = []
    for item in receipt.get("artifacts") or []:
        if isinstance(item, str):
            artifacts.append(item)
        elif isinstance(item, dict):
            value = item.get("path") or item.get("file") or item.get("artifact_path")
            if value:
                artifacts.append(str(value))
    return artifacts


def _has_substantive_terminal_evidence(row: dict[str, Any]) -> bool:
    receipt = row.get("receipt")
    if not isinstance(receipt, dict):
        return False
    if _receipt_artifacts(receipt):
        return True
    evidence = receipt.get("evidence")
    return isinstance(evidence, dict) and bool(evidence)


def _terminal_duplicate_for(
    rows: list[dict[str, Any]],
    *,
    row_index: int,
    task_id: str,
) -> tuple[int, dict[str, Any]] | None:
    for index, candidate in enumerate(rows):
        if index == row_index or str(candidate.get("id") or "") != task_id:
            continue
        lifecycle = task_lifecycle_state(candidate, require_artifact_or_evidence=True)
        if lifecycle.get("closed") and lifecycle.get("verified") and _has_substantive_terminal_evidence(candidate):
            return index, candidate
    return None


def _build_receipt(
    row: dict[str, Any],
    *,
    terminal_index: int,
    terminal_row: dict[str, Any],
    agent_uid: str,
    timestamp: str,
) -> dict[str, Any]:
    task_id = str(row.get("id") or "")
    terminal_receipt = terminal_row.get("receipt") if isinstance(terminal_row.get("receipt"), dict) else {}
    terminal_receipt = terminal_receipt if isinstance(terminal_receipt, dict) else {}
    terminal_agent = _row_agent(terminal_row)
    terminal_receipt_id = str(terminal_receipt.get("receipt_id") or terminal_row.get("receipt_id") or "")
    summary = (
        "Blocked open duplicate A2A row because the same task id already has "
        "a terminal, receipt-verified queue row."
    )
    return build_task_receipt(
        task_id=task_id,
        agent_uid=agent_uid,
        status="blocked",
        summary=summary,
        authority="verified_duplicate_terminal_row_supervisor_block",
        completion_via="a2a_block_verified_duplicate_open_rows",
        failure_reason="duplicate_open_row_already_terminal_verified",
        evidence={
            "duplicate_scope": "same_task_id_only",
            "duplicate_terminal_row_index": terminal_index,
            "original_body_excerpt": _body_excerpt(row),
            "original_created": str(row.get("created") or row.get("created_at") or ""),
            "original_from": str(row.get("from") or ""),
            "original_status": _row_status(row),
            "original_to": str(row.get("to") or ""),
            "supervisor_scope": "block_only_no_task_execution_claimed",
            "terminal_agent_uid": terminal_agent,
            "terminal_authority": str(terminal_receipt.get("authority") or ""),
            "terminal_closed_at": str(terminal_row.get("closed_at") or terminal_receipt.get("closed_at") or ""),
            "terminal_completion_via": str(terminal_receipt.get("completion_via") or terminal_row.get("closed_via") or ""),
            "terminal_receipt_id": terminal_receipt_id,
            "terminal_receipt_status": str(terminal_receipt.get("status") or terminal_row.get("status") or ""),
            "terminal_receipt_summary": str(
                terminal_receipt.get("summary")
                or terminal_receipt.get("receipt_summary")
                or terminal_row.get("closure_note")
                or ""
            )[:420],
            "terminal_verified_artifacts": _receipt_artifacts(terminal_receipt),
        },
        evaluation={
            "overall_verdict": "duplicate_open_row_blocked_by_same_id_verified_terminal_row",
            "criteria_results": [
                {"criterion": "open_row_is_unclaimed", "passed": True},
                {"criterion": "same_task_id_terminal_duplicate_exists", "passed": True},
                {"criterion": "terminal_duplicate_receipt_verified", "passed": True},
                {"criterion": "terminal_duplicate_has_substantive_evidence", "passed": True},
                {"criterion": "no_cross_task_inference", "passed": True},
            ],
            "gate_results": [],
        },
        timestamp=timestamp,
    )


def _candidate_for_row(
    rows: list[dict[str, Any]],
    row: dict[str, Any],
    *,
    row_index: int,
    agent_uid: str,
    timestamp: str,
) -> tuple[VerifiedDuplicateAction | None, VerifiedDuplicateSkip | None, dict[str, Any] | None]:
    task_id = str(row.get("id") or "")
    status = _row_status(row)
    if not task_id:
        return None, VerifiedDuplicateSkip(row_index, "", status, "missing_task_id", ""), None
    lifecycle = task_lifecycle_state(row)
    if lifecycle.get("closed"):
        return None, None, None
    if status == "claimed":
        duplicate = _terminal_duplicate_for(rows, row_index=row_index, task_id=task_id)
        if duplicate is not None:
            return None, VerifiedDuplicateSkip(row_index, task_id, status, "claimed_duplicate_not_touched", ""), None
        return None, None, None
    if status not in OPEN_STATUSES:
        return None, VerifiedDuplicateSkip(row_index, task_id, status, "unsupported_non_terminal_status", status), None

    duplicate = _terminal_duplicate_for(rows, row_index=row_index, task_id=task_id)
    if duplicate is None:
        same_id_count = sum(1 for candidate in rows if str(candidate.get("id") or "") == task_id)
        if same_id_count > 1:
            return None, VerifiedDuplicateSkip(row_index, task_id, status, "no_verified_terminal_duplicate", ""), None
        return None, None, None

    terminal_index, terminal_row = duplicate
    terminal_receipt = terminal_row.get("receipt") if isinstance(terminal_row.get("receipt"), dict) else {}
    terminal_receipt = terminal_receipt if isinstance(terminal_receipt, dict) else {}
    receipt = _build_receipt(
        row,
        terminal_index=terminal_index,
        terminal_row=terminal_row,
        agent_uid=agent_uid,
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
            VerifiedDuplicateSkip(row_index, task_id, status, "block_receipt_invalid", "; ".join(validation["errors"])),
            None,
        )
    return (
        VerifiedDuplicateAction(
            row_index=row_index,
            task_id=task_id,
            original_status=status,
            duplicate_terminal_row_index=terminal_index,
            terminal_status=_row_status(terminal_row),
            terminal_agent_uid=_row_agent(terminal_row),
            terminal_receipt_id=str(terminal_receipt.get("receipt_id") or terminal_row.get("receipt_id") or ""),
            terminal_authority=str(terminal_receipt.get("authority") or ""),
            a2a_receipt_id=str(receipt.get("receipt_id") or ""),
            validation=validation,
            reason="same_task_id_terminal_verified_duplicate",
        ),
        None,
        receipt,
    )


def find_actions(
    rows: list[dict[str, Any]],
    *,
    agent_uid: str,
    timestamp: str,
) -> tuple[list[VerifiedDuplicateAction], list[VerifiedDuplicateSkip], dict[int, dict[str, Any]]]:
    actions: list[VerifiedDuplicateAction] = []
    skips: list[VerifiedDuplicateSkip] = []
    receipts_by_index: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        action, skip, receipt = _candidate_for_row(
            rows,
            row,
            row_index=index,
            agent_uid=agent_uid,
            timestamp=timestamp,
        )
        if action is not None and receipt is not None:
            actions.append(action)
            receipts_by_index[index] = receipt
        if skip is not None:
            skips.append(skip)
    return actions, skips, receipts_by_index


def _apply_actions(
    *,
    rows: list[dict[str, Any]],
    actions: list[VerifiedDuplicateAction],
    receipts_by_index: dict[int, dict[str, Any]],
    agent_uid: str,
    timestamp: str,
) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    actions_by_index = {action.row_index: action for action in actions}
    for index, row in enumerate(rows):
        action = actions_by_index.get(index)
        receipt = receipts_by_index.get(index)
        if action is None or receipt is None:
            continue
        validation = validate_task_receipt(
            receipt,
            task_id=action.task_id,
            agent_uid=agent_uid,
            status="blocked",
            require_artifact_or_evidence=True,
        )
        row["status"] = "blocked"
        row["closed_at"] = timestamp
        row["closed_by"] = agent_uid
        row["closed_via"] = "a2a_block_verified_duplicate_open_rows"
        row["blocked_at"] = timestamp
        row["blocked_by"] = agent_uid
        row["failure_reason"] = receipt.get("failure_reason")
        row["receipt"] = receipt
        row["receipt_id"] = receipt.get("receipt_id")
        row["receipt_validation"] = validation
        row["a2a_duplicate_blocked_at"] = timestamp
        row["a2a_duplicate_blocked_via"] = "scripts/governance/a2a_block_verified_duplicate_open_rows.py"
        row["duplicate_terminal_row_index"] = action.duplicate_terminal_row_index
        row["duplicate_terminal_receipt_id"] = action.terminal_receipt_id
        row["required_receipt_schema"] = "dharma_a2a_task_receipt.v1"
        applied.append(
            {
                "task_id": action.task_id,
                "row_index": action.row_index,
                "status": "blocked",
                "receipt_id": receipt.get("receipt_id"),
                "duplicate_terminal_row_index": action.duplicate_terminal_row_index,
                "duplicate_terminal_receipt_id": action.terminal_receipt_id,
                "validation": validation,
            }
        )
    return applied


def build_report(
    state_root: Path | str | None = None,
    *,
    apply: bool = False,
    agent_uid: str = DEFAULT_AGENT_UID,
    timestamp: str | None = None,
    output: Path | None = None,
) -> dict[str, Any]:
    ts = timestamp or _utc_now()
    state = Path(state_root) if state_root is not None else None
    path = queue_path(state)
    rows = _read_rows(path)
    actions, skips, receipts_by_index = find_actions(
        rows,
        agent_uid=agent_uid,
        timestamp=ts,
    )

    backup_path = ""
    applied: list[dict[str, Any]] = []
    if apply and actions:
        backup = path.with_name(f"{path.name}.a2a-verified-duplicate-block-{_safe_timestamp(ts)}.bak")
        shutil.copy2(path, backup)
        backup_path = str(backup)
        applied = _apply_actions(
            rows=rows,
            actions=actions,
            receipts_by_index=receipts_by_index,
            agent_uid=agent_uid,
            timestamp=ts,
        )
        _write_rows(path, rows)

    readiness = evaluate_a2a_readiness(state)
    report = {
        "schema_version": 1,
        "mode": "apply" if apply else "dry_run",
        "generated_at": ts,
        "queue_path": str(path),
        "agent_uid": agent_uid,
        "backup_path": backup_path,
        "candidate_count": len(actions),
        "applied_count": len(applied),
        "skip_count": len(skips),
        "actions": [asdict(action) for action in actions],
        "skips": [asdict(skip) for skip in skips],
        "applied": applied,
        "post_readiness": {
            "ready": readiness.ready,
            "gate_status": readiness.gate_status,
            "open_tasks": readiness.open_tasks,
            "unknown_status_tasks": readiness.unknown_status_tasks,
            "unverified_closed_tasks": readiness.unverified_closed_tasks,
            "reasons": readiness.reasons,
            "blocker_task_ids": readiness.blocker_task_ids,
        },
    }
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Mutate the queue after writing a backup.")
    parser.add_argument("--state-root", type=Path, default=None, help="Override DHARMA state root.")
    parser.add_argument("--agent-uid", default=DEFAULT_AGENT_UID, help="Supervisor identity to stamp on receipts.")
    parser.add_argument("--timestamp", default=None, help="Receipt/report timestamp.")
    parser.add_argument("--output", type=Path, default=None, help="Optional report JSON path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = build_report(
        state_root=args.state_root,
        apply=args.apply,
        agent_uid=args.agent_uid,
        timestamp=args.timestamp,
        output=args.output,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
