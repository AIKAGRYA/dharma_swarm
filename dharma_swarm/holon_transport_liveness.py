"""Read-only transport reachability projection for HOLON gateways.

This module consumes existing A2A inbox bridge heartbeat files. It does not
publish messages, inspect NATS directly, or create transport state.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TRANSPORT_LIVENESS_SCHEMA_VERSION = "dharma.holon_transport_liveness.v1"
A2A_INBOX_HEARTBEAT_SCHEMA_VERSION = "dharma.a2a.inbox_bridge_heartbeat.v1"
DEFAULT_A2A_HEARTBEAT_FRESH_SECONDS = 3600
DEFAULT_A2A_BUS = Path.home() / ".dharma" / "a2a_bus"
DEFAULT_A2A_BRIDGE_HEARTBEATS = DEFAULT_A2A_BUS / "bridge_heartbeats"
STATUS_NO_MESSAGES = "NO_MESSAGES"
STATUS_DELIVERED_AND_ACKED = "DELIVERED_AND_ACKED"
STATUS_INVALID_ENVELOPE_ACKED = "INVALID_ENVELOPE_ACKED"
REACHABLE_A2A_STATUSES = {
    "IDLE",
    STATUS_NO_MESSAGES,
    STATUS_DELIVERED_AND_ACKED,
    STATUS_INVALID_ENVELOPE_ACKED,
}


def default_a2a_bridge_heartbeat_file(agent_uid: str) -> Path:
    safe_agent_uid = "".join(
        char if char.isalnum() or char in ("_", "-") else "_"
        for char in str(agent_uid or "").strip()
    ).strip("_-")
    return DEFAULT_A2A_BRIDGE_HEARTBEATS / f"{safe_agent_uid or 'unknown'}.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_utc(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _age_seconds(timestamp: str, now: datetime) -> float | None:
    observed = _parse_utc(timestamp)
    if observed is None:
        return None
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return max(0.0, round((current.astimezone(UTC) - observed).total_seconds(), 3))


def assess_a2a_inbox_bridge_liveness(
    agent_uid: str,
    *,
    heartbeat_path: Path | None = None,
    now: datetime | None = None,
    fresh_after_seconds: int = DEFAULT_A2A_HEARTBEAT_FRESH_SECONDS,
) -> dict[str, Any]:
    path = heartbeat_path or default_a2a_bridge_heartbeat_file(agent_uid)
    payload = _read_json(path)
    current = now or datetime.now(UTC)
    timestamp = str(payload.get("timestamp") or payload.get("ts") or "")
    age_seconds = _age_seconds(timestamp, current)
    fresh_limit = max(1, int(fresh_after_seconds))
    fresh = age_seconds is not None and age_seconds <= fresh_limit
    schema_ok = payload.get("schema_version") == A2A_INBOX_HEARTBEAT_SCHEMA_VERSION
    status = str(payload.get("status") or "unknown")
    heartbeat_seen = bool(payload)
    transport_reachable = bool(
        heartbeat_seen
        and schema_ok
        and fresh
        and status in REACHABLE_A2A_STATUSES
    )
    failure_reasons: list[str] = []
    if not heartbeat_seen:
        failure_reasons.append("a2a_inbox_bridge_heartbeat_missing")
    if heartbeat_seen and not schema_ok:
        failure_reasons.append("a2a_inbox_bridge_heartbeat_schema_mismatch")
    if heartbeat_seen and not fresh:
        failure_reasons.append("a2a_inbox_bridge_heartbeat_stale")
    if heartbeat_seen and status not in REACHABLE_A2A_STATUSES:
        failure_reasons.append(f"a2a_inbox_bridge_status_{status.lower()}")
    return {
        "schema_version": TRANSPORT_LIVENESS_SCHEMA_VERSION,
        "transport": "a2a_inbox_bridge",
        "agent_uid": agent_uid,
        "heartbeat_path": str(path),
        "heartbeat_seen": heartbeat_seen,
        "schema_ok": schema_ok,
        "transport_reachable": transport_reachable,
        "fresh": fresh,
        "fresh_after_seconds": fresh_limit,
        "age_seconds": age_seconds,
        "status": status,
        "timestamp": timestamp,
        "subject": str(payload.get("subject") or ""),
        "stream": str(payload.get("stream") or ""),
        "consumer": str(payload.get("consumer") or ""),
        "cycle": int(payload.get("cycle") or 0),
        "last_receipt_path": str(payload.get("last_receipt_path") or ""),
        "failure_reasons": failure_reasons,
    }
