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
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control-surface", tags=["control-surface"])
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DS_GOAL_STATE_ROOT = Path.home() / ".dharma" / "ds_goals"
_AGENTOPS_WORK_PACKET_ROOT = _REPO_ROOT / "reports" / "agentops" / "work_packets"
_A2A_SEND_RECEIPT_ROOT = _REPO_ROOT / "reports" / "a2a" / "send_receipts"
_A2A_INBOX_BRIDGE_RECEIPT_ROOT = _REPO_ROOT / "reports" / "a2a" / "inbox_bridge_receipts"
_A2A_DOMAIN_REPLY_RECEIPT_ROOT = _REPO_ROOT / "reports" / "a2a" / "domain_reply_receipts"
_A2A_REPLY_RECEIPT_ROOT = _REPO_ROOT / "reports" / "a2a" / "reply_receipts"
_SEMANTIC_RECEIPT_ROOT = _REPO_ROOT / "reports" / "agentops" / "semantic_receipts"
_IMPORT_LOCK = threading.Lock()
_ENVELOPE_TYPES: tuple[Any, Any, Any] | None = None
_CONTROL_SURFACE_FUNCS: tuple[Any, Any, Any] | None = None
_DS_GOAL_CARD_LOADER: Any | None = None
_AGENTOPS_CARD_LOADER: Any | None = None
_A2A_SEND_CARD_LOADER: Any | None = None
_SEMANTIC_RECEIPT_CARD_LOADER: Any | None = None
_MISSION_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}")
_MISSION_AUTHORITY = "TaskBoard+RuntimeStateStore"


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
        "authority": _MISSION_AUTHORITY,
        "source_mode": "injected_read_only",
        "runtime_projection_mode": runtime_projection_mode,
        "simulation": False,
        "snapshot": snapshot,
        # Lifecycle rows, leases, heartbeats, acks, and receipts do not prove
        # that an executor process is alive at observation time.
        "proves_executor_liveness": False,
    }


def _project_injected_snapshot(snapshot: Any, mission_id: str) -> dict[str, Any]:
    """Validate a provider result against the public MissionSnapshot shape."""
    projected = jsonable_encoder(snapshot)
    if not isinstance(projected, dict):
        raise TypeError("mission snapshot provider returned a non-object")
    mission = projected.get("mission")
    if not isinstance(mission, dict) or mission.get("mission_id") != mission_id:
        raise ValueError("mission snapshot identity does not match the request")
    for field in ("tasks", "attempts", "leases", "receipts"):
        if not isinstance(projected.get(field), list):
            raise TypeError(f"mission snapshot field {field!r} must be a list")
    if not isinstance(projected.get("reconciliation"), str):
        raise TypeError("mission snapshot reconciliation must be a string")
    if not isinstance(projected.get("observed_at"), str):
        raise TypeError("mission snapshot observed_at must be an ISO timestamp")
    if projected.get("authority") != _MISSION_AUTHORITY:
        raise ValueError("mission snapshot authority is not canonical")
    if projected.get("proves_executor_liveness") is not False:
        raise ValueError("mission snapshot cannot claim executor liveness")
    return projected


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

    reader = getattr(provider, "get_snapshot", None)
    if reader is None and callable(provider):
        reader = provider
    if not callable(reader):
        return _build_envelope(
            _mission_snapshot_projection(mission_id, state="unknown"),
            [
                {
                    "source": "mission_snapshot_provider",
                    "error": "injected provider has no read-only get_snapshot callable",
                }
            ],
        )

    try:
        candidate = reader(mission_id)
        snapshot = await candidate if inspect.isawaitable(candidate) else candidate
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
        projected = _project_injected_snapshot(snapshot, mission_id)
        provider_mode = getattr(provider, "runtime_projection_mode", None)
        runtime_projection_mode = (
            provider_mode
            if provider_mode in {"immutable_copy", "owner_supplied_read_only"}
            else "unavailable"
        )
        return _build_envelope(
            _mission_snapshot_projection(
                mission_id,
                state="observed",
                snapshot=projected,
                runtime_projection_mode=runtime_projection_mode,
            )
        )
    except Exception as exc:
        logger.warning(
            "mission snapshot provider failed for explicit mission %r (%s)",
            mission_id,
            type(exc).__name__,
        )
        return _build_envelope(
            _mission_snapshot_projection(mission_id, state="unknown"),
            [
                {
                    "source": "mission_snapshot_provider",
                    "error": f"read failed ({type(exc).__name__})",
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
