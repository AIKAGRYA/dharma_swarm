"""Control Surface API — declared intent vs observed reality.

GET  /api/control-surface/summary         -> coherence summary (envelope)
GET  /api/control-surface/rows            -> full list of ControlSurfaceRow (envelope)
GET  /api/control-surface/rows/{id}       -> single row by id (envelope)
POST /api/control-surface/rows/{id}/handoff-prompt -> agent handoff prompt
GET  /api/control-surface/stream          -> SSE stream of updated rows

ACTIVE_SURFACE_MANIFEST.yaml declares intent; observed reality comes from
runtime/code/evidence adapters.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control-surface", tags=["control-surface"])


def _build_envelope(data: Any, source_errors: list[dict[str, str]] | None = None) -> dict[str, Any]:
    from dharma_swarm.operator_core.control_surface_models import (
        ControlSurfaceEnvelope,
        SourceError,
        _utc_now_iso,
    )
    errors = [SourceError(**e) for e in (source_errors or [])]
    envelope = ControlSurfaceEnvelope(
        schema_version="0.2.0",
        request_id=str(uuid.uuid4()),
        generated_at=_utc_now_iso(),
        source_errors=errors,
        data=data,
    )
    return envelope.model_dump()


def _build_rows_with_errors() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Build rows and collect any source errors encountered."""
    from dharma_swarm.operator_core.control_surface import build_control_surface_rows
    source_errors: list[dict[str, str]] = []
    try:
        rows = build_control_surface_rows()
    except Exception as exc:
        logger.exception("control-surface projection failed")
        source_errors.append({"source": "projection_engine", "error": str(exc)})
        return [], source_errors
    return [row.to_dict() for row in rows], source_errors


def _build_rows() -> list[dict[str, Any]]:
    rows, _ = _build_rows_with_errors()
    return rows


def _find_row_object(row_id: str):  # noqa: ANN202
    from dharma_swarm.operator_core.control_surface import build_control_surface_rows
    rows = build_control_surface_rows()
    for row in rows:
        if row.id == row_id:
            return row
    return None


@router.get("/summary")
async def control_surface_summary() -> dict[str, Any]:
    """Lightweight coherence summary with counts by state."""
    try:
        from dharma_swarm.operator_core.control_surface import (
            build_control_surface_rows,
            build_control_surface_summary,
        )
        rows = build_control_surface_rows()
        summary = build_control_surface_summary(rows)
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
                row_dicts = _build_rows()
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
async def control_surface_rows() -> dict[str, Any]:
    """All control surface rows — declared intent reconciled with observed reality."""
    try:
        row_dicts, source_errors = _build_rows_with_errors()
        return _build_envelope(row_dicts, source_errors)
    except Exception as e:
        logger.exception("control-surface/rows failed")
        return _build_envelope(None, [{"source": "rows", "error": str(e)}])


@router.post("/rows/{row_id:path}/handoff-prompt")
async def control_surface_handoff_prompt(row_id: str) -> dict[str, Any]:
    """Generate a scoped agent handoff prompt for a control surface row."""
    try:
        from dharma_swarm.operator_core.control_surface import generate_handoff_prompt

        row = _find_row_object(row_id)
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
async def control_surface_row(row_id: str) -> dict[str, Any]:
    """Single control surface row by ID."""
    try:
        row_dicts, source_errors = _build_rows_with_errors()
        for row in row_dicts:
            if row["id"] == row_id:
                return _build_envelope(row, source_errors)
        raise HTTPException(status_code=404, detail=f"row '{row_id}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("control-surface/rows/<id> failed")
        return _build_envelope(None, [{"source": f"row/{row_id}", "error": str(e)}])
