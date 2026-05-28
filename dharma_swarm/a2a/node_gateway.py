"""Node Gateway — HTTP transport for the A2A fleet control plane.

A2A 1.0 spec-conformant HTTP transport with both standard and legacy endpoints.

Spec-standard endpoints (A2A 1.0):
  - GET  /.well-known/agent-card.json  — Agent card discovery
  - POST /tasks                         — submit a task
  - GET  /tasks/{task_id}               — poll task status + result
  - POST /tasks/{task_id}:cancel        — cancel a running task
  - POST /tasks/{task_id}:reject        — reject a task (A2A 1.0)
  - GET  /tasks/{task_id}:stream        — SSE streaming (A2A 1.0)
  - GET  /health                        — heartbeat / node status
  - GET  /skills                        — list skills (A2A 1.0 name)

Legacy endpoints (backward compat):
  - POST /a2a/tasks
  - GET  /a2a/tasks/{task_id}
  - POST /a2a/tasks/{task_id}/cancel
  - GET  /a2a/health
  - GET  /a2a/capabilities

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
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

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
    d = asdict(task)
    # Exclude the property alias from serialization
    d.pop("messages", None)
    return d


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_task_from_body(body: dict[str, Any]) -> A2ATask:
    """Parse an A2ATask from a request body."""
    messages: list[A2AMessage] = []
    for msg_data in body.get("messages", body.get("history", [])):
        messages.append(A2AMessage.text(
            msg_data.get("content", msg_data.get("text", "")),
            role=msg_data.get("role", "user"),
        ))

    if not messages and body.get("message"):
        messages = [A2AMessage.text(body["message"])]

    return A2ATask(
        from_agent=body.get("from_agent", "remote"),
        to_agent=body.get("to_agent", ""),
        capability=body.get("capability", ""),
        context_id=body.get("context_id", ""),
        history=messages,
        metadata=body.get("metadata", {}),
    )


def _health_payload() -> dict[str, Any]:
    """Build health check response payload."""
    task_counts: dict[str, int] = {}
    if _server is not None:
        for status in A2ATaskStatus:
            tasks = _server.list_tasks(status=status)
            if tasks:
                task_counts[status.value] = len(tasks)

    skills: list[str] = []
    if _node_card is not None:
        skills = _node_card.capability_names()

    return {
        "node_id": _node_id,
        "status": "online",
        "started_at": _started_at,
        "checked_at": _utc_now(),
        "task_counts": task_counts,
        "skills": skills,
        "capabilities": skills,  # backward compat
        "gateway_version": "2.0.0",
        "spec_version": "a2a-1.0",
    }


def _skills_payload() -> dict[str, Any]:
    """Build skills list response payload."""
    if _registry is None:
        return {"node_id": _node_id, "agents": []}

    cards = _registry.list_all()
    result = []
    for card in cards:
        result.append({
            "agent": card.name,
            "role": card.role,
            "status": card.status,
            "skills": [
                {
                    "id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "tags": skill.tags,
                }
                for skill in card.skills
            ],
        })

    return {"node_id": _node_id, "agents": result}


# ---------------------------------------------------------------------------
# A2A 1.0 spec-standard endpoints
# ---------------------------------------------------------------------------


@router.get("/.well-known/agent-card.json")
async def get_agent_card() -> JSONResponse:
    """Serve this node's A2A agent card (standard discovery endpoint)."""
    if _node_card is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    return JSONResponse(content=_node_card.to_dict())


@router.post("/tasks", dependencies=[Depends(_verify_api_key)])
async def submit_task_v1(request: Request) -> JSONResponse:
    """Submit a task (A2A 1.0 spec path)."""
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    body = await request.json()
    task = _parse_task_from_body(body)
    result = _server.submit(task)
    return JSONResponse(
        content=_task_to_dict(result),
        status_code=201 if result.status != A2ATaskStatus.FAILED else 422,
    )


# Colon-action routes MUST be registered before the generic /tasks/{task_id}
# so FastAPI's route matching doesn't greedily capture the suffix.


@router.post("/tasks/{task_id}:cancel", dependencies=[Depends(_verify_api_key)])
async def cancel_task_v1(task_id: str) -> JSONResponse:
    """Cancel a task (A2A 1.0 spec path with colon syntax)."""
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    if not _server.cancel(task_id):
        raise HTTPException(
            status_code=409,
            detail=f"Task {task_id} cannot be cancelled (not found or already terminal)",
        )
    return JSONResponse(content={"task_id": task_id, "status": "cancelled"})


@router.post("/tasks/{task_id}:reject", dependencies=[Depends(_verify_api_key)])
async def reject_task_v1(task_id: str, request: Request) -> JSONResponse:
    """Reject a task (A2A 1.0)."""
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    body = await request.json()
    reason = body.get("reason", "")
    if not _server.reject(task_id, reason):
        raise HTTPException(
            status_code=409,
            detail=f"Task {task_id} cannot be rejected (not found or already terminal)",
        )
    return JSONResponse(content={"task_id": task_id, "status": "rejected", "reason": reason})


async def _sse_task_stream(task_id: str) -> Any:
    """Generate SSE events for a task until it reaches terminal state."""
    import asyncio
    while True:
        if _server is None:
            yield "event: error\ndata: {\"error\": \"server unavailable\"}\n\n"
            return
        task = _server.get_task(task_id)
        if task is None:
            yield "event: error\ndata: {\"error\": \"task not found\"}\n\n"
            return
        payload = json.dumps(_task_to_dict(task))
        yield f"event: statusUpdate\ndata: {payload}\n\n"
        if task.is_terminal():
            return
        await asyncio.sleep(0.5)


@router.get("/tasks/{task_id}:stream", dependencies=[Depends(_verify_api_key)])
async def stream_task_v1(task_id: str) -> StreamingResponse:
    """SSE stream for task lifecycle events (A2A 1.0)."""
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    task = _server.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return StreamingResponse(
        _sse_task_stream(task_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Generic task retrieval AFTER colon-action routes
@router.get("/tasks/{task_id}", dependencies=[Depends(_verify_api_key)])
async def get_task_v1(task_id: str) -> JSONResponse:
    """Get task status (A2A 1.0 spec path)."""
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    task = _server.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return JSONResponse(content=_task_to_dict(task))


@router.get("/health")
async def health_check_v1() -> JSONResponse:
    """Heartbeat (A2A 1.0 spec path)."""
    return JSONResponse(content=_health_payload())


@router.get("/skills", dependencies=[Depends(_verify_api_key)])
async def list_skills_v1() -> JSONResponse:
    """List skills on this node (A2A 1.0 spec name)."""
    if _registry is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    return JSONResponse(content=_skills_payload())


# ---------------------------------------------------------------------------
# Legacy endpoints (backward compat)
# ---------------------------------------------------------------------------


@router.post("/a2a/tasks", dependencies=[Depends(_verify_api_key)])
async def submit_task_legacy(request: Request) -> JSONResponse:
    """Submit a task (legacy path)."""
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    body = await request.json()
    task = _parse_task_from_body(body)
    result = _server.submit(task)
    return JSONResponse(
        content=_task_to_dict(result),
        status_code=201 if result.status != A2ATaskStatus.FAILED else 422,
    )


@router.get("/a2a/tasks/{task_id}", dependencies=[Depends(_verify_api_key)])
async def get_task_legacy(task_id: str) -> JSONResponse:
    """Get task status (legacy path)."""
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    task = _server.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return JSONResponse(content=_task_to_dict(task))


@router.post("/a2a/tasks/{task_id}/cancel", dependencies=[Depends(_verify_api_key)])
async def cancel_task_legacy(task_id: str) -> JSONResponse:
    """Cancel a task (legacy path)."""
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    if not _server.cancel(task_id):
        raise HTTPException(
            status_code=409,
            detail=f"Task {task_id} cannot be cancelled (not found or already terminal)",
        )
    return JSONResponse(content={"task_id": task_id, "status": "cancelled"})


@router.get("/a2a/health")
async def health_check_legacy() -> JSONResponse:
    """Heartbeat (legacy path)."""
    return JSONResponse(content=_health_payload())


@router.get("/a2a/capabilities", dependencies=[Depends(_verify_api_key)])
async def list_capabilities_legacy() -> JSONResponse:
    """List capabilities (legacy path, delegates to skills)."""
    if _registry is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    return JSONResponse(content=_skills_payload())
