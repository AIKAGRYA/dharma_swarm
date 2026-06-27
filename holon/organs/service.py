"""Standalone supervisor lock and service heartbeat helpers."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from holon.receipts import stable_digest

LOCK_SCHEMA_VERSION = "holon.service_lock.v1"
HEARTBEAT_SCHEMA_VERSION = "holon.service_heartbeat.v1"
HEARTBEAT_LEDGER_NAME = "service_heartbeats.jsonl"
LIVE_STATUSES = {"running", "idle", "safe_refusal"}


@dataclass(frozen=True)
class ServiceLock:
    acquired: bool
    path: str
    lock_id: str = ""
    holder: str = ""
    expires_at: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def supervisor_lock_path(name: str, *, agents_root: Path) -> Path:
    return agents_root / name / "supervisor.lock"


def service_heartbeat_path(name: str, *, agents_root: Path) -> Path:
    return agents_root / name / HEARTBEAT_LEDGER_NAME


def acquire_service_lock(
    name: str,
    *,
    agents_root: Path,
    holder: str,
    lease_seconds: int = 300,
    lock_path: Path | None = None,
) -> ServiceLock:
    path = lock_path or supervisor_lock_path(name, agents_root=agents_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = _utc_now()
    lease = max(1, int(lease_seconds))
    _remove_expired_lock(path, now=now)
    expires_at = _format_utc(now + timedelta(seconds=lease))
    lock_id = stable_digest(
        {
            "holon": name,
            "holder": holder,
            "path": str(path),
            "observed_at": _format_utc(now),
            "expires_at": expires_at,
        }
    )
    payload = {
        "schema_version": LOCK_SCHEMA_VERSION,
        "holon": name,
        "holder": holder,
        "lock_id": lock_id,
        "acquired_at": _format_utc(now),
        "expires_at": expires_at,
    }
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return ServiceLock(
            acquired=False,
            path=str(path),
            holder=holder,
            reason="lock_held",
        )
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return ServiceLock(
        acquired=True,
        path=str(path),
        lock_id=lock_id,
        holder=holder,
        expires_at=expires_at,
    )


def release_service_lock(lock: ServiceLock) -> bool:
    if not lock.acquired:
        return False
    path = Path(lock.path)
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if str(payload.get("lock_id") or "") != lock.lock_id:
        return False
    path.unlink()
    return True


def record_service_heartbeat(
    name: str,
    *,
    agents_root: Path,
    session_id: str = "",
    service_id: str = "holon-supervisor",
    status: str = "running",
    runtime_ref: dict[str, Any] | None = None,
    proof_ref: dict[str, Any] | None = None,
    claim_scope: dict[str, Any] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    path = service_heartbeat_path(name, agents_root=agents_root)
    rows, _errors = _read_rows(path)
    previous_hash = str(rows[-1].get("record_hash") or "") if rows else ""
    row = {
        "schema_version": HEARTBEAT_SCHEMA_VERSION,
        "holon": name,
        "service_id": service_id,
        "session_id": session_id,
        "status": status,
        "observed_at": _format_utc(observed_at or _utc_now()),
        "runtime_ref": dict(runtime_ref or {}),
        "proof_ref": dict(proof_ref or {}),
        "claim_scope": dict(claim_scope or {}),
        "previous_record_hash": previous_hash,
        "record_hash": "",
    }
    row["record_hash"] = stable_digest(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


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
        if observed_hash != stable_digest(material):
            errors.append(f"line {index}: record_hash mismatch")
        previous_hash = observed_hash
    return len(errors) == 0, errors


def latest_service_heartbeat(
    name: str,
    *,
    agents_root: Path,
    service_id: str | None = None,
) -> dict[str, Any] | None:
    rows, _errors = _read_rows(service_heartbeat_path(name, agents_root=agents_root))
    if service_id:
        rows = [row for row in rows if str(row.get("service_id") or "") == service_id]
    return dict(rows[-1]) if rows else None


def assess_service_liveness(
    name: str,
    *,
    agents_root: Path,
    service_id: str | None = None,
    now: datetime | None = None,
    fresh_after_seconds: int = 300,
) -> dict[str, Any]:
    path = service_heartbeat_path(name, agents_root=agents_root)
    ledger_ok, ledger_errors = verify_service_heartbeat_ledger(path)
    latest = latest_service_heartbeat(name, agents_root=agents_root, service_id=service_id)
    observed = _parse_utc(str((latest or {}).get("observed_at") or ""))
    current = now or _utc_now()
    age_seconds = None
    if observed is not None:
        age_seconds = max(0.0, round((current - observed).total_seconds(), 3))
    fresh_limit = max(1, int(fresh_after_seconds))
    status = str((latest or {}).get("status") or "unknown")
    fresh = age_seconds is not None and age_seconds <= fresh_limit
    return {
        "schema_version": "holon.service_liveness.v1",
        "holon": name,
        "heartbeat_seen": latest is not None,
        "service_alive": bool(latest and fresh and ledger_ok and status in LIVE_STATUSES),
        "fresh": fresh,
        "status": status,
        "age_seconds": age_seconds,
        "fresh_after_seconds": fresh_limit,
        "ledger_ok": ledger_ok,
        "ledger_errors": ledger_errors,
        "heartbeat_path": str(path),
        "latest_record_hash": str((latest or {}).get("record_hash") or ""),
        "latest_observed_at": str((latest or {}).get("observed_at") or ""),
        "latest_service_id": str((latest or {}).get("service_id") or ""),
    }


def _remove_expired_lock(path: Path, *, now: datetime) -> None:
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    expires_at = _parse_utc(str(payload.get("expires_at") or ""))
    if expires_at is not None and expires_at <= now:
        path.unlink()


def _read_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"{path.name} missing"]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            errors.append(f"line {index}: invalid_json")
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            errors.append(f"line {index}: not_object")
    if not rows and not errors:
        errors.append(f"{path.name} empty")
    return rows, errors


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _format_utc(value: datetime) -> str:
    observed = value
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=UTC)
    return observed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

