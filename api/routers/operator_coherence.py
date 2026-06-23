"""Operator Coherence Cockpit API.

Serves the normalized read-only projection used by /dashboard/cockpit.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/operator-coherence", tags=["operator-coherence"])
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _envelope(data: Any, source_errors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from dharma_swarm.operator_core.control_surface_models import _utc_now_iso

    return {
        "status": "ok" if not source_errors else "partial",
        "schema_version": "operator_coherence_api.v0.1",
        "request_id": str(uuid.uuid4()),
        "generated_at": _utc_now_iso(),
        "timestamp": _utc_now_iso(),
        "error": "",
        "source_errors": source_errors or [],
        "data": data,
    }


@router.get("/report")
def operator_coherence_report(
    github: bool = Query(False, description="Include GitHub gh PR/CI probes when auth exists."),
    live_probes: bool = Query(True, description="Include tmux/launchctl/ps probes."),
) -> dict[str, Any]:
    """Return the full cockpit projection.

    GitHub is opt-in for the dashboard route because local gh auth can be slow
    or absent; the CLI generator enables it by default.
    """
    try:
        from dharma_swarm.operator_core.operator_coherence_cockpit import (
            build_operator_coherence_cockpit,
        )

        payload = build_operator_coherence_cockpit(
            _REPO_ROOT,
            include_github=github,
            include_live_probes=live_probes,
        )
        return _envelope(payload, payload.get("source_errors", []))
    except Exception as exc:  # pragma: no cover - defensive API boundary
        logger.exception("operator-coherence/report failed")
        return _envelope(None, [{"source": "operator_coherence_projection", "error": "internal error"}])
