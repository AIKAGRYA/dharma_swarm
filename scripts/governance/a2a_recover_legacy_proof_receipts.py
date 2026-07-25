#!/usr/bin/env python3
"""Recover A2A receipts for terminal rows with legacy proof artifacts.

This adapter is intentionally narrower than a generic queue repair.  It only
embeds ``dharma_a2a_task_receipt.v1`` receipts for rows that are already
terminal, fail strict A2A verification only because no receipt is embedded,
and carry an existing legacy proof artifact pointer.  It never closes open
rows or infers task completion across duplicate task ids.
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
    VALID_CLOSE_STATUSES,
    build_task_receipt,
    queue_path,
    task_lifecycle_state,
    validate_task_receipt,
)
from scripts.governance.check_a2a_readiness import evaluate_a2a_readiness  # noqa: E402

A2A_RECEIPT_SCHEMA = "dharma_a2a_task_receipt.v1"


@dataclass(frozen=True)
class LegacyProofAction:
    row_index: int
    task_id: str
    terminal_status: str
    agent_uid: str
    proof_pointer: str
    resolved_proof_path: str
    a2a_receipt_id: str
    validation: dict[str, Any]
    reason: str


@dataclass(frozen=True)
class LegacyProofSkip:
    row_index: int
    task_id: str
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


def _resolve_pointer(path_value: str, artifact_roots: list[Path]) -> Path | None:
    candidate = Path(path_value).expanduser()
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    for root in artifact_roots:
        resolved = root / candidate
        if resolved.exists():
            return resolved
    return None


def _row_agent(row: dict[str, Any]) -> str:
    return str(
        row.get("closed_by")
        or row.get("completed_by")
        or row.get("blocked_by")
        or row.get("failed_by")
        or row.get("claimed_by")
        or ""
    )


def _proof_pointer(row: dict[str, Any]) -> str:
    return str(
        row.get("proof_pointer")
        or row.get("proof_path")
        or row.get("artifact_path")
        or row.get("closure_artifact")
        or ""
    )


def _build_receipt(
    row: dict[str, Any],
    *,
    agent_uid: str,
    status: str,
    resolved_proof: Path,
    timestamp: str,
) -> dict[str, Any]:
    task_id = str(row.get("id") or "")
    closure_note = str(row.get("closure_note") or row.get("summary") or "")
    closed_via = str(row.get("closed_via") or row.get("completion_via") or "legacy_a2a_queue")
    summary = "Recovered A2A receipt from existing legacy proof artifact."
    if closure_note:
        summary = f"{summary} {closure_note[:260]}"
    return build_task_receipt(
        task_id=task_id,
        agent_uid=agent_uid,
        status=status,  # type: ignore[arg-type]
        summary=summary,
        artifacts=[str(resolved_proof)],
        authority="legacy_proof_pointer_recovery",
        completion_via="a2a_recover_legacy_proof_receipts",
        evidence={
            "adapter_reason": "terminal row had existing legacy proof artifact but no embedded A2A receipt",
            "legacy_closed_via": closed_via,
            "legacy_closure_note": closure_note,
            "legacy_proof_pointer": str(row.get("proof_pointer") or ""),
            "legacy_proof_path": str(resolved_proof),
            "original_row_status_was": str(row.get("original_row_status_was") or ""),
            "recovery_scope": "terminal_row_only_no_duplicate_task_inference",
        },
        evaluation={
            "overall_verdict": "legacy_proof_artifact_exists_and_receipt_recovered",
            "criteria_results": [
                {"criterion": "terminal_queue_row_only", "passed": True},
                {"criterion": "legacy_proof_pointer_present", "passed": True},
                {"criterion": "legacy_proof_artifact_exists", "passed": True},
                {"criterion": "closer_identity_present", "passed": bool(agent_uid)},
            ],
            "gate_results": [],
        },
        timestamp=timestamp,
    )


def _candidate_for_row(
    row: dict[str, Any],
    *,
    row_index: int,
    artifact_roots: list[Path],
    timestamp: str,
) -> tuple[LegacyProofAction | None, LegacyProofSkip | None, dict[str, Any] | None]:
    task_id = str(row.get("id") or "")
    lifecycle = task_lifecycle_state(row)
    if not lifecycle.get("closed") or lifecycle.get("verified"):
        return None, None, None

    status = str(row.get("status") or "").lower()
    if status not in VALID_CLOSE_STATUSES:
        return None, LegacyProofSkip(row_index, task_id, "unsupported_terminal_status", status), None
    if isinstance(row.get("receipt"), dict):
        return None, LegacyProofSkip(row_index, task_id, "embedded_a2a_receipt_invalid", "manual repair required"), None
    pointer = _proof_pointer(row)
    if not pointer:
        return None, LegacyProofSkip(row_index, task_id, "missing_proof_pointer", ""), None
    resolved = _resolve_pointer(pointer, artifact_roots)
    if resolved is None:
        return None, LegacyProofSkip(row_index, task_id, "proof_pointer_missing", pointer), None

    agent_uid = _row_agent(row)
    if not agent_uid:
        return None, LegacyProofSkip(row_index, task_id, "missing_closer_identity", ""), None
    if not str(row.get("closure_note") or row.get("closed_via") or row.get("completion_via") or ""):
        return None, LegacyProofSkip(row_index, task_id, "missing_legacy_closure_context", pointer), None

    receipt = _build_receipt(
        row,
        agent_uid=agent_uid,
        status=status,
        resolved_proof=resolved,
        timestamp=timestamp,
    )
    validation = validate_task_receipt(
        receipt,
        task_id=task_id,
        agent_uid=agent_uid,
        status=status,  # type: ignore[arg-type]
        require_artifact_or_evidence=True,
    )
    if not validation["valid"]:
        return (
            None,
            LegacyProofSkip(row_index, task_id, "recovered_a2a_receipt_invalid", "; ".join(validation["errors"])),
            None,
        )

    return (
        LegacyProofAction(
            row_index=row_index,
            task_id=task_id,
            terminal_status=status,
            agent_uid=agent_uid,
            proof_pointer=pointer,
            resolved_proof_path=str(resolved),
            a2a_receipt_id=str(receipt.get("receipt_id") or ""),
            validation=validation,
            reason="terminal_legacy_proof_pointer_without_embedded_a2a_receipt",
        ),
        None,
        receipt,
    )


def find_actions(
    rows: list[dict[str, Any]],
    *,
    artifact_roots: list[Path],
    timestamp: str,
) -> tuple[list[LegacyProofAction], list[LegacyProofSkip], dict[int, dict[str, Any]]]:
    actions: list[LegacyProofAction] = []
    skips: list[LegacyProofSkip] = []
    receipts_by_index: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        action, skip, receipt = _candidate_for_row(
            row,
            row_index=index,
            artifact_roots=artifact_roots,
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
    actions: list[LegacyProofAction],
    receipts_by_index: dict[int, dict[str, Any]],
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
            agent_uid=action.agent_uid,
            status=action.terminal_status,  # type: ignore[arg-type]
            require_artifact_or_evidence=True,
        )
        row["a2a_recovered_at"] = timestamp
        row["a2a_recovered_via"] = "scripts/governance/a2a_recover_legacy_proof_receipts.py"
        row["a2a_recovered_from"] = "legacy_proof_pointer"
        row["legacy_proof_pointer"] = action.proof_pointer
        row["legacy_proof_path"] = action.resolved_proof_path
        row["legacy_proof_validation"] = {"valid": True, "errors": []}
        row["receipt"] = receipt
        row["receipt_id"] = receipt.get("receipt_id")
        row["receipt_validation"] = validation
        row["required_receipt_schema"] = A2A_RECEIPT_SCHEMA
        row["closed_by"] = row.get("closed_by") or action.agent_uid
        if action.terminal_status == "completed":
            row["completed_by"] = row.get("completed_by") or action.agent_uid
        elif action.terminal_status == "blocked":
            row["blocked_by"] = row.get("blocked_by") or action.agent_uid
        elif action.terminal_status == "failed":
            row["failed_by"] = row.get("failed_by") or action.agent_uid
        applied.append(
            {
                "task_id": action.task_id,
                "status": "recovered",
                "proof_pointer": action.proof_pointer,
                "a2a_receipt_id": action.a2a_receipt_id,
                "validation": validation,
            }
        )
    return applied


def build_report(
    *,
    state_root: Path | str | None = None,
    artifact_roots: list[Path] | None = None,
    apply: bool = False,
    timestamp: str | None = None,
) -> dict[str, Any]:
    ts = timestamp or _utc_now()
    roots = artifact_roots or [Path.cwd()]
    path = queue_path(state_root)
    rows = _read_rows(path)
    actions, skips, receipts_by_index = find_actions(rows, artifact_roots=roots, timestamp=ts)
    backup_path = ""
    applied: list[dict[str, Any]] = []
    if apply and actions:
        backup_path = str(path.with_name(f"{path.name}.a2a-legacy-proof-recovery-{_safe_timestamp(ts)}.bak"))
        shutil.copy2(path, backup_path)
        applied = _apply_actions(
            rows=rows,
            actions=actions,
            receipts_by_index=receipts_by_index,
            timestamp=ts,
        )
        _write_rows(path, rows)
    readiness = evaluate_a2a_readiness(state_root)
    return {
        "schema_version": 1,
        "mode": "apply" if apply else "dry_run",
        "generated_at": ts,
        "queue_path": str(path),
        "artifact_roots": [str(root) for root in roots],
        "backup_path": backup_path,
        "candidate_count": len(actions),
        "applied_count": len(applied),
        "skip_count": len(skips),
        "candidates": [asdict(action) for action in actions],
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--artifact-root", action="append", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--timestamp", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    artifact_roots = (
        [Path(root).expanduser() for root in args.artifact_root]
        if args.artifact_root
        else None
    )
    report = build_report(
        state_root=args.state_root,
        artifact_roots=artifact_roots,
        apply=args.apply,
        timestamp=args.timestamp,
    )
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
