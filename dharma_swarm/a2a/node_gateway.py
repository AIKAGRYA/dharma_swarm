"""Node Gateway — HTTP transport for the A2A fleet control plane.

Each VPS runs a node gateway that exposes:
  - GET  /.well-known/agent-card.json  — A2A standard agent card
  - POST /a2a/tasks                     — submit a task for execution
  - GET  /a2a/tasks/{task_id}           — poll task status + result
  - POST /a2a/tasks/{task_id}/cancel    — cancel a running task
  - GET  /a2a/health                    — heartbeat / node status
  - GET  /a2a/capabilities              — list local capabilities

The gateway is a thin HTTP skin over the existing A2AServer.
Business logic, task lifecycle, and handler dispatch are all delegated
to the local A2AServer instance.  Dharma owns global truth; the gateway
owns local execution.

Four-question discipline (Contemplative Spine §11):
  1. Which loop?  Central metabolic: opportunity → dispatch → outcome → feedback
  2. Which membrane?  Network boundary between Dharma hub and remote nodes
  3. What artifact?  A2ATask with full lifecycle metadata, streamed back to hub
  4. Self-correcting?  Health endpoint + heartbeat lets Guardian detect failures

Security:
  - API key auth via X-A2A-Key header
  - Allowed keys loaded from ~/.dharma/a2a/allowed_keys.json
  - No key file = gateway rejects all remote requests (safe default)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from dharma_swarm.a2a.a2a_server import (
    A2AMessage,
    A2AServer,
    A2ATask,
    A2ATaskStatus,
)
from dharma_swarm.a2a.agent_card import AgentCard, CardRegistry
from dharma_swarm.daemon_config import dharma_state_dir

logger = logging.getLogger(__name__)

_STATE_DIR = dharma_state_dir("DHARMA_HOME")
_KEYS_PATH = _STATE_DIR / "a2a" / "allowed_keys.json"

router = APIRouter(tags=["a2a-gateway"])

# ---------------------------------------------------------------------------
# Singleton state — initialized by init_gateway()
# ---------------------------------------------------------------------------

_server: A2AServer | None = None
_registry: CardRegistry | None = None
_node_card: AgentCard | None = None
_allowed_keys: set[str] = set()
_node_id: str = "unknown"
_started_at: str = ""


def init_gateway(
    server: A2AServer,
    registry: CardRegistry,
    node_card: AgentCard,
    node_id: str = "dharma-hub",
) -> None:
    """Initialize the gateway with local A2A infrastructure.

    Must be called before the router handles any requests.
    Typically called during FastAPI lifespan startup.

    Args:
        server: The local A2AServer that handles task dispatch.
        registry: The local CardRegistry for capability discovery.
        node_card: This node's AgentCard (served at /.well-known/).
        node_id: Unique identifier for this node in the fleet.
    """
    global _server, _registry, _node_card, _node_id, _started_at  # noqa: PLW0603
    _server = server
    _registry = registry
    _node_card = node_card
    _node_id = node_id
    _started_at = datetime.now(timezone.utc).isoformat()
    _load_allowed_keys()
    logger.info("Node gateway initialized: node_id=%s", node_id)


def _load_allowed_keys() -> None:
    """Load API keys from the keys file."""
    global _allowed_keys  # noqa: PLW0603
    if not _KEYS_PATH.exists():
        _allowed_keys = set()
        return
    try:
        data = json.loads(_KEYS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            _allowed_keys = {str(k) for k in data if k}
        elif isinstance(data, dict):
            _allowed_keys = {str(k) for k in data.get("keys", []) if k}
        else:
            _allowed_keys = set()
    except Exception as exc:
        logger.warning("Failed to load allowed keys from %s: %s", _KEYS_PATH, exc)
        _allowed_keys = set()


def _verify_api_key(request: Request) -> None:
    """Validate X-A2A-Key header against allowed keys.

    If no keys file exists, all remote requests are rejected (safe default).
    Local requests (from 127.0.0.1) bypass auth for development.
    """
    client_host = request.client.host if request.client else ""
    if client_host in ("127.0.0.1", "::1", "localhost"):
        return

    if not _allowed_keys:
        raise HTTPException(
            status_code=403,
            detail="No API keys configured. Remote access denied.",
        )

    key = request.headers.get("X-A2A-Key", "")
    if key not in _allowed_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing X-A2A-Key")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _task_to_dict(task: A2ATask) -> dict[str, Any]:
    """Serialize an A2ATask to a JSON-safe dict."""
    return asdict(task)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/.well-known/agent-card.json")
async def get_agent_card() -> JSONResponse:
    """Serve this node's A2A agent card (standard discovery endpoint)."""
    if _node_card is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    return JSONResponse(content=_node_card.to_dict())


@router.post("/a2a/tasks", dependencies=[Depends(_verify_api_key)])
async def submit_task(request: Request) -> JSONResponse:
    """Submit a task for local execution.

    Request body: JSON matching A2ATask fields.
    Required: from_agent, capability or to_agent, messages (list of dicts).
    """
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    body = await request.json()

    messages = []
    for msg_data in body.get("messages", []):
        messages.append(A2AMessage.text(
            msg_data.get("content", msg_data.get("text", "")),
            role=msg_data.get("role", "user"),
        ))

    if not messages and body.get("message"):
        messages = [A2AMessage.text(body["message"])]

    task = A2ATask(
        from_agent=body.get("from_agent", "remote"),
        to_agent=body.get("to_agent", ""),
        capability=body.get("capability", ""),
        messages=messages,
        metadata=body.get("metadata", {}),
    )
    if body.get("correlation_id"):
        task.correlation_id = body["correlation_id"]

    result = _server.submit(task)
    return JSONResponse(
        content=_task_to_dict(result),
        status_code=201 if result.status != A2ATaskStatus.FAILED else 422,
    )


@router.get("/a2a/tasks/{task_id}", dependencies=[Depends(_verify_api_key)])
async def get_task(task_id: str) -> JSONResponse:
    """Get the current status and result of a task."""
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    task = _server.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return JSONResponse(content=_task_to_dict(task))


@router.post("/a2a/tasks/{task_id}/cancel", dependencies=[Depends(_verify_api_key)])
async def cancel_task(task_id: str) -> JSONResponse:
    """Cancel a running task."""
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    cancelled = _server.cancel(task_id)
    if not cancelled:
        raise HTTPException(
            status_code=409,
            detail=f"Task {task_id} cannot be cancelled (not found or already terminal)",
        )

    return JSONResponse(content={"task_id": task_id, "status": "cancelled"})


@router.get("/a2a/health")
async def health_check() -> JSONResponse:
    """Heartbeat endpoint for fleet health monitoring.

    Returns node status, uptime, task counts, and capability list.
    No auth required (health checks must work without credentials).
    """
    task_counts: dict[str, int] = {}
    if _server is not None:
        for status in A2ATaskStatus:
            tasks = _server.list_tasks(status=status)
            if tasks:
                task_counts[status.value] = len(tasks)

    capabilities: list[str] = []
    if _node_card is not None:
        capabilities = _node_card.capability_names()

    return JSONResponse(content={
        "node_id": _node_id,
        "status": "online",
        "started_at": _started_at,
        "checked_at": _utc_now(),
        "task_counts": task_counts,
        "capabilities": capabilities,
        "gateway_version": "1.0.0",
    })


@router.get("/a2a/capabilities", dependencies=[Depends(_verify_api_key)])
async def list_capabilities() -> JSONResponse:
    """List all capabilities available on this node."""
    if _registry is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    cards = _registry.list_all()
    result = []
    for card in cards:
        result.append({
            "agent": card.name,
            "role": card.role,
            "status": card.status,
            "capabilities": [
                {"name": cap.name, "description": cap.description}
                for cap in card.capabilities
            ],
        })

    return JSONResponse(content={"node_id": _node_id, "agents": result})
