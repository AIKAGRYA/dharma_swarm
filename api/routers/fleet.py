"""Fleet management API — dashboard-facing endpoints for the node registry.

Provides REST endpoints for:
  - Listing all fleet nodes and their statuses
  - Registering / updating / removing nodes
  - Triggering health checks
  - Dispatching tasks to remote nodes
  - Querying fleet-wide capabilities

All routes are under /api/fleet/ and require the standard dashboard auth.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from dharma_swarm.a2a.node_registry import (
    NodeRegistry,
    RemoteNode,
    dispatch_remote_task,
)

logger = logging.getLogger(__name__)

_LOG_SANITIZE_RE = re.compile(r"[\r\n\x00-\x1f\x7f]")


def _sanitize(value: object) -> str:
    return _LOG_SANITIZE_RE.sub("_", str(value))

router = APIRouter(prefix="/api/fleet", tags=["fleet"])

_registry: NodeRegistry | None = None


def _get_registry() -> NodeRegistry:
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = NodeRegistry()
    return _registry


@router.get("/nodes")
async def list_nodes() -> JSONResponse:
    """List all fleet nodes with current status."""
    reg = _get_registry()
    nodes = reg.list_all()
    return JSONResponse(content={
        "count": len(nodes),
        "nodes": [n.to_dict() for n in nodes],
    })


@router.get("/nodes/{node_id}")
async def get_node(node_id: str) -> JSONResponse:
    """Get a specific node's details."""
    reg = _get_registry()
    node = reg.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return JSONResponse(content=node.to_dict())


@router.post("/nodes")
async def register_node(request_body: dict[str, Any]) -> JSONResponse:
    """Register or update a fleet node.

    Body: {"node_id": "agni", "endpoint": "http://...", "ssh_alias": "agni"}
    """
    node_id = request_body.get("node_id", "")
    if not node_id:
        raise HTTPException(status_code=400, detail="node_id is required")

    reg = _get_registry()
    known = {f.name for f in RemoteNode.__dataclass_fields__.values()}
    filtered = {k: v for k, v in request_body.items() if k in known}
    node = RemoteNode(**filtered)
    reg.register(node)
    return JSONResponse(content=node.to_dict(), status_code=201)


@router.delete("/nodes/{node_id}")
async def unregister_node(node_id: str) -> JSONResponse:
    """Remove a node from the fleet."""
    reg = _get_registry()
    removed = reg.unregister(node_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    return JSONResponse(content={"removed": node_id})


@router.post("/nodes/{node_id}/health")
async def check_node_health(node_id: str) -> JSONResponse:
    """Trigger a health check for a specific node."""
    reg = _get_registry()
    node = reg.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
    updated = await reg.health_check(node_id)
    return JSONResponse(content=updated.to_dict())


@router.post("/health-check-all")
async def check_all_health() -> JSONResponse:
    """Trigger health checks for all nodes."""
    reg = _get_registry()
    results = await reg.health_check_all()
    return JSONResponse(content={
        "checked": len(results),
        "nodes": [n.to_dict() for n in results],
    })


@router.get("/capabilities")
async def fleet_capabilities() -> JSONResponse:
    """List capabilities available across the fleet."""
    reg = _get_registry()
    cap_map: dict[str, list[str]] = {}
    for node in reg.list_online():
        for cap in node.capabilities:
            cap_map.setdefault(cap, []).append(node.node_id)
    return JSONResponse(content={"capabilities": cap_map})


@router.post("/dispatch")
async def dispatch_task(body: dict[str, Any]) -> JSONResponse:
    """Dispatch a task to a specific remote node.

    Body: {"node_id": "agni", "capability": "code_review",
           "message": "Review auth module", "metadata": {}}
    """
    node_id = body.get("node_id", "")
    capability = body.get("capability", "")
    message = body.get("message", "")

    if not node_id or not message:
        raise HTTPException(
            status_code=400,
            detail="node_id and message are required",
        )

    reg = _get_registry()
    node = reg.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")

    if not node.is_reachable():
        raise HTTPException(
            status_code=503,
            detail=f"Node {node_id} is not reachable (status={node.status})",
        )

    try:
        result = await dispatch_remote_task(
            node=node,
            capability=capability,
            message=message,
            from_agent=body.get("from_agent", "dashboard"),
            metadata=body.get("metadata"),
        )
        return JSONResponse(content=result, status_code=201)
    except Exception as exc:
        logger.error("Fleet dispatch to %s failed: %s", _sanitize(node_id), exc)
        raise HTTPException(
            status_code=502,
            detail=f"Dispatch to {node_id} failed: {exc}",
        ) from exc
