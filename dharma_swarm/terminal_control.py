"""Shared terminal-control state loader for dashboard and terminal bridge.

Reads only supervisor-owned ``run.json`` and ``verification.json`` authority
and exposes a compact, shell-neutral summary. Terminal-authored legacy
sidecars are deliberately not inputs to verification, loop, or run truth.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_SUPERVISOR_ROOT = Path.home() / ".dharma" / "terminal_supervisor"
SUPERVISOR_STATE_ENV_VARS = (
    "DHARMA_TERMINAL_SUPERVISOR_STATE_DIR",
    "DHARMA_TERMINAL_STATE_DIR",
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _summary_field(summary: dict[str, Any], key: str) -> str:
    value = summary.get(key)
    return value.strip() if isinstance(value, str) else ""


def _string_field(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _parse_verification_checks(value: Any) -> list[dict[str, Any]]:
    """Validate the supervisor's structured verification bundle atomically."""

    if not isinstance(value, list) or not value:
        return []
    checks: list[dict[str, Any]] = []
    for check in value:
        if not isinstance(check, dict):
            return []
        name = check.get("name")
        ok = check.get("ok")
        if not isinstance(name, str) or not name.strip() or not isinstance(ok, bool):
            return []
        checks.append({"name": name.strip(), "ok": ok})
    return checks


def _build_verification_summary(checks: list[dict[str, Any]]) -> dict[str, str]:
    if not checks:
        return {
            "status": "unknown",
            "passing": "unknown",
            "failing": "unknown",
            "bundle": "none",
        }
    passing = [check["name"] for check in checks if check.get("ok")]
    failing = [check["name"] for check in checks if not check.get("ok")]
    return {
        "status": (
            f"{len(failing)} failing, {len(passing)}/{len(checks)} passing"
            if failing
            else f"all {len(checks)} checks passing"
        ),
        "passing": ", ".join(passing) if passing else "none",
        "failing": ", ".join(failing) if failing else "none",
        "bundle": " | ".join(f"{check['name']}={'ok' if check['ok'] else 'fail'}" for check in checks),
    }


def _optional_int(record: dict[str, Any], key: str) -> int | None:
    value = record.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def candidate_supervisor_state_dirs() -> list[Path]:
    explicit = [
        Path(value.strip())
        for name in SUPERVISOR_STATE_ENV_VARS
        for value in [os.getenv(name, "")]
        if value.strip()
    ]
    if explicit:
        return explicit
    if not DEFAULT_SUPERVISOR_ROOT.exists():
        return []
    return [
        child / "state"
        for child in DEFAULT_SUPERVISOR_ROOT.iterdir()
        if child.is_dir()
    ]


def resolve_supervisor_state_dir(repo_root: str | Path) -> Path | None:
    repo_root = Path(repo_root).resolve()
    candidates: list[tuple[Path, str, float]] = []
    for state_dir in candidate_supervisor_state_dirs():
        run_path = state_dir / "run.json"
        if not run_path.exists():
            continue
        run = _read_json(run_path)
        run_repo_root = str(run.get("repo_root", "") or "").strip()
        if run_repo_root and Path(run_repo_root).resolve() != repo_root:
            continue
        updated_at = str(run.get("updated_at", "") or "")
        try:
            mtime = run_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        candidates.append((state_dir, updated_at, mtime))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[1], item[2]), reverse=True)
    return candidates[0][0]


def load_terminal_control_state(repo_root: str | Path) -> dict[str, Any] | None:
    state_dir = resolve_supervisor_state_dir(repo_root)
    if state_dir is None:
        return None

    run = _read_json(state_dir / "run.json")
    verification = _read_json(state_dir / "verification.json")
    summary = _as_record(run.get("last_summary_fields"))
    verification_checks = _parse_verification_checks(verification.get("checks"))
    verification_rows = _build_verification_summary(verification_checks)
    checks = [
        f"{check['name']} {'ok' if check['ok'] else 'fail'}"
        for check in verification_checks
    ]

    run_continue_required = run.get("last_continue_required")
    verification_continue_required = verification.get("continue_required")
    has_failing_check = any(not check["ok"] for check in verification_checks)
    if has_failing_check or run_continue_required is True or verification_continue_required is True:
        continue_required: bool | None = True
    elif (
        run_continue_required is False
        and verification_checks
        and verification_continue_required is False
    ):
        continue_required = False
    else:
        continue_required = None

    cycle = _optional_int(run, "cycle")
    run_status = _string_field(run, "status") or "unknown"
    tasks_total = _optional_int(run, "tasks_total")
    tasks_pending = _optional_int(run, "tasks_pending")
    active_task_id = _string_field(run, "last_task_id")
    last_result_status = _summary_field(summary, "status")
    acceptance = _summary_field(summary, "acceptance")
    next_task = _summary_field(summary, "next_task")
    updated_at = _string_field(run, "updated_at")
    loop_state = f"cycle {cycle} {run_status}" if cycle is not None else run_status
    task_progress = ""
    if tasks_total is not None and tasks_pending is not None:
        tasks_done = max(tasks_total - tasks_pending, 0)
        task_progress = f"{tasks_done} done, {tasks_pending} pending of {tasks_total}"

    return {
        "state_dir": str(state_dir),
        "cycle": cycle,
        "run_status": run_status,
        "tasks_total": tasks_total,
        "tasks_pending": tasks_pending,
        "active_task_id": active_task_id,
        "last_result_status": last_result_status,
        "acceptance": acceptance,
        "verification_summary": verification_rows["bundle"] if verification_checks else "unknown",
        "verification_checks": checks,
        "verification_status": verification_rows["status"],
        "verification_passing": verification_rows["passing"],
        "verification_failing": verification_rows["failing"],
        "verification_bundle": verification_rows["bundle"],
        "continue_required": continue_required,
        "loop_decision": (
            "continue required"
            if continue_required is True
            else "ready to stop"
            if continue_required is False
            else "unknown"
        ),
        "next_task": next_task,
        "updated_at": updated_at,
        "loop_state": loop_state,
        "task_progress": task_progress,
        "last_result": _summary_field(summary, "result"),
        "runtime_db": "",
        "session_state": "",
        "run_state": run_status if run_status != "unknown" else "",
        "active_runs_detail": "",
        "context_state": "",
        "recent_operator_actions": "",
        "runtime_activity": "",
        "artifact_state": "",
        "toolchain": "",
        "alerts": "",
        "runtime_summary": "",
        "runtime_freshness": "",
    }
