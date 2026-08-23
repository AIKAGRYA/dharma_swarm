"""Filesystem custody primitives for the deterministic campaign oracle."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from pathlib import Path
from typing import Any

from dharma_swarm.mission_control_contract import MissionControlError


MAX_ORACLE_FILE_BYTES = 1_048_576


class HeldOutOracleError(MissionControlError):
    """Held-out manifest, evidence, evaluator, or replay is invalid."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise HeldOutOracleError(message)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as exc:
        raise HeldOutOracleError("held-out oracle JSON is not canonicalizable") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _need(key not in result, f"held-out oracle duplicates key {key!r}")
        result[key] = value
    return result


def _file_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_uid,
        value.st_gid,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _directory_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    _need(nofollow is not None and directory is not None,
          "held-out oracle custody requires O_NOFOLLOW and O_DIRECTORY")
    return os.O_RDONLY | nofollow | directory


def _open_parent(path: Path) -> tuple[int, str]:
    _need(path.is_absolute() and path.name not in {"", ".", ".."},
          "held-out oracle path must be an absolute leaf")
    flags = _directory_flags()
    descriptor = os.open(os.path.sep, flags)
    try:
        for component in path.parent.parts[1:]:
            _need(component not in {"", ".", ".."},
                  "held-out oracle path component is invalid")
            child = os.open(component, flags, dir_fd=descriptor)
            info = os.fstat(child)
            _need(stat.S_ISDIR(info.st_mode),
                  "held-out oracle ancestor is not a directory")
            os.close(descriptor)
            descriptor = child
        return descriptor, path.name
    except BaseException:
        os.close(descriptor)
        raise


def read_exact(
    path: Path,
    *,
    label: str,
    canonical_json: bool,
) -> tuple[bytes, Any]:
    parent, name = _open_parent(path)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    assert nofollow is not None
    try:
        descriptor = os.open(name, os.O_RDONLY | nofollow, dir_fd=parent)
    except OSError as exc:
        os.close(parent)
        raise HeldOutOracleError(f"{label} could not be opened exactly") from exc
    try:
        before = os.fstat(descriptor)
        _need(stat.S_ISREG(before.st_mode), f"{label} must be a regular file")
        _need(before.st_nlink == 1, f"{label} must have one filesystem link")
        _need(stat.S_IMODE(before.st_mode) == 0o600, f"{label} mode must be 0600")
        _need(before.st_uid == os.geteuid(), f"{label} owner is foreign")
        _need(0 < before.st_size <= MAX_ORACLE_FILE_BYTES, f"{label} size is invalid")
        chunks: list[bytes] = []
        remaining = MAX_ORACLE_FILE_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
        os.close(parent)
    _need(_file_identity(before) == _file_identity(after), f"{label} changed while read")
    _need(len(raw) == before.st_size, f"{label} read was incomplete")
    if not canonical_json:
        return raw, None
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HeldOutOracleError(f"{label} is not strict UTF-8 JSON") from exc
    _need(raw == _canonical_bytes(value), f"{label} bytes are not canonical")
    return raw, value


def private_directory(path: Path, label: str) -> Path:
    _need(path.is_absolute(), f"{label} must be absolute")
    parent, name = _open_parent(path)
    try:
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
        except FileExistsError:
            pass
        descriptor = os.open(name, _directory_flags(), dir_fd=parent)
        try:
            info = os.fstat(descriptor)
            _need(
                stat.S_ISDIR(info.st_mode)
                and info.st_uid == os.geteuid()
                and stat.S_IMODE(info.st_mode) == 0o700,
                f"{label} custody is invalid",
            )
        finally:
            os.close(descriptor)
    finally:
        os.close(parent)
    return path


def list_private_directory(path: Path, label: str) -> tuple[str, ...]:
    parent, name = _open_parent(path)
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent)
        try:
            info = os.fstat(descriptor)
            _need(
                info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700,
                f"{label} custody is invalid",
            )
            return tuple(sorted(os.listdir(descriptor)))
        finally:
            os.close(descriptor)
    finally:
        os.close(parent)


def write_exact(
    path: Path,
    payload: bytes,
    *,
    canonical_json_on_replay: bool = True,
) -> None:
    parent, name = _open_parent(path)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    assert nofollow is not None
    try:
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
                0o600,
                dir_fd=parent,
            )
        except FileExistsError:
            raw, _ = read_exact(
                path,
                label="held-out oracle input",
                canonical_json=canonical_json_on_replay,
            )
            _need(raw == payload, "held-out oracle input replay conflicts")
            return
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                _need(written > 0, "held-out oracle input write failed")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(parent)
    finally:
        os.close(parent)


class OracleRunLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._descriptor: int | None = None

    def __enter__(self) -> OracleRunLock:
        parent, name = _open_parent(self._path)
        nofollow = getattr(os, "O_NOFOLLOW", None)
        assert nofollow is not None
        try:
            descriptor = os.open(
                name,
                os.O_RDWR | os.O_CREAT | nofollow,
                0o600,
                dir_fd=parent,
            )
        finally:
            os.close(parent)
        try:
            info = os.fstat(descriptor)
            _need(
                stat.S_ISREG(info.st_mode)
                and info.st_uid == os.geteuid()
                and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_nlink == 1,
                "held-out oracle lock custody is invalid",
            )
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise HeldOutOracleError("held-out oracle run is already active") from exc
            self._descriptor = descriptor
            return self
        except BaseException:
            os.close(descriptor)
            raise

    def __exit__(self, *_: object) -> None:
        descriptor, self._descriptor = self._descriptor, None
        if descriptor is None:
            return
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


__all__ = [
    "HeldOutOracleError",
    "OracleRunLock",
    "list_private_directory",
    "private_directory",
    "read_exact",
    "write_exact",
]
