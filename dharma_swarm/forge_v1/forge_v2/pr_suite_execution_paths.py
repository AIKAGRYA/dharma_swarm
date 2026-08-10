"""Race-resistant path validation and receipt materialization helpers."""
from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .pr_suite_execution_profile import (
    UnsafeTargetPath,
    _SECRET_NAME_RE,
    _URL_USERINFO_RE,
)


def validated_target_path(target: str, checkout: Path) -> str:
    full = str(target)
    raw = full.split("::", 1)[0].strip()
    if not raw or any(character in full for character in ("\x00", "\\", "\n", "\r")):
        raise UnsafeTargetPath("test target must be a non-empty POSIX path")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise UnsafeTargetPath(f"unsafe test target path: {raw!r}")
    if pure.parts[0].endswith(":"):
        raise UnsafeTargetPath(f"drive-qualified test target path: {raw!r}")
    root = checkout.resolve(strict=False)
    destination = checkout.joinpath(*pure.parts)
    try:
        destination.resolve(strict=False).relative_to(root)
        destination.parent.resolve(strict=False).relative_to(root)
    except (OSError, ValueError) as exc:
        raise UnsafeTargetPath(f"test target escapes checkout: {raw!r}") from exc
    return pure.as_posix()


def redact_secret_text(value: str) -> str:
    """Redact URL userinfo and explicit credential assignments in receipts."""

    redacted = _URL_USERINFO_RE.sub(r"\1<redacted>@", str(value))
    if "=" in redacted:
        name, _, _ = redacted.partition("=")
        if _SECRET_NAME_RE.search(name):
            return f"{name}=<redacted>"
    return redacted


def safe_materialization_path(checkout: Path, target: str) -> Path:
    """Return a validated destination for read-only callers.

    Production writes must use :func:`materialize_text`, which performs the
    traversal and final open relative to directory file descriptors. Merely
    resolving a path and then calling ``Path.write_text`` leaves a check/use
    gap and follows a final symlink.
    """

    relative = validated_target_path(target, checkout)
    destination = checkout.joinpath(*PurePosixPath(relative).parts)
    root = checkout.resolve(strict=True)
    try:
        destination.resolve(strict=False).relative_to(root)
        destination.parent.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise UnsafeTargetPath(f"test target symlink escapes checkout: {relative!r}") from exc
    current = checkout
    for part in PurePosixPath(relative).parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise UnsafeTargetPath(f"test target contains a symlink: {relative!r}")
    return destination


def _open_materialization_parent(checkout: Path, relative: str) -> tuple[int, str]:
    """Open a target's parent without following checkout-controlled links."""

    parts = PurePosixPath(relative).parts
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        descriptor = os.open(checkout, flags)
    except OSError as exc:
        raise UnsafeTargetPath("checkout is not a safe materialization directory") from exc
    try:
        for part in parts[:-1]:
            try:
                os.mkdir(part, mode=0o700, dir_fd=descriptor)
            except FileExistsError:
                pass
            try:
                child = os.open(part, flags, dir_fd=descriptor)
            except OSError as exc:
                raise UnsafeTargetPath(
                    f"test target parent is not a real directory: {relative!r}"
                ) from exc
            os.close(descriptor)
            descriptor = child
        return descriptor, parts[-1]
    except BaseException:
        os.close(descriptor)
        raise


def materialize_text(checkout: Path, target: str, value: str) -> Path:
    """Write one test artifact without following repository-controlled links."""

    relative = validated_target_path(target, checkout)
    parent_fd, name = _open_materialization_parent(checkout, relative)
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise UnsafeTargetPath(
                f"test target is not a safe regular file: {relative!r}"
            ) from exc
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise UnsafeTargetPath(
                f"test target is not a singly-linked regular file: {relative!r}"
            )
        encoded = value.encode("utf-8")
        os.ftruncate(descriptor, 0)
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise OSError("materialization write made no progress")
            offset += written
        os.fsync(descriptor)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)
    return checkout.joinpath(*PurePosixPath(relative).parts)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
    )


__all__ = [
    "atomic_write_json",
    "atomic_write_text",
    "materialize_text",
    "redact_secret_text",
    "safe_materialization_path",
    "validated_target_path",
]
