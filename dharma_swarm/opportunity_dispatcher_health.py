"""Health state and stalled-frontier invariant helpers for the dispatcher."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("dharma_swarm.opportunity_dispatcher")


@dataclass
class HealthState:
    last_run_at: str = ""
    last_success_at: str | None = None
    consecutive_failures: int = 0
    run_count: int = 0
    success_count: int = 0
    last_run_dispatched: int = 0
    last_run_dry_run: bool = False
    last_run_paused: bool = False
    last_run_pending_count: int = 0
    last_run_errors: list[str] = field(default_factory=list)
    # Observer (PR2) - counts from the most recent reconciliation pass.
    last_run_observed_completed: int = 0
    last_run_observed_failed_retried: int = 0
    last_run_observed_failed_abandoned: int = 0
    last_run_observed_quarantined: int = 0
    last_run_observed_in_flight: int = 0


def read_health(path: Path) -> HealthState:
    if not path.exists():
        return HealthState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return HealthState()
    return HealthState(
        last_run_at=str(raw.get("last_run_at") or ""),
        last_success_at=raw.get("last_success_at"),
        consecutive_failures=int(raw.get("consecutive_failures") or 0),
        run_count=int(raw.get("run_count") or 0),
        success_count=int(raw.get("success_count") or 0),
        last_run_dispatched=int(raw.get("last_run_dispatched") or 0),
        last_run_dry_run=bool(raw.get("last_run_dry_run") or False),
        last_run_paused=bool(raw.get("last_run_paused") or False),
        last_run_pending_count=int(raw.get("last_run_pending_count") or 0),
        last_run_errors=list(raw.get("last_run_errors") or []),
        last_run_observed_completed=int(raw.get("last_run_observed_completed") or 0),
        last_run_observed_failed_retried=int(raw.get("last_run_observed_failed_retried") or 0),
        last_run_observed_failed_abandoned=int(raw.get("last_run_observed_failed_abandoned") or 0),
        last_run_observed_quarantined=int(raw.get("last_run_observed_quarantined") or 0),
        last_run_observed_in_flight=int(raw.get("last_run_observed_in_flight") or 0),
    )


def write_health(path: Path, state: HealthState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_run_at": state.last_run_at,
        "last_success_at": state.last_success_at,
        "consecutive_failures": state.consecutive_failures,
        "run_count": state.run_count,
        "success_count": state.success_count,
        "last_run_dispatched": state.last_run_dispatched,
        "last_run_dry_run": state.last_run_dry_run,
        "last_run_paused": state.last_run_paused,
        "last_run_pending_count": state.last_run_pending_count,
        "last_run_errors": state.last_run_errors[-5:],  # cap retained errors
        "last_run_observed_completed": state.last_run_observed_completed,
        "last_run_observed_failed_retried": state.last_run_observed_failed_retried,
        "last_run_observed_failed_abandoned": state.last_run_observed_failed_abandoned,
        "last_run_observed_quarantined": state.last_run_observed_quarantined,
        "last_run_observed_in_flight": state.last_run_observed_in_flight,
        "schema_version": 2,
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def update_health_from_result(state: HealthState, result: Any, ok: bool) -> HealthState:
    state.run_count += 1
    state.last_run_at = datetime.now(timezone.utc).isoformat()
    state.last_run_dry_run = result.dry_run
    state.last_run_paused = result.paused
    state.last_run_pending_count = result.pending_count
    state.last_run_dispatched = len(result.promoted)
    state.last_run_errors = list(result.errors)
    if ok:
        state.success_count += 1
        state.last_success_at = state.last_run_at
        state.consecutive_failures = 0
    else:
        state.consecutive_failures += 1
    return state


# Default cron interval if the operator has not set DISPATCHER_INTERVAL_SECONDS.
DEFAULT_INTERVAL_SECONDS = 1800  # 30 min - matches PR6 cron suggestion.

# Critical fires after N consecutive dispatcher failures.
CRITICAL_FAILURE_THRESHOLD = 3


def _is_frontier_active(pending_count: int, observed_in_flight: int) -> bool:
    """Return true when there is real frontier work to do."""
    return pending_count > 0 or observed_in_flight > 0


def _stall_window_seconds(interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> int:
    """Two missed cron intervals means the dispatcher is stale."""
    return 2 * int(interval_seconds)


def detect_stalled_frontier(
    *,
    state: HealthState,
    pending_count: int,
    observed_in_flight: int,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> dict[str, Any] | None:
    """Inspect health state and return an algedonic signal payload if stalled."""
    if not _is_frontier_active(pending_count, observed_in_flight):
        return None

    if state.consecutive_failures >= CRITICAL_FAILURE_THRESHOLD:
        return {
            "severity": "critical",
            "kind": "dispatcher_consecutive_failures",
            "action": f"opportunity_dispatcher failed {state.consecutive_failures}x in a row",
            "value": state.consecutive_failures,
            "description": (
                f"opportunity_dispatcher has failed {state.consecutive_failures} "
                f"consecutive times while pending={pending_count} and "
                f"in_flight={observed_in_flight}. The frontier is stalled — "
                f"investigate logs and last_run_errors before clearing."
            ),
            "context": {
                "consecutive_failures": state.consecutive_failures,
                "pending_count": pending_count,
                "in_flight": observed_in_flight,
                "last_run_errors": state.last_run_errors,
                "last_success_at": state.last_success_at,
            },
        }

    if state.last_success_at:
        try:
            last_success = datetime.fromisoformat(state.last_success_at)
        except ValueError:
            last_success = None
    else:
        last_success = None
    if last_success is not None:
        elapsed = (datetime.now(timezone.utc) - last_success).total_seconds()
        if elapsed > _stall_window_seconds(interval_seconds):
            return {
                "severity": "warning",
                "kind": "dispatcher_stale_success",
                "action": f"opportunity_dispatcher stale by {int(elapsed)}s",
                "value": int(elapsed),
                "description": (
                    f"opportunity_dispatcher last reported success "
                    f"{int(elapsed)}s ago (window={_stall_window_seconds(interval_seconds)}s) "
                    f"while pending={pending_count} and in_flight={observed_in_flight}."
                ),
                "context": {
                    "elapsed_seconds": int(elapsed),
                    "stall_window_seconds": _stall_window_seconds(interval_seconds),
                    "pending_count": pending_count,
                    "in_flight": observed_in_flight,
                    "last_success_at": state.last_success_at,
                },
            }

    return None


def maybe_fire_invariant(
    state: HealthState,
    pending_count: int,
    observed_in_flight: int,
    *,
    interval_seconds: int | None = None,
    source: str = "opportunity_dispatcher",
) -> None:
    """Detect a stalled frontier and fire through the bridge if needed."""
    if interval_seconds is None:
        interval_seconds = int(os.environ.get("DISPATCHER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))
    sig = detect_stalled_frontier(
        state=state,
        pending_count=pending_count,
        observed_in_flight=observed_in_flight,
        interval_seconds=interval_seconds,
    )
    if sig is None:
        return
    try:
        from dharma_swarm.algedonic_bridge import fire_signal
        fire_signal(
            kind=sig["kind"],
            severity=sig["severity"],
            action=sig["action"],
            value=sig["value"],
            description=sig["description"],
            source=source,
            context=sig["context"],
        )
    except Exception:
        logger.exception("algedonic_bridge.fire_signal raised")
