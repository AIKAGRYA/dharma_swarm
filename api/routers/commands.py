"""Command endpoints — trigger swarm operations."""

from __future__ import annotations

from fastapi import APIRouter

from api.models import ApiResponse, CreateTaskRequest, EvolveRequest, TraceOut

router = APIRouter(prefix="/api", tags=["commands"])


def _get_swarm():
    from api.main import get_swarm
    return get_swarm()


def _serialize_task(task) -> dict[str, object]:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value if hasattr(task.status, "value") else str(task.status),
        "priority": task.priority.value if hasattr(task.priority, "value") else str(task.priority),
        "assigned_to": task.assigned_to,
        "created_by": getattr(task, "created_by", "system"),
        "created_at": str(task.created_at),
        "updated_at": str(task.updated_at),
        "result": task.result,
        "metadata": dict(getattr(task, "metadata", {}) or {}),
    }


@router.post("/commands/evolve")
async def trigger_evolve(req: EvolveRequest) -> ApiResponse:
    swarm = _get_swarm()
    try:
        result = await swarm.evolve(component=req.component, generations=req.generations)
        return ApiResponse(data=result)
    except Exception as e:
        return ApiResponse(status="error", error=str(e))


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
        task = await swarm.create_task(
            title=req.title,
            description=req.description,
            priority=priority,
            created_by=req.created_by,
            assigned_to=req.assigned_to,
            metadata=meta,
        )
        return ApiResponse(data=_serialize_task(task))
    except Exception as e:
        return ApiResponse(status="error", error=str(e))


@router.get("/commands/tasks")
async def list_tasks() -> ApiResponse:
    swarm = _get_swarm()
    try:
        tasks = await swarm.list_tasks()
        return ApiResponse(data=[_serialize_task(t) for t in tasks])
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
