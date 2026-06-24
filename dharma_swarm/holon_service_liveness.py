"""Per-holon service heartbeat ledger and liveness projection.

This module owns only HOLON-local service heartbeat evidence. It does not start
or supervise daemons; supervisors and runtimes remain separate owners.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from dharma_swarm.holon_bridge import AGENTS_ROOT
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now

HEARTBEAT_SCHEMA_VERSION = "dharma.holon_service_heartbeat.v1"
LIVENESS_SCHEMA_VERSION = "dharma.holon_service_liveness.v1"
HEARTBEAT_LEDGER_NAME = "service_heartbeats.jsonl"
LIVE_STATUSES = {"running", "idle", "safe_refusal"}

ServiceHeartbeatStatus = Literal[
    "running",
    "idle",
    "paused",
    "safe_refusal",
    "stopped",
    "error",
    "unknown",
]


def service_heartbeat_path(name: str, agents_root: Path | None = None) -> Path:
    return (agents_root or AGENTS_ROOT) / name / HEARTBEAT_LEDGER_NAME


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def _read_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"{path.name} missing"]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                errors.append(f"line {index}: invalid_json")
                continue
            if not isinstance(row, dict):
                errors.append(f"line {index}: not_object")
                continue
            rows.append(row)
    if not rows and not errors:
        errors.append(f"{path.name} empty")
    return rows, errors


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


def _format_utc(value: datetime | None = None) -> str:
    observed = value or datetime.now(UTC)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    return observed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _seal_record(row: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(row)
    sealed["record_hash"] = ""
    sealed["record_hash"] = stable_payload_hash(sealed)
    return sealed


def verify_service_heartbeat_ledger(path: Path) -> tuple[bool, list[str]]:
    rows, errors = _read_rows(path)
    previous_hash = ""
    for index, row in enumerate(rows, start=1):
        if row.get("schema_version") != HEARTBEAT_SCHEMA_VERSION:
            errors.append(f"line {index}: schema_version mismatch")
        if str(row.get("previous_record_hash") or "") != previous_hash:
            errors.append(f"line {index}: previous_record_hash mismatch")
        observed_hash = str(row.get("record_hash") or "")
        material = dict(row)
        material["record_hash"] = ""
        if observed_hash != stable_payload_hash(material):
            errors.append(f"line {index}: record_hash mismatch")
        previous_hash = observed_hash
    return len(errors) == 0, errors


def latest_service_heartbeat(
    name: str,
    agents_root: Path | None = None,
    *,
    service_id: str | None = None,
) -> dict[str, Any] | None:
    rows, _errors = _read_rows(service_heartbeat_path(name, agents_root))
    if service_id:
        rows = [row for row in rows if str(row.get("service_id") or "") == service_id]
    return dict(rows[-1]) if rows else None


def record_service_heartbeat(
    name: str,
    *,
    agents_root: Path | None = None,
    session_id: str = "",
    service_id: str = "holon-service",
    status: ServiceHeartbeatStatus = "running",
    observed_at: datetime | None = None,
    runtime_ref: dict[str, Any] | None = None,
    proof_ref: dict[str, Any] | None = None,
    claim_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = service_heartbeat_path(name, agents_root)
    rows, _errors = _read_rows(path)
    previous_hash = str(rows[-1].get("record_hash") or "") if rows else ""
    row = {
        "schema_version": HEARTBEAT_SCHEMA_VERSION,
        "holon": name,
        "service_id": service_id,
        "session_id": session_id,
        "status": status,
        "observed_at": _format_utc(observed_at),
        "runtime_ref": dict(runtime_ref or {}),
        "proof_ref": dict(proof_ref or {}),
        "claim_scope": dict(claim_scope or {}),
        "previous_record_hash": previous_hash,
        "record_hash": "",
    }
    sealed = _seal_record(row)
    _append_jsonl(path, sealed)
    return sealed


def assess_service_liveness(
    name: str,
    *,
    agents_root: Path | None = None,
    now: datetime | None = None,
    fresh_after_seconds: int = 300,
    service_id: str | None = None,
) -> dict[str, Any]:
    path = service_heartbeat_path(name, agents_root)
    ledger_ok, ledger_errors = verify_service_heartbeat_ledger(path)
    latest = latest_service_heartbeat(name, agents_root, service_id=service_id)
    observed = _parse_utc(str((latest or {}).get("observed_at") or ""))
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    age_seconds = None
    if observed is not None:
        age_seconds = max(0.0, round((current.astimezone(UTC) - observed).total_seconds(), 3))
    fresh_limit = max(1, int(fresh_after_seconds))
    status = str((latest or {}).get("status") or "unknown")
    heartbeat_seen = latest is not None
    fresh = age_seconds is not None and age_seconds <= fresh_limit
    service_alive = bool(heartbeat_seen and fresh and ledger_ok and status in LIVE_STATUSES)
    service_paused = bool(heartbeat_seen and fresh and ledger_ok and status == "paused")
    return {
        "schema_version": LIVENESS_SCHEMA_VERSION,
        "holon": name,
        "heartbeat_seen": heartbeat_seen,
        "service_alive": service_alive,
        "service_paused": service_paused,
        "fresh": fresh,
        "status": status,
        "age_seconds": age_seconds,
        "fresh_after_seconds": fresh_limit,
        "ledger_ok": ledger_ok,
        "ledger_errors": ledger_errors,
        "heartbeat_path": str(path),
        "latest_record_hash": str((latest or {}).get("record_hash") or ""),
        "latest_observed_at": str((latest or {}).get("observed_at") or ""),
        "latest_session_id": str((latest or {}).get("session_id") or ""),
        "latest_service_id": str((latest or {}).get("service_id") or ""),
        "required_service_id": str(service_id or ""),
        "observed_at": utc_now(),
    }
