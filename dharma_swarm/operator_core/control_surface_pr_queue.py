"""PR queue receipt adapter for the Control Surface Projector."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.control_surface_models import ControlSurfaceRow

DEFAULT_PR_REVIEW_ROOT = Path("~/.dharma/pr_review")
DEFAULT_QUEUE_TTL_S = 900

_STATUS_TO_STATE: dict[str, str] = {
    "DRAFT": "draft",
    "BLOCKED_CONFLICT": "blocked_conflict",
    "BLOCKED_CHECKS": "blocked_checks",
    "BLOCKED_REVIEW": "blocked_review",
    "WAITING_CHECKS": "waiting_checks",
    "NEEDS_REFRESH": "needs_refresh",
    "NEEDS_AGENT_REVIEW": "needs_agent_review",
    "GITHUB_GREEN_NEEDS_PACKET": "merge_ready_needs_packet",
}

_STATE_TO_NEXT_ACTION: dict[str, str] = {
    "draft": "wait for author to mark PR ready for review",
    "blocked_conflict": "repair merge conflict before packeting",
    "blocked_checks": "repair failing checks before packeting",
    "blocked_review": "resolve requested changes before packeting",
    "waiting_checks": "wait for checks or rerun transient failures",
    "needs_refresh": "refresh GitHub mergeability with make pr-queue",
    "needs_agent_review": "run packet and reviewer receipts",
    "merge_ready_needs_packet": "run make pr-packet and merge gate before any merge decision",
    "unknown": "refresh PR queue receipt with make pr-queue",
}

_BLOCKED_STATES = {"blocked_conflict", "blocked_checks", "blocked_review"}


def _expand(path: str | Path) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def _default_queue_path() -> Path:
    root = _expand(os.environ.get("DHARMA_PR_REVIEW_ROOT", str(DEFAULT_PR_REVIEW_ROOT)))
    return root / "queue" / "latest.json"


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _freshness_state(generated_at: str, ttl_s: int = DEFAULT_QUEUE_TTL_S) -> tuple[str, float | None]:
    observed = _parse_utc(generated_at)
    if observed is None:
        return "unknown", None
    age_s = (datetime.now(timezone.utc) - observed).total_seconds()
    return ("stale" if age_s > ttl_s else "fresh"), age_s


def _queue_missing_row(queue_path: Path) -> ControlSurfaceRow:
    row = ControlSurfaceRow(
        id="pr.queue",
        kind="pr_queue",
        label="PR review queue receipt",
        authority_role="projection",
        declared_state="receipt-backed-pr-queue",
        desired_state="fresh",
        observed_state="missing",
        coherence_state="unknown",
        priority="p1",
        owner_module="scripts/runtime/pr_merge_control.py",
        truth_owner="pr_merge_control_queue_receipt",
        freshness="",
        gap_codes=[
            "pr_queue_missing",
            "freshness_state:unknown",
            "authority_tier:projection",
            "mutation_surface:none",
        ],
        next_action="run make pr-queue to refresh the local PR queue receipt",
        raw={"queue_path": str(queue_path), "freshness_ttl_s": DEFAULT_QUEUE_TTL_S},
    )
    row.add_source_ref("file", "scripts/runtime/pr_merge_control.py", exists=True)
    row.add_source_ref("file", "docs/ops/PR_REVIEW_CONTROL.md", exists=True)
    row.add_evidence(
        "file",
        str(queue_path),
        status="missing",
        provenance_chain=["pr_merge_control", "queue_receipt"],
    )
    return row


def _coherence_for_queue_state(queue_state: str, freshness_state: str) -> str:
    if freshness_state == "stale":
        return "drifted"
    if queue_state in _BLOCKED_STATES:
        return "drifted"
    if queue_state in {"merge_ready_needs_packet", "needs_agent_review", "waiting_checks", "needs_refresh"}:
        return "partial"
    if queue_state == "draft":
        return "partial"
    return "unknown"


def _priority_for_queue_state(queue_state: str) -> str:
    if queue_state in _BLOCKED_STATES:
        return "p0"
    if queue_state in {"merge_ready_needs_packet", "needs_agent_review", "needs_refresh"}:
        return "p1"
    return "p2"


def _row_for_pr_item(
    item: dict[str, Any],
    *,
    queue_path: Path,
    generated_at: str,
    freshness_state: str,
    age_s: float | None,
) -> ControlSurfaceRow:
    number = item.get("number")
    status = str(item.get("status") or "UNKNOWN")
    queue_state = _STATUS_TO_STATE.get(status, "unknown")
    head_sha = str(item.get("headRefOid") or "")
    reasons = [str(reason) for reason in item.get("reasons", [])]
    checks = item.get("checks") if isinstance(item.get("checks"), dict) else {}
    gap_codes = [
        f"pr_queue_status:{status}",
        f"pr_queue_state:{queue_state}",
        f"freshness_state:{freshness_state}",
        "authority_tier:receipt_backed",
        "mutation_surface:none",
    ]
    if not head_sha:
        gap_codes.append("head_sha_missing")
    if freshness_state == "stale":
        gap_codes.append("pr_queue_stale")
    if checks.get("failing"):
        gap_codes.append("checks_failing")
    if checks.get("pending"):
        gap_codes.append("checks_pending")

    row = ControlSurfaceRow(
        id=f"pr.#{number}" if number is not None else "pr.unknown",
        kind="pr_queue",
        label=f"PR #{number}: {item.get('title') or '(untitled)'}",
        authority_role="observed_authority",
        declared_state="receipt-backed-pr-queue",
        desired_state="operator-reviewed",
        observed_state=queue_state,
        coherence_state=_coherence_for_queue_state(queue_state, freshness_state),
        priority=_priority_for_queue_state(queue_state),
        owner_module="scripts/runtime/pr_merge_control.py",
        truth_owner="pr_merge_control_queue_receipt",
        freshness=generated_at,
        gap_codes=gap_codes,
        next_action=_STATE_TO_NEXT_ACTION.get(queue_state, _STATE_TO_NEXT_ACTION["unknown"]),
        raw={
            "queue_path": str(queue_path),
            "generated_at": generated_at,
            "freshness_state": freshness_state,
            "age_s": age_s,
            "pr_number": number,
            "head_sha": head_sha,
            "head_ref": item.get("headRefName") or "",
            "base_ref": item.get("baseRefName") or "",
            "queue_status": status,
            "review_decision": item.get("reviewDecision") or "NONE",
            "mergeable": item.get("mergeable") or "UNKNOWN",
            "check_summary": checks,
            "reasons": reasons,
            "url": item.get("url") or "",
            "risk": item.get("risk") or "unknown",
        },
    )
    row.add_source_ref("file", "scripts/runtime/pr_merge_control.py", exists=True)
    row.add_source_ref("file", "docs/ops/PR_REVIEW_CONTROL.md", exists=True)
    row.add_source_ref("config", str(queue_path), exists=queue_path.exists())
    row.add_evidence(
        "file",
        str(queue_path),
        status=freshness_state,
        provenance_chain=["pr_merge_control", "queue_receipt", str(number)],
    )
    if reasons:
        row.add_evidence(
            "file",
            "; ".join(reasons),
            status=status,
            provenance_chain=["pr_merge_control", "classify_pr", str(number)],
        )
    return row


def rows_from_pr_queue_payload(
    payload: dict[str, Any],
    *,
    queue_path: Path | None = None,
    ttl_s: int = DEFAULT_QUEUE_TTL_S,
) -> list[ControlSurfaceRow]:
    path = queue_path or _default_queue_path()
    generated_at = str(payload.get("generated_at") or "")
    freshness_state, age_s = _freshness_state(generated_at, ttl_s)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    rows = [
        _row_for_pr_item(
            item if isinstance(item, dict) else {},
            queue_path=path,
            generated_at=generated_at,
            freshness_state=freshness_state,
            age_s=age_s,
        )
        for item in items
    ]
    if rows:
        return rows

    row = ControlSurfaceRow(
        id="pr.queue",
        kind="pr_queue",
        label="PR review queue",
        authority_role="observed_authority",
        declared_state="receipt-backed-pr-queue",
        desired_state="fresh",
        observed_state="empty",
        coherence_state="bound" if freshness_state == "fresh" else "drifted",
        priority="p2",
        owner_module="scripts/runtime/pr_merge_control.py",
        truth_owner="pr_merge_control_queue_receipt",
        freshness=generated_at,
        gap_codes=[
            "pr_queue_empty",
            f"freshness_state:{freshness_state}",
            "authority_tier:receipt_backed",
            "mutation_surface:none",
        ],
        next_action="no open PRs in queue receipt" if freshness_state == "fresh" else "run make pr-queue",
        raw={"queue_path": str(path), "generated_at": generated_at, "age_s": age_s},
    )
    row.add_source_ref("file", "scripts/runtime/pr_merge_control.py", exists=True)
    row.add_source_ref("config", str(path), exists=path.exists())
    row.add_evidence("file", str(path), status=freshness_state, provenance_chain=["pr_merge_control", "queue_receipt"])
    return [row]


def pr_queue_rows(queue_path: Path | None = None) -> list[ControlSurfaceRow]:
    path = queue_path or _default_queue_path()
    if not path.exists():
        return [_queue_missing_row(path)]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        row = _queue_missing_row(path)
        row.observed_state = "unreadable"
        row.coherence_state = "drifted"
        row.gap_codes = [
            "pr_queue_unreadable",
            "freshness_state:unknown",
            "authority_tier:projection",
            "mutation_surface:none",
        ]
        row.next_action = "inspect the PR queue receipt and rerun make pr-queue"
        row.raw["error"] = str(exc)
        if row.evidence:
            row.evidence[0].status = "error"
        return [row]
    return rows_from_pr_queue_payload(payload, queue_path=path)
