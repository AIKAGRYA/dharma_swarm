"""Bounded joined snapshots of Mission Control's two SQLite owners."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

from dharma_swarm.mission_control_a2a_io import _existing_db, _regular_state
from dharma_swarm.mission_control_contract import MissionControlError

_MAX_RUNTIME_DATABASE_BYTES = 1024 * 1024 * 1024
_MAX_TASKBOARD_DATABASE_BYTES = 256 * 1024 * 1024
_MAX_OWNER_WAL_BYTES = 256 * 1024 * 1024
_COPY_CHUNK_BYTES = 1024 * 1024

_FileState = tuple[int, int, int, int, int]
_SourceRole = tuple[str, Path, Path, int, bool]


def one_owner_row(
    connection: sqlite3.Connection,
    query: str,
    parameters: tuple[Any, ...],
    label: str,
) -> sqlite3.Row:
    rows = connection.execute(query, parameters).fetchall()
    if len(rows) != 1:
        raise MissionControlError(f"{label} is not unique in the owner snapshot")
    return rows[0]


def owner_text(row: sqlite3.Row, name: str) -> str:
    value = row[name]
    if type(value) is not str:
        raise MissionControlError(f"owner field {name} is not SQLite TEXT")
    return value


def owner_object(raw: object, label: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, child in items:
            if key in value:
                raise ValueError("duplicate key")
            value[key] = child
        return value

    def reject_constant(constant: str) -> None:
        raise ValueError(f"non-finite constant {constant}")

    try:
        if type(raw) is not str or len(raw) > 1024 * 1024:
            raise ValueError("not bounded text")
        value = json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
        if type(value) is not dict:
            raise ValueError("not object")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MissionControlError(f"{label} metadata is malformed") from exc
    return value


def owner_time(row: sqlite3.Row, name: str) -> datetime:
    try:
        value = datetime.fromisoformat(owner_text(row, name))
    except ValueError as exc:
        raise MissionControlError(f"owner timestamp {name} is malformed") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise MissionControlError(f"owner timestamp {name} is not timezone-aware")
    return value


def _require_table(
    connection: sqlite3.Connection,
    schema: str,
    table: str,
    required: frozenset[str],
) -> None:
    catalog = f"{schema}.sqlite_schema"
    rows = connection.execute(
        f"SELECT type FROM {catalog} WHERE name = ? LIMIT 2",
        (table,),
    ).fetchall()
    columns = connection.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    names = {str(row["name"]) for row in columns if type(row["name"]) is str}
    if (
        len(rows) != 1
        or owner_text(rows[0], "type") != "table"
        or not required <= names
    ):
        raise MissionControlError(f"owner table {schema}.{table} has the wrong schema")


def require_owner_schema(connection: sqlite3.Connection) -> None:
    tables = (
        (
            "main",
            "sessions",
            frozenset({"session_id", "operator_id", "status", "metadata_json"}),
        ),
        (
            "main",
            "task_claims",
            frozenset(
                {
                    "claim_id",
                    "task_id",
                    "session_id",
                    "agent_id",
                    "status",
                    "claimed_at",
                    "acked_at",
                    "heartbeat_at",
                    "stale_after",
                    "recovered_at",
                    "metadata_json",
                }
            ),
        ),
        (
            "main",
            "delegation_runs",
            frozenset(
                {
                    "run_id",
                    "session_id",
                    "task_id",
                    "claim_id",
                    "assigned_by",
                    "assigned_to",
                    "status",
                    "completed_at",
                    "failure_code",
                    "metadata_json",
                }
            ),
        ),
        (
            "main",
            "execution_identities",
            frozenset(
                {
                    "run_id",
                    "trace_id",
                    "correlation_id",
                    "task_id",
                    "claim_id",
                    "idempotency_key",
                    "causation_id",
                    "parent_run_id",
                    "agent_id",
                    "session_id",
                    "external_a2a_task_id",
                    "message_id",
                    "event_id",
                    "artifact_id",
                    "proposal_id",
                    "source",
                    "metadata_json",
                }
            ),
        ),
        (
            "main",
            "runtime_receipts",
            frozenset(
                {
                    "receipt_id",
                    "receipt_type",
                    "run_id",
                    "side_effect_key",
                    "correlation_id",
                    "payload_json",
                    "created_at",
                }
            ),
        ),
        (
            "main",
            "idempotency_records",
            frozenset({"idempotency_key", "side_effect_key", "run_id", "status"}),
        ),
        (
            "taskboard",
            "tasks",
            frozenset({"id", "status", "assigned_to", "metadata"}),
        ),
    )
    for schema, table, required in tables:
        _require_table(connection, schema, table, required)


def _file_state(info: os.stat_result) -> _FileState:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _copy_snapshot_file(
    source: Path,
    destination: Path,
    *,
    label: str,
    limit: int,
    expected: _FileState,
) -> None:
    """Stream one no-follow regular file while preserving its stat witness."""

    if expected[2] > limit:
        raise MissionControlError(f"{label} exceeds its snapshot bound")
    read_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    write_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    source_fd = destination_fd = -1
    try:
        source_fd = os.open(source, read_flags)
        opened = os.fstat(source_fd)
        if not stat.S_ISREG(opened.st_mode) or _file_state(opened) != expected:
            raise MissionControlError(f"{label} changed before snapshot copy")
        destination_fd = os.open(destination, write_flags, 0o600)
        copied = 0
        while True:
            chunk = os.read(source_fd, _COPY_CHUNK_BYTES)
            if not chunk:
                break
            copied += len(chunk)
            if copied > limit:
                raise MissionControlError(f"{label} exceeds its snapshot bound")
            view = memoryview(chunk)
            while view:
                written = os.write(destination_fd, view)
                if written <= 0:
                    raise OSError("snapshot write made no progress")
                view = view[written:]
        if copied != expected[2] or _file_state(os.fstat(source_fd)) != expected:
            raise MissionControlError(f"{label} changed during snapshot copy")
    except MissionControlError:
        raise
    except OSError as exc:
        raise MissionControlError(f"{label} snapshot copy failed") from exc
    finally:
        if destination_fd >= 0:
            os.close(destination_fd)
        if source_fd >= 0:
            os.close(source_fd)


def _source_roles(
    runtime_database: Path,
    task_database: Path,
    runtime_destination: Path,
    task_destination: Path,
) -> tuple[_SourceRole, ...]:
    return (
        (
            "RuntimeState database",
            runtime_database,
            runtime_destination,
            _MAX_RUNTIME_DATABASE_BYTES,
            True,
        ),
        (
            "RuntimeState WAL",
            Path(f"{runtime_database}-wal"),
            Path(f"{runtime_destination}-wal"),
            _MAX_OWNER_WAL_BYTES,
            False,
        ),
        (
            "TaskBoard database",
            task_database,
            task_destination,
            _MAX_TASKBOARD_DATABASE_BYTES,
            True,
        ),
        (
            "TaskBoard WAL",
            Path(f"{task_database}-wal"),
            Path(f"{task_destination}-wal"),
            _MAX_OWNER_WAL_BYTES,
            False,
        ),
    )


def _snapshot_owner_pair(
    runtime_database: Path,
    task_database: Path,
    runtime_destination: Path,
    task_destination: Path,
) -> None:
    """Copy both DB/WAL pairs under one positional stability bracket."""

    roles = _source_roles(
        runtime_database,
        task_database,
        runtime_destination,
        task_destination,
    )
    before = tuple(_regular_state(source, label) for label, source, _, _, _ in roles)
    if any(state is None for state, role in zip(before, roles, strict=True) if role[4]):
        raise MissionControlError("Mission Control owner database disappeared")
    present = [
        (role[1], state)
        for role, state in zip(roles, before, strict=True)
        if state is not None
    ]
    if len({str(path) for path, _ in present}) != len(present):
        raise MissionControlError("Mission Control owner source roles overlap")
    if len({state[:2] for _, state in present}) != len(present):
        raise MissionControlError("Mission Control owner source inodes overlap")
    for role, expected in zip(roles, before, strict=True):
        label, source, destination, limit, _ = role
        if expected is not None:
            _copy_snapshot_file(
                source,
                destination,
                label=label,
                limit=limit,
                expected=expected,
            )
    after = tuple(_regular_state(source, label) for label, source, _, _, _ in roles)
    if after != before:
        raise MissionControlError(
            "Mission Control owner databases changed during joined snapshot"
        )


@contextmanager
def read_only_owner_snapshot(
    runtime_path: Path,
    task_path: Path,
) -> Iterator[sqlite3.Connection]:
    """Yield a stable joined observation, never a cross-store atomicity claim."""

    runtime_database = _existing_db(runtime_path, "RuntimeState")
    task_database = _existing_db(task_path, "TaskBoard")
    connection: sqlite3.Connection | None = None
    with tempfile.TemporaryDirectory(prefix="dharma-mc-owner-ro-") as raw:
        root = Path(raw)
        runtime_snapshot = root / "runtime.snapshot"
        task_snapshot = root / "taskboard.snapshot"
        _snapshot_owner_pair(
            runtime_database,
            task_database,
            runtime_snapshot,
            task_snapshot,
        )
        runtime_uri = f"file:{quote(str(runtime_snapshot))}?mode=rw"
        task_uri = f"file:{quote(str(task_snapshot))}?mode=rw"
        try:
            connection = sqlite3.connect(runtime_uri, uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("ATTACH DATABASE ? AS taskboard", (task_uri,))
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            yield connection
        except sqlite3.Error as exc:
            raise MissionControlError(
                "Mission Control owner snapshot is unavailable or malformed"
            ) from exc
        finally:
            if connection is not None:
                connection.close()


__all__ = [
    "one_owner_row",
    "owner_object",
    "owner_text",
    "owner_time",
    "read_only_owner_snapshot",
    "require_owner_schema",
]
