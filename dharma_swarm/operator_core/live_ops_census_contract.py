"""Shared contract for the live-ops census receipt.

This module owns the small, import-safe contract surface for read models:
receipt schema, owner path, validation, and freshness. The heavy census builder
and writer remain in scripts/runtime/live_ops_census.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir


LIVE_OPS_CENSUS_SCHEMA_VERSION = "live_ops_census.v1"
LIVE_OPS_CENSUS_MAX_AGE_HOURS = 24.0


def default_state_root() -> Path:
    return dharma_state_dir("DHARMA_STATE_DIR").expanduser()


def default_output_path() -> Path:
    return default_state_root() / "ops" / "live_process_census.json"


DEFAULT_STATE_ROOT = default_state_root()
DEFAULT_OUTPUT = default_output_path()


def validate_census_payload(payload: Any) -> list[str]:
    """Return schema errors for a live-ops census payload."""
    if not isinstance(payload, dict):
        return ["live ops census receipt root is not a JSON object"]

    errors: list[str] = []
    schema_version = str(payload.get("schema_version") or "")
    if schema_version != LIVE_OPS_CENSUS_SCHEMA_VERSION:
        errors.append(
            "live ops census receipt schema_version is "
            f"{schema_version or 'missing'}"
        )
    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at:
        errors.append("live ops census receipt is missing generated_at")
    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, list):
        errors.append("live ops census receipt surfaces is missing or not a list")
    elif not surfaces:
        errors.append("live ops census receipt surfaces is empty")
    else:
        malformed_surfaces = [
            index
            for index, surface in enumerate(surfaces)
            if not isinstance(surface, dict)
            or not str(surface.get("id") or surface.get("surface_id") or "")
            or not str(surface.get("status") or "")
        ]
        if malformed_surfaces:
            errors.append(
                "live ops census receipt surfaces have malformed id/status at "
                f"indices {malformed_surfaces[:5]}"
            )
    return errors


def _parse_iso_datetime(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    text = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def census_payload_freshness(
    payload: Any,
    *,
    max_age_hours: float = LIVE_OPS_CENSUS_MAX_AGE_HOURS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return freshness state for a schema-valid live-ops census payload."""
    generated_at = payload.get("generated_at") if isinstance(payload, dict) else None
    parsed = _parse_iso_datetime(generated_at)
    if parsed is None:
        return {
            "state": "stale",
            "age_minutes": None,
            "max_age_hours": max_age_hours,
            "evidence": "live ops census receipt generated_at is missing or unparsable",
        }
    now_utc = (now or datetime.now(UTC)).astimezone(UTC)
    age_minutes = max(0.0, (now_utc - parsed).total_seconds() / 60.0)
    if age_minutes > max_age_hours * 60:
        return {
            "state": "stale",
            "age_minutes": round(age_minutes, 1),
            "max_age_hours": max_age_hours,
            "evidence": (
                "live ops census receipt generated_at is older than "
                f"{max_age_hours:g}h"
            ),
        }
    return {
        "state": "fresh",
        "age_minutes": round(age_minutes, 1),
        "max_age_hours": max_age_hours,
        "evidence": "live ops census receipt generated_at is fresh",
    }
