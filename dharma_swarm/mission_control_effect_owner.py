"""Pinned owner-file custody and joined SQLite writer transaction."""

from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.mission_control_a2a_owner_snapshot import require_owner_schema
from dharma_swarm.mission_control_effect_records import OwnerStoreBinding
from dharma_swarm.runtime_state_effect_fence import require_effect_fence_schema


def _ancestry(path: Path) -> str:
    rows: list[dict[str, object]] = []
    current = path.parent
    secure_anchor = False
    while True:
        info = current.stat(follow_symlinks=False)
        mode = stat.S_IMODE(info.st_mode)
        sticky_root = bool(mode & stat.S_ISVTX) and info.st_uid == 0
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid not in {0, os.getuid()}
            or (mode & 0o022 and not (secure_anchor and sticky_root))
        ):
            raise ValueError("owner database ancestry is writable by another principal")
        if info.st_uid == os.getuid() and not mode & 0o022:
            secure_anchor = True
        rows.append({
            "path": str(current), "device": info.st_dev, "inode": info.st_ino,
            "mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid,
            "gid": info.st_gid,
        })
        if current == current.parent:
            break
        current = current.parent
    return canonical_sha256(rows)


def _sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(f"{path}{suffix}")
        try:
            lexical = sidecar.lstat()
        except FileNotFoundError:
            continue
        if (
            stat.S_ISLNK(lexical.st_mode) or not stat.S_ISREG(lexical.st_mode)
            or lexical.st_uid != os.getuid() or lexical.st_nlink != 1
            or stat.S_IMODE(lexical.st_mode) & 0o022
        ):
            raise ValueError("owner database sidecar custody is unsafe")


def _database(path: Path, label: str) -> tuple[Path, os.stat_result, str]:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError(f"{label} database path is not absolute")
    lexical = candidate.lstat()
    resolved = candidate.resolve(strict=True)
    info = resolved.stat(follow_symlinks=False)
    if (
        stat.S_ISLNK(lexical.st_mode) or not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o022
    ):
        raise ValueError(f"{label} database custody is unsafe")
    return resolved, info, _ancestry(resolved)


def inspect_owner_stores(
    runtime_database: Path, task_database: Path,
) -> OwnerStoreBinding:
    """Observe pinned owner files; this value alone grants no authority."""

    runtime, run, run_ancestry = _database(runtime_database, "RuntimeState")
    task, board, board_ancestry = _database(task_database, "TaskBoard")
    _sidecars(runtime)
    _sidecars(task)
    if runtime == task or (run.st_dev, run.st_ino) == (board.st_dev, board.st_ino):
        raise ValueError("RuntimeState and TaskBoard owners are aliased")
    if run.st_uid != board.st_uid or run.st_uid != os.getuid():
        raise ValueError("owner databases are outside the supervisor OS UID")
    return OwnerStoreBinding(
        str(runtime), run.st_dev, run.st_ino, stat.S_IMODE(run.st_mode),
        run.st_uid, run.st_gid, run.st_nlink, run_ancestry,
        str(task), board.st_dev, board.st_ino, stat.S_IMODE(board.st_mode),
        board.st_uid, board.st_gid, board.st_nlink, board_ancestry,
    )


@contextmanager
def owner_transaction(owner: OwnerStoreBinding) -> Iterator[sqlite3.Connection]:
    current = inspect_owner_stores(
        Path(owner.runtime_database_path), Path(owner.task_database_path)
    )
    if current != owner:
        raise ValueError("owner database identity drifted")
    runtime_uri = f"file:{quote(owner.runtime_database_path)}?mode=rw"
    task_uri = f"file:{quote(owner.task_database_path)}?mode=rw"
    connection = sqlite3.connect(
        runtime_uri, uri=True, isolation_level=None, timeout=10,
    )
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("ATTACH DATABASE ? AS taskboard", (task_uri,))
        connection.execute("PRAGMA main.synchronous=FULL")
        synchronous = connection.execute("PRAGMA main.synchronous").fetchone()
        if synchronous is None or synchronous[0] != 2:
            raise ValueError("RuntimeState durability policy is not FULL")
        connection.execute("BEGIN IMMEDIATE")
        listed = {
            str(row[1]): str(Path(str(row[2])).resolve(strict=True))
            for row in connection.execute("PRAGMA database_list").fetchall()
        }
        if listed != {
            "main": owner.runtime_database_path,
            "taskboard": owner.task_database_path,
        } or inspect_owner_stores(
            Path(owner.runtime_database_path), Path(owner.task_database_path)
        ) != owner:
            raise ValueError("attached owner databases disagree with supervisor binding")
        require_owner_schema(connection)
        require_effect_fence_schema(connection)
        yield connection
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


__all__ = ["inspect_owner_stores", "owner_transaction"]
