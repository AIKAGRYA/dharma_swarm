"""Helpers for canonical runtime artifacts under ``~/.dharma``."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def parse_iso_datetime(raw: Any) -> datetime | None:
    """Return a UTC datetime for an ISO-ish timestamp, or ``None``."""
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def pulse_log_candidates(state_dir: Path) -> tuple[Path, ...]:
    """Return pulse log locations in canonical preference order."""
    return (
        state_dir / "logs" / "pulse.log",
        state_dir / "pulse.log",
    )


def freshest_pulse_log_path(state_dir: Path) -> Path | None:
    """Return the freshest existing pulse log, if any."""
    existing = [path for path in pulse_log_candidates(state_dir) if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda path: path.stat().st_mtime)


def pulse_log_fresh(state_dir: Path, *, freshness_seconds: float) -> bool:
    """Whether any known pulse log was updated recently enough."""
    pulse_log = freshest_pulse_log_path(state_dir)
    if pulse_log is None:
        return False
    age_seconds = max(
        0.0,
        datetime.now(timezone.utc).timestamp() - pulse_log.stat().st_mtime,
    )
    return age_seconds < freshness_seconds


def append_pulse_log(state_dir: Path, entry: str) -> None:
    """Write a pulse entry to the canonical log and mirror the legacy path."""
    for path in pulse_log_candidates(state_dir):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _positive_float(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


def _liveness_summary(
    payload: dict[str, Any],
    *,
    stale_after_seconds: float,
) -> dict[str, Any]:
    raw = payload.get("liveness")
    if not isinstance(raw, dict):
        raw = {}

    process_started_at = parse_iso_datetime(raw.get("process_started_at"))
    bootstrap_started_at = parse_iso_datetime(raw.get("bootstrap_started_at"))
    bootstrap_completed_at = parse_iso_datetime(raw.get("bootstrap_completed_at"))
    last_tick_started_at = parse_iso_datetime(raw.get("last_tick_started_at"))
    last_tick_completed_at = parse_iso_datetime(raw.get("last_tick_completed_at"))
    last_coordination_started_at = parse_iso_datetime(raw.get("last_coordination_started_at"))
    last_coordination_completed_at = parse_iso_datetime(raw.get("last_coordination_completed_at"))
    last_task_dispatch_at = parse_iso_datetime(raw.get("last_task_dispatch_at"))
    last_task_completion_at = parse_iso_datetime(raw.get("last_task_completion_at"))
    stall_since = parse_iso_datetime(raw.get("stall_since"))

    bootstrap_phase = str(raw.get("bootstrap_phase", "unknown") or "unknown").strip() or "unknown"
    bootstrap_complete = bootstrap_phase == "bootstrap_complete" or bootstrap_completed_at is not None

    tick_interval_s = _positive_float(raw.get("tick_interval_s")) or 30.0
    coordination_refresh_interval_s = (
        _positive_float(raw.get("coordination_refresh_interval_s")) or tick_interval_s
    )
    tick_fresh_threshold_s = max(15.0, tick_interval_s * 3.0)
    coordination_fresh_threshold_s = max(
        tick_fresh_threshold_s,
        coordination_refresh_interval_s * 2.0,
    )
    bootstrap_stall_threshold_s = max(120.0, tick_interval_s * 4.0)

    now = datetime.now(timezone.utc)

    def _age(ts: datetime | None) -> float | None:
        if ts is None:
            return None
        return max(0.0, (now - ts).total_seconds())

    phase_history = raw.get("bootstrap_phase_history")
    phase_entered_at = bootstrap_started_at
    if isinstance(phase_history, list):
        for entry in reversed(phase_history):
            if isinstance(entry, dict):
                candidate = parse_iso_datetime(entry.get("entered_at"))
                if candidate is not None:
                    phase_entered_at = candidate
                    break

    last_progress_at = (
        last_tick_completed_at
        or bootstrap_completed_at
        or phase_entered_at
        or bootstrap_started_at
        or process_started_at
    )

    tick_age_seconds = _age(last_tick_completed_at)
    coordination_age_seconds = _age(last_coordination_completed_at)
    phase_age_seconds = _age(phase_entered_at)
    last_task_dispatch_age_seconds = _age(last_task_dispatch_at)
    last_task_completion_age_seconds = _age(last_task_completion_at)

    tick_fresh = tick_age_seconds is not None and tick_age_seconds <= tick_fresh_threshold_s
    coordination_fresh = (
        coordination_age_seconds is not None
        and coordination_age_seconds <= coordination_fresh_threshold_s
    )

    persisted_stall_state = str(raw.get("stall_state", "none") or "none").strip() or "none"
    persisted_stall_reason = str(raw.get("stall_reason", "") or "").strip()
    stall_state = persisted_stall_state
    stall_reason = persisted_stall_reason
    status = "unknown"

    if persisted_stall_state != "none":
        status = "stalled"
    elif not bootstrap_complete:
        if phase_age_seconds is not None and phase_age_seconds > bootstrap_stall_threshold_s:
            status = "stalled"
            stall_state = "bootstrap_stalled"
            stall_reason = stall_reason or f"bootstrap phase '{bootstrap_phase}' exceeded freshness window"
            if stall_since is None:
                stall_since = phase_entered_at
        else:
            status = "booting"
            stall_state = "none"
            stall_reason = ""
    elif not tick_fresh:
        status = "stalled"
        stall_state = "tick_stalled"
        stall_reason = stall_reason or "last swarm tick is stale"
        if stall_since is None:
            stall_since = last_tick_completed_at or last_tick_started_at or last_progress_at
    elif not coordination_fresh:
        status = "degraded"
        stall_state = "coordination_stale"
        stall_reason = stall_reason or "coordination window is stale"
        if stall_since is None:
            stall_since = last_coordination_completed_at or last_progress_at
    else:
        status = "healthy"
        stall_state = "none"
        stall_reason = ""
        stall_since = None

    return {
        "process_started_at": raw.get("process_started_at"),
        "bootstrap_phase": bootstrap_phase,
        "bootstrap_started_at": raw.get("bootstrap_started_at"),
        "bootstrap_completed_at": raw.get("bootstrap_completed_at"),
        "bootstrap_phase_history": phase_history if isinstance(phase_history, list) else [],
        "bootstrap_complete": bootstrap_complete,
        "last_tick_started_at": raw.get("last_tick_started_at"),
        "last_tick_completed_at": raw.get("last_tick_completed_at"),
        "last_tick_duration_s": raw.get("last_tick_duration_s"),
        "last_tick_number": int(raw.get("last_tick_number", 0) or 0),
        "last_coordination_started_at": raw.get("last_coordination_started_at"),
        "last_coordination_completed_at": raw.get("last_coordination_completed_at"),
        "last_coordination_duration_s": raw.get("last_coordination_duration_s"),
        "last_task_dispatch_at": raw.get("last_task_dispatch_at"),
        "last_task_completion_at": raw.get("last_task_completion_at"),
        "last_task_dispatch_age_seconds": last_task_dispatch_age_seconds,
        "last_task_completion_age_seconds": last_task_completion_age_seconds,
        "total_agents": int(raw.get("total_agents", 0) or 0),
        "idle_agents": int(raw.get("idle_agents", 0) or 0),
        "tasks_pending": int(raw.get("tasks_pending", 0) or 0),
        "tasks_assigned": int(raw.get("tasks_assigned", 0) or 0),
        "tasks_running": int(raw.get("tasks_running", 0) or 0),
        "tasks_completed": int(raw.get("tasks_completed", 0) or 0),
        "tasks_failed": int(raw.get("tasks_failed", 0) or 0),
        "tick_interval_s": tick_interval_s,
        "coordination_refresh_interval_s": coordination_refresh_interval_s,
        "tick_fresh_threshold_s": tick_fresh_threshold_s,
        "coordination_fresh_threshold_s": coordination_fresh_threshold_s,
        "tick_age_seconds": tick_age_seconds,
        "coordination_age_seconds": coordination_age_seconds,
        "phase_age_seconds": phase_age_seconds,
        "tick_fresh": tick_fresh,
        "coordination_fresh": coordination_fresh,
        "status": status,
        "stall_state": stall_state,
        "stall_reason": stall_reason,
        "stall_since": stall_since.isoformat() if stall_since is not None else None,
    }


def dgc_health_snapshot_summary(
    state_dir: Path,
    *,
    stale_after_seconds: float = 3600.0,
) -> dict[str, Any]:
    """Read ``dgc_health.json`` with freshness metadata."""
    path = state_dir / "stigmergy" / "dgc_health.json"
    summary: dict[str, Any] = {
        "path": path,
        "exists": path.exists(),
        "status": "missing",
        "payload": None,
        "timestamp": None,
        "age_seconds": None,
        "daemon_pid": None,
        "live_pid": None,
        "daemon_pid_mismatch": False,
        "liveness": {},
    }
    if not path.exists():
        return summary

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        summary["status"] = "unreadable"
        summary["error"] = str(exc)
        return summary

    timestamp = parse_iso_datetime(payload.get("timestamp"))
    now = datetime.now(timezone.utc)
    age_seconds = None if timestamp is None else max(0.0, (now - timestamp).total_seconds())

    daemon_pid = payload.get("daemon_pid")
    live_pid = None
    pid_file = state_dir / "daemon.pid"
    if pid_file.exists():
        try:
            live_pid = int(pid_file.read_text(encoding="utf-8").strip())
        except Exception:
            live_pid = None

    summary.update(
        {
            "payload": payload,
            "timestamp": timestamp,
            "age_seconds": age_seconds,
            "daemon_pid": daemon_pid,
            "live_pid": live_pid,
            "daemon_pid_mismatch": (
                daemon_pid is not None
                and live_pid is not None
                and str(daemon_pid).strip() != str(live_pid).strip()
            ),
            "liveness": _liveness_summary(payload, stale_after_seconds=stale_after_seconds),
        }
    )

    if timestamp is None:
        summary["status"] = "unknown"
    elif age_seconds is not None and age_seconds > stale_after_seconds:
        summary["status"] = "stale"
    else:
        summary["status"] = "fresh"
    return summary


def build_swarm_liveness_watch_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    liveness = snapshot.get("liveness") if isinstance(snapshot.get("liveness"), dict) else {}
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_status": snapshot.get("status", "missing"),
        "snapshot_age_seconds": snapshot.get("age_seconds"),
        "daemon_pid_mismatch": bool(snapshot.get("daemon_pid_mismatch")),
        "source": payload.get("source"),
        "agent_count": payload.get("agent_count"),
        "task_count": payload.get("task_count"),
        "liveness": liveness,
    }


def write_swarm_liveness_snapshot(state_dir: Path, snapshot: dict[str, Any]) -> Path:
    """Persist the canonical operator-facing swarm liveness artifact."""
    path = state_dir / "meta" / "swarm_liveness.json"
    _write_json_atomic(path, build_swarm_liveness_watch_payload(snapshot))
    return path


def write_dgc_health_snapshot(
    state_dir: Path,
    *,
    daemon_pid: int,
    agent_count: int,
    task_count: int,
    anomaly_count: int,
    source: str,
    liveness: dict[str, Any] | None = None,
) -> Path:
    """Persist a fresh canonical ``dgc_health.json`` snapshot."""
    path = state_dir / "stigmergy" / "dgc_health.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    payload = {
        "daemon_pid": int(daemon_pid),
        "agent_count": int(agent_count),
        "task_count": int(task_count),
        "anomaly_count": int(anomaly_count),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }
    if liveness is None and isinstance(existing.get("liveness"), dict):
        payload["liveness"] = existing["liveness"]
    elif isinstance(liveness, dict):
        payload["liveness"] = liveness
    _write_json_atomic(path, payload)
    return path
