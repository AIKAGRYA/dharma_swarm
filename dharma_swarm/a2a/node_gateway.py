"""Node Gateway — HTTP transport for the A2A fleet control plane.

Dharma Swarm Tier-1 HTTP gateway subset of the A2A 1.0 specification.
This implements the core task lifecycle operations over HTTP+JSON but does
NOT cover the full A2A 1.0 transport surface.  Specifically:

  Implemented (Tier 1):
    - Task submit, poll, cancel, reject
    - SSE streaming (statusUpdate events for a single task)
    - Agent card discovery at /.well-known/agent-card.json
    - API key authentication (X-A2A-Key header)
    - Skills listing

  Not yet implemented (future follow-up):
    - message:send / message:stream semantics (distinct from task submit)
    - task subscribe semantics (if distinct from current SSE stream)
    - Push notification config registration (POST /tasks/{id}/pushNotificationConfigs)
    - Full StreamResponse event typing (task, message, statusUpdate, artifactUpdate)
    - Ordering and fanout guarantees for concurrent SSE subscribers
    - gRPC / NATS transport bindings (Tier 2)
    - OAuth2 / mTLS / JWS enforcement (Tier 2)

Four-question discipline (Contemplative Spine §11):
  1. Which loop?  Central metabolic: opportunity → dispatch → outcome → feedback
  2. Which membrane?  Network boundary between Dharma hub and remote nodes
  3. What artifact?  A2ATask with full lifecycle metadata, streamed back to hub
  4. Self-correcting?  Health endpoint + heartbeat lets Guardian detect failures

Security:
  - API key auth via X-A2A-Key header (enforced on all requests)
  - Allowed keys loaded from ~/.dharma/a2a/allowed_keys.json
  - No key file = gateway rejects all requests (safe default)
  - Localhost bypass ONLY when A2A_ALLOW_LOCAL_NOAUTH=1 is set (dev only)
  - Behind reverse proxy: localhost bypass is disabled by default to prevent
    auth bypass when request.client.host resolves to proxy's local address
  - OAuth2/mTLS/JWS are declared in AgentCard but not yet enforced (Tier 2)
"""

from __future__ import annotations

import json
import logging
import os
import uuid
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
from dharma_swarm.a2a.spine_adapter import submit_task_via_spine
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
_initialization_error: str = ""


def mark_gateway_degraded(error_type: str) -> None:
    """Record a safe startup failure class without exposing exception details."""
    global _server, _registry, _node_card, _node_id, _started_at, _initialization_error  # noqa: PLW0603
    _server = None
    _registry = None
    _node_card = None
    _node_id = "unknown"
    _started_at = ""
    _initialization_error = str(error_type or "GatewayInitializationError")


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
    global _server, _registry, _node_card, _node_id, _started_at, _initialization_error  # noqa: PLW0603
    try:
        _load_allowed_keys()
    except Exception as exc:
        mark_gateway_degraded(type(exc).__name__)
        raise
    _server = server
    _registry = registry
    _node_card = node_card
    _node_id = node_id
    _started_at = datetime.now(timezone.utc).isoformat()
    _initialization_error = ""
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
    Local requests bypass auth ONLY when A2A_ALLOW_LOCAL_NOAUTH=1 is set.
    This prevents accidental auth bypass behind reverse proxies where
    request.client.host resolves to the proxy's local address.
    """
    client_host = request.client.host if request.client else ""
    if client_host in ("127.0.0.1", "::1", "localhost"):
        if os.environ.get("A2A_ALLOW_LOCAL_NOAUTH") == "1":
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
    metadata = dict(d.get("metadata") or {})
    for key in (
        "run_id",
        "runtime_run_id",
        "correlation_id",
        "idempotency_key",
        "claim_id",
        "external_a2a_task_id",
    ):
        if metadata.get(key):
            d[key] = metadata[key]
    # Strip internal validation flags from serialized parts
    _strip_internal_fields(d)
    return d


def _strip_internal_fields(obj: Any) -> None:
    """Recursively remove internal fields (prefixed with _) from dicts."""
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if key.startswith("_"):
                del obj[key]
            else:
                _strip_internal_fields(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            _strip_internal_fields(item)


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

    metadata = dict(body.get("metadata", {}) or {})
    for key in (
        "run_id",
        "runtime_run_id",
        "correlation_id",
        "causation_id",
        "parent_run_id",
        "claim_id",
        "idempotency_key",
        "session_id",
        "task_id",
    ):
        if body.get(key):
            metadata[key] = body[key]

    task = A2ATask(
        id=str(body.get("id") or body.get("task_id") or "") or uuid.uuid4().hex[:16],
        from_agent=body.get("from_agent", "remote"),
        to_agent=body.get("to_agent", ""),
        capability=body.get("capability", ""),
        context_id=body.get("context_id", ""),
        trace_id=body.get("trace_id", ""),
        history=messages,
        metadata=metadata,
    )
    return task


def _health_payload() -> dict[str, Any]:
    """Build health check response payload."""
    initialized = _server is not None and _registry is not None and _node_card is not None
    health_status = (
        "online" if initialized else ("degraded" if _initialization_error else "uninitialized")
    )
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
        "status": health_status,
        "initialized": initialized,
        "initialization_error": _initialization_error,
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
    """Submit a task (A2A 1.0 spec path).

    Spine-adopted: dispatches through the Runtime Truth Spine
    (invoke_agent + exactly one EvidenceReceipt per submit).
    """
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    body = await request.json()
    task = _parse_task_from_body(body)
    result, receipt = await submit_task_via_spine(
        _server, task, router_name="node_gateway",
    )
    if receipt.status == "failed" and not receipt.provider_attempted:
        # Pre-spine contract: an internal submit() error surfaced as a 500,
        # not a FAILED task payload. Preserve that boundary.
        raise HTTPException(status_code=500, detail=receipt.error_detail or "submit failed")
    return JSONResponse(
        content=_task_to_dict(result),
        status_code=201 if result.status != A2ATaskStatus.FAILED else 422,
    )


# Register colon-action routes before generic /tasks/{task_id} to avoid suffix capture.


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
    payload = _health_payload()
    return JSONResponse(content=payload, status_code=200 if payload["initialized"] else 503)


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
    """Submit a task (legacy path).

    Spine-adopted: dispatches through the Runtime Truth Spine
    (invoke_agent + exactly one EvidenceReceipt per submit).
    """
    if _server is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    body = await request.json()
    task = _parse_task_from_body(body)
    result, receipt = await submit_task_via_spine(
        _server, task, router_name="node_gateway",
    )
    if receipt.status == "failed" and not receipt.provider_attempted:
        raise HTTPException(status_code=500, detail=receipt.error_detail or "submit failed")
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
    payload = _health_payload()
    return JSONResponse(content=payload, status_code=200 if payload["initialized"] else 503)


@router.get("/a2a/capabilities", dependencies=[Depends(_verify_api_key)])
async def list_capabilities_legacy() -> JSONResponse:
    """List capabilities (legacy path, delegates to skills)."""
    if _registry is None:
        raise HTTPException(status_code=503, detail="Gateway not initialized")
    return JSONResponse(content=_skills_payload())
