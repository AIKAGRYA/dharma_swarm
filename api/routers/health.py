"""Health + anomaly detection endpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from api.models import (
    AgentHealthOut,
    AnomalyOut,
    ApiResponse,
    HealthOut,
    SwarmOverview,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _get_deps():
    """Lazy-load dharma_swarm dependencies."""
    from api.main import get_swarm, get_trace_store, get_monitor
    return get_swarm(), get_trace_store(), get_monitor()


def _runtime_truth_closeout() -> dict[str, Any]:
    """Evaluate the live runtime truth gate on demand for operator UI use."""
    from dharma_swarm.operator_core.live_ops_census_contract import DEFAULT_STATE_ROOT
    from scripts.runtime.runtime_truth_closeout import _build_census, evaluate_closeout

    state_root = DEFAULT_STATE_ROOT
    census = _build_census(_REPO_ROOT, state_root)
    return evaluate_closeout(census, state_root=state_root)


def _health_out_with_runtime_truth(health: HealthOut) -> HealthOut:
    try:
        runtime_truth = _runtime_truth_closeout()
    except Exception as exc:
        health.runtime_truth = {
            "schema_version": "runtime_truth_closeout.v1",
            "status": "error",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        health.overall_status = "degraded"
        return health

    health.runtime_truth = runtime_truth
    if runtime_truth.get("passed") is not True:
        health.overall_status = "degraded"
    return health


@router.get("/health")
async def health_check(
    deep: bool = Query(
        False,
        description=(
            "Run the expensive monitor-backed swarm health scan. The default "
            "response is API liveness only so launchd and cockpit probes stay fast."
        ),
    ),
    runtime_truth: bool = Query(
        False,
        description=(
            "Attach the live runtime truth closeout. This is operator/cockpit "
            "truth, not a cheap liveness probe."
        ),
    ),
) -> ApiResponse:
    if not deep:
        health = HealthOut(overall_status="healthy")
        if runtime_truth:
            health = _health_out_with_runtime_truth(health)
        return ApiResponse(data=health.model_dump())

    _, _, monitor = _get_deps()
    try:
        report = await monitor.check_health()
        return _health_report_response(report, runtime_truth=runtime_truth)
    except Exception as e:
        health = HealthOut(overall_status="unknown")
        if runtime_truth:
            health = _health_out_with_runtime_truth(health)
        return ApiResponse(data=health.model_dump(), error=str(e))


def _health_report_response(report, *, runtime_truth: bool = False) -> ApiResponse:  # noqa: ANN001
    health = HealthOut(
        overall_status=report.overall_status.value if hasattr(report.overall_status, 'value') else str(report.overall_status),
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
            for a in report.anomalies
        ],
        total_traces=report.total_traces,
        traces_last_hour=report.traces_last_hour,
        failure_rate=report.failure_rate,
        mean_fitness=report.mean_fitness,
    )
    if runtime_truth:
        health = _health_out_with_runtime_truth(health)
    return ApiResponse(data=health.model_dump())


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
