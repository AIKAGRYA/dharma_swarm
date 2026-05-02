"""Strange loop endpoints — organism self-modification engine.

Exposes mutation history, current organism config, and loop statistics.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Query

from api.models import ApiResponse
from dharma_swarm.runtime_config import dharma_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strange-loop", tags=["strange-loop"])

_MUTATIONS_FILE = dharma_path("organism_memory", "mutations.jsonl")


def _get_strange_loop():
    """Access strange loop via swarm organism."""
    from api.main import get_swarm
    swarm = get_swarm()
    if hasattr(swarm, "organism") and swarm.organism and hasattr(swarm.organism, "strange_loop"):
        return swarm.organism.strange_loop
    return None


@router.get("/stats")
async def strange_loop_stats() -> ApiResponse:
    """Mutation counts, kept/reverted ratio, current config snapshot."""
    try:
        sl = _get_strange_loop()
        if sl is None:
            return ApiResponse(data=_stats_from_file())
        return ApiResponse(data=sl.stats)
    except Exception as e:
        logger.warning("Strange loop stats failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/mutations")
async def mutation_history(
    limit: int = Query(50, ge=1, le=500),
) -> ApiResponse:
    """Full mutation history from ~/.dharma/organism_memory/mutations.jsonl."""
    try:
        sl = _get_strange_loop()
        if sl and hasattr(sl, "_mutations"):
            mutations = sl._mutations[-limit:]
            return ApiResponse(data=[
                {
                    "id": getattr(m, "id", ""),
                    "parameter": getattr(m, "parameter", ""),
                    "old_value": getattr(m, "old_value", None),
                    "new_value": getattr(m, "new_value", None),
                    "reason": getattr(m, "reason", ""),
                    "proposed_at": str(getattr(m, "proposed_at", "")),
                    "applied_at": str(getattr(m, "applied_at", "")),
                    "reverted_at": str(getattr(m, "reverted_at", "")),
                    "gnani_verdict": getattr(m, "gnani_verdict", None),
                    "kept": getattr(m, "kept", None),
                }
                for m in reversed(mutations)
            ])

        return ApiResponse(data=_mutations_from_file(limit))
    except Exception as e:
        logger.warning("Mutation history failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/config")
async def organism_config() -> ApiResponse:
    """Current organism configuration parameters."""
    try:
        sl = _get_strange_loop()
        if sl and hasattr(sl, "config"):
            cfg = sl.config
            return ApiResponse(data={
                k: getattr(cfg, k) for k in vars(cfg) if not k.startswith("_")
            })
        return ApiResponse(data={})
    except Exception as e:
        logger.warning("Organism config failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


def _mutations_from_file(limit: int) -> list[dict]:
    """Fallback: read mutations directly from JSONL file."""
    if not _MUTATIONS_FILE.exists():
        return []
    entries = []
    try:
        for line in _MUTATIONS_FILE.read_text(encoding="utf-8").strip().splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return entries[-limit:][::-1]


def _stats_from_file() -> dict:
    """Fallback: compute stats from file when organism not available."""
    mutations = _mutations_from_file(500)
    kept = sum(1 for m in mutations if m.get("kept") is True)
    reverted = sum(1 for m in mutations if m.get("kept") is False)
    return {
        "total_mutations": len(mutations),
        "kept": kept,
        "reverted": reverted,
        "pending": len(mutations) - kept - reverted,
        "current_config": {},
    }
