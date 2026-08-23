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
CONTROL_CLAIM_FILENAME_RE = re.compile(
    r"\A\.claim\.(?P<control>[0-9a-f]{64}\.control\.json)\."
    r"(?P<nonce>[0-9a-f]{32})\Z"
)
CONTROL_QUARANTINE_FILENAME_RE = re.compile(
    r"\A\.quarantine\.(?P<control>[0-9a-f]{64}\.control\.json)\."
    r"(?P<error>[a-z][a-z0-9_]*)\.(?P<nonce>[0-9a-f]{32})\Z"
)
CONTROL_QUARANTINE_RECEIPT_FILENAME_RE = re.compile(
    r"\A\.quarantine\.(?P<control>[0-9a-f]{64}\.control\.json)\."
    r"(?P<error>[a-z][a-z0-9_]*)\.(?P<nonce>[0-9a-f]{32})"
    r"\.terminal\.json\Z"
)
_ERROR_CODE_RE = re.compile(r"\A[a-z][a-z0-9_]*\Z")
_PRIVATE_NAME_ATTEMPTS = 8


class OperatorControlError(ValueError):
    """Base class for safe, typed protocol failures."""

    code = "invalid_control_request"
    claim_path: Path | None = None
    control_filename: str = ""


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
    """Claim before reading, then promote only the exact claimed regular file.

    The public dropbox name is never opened before it is atomically moved to an
    unpredictable name in the private destination.  Any validation failure is
    annotated with that durable claim path so the caller can quarantine the
    object it actually owns instead of retrying a possibly replaced source.
    """

    if not CONTROL_FILENAME_RE.fullmatch(source.name):
        raise ControlSchemaError("control candidate filename is invalid")
    claim_path = claim_control_candidate(source, destination_directory)
    return promote_claimed_regular(claim_path)


def claim_control_candidate(source: Path, destination_directory: Path) -> Path:
    """Atomically take custody under an unpredictable private claim name."""

    if not CONTROL_FILENAME_RE.fullmatch(source.name):
        raise ControlSchemaError("control candidate filename is invalid")
    source_directory = open_directory_nofollow(source.parent)
    try:
        destination = open_directory_nofollow(destination_directory)
    except Exception:
        os.close(source_directory)
        raise
    claimed_name = ""
    claimed = False
    try:
        for _ in range(_PRIVATE_NAME_ATTEMPTS):
            claimed_name = f".claim.{source.name}.{secrets.token_hex(16)}"
            try:
                rename_noreplace(
                    source_directory,
                    source.name,
                    destination,
                    claimed_name,
                )
                claimed = True
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise InboxUnavailable(
                    "control custody claim failed atomically"
                ) from exc
        if not claimed:
            raise InboxUnavailable("control custody claim name could not be allocated")
        os.fsync(source_directory)
        os.fsync(destination)
        return destination_directory / claimed_name
    except OperatorControlError as exc:
        if claimed:
            _annotate_claim_error(
                exc,
                claim_path=destination_directory / claimed_name,
                control_filename=source.name,
            )
        raise
    except OSError as exc:
        unavailable = InboxUnavailable("control custody claim was not made durable")
        if claimed:
            _annotate_claim_error(
                unavailable,
                claim_path=destination_directory / claimed_name,
                control_filename=source.name,
            )
        raise unavailable from exc
    finally:
        os.close(source_directory)
        os.close(destination)


def claimed_control_filename(claim_name: str) -> str:
    """Return the canonical name bound into one private custody claim."""

    match = CONTROL_CLAIM_FILENAME_RE.fullmatch(claim_name)
    if match is None:
        raise ControlSchemaError("control custody claim filename is invalid")
    return match.group("control")


def promote_claimed_regular(claim_path: Path) -> bytes:
    """Validate a private claim and promote it without replacing canonical state."""

    control_name = claimed_control_filename(claim_path.name)
    directory = open_directory_nofollow(claim_path.parent)
    promoted = False
    try:
        payload = read_regular_entry(directory, claim_path.name)
        try:
            rename_noreplace(directory, claim_path.name, directory, control_name)
            promoted = True
        except FileExistsError:
            if read_regular_entry(directory, control_name) != payload:
                raise ControlIdempotencyConflict(
                    "custody destination contains different canonical bytes"
                )
            if read_regular_entry(directory, claim_path.name) != payload:
                raise UnsafeInboxEntry("private custody claim changed before replay")
            try:
                os.unlink(claim_path.name, dir_fd=directory)
                promoted = True
            except OSError as exc:
                raise InboxUnavailable(
                    "private replay claim could not be removed"
                ) from exc
        except OSError as exc:
            raise InboxUnavailable(
                "control custody promotion failed atomically"
            ) from exc
        os.fsync(directory)
        if read_regular_entry(directory, control_name) != payload:
            raise UnsafeInboxEntry("control candidate changed during custody promotion")
        return payload
    except OperatorControlError as exc:
        _annotate_claim_error(
            exc,
            claim_path=(claim_path.parent / control_name if promoted else claim_path),
            control_filename=control_name,
        )
        raise
    except OSError as exc:
        unavailable = InboxUnavailable("control custody promotion was not durable")
        _annotate_claim_error(
            unavailable,
            claim_path=(claim_path.parent / control_name if promoted else claim_path),
            control_filename=control_name,
        )
        raise unavailable from exc
    finally:
        os.close(directory)


def _annotate_claim_error(
    error: OperatorControlError, *, claim_path: Path, control_filename: str
) -> None:
    """Bind a typed failure to the private object that actually caused it."""

    error.claim_path = claim_path
    error.control_filename = control_filename


def quarantine_unsafe(
    source: Path,
    rejected_directory: Path,
    *,
    control_filename: str,
    error_code: str,
) -> Path:
    """Move a claimed object to collision-safe, non-canonical quarantine."""

    if not CONTROL_FILENAME_RE.fullmatch(control_filename):
        raise ControlSchemaError("quarantine control filename is invalid")
    if not _ERROR_CODE_RE.fullmatch(error_code):
        raise ControlSchemaError("quarantine error code is invalid")

    source_directory = open_directory_nofollow(source.parent)
    try:
        rejected = open_directory_nofollow(rejected_directory)
    except Exception:
        os.close(source_directory)
        raise
    quarantine_name = ""
    quarantined = False
    try:
        try:
            os.stat(source.name, dir_fd=source_directory, follow_symlinks=False)
        except OSError as exc:
            raise UnsafeInboxEntry("control custody entry is unavailable") from exc
        for _ in range(_PRIVATE_NAME_ATTEMPTS):
            quarantine_name = (
                f".quarantine.{control_filename}.{error_code}."
                f"{secrets.token_hex(16)}"
            )
            try:
                rename_noreplace(
                    source_directory,
                    source.name,
                    rejected,
                    quarantine_name,
                )
                quarantined = True
                break
            except FileExistsError:
                continue
            except OSError as exc:
                raise InboxUnavailable(
                    "control quarantine move failed atomically"
                ) from exc
        if not quarantined:
            raise InboxUnavailable("control quarantine name could not be allocated")
        os.fsync(source_directory)
        os.fsync(rejected)
    finally:
        os.close(source_directory)
        os.close(rejected)
    return rejected_directory / quarantine_name


def quarantined_control_identity(quarantine_name: str) -> tuple[str, str]:
    """Return the canonical source name and typed error for a quarantine."""

    match = CONTROL_QUARANTINE_FILENAME_RE.fullmatch(quarantine_name)
    if match is None:
        raise ControlSchemaError("control quarantine filename is invalid")
    return match.group("control"), match.group("error")


def quarantine_receipt_filename(quarantine_name: str) -> str:
    """Return the collision-safe evidence sidecar for one exact quarantine."""

    quarantined_control_identity(quarantine_name)
    return f"{quarantine_name}.terminal.json"
