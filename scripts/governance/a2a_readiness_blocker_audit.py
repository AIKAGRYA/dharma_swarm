#!/usr/bin/env python3
"""Audit A2A strict-readiness blockers without mutating the live queue."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.a2a_task_lifecycle import (
    CLOSED_STATUSES,
    OPEN_STATUSES,
    queue_path,
    read_queue,
    task_lifecycle_state,
)


DEFAULT_STALE_HOURS = 24.0


@dataclass(frozen=True)
class ReceiptPointer:
    path: str
    exists: bool
    resolved_path: str | None
    validation: dict[str, Any]


@dataclass(frozen=True)
class BlockerAuditItem:
    task_id: str
    status: str
    lifecycle_state: str
    closed: bool
    verified: bool
    classification: str
    reason: str
    claimed_by: str
    claimed_at: str
    age_hours: float | None
    receipt_id: str
    receipt_path: str
    required_receipt_schema: str
    receipt_validation_schema: str
    receipt_pointer: ReceiptPointer | None
    flags: list[str]
    recommended_action: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _row_flags(row: dict[str, Any]) -> list[str]:
    body = str(row.get("body") or "").lower()
    flags: list[str] = []
    if "operator-gated" in body or "operator gated" in body:
        flags.append("operator_gated")
    if "approval" in body or "sign-off" in body or "signoff" in body:
        flags.append("approval_required")
    if "no naked ack" in body or "acknowledgement alone is failure" in body:
        flags.append("no_ack_only")
    if row.get("semantic_receipt_required") or "semantic_receipt" in str(row.get("receipt_id") or ""):
        flags.append("semantic_receipt_required")
    return sorted(set(flags))


def _resolve_pointer(path_value: str, artifact_roots: list[Path]) -> tuple[bool, Path | None]:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path.exists(), path if path.exists() else None
    for root in artifact_roots:
        candidate = root / path
        if candidate.exists():
            return True, candidate
    return False, None


def _validate_sab_semantic_receipt(
    payload: Any,
    *,
    task_id: str,
    receipt_id: str,
) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["receipt payload must be an object"]}
    if payload.get("schema") != "sab.semantic_receipt.v1":
        errors.append("schema must be sab.semantic_receipt.v1")
    if str(payload.get("task_id") or "") != task_id:
        errors.append("task_id does not match queue row")
    payload_receipt_id = str(payload.get("receipt_id") or "")
    if receipt_id and payload_receipt_id and payload_receipt_id != receipt_id:
        errors.append("receipt_id does not match queue row")
    if not str(payload.get("agent") or payload.get("agent_id") or ""):
        errors.append("agent or agent_id must be present")
    required = {
        "sab_instance_id",
        "latest_post_id_seen",
        "latest_witness_hash_seen",
        "semantic_action",
        "claim",
        "action_taken",
        "next_request",
    }
    missing = sorted(key for key in required if key not in payload)
    if missing:
        errors.append(f"missing SAB semantic receipt field(s): {', '.join(missing)}")
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be a non-empty list")
    return {"valid": not errors, "errors": errors}


def _inspect_receipt_pointer(row: dict[str, Any], artifact_roots: list[Path]) -> ReceiptPointer | None:
    pointer = str(row.get("receipt_path") or "")
    if not pointer:
        return None
    exists, resolved = _resolve_pointer(pointer, artifact_roots)
    validation: dict[str, Any]
    if not exists or resolved is None:
        validation = {"valid": False, "errors": ["receipt_path does not exist under artifact roots"]}
    elif str(row.get("required_receipt_schema") or row.get("receipt_validation", {}).get("schema") or "") == (
        "sab.semantic_receipt.v1"
    ):
        try:
            payload = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            validation = {"valid": False, "errors": [f"could not read receipt JSON: {exc}"]}
        else:
            validation = _validate_sab_semantic_receipt(
                payload,
                task_id=str(row.get("id") or ""),
                receipt_id=str(row.get("receipt_id") or ""),
            )
    else:
        validation = {"valid": False, "errors": ["receipt_path schema is not a supported audit adapter"]}
    return ReceiptPointer(
        path=pointer,
        exists=exists,
        resolved_path=str(resolved) if resolved else None,
        validation=validation,
    )


def _classify(
    row: dict[str, Any],
    *,
    lifecycle: dict[str, Any],
    receipt_pointer: ReceiptPointer | None,
    stale_after_hours: float,
    now: datetime,
) -> tuple[str, str, str]:
    task_id = str(row.get("id") or "")
    status = str(row.get("status") or "pending").lower()
    closed = bool(lifecycle.get("closed"))
    age = _age_hours(row, now)

    if closed:
        if row.get("receipt") is None:
            if receipt_pointer is None:
                return (
                    "closed_missing_a2a_receipt_no_pointer",
                    "Terminal row has no embedded A2A task receipt and no external receipt_path.",
                    "Recover or create a task-specific dharma_a2a_task_receipt.v1 receipt with evidence.",
                )
            if not receipt_pointer.exists:
                return (
                    "closed_semantic_receipt_pointer_missing_file",
                    "Terminal row has no embedded A2A task receipt and its external receipt_path is not present.",
                    "Recover the referenced artifact before any semantic-to-A2A reconciliation.",
                )
            if receipt_pointer.validation.get("valid"):
                return (
                    "closed_semantic_receipt_present_non_a2a",
                    "Referenced semantic receipt validates, but it is not an embedded A2A task receipt.",
                    "Use a governed adapter only if the semantic artifact is accepted as evidence for an A2A receipt.",
                )
            return (
                "closed_semantic_receipt_invalid_non_a2a",
                "Referenced receipt_path exists but fails semantic receipt validation.",
                "Repair or reject the referenced artifact before A2A closure.",
            )
        return (
            "closed_invalid_a2a_receipt",
            "Terminal row has an embedded receipt, but strict A2A receipt validation rejects it.",
            "Repair the embedded receipt content hash/schema/identity fields or leave the row unverified.",
        )

    if status == "claimed":
        stale = age is None or age >= stale_after_hours
        if stale:
            return (
                "open_stale_claimed_without_terminal_receipt",
                "Claimed row is older than the stale threshold and has no terminal A2A receipt.",
                "Close with a task-specific completed/blocked/failed receipt, or supervisor-block with evidence.",
            )
        return (
            "open_recent_claimed_without_terminal_receipt",
            "Claimed row has not crossed the stale threshold and has no terminal A2A receipt.",
            "Let the owning agent close it or wait for the stale threshold.",
        )

    if status in OPEN_STATUSES or status not in CLOSED_STATUSES:
        stale = age is None or age >= stale_after_hours
        if stale:
            return (
                "open_stale_unclaimed_without_terminal_receipt",
                "Open row is unclaimed or non-terminal beyond the stale threshold.",
                "Claim and execute, or close blocked with evidence if the task is obsolete or externally gated.",
            )
        return (
            "open_recent_unclaimed_without_terminal_receipt",
            "Open row is unclaimed and has not crossed the stale threshold.",
            "Claim and execute, or wait for ownership.",
        )

    return (
        "unknown_lifecycle_blocker",
        f"Task {task_id} is not verified and did not match a known audit class.",
        "Inspect the queue row manually and add an audit class if this recurs.",
    )


def build_report(
    state_root: Path | str | None = None,
    *,
    artifact_roots: list[Path] | None = None,
    stale_after_hours: float = DEFAULT_STALE_HOURS,
    now: datetime | None = None,
) -> dict[str, Any]:
    resolved_roots = [Path.cwd()] if artifact_roots is None else [Path(root) for root in artifact_roots]
    timestamp = now or _utc_now()
    rows = read_queue(state_root)
    items: list[BlockerAuditItem] = []

    for row in rows:
        lifecycle = task_lifecycle_state(row)
        if lifecycle.get("closed") and lifecycle.get("verified"):
            continue
        pointer = _inspect_receipt_pointer(row, resolved_roots)
        classification, reason, recommended_action = _classify(
            row,
            lifecycle=lifecycle,
            receipt_pointer=pointer,
            stale_after_hours=stale_after_hours,
            now=timestamp,
        )
        receipt_validation = row.get("receipt_validation") if isinstance(row.get("receipt_validation"), dict) else {}
        items.append(
            BlockerAuditItem(
                task_id=str(row.get("id") or ""),
                status=str(row.get("status") or "pending").lower(),
                lifecycle_state=str(lifecycle.get("state") or ""),
                closed=bool(lifecycle.get("closed")),
                verified=bool(lifecycle.get("verified")),
                classification=classification,
                reason=reason,
                claimed_by=str(row.get("claimed_by") or ""),
                claimed_at=str(row.get("claimed_at") or ""),
                age_hours=_age_hours(row, timestamp),
                receipt_id=str(row.get("receipt_id") or ""),
                receipt_path=str(row.get("receipt_path") or ""),
                required_receipt_schema=str(row.get("required_receipt_schema") or ""),
                receipt_validation_schema=str(receipt_validation.get("schema") or ""),
                receipt_pointer=pointer,
                flags=_row_flags(row),
                recommended_action=recommended_action,
            )
        )

    classification_counts = Counter(item.classification for item in items)
    lifecycle_counts = Counter(item.lifecycle_state for item in items)
    return {
        "schema_version": 1,
        "generated_at": timestamp.isoformat().replace("+00:00", "Z"),
        "queue_path": str(queue_path(state_root)),
        "artifact_roots": [str(root) for root in resolved_roots],
        "stale_after_hours": stale_after_hours,
        "total_tasks": len(rows),
        "blocker_count": len(items),
        "classification_counts": dict(sorted(classification_counts.items())),
        "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
        "blockers": [asdict(item) for item in items],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", default=None)
    parser.add_argument(
        "--artifact-root",
        action="append",
        default=None,
        help="Root used to resolve relative receipt_path values. Repeatable; defaults to cwd.",
    )
    parser.add_argument("--stale-after-hours", type=float, default=DEFAULT_STALE_HOURS)
    parser.add_argument("--output", default=None, help="Optional JSON report output path.")
    args = parser.parse_args(argv)

    report = build_report(
        args.state_root,
        artifact_roots=[Path(root) for root in args.artifact_root] if args.artifact_root else None,
        stale_after_hours=args.stale_after_hours,
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
