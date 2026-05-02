"""Catalytic graph endpoints — autocatalytic set detection via Tarjan SCC.

Exposes the graph of how artifacts catalyze each other,
detects self-sustaining loops, and identifies missing edges.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.models import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/catalytic", tags=["catalytic"])


def _get_graph():
    from api.main import get_catalytic_graph
    return get_catalytic_graph()


@router.get("/summary")
async def catalytic_summary() -> ApiResponse:
    """Node/edge counts, SCC count, autocatalytic sets, revenue-ready."""
    try:
        graph = _get_graph()
        return ApiResponse(data=graph.summary())
    except Exception as e:
        logger.warning("Catalytic summary failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/graph")
async def catalytic_graph() -> ApiResponse:
    """Full graph for visualization — nodes and edges."""
    try:
        graph = _get_graph()
        nodes_map = dict(getattr(graph, "_nodes", {})) if isinstance(getattr(graph, "_nodes", None), dict) else {}
        nodes = [
            {"id": nid, "metadata": meta if isinstance(meta, dict) else {}}
            for nid, meta in nodes_map.items()
        ]

        edges = []
        for edge in list(getattr(graph, "_edges", [])):
            edges.append({
                "source": getattr(edge, "source", ""),
                "target": getattr(edge, "target", ""),
                "edge_type": getattr(edge, "edge_type", "enables"),
                "strength": getattr(edge, "strength", 0.5),
                "evidence": getattr(edge, "evidence", ""),
            })

        return ApiResponse(data={"nodes": nodes, "edges": edges})
    except Exception as e:
        logger.warning("Catalytic graph failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/autocatalytic")
async def autocatalytic_sets() -> ApiResponse:
    """Detect autocatalytic sets — self-sustaining artifact loops."""
    try:
        graph = _get_graph()
        sets = graph.detect_autocatalytic_sets()
        return ApiResponse(data={
            "sets": sets,
            "count": len(sets),
            "largest": max(sets, key=len) if sets else [],
        })
    except Exception as e:
        logger.warning("Autocatalytic detection failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/priorities")
async def loop_closure_priorities() -> ApiResponse:
    """Missing edges ranked by loop-closing value."""
    try:
        graph = _get_graph()
        priorities = graph.loop_closure_priority()
        return ApiResponse(data=[
            {"source": src, "target": tgt, "value": val}
            for src, tgt, val in priorities[:50]
        ])
    except Exception as e:
        logger.warning("Loop closure priorities failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")


@router.get("/revenue-ready")
async def revenue_ready() -> ApiResponse:
    """Autocatalytic sets touching funds/attracts edges."""
    try:
        graph = _get_graph()
        sets = graph.revenue_ready_sets()
        return ApiResponse(data={"sets": sets, "count": len(sets)})
    except Exception as e:
        logger.warning("Revenue-ready sets failed: %s", e, exc_info=True)
        return ApiResponse(status="error", error="Internal error")
