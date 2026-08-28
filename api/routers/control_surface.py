"""Control Surface API — declared intent vs observed reality.

GET  /api/control-surface/summary         -> coherence summary (envelope)
GET  /api/control-surface/rows            -> full list of ControlSurfaceRow (envelope)
GET  /api/control-surface/rows/{id}       -> single row by id (envelope)
GET  /api/control-surface/ds-goal/cards   -> ds-goal ledgers as BoardStore cards (envelope)
GET  /api/control-surface/agentops/cards  -> AgentOps work packets as BoardStore cards (envelope)
GET  /api/control-surface/a2a/cards       -> A2A receipts as BoardStore cards (envelope)
GET  /api/control-surface/semantic-receipts/cards -> SemanticReceipt artifacts as BoardStore cards (envelope)
GET  /api/control-surface/missions/{id}/snapshot -> one injected read-only MissionSnapshot
POST /api/control-surface/rows/{id}/handoff-prompt -> agent handoff prompt
GET  /api/control-surface/stream          -> SSE stream of updated rows

ACTIVE_SURFACE_MANIFEST.yaml declares intent; observed reality comes from
runtime/code/evidence adapters.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import threading
import uuid
from concurrent.futures import Future
from contextvars import Context, copy_context
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from api.routers.mission_control_snapshot_validation import (
    MISSION_AUTHORITY,
    project_injected_mission_snapshot,
)
from dharma_swarm.daemon_config import runtime_report_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control-surface", tags=["control-surface"])
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DS_GOAL_STATE_ROOT = Path.home() / ".dharma" / "ds_goals"
_AGENTOPS_WORK_PACKET_ROOT = _REPO_ROOT / "reports" / "agentops" / "work_packets"
_A2A_SEND_RECEIPT_ROOT = runtime_report_dir("a2a", "send_receipts")
_A2A_INBOX_BRIDGE_RECEIPT_ROOT = runtime_report_dir("a2a", "inbox_bridge_receipts")
_A2A_DOMAIN_REPLY_RECEIPT_ROOT = runtime_report_dir("a2a", "domain_reply_receipts")
_A2A_REPLY_RECEIPT_ROOT = runtime_report_dir("a2a", "reply_receipts")
_SEMANTIC_RECEIPT_ROOT = runtime_report_dir("agentops", "semantic_receipts")
_IMPORT_LOCK = threading.Lock()
_ENVELOPE_TYPES: tuple[Any, Any, Any] | None = None
_CONTROL_SURFACE_FUNCS: tuple[Any, Any, Any] | None = None
_DS_GOAL_CARD_LOADER: Any | None = None
_AGENTOPS_CARD_LOADER: Any | None = None
_A2A_SEND_CARD_LOADER: Any | None = None
_SEMANTIC_RECEIPT_CARD_LOADER: Any | None = None
_MISSION_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}")
_SAFE_ERROR_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,79}")
_MISSION_SNAPSHOT_PROVIDER_TIMEOUT_SECONDS = 1.0
_MISSION_SNAPSHOT_READ_SLOTS = threading.BoundedSemaphore(value=4)
_MISSION_SNAPSHOT_READ_FUTURES_LOCK = threading.Lock()
_MISSION_SNAPSHOT_READ_FUTURES: set[Future[Any]] = set()
_MISSING_SNAPSHOT_READER = object()


class ProviderCancelledError(RuntimeError):
    """An injected provider cancelled its own read operation."""


class _MissionSnapshotProviderResult:
    __slots__ = ("runtime_projection_mode", "snapshot")

    def __init__(self, snapshot: Any, runtime_projection_mode: str) -> None:
        self.snapshot = snapshot
        self.runtime_projection_mode = runtime_projection_mode


class _WorkerTaskGuard:
    """Best-effort cleanup for a trusted quiescent read provider."""

    def __init__(self) -> None:
        self.failed = False
        self.cleanup_started = False
        self.tasks: set[asyncio.Task[Any]] = set()
        self.root_tasks: set[asyncio.Task[Any]] = set()

    def task_factory(
        self,
        loop: asyncio.AbstractEventLoop,
        coro: Any,
        **kwargs: Any,
    ) -> asyncio.Task[Any]:
        if self.cleanup_started:
            self.failed = True
            kwargs.pop("eager_start", None)
            _discard_unstarted_awaitable(coro)

            async def cancelled_placeholder() -> None:
                return None

            coro = cancelled_placeholder()
        task = asyncio.Task(coro, loop=loop, **kwargs)
        self.tasks.add(task)
        if self.cleanup_started:
            task.cancel()
        return task

    def allow_root(self, task: asyncio.Task[Any]) -> None:
        self.root_tasks.add(task)

    def observe_task(self, task: asyncio.Task[Any]) -> None:
        self.tasks.discard(task)
        if task.cancelled():
            return
        unobserved = bool(getattr(task, "_log_traceback", False))
        try:
            exception = task.exception()
        except asyncio.CancelledError:
            return
        if exception is not None and task not in self.root_tasks and unobserved:
            self.failed = True

    async def quiesce(
        self,
        loop: asyncio.AbstractEventLoop,
        current: asyncio.Task[Any],
    ) -> None:
        self.cleanup_started = True
        stable_turns = 0
        while stable_turns < 2:
            pending = {
                task
                for task in self.tasks | asyncio.all_tasks(loop)
                if task is not current and not task.done()
            }
            if pending:
                self.failed = True
                stable_turns = 0
                for task in pending:
                    task.cancel()
                results = await asyncio.gather(*pending, return_exceptions=True)
                if any(
                    isinstance(result, BaseException)
                    and not isinstance(result, asyncio.CancelledError)
                    for result in results
                ):
                    self.failed = True
            else:
                stable_turns += 1
            await asyncio.sleep(0)

    async def drain_async_generators(
        self,
        loop: asyncio.AbstractEventLoop,
        current: asyncio.Task[Any],
    ) -> None:
        registry = getattr(loop, "_asyncgens", None)
        if registry is None:
            self.failed = True
            return
        stable_turns = 0
        while stable_turns < 2:
            generators = list(registry)
            registry.clear()
            if generators:
                stable_turns = 0
                for generator in generators:
                    try:
                        await generator.aclose()
                    except BaseException:
                        self.failed = True
                await self.quiesce(loop, current)
            else:
                stable_turns += 1
            await asyncio.sleep(0)
        setattr(loop, "_asyncgens_shutdown_called", True)

    async def shutdown(
        self,
        loop: asyncio.AbstractEventLoop,
        current: asyncio.Task[Any],
    ) -> None:
        """Best-effort reject observed work forbidden by the provider contract."""
        await self.quiesce(loop, current)
        await self.drain_async_generators(loop, current)
        await self.quiesce(loop, current)

    def finalize_registry(self) -> None:
        for task in tuple(self.tasks):
            if task.done():
                self.observe_task(task)
        if self.tasks:
            self.failed = True

    def handle_loop_exception(
        self,
        _loop: asyncio.AbstractEventLoop,
        context: dict[str, Any],
    ) -> None:
        self.failed = True
        future = context.get("task") or context.get("future")
        if isinstance(future, asyncio.Future) and not future.cancelled():
            try:
                future.exception()
            except (asyncio.CancelledError, asyncio.InvalidStateError):
                pass


class _MissionSnapshotReadState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._abandoned = False
        self._worker_loop: asyncio.AbstractEventLoop | None = None
        self._worker_task: asyncio.Task[Any] | None = None

    def is_abandoned(self) -> bool:
        with self._lock:
            return self._abandoned

    def install_worker_task(
        self,
        loop: asyncio.AbstractEventLoop,
        candidate: Any,
    ) -> asyncio.Task[Any] | None:
        with self._lock:
            if self._abandoned:
                return None
            task = loop.create_task(_await_provider_result(candidate))
            self._worker_loop = loop
            self._worker_task = task
            return task

    def clear_worker_task(
        self,
        loop: asyncio.AbstractEventLoop,
        task: asyncio.Task[Any],
    ) -> None:
        with self._lock:
            if self._worker_loop is loop and self._worker_task is task:
                self._worker_loop = None
                self._worker_task = None

    def abandon(self) -> None:
        with self._lock:
            self._abandoned = True
            loop = self._worker_loop
            task = self._worker_task
        if loop is not None and task is not None:
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass


async def _await_provider_result(candidate: Any) -> Any:
    return await candidate


async def _complete_provider_result(
    candidate: Any,
    state: _MissionSnapshotReadState,
    worker_guard: _WorkerTaskGuard,
) -> Any:
    worker_loop = asyncio.get_running_loop()
    current = asyncio.current_task()
    if current is None:
        raise RuntimeError("mission snapshot worker task is unavailable")
    worker_guard.allow_root(current)
    worker_task: asyncio.Task[Any] | None = None
    try:
        worker_task = state.install_worker_task(worker_loop, candidate)
        if worker_task is None:
            _discard_unstarted_awaitable(candidate)
            raise RuntimeError("mission snapshot read was abandoned")
        worker_guard.allow_root(worker_task)
        return await worker_task
    finally:
        if worker_task is not None:
            state.clear_worker_task(worker_loop, worker_task)
        await worker_guard.shutdown(worker_loop, current)


def _discard_unstarted_awaitable(candidate: Any) -> None:
    if inspect.iscoroutine(candidate):
        candidate.close()
    elif isinstance(candidate, asyncio.Future):
        candidate.cancel()
    elif inspect.isawaitable(candidate):
        close = getattr(candidate, "close", None)
        if callable(close):
            close()


def _invoke_mission_snapshot_provider(
    provider: Any,
    mission_id: str,
) -> Any:
    """Resolve and invoke one provider without consuming Starlette's sync pool."""
    reader = getattr(provider, "get_snapshot", None)
    if reader is None and callable(provider):
        reader = provider
    if not callable(reader):
        return _MISSING_SNAPSHOT_READER
    return reader(mission_id)


def _run_mission_snapshot_provider_operation(
    provider: Any,
    mission_id: str,
    state: _MissionSnapshotReadState,
) -> _MissionSnapshotProviderResult:
    """Complete the provider-returned operation inside one worker thread."""
    try:
        if state.is_abandoned():
            raise RuntimeError("mission snapshot read was abandoned")
        candidate = _invoke_mission_snapshot_provider(provider, mission_id)
        if inspect.isawaitable(candidate) and not inspect.iscoroutine(candidate):
            _discard_unstarted_awaitable(candidate)
            raise TypeError(
                "mission snapshot provider must return a value or native coroutine"
            )
        if inspect.iscoroutine(candidate):
            if state.is_abandoned():
                _discard_unstarted_awaitable(candidate)
                raise RuntimeError("mission snapshot read was abandoned")
            worker_guard = _WorkerTaskGuard()
            with asyncio.Runner() as runner:
                worker_loop = runner.get_loop()
                worker_loop.set_task_factory(worker_guard.task_factory)
                worker_loop.set_exception_handler(worker_guard.handle_loop_exception)
                try:
                    snapshot = runner.run(
                        _complete_provider_result(candidate, state, worker_guard)
                    )
                finally:
                    worker_loop.set_task_factory(None)
            worker_guard.finalize_registry()
            if worker_guard.failed:
                raise RuntimeError("mission snapshot provider background task failed")
        else:
            snapshot = candidate
        if state.is_abandoned():
            raise RuntimeError("mission snapshot read was abandoned")
        if snapshot is _MISSING_SNAPSHOT_READER or snapshot is None:
            return _MissionSnapshotProviderResult(snapshot, "unavailable")
        provider_mode = getattr(provider, "runtime_projection_mode", None)
        runtime_projection_mode = (
            provider_mode
            if isinstance(provider_mode, str)
            and provider_mode in {"immutable_copy", "owner_supplied_read_only"}
            else "unavailable"
        )
        if state.is_abandoned():
            raise RuntimeError("mission snapshot read was abandoned")
        return _MissionSnapshotProviderResult(snapshot, runtime_projection_mode)
    except asyncio.CancelledError as exc:
        raise ProviderCancelledError("mission snapshot provider cancelled") from exc


def _mission_snapshot_worker(
    result_future: Future[_MissionSnapshotProviderResult],
    provider: Any,
    mission_id: str,
    state: _MissionSnapshotReadState,
    provider_context: Context,
) -> None:
    if not result_future.set_running_or_notify_cancel():
        return
    try:
        result = provider_context.run(
            _run_mission_snapshot_provider_operation,
            provider,
            mission_id,
            state,
        )
    except BaseException as exc:
        error = exc if isinstance(exc, Exception) else RuntimeError(
            "mission snapshot provider failed"
        )
        result_future.set_exception(error)
    else:
        result_future.set_result(result)


def _finish_mission_snapshot_read(
    result_future: Future[_MissionSnapshotProviderResult],
) -> None:
    """Consume the raw worker result and release its ownership slot."""
    try:
        if not result_future.cancelled():
            result_future.exception()
    finally:
        with _MISSION_SNAPSHOT_READ_FUTURES_LOCK:
            _MISSION_SNAPSHOT_READ_FUTURES.discard(result_future)
        _MISSION_SNAPSHOT_READ_SLOTS.release()


def _consume_wrapped_provider_result(result: asyncio.Future[Any]) -> None:
    if not result.cancelled():
        result.exception()


async def _read_mission_snapshot(
    provider: Any,
    mission_id: str,
) -> _MissionSnapshotProviderResult:
    """Apply a hard outward deadline while capping detached provider reads."""
    if not _MISSION_SNAPSHOT_READ_SLOTS.acquire(blocking=False):
        raise TimeoutError("mission snapshot read capacity is exhausted")
    state = _MissionSnapshotReadState()
    result_future: Future[_MissionSnapshotProviderResult] = Future()
    with _MISSION_SNAPSHOT_READ_FUTURES_LOCK:
        _MISSION_SNAPSHOT_READ_FUTURES.add(result_future)
    result_future.add_done_callback(_finish_mission_snapshot_read)
    try:
        worker = threading.Thread(
            target=_mission_snapshot_worker,
            args=(result_future, provider, mission_id, state, copy_context()),
            name="mission-snapshot-provider",
            daemon=True,
        )
        worker.start()
    except BaseException:
        state.abandon()
        result_future.cancel()
        raise
    wrapped_future = asyncio.wrap_future(result_future)
    wrapped_future.add_done_callback(_consume_wrapped_provider_result)
    try:
        done, _ = await asyncio.wait(
            {wrapped_future},
            timeout=_MISSION_SNAPSHOT_PROVIDER_TIMEOUT_SECONDS,
        )
    except asyncio.CancelledError:
        state.abandon()
        wrapped_future.cancel()
        raise
    except BaseException:
        state.abandon()
        wrapped_future.cancel()
        raise
    if wrapped_future in done:
        try:
            return wrapped_future.result()
        except asyncio.CancelledError as exc:
            raise ProviderCancelledError(
                "mission snapshot provider cancelled"
            ) from exc
    state.abandon()
    wrapped_future.cancel()
    raise TimeoutError("mission snapshot provider read timed out")


def _get_envelope_types() -> tuple[Any, Any, Any]:
    global _ENVELOPE_TYPES
    if _ENVELOPE_TYPES is None:
        with _IMPORT_LOCK:
            if _ENVELOPE_TYPES is None:
                from dharma_swarm.operator_core.control_surface_models import (
                    ControlSurfaceEnvelope,
                    SourceError,
                    _utc_now_iso,
                )

                _ENVELOPE_TYPES = (ControlSurfaceEnvelope, SourceError, _utc_now_iso)
    return _ENVELOPE_TYPES


def _get_control_surface_funcs() -> tuple[Any, Any, Any]:
    global _CONTROL_SURFACE_FUNCS
    if _CONTROL_SURFACE_FUNCS is None:
        with _IMPORT_LOCK:
            if _CONTROL_SURFACE_FUNCS is None:
                from dharma_swarm.operator_core.control_surface import (
                    build_control_surface_rows,
                    build_control_surface_summary,
                    generate_handoff_prompt,
                )

                _CONTROL_SURFACE_FUNCS = (
                    build_control_surface_rows,
                    build_control_surface_summary,
                    generate_handoff_prompt,
                )
    return _CONTROL_SURFACE_FUNCS


def _get_ds_goal_card_loader():  # noqa: ANN202
    global _DS_GOAL_CARD_LOADER
    if _DS_GOAL_CARD_LOADER is None:
        with _IMPORT_LOCK:
            if _DS_GOAL_CARD_LOADER is None:
                from dharma_swarm.board.adapters.ds_goal_adapter import load_ds_goal_cards

                _DS_GOAL_CARD_LOADER = load_ds_goal_cards
    return _DS_GOAL_CARD_LOADER


def _get_agentops_card_loader():  # noqa: ANN202
    global _AGENTOPS_CARD_LOADER
    if _AGENTOPS_CARD_LOADER is None:
        with _IMPORT_LOCK:
            if _AGENTOPS_CARD_LOADER is None:
                from dharma_swarm.board.adapters.agentops_adapter import load_agentops_cards

                _AGENTOPS_CARD_LOADER = load_agentops_cards
    return _AGENTOPS_CARD_LOADER


def _get_a2a_send_card_loader():  # noqa: ANN202
    global _A2A_SEND_CARD_LOADER
    if _A2A_SEND_CARD_LOADER is None:
        with _IMPORT_LOCK:
            if _A2A_SEND_CARD_LOADER is None:
                from dharma_swarm.board.adapters.a2a_send_adapter import load_a2a_send_cards

                _A2A_SEND_CARD_LOADER = load_a2a_send_cards
    return _A2A_SEND_CARD_LOADER


def _get_semantic_receipt_card_loader():  # noqa: ANN202
    global _SEMANTIC_RECEIPT_CARD_LOADER
    if _SEMANTIC_RECEIPT_CARD_LOADER is None:
        with _IMPORT_LOCK:
            if _SEMANTIC_RECEIPT_CARD_LOADER is None:
                from dharma_swarm.board.adapters.semantic_receipt_adapter import (
                    load_semantic_receipt_cards,
                )

                _SEMANTIC_RECEIPT_CARD_LOADER = load_semantic_receipt_cards
    return _SEMANTIC_RECEIPT_CARD_LOADER


def _build_envelope(data: Any, source_errors: list[dict[str, str]] | None = None) -> dict[str, Any]:
    ControlSurfaceEnvelope, SourceError, _utc_now_iso = _get_envelope_types()
    errors = [SourceError(**e) for e in (source_errors or [])]
    envelope = ControlSurfaceEnvelope(
        schema_version="0.2.0",
        request_id=str(uuid.uuid4()),
        generated_at=_utc_now_iso(),
        source_errors=errors,
        data=data,
    )
    return envelope.model_dump()


def _build_rows_with_errors(
    *,
    memory_depth: str = "snapshot",
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Build rows and collect any source errors encountered."""
    build_control_surface_rows, _, _ = _get_control_surface_funcs()
    source_errors: list[dict[str, str]] = []
    try:
        rows = build_control_surface_rows(memory_depth=memory_depth)
    except Exception as exc:
        logger.exception("control-surface projection failed")
        source_errors.append({"source": "projection_engine", "error": str(exc)})
        return [], source_errors
    return [row.to_dict() for row in rows], source_errors


def _build_rows(*, memory_depth: str = "snapshot") -> list[dict[str, Any]]:
    rows, _ = _build_rows_with_errors(memory_depth=memory_depth)
    return rows


def _find_row_object(row_id: str, *, memory_depth: str = "snapshot"):  # noqa: ANN202
    build_control_surface_rows, _, _ = _get_control_surface_funcs()
    rows = build_control_surface_rows(memory_depth=memory_depth)
    for row in rows:
        if row.id == row_id:
            return row
    return None


def _mission_snapshot_projection(
    mission_id: str,
    *,
    state: str,
    snapshot: dict[str, Any] | None = None,
    runtime_projection_mode: str = "unavailable",
) -> dict[str, Any]:
    """Build a non-promotional read model for one explicit mission."""
    return {
        "schema_version": "dharma.control_surface.mission_snapshot_projection.v1",
        "mission_id": mission_id,
        "state": state,
        "authority": MISSION_AUTHORITY,
        "source_mode": "injected_read_only",
        "runtime_projection_mode": runtime_projection_mode,
        "simulation": False,
        "snapshot": snapshot,
        # Lifecycle rows, leases, heartbeats, acks, and receipts do not prove
        # that an executor process is alive at observation time.
        "proves_executor_liveness": False,
    }


@router.get("/summary")
def control_surface_summary(
    memory_depth: str = Query(
        "snapshot",
        pattern="^(snapshot|deep)$",
        description="MemoryKernel projection depth. Use deep only for explicit readiness verification.",
    ),
) -> dict[str, Any]:
    """Lightweight coherence summary with counts by state."""
    try:
        build_control_surface_rows, build_control_surface_summary, _ = _get_control_surface_funcs()
        rows = build_control_surface_rows(memory_depth=memory_depth)
        summary = build_control_surface_summary(rows)
        summary["memory_depth"] = memory_depth
        return _build_envelope(summary)
    except Exception as e:
        logger.exception("control-surface/summary failed")
        return _build_envelope(None, [{"source": "summary", "error": str(e)}])


@router.get("/stream")
async def control_surface_stream():
    """SSE stream pushing updated rows when the projection changes."""
    async def event_generator():  # noqa: ANN202
        last_hash: int | None = None
        while True:
            try:
                row_dicts = _build_rows(memory_depth="snapshot")
                payload = json.dumps(row_dicts, sort_keys=True)
                current_hash = hash(payload)
                if current_hash != last_hash:
                    yield f"data: {payload}\n\n"
                    last_hash = current_hash
            except Exception:
                logger.exception("control-surface/stream iteration failed")
            await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/rows")
def control_surface_rows(
    memory_depth: str = Query(
        "snapshot",
        pattern="^(snapshot|deep)$",
        description="MemoryKernel projection depth. Use deep only for explicit readiness verification.",
    ),
) -> dict[str, Any]:
    """All control surface rows — declared intent reconciled with observed reality."""
    try:
        row_dicts, source_errors = _build_rows_with_errors(memory_depth=memory_depth)
        return _build_envelope(row_dicts, source_errors)
    except Exception as e:
        logger.exception("control-surface/rows failed")
        return _build_envelope(None, [{"source": "rows", "error": str(e)}])


@router.get("/ds-goal/cards")
def control_surface_ds_goal_cards(
    mission_id: str = Query("", description="Optional ds-goal mission id filter."),
) -> dict[str, Any]:
    """Project ds-goal mission ledgers into existing BoardStore Card JSON."""
    try:
        load_ds_goal_cards = _get_ds_goal_card_loader()
        cards = [
            card.model_dump(mode="json")
            for card in load_ds_goal_cards(_DS_GOAL_STATE_ROOT, mission_id=mission_id)
        ]
        return _build_envelope(
            {
                "state_root": str(_DS_GOAL_STATE_ROOT),
                "mission_id": mission_id or None,
                "card_count": len(cards),
                "cards": cards,
            }
        )
    except Exception as e:
        logger.exception("control-surface/ds-goal/cards failed")
        return _build_envelope(
            {
                "state_root": str(_DS_GOAL_STATE_ROOT),
                "mission_id": mission_id or None,
                "card_count": 0,
                "cards": [],
            },
            [{"source": "ds_goal_cards", "error": str(e)}],
        )


@router.get("/agentops/cards")
def control_surface_agentops_cards(
    packet_id: str = Query("", description="Optional AgentOps packet id filter."),
    limit: int = Query(0, ge=0, le=200, description="Optional maximum card count."),
) -> dict[str, Any]:
    """Project AgentOps work packets into existing BoardStore Card JSON."""
    try:
        load_agentops_cards = _get_agentops_card_loader()
        cards = [
            card.model_dump(mode="json")
            for card in load_agentops_cards(
                _AGENTOPS_WORK_PACKET_ROOT,
                packet_id=packet_id,
                limit=limit,
            )
        ]
        return _build_envelope(
            {
                "work_packet_root": str(_AGENTOPS_WORK_PACKET_ROOT),
                "packet_id": packet_id or None,
                "card_count": len(cards),
                "cards": cards,
            }
        )
    except Exception as e:
        logger.exception("control-surface/agentops/cards failed")
        return _build_envelope(
            {
                "work_packet_root": str(_AGENTOPS_WORK_PACKET_ROOT),
                "packet_id": packet_id or None,
                "card_count": 0,
                "cards": [],
            },
            [{"source": "agentops_cards", "error": str(e)}],
        )


@router.get("/a2a/cards")
def control_surface_a2a_cards(
    target: str = Query("", description="Optional A2A target filter."),
    limit: int = Query(0, ge=0, le=200, description="Optional maximum card count."),
) -> dict[str, Any]:
    """Project A2A send/bridge receipts into existing BoardStore Card JSON."""
    try:
        load_a2a_send_cards = _get_a2a_send_card_loader()
        cards = [
            card.model_dump(mode="json")
            for card in load_a2a_send_cards(
                _A2A_SEND_RECEIPT_ROOT,
                bridge_receipt_root=_A2A_INBOX_BRIDGE_RECEIPT_ROOT,
                domain_reply_receipt_root=_A2A_DOMAIN_REPLY_RECEIPT_ROOT,
                reply_receipt_root=_A2A_REPLY_RECEIPT_ROOT,
                target=target,
                limit=limit,
            )
        ]
        return _build_envelope(
            {
                "receipt_root": str(_A2A_SEND_RECEIPT_ROOT),
                "bridge_receipt_root": str(_A2A_INBOX_BRIDGE_RECEIPT_ROOT),
                "domain_reply_receipt_root": str(_A2A_DOMAIN_REPLY_RECEIPT_ROOT),
                "reply_receipt_root": str(_A2A_REPLY_RECEIPT_ROOT),
                "target": target or None,
                "card_count": len(cards),
                "cards": cards,
            }
        )
    except Exception as e:
        logger.exception("control-surface/a2a/cards failed")
        return _build_envelope(
            {
                "receipt_root": str(_A2A_SEND_RECEIPT_ROOT),
                "bridge_receipt_root": str(_A2A_INBOX_BRIDGE_RECEIPT_ROOT),
                "domain_reply_receipt_root": str(_A2A_DOMAIN_REPLY_RECEIPT_ROOT),
                "reply_receipt_root": str(_A2A_REPLY_RECEIPT_ROOT),
                "target": target or None,
                "card_count": 0,
                "cards": [],
            },
            [{"source": "a2a_cards", "error": str(e)}],
        )


@router.get("/semantic-receipts/cards")
def control_surface_semantic_receipt_cards(
    model: str = Query("", description="Optional model filter."),
    verdict: str = Query("", description="Optional verdict filter."),
    limit: int = Query(0, ge=0, le=200, description="Optional maximum card count."),
) -> dict[str, Any]:
    """Project SemanticReceipt artifacts into existing BoardStore Card JSON."""
    try:
        load_semantic_receipt_cards = _get_semantic_receipt_card_loader()
        cards = [
            card.model_dump(mode="json")
            for card in load_semantic_receipt_cards(
                _SEMANTIC_RECEIPT_ROOT,
                model=model,
                verdict=verdict,
                limit=limit,
            )
        ]
        return _build_envelope(
            {
                "receipt_root": str(_SEMANTIC_RECEIPT_ROOT),
                "model": model or None,
                "verdict": verdict or None,
                "card_count": len(cards),
                "cards": cards,
            }
        )
    except Exception as e:
        logger.exception("control-surface/semantic-receipts/cards failed")
        return _build_envelope(
            {
                "receipt_root": str(_SEMANTIC_RECEIPT_ROOT),
                "model": model or None,
                "verdict": verdict or None,
                "card_count": 0,
                "cards": [],
            },
            [{"source": "semantic_receipt_cards", "error": str(e)}],
        )


@router.get("/missions/{mission_id}/snapshot")
async def control_surface_mission_snapshot(
    mission_id: str,
    request: Request,
) -> dict[str, Any]:
    """Project one canonical MissionSnapshot through an injected reader only.

    A request never constructs MissionControl, TaskBoard, RuntimeStateStore,
    an MCP client, or a background worker. The embedding application must
    explicitly supply its already-governed read-only provider.
    """
    mission_id = mission_id.strip()
    if _MISSION_IDENTIFIER.fullmatch(mission_id) is None:
        raise HTTPException(
            status_code=422,
            detail="mission_id must be a bounded identifier",
        )

    provider = getattr(request.app.state, "mission_snapshot_provider", None)
    if provider is None:
        return _build_envelope(
            _mission_snapshot_projection(mission_id, state="uninitialized"),
            [
                {
                    "source": "mission_snapshot_provider",
                    "error": "read-only provider is not injected",
                }
            ],
        )

    try:
        provider_result = await _read_mission_snapshot(provider, mission_id)
        snapshot = provider_result.snapshot
        if snapshot is _MISSING_SNAPSHOT_READER:
            return _build_envelope(
                _mission_snapshot_projection(mission_id, state="unknown"),
                [
                    {
                        "source": "mission_snapshot_provider",
                        "error": (
                            "injected provider has no read-only get_snapshot callable"
                        ),
                    }
                ],
            )
        if snapshot is None:
            return _build_envelope(
                _mission_snapshot_projection(mission_id, state="unknown"),
                [
                    {
                        "source": "mission_snapshot",
                        "error": "canonical state was not observed for this mission",
                    }
                ],
            )
        projected = project_injected_mission_snapshot(snapshot, mission_id)
        return _build_envelope(
            _mission_snapshot_projection(
                mission_id,
                state="observed",
                snapshot=projected,
                runtime_projection_mode=provider_result.runtime_projection_mode,
            )
        )
    except Exception as exc:
        # The identifier and provider exception are deliberately excluded from
        # logs: both cross an injection boundary and may contain forged lines.
        logger.warning("mission snapshot provider failed (kind=read_failed)")
        error_type = type(exc).__name__
        if _SAFE_ERROR_TYPE.fullmatch(error_type) is None:
            error_type = "ProviderError"
        return _build_envelope(
            _mission_snapshot_projection(mission_id, state="unknown"),
            [
                {
                    "source": "mission_snapshot_provider",
                    "error": f"read failed ({error_type})",
                }
            ],
        )


@router.post("/rows/{row_id:path}/handoff-prompt")
def control_surface_handoff_prompt(
    row_id: str,
    memory_depth: str = Query(
        "snapshot",
        pattern="^(snapshot|deep)$",
        description="MemoryKernel projection depth for locating the row.",
    ),
) -> dict[str, Any]:
    """Generate a scoped agent handoff prompt for a control surface row."""
    try:
        _, _, generate_handoff_prompt = _get_control_surface_funcs()
        row = _find_row_object(row_id, memory_depth=memory_depth)
        if row is None:
            raise HTTPException(status_code=404, detail=f"row '{row_id}' not found")
        prompt = generate_handoff_prompt(row)
        return _build_envelope(prompt.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("control-surface/handoff-prompt failed")
        return _build_envelope(None, [{"source": f"handoff/{row_id}", "error": str(e)}])


@router.get("/rows/{row_id:path}")
def control_surface_row(
    row_id: str,
    memory_depth: str = Query(
        "snapshot",
        pattern="^(snapshot|deep)$",
        description="MemoryKernel projection depth. Use deep only for explicit readiness verification.",
    ),
) -> dict[str, Any]:
    """Single control surface row by ID."""
    try:
        row_dicts, source_errors = _build_rows_with_errors(memory_depth=memory_depth)
        for row in row_dicts:
            if row["id"] == row_id:
                return _build_envelope(row, source_errors)
        raise HTTPException(status_code=404, detail=f"row '{row_id}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("control-surface/rows/<id> failed")
        return _build_envelope(None, [{"source": f"row/{row_id}", "error": str(e)}])
