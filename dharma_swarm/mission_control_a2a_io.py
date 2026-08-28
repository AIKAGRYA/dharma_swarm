"""Bounded, read-only file and SQLite access for Mission Control A2A."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

from dharma_swarm.mission_control_contract import (
    SCHEMA_VERSION as MISSION_CONTROL_SCHEMA,
    MissionControlError,
    session_id as mission_session_id,
)
from dharma_swarm.models import Task, TaskPriority, TaskStatus

_MAX_DATABASE_BYTES = 1024 * 1024 * 1024
_MAX_WAL_BYTES = 256 * 1024 * 1024
_MAX_SHM_BYTES = 16 * 1024 * 1024
_MAX_SNAPSHOT_DATABASE_BYTES = 128 * 1024 * 1024
_MAX_SNAPSHOT_WAL_BYTES = 64 * 1024 * 1024
_SQLITE_LOCK_TIMEOUT_SECONDS = 0.25
_SQLITE_READ_DEADLINE_SECONDS = 5.0
_SQLITE_VM_OP_BUDGET = 5_000_000
_SQLITE_PROGRESS_INTERVAL = 1_000
_SQLITE_MAX_RESULT_ROWS = 30_003
_SQLITE_MAX_RESULT_BYTES = 32 * 1024 * 1024
_SQLITE_MAX_VALUE_BYTES = 16 * 1024 * 1024
_SQLITE_MAX_SQL_BYTES = 64 * 1024
_SQLITE_MAX_PARAMETERS = 256
_SQLITE_MAX_RESULT_COLUMNS = 256
_SQLITE_MAX_QUERIES = 32
_SQLITE_DENIED_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_ANALYZE,
        sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_CREATE_INDEX,
        sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_INDEX,
        sqlite3.SQLITE_CREATE_TEMP_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
        sqlite3.SQLITE_CREATE_TEMP_VIEW,
        sqlite3.SQLITE_CREATE_TRIGGER,
        sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_CREATE_VTABLE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_DETACH,
        sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_INDEX,
        sqlite3.SQLITE_DROP_TEMP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_TRIGGER,
        sqlite3.SQLITE_DROP_TEMP_VIEW,
        sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_DROP_VTABLE,
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_PRAGMA,
        sqlite3.SQLITE_REINDEX,
        sqlite3.SQLITE_SAVEPOINT,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_UPDATE,
    }
)


def _file_state(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


class _IncompleteEvidence(Exception):
    """Absent/partial evidence proves no execution but is not corruption."""


@dataclass(frozen=True, slots=True)
class ReadQuery:
    """Immutable SQL-plus-parameters data submitted before SQLite is opened."""

    sql: str
    parameters: tuple[Any, ...] = ()


def resolved_root(root: Path) -> Path:
    candidate = root.expanduser()
    try:
        info = candidate.lstat()
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise MissionControlError("trusted evidence root is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise MissionControlError("trusted evidence root is not a regular directory")
    return resolved


def safe_file(root: Path, *parts: str) -> Path:
    trusted = resolved_root(root)
    candidate = trusted.joinpath(*parts)
    try:
        info = candidate.lstat()
    except OSError as exc:
        raise MissionControlError(
            f"trusted evidence file is unavailable: {candidate.name}",
        ) from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise MissionControlError(
            f"trusted evidence file is not a regular file: {candidate.name}",
        )
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(trusted):
        raise MissionControlError("trusted evidence path escaped its injected root")
    return resolved


def read_bytes(path: Path, *, limit: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise MissionControlError(
            f"could not open trusted evidence: {path.name}",
        ) from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise MissionControlError(
                f"trusted evidence exceeds its read bound: {path.name}",
            )
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining > 0:
            chunk = os.read(fd, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
        if _file_state(after) != _file_state(info):
            raise MissionControlError(
                f"trusted evidence changed while read: {path.name}",
            )
        data = b"".join(chunks)
    finally:
        os.close(fd)
    if len(data) > limit:
        raise MissionControlError(
            f"trusted evidence exceeds its read bound: {path.name}",
        )
    return data


def read_json(path: Path, *, limit: int) -> tuple[dict[str, Any], bytes]:
    raw = read_bytes(path, limit=limit)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MissionControlError(
            f"malformed trusted JSON evidence: {path.name}",
        ) from exc
    if not isinstance(value, dict):
        raise MissionControlError(
            f"trusted JSON evidence must be an object: {path.name}",
        )
    return value, raw


def _optional_file(root: Path, *parts: str) -> Path | None:
    if not resolved_root(root).joinpath(*parts).exists():
        return None
    return safe_file(root, *parts)


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _exact_path(value: object, expected: Path, label: str) -> None:
    raw = str(value or "")
    if not raw:
        raise _IncompleteEvidence(label)
    declared = Path(raw)
    if not declared.is_absolute() or _absolute_lexical(declared) != expected:
        raise MissionControlError(
            f"{label} does not match its trusted canonical path",
        )


def _trusted_link(value: object, roots: tuple[Path, ...], label: str) -> Path:
    raw = str(value or "")
    if not raw:
        raise _IncompleteEvidence(label)
    declared = Path(raw)
    if not declared.is_absolute():
        raise MissionControlError(f"{label} must be an absolute trusted path")
    lexical = _absolute_lexical(declared)
    for configured in roots:
        trusted = resolved_root(configured)
        if lexical.is_relative_to(trusted):
            if not lexical.exists():
                raise _IncompleteEvidence(label)
            return safe_file(trusted, *lexical.relative_to(trusted).parts)
    if not roots:
        raise _IncompleteEvidence(label)
    raise MissionControlError(
        f"{label} is outside every injected trusted receipt root",
    )


def _field(
    mapping: Mapping[str, Any],
    key: str,
    expected: Any,
    label: str,
) -> None:
    if key not in mapping:
        raise _IncompleteEvidence(f"{label}.{key}")
    actual = mapping[key]
    if type(actual) is not type(expected) or actual != expected:
        raise MissionControlError(
            f"{label}.{key} contradicts native A2A identity",
        )


def _present(mapping: Mapping[str, Any], key: str, label: str) -> Any:
    if key not in mapping or mapping[key] in (None, ""):
        raise _IncompleteEvidence(f"{label}.{key}")
    return mapping[key]


def _exact_json_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _exact_json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _exact_json_equal(first, second)
            for first, second in zip(left, right, strict=True)
        )
    return bool(left == right)


def _successful_send_statuses(agent_uid: str) -> frozenset[str]:
    label = (
        "".join(char.upper() if char.isalnum() else "_" for char in agent_uid).strip(
            "_"
        )
        or "AGENT"
    )
    return frozenset(
        {
            "PUBLISH_ACKED",
            "PUBLISH_DEDUPED",
            f"{label}_CONSUMED",
            f"{label}_REPLIED",
        }
    )


def _existing_db(path: Path, label: str) -> Path:
    candidate = path.expanduser()
    try:
        info = candidate.lstat()
    except OSError as exc:
        raise MissionControlError(f"{label} database is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise MissionControlError(f"{label} database is not a regular file")
    return candidate.resolve(strict=True)


def _regular_state(path: Path, label: str) -> tuple[int, int, int, int, int] | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise MissionControlError(f"{label} database snapshot is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise MissionControlError(f"{label} database snapshot is not regular")
    return _file_state(info)


def _bounded_regular_state(
    path: Path,
    label: str,
    *,
    max_bytes: int,
) -> tuple[int, int, int, int, int] | None:
    state = _regular_state(path, label)
    if state is not None and state[2] > max_bytes:
        raise MissionControlError(f"{label} database exceeds its read bound")
    return state


def _sqlite_value_bytes(value: object) -> int:
    if value is None:
        return 1
    if type(value) in (int, float):
        return 8
    if type(value) is str:
        try:
            return len(value.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise MissionControlError(
                "SQLite returned text that is not valid UTF-8",
            ) from exc
    if type(value) is bytes:
        return len(value)
    raise MissionControlError("SQLite returned an unsupported value type")


def _query_plan_is_valid(queries: object) -> bool:
    if type(queries) is not tuple or not queries or len(queries) > _SQLITE_MAX_QUERIES:
        return False
    parameter_bytes = 0
    for query in queries:
        if (
            type(query) is not ReadQuery
            or type(query.sql) is not str
            or not query.sql.strip()
            or len(query.sql) > _SQLITE_MAX_SQL_BYTES
            or type(query.parameters) is not tuple
            or len(query.parameters) > _SQLITE_MAX_PARAMETERS
        ):
            return False
        try:
            if len(query.sql.encode("utf-8")) > _SQLITE_MAX_SQL_BYTES:
                return False
        except UnicodeEncodeError:
            return False
        for value in query.parameters:
            if type(value) not in (bytes, float, int, str, type(None)):
                return False
            if type(value) is int and not -(2**63) <= value < 2**63:
                return False
            if type(value) is str and len(value) > _SQLITE_MAX_VALUE_BYTES:
                return False
            try:
                value_bytes = _sqlite_value_bytes(value)
            except MissionControlError:
                return False
            if value_bytes > _SQLITE_MAX_VALUE_BYTES:
                return False
            parameter_bytes += value_bytes
            if parameter_bytes > _SQLITE_MAX_RESULT_BYTES:
                return False
    return True


def _snapshot_database(database: Path, destination: Path, label: str) -> None:
    wal = Path(f"{database}-wal")
    database_before = _regular_state(database, label)
    wal_before = _regular_state(wal, label)
    if database_before is None:
        raise MissionControlError(f"{label} database disappeared before snapshot")
    database_bytes = read_bytes(database, limit=_MAX_SNAPSHOT_DATABASE_BYTES)
    wal_bytes = (
        read_bytes(wal, limit=_MAX_SNAPSHOT_WAL_BYTES)
        if wal_before is not None
        else None
    )
    if (
        _regular_state(database, label) != database_before
        or _regular_state(wal, label) != wal_before
    ):
        raise MissionControlError(f"{label} database changed during snapshot")
    destination.write_bytes(database_bytes)
    if wal_bytes is not None:
        Path(f"{destination}-wal").write_bytes(wal_bytes)


def _read_only_queries(
    path: Path,
    label: str,
    queries: tuple[ReadQuery, ...],
    *,
    max_database_bytes: int = _MAX_DATABASE_BYTES,
) -> tuple[tuple[sqlite3.Row, ...], ...]:
    """Run a closed query plan and return rows only after SQLite is closed."""

    if (
        type(max_database_bytes) is not int
        or max_database_bytes <= 0
        or max_database_bytes > _MAX_DATABASE_BYTES
    ):
        raise MissionControlError(f"{label} database read bound is invalid")
    if not _query_plan_is_valid(queries):
        raise MissionControlError(f"{label} query plan is invalid")

    database = _existing_db(path, label)
    wal = Path(f"{database}-wal")
    shm = Path(f"{database}-shm")
    journal = Path(f"{database}-journal")
    database_before = _bounded_regular_state(
        database,
        label,
        max_bytes=max_database_bytes,
    )
    wal_before = _bounded_regular_state(wal, label, max_bytes=_MAX_WAL_BYTES)
    shm_before = _bounded_regular_state(shm, label, max_bytes=_MAX_SHM_BYTES)
    if _regular_state(journal, label) is not None:
        raise MissionControlError(f"{label} rollback journal is not admissible")
    if database_before is None:
        raise MissionControlError(f"{label} database disappeared before read")
    if wal_before is None and shm_before is not None:
        raise MissionControlError(f"{label} database has an orphaned SHM sidecar")

    immutable = wal_before is None and shm_before is None
    query_string = "mode=ro&cache=private"
    if immutable:
        query_string += "&immutable=1"
    uri = f"file:{quote(str(database))}?{query_string}"
    connection: sqlite3.Connection | None = None
    deadline = time.monotonic() + _SQLITE_READ_DEADLINE_SECONDS
    vm_ops = 0
    interrupted = False
    denied = False
    returned_rows = 0
    returned_bytes = 0
    results: list[tuple[sqlite3.Row, ...]] = []

    def _progress() -> int:
        nonlocal interrupted, vm_ops
        vm_ops += _SQLITE_PROGRESS_INTERVAL
        interrupted = (
            vm_ops > _SQLITE_VM_OP_BUDGET or time.monotonic() > deadline
        )
        return int(interrupted)

    def _authorize(
        action: int,
        _arg1: str | None,
        _arg2: str | None,
        _database_name: str | None,
        _trigger_name: str | None,
    ) -> int:
        nonlocal denied
        if action in _SQLITE_DENIED_ACTIONS:
            denied = True
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    try:
        connection = sqlite3.connect(
            uri,
            uri=True,
            timeout=_SQLITE_LOCK_TIMEOUT_SECONDS,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, _SQLITE_MAX_VALUE_BYTES)
        connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, _SQLITE_MAX_SQL_BYTES)
        connection.setlimit(
            sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER,
            _SQLITE_MAX_PARAMETERS,
        )
        connection.setlimit(
            sqlite3.SQLITE_LIMIT_COLUMN,
            _SQLITE_MAX_RESULT_COLUMNS,
        )
        connection.set_progress_handler(_progress, _SQLITE_PROGRESS_INTERVAL)
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise MissionControlError(f"{label} query-only mode was not established")
        if connection.execute("PRAGMA trusted_schema").fetchone()[0] != 0:
            raise MissionControlError(f"{label} trusted schema remained enabled")
        connection.execute("BEGIN")
        connection.execute("SELECT 1 FROM sqlite_schema LIMIT 1").fetchone()
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        if page_count * page_size > max_database_bytes:
            raise MissionControlError(f"{label} database exceeds its logical bound")
        if time.monotonic() > deadline:
            raise MissionControlError(f"{label} database read deadline expired")
        changes_before = connection.total_changes
        connection.set_authorizer(_authorize)

        for query in queries:
            cursor = connection.execute(query.sql, query.parameters)
            query_rows: list[sqlite3.Row] = []
            try:
                while (row := cursor.fetchone()) is not None:
                    row_bytes = 64 + 8 * len(row) + sum(
                        _sqlite_value_bytes(value) for value in row
                    )
                    if (
                        returned_rows + 1 > _SQLITE_MAX_RESULT_ROWS
                        or returned_bytes + row_bytes > _SQLITE_MAX_RESULT_BYTES
                    ):
                        raise MissionControlError(
                            f"{label} query plan exceeded its result bound",
                        )
                    if time.monotonic() > deadline:
                        interrupted = True
                        raise MissionControlError(
                            f"{label} database read deadline expired",
                        )
                    returned_rows += 1
                    returned_bytes += row_bytes
                    query_rows.append(row)
            finally:
                cursor.close()
            results.append(tuple(query_rows))

        if interrupted:
            raise MissionControlError(f"{label} database read budget was exceeded")
        if denied:
            raise MissionControlError(f"{label} attempted a forbidden SQLite action")
        if time.monotonic() > deadline:
            raise MissionControlError(f"{label} database read deadline expired")
        if not connection.in_transaction or connection.total_changes != changes_before:
            raise MissionControlError(f"{label} escaped its read-only transaction")

        database_after = _bounded_regular_state(
            database,
            label,
            max_bytes=max_database_bytes,
        )
        wal_after = _bounded_regular_state(wal, label, max_bytes=_MAX_WAL_BYTES)
        shm_after = _bounded_regular_state(shm, label, max_bytes=_MAX_SHM_BYTES)
        if _regular_state(journal, label) is not None:
            raise MissionControlError(f"{label} rollback journal appeared during read")
        if immutable:
            if (
                database_after != database_before
                or wal_after is not None
                or shm_after is not None
            ):
                raise MissionControlError(
                    f"{label} clean database changed during immutable read",
                )
        elif (
            database_after is None
            or database_after[:2] != database_before[:2]
            or wal_after is None
            or wal_after[:2] != wal_before[:2]
            or (
                shm_before is not None
                and (
                    shm_after is None
                    or shm_after[:2] != shm_before[:2]
                )
            )
        ):
            raise MissionControlError(f"{label} database identity changed during read")
    except (sqlite3.Error, MemoryError) as exc:
        if denied:
            reason = "attempted a forbidden SQLite action"
        elif interrupted:
            reason = "database read budget was exceeded"
        else:
            reason = "database is unavailable or malformed"
        raise MissionControlError(f"{label} {reason}") from exc
    finally:
        if connection is not None:
            connection.set_authorizer(None)
            connection.set_progress_handler(None, 0)
            if connection.in_transaction:
                connection.rollback()
            connection.close()
    return tuple(results)


def read_task(database: Path, task_id: str) -> Task | None:
    rows, dependencies = _read_only_queries(
        database,
        "TaskBoard",
        (
            ReadQuery(
                "SELECT id, title, description, status, priority, assigned_to, "
                "created_by, created_at, updated_at, result, metadata "
                "FROM tasks WHERE id = ? LIMIT 2",
                (task_id,),
            ),
            ReadQuery(
                "SELECT depends_on_id FROM task_dependencies "
                "WHERE task_id = ? ORDER BY depends_on_id",
                (task_id,),
            ),
        ),
    )
    if not rows:
        return None
    if len(rows) != 1:
        raise MissionControlError("TaskBoard contains duplicate task identity")
    row = rows[0]
    try:
        metadata = json.loads(str(row["metadata"] or "{}"))
        if not isinstance(metadata, dict):
            raise TypeError("metadata is not an object")
        return Task(
            id=str(row["id"]),
            title=str(row["title"]),
            description=str(row["description"] or ""),
            status=TaskStatus(str(row["status"])),
            priority=TaskPriority(str(row["priority"])),
            assigned_to=row["assigned_to"],
            created_by=str(row["created_by"] or "system"),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            result=row["result"],
            metadata=metadata,
            depends_on=[str(item[0]) for item in dependencies],
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MissionControlError("TaskBoard task evidence is malformed") from exc


def require_mission(database: Path, mission_id: str) -> None:
    (rows,) = _read_only_queries(
        database,
        "RuntimeState",
        (
            ReadQuery(
                "SELECT status, metadata_json FROM sessions "
                "WHERE session_id = ? LIMIT 2",
                (mission_session_id(mission_id),),
            ),
        ),
    )
    if len(rows) != 1:
        raise MissionControlError(f"mission {mission_id!r} does not exist canonically")
    if type(rows[0]["status"]) is not str or rows[0]["status"] != "active":
        raise MissionControlError(f"mission {mission_id!r} is not active canonically")
    try:
        metadata = json.loads(str(rows[0]["metadata_json"] or "{}"))
    except json.JSONDecodeError as exc:
        raise MissionControlError("canonical mission metadata is malformed") from exc
    if (
        not isinstance(metadata, dict)
        or metadata.get("mission_id") != mission_id
        or metadata.get("schema_version") != MISSION_CONTROL_SCHEMA
    ):
        raise MissionControlError(f"mission {mission_id!r} does not exist canonically")


def read_semantic_job(path: Path, event_id: str, *, max_bytes: int) -> dict[str, Any]:
    if type(max_bytes) is not int or max_bytes <= 0:
        raise MissionControlError("semantic job read bound is invalid")
    rows, payload_rows = _read_only_queries(
        path,
        "semantic job",
        (
            ReadQuery(
                "SELECT event_id, envelope_sha256, status, "
                "typeof(envelope_json) AS envelope_type, "
                "length(CAST(envelope_json AS BLOB)) AS envelope_bytes "
                "FROM semantic_jobs WHERE event_id = ? LIMIT 2",
                (event_id,),
            ),
            ReadQuery(
                "SELECT envelope_json FROM semantic_jobs WHERE event_id = ? "
                "AND typeof(envelope_json) = 'text' "
                "AND length(CAST(envelope_json AS BLOB)) <= ? LIMIT 2",
                (event_id, max_bytes),
            ),
        ),
        max_database_bytes=max_bytes * 16,
    )
    if len(rows) != 1:
        raise MissionControlError(
            "expected exactly one semantic job for the A2A packet"
        )
    if (
        rows[0]["envelope_type"] != "text"
        or type(rows[0]["envelope_bytes"]) is not int
        or rows[0]["envelope_bytes"] > max_bytes
    ):
        raise MissionControlError("semantic job envelope exceeds its read bound")
    if len(payload_rows) != 1 or type(payload_rows[0]["envelope_json"]) is not str:
        raise MissionControlError("semantic job envelope is malformed")
    envelope_json = payload_rows[0]["envelope_json"]
    if len(envelope_json.encode("utf-8")) > max_bytes:
        raise MissionControlError("semantic job envelope exceeds its read bound")
    try:
        envelope = json.loads(envelope_json)
    except json.JSONDecodeError as exc:
        raise MissionControlError("semantic job envelope is malformed") from exc
    if not isinstance(envelope, dict):
        raise MissionControlError("semantic job envelope must be an object")
    return {
        "event_id": str(rows[0]["event_id"]),
        "envelope_sha256": str(rows[0]["envelope_sha256"]),
        "envelope": envelope,
        "status": str(rows[0]["status"]),
    }


__all__ = ["read_bytes", "read_json", "resolved_root", "safe_file"]
