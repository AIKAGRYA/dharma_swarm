"""Cascade / LoopEngine endpoints — universal strange loop convergence.

Exposes registered domains, convergence history, and checkpoint state.
Named cascade_router.py to avoid collision with dharma_swarm/cascade.py.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Query

from api.models import ApiResponse
from dharma_swarm.runtime_config import dharma_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cascade", tags=["cascade"])

_HISTORY_FILE = dharma_path("meta", "cascade_history.jsonl")
_CHECKPOINT_DIR = dharma_path("checkpoints")


@router.get("/domains")
async def registered_domains() -> ApiResponse:
    """All registered cascade domains and their configs."""
    try:
        from dharma_swarm.cascade import get_registered_domains
        domains = get_registered_domains()
        return ApiResponse(data={
            name: {
                "name": getattr(d, "name", name),
                "max_iterations": getattr(d, "max_iterations", 0),
                "max_duration_seconds": getattr(d, "max_duration_seconds", 0),
                "fitness_threshold": getattr(d, "fitness_threshold", 0),
                "eigenform_epsilon": getattr(d, "eigenform_epsilon", 0),
                "convergence_window": getattr(d, "convergence_window", 0),
                "mutation_rate": getattr(d, "mutation_rate", 0),
            }
            for name, d in domains.items()
        })
    except Exception as e:
        logger.warning("Cascade domains failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/history")
async def cascade_history(
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse:
    """Recent domain completion records from cascade_history.jsonl."""
    try:
        if not _HISTORY_FILE.exists():
            return ApiResponse(data=[])

        entries = []
        for line in _HISTORY_FILE.read_text(encoding="utf-8").strip().splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        return ApiResponse(data=entries[-limit:][::-1])
    except Exception as e:
        logger.warning("Cascade history failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/checkpoints")
async def active_checkpoints() -> ApiResponse:
    """Active checkpoints from ~/.dharma/checkpoints/."""
    try:
        if not _CHECKPOINT_DIR.exists():
            return ApiResponse(data=[])

        checkpoints = []
        for f in sorted(_CHECKPOINT_DIR.glob("*.json"), reverse=True)[:20]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                checkpoints.append({
                    "filename": f.name,
                    "domain": data.get("domain", ""),
                    "cycle_id": data.get("cycle_id", ""),
                    "iteration": data.get("iteration", 0),
                    "best_fitness": data.get("best_fitness", 0),
                    "timestamp": data.get("timestamp", ""),
                })
            except (json.JSONDecodeError, OSError):
                continue

        return ApiResponse(data=checkpoints)
    except Exception as e:
        logger.warning("Cascade checkpoints failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")
