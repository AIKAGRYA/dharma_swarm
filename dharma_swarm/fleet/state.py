"""Durable SQLite state for future Dharma fleet coordination.

This module is intentionally persistence-only. It does not dispatch tasks,
register API routes, or modify the existing A2A/operator bridge flows.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4


class FleetTaskStatus(str, Enum):
    """Canonical fleet task states."""

    QUEUED = "queued"
    ASSIGNED = "assigned"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FleetTaskPriority(IntEnum):
    """Integer priority for durable ordering and future schedulers."""

    LOW = 0
    NORMAL = 10
    HIGH = 20
    URGENT = 30


class FleetTaskEventType(str, Enum):
    """Typed event names for the canonical fleet task log."""

    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    EVENT = "event"
    ARTIFACT_RECORDED = "artifact_recorded"
    LEASE_SET = "lease_set"
    LEASE_CLEARED = "lease_cleared"


@dataclass(frozen=True)
class FleetTask:
    task_id: str
    title: str
    kind: str
    parent_task_id: str | None = None
    idempotency_key: str | None = None
    description: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    required_capabilities: list[str] = field(default_factory=list)
    repo: str | None = None
    branch: str | None = None
    requested_by: str | None = None
    status: FleetTaskStatus = FleetTaskStatus.QUEUED
    priority: FleetTaskPriority = FleetTaskPriority.NORMAL
    risk_level: str = "normal"
    approval_status: str = "not_required"
    assigned_node_id: str | None = None
    assigned_worker_id: str | None = None
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    correlation_id: str = ""
    trace_id: str = ""
    created_at: datetime = field(default_factory=lambda: _utc_now())
    updated_at: datetime = field(default_factory=lambda: _utc_now())
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FleetTaskEvent:
    event_id: str
    task_id: str
    event_type: FleetTaskEventType
    node_id: str | None = None
    worker_id: str | None = None
    status: FleetTaskStatus | None = None
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"
    correlation_id: str = ""
    trace_id: str = ""
    created_at: datetime = field(default_factory=lambda: _utc_now())


@dataclass(frozen=True)
class FleetTaskArtifact:
    artifact_id: str
    task_id: str
    name: str
    kind: str
    uri: str
    node_id: str | None = None
    worker_id: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: _utc_now())


_TASKS_DDL = """
CREATE TABLE IF NOT EXISTS fleet_tasks (
    task_id TEXT PRIMARY KEY,
    parent_task_id TEXT,
    idempotency_key TEXT UNIQUE,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    required_capabilities_json TEXT NOT NULL DEFAULT '[]',
    repo TEXT,
    branch TEXT,
    requested_by TEXT,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 10,
    risk_level TEXT NOT NULL DEFAULT 'normal',
    approval_status TEXT NOT NULL DEFAULT 'not_required',
    assigned_node_id TEXT,
    assigned_worker_id TEXT,
    lease_owner TEXT,
    lease_expires_at TEXT,
    correlation_id TEXT NOT NULL DEFAULT '',
    trace_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    failed_reason TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (parent_task_id) REFERENCES fleet_tasks(task_id)
)"""

_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS fleet_task_events (
    event_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    node_id TEXT,
    worker_id TEXT,
    event_type TEXT NOT NULL,
    status TEXT,
    message TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    severity TEXT NOT NULL DEFAULT 'info',
    correlation_id TEXT NOT NULL DEFAULT '',
    trace_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES fleet_tasks(task_id) ON DELETE CASCADE
)"""

_ARTIFACTS_DDL = """
CREATE TABLE IF NOT EXISTS fleet_task_artifacts (
    artifact_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    node_id TEXT,
    worker_id TEXT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    uri TEXT NOT NULL,
    sha256 TEXT,
    size_bytes INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES fleet_tasks(task_id) ON DELETE CASCADE
)"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_fleet_tasks_status ON fleet_tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_fleet_tasks_assigned_node ON fleet_tasks(assigned_node_id)",
    "CREATE INDEX IF NOT EXISTS idx_fleet_tasks_assigned_worker ON fleet_tasks(assigned_worker_id)",
    "CREATE INDEX IF NOT EXISTS idx_fleet_tasks_created_at ON fleet_tasks(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_fleet_task_events_task_created ON fleet_task_events(task_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_fleet_task_events_type_created ON fleet_task_events(event_type, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_fleet_task_artifacts_task ON fleet_task_artifacts(task_id)",
]

_APPROVAL_STATUSES = frozenset({"not_required", "pending", "approved", "rejected"})
_SEVERITIES = frozenset({"debug", "info", "warning", "error", "critical"})
_PRIORITY_BY_NAME = {
    "low": FleetTaskPriority.LOW,
    "normal": FleetTaskPriority.NORMAL,
    "high": FleetTaskPriority.HIGH,
    "urgent": FleetTaskPriority.URGENT,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _json_load(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _dt_to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _coerce_status(value: FleetTaskStatus | str) -> FleetTaskStatus:
    if isinstance(value, FleetTaskStatus):
        return value
    try:
        return FleetTaskStatus(str(value))
    except ValueError as exc:
        raise ValueError(f"Invalid fleet task status: {value!r}") from exc


def _coerce_event_type(value: FleetTaskEventType | str) -> FleetTaskEventType:
    if isinstance(value, FleetTaskEventType):
        return value
    try:
        return FleetTaskEventType(str(value))
    except ValueError as exc:
        raise ValueError(f"Invalid fleet task event type: {value!r}") from exc


def _coerce_priority(value: FleetTaskPriority | int | str) -> FleetTaskPriority:
    if isinstance(value, FleetTaskPriority):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _PRIORITY_BY_NAME:
            return _PRIORITY_BY_NAME[normalized]
        if normalized.isdigit():
            value = int(normalized)
    try:
        return FleetTaskPriority(int(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid fleet task priority: {value!r}") from exc


def _validate_approval_status(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in _APPROVAL_STATUSES:
        raise ValueError(f"Invalid fleet approval status: {value!r}")
    return normalized


def _validate_severity(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized not in _SEVERITIES:
        raise ValueError(f"Invalid fleet event severity: {value!r}")
    return normalized


def _row_to_task(row: sqlite3.Row) -> FleetTask:
    return FleetTask(
        task_id=str(row["task_id"]),
        parent_task_id=row["parent_task_id"],
        idempotency_key=row["idempotency_key"],
        title=str(row["title"]),
        kind=str(row["kind"]),
        description=str(row["description"] or ""),
        payload=_json_load(row["payload_json"], {}),
        required_capabilities=list(_json_load(row["required_capabilities_json"], [])),
        repo=row["repo"],
        branch=row["branch"],
        requested_by=row["requested_by"],
        status=_coerce_status(str(row["status"])),
        priority=_coerce_priority(int(row["priority"])),
        risk_level=str(row["risk_level"] or "normal"),
        approval_status=str(row["approval_status"] or "not_required"),
        assigned_node_id=row["assigned_node_id"],
        assigned_worker_id=row["assigned_worker_id"],
        lease_owner=row["lease_owner"],
        lease_expires_at=_parse_dt(row["lease_expires_at"]),
        correlation_id=str(row["correlation_id"] or ""),
        trace_id=str(row["trace_id"] or ""),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
        started_at=_parse_dt(row["started_at"]),
        completed_at=_parse_dt(row["completed_at"]),
        failed_reason=row["failed_reason"],
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_event(row: sqlite3.Row) -> FleetTaskEvent:
    return FleetTaskEvent(
        event_id=str(row["event_id"]),
        task_id=str(row["task_id"]),
        node_id=row["node_id"],
        worker_id=row["worker_id"],
        event_type=_coerce_event_type(str(row["event_type"])),
        status=_coerce_status(str(row["status"])) if row["status"] else None,
        message=str(row["message"] or ""),
        payload=_json_load(row["payload_json"], {}),
        severity=str(row["severity"] or "info"),
        correlation_id=str(row["correlation_id"] or ""),
        trace_id=str(row["trace_id"] or ""),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
    )


def _row_to_artifact(row: sqlite3.Row) -> FleetTaskArtifact:
    return FleetTaskArtifact(
        artifact_id=str(row["artifact_id"]),
        task_id=str(row["task_id"]),
        node_id=row["node_id"],
        worker_id=row["worker_id"],
        name=str(row["name"]),
        kind=str(row["kind"]),
        uri=str(row["uri"]),
        sha256=row["sha256"],
        size_bytes=int(row["size_bytes"]) if row["size_bytes"] is not None else None,
        metadata=_json_load(row["metadata_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
    )


class FleetStateStore:
    """WAL-backed SQLite store for canonical fleet task state."""

    _BUSY_TIMEOUT_S = 30
    _LOCK_RETRY_DELAYS_S = (0.05, 0.1, 0.25, 0.5, 1.0)

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def _open(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=self._BUSY_TIMEOUT_S)

    @staticmethod
    def _configure_connection(db: sqlite3.Connection) -> None:
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=NORMAL")

    @contextmanager
    def _connect(self, *, row_factory: Any | None = None) -> Iterator[sqlite3.Connection]:
        with self._open() as db:
            self._configure_connection(db)
            if row_factory is not None:
                db.row_factory = row_factory
            yield db

    @staticmethod
    def _is_locked_error(exc: BaseException) -> bool:
        return "database is locked" in str(exc).lower()

    def _run_with_lock_retry(self, operation):
        delays = (0.0, *self._LOCK_RETRY_DELAYS_S)
        for attempt, delay in enumerate(delays):
            if delay:
                time.sleep(delay)
            try:
                return operation()
            except sqlite3.OperationalError as exc:
                if not self._is_locked_error(exc) or attempt == len(delays) - 1:
                    raise
        raise RuntimeError("unreachable SQLite retry state")

    def init_db(self) -> None:
        """Create fleet state tables and indexes idempotently."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        def _init() -> None:
            with self._connect() as db:
                db.execute("PRAGMA journal_mode=WAL")
                for ddl in (_TASKS_DDL, _EVENTS_DDL, _ARTIFACTS_DDL):
                    db.execute(ddl)
                for index in _INDEXES:
                    db.execute(index)
                db.commit()

        self._run_with_lock_retry(_init)

    def create_task(
        self,
        *,
        title: str,
        kind: str = "general",
        description: str = "",
        payload: dict[str, Any] | None = None,
        required_capabilities: list[str] | None = None,
        parent_task_id: str | None = None,
        idempotency_key: str | None = None,
        repo: str | None = None,
        branch: str | None = None,
        requested_by: str | None = None,
        status: FleetTaskStatus | str = FleetTaskStatus.QUEUED,
        priority: FleetTaskPriority | int | str = FleetTaskPriority.NORMAL,
        risk_level: str = "normal",
        approval_status: str = "not_required",
        assigned_node_id: str | None = None,
        assigned_worker_id: str | None = None,
        correlation_id: str = "",
        trace_id: str = "",
        metadata: dict[str, Any] | None = None,
        task_id: str | None = None,
        now: datetime | None = None,
    ) -> FleetTask:
        """Create a task, returning an existing record for matching idempotency keys."""
        self.init_db()
        if not title.strip():
            raise ValueError("Fleet task title is required")
        if not kind.strip():
            raise ValueError("Fleet task kind is required")
        status_value = _coerce_status(status)
        priority_value = _coerce_priority(priority)
        approval_value = _validate_approval_status(approval_status)
        now_dt = now or _utc_now()
        now_iso = now_dt.isoformat()
        record_id = task_id or _new_id("ftask")
        payload_dict = dict(payload or {})
        capability_list = list(required_capabilities or [])
        metadata_dict = dict(metadata or {})

        def _create() -> FleetTask:
            with self._connect(row_factory=sqlite3.Row) as db:
                if idempotency_key:
                    cursor = db.execute(
                        "SELECT * FROM fleet_tasks WHERE idempotency_key = ?",
                        (idempotency_key,),
                    )
                    existing = cursor.fetchone()
                    if existing is not None:
                        return _row_to_task(existing)

                db.execute(
                    "INSERT INTO fleet_tasks"
                    " (task_id, parent_task_id, idempotency_key, title, kind,"
                    " description, payload_json, required_capabilities_json, repo,"
                    " branch, requested_by, status, priority, risk_level,"
                    " approval_status, assigned_node_id, assigned_worker_id,"
                    " correlation_id, trace_id, created_at, updated_at, metadata_json)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        record_id,
                        parent_task_id,
                        idempotency_key,
                        title,
                        kind,
                        description,
                        _json_dump(payload_dict),
                        _json_dump(capability_list),
                        repo,
                        branch,
                        requested_by,
                        status_value.value,
                        int(priority_value),
                        risk_level,
                        approval_value,
                        assigned_node_id,
                        assigned_worker_id,
                        correlation_id,
                        trace_id,
                        now_iso,
                        now_iso,
                        _json_dump(metadata_dict),
                    ),
                )
                self._insert_event_db(
                    db,
                    task_id=record_id,
                    event_type=FleetTaskEventType.CREATED,
                    status=status_value,
                    message="fleet task created",
                    payload={"title": title, "kind": kind},
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    created_at=now_dt,
                )
                cursor = db.execute("SELECT * FROM fleet_tasks WHERE task_id = ?", (record_id,))
                row = cursor.fetchone()
                db.commit()
                return _row_to_task(row)

        return self._run_with_lock_retry(_create)

    def get_task(self, task_id: str) -> FleetTask | None:
        self.init_db()
        with self._connect(row_factory=sqlite3.Row) as db:
            cursor = db.execute("SELECT * FROM fleet_tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
        return _row_to_task(row) if row is not None else None

    def list_tasks(
        self,
        *,
        status: FleetTaskStatus | str | None = None,
        assigned_node_id: str | None = None,
        assigned_worker_id: str | None = None,
        limit: int = 100,
    ) -> list[FleetTask]:
        self.init_db()
        if limit <= 0:
            return []
        query = "SELECT * FROM fleet_tasks WHERE 1=1"
        params: list[Any] = []
        if status is not None:
            query += " AND status = ?"
            params.append(_coerce_status(status).value)
        if assigned_node_id is not None:
            query += " AND assigned_node_id = ?"
            params.append(assigned_node_id)
        if assigned_worker_id is not None:
            query += " AND assigned_worker_id = ?"
            params.append(assigned_worker_id)
        query += " ORDER BY created_at ASC LIMIT ?"
        params.append(int(limit))

        with self._connect(row_factory=sqlite3.Row) as db:
            rows = db.execute(query, params).fetchall()
        return [_row_to_task(row) for row in rows]

    def update_task_status(
        self,
        task_id: str,
        status: FleetTaskStatus | str,
        *,
        message: str = "",
        payload: dict[str, Any] | None = None,
        node_id: str | None = None,
        worker_id: str | None = None,
        failed_reason: str | None = None,
        correlation_id: str = "",
        trace_id: str = "",
        now: datetime | None = None,
    ) -> FleetTask:
        """Update task status and append a status event in the same transaction."""
        self.init_db()
        status_value = _coerce_status(status)
        now_dt = now or _utc_now()
        now_iso = now_dt.isoformat()

        def _update() -> FleetTask:
            with self._connect(row_factory=sqlite3.Row) as db:
                cursor = db.execute("SELECT * FROM fleet_tasks WHERE task_id = ?", (task_id,))
                current = cursor.fetchone()
                if current is None:
                    raise KeyError(f"Fleet task {task_id!r} not found")

                current_status = str(current["status"])
                started_at = current["started_at"]
                completed_at = current["completed_at"]
                if status_value == FleetTaskStatus.RUNNING and not started_at:
                    started_at = now_iso
                if status_value in {
                    FleetTaskStatus.COMPLETED,
                    FleetTaskStatus.FAILED,
                    FleetTaskStatus.CANCELLED,
                } and not completed_at:
                    completed_at = now_iso

                db.execute(
                    "UPDATE fleet_tasks SET status = ?, updated_at = ?, started_at = ?,"
                    " completed_at = ?, failed_reason = COALESCE(?, failed_reason)"
                    " WHERE task_id = ?",
                    (
                        status_value.value,
                        now_iso,
                        started_at,
                        completed_at,
                        failed_reason,
                        task_id,
                    ),
                )
                event_payload = {
                    "old_status": current_status,
                    "new_status": status_value.value,
                    **dict(payload or {}),
                }
                self._insert_event_db(
                    db,
                    task_id=task_id,
                    event_type=FleetTaskEventType.STATUS_CHANGED,
                    node_id=node_id,
                    worker_id=worker_id,
                    status=status_value,
                    message=message or f"fleet task status changed to {status_value.value}",
                    payload=event_payload,
                    correlation_id=correlation_id or str(current["correlation_id"] or ""),
                    trace_id=trace_id or str(current["trace_id"] or ""),
                    created_at=now_dt,
                )
                row = db.execute("SELECT * FROM fleet_tasks WHERE task_id = ?", (task_id,)).fetchone()
                db.commit()
                return _row_to_task(row)

        return self._run_with_lock_retry(_update)

    def set_task_lease(
        self,
        task_id: str,
        *,
        lease_owner: str,
        lease_expires_at: datetime | None = None,
        now: datetime | None = None,
    ) -> FleetTask:
        self.init_db()
        if not lease_owner.strip():
            raise ValueError("lease_owner is required")
        now_dt = now or _utc_now()
        now_iso = now_dt.isoformat()

        def _set() -> FleetTask:
            with self._connect(row_factory=sqlite3.Row) as db:
                if db.execute("SELECT 1 FROM fleet_tasks WHERE task_id = ?", (task_id,)).fetchone() is None:
                    raise KeyError(f"Fleet task {task_id!r} not found")
                db.execute(
                    "UPDATE fleet_tasks SET lease_owner = ?, lease_expires_at = ?,"
                    " updated_at = ? WHERE task_id = ?",
                    (lease_owner, _dt_to_iso(lease_expires_at), now_iso, task_id),
                )
                self._insert_event_db(
                    db,
                    task_id=task_id,
                    event_type=FleetTaskEventType.LEASE_SET,
                    message="fleet task lease set",
                    payload={
                        "lease_owner": lease_owner,
                        "lease_expires_at": _dt_to_iso(lease_expires_at),
                    },
                    created_at=now_dt,
                )
                row = db.execute("SELECT * FROM fleet_tasks WHERE task_id = ?", (task_id,)).fetchone()
                db.commit()
                return _row_to_task(row)

        return self._run_with_lock_retry(_set)

    def clear_task_lease(self, task_id: str, *, now: datetime | None = None) -> FleetTask:
        self.init_db()
        now_dt = now or _utc_now()
        now_iso = now_dt.isoformat()

        def _clear() -> FleetTask:
            with self._connect(row_factory=sqlite3.Row) as db:
                if db.execute("SELECT 1 FROM fleet_tasks WHERE task_id = ?", (task_id,)).fetchone() is None:
                    raise KeyError(f"Fleet task {task_id!r} not found")
                db.execute(
                    "UPDATE fleet_tasks SET lease_owner = NULL, lease_expires_at = NULL,"
                    " updated_at = ? WHERE task_id = ?",
                    (now_iso, task_id),
                )
                self._insert_event_db(
                    db,
                    task_id=task_id,
                    event_type=FleetTaskEventType.LEASE_CLEARED,
                    message="fleet task lease cleared",
                    created_at=now_dt,
                )
                row = db.execute("SELECT * FROM fleet_tasks WHERE task_id = ?", (task_id,)).fetchone()
                db.commit()
                return _row_to_task(row)

        return self._run_with_lock_retry(_clear)

    def append_event(
        self,
        *,
        task_id: str,
        event_type: FleetTaskEventType | str = FleetTaskEventType.EVENT,
        node_id: str | None = None,
        worker_id: str | None = None,
        status: FleetTaskStatus | str | None = None,
        message: str = "",
        payload: dict[str, Any] | None = None,
        severity: str = "info",
        correlation_id: str = "",
        trace_id: str = "",
        event_id: str | None = None,
        created_at: datetime | None = None,
    ) -> FleetTaskEvent:
        self.init_db()
        event_type_value = _coerce_event_type(event_type)
        status_value = _coerce_status(status) if status is not None else None
        severity_value = _validate_severity(severity)
        created_dt = created_at or _utc_now()
        record_id = event_id or _new_id("fevent")
        payload_dict = dict(payload or {})

        def _append() -> FleetTaskEvent:
            with self._connect(row_factory=sqlite3.Row) as db:
                if db.execute("SELECT 1 FROM fleet_tasks WHERE task_id = ?", (task_id,)).fetchone() is None:
                    raise KeyError(f"Fleet task {task_id!r} not found")
                self._insert_event_db(
                    db,
                    task_id=task_id,
                    event_type=event_type_value,
                    node_id=node_id,
                    worker_id=worker_id,
                    status=status_value,
                    message=message,
                    payload=payload_dict,
                    severity=severity_value,
                    correlation_id=correlation_id,
                    trace_id=trace_id,
                    event_id=record_id,
                    created_at=created_dt,
                )
                row = db.execute(
                    "SELECT * FROM fleet_task_events WHERE event_id = ?",
                    (record_id,),
                ).fetchone()
                db.commit()
                return _row_to_event(row)

        return self._run_with_lock_retry(_append)

    def list_events(
        self,
        task_id: str,
        *,
        event_type: FleetTaskEventType | str | None = None,
        limit: int = 100,
    ) -> list[FleetTaskEvent]:
        self.init_db()
        if limit <= 0:
            return []
        query = "SELECT * FROM fleet_task_events WHERE task_id = ?"
        params: list[Any] = [task_id]
        if event_type is not None:
            query += " AND event_type = ?"
            params.append(_coerce_event_type(event_type).value)
        query += " ORDER BY created_at ASC, event_id ASC LIMIT ?"
        params.append(int(limit))

        with self._connect(row_factory=sqlite3.Row) as db:
            rows = db.execute(query, params).fetchall()
        return [_row_to_event(row) for row in rows]

    def record_artifact(
        self,
        *,
        task_id: str,
        name: str,
        kind: str,
        uri: str,
        node_id: str | None = None,
        worker_id: str | None = None,
        sha256: str | None = None,
        size_bytes: int | None = None,
        metadata: dict[str, Any] | None = None,
        artifact_id: str | None = None,
        created_at: datetime | None = None,
    ) -> FleetTaskArtifact:
        self.init_db()
        if not name.strip():
            raise ValueError("Fleet artifact name is required")
        if not kind.strip():
            raise ValueError("Fleet artifact kind is required")
        if not uri.strip():
            raise ValueError("Fleet artifact uri is required")
        if size_bytes is not None and size_bytes < 0:
            raise ValueError("Fleet artifact size_bytes cannot be negative")
        record_id = artifact_id or _new_id("fartifact")
        created_dt = created_at or _utc_now()
        metadata_dict = dict(metadata or {})

        def _record() -> FleetTaskArtifact:
            with self._connect(row_factory=sqlite3.Row) as db:
                if db.execute("SELECT 1 FROM fleet_tasks WHERE task_id = ?", (task_id,)).fetchone() is None:
                    raise KeyError(f"Fleet task {task_id!r} not found")
                db.execute(
                    "INSERT INTO fleet_task_artifacts"
                    " (artifact_id, task_id, node_id, worker_id, name, kind, uri,"
                    " sha256, size_bytes, metadata_json, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        record_id,
                        task_id,
                        node_id,
                        worker_id,
                        name,
                        kind,
                        uri,
                        sha256,
                        size_bytes,
                        _json_dump(metadata_dict),
                        created_dt.isoformat(),
                    ),
                )
                row = db.execute(
                    "SELECT * FROM fleet_task_artifacts WHERE artifact_id = ?",
                    (record_id,),
                ).fetchone()
                db.commit()
                return _row_to_artifact(row)

        return self._run_with_lock_retry(_record)

    def list_artifacts(self, task_id: str, *, limit: int = 100) -> list[FleetTaskArtifact]:
        self.init_db()
        if limit <= 0:
            return []
        with self._connect(row_factory=sqlite3.Row) as db:
            rows = db.execute(
                "SELECT * FROM fleet_task_artifacts WHERE task_id = ?"
                " ORDER BY created_at ASC, artifact_id ASC LIMIT ?",
                (task_id, int(limit)),
            ).fetchall()
        return [_row_to_artifact(row) for row in rows]

    @staticmethod
    def _insert_event_db(
        db: sqlite3.Connection,
        *,
        task_id: str,
        event_type: FleetTaskEventType,
        node_id: str | None = None,
        worker_id: str | None = None,
        status: FleetTaskStatus | None = None,
        message: str = "",
        payload: dict[str, Any] | None = None,
        severity: str = "info",
        correlation_id: str = "",
        trace_id: str = "",
        event_id: str | None = None,
        created_at: datetime | None = None,
    ) -> str:
        record_id = event_id or _new_id("fevent")
        db.execute(
            "INSERT INTO fleet_task_events"
            " (event_id, task_id, node_id, worker_id, event_type, status, message,"
            " payload_json, severity, correlation_id, trace_id, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                record_id,
                task_id,
                node_id,
                worker_id,
                event_type.value,
                status.value if status is not None else None,
                message,
                _json_dump(dict(payload or {})),
                severity,
                correlation_id,
                trace_id,
                (created_at or _utc_now()).isoformat(),
            ),
        )
        return record_id
