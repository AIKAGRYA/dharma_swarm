"""Filesystem fences shared by Forge Lab reconciliation operations."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from dharma_swarm.forge_lab.state_io import forge_state_root


class ReconciliationError(RuntimeError):
    """Fail-closed refusal with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _identity(metadata: os.stat_result) -> dict[str, Any]:
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "size": metadata.st_size,
        "mtime_ns": metadata.st_mtime_ns,
    }


def root(value: Path | None) -> tuple[Path, dict[str, Any]]:
    raw = (Path(value) if value is not None else forge_state_root()).expanduser()
    if not raw.is_absolute() or raw == Path("/"):
        raise ReconciliationError(
            "STATE_ROOT_UNSAFE", "forge root must be absolute and non-root"
        )
    try:
        metadata = raw.lstat()
    except OSError:
        raise ReconciliationError(
            "STATE_ROOT_UNSAFE", f"forge root unavailable: {raw}"
        ) from None
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ReconciliationError(
            "AMBIGUOUS_PATH", f"forge root is not a real directory: {raw}"
        )
    try:
        resolved = raw.resolve(strict=True)
    except OSError:
        raise ReconciliationError(
            "STATE_ROOT_UNSAFE", f"forge root unavailable: {raw}"
        ) from None
    if resolved != raw:
        raise ReconciliationError(
            "AMBIGUOUS_PATH", f"forge root is not canonical: {raw}"
        )
    return resolved, {
        "path": str(resolved),
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
    }


def unambiguous(root_path: Path, path: Path) -> None:
    try:
        parts = path.relative_to(root_path).parts
    except ValueError as exc:
        raise ReconciliationError(
            "AMBIGUOUS_PATH", f"path escapes forge root: {path}"
        ) from exc
    current = root_path
    for index, part in enumerate(parts):
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            return
        except OSError:
            raise ReconciliationError(
                "AMBIGUOUS_PATH", f"cannot inspect: {current}"
            ) from None
        if stat.S_ISLNK(metadata.st_mode):
            raise ReconciliationError(
                "AMBIGUOUS_PATH", f"symlink is forbidden: {current}"
            )
        if index < len(parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise ReconciliationError(
                "AMBIGUOUS_PATH", f"non-directory ancestor: {current}"
            )


def read_json(root_path: Path, path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    unambiguous(root_path, path)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise ReconciliationError(
            "PROJECTION_UNREADABLE", f"cannot open: {path}"
        ) from None
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > 1024 * 1024:
            raise ReconciliationError(
                "PROJECTION_INVALID", f"not a bounded file: {path}"
            )
        raw = b""
        while chunk := os.read(descriptor, 65536):
            raw += chunk
        after = os.fstat(descriptor)
    except ReconciliationError:
        raise
    except OSError:
        raise ReconciliationError(
            "PROJECTION_UNREADABLE", f"cannot read: {path}"
        ) from None
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
    if _identity(before) != _identity(after):
        raise ReconciliationError(
            "PROJECTION_CHANGED", f"projection changed while read: {path}"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReconciliationError(
            "PROJECTION_INVALID", f"invalid JSON: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReconciliationError(
            "PROJECTION_INVALID", "projection must be a JSON object"
        )
    return payload, _identity(before)


def mkdir(root_path: Path, relative: Path) -> Path:
    path = root_path / relative
    unambiguous(root_path, path)
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        raise ReconciliationError(
            "DIRECTORY_PREPARE_FAILED", f"could not prepare directory: {path}"
        ) from None
    unambiguous(root_path, path)
    if not path.is_dir():
        raise ReconciliationError("AMBIGUOUS_PATH", f"unsafe directory: {path}")
    return path


@contextmanager
def lock(root_path: Path, relative: Path) -> Iterator[None]:
    mkdir(root_path, relative.parent)
    path = root_path / relative
    unambiguous(root_path, path)
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError:
        raise ReconciliationError(
            "LOCK_PATH_UNSAFE", f"cannot open lock: {path}"
        ) from None
    try:
        try:
            metadata = os.fstat(descriptor)
        except OSError:
            raise ReconciliationError(
                "LOCK_PATH_UNSAFE", f"cannot inspect lock: {path}"
            ) from None
        if not stat.S_ISREG(metadata.st_mode):
            raise ReconciliationError(
                "LOCK_PATH_UNSAFE", f"lock is not a file: {path}"
            )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ReconciliationError(
                "CONTROL_BUSY", f"another controller holds {path}"
            ) from exc
        except OSError:
            raise ReconciliationError(
                "LOCK_UNAVAILABLE", f"cannot acquire control lock: {path}"
            ) from None
        yield
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass


def fsync_directory(path: Path) -> None:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        os.fsync(descriptor)
    except OSError:
        raise ReconciliationError(
            "DIRECTORY_SYNC_FAILED", f"could not durably synchronize directory: {path}"
        ) from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


__all__ = ["ReconciliationError"]
