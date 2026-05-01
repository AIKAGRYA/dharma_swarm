"""Health + anomaly detection endpoints."""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter

from api.models import (
    AgentHealthOut,
    AnomalyOut,
    ApiResponse,
    HealthOut,
    SwarmOverview,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


def _daemon_base_url() -> str:
    return os.environ.get("DHARMA_DAEMON_URL", "http://127.0.0.1:7433").rstrip("/")


async def _fetch_daemon_health() -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{_daemon_base_url()}/health")
            response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except Exception:
        logger.debug("Failed to fetch daemon health for API blending", exc_info=True)
        return None


def _get_deps():
    """Lazy-load dharma_swarm dependencies."""
    from api.main import get_swarm, get_trace_store, get_monitor
    return get_swarm(), get_trace_store(), get_monitor()


@router.get("/health")
async def health_check() -> ApiResponse:
    _, trace_store, monitor = _get_deps()
    try:
        report = await monitor.check_health()
        daemon = await _fetch_daemon_health()

        daemon_status = str(daemon.get("status", "")).lower() if daemon else ""
        daemon_liveness = daemon.get("liveness", {}) if isinstance(daemon, dict) else {}
        daemon_liveness_status = str(daemon_liveness.get("status", "")).lower()
        daemon_costs_1h = daemon.get("costs", {}).get("1h", {}) if daemon else {}
        daemon_calls_1h = int(daemon_costs_1h.get("calls", 0) or 0) if daemon else 0
        daemon_live = daemon_status == "ok" and daemon_calls_1h > 0

        anomalies = []
        for a in report.anomalies:
            if (
                daemon_live
                and a.anomaly_type == "agent_silent"
                and any(
                    token in a.description
                    for token in ("darwin_engine", "darwin_planner", "organism")
                )
            ):
                continue
            anomalies.append(a)

        overall_status = report.overall_status.value if hasattr(report.overall_status, 'value') else str(report.overall_status)
        if daemon_liveness_status == "stalled":
            overall_status = "critical"
        elif daemon_liveness_status in {"booting", "degraded"} and overall_status not in {"critical", "degraded"}:
            overall_status = "degraded"
        if daemon_live and report.failure_rate == 0.0:
            has_high = any(a.severity == "high" for a in anomalies)
            has_medium = any(a.severity == "medium" for a in anomalies)
            if has_high:
                overall_status = "critical"
            elif has_medium:
                overall_status = "degraded"
            else:
                overall_status = "healthy"

        return ApiResponse(data=HealthOut(
            overall_status=overall_status,
            agent_health=[
                AgentHealthOut(
                    agent_name=ah.agent_name,
                    total_actions=ah.total_actions,
                    failures=ah.failures,
                    success_rate=ah.success_rate,
                    last_seen=str(ah.last_seen) if ah.last_seen else None,
                    status=ah.status.value if hasattr(ah.status, 'value') else str(ah.status),
                )
                for ah in report.agent_health
            ],
            anomalies=[
                AnomalyOut(
                    id=a.id,
                    detected_at=str(a.detected_at),
                    anomaly_type=a.anomaly_type,
                    severity=a.severity,
                    description=a.description,
                    related_traces=a.related_traces,
                )
                for a in anomalies
            ],
            total_traces=report.total_traces,
            traces_last_hour=max(report.traces_last_hour, daemon_calls_1h),
            failure_rate=report.failure_rate,
            mean_fitness=report.mean_fitness,
            liveness=daemon_liveness if isinstance(daemon_liveness, dict) else {},
        ).model_dump())
    except Exception as e:
        return ApiResponse(data=HealthOut(overall_status="unknown").model_dump(), error=str(e))


@router.get("/health/anomalies")
async def get_anomalies(window_hours: float = 1) -> ApiResponse:
    _, _, monitor = _get_deps()
    anomalies = await monitor.detect_anomalies(window_hours=window_hours)
    return ApiResponse(data=[
        AnomalyOut(
            id=a.id,
            detected_at=str(a.detected_at),
            anomaly_type=a.anomaly_type,
            severity=a.severity,
            description=a.description,
            related_traces=a.related_traces,
        ).model_dump()
        for a in anomalies
    ])


@router.get("/overview")
async def overview() -> ApiResponse:
    """Combined swarm overview for the dashboard L1."""
    swarm, trace_store, monitor = _get_deps()

    agent_count = 0
    tasks_pending = 0
    tasks_running = 0
    tasks_completed = 0
    tasks_failed = 0
    uptime = 0.0

    try:
        status = await swarm.status()
        agent_count = len(status.agents)
        tasks_pending = status.tasks_pending
        tasks_running = status.tasks_running
        tasks_completed = status.tasks_completed
        tasks_failed = status.tasks_failed
        uptime = status.uptime_seconds
    except Exception:
        logger.debug("Failed to fetch swarm status for overview", exc_info=True)

    health_status = "unknown"
    try:
        report = await monitor.check_health()
        health_status = report.overall_status.value if hasattr(report.overall_status, 'value') else str(report.overall_status)
    except Exception:
        logger.debug("Failed to check health for overview", exc_info=True)
    try:
        daemon = await _fetch_daemon_health()
        daemon_liveness = daemon.get("liveness", {}) if isinstance(daemon, dict) else {}
        daemon_liveness_status = str(daemon_liveness.get("status", "")).lower()
        if daemon_liveness_status == "stalled":
            health_status = "critical"
        elif daemon_liveness_status in {"booting", "degraded"} and health_status not in {"critical", "degraded"}:
            health_status = "degraded"
    except Exception:
        logger.debug("Failed to blend daemon liveness into overview", exc_info=True)

    mean_fitness = 0.0
    evolution_entries = 0
    try:
        from dharma_swarm.archive import EvolutionArchive
        archive = EvolutionArchive()
        await archive.load()
        entries = await archive.list_entries()
        evolution_entries = len(entries)
        if entries:
            fitnesses = [e.fitness.weighted() for e in entries]
            mean_fitness = sum(fitnesses) / len(fitnesses)
    except Exception:
        logger.debug("Failed to load evolution archive for overview", exc_info=True)

    stig_density = 0
    try:
        from dharma_swarm.stigmergy import StigmergyStore
        stig = StigmergyStore()
        stig_density = stig.density()
    except Exception:
        logger.debug("Failed to read stigmergy density for overview", exc_info=True)

    return ApiResponse(data=SwarmOverview(
        agent_count=agent_count,
        task_count=tasks_pending + tasks_running + tasks_completed + tasks_failed,
        tasks_pending=tasks_pending,
        tasks_running=tasks_running,
        tasks_completed=tasks_completed,
        tasks_failed=tasks_failed,
        mean_fitness=round(mean_fitness, 4),
        uptime_seconds=uptime,
        health_status=health_status,
        stigmergy_density=stig_density,
        evolution_entries=evolution_entries,
    ).model_dump())
