"""Transport reachability projection for HOLON gateways.

This module consumes existing A2A inbox bridge heartbeat files and can append a
derived, per-holon LivingDock transport heartbeat. It does not publish messages
or create a new bus; the append-only ledger lives under the canonical agent
home as ``transport_heartbeats.jsonl``.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dharma_swarm.holon_bridge import AGENTS_ROOT
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now

TRANSPORT_LIVENESS_SCHEMA_VERSION = "dharma.holon_transport_liveness.v1"
TRANSPORT_HEARTBEAT_SCHEMA_VERSION = "dharma.holon_transport_heartbeat.v1"
A2A_INBOX_HEARTBEAT_SCHEMA_VERSION = "dharma.a2a.inbox_bridge_heartbeat.v1"
DEFAULT_A2A_HEARTBEAT_FRESH_SECONDS = 3600
DEFAULT_A2A_BUS = Path.home() / ".dharma" / "a2a_bus"
DEFAULT_A2A_BRIDGE_HEARTBEATS = DEFAULT_A2A_BUS / "bridge_heartbeats"
TRANSPORT_HEARTBEAT_LEDGER_NAME = "transport_heartbeats.jsonl"
STATUS_NO_MESSAGES = "NO_MESSAGES"
STATUS_DELIVERED_AND_ACKED = "DELIVERED_AND_ACKED"
STATUS_INVALID_ENVELOPE_ACKED = "INVALID_ENVELOPE_ACKED"
REACHABLE_A2A_STATUSES = {
    "IDLE",
    STATUS_NO_MESSAGES,
    STATUS_DELIVERED_AND_ACKED,
    STATUS_INVALID_ENVELOPE_ACKED,
}


def transport_heartbeat_path(name: str, agents_root: Path | None = None) -> Path:
    return (agents_root or AGENTS_ROOT) / name / TRANSPORT_HEARTBEAT_LEDGER_NAME


def default_a2a_bridge_heartbeat_file(agent_uid: str) -> Path:
    safe_agent_uid = "".join(
        char if char.isalnum() or char in ("_", "-") else "_"
        for char in str(agent_uid or "").strip()
    ).strip("_-")
    return DEFAULT_A2A_BRIDGE_HEARTBEATS / f"{safe_agent_uid or 'unknown'}.json"


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


def verify_transport_heartbeat_ledger(path: Path) -> tuple[bool, list[str]]:
    rows, errors = _read_rows(path)
    previous_hash = ""
    for index, row in enumerate(rows, start=1):
        if row.get("schema_version") != TRANSPORT_HEARTBEAT_SCHEMA_VERSION:
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


def latest_transport_heartbeat(
    name: str,
    agents_root: Path | None = None,
    *,
    transport_id: str | None = None,
) -> dict[str, Any] | None:
    rows, _errors = _read_rows(transport_heartbeat_path(name, agents_root))
    if transport_id:
        rows = [row for row in rows if str(row.get("transport_id") or "") == transport_id]
    return dict(rows[-1]) if rows else None


def record_transport_heartbeat(
    name: str,
    *,
    agents_root: Path | None = None,
    transport_id: str = "a2a_inbox_bridge",
    status: str = "reachable",
    observed_at: datetime | None = None,
    runtime_ref: dict[str, Any] | None = None,
    proof_ref: dict[str, Any] | None = None,
    claim_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = transport_heartbeat_path(name, agents_root)
    rows, _errors = _read_rows(path)
    previous_hash = str(rows[-1].get("record_hash") or "") if rows else ""
    row = {
        "schema_version": TRANSPORT_HEARTBEAT_SCHEMA_VERSION,
        "holon": name,
        "transport_id": transport_id,
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


def record_a2a_bridge_transport_heartbeat(
    name: str,
    *,
    agents_root: Path | None = None,
    heartbeat_path: Path | None = None,
    now: datetime | None = None,
    fresh_after_seconds: int = DEFAULT_A2A_HEARTBEAT_FRESH_SECONDS,
) -> dict[str, Any]:
    liveness = assess_a2a_inbox_bridge_liveness(
        name,
        heartbeat_path=heartbeat_path,
        now=now,
        fresh_after_seconds=fresh_after_seconds,
    )
    status = "reachable" if liveness["transport_reachable"] else "unreachable"
    return record_transport_heartbeat(
        name,
        agents_root=agents_root,
        transport_id="a2a_inbox_bridge",
        status=status,
        observed_at=now,
        runtime_ref={
            "subject": liveness["subject"],
            "stream": liveness["stream"],
            "consumer": liveness["consumer"],
            "cycle": liveness["cycle"],
        },
        proof_ref={
            "kind": "a2a_inbox_bridge_heartbeat",
            "heartbeat_path": liveness["heartbeat_path"],
            "last_receipt_path": liveness["last_receipt_path"],
            "source_status": liveness["status"],
            "failure_reasons": liveness["failure_reasons"],
        },
        claim_scope={
            "transport_reachable": bool(liveness["transport_reachable"]),
            "fresh": bool(liveness["fresh"]),
            "schema_ok": bool(liveness["schema_ok"]),
        },
    )


def assess_transport_liveness(
    name: str,
    *,
    agents_root: Path | None = None,
    now: datetime | None = None,
    fresh_after_seconds: int = 300,
    transport_id: str | None = None,
) -> dict[str, Any]:
    path = transport_heartbeat_path(name, agents_root)
    ledger_ok, ledger_errors = verify_transport_heartbeat_ledger(path)
    latest = latest_transport_heartbeat(name, agents_root, transport_id=transport_id)
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    age_seconds = _age_seconds(str((latest or {}).get("observed_at") or ""), current)
    fresh_limit = max(1, int(fresh_after_seconds))
    fresh = age_seconds is not None and age_seconds <= fresh_limit
    status = str((latest or {}).get("status") or "unknown")
    heartbeat_seen = latest is not None
    transport_reachable = bool(heartbeat_seen and fresh and ledger_ok and status == "reachable")
    return {
        "schema_version": TRANSPORT_LIVENESS_SCHEMA_VERSION,
        "transport": str(transport_id or (latest or {}).get("transport_id") or ""),
        "holon": name,
        "heartbeat_seen": heartbeat_seen,
        "transport_reachable": transport_reachable,
        "fresh": fresh,
        "status": status,
        "age_seconds": age_seconds,
        "fresh_after_seconds": fresh_limit,
        "ledger_ok": ledger_ok,
        "ledger_errors": ledger_errors,
        "heartbeat_path": str(path),
        "latest_record_hash": str((latest or {}).get("record_hash") or ""),
        "latest_observed_at": str((latest or {}).get("observed_at") or ""),
        "latest_transport_id": str((latest or {}).get("transport_id") or ""),
        "required_transport_id": str(transport_id or ""),
        "observed_at": utc_now(),
    }
