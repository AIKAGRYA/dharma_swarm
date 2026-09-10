"""Small atomic state files; no paths obtained from receipts escape the state root."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import DesktopError

MAX_STATE_BYTES = 1_048_576


def state_path(root: Path, relative: str) -> Path:
    child = Path(relative)
    if child.is_absolute() or not child.parts or any(p in {".", ".."} for p in child.parts):
        raise DesktopError("invalid state-relative path")
    current = root
    if any(parent.is_symlink() for parent in (root, *root.parents)):
        raise DesktopError(f"refusing symlink in state root: {root}")
    for part in child.parts:
        current = current / part
        if current.is_symlink():
            raise DesktopError(f"refusing symlink inside state directory: {current}")
    if root.resolve() not in current.resolve().parents:
        raise DesktopError("state path escaped its root")
    return current


def read_json(root: Path, relative: str) -> dict[str, Any] | None:
    path = state_path(root, relative)
    try:
        if path.stat().st_size > MAX_STATE_BYTES:
            raise DesktopError(f"state file exceeds size limit: {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise DesktopError(f"cannot read state file {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise DesktopError(f"state file must contain an object: {path.name}")
    return value


def write_bytes(root: Path, relative: str, data: bytes, mode: int = 0o600) -> None:
    path = state_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_path(root, relative)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        state_path(root, relative)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(root: Path, relative: str, value: dict[str, Any]) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if len(data) > MAX_STATE_BYTES:
        raise DesktopError("state exceeds size limit")
    write_bytes(root, relative, data)


@contextmanager
def operation_lock(root: Path) -> Iterator[None]:
    """Serialize explicit desktop actions, fail promptly instead of queueing UI clicks."""
    path = state_path(root, "operation.lock")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DesktopError("another desktop action is in progress; retry when it finishes") from exc
        yield
    finally:
        os.close(fd)
