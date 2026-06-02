"""Live ops census adapter for the Control Surface Projector."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.control_surface_models import (
    ControlSurfaceRow,
    _utc_now_iso,
)

logger = logging.getLogger(__name__)


def _live_ops_census_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Load or build the read-only live ops census."""
    root = repo_root or Path.cwd()
    output = Path.home() / ".dharma" / "ops" / "live_process_census.json"
    try:
        if output.exists():
            age = datetime.now(timezone.utc).timestamp() - output.stat().st_mtime
            if age <= 300:
                return json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.debug("live ops census cache unreadable", exc_info=True)

    try:
        from scripts.runtime.live_ops_census import build_live_ops_census

        return build_live_ops_census(repo_root=root, run_probes=True)
    except Exception as exc:
        logger.warning("live ops census adapter failed: %s", exc)
        return {
            "schema_version": "live_ops_census.v1",
            "generated_at": _utc_now_iso(),
            "surfaces": [
                {
                    "id": "adapter.error",
                    "label": "Live ops census adapter",
                    "class": "substrate",
                    "status": "unknown",
                    "desired_state": "live",
                    "priority": "p0",
                    "evidence": [f"adapter error: {exc}"],
                    "authority_refs": ["scripts/runtime/live_ops_census.py"],
                    "human_authority_required": True,
                    "next_action": "inspect live ops census adapter",
                    "raw": {},
                }
            ],
        }


def _live_ops_coherence(surface: dict[str, Any]) -> str:
    status = str(surface.get("status") or "unknown")
    priority = str(surface.get("priority") or "unknown")
    if status == "live":
        return "bound"
    if status in {"blocked", "stale"}:
        return "drifted"
    if status == "stopped":
        return "drifted" if priority == "p0" else "partial"
    if status == "unknown":
        return "unknown"
    return "partial"


def _rows_from_live_ops_census(
    payload: dict[str, Any],
    repo_root: Path | None = None,
) -> list[ControlSurfaceRow]:
    root = repo_root or Path.cwd()
    rows: list[ControlSurfaceRow] = []
    for surface in payload.get("surfaces", []):
        sid = str(surface.get("id") or "unknown")
        status = str(surface.get("status") or "unknown")
        gap_codes = [f"live_ops_status:{status}"]
        if status != "live":
            gap_codes.append("live_ops_not_live")
        if surface.get("human_authority_required"):
            gap_codes.append("human_authority_required")
        if surface.get("vps_candidate"):
            gap_codes.append("vps_candidate")
        if surface.get("class") == "heavy":
            gap_codes.append("heavy_local_load")

        row = ControlSurfaceRow(
            id=f"live_ops.{sid}",
            kind="fleet",
            label=str(surface.get("label") or sid),
            authority_role="observed_authority",
            declared_state=str(surface.get("desired_state") or ""),
            desired_state=str(surface.get("desired_state") or ""),
            observed_state=status,
            coherence_state=_live_ops_coherence(surface),
            priority=str(surface.get("priority") or "unknown"),
            owner_module="scripts/runtime/live_ops_census.py",
            truth_owner="live_ops_census",
            freshness=str(surface.get("freshness") or payload.get("generated_at") or ""),
            gap_codes=gap_codes,
            next_action=str(surface.get("next_action") or ""),
            raw=surface,
        )
        row.add_source_ref("file", "scripts/runtime/live_ops_census.py", exists=True)
        for ref in surface.get("authority_refs", []):
            ref_str = str(ref)
            if not ref_str:
                continue
            ref_path = Path(ref_str)
            if ref_path.is_absolute():
                row.add_source_ref("config", ref_str, exists=ref_path.exists())
            else:
                row.add_source_ref("file", ref_str, exists=(root / ref_str).exists())
        for ev in surface.get("evidence", []):
            ev_str = str(ev)
            if ev_str:
                row.add_evidence(
                    "process",
                    ev_str,
                    status=status,
                    provenance_chain=["live_ops_census", sid],
                )
        if surface.get("pids"):
            row.add_evidence(
                "process",
                f"pids={','.join(str(pid) for pid in surface.get('pids', []))}",
                status="present",
                provenance_chain=["live_ops_census", sid, "process_snapshot"],
            )
        if surface.get("port"):
            port_status = "present" if surface.get("port_listening") else "missing"
            row.add_evidence(
                "process",
                f"port:{surface.get('port')}",
                status=port_status,
                provenance_chain=["live_ops_census", sid, "port_snapshot"],
            )
        rows.append(row)
    return rows


def _live_ops_census_rows(repo_root: Path | None = None) -> list[ControlSurfaceRow]:
    return _rows_from_live_ops_census(_live_ops_census_payload(repo_root), repo_root)
