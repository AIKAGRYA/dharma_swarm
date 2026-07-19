"""Command endpoints — trigger swarm operations."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.models import ApiResponse, CreateTaskRequest, EvolveRequest, TraceOut

router = APIRouter(prefix="/api", tags=["commands"])
logger = logging.getLogger(__name__)


def _get_swarm():
    from api.main import get_swarm
    return get_swarm()


def _get_boardstore_outbox():
    from api.main import get_boardstore_outbox
    return get_boardstore_outbox()


@router.post("/commands/evolve")
async def trigger_evolve(req: EvolveRequest) -> ApiResponse:
    # `Swarm.evolve` runs a single gated DarwinEngine proposal and requires
    # change_type/description (dharma_swarm/swarm.py) — it has NO `generations`
    # parameter. This endpoint was calling it with an argument the method never
    # accepted, so every request raised TypeError and returned it as a generic
    # error: a permanently-broken endpoint masquerading as a transient failure,
    # while still constructing the swarm on each call.
    #
    # Wiring a live, unauthenticated HTTP trigger to gated self-evolution is a
    # deliberate feature+authorization decision, not a hardening one. Until that
    # is designed, report the true contract instead of leaking a signature error
    # or driving the engine from this request.
    del req  # request fields (component/generations) do not map to Swarm.evolve
    return ApiResponse(
        status="error",
        error=(
            "evolve is not wired via this endpoint. Swarm.evolve requires "
            "change_type/description and runs a gated proposal; triggering it "
            "over unauthenticated HTTP is intentionally not enabled. Use the "
            "operator terminal 'evolve apply' path."
        ),
    )


@router.post("/commands/task")
async def create_task(req: CreateTaskRequest) -> ApiResponse:
    swarm = _get_swarm()
    try:
        from dharma_swarm.models import TaskPriority
        try:
            priority = TaskPriority(req.priority)
        except ValueError:
            priority = TaskPriority.NORMAL

        meta = dict(req.metadata or {})
        if req.assigned_to:
            meta["assigned_to"] = req.assigned_to
        task = await swarm.create_task(
            title=req.title,
            description=req.description,
            priority=priority,
            metadata=meta,
        )
        outbox = _get_boardstore_outbox()
        if outbox is not None:
            try:
                await outbox.publish(task.id, operation="create")
            except Exception as exc:
                logger.warning(
                    "BoardStore create shadow failed after canonical task %s (%s)",
                    task.id,
                    type(exc).__name__,
                )
        return ApiResponse(data={
            "id": task.id,
            "title": task.title,
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
            "priority": task.priority.value if hasattr(task.priority, 'value') else str(task.priority),
        })
    except Exception as e:
        return ApiResponse(status="error", error=str(e))


@router.get("/commands/tasks")
async def list_tasks() -> ApiResponse:
    swarm = _get_swarm()
    try:
        tasks = await swarm.list_tasks()
        return ApiResponse(data=[
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
                "priority": t.priority.value if hasattr(t.priority, 'value') else str(t.priority),
                "assigned_to": t.assigned_to,
                "created_at": str(t.created_at),
                "updated_at": str(t.updated_at),
                "result": t.result,
            }
            for t in tasks
        ])
    except Exception as e:
        return ApiResponse(data=[], error=str(e))


@router.get("/commands/traces")
async def recent_traces(limit: int = 30) -> ApiResponse:
    from api.main import get_trace_store
    store = get_trace_store()
    try:
        traces = await store.get_recent(limit=limit)
        return ApiResponse(data=[
            TraceOut(
                id=t.id,
                timestamp=str(t.timestamp),
                agent=t.agent,
                action=t.action,
                state=t.state,
                parent_id=t.parent_id,
                metadata=t.metadata,
            ).model_dump()
            for t in traces
        ])
    except Exception as e:
        return ApiResponse(data=[], error=str(e))


@router.post("/commands/dispatch")
async def dispatch_tasks() -> ApiResponse:
    """Trigger task dispatch cycle."""
    swarm = _get_swarm()
    try:
        count = await swarm.dispatch_next()
        return ApiResponse(data={"dispatched": count})
    except Exception as e:
        return ApiResponse(status="error", error=str(e))


@router.get("/commands/dharma")
async def dharma_status() -> ApiResponse:
    swarm = _get_swarm()
    try:
        status = await swarm.dharma_status()
        return ApiResponse(data=status)
    except Exception as e:
        return ApiResponse(status="error", error=str(e))
