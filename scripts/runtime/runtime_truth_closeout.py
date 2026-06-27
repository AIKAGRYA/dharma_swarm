#!/usr/bin/env python3
"""Runtime truth closeout gate for the live daemon spine."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORT))

from dharma_swarm.operator_core.live_ops_census_contract import (  # noqa: E402
    DEFAULT_OUTPUT,
    DEFAULT_STATE_ROOT,
)

DEFAULT_MIN_LATEST_MAJOR = 50
DEFAULT_MIN_TERMINAL_MAJOR = 20
DEFAULT_MAX_CLEAN_EPOCH_DECLARATIONS = 1
# Clean-epoch declarations are append-only, so an all-time count can never
# shrink and would make the bound permanently red. Bound *recent* churn within
# a trailing window instead; the sample floor already defeats reset-gaming.
DEFAULT_CLEAN_EPOCH_LOOKBACK_HOURS = 24.0


@dataclass(frozen=True)
class CloseoutCheck:
    check_id: str
    passed: bool
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "status": "pass" if self.passed else "fail",
            "passed": self.passed,
            "evidence": self.evidence,
        }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _daemon_surface(census: dict[str, Any]) -> dict[str, Any]:
    for surface in census.get("surfaces") or []:
        if isinstance(surface, dict) and surface.get("id") == "substrate.dharma_daemon":
            return surface
    return {}


def _check(checks: list[CloseoutCheck], check_id: str, passed: bool, evidence: str) -> None:
    checks.append(CloseoutCheck(check_id, bool(passed), evidence))


def _task_backlog_summary(state_root: Path) -> dict[str, Any]:
    db_path = state_root / "db" / "tasks.db"
    if not db_path.exists():
        return {
            "available": False,
            "db_path": str(db_path),
            "error": "tasks_db_missing",
        }
    try:
        with sqlite3.connect(db_path) as db:
            rows = db.execute(
                """
                SELECT status, priority, COUNT(*)
                FROM tasks
                GROUP BY status, priority
                """
            ).fetchall()
    except sqlite3.Error as exc:
        return {
            "available": False,
            "db_path": str(db_path),
            "error": f"tasks_db_error:{type(exc).__name__}",
        }

    by_status_priority: dict[str, dict[str, int]] = {}
    for status, priority, count in rows:
        status_key = str(status or "unknown")
        priority_key = str(priority or "unknown")
        by_status_priority.setdefault(status_key, {})[priority_key] = int(count or 0)
    pending_statuses = {"pending", "ready", "assigned"}
    running_statuses = {"running", "in_progress"}
    pending_total = sum(
        count
        for status, priorities in by_status_priority.items()
        if status in pending_statuses
        for count in priorities.values()
    )
    pending_high = sum(
        priorities.get("high", 0) + priorities.get("urgent", 0)
        for status, priorities in by_status_priority.items()
        if status in pending_statuses
    )
    running_total = sum(
        count
        for status, priorities in by_status_priority.items()
        if status in running_statuses
        for count in priorities.values()
    )
    return {
        "available": True,
        "db_path": str(db_path),
        "by_status_priority": by_status_priority,
        "pending_total": pending_total,
        "pending_high_or_urgent": pending_high,
        "running_total": running_total,
    }


def _burn_in_preflight_evidence(backlog: dict[str, Any]) -> str:
    if not backlog.get("available"):
        return str(backlog.get("error") or "tasks backlog unavailable")
    return (
        f"pending_high_or_urgent={backlog.get('pending_high_or_urgent')}; "
        f"pending_total={backlog.get('pending_total')}; "
        f"running_total={backlog.get('running_total')}"
    )


def _burn_in_preflight_passed(
    backlog: dict[str, Any],
    *,
    max_pending_high: int,
    max_pending_total: int,
    max_running: int,
) -> bool:
    if not backlog.get("available"):
        return False
    return (
        int(backlog.get("pending_high_or_urgent") or 0) <= max_pending_high
        and int(backlog.get("pending_total") or 0) <= max_pending_total
        and int(backlog.get("running_total") or 0) <= max_running
    )


def _clean_epoch_declaration_summary(
    state_root: Path,
    *,
    lookback_hours: float = DEFAULT_CLEAN_EPOCH_LOOKBACK_HOURS,
    now: datetime | None = None,
) -> dict[str, Any]:
    db_path = state_root / "state" / "runtime.db"
    if not db_path.exists():
        return {
            "available": False,
            "db_path": str(db_path),
            "error": "runtime_db_missing",
        }
    anchor = now or datetime.now(UTC)
    cutoff_iso = (anchor - timedelta(hours=max(0.0, lookback_hours))).isoformat()
    try:
        uri = f"{db_path.expanduser().resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as db:
            total_count = int(
                db.execute(
                    """
                    SELECT COUNT(*)
                    FROM runtime_receipts
                    WHERE receipt_type = 'runtime_truth_clean_epoch'
                    """
                ).fetchone()[0]
            )
            recent_count = int(
                db.execute(
                    """
                    SELECT COUNT(*)
                    FROM runtime_receipts
                    WHERE receipt_type = 'runtime_truth_clean_epoch'
                      AND created_at >= ?
                    """,
                    (cutoff_iso,),
                ).fetchone()[0]
            )
            latest = [
                {
                    "receipt_id": str(receipt_id or ""),
                    "created_at": str(created_at or ""),
                    "status": str(status or ""),
                }
                for receipt_id, created_at, status in db.execute(
                    """
                    SELECT receipt_id, created_at, status
                    FROM runtime_receipts
                    WHERE receipt_type = 'runtime_truth_clean_epoch'
                    ORDER BY created_at DESC, receipt_id DESC
                    LIMIT 3
                    """
                ).fetchall()
            ]
    except sqlite3.Error as exc:
        return {
            "available": False,
            "db_path": str(db_path),
            "error": f"runtime_db_error:{type(exc).__name__}",
        }
    return {
        "available": True,
        "db_path": str(db_path),
        "count": recent_count,
        "recent_count": recent_count,
        "total_count": total_count,
        "lookback_hours": lookback_hours,
        "window_start": cutoff_iso,
        "latest": latest,
    }


def _clean_epoch_declaration_evidence(summary: dict[str, Any]) -> str:
    if not summary.get("available"):
        return str(summary.get("error") or "clean epoch declarations unavailable")
    latest = summary.get("latest") if isinstance(summary.get("latest"), list) else []
    latest_ids = [
        str(item.get("receipt_id") or "")
        for item in latest
        if isinstance(item, dict) and str(item.get("receipt_id") or "").strip()
    ]
    latest_text = ",".join(latest_ids) if latest_ids else "none"
    return (
        f"recent={summary.get('recent_count')}/{summary.get('lookback_hours')}h; "
        f"total={summary.get('total_count')}; latest={latest_text}"
    )


def evaluate_closeout(
    census: dict[str, Any],
    *,
    state_root: Path,
    allow_paused: bool = False,
    require_canonical_db: bool = True,
    min_latest_major: int = DEFAULT_MIN_LATEST_MAJOR,
    min_terminal_major: int = DEFAULT_MIN_TERMINAL_MAJOR,
    max_clean_epoch_declarations: int = DEFAULT_MAX_CLEAN_EPOCH_DECLARATIONS,
    clean_epoch_lookback_hours: float = DEFAULT_CLEAN_EPOCH_LOOKBACK_HOURS,
    max_pending_high: int = 25,
    max_pending_total: int = 100,
    max_running: int = 25,
) -> dict[str, Any]:
    daemon = _daemon_surface(census)
    raw = daemon.get("raw") if isinstance(daemon.get("raw"), dict) else {}
    coverage = (
        raw.get("runtime_receipt_coverage")
        if isinstance(raw.get("runtime_receipt_coverage"), dict)
        else {}
    )
    active_head = (
        raw.get("runtime_receipt_active_head")
        if isinstance(raw.get("runtime_receipt_active_head"), dict)
        else {}
    )
    since_boot = (
        raw.get("runtime_receipt_since_boot")
        if isinstance(raw.get("runtime_receipt_since_boot"), dict)
        else {}
    )
    epoch = (
        raw.get("runtime_truth_clean_epoch")
        if isinstance(raw.get("runtime_truth_clean_epoch"), dict)
        else {}
    )
    checks: list[CloseoutCheck] = []
    canonical_db = state_root / "state" / "runtime.db"
    observed_db = Path(str(coverage.get("db_path") or ""))
    pause_path = state_root / ".PAUSE"
    pause_present = pause_path.exists()
    backlog = _task_backlog_summary(state_root)
    clean_epoch_declarations = _clean_epoch_declaration_summary(
        state_root, lookback_hours=clean_epoch_lookback_hours
    )

    _check(
        checks,
        "daemon_surface_present",
        bool(daemon),
        "substrate.dharma_daemon surface found" if daemon else "daemon surface missing",
    )
    _check(
        checks,
        "daemon_live",
        daemon.get("status") == "live",
        f"daemon status={daemon.get('status', 'missing')}",
    )
    daemon_gaps = [
        str(gap)
        for gap in (daemon.get("proof_gaps") or [])
        if str(gap or "").strip()
    ]
    _check(
        checks,
        "daemon_proof_gaps_empty",
        not daemon_gaps,
        "none" if not daemon_gaps else ",".join(daemon_gaps),
    )
    _check(
        checks,
        "canonical_runtime_db",
        (not require_canonical_db) or observed_db == canonical_db,
        f"observed={observed_db}; expected={canonical_db}",
    )
    _check(
        checks,
        "clean_epoch_verified",
        epoch.get("enabled") is True and epoch.get("receipt_verified") is True,
        str(epoch.get("evidence") or "clean epoch not verified"),
    )
    clean_epoch_count = int(clean_epoch_declarations.get("count") or 0)
    _check(
        checks,
        "clean_epoch_declarations_bounded",
        clean_epoch_declarations.get("available") is True
        and clean_epoch_count <= max_clean_epoch_declarations,
        (
            _clean_epoch_declaration_evidence(clean_epoch_declarations)
            + f"; max<={max_clean_epoch_declarations}"
        ),
    )
    _check(
        checks,
        "coverage_report_available",
        coverage.get("coverage_report_available") is True,
        str(coverage.get("evidence") or "coverage report unavailable"),
    )
    _check(
        checks,
        "active_head_side_effect_clean",
        active_head.get("active_head_side_effect_key_clean") is True,
        str(active_head.get("evidence") or "active head side_effect_key unproven"),
    )
    _check(
        checks,
        "since_boot_major_identity_clean",
        since_boot.get("since_boot_major_identity_clean") is True,
        str(since_boot.get("evidence") or "since-boot major receipt identity unproven"),
    )
    latest_sample = int(coverage.get("latest_sample_size") or 0)
    terminal_sample = int(coverage.get("latest_terminal_sample_size") or 0)
    _check(
        checks,
        "latest_major_sample_present",
        latest_sample >= min_latest_major,
        f"latest={latest_sample}; required>={min_latest_major}",
    )
    _check(
        checks,
        "terminal_major_sample_present",
        terminal_sample >= min_terminal_major,
        f"terminal={terminal_sample}; required>={min_terminal_major}",
    )
    _check(
        checks,
        "provider_model_accounted",
        coverage.get("provider_model_latest_complete") is True,
        (
            f"basis={coverage.get('provider_model_readiness_basis')}; "
            f"latest_accounted="
            f"{coverage.get('latest_major_task_receipts_provider_model_accounted_percent')}; "
            f"terminal_accounted="
            f"{coverage.get('latest_terminal_major_task_receipts_provider_model_accounted_percent')}"
        ),
    )
    blockers = [
        str(blocker)
        for blocker in [
            *(coverage.get("blockers") or []),
            *(coverage.get("production_readiness_blockers") or []),
        ]
        if str(blocker or "").strip()
    ]
    _check(
        checks,
        "coverage_blockers_empty",
        not blockers,
        "none" if not blockers else " | ".join(blockers),
    )
    _check(
        checks,
        "daemon_unpaused",
        allow_paused or not pause_present,
        (
            f"pause_present={pause_present}; path={pause_path}; "
            f"allow_paused={allow_paused}"
        ),
    )
    _check(
        checks,
        "unpaused_burn_in_preflight",
        allow_paused
        or _burn_in_preflight_passed(
            backlog,
            max_pending_high=max_pending_high,
            max_pending_total=max_pending_total,
            max_running=max_running,
        ),
        (
            "skipped for paused smoke"
            if allow_paused
            else _burn_in_preflight_evidence(backlog)
            + (
                f"; limits high_or_urgent<={max_pending_high} "
                f"total<={max_pending_total} running<={max_running}"
            )
        ),
    )

    passed = all(check.passed for check in checks)
    return {
        "schema_version": "runtime_truth_closeout.v1",
        "status": "pass" if passed else "fail",
        "passed": passed,
        "state_root": str(state_root),
        "canonical_db": str(canonical_db),
        "scope": {
            "mode": coverage.get("scope_mode") or "all",
            "since_created_at": coverage.get("scope_since_created_at") or "",
            "epoch_receipt_id": epoch.get("receipt_id") or "",
        },
        "unpaused_burn_in_preflight": backlog,
        "clean_epoch_declarations": clean_epoch_declarations,
        "checks": [check.to_dict() for check in checks],
    }


def _build_census(repo_root: Path, state_root: Path) -> dict[str, Any]:
    from scripts.runtime.live_ops_census import build_live_ops_census

    return build_live_ops_census(
        repo_root=repo_root,
        state_root=state_root,
        run_probes=True,
    )


def _print_text(result: dict[str, Any]) -> None:
    print("RUNTIME TRUTH CLOSEOUT")
    print(f"status: {result['status']}")
    scope = result.get("scope") or {}
    print(
        "scope: "
        f"mode={scope.get('mode')} "
        f"since={scope.get('since_created_at') or '?'} "
        f"epoch={scope.get('epoch_receipt_id') or '?'}"
    )
    for check in result.get("checks") or []:
        print(
            f"{check['status'].upper():<4} {check['id']}: "
            f"{check.get('evidence') or ''}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT_FOR_IMPORT)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--census", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-refresh-census", action="store_true")
    parser.add_argument("--allow-paused", action="store_true")
    parser.add_argument("--allow-db-override", action="store_true")
    parser.add_argument("--min-latest-major", type=int, default=DEFAULT_MIN_LATEST_MAJOR)
    parser.add_argument("--min-terminal-major", type=int, default=DEFAULT_MIN_TERMINAL_MAJOR)
    parser.add_argument(
        "--max-clean-epoch-declarations",
        type=int,
        default=DEFAULT_MAX_CLEAN_EPOCH_DECLARATIONS,
    )
    parser.add_argument(
        "--clean-epoch-lookback-hours",
        type=float,
        default=DEFAULT_CLEAN_EPOCH_LOOKBACK_HOURS,
    )
    parser.add_argument("--max-pending-high", type=int, default=25)
    parser.add_argument("--max-pending-total", type=int, default=100)
    parser.add_argument("--max-running", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    state_root = args.state_root.expanduser()
    if args.no_refresh_census:
        census = _load_json(args.census.expanduser())
    else:
        census = _build_census(args.repo_root.expanduser(), state_root)
    result = evaluate_closeout(
        census,
        state_root=state_root,
        allow_paused=args.allow_paused,
        require_canonical_db=not args.allow_db_override,
        min_latest_major=max(0, args.min_latest_major),
        min_terminal_major=max(0, args.min_terminal_major),
        max_clean_epoch_declarations=max(0, args.max_clean_epoch_declarations),
        clean_epoch_lookback_hours=max(0.0, args.clean_epoch_lookback_hours),
        max_pending_high=max(0, args.max_pending_high),
        max_pending_total=max(0, args.max_pending_total),
        max_running=max(0, args.max_running),
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_text(result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
