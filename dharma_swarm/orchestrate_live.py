"""Live Orchestrator — runs all DGC systems concurrently.

Boots SwarmManager + concurrent pulse heartbeat + evolution cycles + health
monitoring in a single asyncio event loop. Uses `claude -p` (authenticated)
as the execution engine — no API keys required.

Usage:
    dgc orchestrate                     # interactive (60s tick)
    dgc orchestrate --background        # background daemon
    python3 -m dharma_swarm.orchestrate_live  # direct

Systems run concurrently:
    1. Swarm loop — agent pool, task dispatch, coordination synthesis
    2. Pulse loop — claude -p heartbeat with thread rotation + telos gates
    3. Evolution loop — periodic Darwin Engine cycles
    4. Living layers — stigmergy decay, shakti perception, subconscious dreams
    5. Health monitor — anomaly detection, auto-healing
    6. Zeitgeist (S4) — environmental scanning, gate pressure feedback
    7. Witness (S3*) — sporadic random audit of agent behavior
    8. Training flywheel — trajectory scoring, strategy reinforcement, dataset building
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

from dharma_swarm.config import DEFAULT_CONFIG
from dharma_swarm.models import TaskPriority, TaskStatus
from dharma_swarm.pending_proposals import append_pending_proposals
from dharma_swarm.runtime_artifacts import (
    dgc_health_snapshot_summary,
    freshest_pulse_log_path,
    parse_iso_datetime,
    write_dgc_health_snapshot,
)

HOME = Path.home()
STATE_DIR = HOME / ".dharma"
LOG_DIR = STATE_DIR / "logs"

# Orchestrator defaults — sourced from central config (env overrides baked in)
_ll = DEFAULT_CONFIG.live_loop
SWARM_TICK = _ll.swarm_tick_seconds
PULSE_INTERVAL = _ll.pulse_interval_seconds
EVOLUTION_INTERVAL = _ll.evolution_interval_seconds
HEALTH_INTERVAL = _ll.health_interval_seconds
LIVING_INTERVAL = _ll.living_interval_seconds
MAX_DAILY = _ll.max_daily_tasks
_RUNTIME_HEALTH_STATE: dict[str, int] = {
    "agent_count": 0,
    "task_count": 0,
}
SWARM_LIVENESS_PATH = STATE_DIR / "meta" / "swarm_liveness.json"
STARTUP_SEED_TIMEOUT_S = max(5.0, min(float(SWARM_TICK), 30.0))
CAMPAIGN_NURTURE_INTERVAL_S = max(300.0, min(1800.0, float(SWARM_TICK) * 5.0))
CAMPAIGN_NURTURE_STALE_HOURS = 2.0
CAMPAIGN_NURTURE_RECENT_HOURS = 12.0
CAMPAIGN_NURTURE_MAX_SPECS = 3


def _update_runtime_health_state(*, agent_count: int | None = None, task_count: int | None = None) -> None:
    if agent_count is not None:
        _RUNTIME_HEALTH_STATE["agent_count"] = max(0, int(agent_count))
    if task_count is not None:
        _RUNTIME_HEALTH_STATE["task_count"] = max(0, int(task_count))


def _log(system: str, msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] [{system}] {msg}"
    print(line, flush=True)
    logger.info("[%s] %s", system, msg)


async def _consume_event_backlog(
    bus: Any,
    event_type: str,
    *,
    batch_size: int = 500,
    max_events: int = 1000,
) -> list[Any]:
    """Drain a bounded event backlog without starving the loop."""
    events: list[Any] = []
    while len(events) < max_events:
        remaining = max_events - len(events)
        limit = max(1, min(batch_size, remaining))
        batch = await bus.consume_events(event_type, limit=limit)
        if not batch:
            break
        events.extend(batch)
        if len(batch) < limit:
            break
    return events


def _swarm_liveness_watch_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
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


def _write_swarm_liveness_watch(state_dir: Path, payload: dict[str, Any]) -> Path:
    path = state_dir / "meta" / "swarm_liveness.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _swarm_liveness_transition_key(payload: dict[str, Any]) -> tuple[str, str, str]:
    liveness = payload.get("liveness") if isinstance(payload.get("liveness"), dict) else {}
    return (
        str(liveness.get("status", "unknown") or "unknown"),
        str(liveness.get("bootstrap_phase", "unknown") or "unknown"),
        str(liveness.get("stall_state", "none") or "none"),
    )


def _log_swarm_liveness_transition(
    previous_key: tuple[str, str, str] | None,
    payload: dict[str, Any],
) -> tuple[str, str, str]:
    key = _swarm_liveness_transition_key(payload)
    if key == previous_key:
        return key

    liveness = payload.get("liveness") if isinstance(payload.get("liveness"), dict) else {}
    status, phase, stall_state = key
    reason = str(liveness.get("stall_reason", "") or "").strip()

    if status == "stalled":
        detail = reason or stall_state.replace("_", " ")
        _log("watchdog", f"Swarm hot path stalled at phase={phase}: {detail}")
    elif status == "booting":
        _log("watchdog", f"Swarm hot path booting: phase={phase}")
    elif status == "degraded":
        detail = reason or stall_state.replace("_", " ")
        _log("watchdog", f"Swarm hot path degraded at phase={phase}: {detail}")
    elif status == "healthy":
        _log("watchdog", f"Swarm hot path healthy: phase={phase}")

    return key


def _enqueue_shakti_escalations(
    perceptions: list[Any],
    *,
    proposals_path: Path | None = None,
) -> int:
    """Durably hand Shakti escalations to Darwin through the shared queue."""
    payloads: list[dict[str, Any]] = []
    for perception in perceptions:
        impact_level = str(getattr(perception, "impact_level", "") or "").strip().lower()
        if impact_level not in {"module", "system"}:
            continue
        connection = str(getattr(perception, "connection", "") or "system").strip() or "system"
        observation = str(
            getattr(perception, "proposal", "") or getattr(perception, "observation", "") or ""
        ).strip()
        energy = getattr(getattr(perception, "energy", None), "value", None) or str(
            getattr(perception, "energy", "unknown")
        )
        salience = float(getattr(perception, "salience", 0.0) or 0.0)
        payloads.append(
            {
                "component": connection,
                "change_type": "shakti_escalation",
                "description": f"[shakti:{energy}] {observation}",
                "diff": "",
                "spec_ref": "shakti_loop",
                "metadata": {
                    "source": "living_layers",
                    "impact_level": impact_level,
                    "salience": salience,
                    "energy": str(energy),
                },
            }
        )
    return append_pending_proposals(payloads, path=proposals_path)


async def _wait_or_shutdown(shutdown_event: asyncio.Event, delay: float) -> bool:
    """Sleep for a backoff window unless shutdown is requested first."""
    if delay <= 0:
        return shutdown_event.is_set()
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
        return True
    except asyncio.TimeoutError:
        return shutdown_event.is_set()


async def _wait_for_bootstrap_gate(
    system: str,
    bootstrap_ready_event: asyncio.Event | None,
    shutdown_event: asyncio.Event,
) -> bool:
    """Block noncritical boot work until the swarm startup gate opens."""
    if bootstrap_ready_event is None:
        return not shutdown_event.is_set()
    if bootstrap_ready_event.is_set():
        return True
    if shutdown_event.is_set():
        return False

    _log(system, "Waiting for swarm bootstrap gate")
    gate_task = asyncio.create_task(bootstrap_ready_event.wait())
    shutdown_task = asyncio.create_task(shutdown_event.wait())
    done, pending = await asyncio.wait(
        {gate_task, shutdown_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for pending_task in pending:
        pending_task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)

    if shutdown_task in done and shutdown_event.is_set() and not bootstrap_ready_event.is_set():
        _log(system, "Startup gate wait cancelled by shutdown")
        return False

    _log(system, "Startup gate released")
    return True


async def _run_gated_loop(
    system: str,
    shutdown_event: asyncio.Event,
    bootstrap_ready_event: asyncio.Event | None,
    factory: Callable[[], Awaitable[None]],
) -> None:
    """Run a loop only after the swarm startup gate opens."""
    if not await _wait_for_bootstrap_gate(system, bootstrap_ready_event, shutdown_event):
        return
    await factory()


async def _publish_swarm_runtime_snapshot(
    swarm: Any,
    *,
    source: str,
) -> None:
    """Best-effort runtime snapshot publish for the live orchestrator path."""
    publisher = getattr(swarm, "_publish_runtime_health_snapshot", None)
    if publisher is None:
        return
    try:
        await publisher(source=source)
    except Exception:
        logger.debug("Swarm runtime snapshot publish failed (%s)", source, exc_info=True)


async def _post_tick_runtime_bookkeeping(
    swarm: Any,
    *,
    status_timeout_s: float = 5.0,
    snapshot_timeout_s: float = 5.0,
) -> None:
    """Refresh operator-facing runtime state without blocking cadence.

    ``run_swarm_loop`` should never stop ticking because a secondary status
    read or snapshot write stalls. Time-bound both operations and fall back to
    the in-process liveness view when richer status collection is unavailable.
    """
    bounded_status_timeout = max(0.1, float(status_timeout_s))
    bounded_snapshot_timeout = max(0.1, float(snapshot_timeout_s))
    try:
        swarm_state = await asyncio.wait_for(
            swarm.status(),
            timeout=bounded_status_timeout,
        )
    except asyncio.TimeoutError:
        _log(
            "swarm",
            f"status refresh exceeded {bounded_status_timeout:.1f}s; continuing",
        )
        liveness = swarm.hot_path_liveness() if hasattr(swarm, "hot_path_liveness") else {}
        _update_runtime_health_state(
            agent_count=int(liveness.get("total_agents", 0) or 0),
            task_count=(
                int(liveness.get("tasks_pending", 0) or 0)
                + int(liveness.get("tasks_assigned", 0) or 0)
                + int(liveness.get("tasks_running", 0) or 0)
                + int(liveness.get("tasks_completed", 0) or 0)
                + int(liveness.get("tasks_failed", 0) or 0)
            ),
        )
    else:
        _update_runtime_health_state(
            agent_count=len(swarm_state.agents),
            task_count=(
                swarm_state.tasks_pending
                + swarm_state.tasks_running
                + swarm_state.tasks_completed
                + swarm_state.tasks_failed
            ),
        )

    try:
        await asyncio.wait_for(
            _publish_swarm_runtime_snapshot(
                swarm,
                source="swarm.tick_complete",
            ),
            timeout=bounded_snapshot_timeout,
        )
    except asyncio.TimeoutError:
        _log(
            "swarm",
            f"runtime snapshot publish exceeded {bounded_snapshot_timeout:.1f}s; continuing",
        )


async def _release_startup_gate_after_first_tick(
    swarm: Any,
    bootstrap_ready_event: asyncio.Event | None,
    *,
    shutdown_event: asyncio.Event | None = None,
    poll_interval_s: float = 0.1,
) -> str:
    """Open the startup gate only after the swarm reaches bootstrap complete.

    A completed first tick is not strong enough when the orchestrator times out
    after partial dispatch work; sibling boot tasks must stay blocked until the
    swarm has actually recorded ``bootstrap_complete``.
    """
    phase = await swarm.wait_until_bootstrap_ready()
    if phase in _BOOT_TERMINAL_PHASES:
        return phase

    wait_interval = max(0.01, float(poll_interval_s))
    while True:
        liveness = swarm.hot_path_liveness()
        phase = str(liveness.get("bootstrap_phase", "") or "").strip()
        if phase in _BOOT_TERMINAL_PHASES:
            return phase
        if phase == "bootstrap_complete":
            await _publish_swarm_runtime_snapshot(
                swarm,
                source="swarm.startup_gate_release",
            )
            if bootstrap_ready_event is not None:
                bootstrap_ready_event.set()
            return phase
        if shutdown_event is None:
            await asyncio.sleep(wait_interval)
            continue
        if await _wait_or_shutdown(shutdown_event, wait_interval):
            return phase


_EXECUTION_BEARING_MODES = {"persistent_agent"}
_EXECUTION_BEARING_SOURCES = {
    "agent_runner",
    "swarm.latent_gold",
    "research_rtn",
    "research_rtn_multi",
    "research_rtn_review",
    "research_rtn_synthesize",
    "research_rtn_verify",
}


def _mission_campaign_id(mission_title: str) -> str:
    norm = (mission_title or "").strip().lower()
    digest = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:10]
    return f"mission_{digest}"


def _artifact_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower()).strip("_")
    return slug[:48] or "artifact"


def _campaign_artifact_path(campaign_id: str) -> str:
    return f"~/.dharma/shared/campaigns/{campaign_id}.md"


def _campaign_task_artifact_path(campaign_id: str, title: str) -> str:
    return f"~/.dharma/shared/campaigns/{campaign_id}_{_artifact_slug(title)}.md"


def _recent_worker_call_count() -> int:
    try:
        from dharma_swarm.cost_tracker import summarize_costs

        rollup = summarize_costs(1.0)
        by_mode = rollup.get("by_execution_mode", {}) or {}
        by_source = rollup.get("by_source", {}) or {}
        mode_calls = sum(
            int((by_mode.get(mode) or {}).get("calls", 0))
            for mode in _EXECUTION_BEARING_MODES
        )
        source_calls = sum(
            int((by_source.get(source) or {}).get("calls", 0))
            for source in _EXECUTION_BEARING_SOURCES
        )
        return max(mode_calls, source_calls)
    except Exception:
        return 0


def _should_seed_startup_pressure(
    *,
    pending_count: int,
    running_count: int,
    primary_campaign_viable: bool,
    worker_calls_last_hour: int,
    has_mission_pressure: bool,
) -> tuple[bool, str]:
    in_flight = max(0, pending_count) + max(0, running_count)
    if in_flight == 0:
        return True, "empty_board"
    if worker_calls_last_hour <= 0 and not primary_campaign_viable:
        return True, "stagnation_dead_campaign"
    if not has_mission_pressure and not primary_campaign_viable:
        return True, "no_mission_pressure"
    return False, "steady_state"


def _campaign_has_board_presence(campaign: dict[str, Any] | None, tasks: list[Any]) -> bool:
    if not campaign:
        return False
    campaign_id = str(campaign.get("campaign_id") or "").strip()
    if not campaign_id:
        return False
    for task in tasks:
        metadata = getattr(task, "metadata", None)
        if isinstance(metadata, dict) and str(metadata.get("campaign_id") or "").strip() == campaign_id:
            return True
    return False


def _campaign_has_open_human_blocker(campaign: dict[str, Any] | None) -> bool:
    if not campaign:
        return False
    blockers = campaign.get("human_blocking")
    if not isinstance(blockers, list):
        return False
    terminal_statuses = {
        "abandoned",
        "canceled",
        "cancelled",
        "completed",
        "done",
        "resolved",
    }
    for blocker in blockers:
        if isinstance(blocker, str):
            if blocker.strip():
                return True
            continue
        if not isinstance(blocker, dict):
            continue
        status = str(blocker.get("status") or "").strip().lower()
        if status in terminal_statuses:
            continue
        if blocker:
            return True
    return False


def _task_matches_campaign(task: Any, campaign_id: str) -> bool:
    metadata = getattr(task, "metadata", None)
    if not isinstance(metadata, dict):
        return False
    return str(metadata.get("campaign_id") or "").strip() == campaign_id


def _campaign_has_live_board_presence(campaign: dict[str, Any] | None, tasks: list[Any]) -> bool:
    if not campaign:
        return False
    campaign_id = str(campaign.get("campaign_id") or "").strip()
    if not campaign_id:
        return False
    live_statuses = {
        TaskStatus.PENDING,
        TaskStatus.ASSIGNED,
        TaskStatus.RUNNING,
    }
    for task in tasks:
        if not _task_matches_campaign(task, campaign_id):
            continue
        if getattr(task, "status", None) in live_statuses:
            return True
    return False


def _task_is_recent(
    task: Any,
    *,
    hours: float,
    now: datetime | None = None,
) -> bool:
    ts = getattr(task, "updated_at", None) or getattr(task, "created_at", None)
    if not isinstance(ts, datetime):
        return False
    current = now or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (current - ts).total_seconds() <= max(0.0, hours) * 3600.0


def _campaign_has_recent_nurture_task(
    campaign: dict[str, Any] | None,
    tasks: list[Any],
    *,
    recent_hours: float = CAMPAIGN_NURTURE_RECENT_HOURS,
) -> bool:
    if not campaign:
        return False
    campaign_id = str(campaign.get("campaign_id") or "").strip()
    if not campaign_id:
        return False
    for task in tasks:
        if not _task_matches_campaign(task, campaign_id):
            continue
        metadata = getattr(task, "metadata", None)
        if not isinstance(metadata, dict):
            continue
        if str(metadata.get("created_via") or "") != "campaign_nurture":
            continue
        if _task_is_recent(task, hours=recent_hours):
            return True
    return False


def _task_has_mission_pressure(task: Any) -> bool:
    metadata = getattr(task, "metadata", None)
    if not isinstance(metadata, dict):
        return False
    if metadata.get("campaign_id") or metadata.get("artifact_required"):
        return True
    if metadata.get("seed_class") in {"startup_seed", "director_mission"}:
        return True
    if metadata.get("created_via") in {"manual_seed", "swarm.create_task"}:
        return True
    return False


def _campaign_is_stale(campaign: dict[str, Any] | None, *, max_age_hours: float = 2.0) -> bool:
    if not campaign:
        return True
    ts_raw = campaign.get("last_check_in") or campaign.get("created")
    if not ts_raw:
        return True
    try:
        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
    except Exception:
        return True
    age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0
    return age_hours > max_age_hours


def _campaign_nurture_reason(
    campaign: dict[str, Any],
    tasks: list[Any],
    *,
    stale_hours: float = CAMPAIGN_NURTURE_STALE_HOURS,
) -> str:
    is_primary = bool(campaign.get("primary"))
    stale = _campaign_is_stale(campaign, max_age_hours=stale_hours)
    live_presence = _campaign_has_live_board_presence(campaign, tasks)
    if not live_presence and _campaign_has_open_human_blocker(campaign):
        return ""
    if not live_presence and stale:
        return "stale_no_live_work"
    if not live_presence and is_primary:
        return "primary_no_live_work"
    return ""


def _build_campaign_nurture_specs(
    *,
    campaigns: list[dict[str, Any]],
    tasks: list[Any],
    stale_hours: float = CAMPAIGN_NURTURE_STALE_HOURS,
    recent_hours: float = CAMPAIGN_NURTURE_RECENT_HOURS,
    limit: int = CAMPAIGN_NURTURE_MAX_SPECS,
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    active_campaigns = [
        campaign for campaign in campaigns
        if isinstance(campaign, dict) and campaign.get("status", "active") == "active"
    ]
    primary_campaigns = [campaign for campaign in active_campaigns if campaign.get("primary")]
    candidate_campaigns = primary_campaigns[:1] if primary_campaigns else active_campaigns
    for campaign in candidate_campaigns:
        if not isinstance(campaign, dict):
            continue
        campaign_id = str(campaign.get("campaign_id") or "").strip()
        if not campaign_id:
            continue
        if _campaign_has_recent_nurture_task(
            campaign,
            tasks,
            recent_hours=recent_hours,
        ):
            continue
        reason = _campaign_nurture_reason(
            campaign,
            tasks,
            stale_hours=stale_hours,
        )
        if not reason:
            continue
        title = f"Campaign nurture: {campaign.get('title') or campaign_id}"
        artifact_path = str(campaign.get("artifact_path") or _campaign_artifact_path(campaign_id))
        markers = list(campaign.get("progress_markers") or [])
        last_marker = markers[-1] if markers else {}
        last_note = str(last_marker.get("note") or "").strip()
        description_lines = [
            f"Campaign: {campaign_id}",
            f"Title: {campaign.get('title') or campaign_id}",
            f"Domain: {campaign.get('domain') or 'unknown'}",
            f"Reason: {reason}.",
            "",
            "This active campaign has gone cold or lost live board pressure.",
            f"Write or refresh the binding campaign artifact at {artifact_path}.",
            "Include:",
            "1. current state and strongest real evidence",
            "2. blocking gap or decision that is preventing progress",
            "3. one concrete next external action or deliverable",
            "4. up to three bounded follow-on tasks if real branches emerge",
        ]
        if last_note:
            description_lines.extend(["", f"Last marker: {last_note[:280]}"])
        specs.append(
            {
                "title": title,
                "description": "\n".join(description_lines),
                "priority": TaskPriority.HIGH if campaign.get("primary") else TaskPriority.NORMAL,
                "created_by": "campaign_garden",
                "metadata": {
                    "campaign_id": campaign_id,
                    "campaign_support": True,
                    "artifact_required": True,
                    "seed_class": "campaign_nurture",
                    "created_via": "campaign_nurture",
                    "nurture_reason": reason,
                    "domain": campaign.get("domain") or "",
                    "target_artifact": artifact_path,
                },
            }
        )
        if len(specs) >= max(1, int(limit)):
            break
    return specs


async def _refresh_campaign_pressure(swarm: Any) -> int:
    """Keep durable campaigns warm by reseeding bounded board work when they cool off."""
    try:
        from dharma_swarm.campaigns import load_active

        campaigns = load_active(STATE_DIR / "meta")
        if not campaigns:
            return 0
        board = swarm._orchestrator._board
        tasks = await board.list_tasks(limit=400)
        specs = _build_campaign_nurture_specs(campaigns=campaigns, tasks=tasks)
        if not specs:
            return 0
        created = await _enqueue_startup_specs(swarm, specs)
        if created:
            _log("swarm", f"Campaign nurture: queued {created} task(s)")
        return created
    except Exception as exc:
        _log("swarm", f"Campaign nurture failed (non-fatal): {exc}")
        return 0


def _build_mission_seed_specs(
    *,
    mission_title: str,
    task_titles: list[str],
    existing_titles: set[str],
    campaign_id: str,
    domain: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for title in task_titles[:limit]:
        norm = (title or "").strip().lower()
        if not norm or norm in existing_titles:
            continue
        artifact_path = _campaign_task_artifact_path(campaign_id, title)
        specs.append(
            {
                "title": title,
                "description": (
                    f"Mission: {mission_title}.\n"
                    f"Campaign: {campaign_id}.\n"
                    f"Write the deliverable to {artifact_path}.\n"
                    "Produce a durable artifact in ~/.dharma/shared/ or the repo. "
                    "Prefer evidence-backed output over coordination churn."
                ),
                "priority": TaskPriority.HIGH,
                "created_by": "director",
                "metadata": {
                    "campaign_id": campaign_id,
                    "campaign_support": True,
                    "domain": domain,
                    "artifact_required": True,
                    "mission_title": mission_title,
                    "seed_class": "director_mission",
                    "target_artifact": artifact_path,
                },
            }
        )
    return specs


async def _enqueue_startup_specs(swarm: Any, specs: list[dict[str, Any]]) -> int:
    """Create startup tasks through the swarm API when available.

    The raw board path bypasses task enrichment used elsewhere in the daemon.
    Startup pressure should flow through the same batch-creation seam as other
    meaningful swarm work so metadata, trace IDs, and gate checks stay aligned.
    """
    if not specs:
        return 0
    create_task_batch = getattr(swarm, "create_task_batch", None)
    if callable(create_task_batch):
        created = await create_task_batch(specs)
        return len(created or [])
    board = swarm._orchestrator._board
    created = await board.create_batch(specs)
    return len(created or [])


async def _seed_startup_pressure(swarm: Any) -> None:
    """Assert mission-bearing pressure when the daemon boots into stagnation."""
    try:
        from dharma_swarm.campaigns import active_primary, create_campaign
        from dharma_swarm.domain_classify import THEME_TO_DOMAIN, classify_text
        from dharma_swarm.mission_contract import load_active_mission_state
        from dharma_swarm.startup_crew import SEED_TASKS

        board = swarm._orchestrator._board
        board_stats = await board.stats()
        pending = int(board_stats.get("pending", 0) or 0)
        running = int(board_stats.get("running", 0) or 0)
        existing_tasks = await board.list_tasks(limit=200)
        primary_campaign = active_primary(STATE_DIR / "meta")
        worker_calls_last_hour = _recent_worker_call_count()
        has_mission_pressure = any(_task_has_mission_pressure(task) for task in existing_tasks)
        primary_campaign_viable = (
            primary_campaign is not None
            and (
                _campaign_has_open_human_blocker(primary_campaign)
                or (
                    not _campaign_is_stale(primary_campaign)
                    and _campaign_has_board_presence(primary_campaign, existing_tasks)
                )
            )
        )
        _log(
            "swarm",
            "Startup seed check: "
            f"pending={pending} running={running} existing={len(existing_tasks)} "
            f"worker_calls_1h={worker_calls_last_hour} "
            f"primary_campaign={'yes' if primary_campaign else 'no'} "
            f"primary_viable={'yes' if primary_campaign_viable else 'no'} "
            f"mission_pressure={'yes' if has_mission_pressure else 'no'}",
        )
        should_seed, reason = _should_seed_startup_pressure(
            pending_count=pending,
            running_count=running,
            primary_campaign_viable=primary_campaign_viable,
            worker_calls_last_hour=worker_calls_last_hour,
            has_mission_pressure=has_mission_pressure,
        )
        if not should_seed:
            _log("swarm", f"Startup seed check: steady, skip ({reason})")
            return
        _log("swarm", f"Startup seed check: seeding triggered ({reason})")

        existing_titles = {
            (task.title or "").strip().lower()
            for task in existing_tasks
            if (task.title or "").strip()
        }

        mission_artifact = load_active_mission_state(state_dir=STATE_DIR)
        if mission_artifact and mission_artifact.state.task_titles:
            mission = mission_artifact.state
            campaign_id = _mission_campaign_id(mission.mission_title)
            domain = THEME_TO_DOMAIN.get(
                (mission.mission_theme or "").strip().lower(),
                classify_text(f"{mission.mission_title}\n{mission.mission_thesis}"),
            )
            create_campaign(
                campaign_id=campaign_id,
                domain=domain,
                pinned_agents=[],
                title=mission.mission_title,
                success_criteria=mission.mission_thesis,
                source="director",
                primary=True,
                artifact_path=_campaign_artifact_path(campaign_id),
                meta_dir=STATE_DIR / "meta",
            )
            specs = _build_mission_seed_specs(
                mission_title=mission.mission_title,
                task_titles=list(mission.task_titles),
                existing_titles=existing_titles,
                campaign_id=campaign_id,
                domain=domain,
            )
            if specs:
                created_count = await _enqueue_startup_specs(swarm, specs)
                _log(
                    "swarm",
                    f"Startup seeding ({reason}): queued {created_count} director tasks for '{mission.mission_title}'",
                )
                return
            _log(
                "swarm",
                f"Startup seeding ({reason}): director mission already represented on board",
            )
            return

        fallback_campaign_id = "startup_world_facing"
        create_campaign(
            campaign_id=fallback_campaign_id,
            domain="artifact_publication",
            pinned_agents=[],
            title="Startup World-Facing Pressure",
            success_criteria="Convert daemon boot into durable world-facing artifacts.",
            source="startup_seed",
            primary=True,
            artifact_path=_campaign_artifact_path(fallback_campaign_id),
            meta_dir=STATE_DIR / "meta",
        )

        seed_specs: list[dict[str, Any]] = []
        for spec in SEED_TASKS[:3]:
            title = str(spec.get("title", "") or "").strip()
            if not title or title.lower() in existing_titles:
                continue
            artifact_path = _campaign_task_artifact_path(fallback_campaign_id, title)
            description = str(spec.get("description", "") or "").strip()
            seed_specs.append(
                {
                    "title": title,
                    "description": (
                        f"{description}\n\n"
                        f"Write the deliverable to {artifact_path} before marking the task complete."
                    ).strip(),
                    "priority": spec.get("priority", TaskPriority.HIGH),
                    "created_by": "seed_task",
                    "metadata": {
                        "campaign_id": fallback_campaign_id,
                        "campaign_support": True,
                        "artifact_required": True,
                        "seed_class": "startup_seed",
                        "domain": "artifact_publication",
                        "target_artifact": artifact_path,
                    },
                }
            )
        if seed_specs:
            created_count = await _enqueue_startup_specs(swarm, seed_specs)
            _log(
                "swarm",
                f"Startup seeding ({reason}): queued {created_count} fallback seed tasks",
            )
        else:
            _log("swarm", f"Startup seeding ({reason}): no fallback seed specs survived dedupe")
    except Exception as exc:
        _log("swarm", f"Startup seeding failed (non-fatal): {exc}")


async def _delayed_startup_reseed(
    swarm: Any,
    shutdown_event: asyncio.Event,
    delay_seconds: float = 15.0,
) -> None:
    """Retry startup seeding after deferred startup settles."""
    if await _wait_or_shutdown(shutdown_event, delay_seconds):
        return
    await _seed_startup_pressure(swarm)


async def _safe_seed_startup_pressure(
    swarm: Any,
    *,
    timeout_s: float | None = None,
) -> bool:
    timeout = max(1.0, float(timeout_s if timeout_s is not None else STARTUP_SEED_TIMEOUT_S))
    try:
        await asyncio.wait_for(_seed_startup_pressure(swarm), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        _log(
            "swarm",
            f"Startup seed check timed out after {timeout:.1f}s; continuing to first tick",
        )
        return False


_BOOT_READY_PHASES = frozenset(
    {"bootstrap_ready", "bootstrap_complete", "steady_state"}
)
_BOOT_TERMINAL_PHASES = frozenset({"bootstrap_failed"})
BOOT_STALL_THRESHOLD_DEFAULT_S = max(120.0, float(SWARM_TICK) * 4.0)
LIVENESS_WATCHDOG_INTERVAL_S = max(5.0, min(float(SWARM_TICK), 20.0))


def _read_tick_budget_seconds() -> float:
    """Read DHARMA_TICK_BUDGET_S env; fallback to min(180, 3*SWARM_TICK), floor 5s.

    The tick budget is the outer wall-clock wrapper around ``swarm.tick()``;
    a tick that exceeds it is cancelled so the event loop cannot silently pin
    forever on a single bad tick.
    """
    raw = os.environ.get("DHARMA_TICK_BUDGET_S", "").strip()
    try:
        value = float(raw) if raw else 0.0
    except ValueError:
        value = 0.0
    if value <= 0:
        value = min(180.0, float(SWARM_TICK) * 3.0)
    return max(5.0, value)


async def _invoke_swarm_tick(swarm: Any, timeout_s: float) -> dict[str, Any]:
    """Call ``swarm.tick()`` under a wall-clock budget.

    Raises ``asyncio.TimeoutError`` if the tick exceeds ``timeout_s`` — the
    caller's existing ``except Exception`` branch is expected to log and feed
    the circuit breaker.
    """
    return await asyncio.wait_for(swarm.tick(), timeout=timeout_s)


def _evaluate_boot_stall(
    liveness: dict[str, Any],
    *,
    threshold_s: float,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Classify whether the hot path is boot-stalled.

    Returns ``("boot_stall", reason)`` if the bootstrap has been running past
    ``threshold_s`` without reaching a ready phase; returns ``("", "")``
    otherwise. The hot path itself self-declares via this classifier so that
    downstream observers do not need to reconstruct the stall from timestamps.
    """
    phase = str(liveness.get("bootstrap_phase", "") or "").strip()
    if phase in _BOOT_READY_PHASES or phase in _BOOT_TERMINAL_PHASES:
        return "", ""
    started = parse_iso_datetime(liveness.get("bootstrap_started_at"))
    if started is None:
        return "", ""
    current = now or datetime.now(timezone.utc)
    elapsed = (current - started).total_seconds()
    if elapsed < threshold_s:
        return "", ""
    return (
        "boot_stall",
        f"bootstrap phase '{phase or 'unknown'}' exceeded {threshold_s:.0f}s "
        f"budget ({elapsed:.0f}s elapsed)",
    )


async def run_swarm_liveness_watchdog(
    swarm: Any,
    shutdown_event: asyncio.Event,
    *,
    interval_s: float = LIVENESS_WATCHDOG_INTERVAL_S,
    boot_stall_threshold_s: float = BOOT_STALL_THRESHOLD_DEFAULT_S,
) -> None:
    """Hot-path liveness watchdog.

    Runs in the same event loop as the tick loop so that if the loop wedges,
    the watchdog cannot publish either — making staleness in
    ``dgc_health.json`` / ``meta/swarm_liveness.json`` the truthful signal.

    Does two things each iteration:

    1. Evaluates whether the bootstrap has exceeded its budget and, if so,
       marks ``boot_stall`` on the swarm's in-process liveness state.
    2. Calls ``_publish_runtime_health_snapshot`` so both canonical operator
       artifacts (``dgc_health.json`` and ``meta/swarm_liveness.json``) are
       refreshed even when no tick has ever fired.
    """
    _log(
        "watchdog",
        f"Liveness watchdog starting (interval={interval_s:.0f}s, "
        f"boot_budget={boot_stall_threshold_s:.0f}s)",
    )
    last_logged_state: str | None = None
    while not shutdown_event.is_set():
        try:
            liveness = swarm.hot_path_liveness()
            existing_stall = str(liveness.get("stall_state", "") or "none") or "none"
            classified, reason = _evaluate_boot_stall(
                liveness, threshold_s=boot_stall_threshold_s,
            )
            if classified == "boot_stall":
                if existing_stall != "boot_stall":
                    swarm._mark_liveness_stall("boot_stall", reason)
                if last_logged_state != "boot_stall":
                    _log("watchdog", f"BOOT STALL detected: {reason}")
                    last_logged_state = "boot_stall"
            elif existing_stall == "boot_stall":
                swarm._clear_liveness_stall()
                if last_logged_state != "cleared":
                    _log("watchdog", "Boot stall cleared — bootstrap progressed")
                    last_logged_state = "cleared"
            else:
                last_logged_state = existing_stall or "none"
            try:
                await swarm._publish_runtime_health_snapshot(
                    source="swarm.liveness_watchdog",
                )
            except Exception:
                logger.debug(
                    "Liveness watchdog: snapshot publish failed", exc_info=True,
                )
        except Exception:
            logger.debug("Liveness watchdog iteration failed", exc_info=True)
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval_s)
        except asyncio.TimeoutError:
            pass
    _log("watchdog", "Liveness watchdog shutting down")


async def run_swarm_loop(
    shutdown_event: asyncio.Event,
    signal_bus: "Any | None" = None,
    supervisor: "Any | None" = None,
    bootstrap_ready_event: asyncio.Event | None = None,
) -> None:
    """Primary loop: SwarmManager.tick() -- the ONE control path.

    Strange Loop Phase 0: unified tick. No more split brain.
    """
    from dharma_swarm.daemon_config import DaemonConfig
    from dharma_swarm.swarm import SwarmManager

    _log("swarm", f"Initializing (tick={SWARM_TICK}s, max_daily={MAX_DAILY})...")

    cfg = DaemonConfig()
    cfg.heartbeat_interval = float(SWARM_TICK)
    cfg.max_daily_contributions = MAX_DAILY

    swarm = SwarmManager(state_dir=str(STATE_DIR), daemon_config=cfg)
    await swarm.init()
    max_tick_budget_s = _read_tick_budget_seconds()
    _log(
        "swarm",
        f"Tick budget enforced at {max_tick_budget_s:.0f}s per tick",
    )
    watchdog_task = asyncio.create_task(
        run_swarm_liveness_watchdog(swarm, shutdown_event),
        name="swarm-liveness-watchdog",
    )

    # MessageBus for instinct signal consumption
    from dharma_swarm.message_bus import MessageBus as _MBus
    _instinct_bus = _MBus(STATE_DIR / "db" / "messages.db")
    await _instinct_bus.init_db()

    _update_runtime_health_state(
        agent_count=0,
        task_count=0,
    )
    _log(
        "swarm",
        f"Ready: core runtime initialized, bootstrap_phase={swarm.hot_path_liveness().get('bootstrap_phase', 'unknown')}, "
        f"thread={swarm.current_thread}",
    )

    startup_gate_task: asyncio.Task[Any] | None = None
    if bootstrap_ready_event is not None:
        async def _signal_bootstrap_ready() -> None:
            phase = await _release_startup_gate_after_first_tick(
                swarm,
                bootstrap_ready_event,
                shutdown_event=shutdown_event,
            )
            if bootstrap_ready_event.is_set():
                _log("swarm", f"Startup gate released after first tick (phase={phase})")
            else:
                _log("swarm", f"Startup gate blocked at phase={phase}")

        startup_gate_task = asyncio.create_task(
            _signal_bootstrap_ready(),
            name="swarm-startup-gate",
        )

    await _safe_seed_startup_pressure(swarm)
    asyncio.create_task(_delayed_startup_reseed(swarm, shutdown_event))
    last_campaign_nurture_at = 0.0

    try:
        while not shutdown_event.is_set():
            try:
                # Drain signal bus before tick -- respond to inter-loop signals
                if signal_bus is not None:
                    anomaly_signals = signal_bus.drain(["ANOMALY_DETECTED"])
                    if anomaly_signals:
                        _log("swarm", f"Signal bus: {len(anomaly_signals)} anomaly signal(s)")

                # Drain skill bridge inbox — route Claude Code skill outputs to swarm
                try:
                    from dharma_swarm.skill_bridge import SkillBridge
                    _bridge = SkillBridge()
                    _bridge_entries = _bridge.drain_inbox()
                    if _bridge_entries:
                        _bridge_counts = _bridge.process_entries(_bridge_entries)
                        _log("swarm", f"Skill bridge: processed {sum(_bridge_counts.values())} entries ({_bridge_counts})")
                except Exception:
                    pass  # Skill bridge is best-effort

                # Drain instinct signals — negative patterns inform task quality
                try:
                    from dharma_swarm.signal_bus import SIGNAL_ECC_INSTINCT
                    instinct_events = await _instinct_bus.consume_events(
                        SIGNAL_ECC_INSTINCT, limit=10,
                    )
                    negatives = [
                        e for e in instinct_events
                        if e.get("payload", {}).get("signal") == "negative"
                    ]
                    if negatives:
                        _log("swarm", f"Instinct: {len(negatives)} negative pattern(s) detected")
                        for neg in negatives[:3]:
                            p = neg.get("payload", {})
                            _log("swarm", f"  ↳ {p.get('pattern_type', '?')}: {p.get('detail', '')[:60]}")
                except Exception:
                    logger.debug("Swarm: instinct drain failed", exc_info=True)

                activity = await _invoke_swarm_tick(swarm, max_tick_budget_s)

                # Liveness watchdog: record healthy tick + check all loops
                if supervisor is not None:
                    supervisor.record_tick("swarm")
                    alerts = supervisor.tick()
                    for alert in alerts:
                        _log("watchdog", f"{alert.severity.upper()} [{alert.loop_name}]: "
                             f"{alert.message} → {alert.intervention}")

                await _post_tick_runtime_bookkeeping(swarm)

                phase = str(
                    swarm.hot_path_liveness().get("bootstrap_phase", "") or ""
                ).strip()
                now_monotonic = time.monotonic()
                if (
                    phase == "bootstrap_complete"
                    and (now_monotonic - last_campaign_nurture_at) >= CAMPAIGN_NURTURE_INTERVAL_S
                ):
                    last_campaign_nurture_at = now_monotonic
                    try:
                        await asyncio.wait_for(
                            _refresh_campaign_pressure(swarm),
                            timeout=10.0,
                        )
                    except asyncio.TimeoutError:
                        _log("swarm", "Campaign nurture exceeded 10.0s; continuing")

                if activity.get("paused"):
                    _log("swarm", "Paused (.PAUSE file)")
                    await asyncio.sleep(30)
                    continue
                if activity.get("circuit_broken"):
                    _log("swarm", "Circuit breaker tripped, waiting...")
                    await asyncio.sleep(60)
                    continue

                dispatched = activity.get("dispatched", 0)
                settled = activity.get("settled", 0)
                rescued = activity.get("rescued", 0)
                if dispatched or settled or rescued:
                    _log("swarm", f"tick: dispatched={dispatched} settled={settled} rescued={rescued}")

                cfg.circuit_breaker.record_success()

            except asyncio.TimeoutError:
                _log(
                    "swarm",
                    f"tick exceeded {max_tick_budget_s:.0f}s budget — cancelled",
                )
                cfg.circuit_breaker.record_failure()
            except Exception as e:
                _log("swarm", f"tick error: {e}")
                cfg.circuit_breaker.record_failure()

            await asyncio.sleep(SWARM_TICK)
    finally:
        if startup_gate_task is not None:
            startup_gate_task.cancel()
            try:
                await startup_gate_task
            except (asyncio.CancelledError, Exception):
                pass
        watchdog_task.cancel()
        try:
            await watchdog_task
        except (asyncio.CancelledError, Exception):
            pass
        await swarm.shutdown()
        _log("swarm", "Shutdown complete")


async def run_pulse_loop(shutdown_event: asyncio.Event) -> None:
    """Pulse heartbeat — runs claude -p with thread rotation.

    Skips if running inside a Claude Code session (nested sessions not allowed).
    """
    if os.environ.get("CLAUDECODE"):
        _log("pulse", "Skipping — running inside Claude Code session (nested not allowed)")
        return

    from dharma_swarm.pulse import pulse
    from dharma_swarm.daemon_config import DaemonConfig

    _log("pulse", f"Starting (interval={PULSE_INTERVAL}s)")

    cfg = DaemonConfig()
    cfg.heartbeat_interval = float(PULSE_INTERVAL)
    cfg.max_daily_contributions = MAX_DAILY
    daily_count = 0

    while not shutdown_event.is_set():
        if daily_count >= MAX_DAILY:
            _log("pulse", f"Daily limit ({MAX_DAILY}) reached")
            await asyncio.sleep(3600)
            continue

        try:
            _log("pulse", f"Pulsing... (#{daily_count + 1})")
            # Run pulse in thread to not block event loop (it calls subprocess)
            result = await asyncio.to_thread(pulse, cfg)
            short = result[:120].replace("\n", " ")
            _log("pulse", f"Result: {short}")

            if not result.startswith(("PAUSED", "QUIET", "CIRCUIT", "TELOS")):
                daily_count += 1
        except Exception as e:
            _log("pulse", f"Error: {e}")

        await asyncio.sleep(PULSE_INTERVAL)


async def run_evolution_loop(shutdown_event: asyncio.Event) -> None:
    """Periodic evolution cycles — propose, gate, evaluate, archive."""
    from dharma_swarm.evolution import DarwinEngine, CycleResult
    from dharma_swarm.meta_evolution import MetaEvolutionEngine

    _log("evolution", f"Starting (interval={EVOLUTION_INTERVAL}s)")
    await asyncio.sleep(30)  # Let swarm init first

    evo_dir = STATE_DIR / "evolution"
    traces_dir = STATE_DIR / "traces"

    engine = DarwinEngine(
        archive_path=evo_dir / "archive.jsonl",
        traces_path=traces_dir,
        predictor_path=evo_dir / "predictor_data.jsonl",
    )
    await engine.init()

    # Meta-evolution: adapts hyperparameters when object-level fitness stalls
    meta_engine = MetaEvolutionEngine(
        engine,
        meta_archive_path=evo_dir / "meta_archive.jsonl",
        n_object_cycles_per_meta=2,
        auto_apply=True,
    )

    # Connect to MessageBus for durable fitness event consumption
    from dharma_swarm.message_bus import MessageBus as _MBus
    db_dir = STATE_DIR / "db"
    _bus = _MBus(db_dir / "messages.db")
    await _bus.init_db()

    # Subscribe to orchestrator.lifecycle — track task throughput for fitness context
    try:
        await _bus.subscribe("evolution_loop", "orchestrator.lifecycle")
    except Exception:
        logger.debug("Evolution: lifecycle subscription failed", exc_info=True)

    # Source files for evolution proposals — core modules only
    _src_root = Path(__file__).resolve().parent
    _EVOLUTION_TARGETS = [
        "swarm.py", "orchestrator.py", "agent_runner.py", "providers.py",
        "evolution.py", "dharma_kernel.py", "telos_gates.py",
        "thinkodynamic_director.py",
    ]
    cycle_count = 0

    while not shutdown_event.is_set():
        try:
            count = len(engine.archive._entries) if engine.archive else 0
            _log("evolution", f"Archive: {count} entries")

            # Consume durable fitness events from MessageBus
            fitness_events = []
            try:
                fitness_events = await _bus.consume_events("AGENT_FITNESS", limit=50)
                if fitness_events:
                    _log("evolution", f"Consumed {len(fitness_events)} fitness events from bus")
            except Exception as exc:
                _log("evolution", f"Bus consume error: {exc}")

            # Drain lifecycle events — task completion throughput for fitness context
            completions = 0
            try:
                lifecycle_events = await _consume_event_backlog(
                    _bus,
                    "AGENT_LIFECYCLE_COMPLETED",
                    batch_size=500,
                    max_events=5000,
                )
                completions = len(lifecycle_events)
                if completions:
                    _log("evolution", f"Lifecycle: {completions} task completion(s) since last cycle")
            except Exception:
                logger.debug("Evolution: lifecycle drain failed", exc_info=True)

            # Check fitness trend
            avg_fitness = 0.0
            try:
                trend = await engine.get_fitness_trend(limit=5)
                if trend:
                    avg_fitness = sum(f for _, f in trend) / len(trend)
                    _log("evolution", f"Fitness trend (last {len(trend)}): avg={avg_fitness:.3f}")
            except Exception:
                logger.debug("Fitness trend read failed", exc_info=True)

            # ── ACTIVE EVOLUTION: run cycle + meta-adaptation ──
            cycle_count += 1
            meta_observation: CycleResult | None = None

            # Extract live fitness from AGENT_FITNESS event payloads and persist
            live_fitness_scores: list[float] = []
            for ev in fitness_events:
                payload = ev.get("payload") if isinstance(ev, dict) else {}
                if isinstance(payload, dict):
                    # agent_runner emits swabhaav_ratio as the primary score
                    score = (
                        payload.get("swabhaav_ratio")
                        or payload.get("fitness_score")
                        or payload.get("composite")
                    )
                    if isinstance(score, (int, float)) and score > 0:
                        live_fitness_scores.append(float(score))
                        # Persist to archive so get_fitness_trend() works
                        try:
                            await engine.record_fitness_observation(
                                agent_name=payload.get("agent", "unknown"),
                                fitness_score=float(score),
                                task_id=payload.get("task_id"),
                            )
                        except Exception:
                            logger.debug("Fitness archival failed", exc_info=True)
            if live_fitness_scores:
                _log("evolution", f"Live fitness from {len(live_fitness_scores)} agents: "
                     f"avg={sum(live_fitness_scores)/len(live_fitness_scores):.3f} "
                     f"max={max(live_fitness_scores):.3f}")

            # Stage one meta-evolution observation per loop cycle. Live fitness
            # is useful context, but a real Darwin cycle result supersedes it.
            if avg_fitness > 0 or fitness_events:
                if live_fitness_scores:
                    best_fitness = max(live_fitness_scores)
                else:
                    best_fitness = avg_fitness if avg_fitness > 0 else 0.0
                meta_observation = CycleResult(
                    cycle_id=f"orch-evo-{cycle_count}",
                    best_fitness=best_fitness,
                    proposals_submitted=len(fitness_events),
                )

            # Drain active inference prediction errors — bias evolution toward high-error areas
            try:
                from dharma_swarm.signal_bus import SignalBus as _EvSB
                _ev_bus = _EvSB.get()
                pe_signals = _ev_bus.drain(["ACTIVE_INFERENCE_PREDICTION_ERROR"])
                if pe_signals:
                    high_error = sorted(pe_signals, key=lambda s: abs(s.get("error", 0)), reverse=True)[:3]
                    error_summary = ", ".join(f"{s.get('agent', '?')}:{s.get('error', 0):.3f}" for s in high_error)
                    _log("evolution", f"Prediction errors from {len(pe_signals)} observations: {error_summary}")
            except Exception:
                pass

            # Read health anomalies from file (written by health loop, avoids signal bus contention)
            try:
                import json as _ej
                _anomaly_file = STATE_DIR / "health" / "latest_anomalies.json"
                if _anomaly_file.exists():
                    _anomaly_data = _ej.loads(_anomaly_file.read_text())
                    if _anomaly_data:
                        _anomaly_types = [a.get("type", "?") for a in _anomaly_data]
                        _log("evolution", f"Health context: {', '.join(_anomaly_types)}")
            except Exception:
                pass

            # --- EVAL VERDICT GATE: check overnight verdict before evolving ---
            _evo_allowed = True
            try:
                import json as _vj
                _verdict_dir = STATE_DIR / "overnight" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
                _verdict_file = _verdict_dir / "verdict.json"
                if _verdict_file.exists():
                    _vdata = _vj.loads(_verdict_file.read_text())
                    _v = _vdata.get("verdict", "")
                    if _v == "rollback":
                        _evo_allowed = False
                        _log("evolution", "PAUSED: overnight ROLLBACK verdict — skipping auto_evolve")
                    elif _v == "hold":
                        # On HOLD, only allow shadow mode
                        _log("evolution", "CONSTRAINED: overnight HOLD verdict — forcing shadow mode")
            except Exception:
                pass

            # Auto-evolve: propose improvements via LLM every 3rd cycle
            # Shadow mode controlled by env var (default: ON for safety)
            # Set DHARMA_EVOLUTION_SHADOW=0 + DGC_AUTONOMY_LEVEL>=2 for real mutation
            if cycle_count % 3 == 0 and _evo_allowed:
                try:
                    from dharma_swarm.providers import OpenRouterProvider
                    import os as _evo_os
                    if _evo_os.environ.get("OPENROUTER_API_KEY"):
                        provider = OpenRouterProvider()
                        # Pick 2 random source files per cycle to limit LLM cost
                        import random as _evo_rng
                        targets = [
                            _src_root / f for f in _EVOLUTION_TARGETS
                            if (_src_root / f).exists()
                        ]
                        if targets:
                            selected = _evo_rng.sample(targets, min(2, len(targets)))

                            # Determine shadow mode: real mutation requires explicit opt-in
                            _shadow = _evo_os.environ.get("DHARMA_EVOLUTION_SHADOW", "1") != "0"
                            _autonomy = int(_evo_os.environ.get("DGC_AUTONOMY_LEVEL", "1"))
                            if not _shadow and _autonomy < 2:
                                _shadow = True  # Autonomy too low for real mutation
                                _log("evolution", "Shadow forced: DGC_AUTONOMY_LEVEL < 2")

                            # Eval verdict override: HOLD forces shadow mode
                            try:
                                if _verdict_file.exists():
                                    _vd2 = _vj.loads(_verdict_file.read_text())
                                    if _vd2.get("verdict") == "hold" and not _shadow:
                                        _shadow = True
                                        _log("evolution", "Shadow forced: overnight HOLD verdict")
                            except Exception:
                                pass

                            # Merge any pending proposals from consolidation/skill bridge
                            _pending = engine.load_pending_proposals()
                            if _pending:
                                _log("evolution", f"Loaded {len(_pending)} pending proposals from consolidation/bridge")

                            mode_label = "shadow" if _shadow else "LIVE"
                            _log("evolution", f"Auto-evolve ({mode_label}): {[s.name for s in selected]}")

                            # Create darwin branch for live mutation
                            if not _shadow:
                                _branch = f"darwin/cycle-{cycle_count}"
                                _br_proc = await asyncio.create_subprocess_exec(
                                    "git", "checkout", "-b", _branch,
                                    cwd=str(_src_root.parent),
                                    stdout=asyncio.subprocess.PIPE,
                                    stderr=asyncio.subprocess.PIPE,
                                )
                                await _br_proc.communicate()
                                _log("evolution", f"Created branch {_branch}")

                            result = await engine.auto_evolve(
                                provider=provider,
                                source_files=selected,
                                shadow=_shadow,
                                timeout=30.0,
                                context=f"Fitness avg={avg_fitness:.3f}, completions={completions}",
                            )
                            _log(
                                "evolution",
                                f"Auto-evolve result ({mode_label}): fitness={result.best_fitness:.3f}, "
                                f"submitted={result.proposals_submitted}, "
                                f"gated={result.proposals_gated}",
                            )

                            # For live mode: commit worthy proposals, then return to main branch
                            if not _shadow and result.proposals_archived > 0:
                                _committed = 0
                                _best_entries = await engine.archive.get_best(n=3)
                                for entry in _best_entries:
                                    # Build a Proposal from ArchiveEntry for commit_if_worthy
                                    from dharma_swarm.evolution import Proposal
                                    _p = Proposal(
                                        id=entry.id,
                                        component=entry.component,
                                        change_type=entry.change_type,
                                        description=entry.description,
                                        diff=entry.diff,
                                        actual_fitness=entry.fitness,
                                    )
                                    sha = await engine.commit_if_worthy(_p)
                                    if sha:
                                        _committed += 1
                                        _log("evolution", f"Committed {sha[:8]} for {entry.component}")
                                if _committed == 0:
                                    # No commits — delete the branch
                                    _del_proc = await asyncio.create_subprocess_exec(
                                        "git", "checkout", "-",
                                        cwd=str(_src_root.parent),
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE,
                                    )
                                    await _del_proc.communicate()
                                    await asyncio.create_subprocess_exec(
                                        "git", "branch", "-D", _branch,
                                        cwd=str(_src_root.parent),
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE,
                                    )
                                else:
                                    # Return to previous branch, keep darwin branch
                                    await asyncio.create_subprocess_exec(
                                        "git", "checkout", "-",
                                        cwd=str(_src_root.parent),
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE,
                                    )
                                _log("evolution", f"Live cycle: {_committed} commits on {_branch}")

                            meta_observation = result
                    else:
                        _log("evolution", "Auto-evolve skipped: OPENROUTER_API_KEY not set")
                except Exception as exc:
                    _log("evolution", f"Auto-evolve error: {exc}")

            if meta_observation is not None:
                meta_result = meta_engine.observe_cycle_result(meta_observation)
                if meta_result is not None:
                    if meta_result.evolved_parameters:
                        _log(
                            "evolution",
                            f"Meta-evolution adapted parameters "
                            f"(meta_fitness={meta_result.meta_fitness:.3f}, "
                            f"applied={meta_result.applied_parameters})",
                        )
                    else:
                        _log(
                            "evolution",
                            f"Meta-evolution: no adaptation needed "
                            f"(meta_fitness={meta_result.meta_fitness:.3f})",
                        )

            # Bus metrics for observability
            try:
                stats = await _bus.event_stats()
                if stats.get("queued", 0) > 0:
                    _log("evolution", f"Bus: {stats['queued']} queued, {stats['consumed']} consumed")
            except Exception:
                logger.debug("Bus event stats failed", exc_info=True)

        except Exception as e:
            _log("evolution", f"Error: {e}")

        await asyncio.sleep(EVOLUTION_INTERVAL)


async def run_health_loop(shutdown_event: asyncio.Event) -> None:
    """Health monitoring — detect anomalies, report status."""
    _log("health", f"Starting (interval={HEALTH_INTERVAL}s)")
    await asyncio.sleep(15)  # Let swarm init first

    # Hoist heavy objects out of the loop
    from dharma_swarm.monitor import SystemMonitor
    from dharma_swarm.traces import TraceStore

    traces_dir = STATE_DIR / "traces"
    store = TraceStore(base_path=traces_dir)
    await store.init()
    monitor = SystemMonitor(trace_store=store)

    # Import signal bus for WITNESS_AUDIT drain
    from dharma_swarm.signal_bus import SignalBus
    signal_bus = SignalBus.get()
    last_swarm_liveness_key: tuple[str, str, str] | None = None

    while not shutdown_event.is_set():
        try:
            # Drain WITNESS_AUDIT signals — close the S3* feedback loop
            witness_signals = signal_bus.drain(["WITNESS_AUDIT"])
            for ws in witness_signals:
                criticals = ws.get("severities", {}).get("critical", 0)
                warnings = ws.get("severities", {}).get("warning", 0)
                total = ws.get("total_findings", 0)
                if criticals:
                    _log("health", f"WITNESS: {criticals} critical finding(s) in audit cycle {ws.get('cycle', '?')}")
                elif warnings:
                    _log("health", f"WITNESS: {warnings} warning(s), {total} total in cycle {ws.get('cycle', '?')}")

            anomalies = await monitor.detect_anomalies()
            if anomalies:
                for a in anomalies[:3]:
                    _log("health", f"ANOMALY: {a.anomaly_type} severity={a.severity} — {a.description[:80]}")
                # Emit to signal bus so swarm loop can drain
                for a in anomalies[:5]:
                    signal_bus.emit({
                        "type": "ANOMALY_DETECTED",
                        "anomaly_type": a.anomaly_type,
                        "severity": a.severity,
                        "description": a.description[:200],
                    })
                # Write anomaly file for evolution loop (avoids signal bus contention)
                anomaly_dir = STATE_DIR / "health"
                anomaly_dir.mkdir(parents=True, exist_ok=True)
                import json as _hj
                summary = [{"type": a.anomaly_type, "severity": a.severity} for a in anomalies[:10]]
                (anomaly_dir / "latest_anomalies.json").write_text(_hj.dumps(summary))
            else:
                # Quick summary
                pid_file = STATE_DIR / "daemon.pid"
                pulse_log = freshest_pulse_log_path(STATE_DIR)
                status_parts = []
                if pid_file.exists():
                    try:
                        pid = int(pid_file.read_text().strip())
                        os.kill(pid, 0)
                        status_parts.append(f"daemon=PID:{pid}")
                    except (ValueError, OSError):
                        status_parts.append("daemon=dead")
                if pulse_log is not None and pulse_log.exists():
                    lines = pulse_log.read_text().split("--- PULSE @")
                    status_parts.append(f"pulses={len(lines)-1}")
                _log("health", f"OK ({', '.join(status_parts) or 'nominal'})")

            liveness_snapshot = dgc_health_snapshot_summary(STATE_DIR)
            liveness_payload = _swarm_liveness_watch_payload(liveness_snapshot)
            _write_swarm_liveness_watch(STATE_DIR, liveness_payload)
            last_swarm_liveness_key = _log_swarm_liveness_transition(
                last_swarm_liveness_key,
                liveness_payload,
            )
            liveness_status = str(
                (liveness_payload.get("liveness") or {}).get("status", "")
            ).strip().lower()
            if liveness_status in {"stalled", "degraded"}:
                signal_bus.emit(
                    {
                        "type": "SWARM_LIVENESS",
                        "status": liveness_status,
                        "detail": (liveness_payload.get("liveness") or {}).get("stall_reason", ""),
                    }
                )

            write_dgc_health_snapshot(
                STATE_DIR,
                daemon_pid=os.getpid(),
                agent_count=_RUNTIME_HEALTH_STATE.get("agent_count", 0),
                task_count=_RUNTIME_HEALTH_STATE.get("task_count", 0),
                anomaly_count=len(anomalies),
                source="orchestrate_live",
            )

        except Exception as e:
            _log("health", f"Error: {e}")

        await asyncio.sleep(HEALTH_INTERVAL)


async def run_living_layers(
    shutdown_event: asyncio.Event,
    stigmergy_store: "StigmergyStore | None" = None,
) -> None:
    """Living layers — stigmergy decay, shakti perception, subconscious dreams."""
    _log("living", f"Starting (interval={LIVING_INTERVAL}s)")
    await asyncio.sleep(45)  # Let other systems init first

    # Hoist heavy objects out of the loop
    from dharma_swarm.stigmergy import StigmergyStore
    from dharma_swarm.subconscious import SubconsciousStream
    from dharma_swarm.shakti import ShaktiLoop

    store = stigmergy_store or StigmergyStore()
    stream = SubconsciousStream(stigmergy=store)
    loop = ShaktiLoop(stigmergy=store)

    while not shutdown_event.is_set():
        try:
            density = store.density()
            summary = [f"density={density}"]

            # Stigmergy decay (evaporate old marks)
            if density > 100:
                decayed = await store.decay(max_age_hours=168)
                if decayed:
                    summary.append(f"decayed={decayed}")

            # Sync stigmergy marks → catalytic graph edges
            try:
                from dharma_swarm.catalytic_graph import CatalyticGraph
                cg = CatalyticGraph()
                cg.load()
                pre_edges = len(cg._edges)
                recent = await store.read_marks(limit=50)
                agent_topics: dict[str, set[str]] = {}
                for mark in recent:
                    agent = mark.agent or "unknown"
                    topic = (mark.observation or mark.action or "")[:40]
                    if agent and topic:
                        agent_topics.setdefault(agent, set()).add(topic)
                        cg.add_node(f"agent:{agent}", type="agent")
                        cg.add_node(f"obs:{topic}", type="observation")
                # Connect agents that share topics (mutual catalysis)
                agents = list(agent_topics.keys())
                for i, a1 in enumerate(agents):
                    for a2 in agents[i+1:]:
                        shared = agent_topics[a1] & agent_topics[a2]
                        if shared:
                            cg.add_edge(f"agent:{a1}", f"agent:{a2}", "validates",
                                        strength=min(1.0, len(shared) * 0.2),
                                        evidence=f"Shared topics: {len(shared)}")
                            cg.add_edge(f"agent:{a2}", f"agent:{a1}", "validates",
                                        strength=min(1.0, len(shared) * 0.2),
                                        evidence=f"Shared topics: {len(shared)}")
                new_edges = len(cg._edges) - pre_edges
                if new_edges > 0:
                    cg.save()
                    summary.append(f"graph_edges=+{new_edges}")
            except Exception as e:
                logger.debug("Stigmergy→graph sync failed: %s", e)

            # Subconscious dreams (trigger on density threshold)
            if await stream.should_wake():
                associations = await stream.dream()
                summary.append(f"dreams={len(associations)}")

            # Shakti perception
            perceptions = await loop.perceive(
                current_context="orchestrator living-layer tick",
                agent_role="orchestrator",
            )
            if perceptions:
                summary.append(f"perceptions={len(perceptions)}")
                high = [p for p in perceptions if p.salience >= 0.7]
                if high:
                    summary.append(f"high_salience={len(high)}")

                    # Route high-salience escalations to Darwin Engine
                    try:
                        queued = _enqueue_shakti_escalations(high)
                        if queued:
                            summary.append(f"darwin_proposals={queued}")
                    except Exception as e:
                        logger.debug("Shakti→Darwin routing failed: %s", e, exc_info=True)

            _log("living", " ".join(summary))

        except Exception as e:
            _log("living", f"Error: {e}")

        await asyncio.sleep(LIVING_INTERVAL)


def _list_orchestrator_processes() -> list[tuple[int, str]]:
    """Best-effort process scan for competing live orchestrators."""
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except Exception:
        return []

    if proc.returncode != 0:
        return []

    current_pid = os.getpid()
    matches: list[tuple[int, str]] = []
    needles = (
        "dharma_swarm.orchestrate_live",
        "orchestrate_live.py",
        "run_daemon.sh",
        "dgc orchestrate-live",
    )
    skip_markers = (
        "ps -axo",
        "rg ",
        "pytest",
        "pre-commit",
        "check-added-large-files",
        "codex exec",
        "claude --bare -p",
    )

    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        command = parts[1]
        if pid == current_pid:
            continue
        if not any(needle in command for needle in needles):
            continue
        if any(marker in command for marker in skip_markers):
            continue
        matches.append((pid, command))

    return matches


def _find_competing_orchestrator() -> tuple[int, str] | None:
    matches = _list_orchestrator_processes()
    if not matches:
        return None
    return matches[0]


def _stop_old_daemon() -> None:
    """Stop existing daemon if running, to avoid DB conflicts."""
    pid_file = STATE_DIR / "daemon.pid"
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)  # Check alive
        _log("orchestrator", f"Stopping old daemon (PID {pid})...")
        os.kill(pid, signal.SIGTERM)
        # Wait up to 5 seconds for clean exit
        for _ in range(10):
            try:
                os.kill(pid, 0)
                import time
                time.sleep(0.5)
            except OSError:
                break
        _log("orchestrator", "Old daemon stopped")
    except (ValueError, OSError):
        pass
    pid_file.unlink(missing_ok=True)


def _reap_stale_pid_files() -> None:
    """Remove PID files that point to dead processes."""
    for pid_file in STATE_DIR.glob("*.pid"):
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)  # Still alive — leave it
        except (ValueError, OSError):
            _log("orchestrator", f"Reaped stale PID file: {pid_file.name}")
            pid_file.unlink(missing_ok=True)


CONSOLIDATION_INTERVAL = _ll.consolidation_interval_seconds

WITNESS_INTERVAL = 3600  # 60 minutes between S3* sporadic audits

ZEITGEIST_INTERVAL = 600  # 10 minutes between S4 environmental scans

REPLICATION_INTERVAL = 3600  # 1 hour between replication checks

RECOGNITION_INTERVAL = 7200  # 2 hours between recognition synthesis

EXECUTIVE_INTERVAL = 2700  # 45 minutes between strategic executive cycles


async def _run_recognition_loop(shutdown_event: asyncio.Event) -> None:
    """Periodic recognition synthesis — the strange loop's self-model.

    Every 2 hours, synthesizes signals from all subsystems into a recognition
    seed that feeds back into agent context via L9 META layer.

    On first run: generates an immediate seed so agents have self-model context
    from the very first task, not after 2 hours of blind operation.
    """
    import time  # required for _seed_stale calculation below
    from dharma_swarm.meta_daemon import RecognitionEngine
    engine = RecognitionEngine()

    # First-run: generate seed immediately if it doesn't exist or is stale (>12h)
    _seed_path = STATE_DIR / "meta" / "recognition_seed.md"
    _seed_stale = (
        not _seed_path.exists() or
        (time.time() - _seed_path.stat().st_mtime) > 43200  # 12 hours
    )
    if _seed_stale:
        _log("recognition", "Generating first-run recognition seed...")
        await asyncio.sleep(30)  # Let other systems init first
        try:
            seed = await asyncio.wait_for(engine.synthesize("light"), timeout=60)
            _log("recognition", f"First-run seed generated ({len(seed)} chars)")
        except Exception as e:
            _log("recognition", f"First-run synthesis failed (non-fatal): {e}")
    else:
        _log("recognition", f"Existing seed is fresh ({_seed_path.stat().st_size}b)")

    # Then run on the normal 2-hour cycle
    while not shutdown_event.is_set():
        await asyncio.sleep(RECOGNITION_INTERVAL)
        if shutdown_event.is_set():
            break
        try:
            seed = await asyncio.wait_for(engine.synthesize("light"), timeout=120)
            _log("recognition", f"Seed updated ({len(seed)} chars)")
        except Exception as e:
            _log("recognition", f"Synthesis failed: {e}")

    # Exit the loop cleanly (original code had the wait at the bottom)
    return


async def _run_recognition_loop_UNUSED(shutdown_event: asyncio.Event) -> None:
    # Keep for reference — original simple loop
    from dharma_swarm.meta_daemon import RecognitionEngine
    engine = RecognitionEngine()

    while not shutdown_event.is_set():
        try:
            seed = await engine.synthesize("light")
            _log("recognition", f"Seed updated ({len(seed)} chars)")
        except Exception as e:
            _log("recognition", f"Synthesis failed: {e}")
    return  # pragma: no cover


async def _run_witness_loop(shutdown_event: asyncio.Event) -> None:
    """S3* Sporadic Audit — random direct audit of agent behavior.

    Implements Beer's S3* function: the Witness samples recent traces,
    evaluates telos alignment, detects mimicry, and publishes findings
    to stigmergy governance channel + signal bus. Closes VSM Gap #2.
    """
    # Let other systems produce traces first
    await asyncio.sleep(120)
    _log("witness", f"S3* Witness auditor starting (cycle={WITNESS_INTERVAL}s)")

    from dharma_swarm.witness import WitnessAuditor

    auditor = WitnessAuditor(cycle_seconds=WITNESS_INTERVAL)

    while not shutdown_event.is_set():
        try:
            findings = await auditor.run_cycle()
            actionable = [f for f in findings if f.is_actionable]
            stats = auditor.get_stats()
            _log(
                "witness",
                f"S3* audit cycle {stats['cycles_completed']}: "
                f"{len(findings)} findings, {len(actionable)} actionable",
            )
            if actionable:
                for f in actionable[:3]:
                    _log("witness", f"  [{f.severity}] {f.agent}/{f.action}: {f.observation[:100]}")
        except Exception as e:
            _log("witness", f"S3* audit failed: {e}")

        try:
            await asyncio.wait_for(
                shutdown_event.wait(), timeout=WITNESS_INTERVAL
            )
            break
        except asyncio.TimeoutError:
            pass

    auditor.stop()
    _log("witness", "S3* Witness auditor stopped")


async def _run_consolidation_loop(shutdown_event: asyncio.Event) -> None:
    """Consolidation Cycle — system-wide sleep/backpropagation.

    Two consolidator agents (Alpha/Beta) read ALL agents' state, have a
    structured contrarian debate, and modify behavioral DNA based on
    observed "loss". Mirrors sleep consolidation in the brain.
    """
    # Wait 2 hours after boot to let other systems produce traces
    await asyncio.sleep(7200)
    _log("consolidation", f"Sleep cycle starting (interval={CONSOLIDATION_INTERVAL}s)")

    from dharma_swarm.consolidation import ConsolidationCycle

    cycle = ConsolidationCycle(state_dir=STATE_DIR)

    # Neural consolidator: algorithmic forward-pass + loss detection + corrections
    # Runs BEFORE the LLM debate cycle — no LLM cost, identifies losses fast
    try:
        from dharma_swarm.neural_consolidator import NeuralConsolidator
        _neural = NeuralConsolidator(
            provider=None,  # Algorithmic mode, no LLM calls
            base_path=STATE_DIR,
        )
    except Exception as _ne:
        _neural = None
        _log("consolidation", f"Neural consolidator init failed: {_ne}")

    while not shutdown_event.is_set():
        # Neural pass first (algorithmic, fast, no LLM cost)
        if _neural is not None:
            try:
                _nr = await _neural.consolidation_cycle()
                _log(
                    "consolidation",
                    f"Neural pass: losses={_nr.losses_found} "
                    f"corrections={_nr.corrections_applied} "
                    f"divisions={_nr.division_proposals}",
                )
            except Exception as _ne:
                _log("consolidation", f"Neural pass error: {_ne}")

        # LLM-based contrarian debate cycle
        try:
            outcome = await cycle.run()
            _log(
                "consolidation",
                f"Cycle {outcome.cycle_number}: loss={outcome.system_loss_score:.3f} "
                f"corrections={outcome.corrections_applied}/{outcome.corrections_proposed} "
                f"({outcome.duration_seconds:.1f}s)",
            )
            # Export capability/fitness gap corrections as evolution proposals
            try:
                exported = cycle.export_evolution_proposals(outcome)
                if exported:
                    _log("consolidation", f"Exported {exported} proposals to evolution pipeline")
            except Exception as _ep_err:
                _log("consolidation", f"Proposal export failed: {_ep_err}")
        except Exception as e:
            _log("consolidation", f"Cycle failed: {e}")

        try:
            await asyncio.wait_for(
                shutdown_event.wait(), timeout=CONSOLIDATION_INTERVAL
            )
            break
        except asyncio.TimeoutError:
            pass

    _log("consolidation", "Sleep cycle stopped")


# ---------------------------------------------------------------------------
# Loop 13: Free Evolution Grind — nonstop free-tier evolution with hunger signal
# ---------------------------------------------------------------------------

# Hunger thresholds: when hunger > HIGH, run fast. When < LOW, run slow.
_GRIND_HUNGER_HIGH = 0.7
_GRIND_HUNGER_LOW = 0.3
_GRIND_INTERVAL_FAST = 60      # seconds — when hungry
_GRIND_INTERVAL_SLOW = 300     # seconds — when satisfied
_GRIND_STAGNATION_WINDOW = 10  # meta-archive entries to check for plateau

# Low-cost and free providers preferred for the continuous grind.
_FREE_PROVIDER_TYPES = (
    "ollama",
    "nvidia_nim",
    "siliconflow",
    "together",
    "fireworks",
    "cerebras",
    "sambanova",
    "openrouter_free",
    "groq",
    "openrouter",
)

# Core Python modules to target for evolution — actual testable source
_GRIND_EVOLUTION_TARGETS = (
    "swarm.py", "orchestrator.py", "agent_runner.py", "providers.py",
    "evolution.py", "thinkodynamic_director.py", "consolidation.py",
    "stigmergy.py", "monitor.py", "auto_proposer.py", "self_improve.py",
    "fitness_predictor.py", "training_flywheel.py", "overnight_evaluator.py",
)


def _compute_hunger(meta_archive_path: Path, last_improvement_time: float) -> float:
    """Hunger = how badly the system wants to evolve right now.

    Inputs:
        - meta_fitness plateau (are recent meta-fitness values flat?)
        - time since last real improvement
        - gap between current fitness and 1.0

    Returns 0.0 (satisfied) to 1.0 (starving).
    """
    import json as _hj
    import time as _ht

    if not meta_archive_path.exists():
        return 0.5  # neutral

    # Read last N meta-archive entries
    try:
        lines = meta_archive_path.read_text().strip().split("\n")
        recent = []
        for line in lines[-_GRIND_STAGNATION_WINDOW:]:
            if line.strip():
                recent.append(_hj.loads(line))
    except Exception:
        return 0.5

    if len(recent) < 3:
        return 0.6  # slight hunger — need more data

    # Component 1: fitness gap (how far from 1.0)
    latest_mf = recent[-1].get("meta_fitness", 0.5)
    fitness_gap = max(0.0, 1.0 - latest_mf)

    # Component 2: stagnation (are recent values flat?)
    mf_values = [e.get("meta_fitness", 0.5) for e in recent]
    if len(mf_values) >= 2:
        diffs = [abs(b - a) for a, b in zip(mf_values, mf_values[1:])]
        avg_diff = sum(diffs) / len(diffs)
        stagnation = max(0.0, 1.0 - (avg_diff * 20))  # flat = high stagnation
    else:
        stagnation = 0.5

    # Component 3: time since last improvement (decays every hour)
    time_since = _ht.time() - last_improvement_time
    time_pressure = min(1.0, time_since / 7200.0)  # maxes at 2 hours

    hunger = (0.4 * fitness_gap) + (0.35 * stagnation) + (0.25 * time_pressure)
    return max(0.0, min(1.0, hunger))


def _hunger_to_interval(hunger: float) -> float:
    """Map hunger to sleep interval: high hunger = short interval."""
    if hunger >= _GRIND_HUNGER_HIGH:
        return _GRIND_INTERVAL_FAST
    if hunger <= _GRIND_HUNGER_LOW:
        return _GRIND_INTERVAL_SLOW
    # Linear interpolation
    ratio = (hunger - _GRIND_HUNGER_LOW) / (_GRIND_HUNGER_HIGH - _GRIND_HUNGER_LOW)
    return _GRIND_INTERVAL_SLOW - (ratio * (_GRIND_INTERVAL_SLOW - _GRIND_INTERVAL_FAST))


async def run_free_evolution_grind(shutdown_event: asyncio.Event) -> None:
    """Nonstop free-tier evolution loop with adaptive hunger signal.

    Runs AutoProposer → DarwinEngine → MetaEvolution using ONLY free providers.
    Adjusts its own cadence: runs every 60s when hungry, every 300s when satisfied.
    Cost: $0. Runs 24/7.

    This is loop #13 in the orchestrator — the system's metabolic drive.
    """
    _log("grind", "Free Evolution Grind starting (loop #13)")
    _log("grind", f"  Preferred providers: {_FREE_PROVIDER_TYPES}")
    _log("grind", f"  Interval range: {_GRIND_INTERVAL_FAST}s (hungry) → {_GRIND_INTERVAL_SLOW}s (satisfied)")
    _log("grind", "  Warm-up delay: 90s before first cycle")
    await asyncio.sleep(90)  # Let swarm + evolution init first

    # Init DarwinEngine (separate instance, reads same archive)
    from dharma_swarm.evolution import DarwinEngine, Proposal
    from dharma_swarm.meta_evolution import MetaEvolutionEngine

    evo_dir = STATE_DIR / "evolution"
    traces_dir = STATE_DIR / "traces"
    meta_archive_path = evo_dir / "meta_archive.jsonl"

    engine = DarwinEngine(
        archive_path=evo_dir / "archive.jsonl",
        traces_path=traces_dir,
        predictor_path=evo_dir / "predictor_data.jsonl",
    )
    await engine.init()

    meta_engine = MetaEvolutionEngine(
        engine,
        meta_archive_path=meta_archive_path,
        n_object_cycles_per_meta=2,
        auto_apply=True,
    )
    from dharma_swarm.message_bus import MessageBus as _MBus

    _bus = _MBus(STATE_DIR / "db" / "messages.db")
    await _bus.init_db()

    cycle_count = 0
    last_improvement_time = __import__("time").time()
    last_best_fitness = 0.0
    recent_targets: list[str] = []

    while not shutdown_event.is_set():
        cycle_count += 1

        try:
            fitness_events = await _bus.consume_events("AGENT_FITNESS", limit=100)
            lifecycle_events = await _consume_event_backlog(
                _bus,
                "AGENT_LIFECYCLE_COMPLETED",
                batch_size=500,
                max_events=5000,
            )
            if fitness_events:
                scores: list[float] = []
                for ev in fitness_events:
                    payload = ev.get("payload") if isinstance(ev, dict) else {}
                    if not isinstance(payload, dict):
                        continue
                    score = (
                        payload.get("swabhaav_ratio")
                        or payload.get("fitness_score")
                        or payload.get("composite")
                    )
                    if isinstance(score, (int, float)) and score > 0:
                        scores.append(float(score))
                        await engine.record_fitness_observation(
                            agent_name=payload.get("agent", "unknown"),
                            fitness_score=float(score),
                            task_id=payload.get("task_id"),
                        )
                if scores:
                    _log(
                        "grind",
                        f"Bus fitness: {len(scores)} score(s), avg={sum(scores) / len(scores):.3f}",
                    )
            if lifecycle_events:
                _log("grind", f"Lifecycle backlog drained: {len(lifecycle_events)} completion event(s)")
        except Exception:
            logger.debug("Free-grind bus drain failed", exc_info=True)

        # Compute hunger
        hunger = _compute_hunger(meta_archive_path, last_improvement_time)
        interval = _hunger_to_interval(hunger)

        try:
            import random as _grng
            _src_root = Path(__file__).resolve().parent
            proposals: list[Proposal] = []

            # Phase 1: Read pending proposals from consolidation bridge
            try:
                pending = engine.load_pending_proposals()
                if pending:
                    # Filter to only Python source targets
                    for p in pending[:3]:
                        comp = p.component
                        if comp.endswith(".py") or "/" not in comp:
                            proposals.append(p)
                    if proposals:
                        _log("grind", f"Loaded {len(proposals)} pending proposals from consolidation")
            except Exception:
                pass

            # Phase 2: AutoProposer observations (only those targeting .py files)
            if len(proposals) < 3:
                try:
                    import json as _gj
                    obs_file = STATE_DIR / "auto_proposer" / "observations.jsonl"
                    if obs_file.exists():
                        obs_lines = obs_file.read_text().strip().split("\n")
                        for line in obs_lines[-5:]:
                            if not line.strip():
                                continue
                            obs = _gj.loads(line)
                            fp = obs.get("source_data", {}).get("file_path", "")
                            # Only accept Python file paths
                            if fp.endswith(".py"):
                                proposals.append(Proposal(
                                    component=fp,
                                    change_type="mutation",
                                    description=obs.get("description", "auto-observation"),
                                    spec_ref=f"auto_proposer:{obs.get('observation_type', '?')}",
                                ))
                except Exception as exc:
                    _log("grind", f"Observation read error: {exc}")

            # Phase 3: Always include a rotating core Python module target.
            available_targets = [
                t for t in _GRIND_EVOLUTION_TARGETS
                if (_src_root / t).exists()
            ]
            if available_targets:
                novel_targets = [t for t in available_targets if t not in recent_targets]
                target_pool = novel_targets or available_targets
                target = _grng.choice(target_pool)
                proposals.append(Proposal(
                    component=target,
                    change_type="mutation",
                    description=f"Grind probe: evolve {target} (hunger={hunger:.2f})",
                    spec_ref="grind_probe",
                ))
                recent_targets.append(target)
                recent_targets = recent_targets[-6:]

            # Phase 4: Run evolution cycle via DarwinEngine.run_cycle
            # (takes proposals directly — no LLM needed for proposal gen)
            result = await engine.run_cycle(proposals)

            # Phase 4b: LLM-powered evolution with the multi-provider roster.
            if cycle_count % 5 == 0 and hunger > 0.4:
                try:
                    if available_targets:
                        from dharma_swarm.providers import OpenRouterProvider, create_default_router

                        router = create_default_router()
                        fallback_provider = OpenRouterProvider()
                        llm_target_pool = [t for t in available_targets if t not in recent_targets]
                        if len(llm_target_pool) < 2:
                            llm_target_pool = available_targets
                        _llm_targets = _grng.sample(llm_target_pool, min(3, len(llm_target_pool)))
                        _llm_files = [_src_root / t for t in _llm_targets]
                        _log("grind", f"LLM evolve via roster: {_llm_targets}")
                        llm_result = await engine.auto_evolve(
                            provider=fallback_provider,
                            source_files=_llm_files,
                            model="",
                            shadow=False,  # Real mode — apply diffs, run tests, roll back on failure
                            timeout=30.0,
                            context=f"Grind cycle {cycle_count}, hunger={hunger:.2f}",
                            router=router,
                        )
                        if llm_result.best_fitness > result.best_fitness:
                            result = llm_result  # Use the better result
                            _log("grind", f"LLM result: fitness={llm_result.best_fitness:.3f} (better)")
                except Exception as _llm_err:
                    _log("grind", f"LLM evolve error: {_llm_err}")

            # Phase 5: Feed to meta-evolution
            meta_result = meta_engine.observe_cycle_result(result)

            # Track improvement
            if result.best_fitness > last_best_fitness + 0.01:
                last_best_fitness = result.best_fitness
                last_improvement_time = __import__("time").time()

            # Phase 5: Log
            meta_note = ""
            if meta_result is not None:
                if meta_result.evolved_parameters:
                    meta_note = f" | META EVOLVED (mf={meta_result.meta_fitness:.3f})"
                else:
                    meta_note = f" | meta ok (mf={meta_result.meta_fitness:.3f})"

            _log(
                "grind",
                f"Cycle {cycle_count}: hunger={hunger:.2f} interval={interval:.0f}s "
                f"proposals={len(proposals)} fitness={result.best_fitness:.3f} "
                f"archived={result.proposals_archived}{meta_note}",
            )

        except Exception as exc:
            _log("grind", f"Cycle {cycle_count} error: {exc}")

        # Adaptive sleep — hunger controls the pace
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            pass

    _log("grind", f"Free Evolution Grind stopped after {cycle_count} cycles")


async def _run_replication_monitor_loop(shutdown_event: asyncio.Event) -> None:
    """Loop 9: Replication monitor -- process proposals, manage child lifecycles.

    Waits for consolidation to run first (initial delay = consolidation interval
    + 1 hour), then periodically drains pending proposals from
    ``~/.dharma/replication/proposals.jsonl`` and runs each through the
    checkpoint-gated ReplicationProtocol pipeline.

    Successful materialization creates a PersistentAgent whose ``run_loop``
    is spawned as a new asyncio task. Probation and apoptosis checks run
    on every tick for all tracked agents.
    """
    # Let consolidation produce proposals before we start consuming them
    initial_delay = CONSOLIDATION_INTERVAL + 3600
    _log("replication", f"Waiting {initial_delay}s for consolidation to run first...")
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=initial_delay)
        _log("replication", "Shutdown during initial delay, exiting")
        return
    except asyncio.TimeoutError:
        pass

    _log("replication", f"Replication monitor starting (interval={REPLICATION_INTERVAL}s)")

    # Lazy imports to avoid circular deps and startup cost
    from dharma_swarm.replication_protocol import ReplicationProtocol

    protocol = ReplicationProtocol(state_dir=STATE_DIR)

    # Track spawned child tasks so we can cancel on shutdown
    child_tasks: list[asyncio.Task[None]] = []

    while not shutdown_event.is_set():
        try:
            pending = protocol.get_pending_proposals()
            if pending:
                _log("replication", f"Processing {len(pending)} pending proposal(s)")

            for proposal_data in pending:
                try:
                    outcome = await protocol.run(proposal_data.model_dump())
                    status = "SUCCESS" if outcome.success else "FAILED"
                    _log(
                        "replication",
                        f"Proposal '{proposal_data.proposed_role}': {status} "
                        f"({outcome.duration_seconds:.1f}s)"
                        + (f" -- {outcome.error}" if outcome.error else ""),
                    )

                    # On success, spawn PersistentAgent for the child
                    if outcome.success and outcome.child_agent_name and outcome.child_spec:
                        try:
                            from dharma_swarm.persistent_agent import PersistentAgent
                            from dharma_swarm.models import AgentRole, ProviderType as PT

                            child = PersistentAgent(
                                name=outcome.child_agent_name,
                                role=AgentRole(outcome.child_spec.get("role", "general")),
                                provider_type=PT(outcome.child_spec.get(
                                    "default_provider", "openrouter_free"
                                )),
                                model=outcome.child_spec.get("default_model", ""),
                                state_dir=STATE_DIR,
                                wake_interval_seconds=float(
                                    outcome.child_spec.get("wake_interval", 3600)
                                ),
                                system_prompt=outcome.child_spec.get("system_prompt", ""),
                            )
                            task = asyncio.create_task(
                                child.run_loop(shutdown_event),
                                name=f"child-{outcome.child_agent_name}",
                            )
                            child_tasks.append(task)
                            _log(
                                "replication",
                                f"Spawned child agent '{outcome.child_agent_name}' as asyncio task",
                            )
                        except Exception as spawn_exc:
                            _log(
                                "replication",
                                f"Failed to spawn child '{outcome.child_agent_name}': {spawn_exc}",
                            )
                except Exception as run_exc:
                    _log(
                        "replication",
                        f"Pipeline error for '{proposal_data.proposed_role}': {run_exc}",
                    )

            # Probation + apoptosis checks
            try:
                from dharma_swarm.population_control import PopulationController
                pop_ctrl = PopulationController(state_dir=STATE_DIR)
                probation_map = pop_ctrl.get_all_probation()
                for name, status in probation_map.items():
                    if not status.is_complete:
                        _log("replication", f"Probation active: '{name}' ({status.cycles_remaining} cycles left)")
            except Exception as pc_exc:
                _log("replication", f"Population check error: {pc_exc}")

        except Exception as e:
            _log("replication", f"Monitor error: {e}")

        # Clean up completed child tasks
        child_tasks = [t for t in child_tasks if not t.done()]

        try:
            await asyncio.wait_for(
                shutdown_event.wait(), timeout=REPLICATION_INTERVAL
            )
            break
        except asyncio.TimeoutError:
            pass

    # Cancel child tasks on shutdown
    for t in child_tasks:
        t.cancel()
    if child_tasks:
        await asyncio.gather(*child_tasks, return_exceptions=True)

    _log("replication", "Replication monitor stopped")


async def _run_zeitgeist_loop(shutdown_event: asyncio.Event) -> None:
    """S4 Environmental Intelligence — periodic zeitgeist scanning.

    Scans witness logs, shared notes, and external signals. When high gate
    block rates are detected, writes gate_pressure.json to tighten S3 trust
    mode. This closes VSM Gap #1: S3<->S4 bidirectional feedback.
    """
    # Initial delay to let other systems boot first
    await asyncio.sleep(30)

    from dharma_swarm.zeitgeist import ZeitgeistScanner
    scanner = ZeitgeistScanner(state_dir=STATE_DIR)

    while not shutdown_event.is_set():
        try:
            signals = await scanner.scan()
            threats = [s for s in signals if s.category == "threat"]
            _log("zeitgeist", f"S4 scan: {len(signals)} signals, {len(threats)} threats")
        except Exception as e:
            _log("zeitgeist", f"S4 scan failed: {e}")

        try:
            await asyncio.wait_for(
                shutdown_event.wait(), timeout=ZEITGEIST_INTERVAL
            )
            break
        except asyncio.TimeoutError:
            pass


async def run_conductor_loop(shutdown_event: asyncio.Event) -> None:
    """Run persistent conductor agents alongside the orchestrator.

    Each conductor has its own wake interval and restart logic.
    If one crashes, the other keeps running.

    Conductors are also registered into the module-level ACTIVE_CONDUCTORS
    registry in ``dharma_swarm.conductors`` so the directive watcher and
    CLI (``dgc agent:direct``, ``dgc campaign:*``) can reach them by name.
    """
    from dharma_swarm.persistent_agent import PersistentAgent
    from dharma_swarm.conductors import CONDUCTOR_CONFIGS, register, unregister

    _log("conductors", f"Initializing {len(CONDUCTOR_CONFIGS)} conductors...")

    conductors: list[PersistentAgent] = []
    for cfg in CONDUCTOR_CONFIGS:
        agent = PersistentAgent(
            name=cfg["name"],
            role=cfg["role"],
            provider_type=cfg["provider_type"],
            model=cfg["model"],
            state_dir=STATE_DIR,
            wake_interval_seconds=cfg["wake_interval_seconds"],
            system_prompt=cfg["system_prompt"],
            max_turns=cfg.get("max_turns", 25),
        )
        conductors.append(agent)
        # Defer registry insertion to the runner so conductor boot cannot block here.
        _log(
            "conductors",
            f"  {cfg['name']}: {cfg['model']} every {cfg['wake_interval_seconds']}s (registered)",
        )

    async def _run_with_restart(conductor: PersistentAgent, delay: float) -> None:
        await asyncio.sleep(delay)
        await register(conductor.name, conductor)
        _log("conductors", f"{conductor.name} registered and starting")
        while not shutdown_event.is_set():
            try:
                await conductor.run_loop(shutdown_event)
            except Exception as e:
                _log("conductors", f"{conductor.name} crashed: {e}. Restarting in 60s")
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout=60)
                    break
                except asyncio.TimeoutError:
                    pass

    try:
        await asyncio.gather(
            _run_with_restart(conductors[0], 10),   # Claude starts +10s
            _run_with_restart(conductors[1], 30),   # Codex starts +30s
        )
    finally:
        for c in conductors:
            try:
                await unregister(c.name)
            except Exception:
                pass


async def _run_gauntlet_loop(shutdown_event: asyncio.Event) -> None:
    """Gauntlet: run adversarial eval pressure on a schedule, feed scores into DGM.

    Tier 1+2 (correctness + research): every 2 hours.
    Tier 3 (self-modification): every 6 hours.
    Tier 4+5 (adversarial + emergent): every 12 hours.
    Scores written to ~/.dharma/gauntlet/ and fed back to BenchmarkRegistry.
    """
    import random as _random
    _log("gauntlet", "Gauntlet loop starting")
    _cycle = 0
    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=7200)
            break
        except asyncio.TimeoutError:
            pass
        if shutdown_event.is_set():
            break

        _cycle += 1
        tiers = [1, 2]
        if _cycle % 3 == 0:
            tiers.append(3)
        if _cycle % 6 == 0:
            tiers += [4, 5]

        try:
            from benchmarks.gauntlet import run_gauntlet
            _log("gauntlet", f"Running tiers {tiers} (cycle {_cycle})")
            report = await asyncio.wait_for(run_gauntlet(tiers=tiers), timeout=1800)
            _log("gauntlet",
                 f"Score: {report.gauntlet_score:.3f} (Δ{report.delta:+.3f}) | "
                 f"DGM targets: {report.dgm_targets}")
            # Feed DGM targets into evolution loop via signal bus
            if report.dgm_targets and report.delta < 0:
                try:
                    from dharma_swarm.signal_bus import SignalBus
                    SignalBus.get().emit("GAUNTLET_REGRESSION", {
                        "score": report.gauntlet_score,
                        "delta": report.delta,
                        "dgm_targets": report.dgm_targets,
                    })
                except Exception:
                    pass
        except asyncio.TimeoutError:
            _log("gauntlet", "Gauntlet cycle timed out (1800s)")
        except Exception as exc:
            _log("gauntlet", f"Gauntlet cycle failed: {exc}")


async def _run_health_api(shutdown_event: asyncio.Event) -> None:
    """Health API: serves http://localhost:7433/health|metrics|loops|providers|telos"""
    try:
        _log("health-api", "Starting health API server")
        from dharma_swarm.swarm_health_api import run_health_api
        await run_health_api(shutdown_event)
    except Exception as exc:
        _log("health-api", f"Health API crashed: {exc}")


async def _run_guardian_loop(shutdown_event: asyncio.Event) -> None:
    """Guardian Crew: continuous interface + loop + router health checking.

    Three specialist agents running every 4 hours:
      AUDITOR        — import chains, method existence, syntax errors
      LOOP_WATCHER   — cybernetic loop health, evolution archive freshness
      ROUTER_PROBE   — circuit breaker state, dead providers, missing keys

    Writes GUARDIAN_REPORT.md to repo root and ~/.dharma/guardian/.
    Creates GitHub issues for BLOCKER-severity findings.
    """
    try:
        from dharma_swarm.guardian_crew import start_guardian_loop
        await start_guardian_loop(
            state_dir=STATE_DIR,
            github_repo="AmitabhainArunachala/dharma_swarm",
            shutdown_event=shutdown_event,
        )
    except Exception as exc:
        _log("guardian", f"Guardian loop crashed: {exc}")


async def _run_cc_tool_marks_loop(shutdown_event: asyncio.Event) -> None:
    """Sprint 1 Fix 3 consumer loop. Aggregates cc_tool_marks.jsonl every 5min.

    Closes the Claude-Code → Dharma one-way bridge. Reads from a persistent
    byte cursor, aggregates per-tool and per-file counts, writes a summary
    to ~/.dharma/meta/cc_tool_marks_signals.json for downstream consumers.

    Rollback: DHARMA_CC_TOOL_MARKS_CONSUMER=off disables consumption.
    """
    _log("cc-tool-marks", "Starting cc_tool_marks consumer loop (interval=300s)")
    try:
        await asyncio.sleep(10)  # small delay after boot
        from dharma_swarm.cc_tool_marks_consumer import CcToolMarksConsumer
        consumer = CcToolMarksConsumer()

        # Run once immediately
        try:
            summary = await asyncio.wait_for(
                asyncio.to_thread(consumer.run_once), timeout=30.0
            )
            _log(
                "cc-tool-marks",
                f"Boot consume: {summary.get('new_records', 0)} new records",
            )
        except Exception as exc:
            _log("cc-tool-marks", f"Boot consume failed (non-fatal): {exc}")

        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=300)
                break
            except asyncio.TimeoutError:
                pass
            if shutdown_event.is_set():
                break
            try:
                summary = await asyncio.wait_for(
                    asyncio.to_thread(consumer.run_once), timeout=30.0
                )
                _log(
                    "cc-tool-marks",
                    f"Cycle: +{summary.get('new_records', 0)} records",
                )
            except asyncio.TimeoutError:
                _log("cc-tool-marks", "Cycle timed out (30s) — continuing")
            except Exception as exc:
                _log("cc-tool-marks", f"Cycle failed (non-fatal): {exc}")
    except Exception as exc:
        _log("cc-tool-marks", f"Loop crashed: {exc}")


async def _run_archaeology_loop(shutdown_event: asyncio.Event) -> None:
    """Fang 7: Self-Reading Archaeology loop.

    Runs ArchaeologyIngestionDaemon on a 30-minute cycle.
    Ingests: evolution archive, shared research, stigmergy marks, task completions.
    Produces: ~/.dharma/meta/lessons_learned.md (anti-amnesia context prefix).
    Agents gain query_archaeology tool access to all ingested institutional memory.
    """
    _log("archaeology", "Starting archaeology ingestion loop (interval=1800s)")
    try:
        from dharma_swarm.archaeology_ingestion import (
            ArchaeologyIngestionDaemon,
            _archaeology_boot_delay_seconds,
        )

        def _run_cycle_sync(daemon: ArchaeologyIngestionDaemon) -> dict[str, int]:
            return asyncio.run(daemon.run_once())

        boot_delay_seconds = _archaeology_boot_delay_seconds(1800)
        if boot_delay_seconds > 0:
            _log("archaeology", f"Deferring boot ingestion for {boot_delay_seconds:.0f}s")
            if await _wait_or_shutdown(shutdown_event, boot_delay_seconds):
                return
        daemon = ArchaeologyIngestionDaemon(state_dir=STATE_DIR, interval_seconds=1800)

        # Run once immediately at boot
        try:
            counts = await asyncio.wait_for(asyncio.to_thread(_run_cycle_sync, daemon), timeout=120.0)
            _log("archaeology", f"Boot ingestion complete: {counts}")
        except asyncio.TimeoutError:
            _log("archaeology", "Boot ingestion timed out (120s) — continuing")
        except Exception as exc:
            _log("archaeology", f"Boot ingestion failed (non-fatal): {exc}")

        # Then loop every 30 minutes
        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=1800)
                break  # shutdown
            except asyncio.TimeoutError:
                pass  # interval elapsed, run ingestion
            if shutdown_event.is_set():
                break
            try:
                counts = await asyncio.wait_for(asyncio.to_thread(_run_cycle_sync, daemon), timeout=120.0)
                _log("archaeology", f"Ingestion cycle complete: {counts}")
            except asyncio.TimeoutError:
                _log("archaeology", "Ingestion cycle timed out (120s) — continuing")
            except Exception as exc:
                _log("archaeology", f"Ingestion cycle error: {exc}")

    except Exception as exc:
        _log("archaeology", f"Archaeology loop crashed: {exc}")


RESEARCH_RTN_INTERVAL = 1800  # 30 minutes


async def _run_research_rtn_loop(shutdown_event: asyncio.Event) -> None:
    _log("research-rtn", f"Starting research RTN loop (interval={RESEARCH_RTN_INTERVAL}s)")
    try:
        await asyncio.sleep(5)  # let other systems boot first
        from dharma_swarm.research_rtn import ResearchRTN
        from dharma_swarm.research_tracks import ALL_TRACKS

        # Try to use WebSearchBackend; fall back to NullSearchBackend
        try:
            from dharma_swarm.auto_research.backends import WebSearchBackend
            backend = WebSearchBackend()
        except Exception:
            from dharma_swarm.auto_research.search import NullSearchBackend
            backend = NullSearchBackend()

        rtn = ResearchRTN(search_backend=backend)
        track_cycle = 0

        while not shutdown_event.is_set():
            track = ALL_TRACKS[track_cycle % len(ALL_TRACKS)]
            brief_idx = track_cycle // len(ALL_TRACKS)
            brief = track.next_brief(index=brief_idx)
            _log("research-rtn", f"Executing: track={track.slug}, topic={brief.topic}")

            try:
                result = await asyncio.to_thread(rtn.execute_brief, brief)
                status = "PASSED" if result.passed_gates else "FAILED"
                score = result.reward.grade_card.final_score if result.reward else 0.0
                _log(
                    "research-rtn",
                    f"Result: {status} (score={score:.2f}, subs={len(result.sub_results)})",
                )
                if result.artifact:
                    _log("research-rtn", f"Artifact published: {result.artifact.ref.artifact_id}")
            except Exception as exc:
                _log("research-rtn", f"RTN execution error: {exc}")

            track_cycle += 1
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(), timeout=RESEARCH_RTN_INTERVAL
                )
                break
            except asyncio.TimeoutError:
                pass

    except Exception as exc:
        _log("research-rtn", f"Research RTN loop crashed: {exc}")


async def _run_directives_loop(shutdown_event: asyncio.Event) -> None:
    """Operator-facing directive watcher.

    Boots 20s after daemon start so conductors have time to register
    themselves into ACTIVE_CONDUCTORS. Thin wrapper around
    ``agent_direct.watcher_loop`` for orchestrator supervision.
    """
    await asyncio.sleep(20)
    from dharma_swarm.agent_direct import watcher_loop

    _log("directives", "Directive watcher starting (poll=5s)")
    try:
        await watcher_loop(shutdown_event, poll_interval=5.0)
    except Exception as exc:
        _log("directives", f"Directive watcher crashed: {exc}")


async def _run_executive_loop(shutdown_event: asyncio.Event) -> None:
    """ShaktiZeitgeistExecutive — strategic sensing + opportunity scoring.

    Phase 1: read-only.  Ingests signals from zeitgeist, mission, organism,
    and algedonic sources.  Scores opportunities with a 12-factor model.
    Emits executive artifacts under ``~/.dharma/meta/``.
    """
    await asyncio.sleep(120)  # let zeitgeist + organism boot first

    from dharma_swarm.shakti_zeitgeist_executive import ShaktiZeitgeistExecutive
    executive = ShaktiZeitgeistExecutive(state_dir=STATE_DIR)

    while not shutdown_event.is_set():
        try:
            result = await executive.cycle()
            n_opps = len(result.opportunities)
            n_starved = len(result.starvation_alerts)
            _log("executive", f"Cycle {result.cycle_id}: {result.signals_ingested} signals, "
                 f"{n_opps} opportunities, {n_starved} starvation alerts "
                 f"({result.duration_ms:.0f}ms)")
        except Exception as e:
            _log("executive", f"Executive cycle failed: {e}")

        try:
            await asyncio.wait_for(
                shutdown_event.wait(), timeout=EXECUTIVE_INTERVAL
            )
            break
        except asyncio.TimeoutError:
            pass


async def orchestrate(background: bool = False) -> None:
    """Main entry point — run all systems concurrently."""
    # Ensure Python logging is configured so module-level logger.info() calls
    # (from orchestrator.py, swarm.py, agent_runner.py etc.) are visible.
    # Rotating file logs: 10MB × 5 files → ~/.dharma/logs/swarm.log
    _log_dir = STATE_DIR / "logs"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _root = logging.getLogger()
    if not _root.handlers:
        _root.setLevel(logging.INFO)
        _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        _ch = logging.StreamHandler()
        _ch.setFormatter(_fmt)
        _root.addHandler(_ch)
        from logging.handlers import RotatingFileHandler as _RFH
        _fh = _RFH(_log_dir / "swarm.log", maxBytes=10 * 1024 * 1024, backupCount=5)
        _fh.setFormatter(_fmt)
        _root.addHandler(_fh)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    competing = _find_competing_orchestrator()
    if competing is not None:
        pid, command = competing
        _log(
            "orchestrator",
            f"Refusing duplicate startup; existing orchestrator PID {pid}: {command[:160]}",
        )
        return

    # Stop any existing daemon to avoid DB conflicts
    _stop_old_daemon()
    _reap_stale_pid_files()

    # Write PID -- use daemon.pid for consistency with _stop_old_daemon()
    pid_file = STATE_DIR / "daemon.pid"
    pid_file.write_text(str(os.getpid()))

    shutdown_event = asyncio.Event()

    def _signal_handler(signum, frame):
        _log("orchestrator", f"Signal {signum} received, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Enable subscription auth for Claude when not nested inside Claude Code
    if "CLAUDECODE" not in os.environ:
        os.environ.setdefault("DHARMA_CLAUDE_AUTH_MODE", "subscription")
        _log("orchestrator", "Claude auth: subscription (Max/Pro plan)")
    else:
        _log("orchestrator", "Claude auth: skipped (nested in Claude Code)")

    # Phase 2: Create shared signal bus for inter-loop temporal coherence
    from dharma_swarm.signal_bus import SignalBus
    bus = SignalBus.get()

    _log("orchestrator", "=" * 60)
    _log("orchestrator", "DGC Live Orchestrator starting (Strange Loop v1)")
    _log("orchestrator", f"  PID: {os.getpid()}")
    _log("orchestrator", f"  State: {STATE_DIR}")
    _log("orchestrator", f"  Swarm tick: {SWARM_TICK}s")
    _log("orchestrator", f"  Pulse interval: {PULSE_INTERVAL}s")
    _log("orchestrator", f"  Max daily: {MAX_DAILY}")
    _log("orchestrator", f"  Signal bus: active")
    _log("orchestrator", "=" * 60)

    # Constitutional size check (Power Prompt Commandment #3)
    try:
        from dharma_swarm.constitutional_size_check import enforce_constitutional_size
        enforce_constitutional_size()
    except RuntimeError as e:
        _log("orchestrator", f"FATAL: {e}")
        raise
    except Exception as e:
        _log("orchestrator", f"Constitutional size check failed (non-fatal): {e}")

    # Strange Loop Phase 0: unified swarm tick handles evolution + living layers + health
    # Only genuinely independent loops remain as separate tasks
    from dharma_swarm.context_agent import run_context_agent_loop
    from dharma_swarm.training_flywheel import run_training_flywheel_loop
    from dharma_swarm.self_improve import run_self_improvement_loop

    # Auto-enable self-improvement when autonomy >= 1
    _auto_level = int(os.environ.get("DGC_AUTONOMY_LEVEL", "1"))
    if _auto_level >= 1 and not os.environ.get("DHARMA_SELF_IMPROVE"):
        os.environ["DHARMA_SELF_IMPROVE"] = "1"
        _log("orchestrator", "Auto-enabled DHARMA_SELF_IMPROVE (autonomy >= 1)")

    # Liveness watchdog — the #1 convergent finding from the 20-agent audit.
    # Detects "alive but not progressing" loops before they compound.
    from dharma_swarm.loop_supervisor import LoopSupervisor
    _supervisor = LoopSupervisor()
    _loop_intervals = {
        "swarm": SWARM_TICK, "pulse": PULSE_INTERVAL, "health": 120,
        "zeitgeist": ZEITGEIST_INTERVAL, "witness": WITNESS_INTERVAL,
        "consolidation": CONSOLIDATION_INTERVAL, "recognition": 7200,
        "replication": 3600, "self-improve": 3600, "free-grind": 600,
        "flywheel": 300, "conductors": 120, "context-agent": 60,
        "research-rtn": RESEARCH_RTN_INTERVAL,
        "executive": EXECUTIVE_INTERVAL,
    }
    for loop_name, interval in _loop_intervals.items():
        _supervisor.register_loop(loop_name, expected_interval=float(interval))

    startup_ready_gate = asyncio.Event()
    task_factories: dict[str, Any] = {
        # ── Health API: curl http://localhost:7433/health ──
        "health-api": lambda: _run_health_api(shutdown_event),
        "swarm": lambda: run_swarm_loop(
            shutdown_event,
            signal_bus=bus,
            supervisor=_supervisor,
            bootstrap_ready_event=startup_ready_gate,
        ),
        "pulse": lambda: run_pulse_loop(shutdown_event),
        "recognition": lambda: _run_recognition_loop(shutdown_event),
        "conductors": lambda: run_conductor_loop(shutdown_event),
        "context-agent": lambda: _run_gated_loop(
            "context-agent",
            shutdown_event,
            startup_ready_gate,
            lambda: run_context_agent_loop(shutdown_event, signal_bus=bus),
        ),
        "zeitgeist": lambda: _run_zeitgeist_loop(shutdown_event),
        "witness": lambda: _run_witness_loop(shutdown_event),
        "consolidation": lambda: _run_consolidation_loop(shutdown_event),
        "replication": lambda: _run_replication_monitor_loop(shutdown_event),
        "flywheel": lambda: run_training_flywheel_loop(shutdown_event),
        "health": lambda: run_health_loop(shutdown_event),
        "self-improve": lambda: run_self_improvement_loop(shutdown_event, interval=3600),
        "free-grind": lambda: run_free_evolution_grind(shutdown_event),
        # ── Fang 7: Self-Reading Archaeology ──
        # Ingests evolution archive, shared research, stigmergy marks, task
        # completions into MemoryPalace every 30 minutes. Produces
        # lessons_learned.md at ~/.dharma/meta/ — the anti-amnesia mechanism.
        "archaeology": lambda: _run_gated_loop(
            "archaeology",
            shutdown_event,
            startup_ready_gate,
            lambda: _run_archaeology_loop(shutdown_event),
        ),
        # ── cc_tool_marks consumer (Sprint 1 Fix 3) ──
        # Aggregates Claude Code tool-use observations every 5min. Closes the
        # Claude-Code → Dharma bridge. Writes ~/.dharma/meta/cc_tool_marks_signals.json.
        "cc-tool-marks": lambda: _run_gated_loop(
            "cc-tool-marks",
            shutdown_event,
            startup_ready_gate,
            lambda: _run_cc_tool_marks_loop(shutdown_event),
        ),
        # ── Guardian Crew: continuous interface + loop + router health checks ──
        # Runs at boot + every 4 hours. Writes GUARDIAN_REPORT.md.
        # Creates GitHub issues for BLOCKER-severity findings.
        "guardian": lambda: _run_guardian_loop(shutdown_event),
        # ── Gauntlet: adversarial eval pressure + DGM feedback loop ──
        "gauntlet": lambda: _run_gauntlet_loop(shutdown_event),
        # ── Research RTN: artifact-producing research pipeline ──
        # Cycles through 3 tracks (swarm/NeurIPS/market) every 30 minutes.
        # Produces graded research artifacts at ~/.dharma/artifacts/research/
        "research-rtn": lambda: _run_research_rtn_loop(shutdown_event),
        # ── ShaktiZeitgeistExecutive: strategic sensing + opportunity scoring ──
        # Phase 1: read-only. Ingests signals, scores opportunities, emits
        # executive artifacts at ~/.dharma/meta/ every 45 minutes.
        "executive": lambda: _run_executive_loop(shutdown_event),
        # ── Directive watcher: operator-facing injection socket ──
        # Polls ~/.dharma/directives/ every 5s. For each JSON directive file,
        # looks up the target conductor in ACTIVE_CONDUCTORS and calls
        # accept_task(). Unmatched/malformed directives move to
        # ~/.dharma/directives/_unmatched/ with a reason.
        "directives": lambda: _run_directives_loop(shutdown_event),
    }
    optional_clean_exit = {"pulse"}
    tasks = {
        name: asyncio.create_task(factory(), name=name)
        for name, factory in task_factories.items()
    }

    _log("orchestrator", f"All {len(tasks)} systems launched ({len(tasks)} loops incl. free-grind)")
    await asyncio.sleep(0)

    try:
        # Resilient loop: restart failed tasks instead of dying on first error.
        # Transient failures (e.g. "database is locked") should not kill all
        # 13 loops — just log, wait a beat, and let the system heal.
        max_restarts = 5
        restart_counts: dict[str, int] = {}

        while tasks and not shutdown_event.is_set():
            done, pending = await asyncio.wait(
                list(tasks.values()), return_when=asyncio.FIRST_COMPLETED, timeout=60.0,
            )
            if not done:
                continue  # timeout, check shutdown flag

            restart_queue: list[str] = []
            for t in done:
                name = t.get_name() or "unknown"
                tasks.pop(name, None)
                if t.cancelled():
                    if shutdown_event.is_set():
                        _log("orchestrator", f"System {name} cancelled during shutdown")
                    else:
                        _log("orchestrator", f"System {name} cancelled unexpectedly")
                        if name not in optional_clean_exit:
                            restart_queue.append(name)
                    continue

                exc = t.exception()
                if exc is not None:
                    _log("orchestrator", f"System {name} failed: {exc}")
                    restart_queue.append(name)
                    continue

                if shutdown_event.is_set() or name in optional_clean_exit:
                    _log("orchestrator", f"System {name} exited cleanly")
                else:
                    _log("orchestrator", f"System {name} exited unexpectedly; scheduling restart")
                    restart_queue.append(name)

            for name in restart_queue:
                count = restart_counts.get(name, 0) + 1
                restart_counts[name] = count
                if count <= max_restarts:
                    _log("orchestrator", f"Restarting {name} (attempt {count}/{max_restarts})")
                    if await _wait_or_shutdown(shutdown_event, min(count * 5, 30)):
                        break
                    tasks[name] = asyncio.create_task(task_factories[name](), name=name)
                else:
                    _log("orchestrator", f"System {name} exceeded max restarts, abandoning")

    except asyncio.CancelledError:
        pass
    finally:
        shutdown_event.set()
        for t in tasks.values():
            t.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        pid_file.unlink(missing_ok=True)
        _log("orchestrator", "All systems stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )
    bg = "--background" in sys.argv or "--bg" in sys.argv
    asyncio.run(orchestrate(background=bg))
