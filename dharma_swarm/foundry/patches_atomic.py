"""Descriptor-anchored atomic replacement for one parsed Foundry patch."""

from __future__ import annotations

import errno
import os
import re
import secrets
import stat
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from dharma_swarm.foundry.patches import PatchReplayError, ParsedPatch, _replay

_DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
_READ_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_ctime_ns,
        value.st_mtime_ns,
    )


def _dir_identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _replacement_identity(
    value: os.stat_result,
) -> tuple[int, int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        stat.S_IMODE(value.st_mode),
        value.st_uid,
        value.st_gid,
        value.st_nlink,
    )


def _read_all(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:  # pragma: no cover - defensive OS contract
            raise OSError("short atomic patch write")
        view = view[written:]


def _open_parent(root: Path, path: PurePosixPath) -> tuple[list[int], int, str]:
    descriptors: list[int] = []
    try:
        current = os.open(root, _DIR_FLAGS)
        descriptors.append(current)
        for part in path.parts[:-1]:
            current = os.open(part, _DIR_FLAGS, dir_fd=current)
            descriptors.append(current)
    except OSError as exc:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise PatchReplayError("patch target is unavailable or unsafe") from exc
    return descriptors, current, path.parts[-1]


def _reopen_parent(
    root_fd: int,
    path: PurePosixPath,
    expected: list[tuple[int, int]],
) -> int:
    current = os.dup(root_fd)
    try:
        if _dir_identity(os.fstat(current)) != expected[0]:
            raise PatchReplayError("pinned tree root identity drifted")
        for part, identity in zip(path.parts[:-1], expected[1:], strict=True):
            following = os.open(part, _DIR_FLAGS, dir_fd=current)
            os.close(current)
            current = following
            if _dir_identity(os.fstat(current)) != identity:
                raise PatchReplayError("patch target directory pathname drifted")
        return current
    except Exception:
        os.close(current)
        raise


def _create_temp(
    parent_fd: int, mode: int, operation_id: str | None
) -> tuple[int, str, bool]:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    if operation_id is not None:
        if re.fullmatch(r"[0-9a-f]{64}", operation_id) is None:
            raise PatchReplayError("atomic patch operation_id is malformed")
        name = f".foundry-replay-{operation_id}"
        try:
            return os.open(name, flags, mode, dir_fd=parent_fd), name, True
        except FileExistsError:
            try:
                return os.open(name, _READ_FLAGS, dir_fd=parent_fd), name, False
            except OSError as exc:
                raise PatchReplayError("atomic patch recovery temp is unsafe") from exc
        except OSError as exc:
            raise PatchReplayError("atomic patch temp creation failed") from exc
    for _ in range(32):
        name = f".foundry-replay-{secrets.token_hex(12)}"
        try:
            descriptor = os.open(name, flags, mode, dir_fd=parent_fd)
        except FileExistsError:
            continue
        except OSError as exc:
            raise PatchReplayError("atomic patch temp creation failed") from exc
        return descriptor, name, True
    raise PatchReplayError("atomic patch temp name budget exhausted")


def _validate_temp(
    descriptor: int,
    *,
    candidate: bytes,
    expected_device: int,
    expected_mode: int,
    expected_uid: int,
    expected_gid: int,
) -> os.stat_result:
    before = os.fstat(descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_dev != expected_device
        or stat.S_IMODE(before.st_mode) != expected_mode
        or before.st_uid != expected_uid
        or before.st_gid != expected_gid
        or before.st_nlink != 1
        or before.st_size != len(candidate)
    ):
        raise PatchReplayError("atomic patch recovery temp does not match")
    os.lseek(descriptor, 0, os.SEEK_SET)
    observed = _read_all(descriptor)
    after = os.fstat(descriptor)
    if observed != candidate or _file_identity(before) != _file_identity(after):
        raise PatchReplayError("atomic patch recovery temp does not match")
    return after


def fsync_exact_replacement(
    root: Path,
    source_path: str,
    *,
    expected_root_identity: tuple[int, int],
    expected_replacement_identity: tuple[int, int, int, int, int, int, int],
    expected_bytes: bytes,
) -> None:
    """Durably sync one exact replacement through held no-follow descriptors.

    A visible rename is not a durable effect.  This primitive pins the whole
    path, verifies the exact replacement before and after syncing both the file
    and its parent directory, and fails closed on any identity or byte drift.
    """

    text = str(source_path)
    path = PurePosixPath(text)
    if (
        not text
        or text.startswith("/")
        or "\\" in text
        or "\x00" in text
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise PatchReplayError("unsafe exact replacement path")
    try:
        resolved_root = Path(root).resolve(strict=True)
    except OSError as exc:
        raise PatchReplayError("pinned tree is unavailable") from exc
    descriptors, parent_fd, name = _open_parent(resolved_root, path)
    directory_identities = [_dir_identity(os.fstat(fd)) for fd in descriptors]

    def validate(descriptor: int) -> tuple[int, int, int, int, int]:
        before = os.fstat(descriptor)
        if _replacement_identity(before) != expected_replacement_identity:
            raise PatchReplayError("exact replacement identity drifted")
        os.lseek(descriptor, 0, os.SEEK_SET)
        observed = _read_all(descriptor)
        after = os.fstat(descriptor)
        if observed != expected_bytes or _file_identity(before) != _file_identity(after):
            raise PatchReplayError("exact replacement bytes drifted")
        return _file_identity(after)

    target_fd = None
    try:
        if directory_identities[0] != expected_root_identity:
            raise PatchReplayError("pinned tree root identity drifted")
        target_fd = os.open(name, _READ_FLAGS, dir_fd=parent_fd)
        target_identity = validate(target_fd)
        os.fsync(target_fd)
        if validate(target_fd) != target_identity:
            raise PatchReplayError("exact replacement drifted across file sync")
        os.fsync(parent_fd)
        if any(
            _dir_identity(os.fstat(fd)) != identity
            for fd, identity in zip(descriptors, directory_identities, strict=True)
        ):
            raise PatchReplayError("patch target directory identity drifted")
        if _dir_identity(os.stat(resolved_root, follow_symlinks=False)) != (
            directory_identities[0]
        ):
            raise PatchReplayError("pinned tree root pathname drifted after sync")
        fresh_parent = _reopen_parent(descriptors[0], path, directory_identities)
        try:
            confirmed_fd = os.open(name, _READ_FLAGS, dir_fd=fresh_parent)
            try:
                if validate(confirmed_fd) != target_identity:
                    raise PatchReplayError("exact replacement changed after sync")
            finally:
                os.close(confirmed_fd)
        finally:
            os.close(fresh_parent)
    except PatchReplayError:
        raise
    except OSError as exc:
        raise PatchReplayError("exact replacement durability sync failed") from exc
    finally:
        if target_fd is not None:
            os.close(target_fd)
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def apply_parsed_diff_atomic(
    root: Path,
    parsed: ParsedPatch,
    *,
    allowed_paths: Iterable[str],
    check_only: bool,
    expected_identity: tuple[int, int, int] | None,
    expected_root_identity: tuple[int, int] | None,
    operation_id: str | None,
) -> Path:
    """Replay via held no-follow descriptors and rename within the held parent."""

    try:
        resolved_root = Path(root).resolve(strict=True)
    except OSError as exc:
        raise PatchReplayError("pinned tree is unavailable") from exc
    allowed = {PurePosixPath(str(path)).as_posix() for path in allowed_paths}
    if not allowed:
        raise PatchReplayError("declared evolve scope is empty")
    if parsed.path not in allowed:
        raise PatchReplayError(
            f"patch path is outside declared evolve scope: {parsed.path}"
        )
    path = PurePosixPath(parsed.path)
    descriptors, parent_fd, name = _open_parent(resolved_root, path)
    directory_identities = [_dir_identity(os.fstat(fd)) for fd in descriptors]
    if (
        expected_root_identity is not None
        and directory_identities[0] != expected_root_identity
    ):
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise PatchReplayError("pinned tree root identity drifted")
    target_fd = temporary_fd = None
    temporary_name = ""
    temporary_created_here = False
    try:
        try:
            target_fd = os.open(name, _READ_FLAGS, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise PatchReplayError(
                    f"symlinked patch path is forbidden: {parsed.path}"
                ) from exc
            raise PatchReplayError(
                f"patch target is unavailable: {parsed.path}"
            ) from exc
        before = os.fstat(target_fd)
        if not stat.S_ISREG(before.st_mode):
            raise PatchReplayError(f"patch target is not a regular file: {parsed.path}")
        if expected_identity is not None and (
            before.st_dev,
            before.st_ino,
            before.st_ctime_ns,
        ) != expected_identity:
            raise PatchReplayError("patch target identity drifted before replay")
        source_bytes = _read_all(target_fd)
        after_read = os.fstat(target_fd)
        if len(source_bytes) != before.st_size or _file_identity(before) != _file_identity(
            after_read
        ):
            raise PatchReplayError("patch target changed while read")
        try:
            source = source_bytes.decode("utf-8").splitlines(keepends=True)
        except UnicodeDecodeError as exc:
            raise PatchReplayError("binary artifact targets are unsupported") from exc
        candidate = "".join(_replay(source, parsed)).encode("utf-8")
        if check_only:
            return resolved_root / Path(*path.parts)

        expected_mode = stat.S_IMODE(before.st_mode)
        parent_device = os.fstat(parent_fd).st_dev
        temporary_fd, temporary_name, created = _create_temp(
            parent_fd, expected_mode, operation_id
        )
        temporary_created_here = created
        if created:
            _write_all(temporary_fd, candidate)
            os.fchmod(temporary_fd, expected_mode)
            os.fsync(temporary_fd)
        temporary = _validate_temp(
            temporary_fd,
            candidate=candidate,
            expected_device=parent_device,
            expected_mode=expected_mode,
            expected_uid=before.st_uid,
            expected_gid=before.st_gid,
        )
        temporary_identity = _replacement_identity(temporary)
        if any(
            _dir_identity(os.fstat(fd)) != identity
            for fd, identity in zip(descriptors, directory_identities, strict=True)
        ):
            raise PatchReplayError("patch target directory identity drifted")
        if _dir_identity(os.stat(resolved_root, follow_symlinks=False)) != (
            directory_identities[0]
        ):
            raise PatchReplayError("pinned tree root pathname drifted")
        fresh_parent = _reopen_parent(descriptors[0], path, directory_identities)
        try:
            current_fd = os.open(name, _READ_FLAGS, dir_fd=fresh_parent)
            try:
                if _file_identity(os.fstat(current_fd)) != _file_identity(before):
                    raise PatchReplayError("patch target identity drifted before replace")
            finally:
                os.close(current_fd)
        finally:
            os.close(fresh_parent)
        temporary = _validate_temp(
            temporary_fd,
            candidate=candidate,
            expected_device=parent_device,
            expected_mode=expected_mode,
            expected_uid=before.st_uid,
            expected_gid=before.st_gid,
        )
        if _replacement_identity(temporary) != temporary_identity:
            raise PatchReplayError("atomic patch recovery temp identity drifted")
        os.replace(
            temporary_name,
            name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        temporary_name = ""
        os.fsync(parent_fd)
        if _dir_identity(os.stat(resolved_root, follow_symlinks=False)) != (
            directory_identities[0]
        ):
            raise PatchReplayError("pinned tree root pathname drifted after replace")
        fresh_parent = _reopen_parent(descriptors[0], path, directory_identities)
        replaced_fd = os.open(name, _READ_FLAGS, dir_fd=fresh_parent)
        try:
            replaced = os.fstat(replaced_fd)
            if _replacement_identity(replaced) != temporary_identity:
                raise PatchReplayError("atomic patch replacement identity mismatch")
            if _read_all(replaced_fd) != candidate:
                raise PatchReplayError("atomic patch postimage mismatch")
        finally:
            os.close(replaced_fd)
            os.close(fresh_parent)
        return resolved_root / Path(*path.parts)
    except PatchReplayError:
        raise
    except OSError as exc:
        raise PatchReplayError("atomic patch replacement failed") from exc
    finally:
        if temporary_fd is not None:
            os.close(temporary_fd)
        if target_fd is not None:
            os.close(target_fd)
        if temporary_name and temporary_created_here:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except OSError:
                pass
        for descriptor in reversed(descriptors):
            os.close(descriptor)


__all__ = ["apply_parsed_diff_atomic", "fsync_exact_replacement"]
