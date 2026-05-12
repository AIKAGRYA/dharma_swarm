"""Live external-agent interop endpoints."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.models import ApiResponse
from dharma_swarm.operator_core.interop import AgentInteropStore

router = APIRouter(prefix="/api", tags=["interop"])


class InteropTaskRequest(BaseModel):
    recipient: str
    summary: str
    body: str
    sender: str = "operator"
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class InteropClaimRequest(BaseModel):
    recipient: str
    worker_id: str
    lease_seconds: int = 900


class InteropHeartbeatRequest(BaseModel):
    worker_id: str
    adapter_id: str
    status: str
    current_task_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class InteropTaskResponseRequest(BaseModel):
    responder: str
    summary: str
    body: str
    status: str = "responded"
    metadata: dict[str, Any] = Field(default_factory=dict)


def _store() -> AgentInteropStore:
    return AgentInteropStore()


@router.get("/interop/status")
async def interop_status() -> ApiResponse:
    return ApiResponse(data=_store().build_status())


@router.get("/interop/tasks")
async def interop_tasks(limit: int = 50) -> ApiResponse:
    return ApiResponse(data=_store().list_tasks(limit=limit))


@router.get("/interop/events")
async def interop_events(after_event_id: str | None = None, limit: int = 100) -> ApiResponse:
    return ApiResponse(data=_store().list_events(after_event_id=after_event_id, limit=limit))


@router.get("/interop/workers")
async def interop_workers() -> ApiResponse:
    return ApiResponse(data=_store().list_workers())


@router.get("/interop/stream")
async def interop_stream(after_event_id: str | None = None) -> StreamingResponse:
    async def event_stream():
        store = _store()
        cursor = after_event_id
        initial = {
            "event_id": "snapshot",
            "event_type": "status.snapshot",
            "summary": "Interop status snapshot",
            "payload": store.build_status(),
        }
        yield f"event: interop\ndata: {json.dumps(initial, ensure_ascii=True, default=str)}\n\n"
        while True:
            events = store.list_events(after_event_id=cursor, limit=100)
            for event in events:
                cursor = str(event.get("event_id") or cursor or "")
                yield f"event: interop\ndata: {json.dumps(event, ensure_ascii=True, default=str)}\n\n"
            await asyncio.sleep(2.0)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/interop/tasks")
async def enqueue_interop_task(req: InteropTaskRequest) -> ApiResponse:
    task = _store().enqueue_task(
        recipient=req.recipient,
        sender=req.sender,
        summary=req.summary,
        body=req.body,
        capabilities=req.capabilities,
        metadata=req.metadata,
    )
    return ApiResponse(data=task)


@router.post("/interop/claim-next")
async def claim_interop_task(req: InteropClaimRequest) -> ApiResponse:
    task = _store().claim_next_task(
        recipient=req.recipient,
        worker_id=req.worker_id,
        lease_seconds=req.lease_seconds,
    )
    return ApiResponse(data=task)


@router.post("/interop/heartbeat")
async def heartbeat_interop_worker(req: InteropHeartbeatRequest) -> ApiResponse:
    return ApiResponse(
        data=_store().heartbeat_worker(
            worker_id=req.worker_id,
            adapter_id=req.adapter_id,
            status=req.status,
            current_task_id=req.current_task_id,
            metadata=req.metadata,
        )
    )


@router.post("/interop/tasks/{task_id}/response")
async def respond_to_interop_task(task_id: str, req: InteropTaskResponseRequest) -> ApiResponse:
    response = _store().respond_to_task(
        task_id=task_id,
        responder=req.responder,
        summary=req.summary,
        body=req.body,
        status=req.status,
        metadata=req.metadata,
    )
    return ApiResponse(data=response)
