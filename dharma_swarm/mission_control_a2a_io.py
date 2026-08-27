"""Bounded, read-only file and SQLite access for Mission Control A2A."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import quote

from dharma_swarm.mission_control_contract import (
    SCHEMA_VERSION as MISSION_CONTROL_SCHEMA,
    MissionControlError,
    session_id as mission_session_id,
)
from dharma_swarm.models import Task, TaskPriority, TaskStatus

_MAX_DATABASE_BYTES = 128 * 1024 * 1024
_MAX_WAL_BYTES = 64 * 1024 * 1024


class _IncompleteEvidence(Exception):
    """Absent/partial evidence proves no execution but is not corruption."""


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
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
        ):
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
    mapping: Mapping[str, Any], key: str, expected: Any, label: str,
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
    label = "".join(
        char.upper() if char.isalnum() else "_" for char in agent_uid
    ).strip("_") or "AGENT"
    return frozenset({
        "PUBLISH_ACKED",
        "PUBLISH_DEDUPED",
        f"{label}_CONSUMED",
        f"{label}_REPLIED",
    })


def _existing_db(path: Path, label: str) -> Path:
    candidate = path.expanduser()
    try:
        info = candidate.lstat()
    except OSError as exc:
        raise MissionControlError(f"{label} database is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise MissionControlError(f"{label} database is not a regular file")
    return candidate.resolve(strict=True)


def _regular_state(path: Path, label: str) -> tuple[int, int, int, int] | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise MissionControlError(f"{label} database snapshot is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise MissionControlError(f"{label} database snapshot is not regular")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _snapshot_database(database: Path, destination: Path, label: str) -> None:
    wal = Path(f"{database}-wal")
    database_before = _regular_state(database, label)
    wal_before = _regular_state(wal, label)
    if database_before is None:
        raise MissionControlError(f"{label} database disappeared before snapshot")
    database_bytes = read_bytes(database, limit=_MAX_DATABASE_BYTES)
    wal_bytes = read_bytes(wal, limit=_MAX_WAL_BYTES) if wal_before is not None else None
    if (
        _regular_state(database, label) != database_before
        or _regular_state(wal, label) != wal_before
    ):
        raise MissionControlError(f"{label} database changed during snapshot")
    destination.write_bytes(database_bytes)
    if wal_bytes is not None:
        Path(f"{destination}-wal").write_bytes(wal_bytes)


@contextmanager
def _read_only_db(path: Path, label: str) -> Iterator[sqlite3.Connection]:
    database = _existing_db(path, label)
    connection: sqlite3.Connection | None = None
    with tempfile.TemporaryDirectory(prefix="dharma-mc-a2a-ro-") as raw:
        snapshot = Path(raw) / "evidence.sqlite3"
        _snapshot_database(database, snapshot, label)
        uri = f"file:{quote(str(snapshot))}?mode=rw"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            yield connection
        except sqlite3.Error as exc:
            raise MissionControlError(
                f"{label} database is unavailable or malformed",
            ) from exc
        finally:
            if connection is not None:
                connection.close()


def read_task(database: Path, task_id: str) -> Task | None:
    with _read_only_db(database, "TaskBoard") as connection:
        rows = connection.execute(
            "SELECT id, title, description, status, priority, assigned_to, "
            "created_by, created_at, updated_at, result, metadata "
            "FROM tasks WHERE id = ? LIMIT 2",
            (task_id,),
        ).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise MissionControlError("TaskBoard contains duplicate task identity")
        dependencies = connection.execute(
            "SELECT depends_on_id FROM task_dependencies "
            "WHERE task_id = ? ORDER BY depends_on_id",
            (task_id,),
        ).fetchall()
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
    with _read_only_db(database, "RuntimeState") as connection:
        rows = connection.execute(
            "SELECT metadata_json FROM sessions WHERE session_id = ? LIMIT 2",
            (mission_session_id(mission_id),),
        ).fetchall()
    if len(rows) != 1:
        raise MissionControlError(f"mission {mission_id!r} does not exist canonically")
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
    if path.stat().st_size > max_bytes * 16:
        raise MissionControlError("semantic job database exceeds its read bound")
    with _read_only_db(path, "semantic job") as connection:
        rows = connection.execute(
            "SELECT event_id, envelope_sha256, envelope_json, status, "
            "length(envelope_json) AS envelope_length FROM semantic_jobs "
            "WHERE event_id = ? LIMIT 2",
            (event_id,),
        ).fetchall()
    if len(rows) != 1:
        raise MissionControlError("expected exactly one semantic job for the A2A packet")
    if int(rows[0]["envelope_length"] or 0) > max_bytes:
        raise MissionControlError("semantic job envelope exceeds its read bound")
    try:
        envelope = json.loads(str(rows[0]["envelope_json"]))
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
