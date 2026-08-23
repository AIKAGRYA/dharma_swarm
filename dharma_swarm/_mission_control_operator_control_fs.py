"""Private fail-closed filesystem custody for SADHANA operator control."""

from __future__ import annotations

import ctypes
import errno
import os
import re
import secrets
import stat
from pathlib import Path

MAX_ENVELOPE_BYTES = 4096
CONTROL_FILE_MODE = 0o640
CONTROL_FILENAME_RE = re.compile(r"\A[0-9a-f]{64}\.control\.json\Z")
TERMINAL_FILENAME_RE = re.compile(r"\A[0-9a-f]{64}\.terminal\.json\Z")


class OperatorControlError(ValueError):
    """Base class for safe, typed protocol failures."""

    code = "invalid_control_request"


class ControlConfigurationError(ValueError):
    """Programming or trusted configuration fault, never candidate poison."""


class ControlSchemaError(OperatorControlError):
    code = "invalid_schema"


class ControlAuthenticationError(OperatorControlError):
    code = "invalid_authentication"


class ControlExpiredError(OperatorControlError):
    code = "expired_request"


class ControlFutureRequestError(OperatorControlError):
    code = "future_request"


class ControlIdempotencyConflict(OperatorControlError):
    code = "idempotency_conflict"


class UnsafeInboxEntry(OperatorControlError):
    code = "unsafe_inbox_entry"


class InboxUnavailable(OperatorControlError):
    code = "inbox_unavailable"


def _required_os_flag(name: str) -> int:
    value = getattr(os, name, None)
    if not isinstance(value, int) or value == 0:
        raise ControlConfigurationError(
            f"platform lacks required filesystem flag {name}"
        )
    return value


def open_directory_nofollow(path: Path) -> int:
    """Open every absolute directory component without following symlinks."""

    directory_flag = _required_os_flag("O_DIRECTORY")
    nofollow_flag = _required_os_flag("O_NOFOLLOW")
    absolute = Path(os.path.abspath(path))
    descriptor = os.open(
        "/", os.O_RDONLY | directory_flag | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        for component in absolute.parts[1:]:
            if component in {"", ".", ".."}:
                raise UnsafeInboxEntry("inbox path contains an unsafe component")
            flags = (
                os.O_RDONLY
                | directory_flag
                | getattr(os, "O_CLOEXEC", 0)
                | nofollow_flag
            )
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            identity = os.fstat(next_descriptor)
            if not stat.S_ISDIR(identity.st_mode):
                os.close(next_descriptor)
                raise UnsafeInboxEntry("inbox path component is not a directory")
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise InboxUnavailable("control inbox cannot be opened safely") from exc
    except Exception:
        os.close(descriptor)
        raise


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise InboxUnavailable("control candidate write did not progress")
        view = view[written:]


def rename_noreplace(
    source_directory: int,
    source_name: str,
    destination_directory: int,
    destination_name: str,
) -> None:
    """Atomically rename without replacement on Linux or Darwin, else fail closed."""

    libc = ctypes.CDLL(None, use_errno=True)
    if hasattr(libc, "renameat2"):
        rename = libc.renameat2
        flag = 1  # Linux RENAME_NOREPLACE
    elif hasattr(libc, "renameatx_np"):
        rename = libc.renameatx_np
        flag = 0x00000004  # Darwin RENAME_EXCL
    else:
        raise InboxUnavailable("platform lacks atomic no-replace rename")
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    result = rename(
        source_directory,
        os.fsencode(source_name),
        destination_directory,
        os.fsencode(destination_name),
        flag,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, os.strerror(error_number), destination_name)
    raise OSError(error_number, os.strerror(error_number), destination_name)


def read_regular_entry(
    directory_descriptor: int, filename: str, *, require_mode: bool = True
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | _required_os_flag("O_NOFOLLOW")
    try:
        descriptor = os.open(filename, flags, dir_fd=directory_descriptor)
    except OSError as exc:
        raise UnsafeInboxEntry("control candidate cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise UnsafeInboxEntry(
                "control candidate must be a single-link regular file"
            )
        if require_mode and stat.S_IMODE(before.st_mode) != CONTROL_FILE_MODE:
            raise UnsafeInboxEntry("control candidate mode must be 0640")
        if before.st_size <= 0 or before.st_size > MAX_ENVELOPE_BYTES:
            raise ControlSchemaError("control candidate size is outside bounds")
        chunks: list[bytes] = []
        remaining = MAX_ENVELOPE_BYTES + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(remaining, 4096))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(descriptor)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if (
            any(
                getattr(before, field) != getattr(after, field)
                for field in stable_fields
            )
            or len(payload) != before.st_size
            or len(payload) > MAX_ENVELOPE_BYTES
        ):
            raise UnsafeInboxEntry("control candidate changed while being read")
        return payload
    finally:
        os.close(descriptor)


def atomic_publish(
    directory: Path,
    filename: str,
    payload: bytes,
    *,
    filename_pattern: re.Pattern[str] = CONTROL_FILENAME_RE,
) -> bool:
    """Publish without overwrite; return True only for an identical replay."""

    if not filename_pattern.fullmatch(filename):
        raise ControlSchemaError("control candidate filename is invalid")
    directory_descriptor = open_directory_nofollow(directory)
    temporary_name = f".{filename}.{secrets.token_hex(16)}.part"
    temporary_descriptor: int | None = None
    temporary_exists = False
    try:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | _required_os_flag("O_NOFOLLOW")
        )
        temporary_descriptor = os.open(
            temporary_name, flags, CONTROL_FILE_MODE, dir_fd=directory_descriptor
        )
        temporary_exists = True
        os.fchmod(temporary_descriptor, CONTROL_FILE_MODE)
        identity = os.fstat(temporary_descriptor)
        if not stat.S_ISREG(identity.st_mode) or identity.st_nlink != 1:
            raise UnsafeInboxEntry("temporary control candidate is unsafe")
        _write_all(temporary_descriptor, payload)
        os.fsync(temporary_descriptor)
        identity = os.fstat(temporary_descriptor)
        if identity.st_size != len(payload) or identity.st_nlink != 1:
            raise UnsafeInboxEntry("temporary control candidate changed during write")
        os.close(temporary_descriptor)
        temporary_descriptor = None
        try:
            rename_noreplace(
                directory_descriptor,
                temporary_name,
                directory_descriptor,
                filename,
            )
            temporary_exists = False
        except FileExistsError:
            if read_regular_entry(directory_descriptor, filename) == payload:
                return True
            raise ControlIdempotencyConflict(
                "idempotency key is already bound to different canonical bytes"
            )
        except OSError as exc:
            raise InboxUnavailable(
                "control candidate cannot be published atomically"
            ) from exc
        os.fsync(directory_descriptor)
        if read_regular_entry(directory_descriptor, filename) != payload:
            raise UnsafeInboxEntry("published control candidate changed unexpectedly")
        return False
    finally:
        if temporary_descriptor is not None:
            os.close(temporary_descriptor)
        if temporary_exists:
            try:
                os.unlink(temporary_name, dir_fd=directory_descriptor)
            except FileNotFoundError:
                pass
        os.close(directory_descriptor)


def atomic_move_regular(source: Path, destination_directory: Path) -> bytes:
    """Atomically move one safe candidate, accepting only an identical replay."""

    if not CONTROL_FILENAME_RE.fullmatch(source.name):
        raise ControlSchemaError("control candidate filename is invalid")
    source_directory = open_directory_nofollow(source.parent)
    destination = open_directory_nofollow(destination_directory)
    try:
        payload = read_regular_entry(source_directory, source.name)
        try:
            rename_noreplace(source_directory, source.name, destination, source.name)
        except FileExistsError:
            if read_regular_entry(destination, source.name) != payload:
                raise ControlIdempotencyConflict(
                    "custody destination contains different canonical bytes"
                )
            # Claim the duplicate into the private destination before cleanup.
            # A writer with access to the source dropbox can replace its stable
            # name, but cannot make those substituted bytes become the canonical
            # destination or race the subsequent private-directory unlink.
            replay_name = f".replay.{source.name}.{secrets.token_hex(16)}"
            rename_noreplace(
                source_directory,
                source.name,
                destination,
                replay_name,
            )
            os.fsync(source_directory)
            os.fsync(destination)
            claimed_payload = read_regular_entry(destination, replay_name)
            if (
                claimed_payload != payload
                or read_regular_entry(destination, source.name) != payload
            ):
                raise UnsafeInboxEntry(
                    "control source changed before private replay cleanup"
                )
            os.unlink(replay_name, dir_fd=destination)
        except OSError as exc:
            raise InboxUnavailable("control custody move failed atomically") from exc
        os.fsync(source_directory)
        os.fsync(destination)
        if read_regular_entry(destination, source.name) != payload:
            raise UnsafeInboxEntry("control candidate changed during custody move")
        return payload
    finally:
        os.close(source_directory)
        os.close(destination)


def quarantine_unsafe(source: Path, rejected_directory: Path) -> Path:
    """Move an unsafe name without following or later treating it as evidence."""

    source_directory = open_directory_nofollow(source.parent)
    rejected = open_directory_nofollow(rejected_directory)
    quarantine_name = f".unsafe.{source.name}.{secrets.token_hex(16)}"
    try:
        try:
            os.stat(source.name, dir_fd=source_directory, follow_symlinks=False)
        except OSError as exc:
            raise UnsafeInboxEntry("control custody entry is unavailable") from exc
        rename_noreplace(
            source_directory,
            source.name,
            rejected,
            quarantine_name,
        )
        os.fsync(source_directory)
        os.fsync(rejected)
    finally:
        os.close(source_directory)
        os.close(rejected)
    return rejected_directory / quarantine_name
