"""Read-only runtime context packet for agent startup and operator probes."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.telemetry_plane import DEFAULT_TELEMETRY_DB


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def runtime_db_path(state_dir: Path | str | None = None) -> Path:
    for env_name in ("DGC_ROUTER_TELEMETRY_DB", "DHARMA_RUNTIME_DB"):
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return Path(raw).expanduser()
    if state_dir is not None:
        return Path(state_dir).expanduser() / "state" / "runtime.db"
    return DEFAULT_TELEMETRY_DB


def git_snapshot(repo_root: Path | str) -> dict[str, Any]:
    root = Path(repo_root)
    branch = _run_git(root, "branch", "--show-current") or "<detached>"
    head = _run_git(root, "rev-parse", "--short=12", "HEAD") or ""
    dirty = _run_git(root, "status", "--porcelain=v1", "-uall")
    dirty_count = len([line for line in dirty.splitlines() if line.strip()])
    divergence = _run_git(root, "rev-list", "--left-right", "--count", "origin/main...HEAD")
    ahead = behind = None
    parts = divergence.split()
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        ahead = int(parts[1])
        behind = int(parts[0])
    return {
        "worktree": str(root),
        "branch": branch,
        "head": head,
        "dirty_entries": dirty_count,
        "origin_main_ahead": ahead,
        "origin_main_behind": behind,
        "origin_main_divergence_raw": divergence,
    }


def provider_route_snapshot(
    *,
    state_dir: Path | str | None = None,
    db_path: Path | str | None = None,
    limit: int = 40,
) -> dict[str, Any]:
    resolved = Path(db_path).expanduser() if db_path is not None else runtime_db_path(state_dir)
    base: dict[str, Any] = {
        "source": "telemetry_plane.provider_attempts",
        "db_path": str(resolved),
        "available": False,
        "recent_attempt_count": 0,
        "recent_success_count": 0,
        "recent_failure_count": 0,
        "recent_success_lanes": [],
        "blocked_lanes": [],
        "degraded_lanes": [],
        "lanes": [],
        "latest_attempts": [],
        "declared_model_targets": declared_model_targets(),
    }
    if not resolved.exists():
        base["error"] = "runtime_db_missing"
        return base
    try:
        conn = _connect_read_only(resolved)
    except sqlite3.Error as exc:
        base["error"] = f"sqlite_open_failed:{type(exc).__name__}"
        return base
    try:
        if not _table_exists(conn, "provider_attempts"):
            base["error"] = "provider_attempts_table_missing"
            return base
        rows = conn.execute(
            """
            SELECT provider, model, tier, success, outcome, error_class,
                   error_detail, duration_ms, circuit_state, created_at
            FROM provider_attempts
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    except sqlite3.Error as exc:
        base["error"] = f"provider_attempt_query_failed:{type(exc).__name__}"
        return base
    finally:
        conn.close()

    attempts = [_attempt_row(row) for row in rows]
    lanes = _lane_rollup(attempts)
    base.update(
        {
            "available": True,
            "recent_attempt_count": len(attempts),
            "recent_success_count": sum(1 for row in attempts if row["success"]),
            "recent_failure_count": sum(1 for row in attempts if not row["success"]),
            "latest_created_at": attempts[0]["created_at"] if attempts else "",
            "recent_success_lanes": [
                lane["route_key"] for lane in lanes if lane["successes"] > 0
            ],
            "blocked_lanes": [
                lane["route_key"] for lane in lanes if lane["status"] == "blocked"
            ],
            "degraded_lanes": [
                lane["route_key"] for lane in lanes if lane["status"] == "degraded"
            ],
            "lanes": lanes,
            "latest_attempts": attempts[:10],
        }
    )
    return base


def build_runtime_context_packet(
    *,
    repo_root: Path | str | None = None,
    state_dir: Path | str | None = None,
    health: dict[str, Any] | None = None,
    runtime_truth: dict[str, Any] | None = None,
    provider_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    state = Path(state_dir) if state_dir is not None else dharma_state_dir("DHARMA_STATE_DIR")
    route_snapshot = provider_route_snapshot(state_dir=state)
    return {
        "schema": "dharma_swarm.runtime_context.v1",
        "generated_at": utc_now(),
        "authority": "projection_only",
        "secrets_included": False,
        "repo": git_snapshot(root),
        "daemon": health or {},
        "runtime_truth": runtime_truth_summary(runtime_truth or {}),
        "provider_status": provider_status or {},
        "provider_routes": route_snapshot,
        "agent_startup_contract": {
            "one_command": "make onboard",
            "live_http": "GET http://127.0.0.1:7433/runtime-context",
            "truth_rule": "prefer this packet, git, and live DB evidence over prose",
            "provider_truth_source": route_snapshot["source"],
            "provider_truth_is_secret_free": True,
        },
    }


def runtime_truth_summary(payload: dict[str, Any]) -> dict[str, Any]:
    checks = [check for check in payload.get("checks") or [] if isinstance(check, dict)]
    failed = [
        str(check.get("id") or "unknown")
        for check in checks
        if check.get("passed") is not True
    ]
    failed_evidence = [
        {
            "id": str(check.get("id") or "unknown"),
            "evidence": str(check.get("evidence") or "")[:300],
        }
        for check in checks
        if check.get("passed") is not True
    ][:8]
    return {
        "schema_version": payload.get("schema_version", ""),
        "status": payload.get("status", "unknown"),
        "passed": payload.get("passed"),
        "failed_checks": failed,
        "failed_evidence": failed_evidence,
    }


def declared_model_targets() -> list[dict[str, str]]:
    try:
        from dharma_swarm.tui.model_routing import all_targets
    except Exception:
        return []
    return [
        {
            "alias": target.alias,
            "provider": target.provider_id,
            "model": target.model_id,
            "label": target.label,
        }
        for target in all_targets()
    ]


def _run_git(repo_root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            text=True,
            capture_output=True,
            timeout=8.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _connect_read_only(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _attempt_row(row: sqlite3.Row) -> dict[str, Any]:
    error_detail = str(row["error_detail"] or "")
    return {
        "provider": str(row["provider"] or ""),
        "model": str(row["model"] or ""),
        "route_key": _route_key(row["provider"], row["model"]),
        "tier": str(row["tier"] or "unknown"),
        "success": bool(row["success"]),
        "outcome": str(row["outcome"] or "unknown"),
        "error_class": str(row["error_class"] or ""),
        "error_detail": error_detail[:220],
        "duration_ms": float(row["duration_ms"] or 0.0),
        "circuit_state": str(row["circuit_state"] or "closed"),
        "created_at": str(row["created_at"] or ""),
    }


def _lane_rollup(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lanes: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        key = str(attempt["route_key"])
        lane = lanes.setdefault(
            key,
            {
                "route_key": key,
                "provider": attempt["provider"],
                "model": attempt["model"],
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "latest_outcome": attempt["outcome"],
                "latest_error_class": attempt["error_class"],
                "latest_error_detail": attempt["error_detail"],
                "latest_created_at": attempt["created_at"],
                "status": _attempt_status(attempt),
            },
        )
        lane["attempts"] += 1
        if attempt["success"]:
            lane["successes"] += 1
        else:
            lane["failures"] += 1
    return list(lanes.values())


def _attempt_status(attempt: dict[str, Any]) -> str:
    if attempt["success"]:
        return "live_success"
    outcome = str(attempt.get("outcome") or "").lower()
    detail = str(attempt.get("error_detail") or "").lower()
    error_class = str(attempt.get("error_class") or "").lower()
    text = " ".join([outcome, detail, error_class])
    if outcome == "started":
        return "in_flight"
    if any(token in text for token in ("402", "insufficient credits", "billing")):
        return "blocked"
    if any(token in text for token in ("404", "not found", "circuit_open")):
        return "blocked"
    if any(token in text for token in ("timeout", "429", "rate limit")):
        return "degraded"
    return "failing"


def _route_key(provider: Any, model: Any) -> str:
    provider_text = str(provider or "").strip()
    model_text = str(model or "").strip()
    return f"{provider_text}:{model_text}" if model_text else provider_text


def packet_json(packet: dict[str, Any]) -> str:
    return json.dumps(packet, sort_keys=True, indent=2)
