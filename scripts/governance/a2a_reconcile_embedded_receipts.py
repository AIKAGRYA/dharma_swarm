#!/usr/bin/env python3
"""Reconcile A2A queue rows that already contain valid terminal receipts."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.a2a_task_lifecycle import (
    A2ATaskLifecycleError,
    VALID_CLOSE_STATUSES,
    close_task,
    queue_path,
    read_queue,
    task_lifecycle_state,
    validate_task_receipt,
)


@dataclass(frozen=True)
class EmbeddedReceiptAction:
    task_id: str
    original_status: str
    terminal_status: str
    agent_uid: str
    receipt_id: str
    needs_supervisor_block: bool
    reason: str


def find_embedded_terminal_receipt_actions(
    state_root: Path | str | None = None,
    *,
    require_artifact_or_evidence: bool = False,
) -> list[EmbeddedReceiptAction]:
    """Return safe normalization actions for rows with valid embedded receipts."""

    actions: list[EmbeddedReceiptAction] = []
    for row in read_queue(state_root):
        task_id = str(row.get("id") or "")
        if not task_id:
            continue
        lifecycle = task_lifecycle_state(
            row,
            require_artifact_or_evidence=require_artifact_or_evidence,
        )
        if lifecycle.get("closed") and lifecycle.get("verified"):
            continue
        receipt = row.get("receipt")
        if not isinstance(receipt, dict):
            continue
        terminal_status = str(receipt.get("status") or "").lower()
        if terminal_status not in VALID_CLOSE_STATUSES:
            continue
        agent_uid = str(receipt.get("agent_uid") or "")
        if not agent_uid:
            continue
        validation = validate_task_receipt(
            receipt,
            task_id=task_id,
            agent_uid=agent_uid,
            status=terminal_status,  # type: ignore[arg-type]
            require_artifact_or_evidence=require_artifact_or_evidence,
        )
        if not validation["valid"]:
            continue
        original_status = str(row.get("status") or "pending").lower()
        claimed_by = str(row.get("claimed_by") or "")
        actions.append(
            EmbeddedReceiptAction(
                task_id=task_id,
                original_status=original_status,
                terminal_status=terminal_status,
                agent_uid=agent_uid,
                receipt_id=str(receipt.get("receipt_id") or ""),
                needs_supervisor_block=bool(
                    terminal_status == "blocked"
                    and claimed_by
                    and claimed_by != agent_uid
                ),
                reason="valid_embedded_terminal_receipt_on_nonterminal_or_unverified_row",
            )
        )
    return actions


def apply_embedded_terminal_receipt_actions(
    actions: list[EmbeddedReceiptAction],
    state_root: Path | str | None = None,
    *,
    require_artifact_or_evidence: bool = False,
) -> list[dict[str, Any]]:
    """Apply safe receipt-backed queue normalizations."""

    applied: list[dict[str, Any]] = []
    rows_by_id = {str(row.get("id") or ""): row for row in read_queue(state_root)}
    for action in actions:
        row = rows_by_id.get(action.task_id)
        receipt = row.get("receipt") if isinstance(row, dict) else None
        if not isinstance(receipt, dict):
            applied.append(
                {
                    "task_id": action.task_id,
                    "status": "error",
                    "error": "embedded receipt disappeared before apply",
                }
            )
            continue
        try:
            closed = close_task(
                action.task_id,
                agent_uid=action.agent_uid,
                status=action.terminal_status,  # type: ignore[arg-type]
                receipt=receipt,
                state_root=state_root,
                require_artifact_or_evidence=require_artifact_or_evidence,
                allow_supervisor_block=action.needs_supervisor_block,
                closed_via="a2a_reconcile_embedded_receipts",
            )
        except A2ATaskLifecycleError as exc:
            applied.append(
                {
                    "task_id": action.task_id,
                    "status": "error",
                    "error": str(exc),
                }
            )
            continue
        applied.append(
            {
                "task_id": action.task_id,
                "status": "normalized",
                "original_status": action.original_status,
                "terminal_status": action.terminal_status,
                "receipt_id": action.receipt_id,
                "queue_status": closed.get("status"),
            }
        )
    return applied


def build_report(
    state_root: Path | str | None = None,
    *,
    apply: bool = False,
    require_artifact_or_evidence: bool = False,
) -> dict[str, Any]:
    actions = find_embedded_terminal_receipt_actions(
        state_root,
        require_artifact_or_evidence=require_artifact_or_evidence,
    )
    applied = (
        apply_embedded_terminal_receipt_actions(
            actions,
            state_root,
            require_artifact_or_evidence=require_artifact_or_evidence,
        )
        if apply
        else []
    )
    return {
        "schema_version": 1,
        "queue_path": str(queue_path(state_root)),
        "mode": "apply" if apply else "dry_run",
        "candidate_count": len(actions),
        "candidates": [asdict(action) for action in actions],
        "applied": applied,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--require-artifact-or-evidence",
        action="store_true",
        help="Apply the stricter receipt validation mode used by the readiness gate option.",
    )
    parser.add_argument("--output", default=None, help="Optional JSON report output path.")
    args = parser.parse_args(argv)

    report = build_report(
        args.state_root,
        apply=args.apply,
        require_artifact_or_evidence=args.require_artifact_or_evidence,
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
