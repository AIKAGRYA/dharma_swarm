"""One read-only reconciliation authority composed from existing projections."""

from __future__ import annotations

from typing import Any

from dharma_swarm.forge_lab.operator_views import reconcile
from dharma_swarm.forge_lab.reconciliation import reconciliation_status

COMPOSITE_STATUS_SCHEMA = "rsi_lab.reconcile_composite.v1"


def composite_reconciliation_status() -> dict[str, Any]:
    """Return every currently blocking reconciliation finding in one view."""

    control_plane = reconciliation_status()
    legacy_projection = reconcile()
    findings = list(control_plane.get("findings") or []) + list(
        legacy_projection.get("findings") or []
    )
    return {
        "schema": COMPOSITE_STATUS_SCHEMA,
        "ok": bool(control_plane.get("ok") and legacy_projection.get("ok")),
        "read_only": True,
        "findings": findings,
        "control_plane": control_plane,
        "legacy_projection": legacy_projection,
    }


__all__ = ["COMPOSITE_STATUS_SCHEMA", "composite_reconciliation_status"]
