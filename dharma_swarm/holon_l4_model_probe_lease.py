"""Governed lease receipts for live L4 HOLON model probes."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dharma_swarm.holon_bridge import AGENTS_ROOT, load_holon
from dharma_swarm.holon_l4_smoke import (
    MODEL_PROBE_LEASE_SCHEMA_VERSION,
    model_probe_lease_digest,
)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso_z(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_lease_filename(lease_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(lease_id or "").strip()).strip("._")
    while ".." in safe:
        safe = safe.replace("..", "_")
    return safe or "model_probe_lease"


def default_model_probe_lease_path(
    name: str,
    *,
    lease_id: str,
    agents_root: Path | None = None,
) -> Path:
    return (agents_root or AGENTS_ROOT) / name / "leases" / f"{safe_lease_filename(lease_id)}.json"


def issue_model_probe_lease(
    *,
    name: str,
    session_id: str,
    lease_id: str = "",
    agents_root: Path | None = None,
    duration_seconds: int = 900,
    allow_subprocess_provider: bool = False,
    purpose: str = "L4 HOLON live model responsiveness probe.",
    now: datetime | None = None,
) -> dict[str, Any]:
    holon = load_holon(name, agents_root=agents_root)
    issued_at = (now or _utc_now()).astimezone(UTC).replace(microsecond=0)
    bounded_duration = max(1, int(duration_seconds))
    rendered_lease_id = str(lease_id or f"lease:l4-model-probe:{session_id}")
    payload: dict[str, Any] = {
        "schema_version": MODEL_PROBE_LEASE_SCHEMA_VERSION,
        "lease_id": rendered_lease_id,
        "holon": holon.name,
        "provider_type": holon.provider_type,
        "model": holon.model,
        "session_id": session_id,
        "allow_live_model_probe": True,
        "allow_subprocess_provider": bool(allow_subprocess_provider),
        "issued_at": _iso_z(issued_at),
        "expires_at": _iso_z(issued_at + timedelta(seconds=bounded_duration)),
        "purpose": str(purpose or "")[:500],
    }
    payload["digest"] = model_probe_lease_digest(payload)
    return payload


def write_model_probe_lease(payload: dict[str, Any], path: Path | str) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return target


__all__ = [
    "default_model_probe_lease_path",
    "issue_model_probe_lease",
    "safe_lease_filename",
    "write_model_probe_lease",
]
