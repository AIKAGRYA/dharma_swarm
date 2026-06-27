#!/usr/bin/env python3
"""Dry-run-first firebreak for unsafe live task backlogs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sqlite3
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORT))

from dharma_swarm.operator_core.live_ops_census_contract import (  # noqa: E402
    DEFAULT_STATE_ROOT,
)
from scripts.runtime.runtime_truth_closeout import (  # noqa: E402
    _burn_in_preflight_evidence,
    _burn_in_preflight_passed,
    _task_backlog_summary,
)


SCHEMA_VERSION = "runtime_task_backlog_firebreak.v1"
DEFAULT_RECEIPT_DIR = DEFAULT_STATE_ROOT / "ops" / "task_backlog_firebreak"
DEFAULT_LATEST_REPORT = DEFAULT_STATE_ROOT / "ops" / "task_backlog_firebreak_latest.json"
PENDING_STATUSES = {"pending", "assigned", "ready"}
RUNNING_STATUSES = {"running", "in_progress"}
TARGET_STATUS = "cancelled"


@dataclass(frozen=True)
class FirebreakCandidate:
    task_id: str
    title: str
    status: str
    priority: str
    created_by: str
    created_at: str
    updated_at: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reason": self.reason,
        }


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _parse_dt(value: Any) -> datetime:
    text = str(value or "")
    if not text:
        return datetime.min.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _age_hours(value: Any, now: datetime) -> float:
    age = now - _parse_dt(value)
    return max(0.0, age.total_seconds() / 3600.0)


def _load_metadata(value: Any) -> dict[str, Any]:
    try:
        payload = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {"_firebreak_metadata_parse_error": True, "_raw_metadata": str(value or "")}
    return payload if isinstance(payload, dict) else {}


def _task_db(state_root: Path) -> Path:
    return state_root / "db" / "tasks.db"


def _receipt_id(now: datetime, candidates: list[FirebreakCandidate]) -> str:
    digest = hashlib.sha256()
    digest.update(now.isoformat().encode("utf-8"))
    for candidate in candidates[:50]:
        digest.update(candidate.task_id.encode("utf-8"))
    return f"rtbf_{now.strftime('%Y%m%dT%H%M%SZ')}_{digest.hexdigest()[:12]}"


def _candidate_reason(
    row: sqlite3.Row,
    *,
    now: datetime,
    max_pending_age_hours: float,
    max_running_age_hours: float,
) -> str:
    status = str(row["status"] or "")
    priority = str(row["priority"] or "")
    title = str(row["title"] or "")
    created_by = str(row["created_by"] or "")
    metadata = _load_metadata(row["metadata"])
    source = str(metadata.get("source") or "")
    created_age = _age_hours(row["created_at"], now)
    updated_age = _age_hours(row["updated_at"], now)

    if (
        status in (PENDING_STATUSES | RUNNING_STATUSES)
        and (created_by == "frontier_refill" or source == "frontier_refill")
        and "Repair: High gate block rate" in title
    ):
        return "runaway_frontier_refill_high_gate_loop"
    if status in PENDING_STATUSES and priority in {"high", "urgent"}:
        if created_age >= max_pending_age_hours:
            return "stale_pending_high_or_urgent"
    if status in PENDING_STATUSES and priority in {"normal", "low"}:
        if created_age >= max_pending_age_hours:
            return "stale_pending_noncritical"
    if status in RUNNING_STATUSES and updated_age >= max_running_age_hours:
        return "stale_running_no_recent_progress"
    return ""


def load_candidates(
    state_root: Path,
    *,
    now: datetime,
    max_pending_age_hours: float,
    max_running_age_hours: float,
    limit: int,
) -> list[FirebreakCandidate]:
    db_path = _task_db(state_root)
    if not db_path.exists():
        return []
    query = """
        SELECT id, title, status, priority, created_by, created_at, updated_at, metadata
        FROM tasks
        WHERE status IN ('pending', 'assigned', 'ready', 'running', 'in_progress')
        ORDER BY CASE priority
            WHEN 'urgent' THEN 0 WHEN 'high' THEN 1
            WHEN 'normal' THEN 2 WHEN 'low' THEN 3 ELSE 4 END,
            created_at ASC
    """
    candidates: list[FirebreakCandidate] = []
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        for row in db.execute(query):
            reason = _candidate_reason(
                row,
                now=now,
                max_pending_age_hours=max_pending_age_hours,
                max_running_age_hours=max_running_age_hours,
            )
            if not reason:
                continue
            candidates.append(
                FirebreakCandidate(
                    task_id=str(row["id"] or ""),
                    title=str(row["title"] or ""),
                    status=str(row["status"] or ""),
                    priority=str(row["priority"] or ""),
                    created_by=str(row["created_by"] or ""),
                    created_at=str(row["created_at"] or ""),
                    updated_at=str(row["updated_at"] or ""),
                    reason=reason,
                )
            )
            if limit > 0 and len(candidates) >= limit:
                break
    return candidates


def _count_by(items: list[FirebreakCandidate], *attrs: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        key = "|".join(str(getattr(item, attr)) for attr in attrs)
        counts[key] += 1
    return dict(sorted(counts.items()))


def _candidate_ids_sha256(candidates: list[FirebreakCandidate]) -> str:
    digest = hashlib.sha256()
    for candidate in candidates:
        digest.update(candidate.task_id.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _recompute_preflight(counts: dict[str, dict[str, int]], db_path: str) -> dict[str, Any]:
    pending_total = sum(
        count
        for status, priorities in counts.items()
        if status in PENDING_STATUSES
        for count in priorities.values()
    )
    pending_high = sum(
        priorities.get("high", 0) + priorities.get("urgent", 0)
        for status, priorities in counts.items()
        if status in PENDING_STATUSES
    )
    running_total = sum(
        count
        for status, priorities in counts.items()
        if status in RUNNING_STATUSES
        for count in priorities.values()
    )
    return {
        "available": True,
        "db_path": db_path,
        "by_status_priority": counts,
        "pending_total": pending_total,
        "pending_high_or_urgent": pending_high,
        "running_total": running_total,
    }


def simulate_backlog(
    before: dict[str, Any],
    candidates: list[FirebreakCandidate],
) -> dict[str, Any]:
    if not before.get("available"):
        return before
    counts = copy.deepcopy(before.get("by_status_priority") or {})
    for candidate in candidates:
        status_counts = counts.get(candidate.status)
        if not isinstance(status_counts, dict):
            continue
        current = int(status_counts.get(candidate.priority) or 0)
        if current <= 0:
            continue
        status_counts[candidate.priority] = current - 1
    return _recompute_preflight(counts, str(before.get("db_path") or ""))


def _augment_metadata(
    raw_metadata: str,
    *,
    receipt_id: str,
    candidate: FirebreakCandidate,
    applied_at: str,
    reason: str,
) -> str:
    metadata = _load_metadata(raw_metadata)
    metadata["runtime_task_backlog_firebreak"] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "applied_at": applied_at,
        "reason": reason,
        "selection_reason": candidate.reason,
        "previous_status": candidate.status,
        "previous_priority": candidate.priority,
    }
    return json.dumps(metadata, ensure_ascii=True, sort_keys=True)


def apply_firebreak(
    state_root: Path,
    candidates: list[FirebreakCandidate],
    *,
    receipt_id: str,
    applied_at: str,
    reason: str,
) -> int:
    if not candidates:
        return 0
    db_path = _task_db(state_root)
    by_id = {candidate.task_id: candidate for candidate in candidates}
    updated = 0
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        for task_id, candidate in by_id.items():
            row = db.execute(
                "SELECT status, metadata FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None or str(row["status"] or "") != candidate.status:
                continue
            metadata = _augment_metadata(
                str(row["metadata"] or "{}"),
                receipt_id=receipt_id,
                candidate=candidate,
                applied_at=applied_at,
                reason=reason,
            )
            db.execute(
                """
                UPDATE tasks
                SET status = ?,
                    assigned_to = NULL,
                    result = ?,
                    metadata = ?,
                    updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    TARGET_STATUS,
                    f"runtime task backlog firebreak: {candidate.reason}",
                    metadata,
                    applied_at,
                    task_id,
                    candidate.status,
                ),
            )
            updated += db.total_changes - updated
        db.commit()
    return updated


def write_receipt(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{time.monotonic_ns()}.tmp")
    tmp_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def build_firebreak_report(
    *,
    state_root: Path,
    apply: bool,
    allow_unpaused_apply: bool,
    max_pending_age_hours: float,
    max_running_age_hours: float,
    max_pending_high: int,
    max_pending_total: int,
    max_running: int,
    limit: int,
    reason: str,
    candidate_detail_limit: int = 50,
    include_all_candidates: bool = False,
) -> dict[str, Any]:
    now = _utc_now()
    before = _task_backlog_summary(state_root)
    candidates = load_candidates(
        state_root,
        now=now,
        max_pending_age_hours=max_pending_age_hours,
        max_running_age_hours=max_running_age_hours,
        limit=limit,
    )
    receipt_id = _receipt_id(now, candidates)
    pause_present = (state_root / ".PAUSE").exists()
    apply_allowed = (not apply) or pause_present or allow_unpaused_apply
    simulated_after = simulate_backlog(before, candidates)
    simulated_safe = _burn_in_preflight_passed(
        simulated_after,
        max_pending_high=max_pending_high,
        max_pending_total=max_pending_total,
        max_running=max_running,
    )
    applied_count = 0
    apply_error = ""
    if apply and apply_allowed:
        applied_count = apply_firebreak(
            state_root,
            candidates,
            receipt_id=receipt_id,
            applied_at=now.isoformat(),
            reason=reason,
        )
    elif apply and not apply_allowed:
        apply_error = "apply_requires_pause_file_or_allow_unpaused_apply"
    after = _task_backlog_summary(state_root) if apply and apply_allowed else simulated_after
    after_safe = _burn_in_preflight_passed(
        after,
        max_pending_high=max_pending_high,
        max_pending_total=max_pending_total,
        max_running=max_running,
    )
    candidate_preview = candidates[:candidate_detail_limit]
    report = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "status": "pass" if (not apply_error and after_safe) else "fail",
        "mode": "apply" if apply else "dry_run",
        "applied": bool(apply and apply_allowed),
        "applied_count": applied_count,
        "apply_error": apply_error,
        "state_root": str(state_root),
        "tasks_db": str(_task_db(state_root)),
        "pause_present": pause_present,
        "allow_unpaused_apply": allow_unpaused_apply,
        "reason": reason,
        "limits": {
            "max_pending_age_hours": max_pending_age_hours,
            "max_running_age_hours": max_running_age_hours,
            "max_pending_high": max_pending_high,
            "max_pending_total": max_pending_total,
            "max_running": max_running,
            "limit": limit,
        },
        "before": before,
        "candidate_count": len(candidates),
        "candidate_ids_sha256": _candidate_ids_sha256(candidates),
        "candidate_counts_by_reason": _count_by(candidates, "reason"),
        "candidate_counts_by_status_priority": _count_by(candidates, "status", "priority"),
        "candidate_preview_count": len(candidate_preview),
        "candidate_preview": [candidate.to_dict() for candidate in candidate_preview],
        "simulated_after": simulated_after,
        "simulated_after_evidence": _burn_in_preflight_evidence(simulated_after),
        "simulated_after_safe": simulated_safe,
        "after": after,
        "after_evidence": _burn_in_preflight_evidence(after),
        "after_safe": after_safe,
    }
    if include_all_candidates:
        report["candidates"] = [candidate.to_dict() for candidate in candidates]
    return report


def _print_text(report: dict[str, Any]) -> None:
    print("RUNTIME TASK BACKLOG FIREBREAK")
    print(f"status: {report['status']}")
    print(f"mode: {report['mode']}")
    print(f"receipt: {report['receipt_id']}")
    print(f"pause_present: {report['pause_present']}")
    if report.get("apply_error"):
        print(f"apply_error: {report['apply_error']}")
    print(f"candidate_count: {report['candidate_count']}")
    print(f"applied_count: {report['applied_count']}")
    print(f"before: {_burn_in_preflight_evidence(report.get('before') or {})}")
    print(f"after: {report.get('after_evidence')}")
    print(f"after_safe: {report['after_safe']}")
    print(f"candidate_counts_by_reason: {report['candidate_counts_by_reason']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-unpaused-apply", action="store_true")
    parser.add_argument("--max-pending-age-hours", type=float, default=4.0)
    parser.add_argument("--max-running-age-hours", type=float, default=6.0)
    parser.add_argument("--max-pending-high", type=int, default=25)
    parser.add_argument("--max-pending-total", type=int, default=100)
    parser.add_argument("--max-running", type=int, default=25)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--candidate-detail-limit", type=int, default=50)
    parser.add_argument("--include-all-candidates", action="store_true")
    parser.add_argument(
        "--reason",
        default="runtime_truth_unpaused_burn_in_firebreak",
    )
    parser.add_argument("--receipt", type=Path, default=None)
    parser.add_argument("--latest-report", type=Path, default=DEFAULT_LATEST_REPORT)
    parser.add_argument("--no-write-receipt", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    state_root = args.state_root.expanduser()
    report = build_firebreak_report(
        state_root=state_root,
        apply=args.apply,
        allow_unpaused_apply=args.allow_unpaused_apply,
        max_pending_age_hours=max(0.0, args.max_pending_age_hours),
        max_running_age_hours=max(0.0, args.max_running_age_hours),
        max_pending_high=max(0, args.max_pending_high),
        max_pending_total=max(0, args.max_pending_total),
        max_running=max(0, args.max_running),
        limit=max(0, args.limit),
        reason=args.reason,
        candidate_detail_limit=max(0, args.candidate_detail_limit),
        include_all_candidates=args.include_all_candidates,
    )
    if not args.no_write_receipt:
        receipt_path = args.receipt
        if receipt_path is None:
            receipt_path = DEFAULT_RECEIPT_DIR / f"{report['receipt_id']}.json"
        write_receipt(receipt_path.expanduser(), report)
        write_receipt(args.latest_report.expanduser(), report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_text(report)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
