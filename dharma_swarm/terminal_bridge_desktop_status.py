"""Optional, bounded desktop observation of the existing terminal bridge.

The bridge owns execution. This file supplies no actions or permission grants.
Callbacks only project allowlisted metadata in memory; one async task coalesces
writes off the event loop. Readers must retain the availability envelope.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import errno
import fcntl
import json
import logging
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping
import uuid

STATUS_SCHEMA = "dharma.helm.desktop_status.v1"
STATUS_FILE_ENV = "DHARMA_HELM_DESKTOP_STATUS_FILE"
MAX_STATUS_BYTES = 64 * 1024
FLUSH_INTERVAL_SECONDS = 0.025
HEARTBEAT_SECONDS = 1.0
EXPIRY_SECONDS = 3.0
_PHASES = frozenset({"starting", "idle", "running", "cancelling", "closed"})
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}\Z")
_SOCKET = re.compile(r"CODEX_MANAGED_[A-Za-z0-9_\-]{1,100}\Z")
_SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{0,127}\Z")
_LOGGER = logging.getLogger(__name__)


def _identifier(value: object) -> str | None:
    return value if isinstance(value, str) and _IDENTIFIER.fullmatch(value) else None


def _seat(socket: object, session: object) -> dict[str, str | None]:
    if socket is None and session is None:
        return {"tmux_socket": None, "tmux_session": None}
    if not (
        isinstance(socket, str) and _SOCKET.fullmatch(socket)
        and isinstance(session, str) and _SESSION.fullmatch(session)
    ):
        raise ValueError("invalid_managed_seat")
    return {"tmux_socket": socket, "tmux_session": session}


def _parent_fd(path: Path, *, create: bool = False) -> int:
    """Walk using directory descriptors so neither parent nor leaf follows links."""

    if not path.is_absolute() or ".." in path.parts or not path.name:
        raise ValueError("absolute_status_path_required")
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parent.parts[1:]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _private_regular(info: os.stat_result) -> None:
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("status_not_regular_file")
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("status_not_private")


async def _offload(operation: Any, *args: Any) -> Any:
    """Join file I/O before cancellation can release its directory or lock."""

    pending = asyncio.create_task(asyncio.to_thread(operation, *args))
    try:
        return await asyncio.shield(pending)
    except asyncio.CancelledError:
        try:
            await pending
        finally:
            raise


def _utc_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid_timestamp") from None
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp_not_utc")
    return parsed


def _exact_fields(value: object, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("invalid_snapshot_shape")
    return value


def validate_snapshot(value: object, *, now: datetime) -> dict[str, Any]:
    """Validate the v1 allowlist; no unknown payload can pass through to a UI."""

    snapshot = _exact_fields(value, {
        "schema_version", "owner", "sequence", "observed_at", "expires_at",
        "phase", "session_id", "request_id", "route", "pending_approvals",
        "repo_root", "seat", "authority",
    })
    if snapshot["schema_version"] != STATUS_SCHEMA or snapshot["authority"] != "observation_only":
        raise ValueError("invalid_status_authority")
    owner = _exact_fields(snapshot["owner"], {"id", "pid", "epoch"})
    if not _identifier(owner["id"]) or not _identifier(owner["epoch"]):
        raise ValueError("invalid_owner")
    if type(owner["pid"]) is not int or not 0 < owner["pid"] < 2**31:
        raise ValueError("invalid_owner_pid")
    if type(snapshot["sequence"]) is not int or not 0 < snapshot["sequence"] < 2**63:
        raise ValueError("invalid_sequence")
    if snapshot["phase"] not in _PHASES:
        raise ValueError("invalid_phase")
    route = _exact_fields(snapshot["route"], {"requested_provider_id", "requested_model_id"})
    for field in (snapshot["session_id"], snapshot["request_id"], *route.values()):
        if field is not None and _identifier(field) is None:
            raise ValueError("invalid_identifier")
    pending = snapshot["pending_approvals"]
    if pending is not None and (type(pending) is not int or not 0 <= pending < 2**31):
        raise ValueError("invalid_approval_count")
    repo = snapshot["repo_root"]
    if not isinstance(repo, str) or len(repo) > 4096 or not repo.startswith("/") or any(ord(c) < 32 for c in repo):
        raise ValueError("invalid_repo_root")
    seat = _exact_fields(snapshot["seat"], {"tmux_socket", "tmux_session"})
    _seat(seat["tmux_socket"], seat["tmux_session"])
    observed = _utc_timestamp(snapshot["observed_at"])
    expires = _utc_timestamp(snapshot["expires_at"])
    if observed > now:
        raise ValueError("future_observation")
    if not 0 < (expires - observed).total_seconds() <= EXPIRY_SECONDS:
        raise ValueError("invalid_expiry")
    return snapshot


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def read_status(path: Path, now: datetime | None = None) -> dict[str, Any]:
    """Read at most 64 KiB, without creating files or contacting a service."""

    def result(availability: str, reason: str, snapshot: object = None) -> dict[str, Any]:
        return {"availability": availability, "reason": reason, "snapshot": snapshot}

    if now is not None and now.utcoffset() is None:
        return result("invalid", "naive_clock")
    try:
        parent = _parent_fd(path)
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        finally:
            os.close(parent)
        try:
            info = os.fstat(fd)
            _private_regular(info)
            if info.st_size > MAX_STATUS_BYTES:
                return result("invalid", "status_too_large")
            raw = os.read(fd, MAX_STATUS_BYTES + 1)
        finally:
            os.close(fd)
        if len(raw) > MAX_STATUS_BYTES:
            return result("invalid", "status_too_large")
        now = now or datetime.now(timezone.utc)
        snapshot = validate_snapshot(json.loads(raw, object_pairs_hook=_unique_object), now=now)
    except FileNotFoundError:
        return result("unavailable", "status_missing")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        # Validation reasons are constants; JSON messages can include payloads.
        reason = str(exc) if type(exc) is ValueError else "invalid_status_json"
        return result("invalid", reason)
    except OSError as exc:
        return result("invalid" if exc.errno in {errno.ELOOP, errno.ENOTDIR} else "unavailable", "status_unreadable")
    if snapshot["phase"] == "closed":
        return result("stale", "owner_closed", snapshot)
    if _utc_timestamp(snapshot["expires_at"]) <= now:
        return result("stale", "status_expired", snapshot)
    try:
        os.kill(snapshot["owner"]["pid"], 0)
    except ProcessLookupError:
        return result("stale", "owner_not_running", snapshot)
    except PermissionError:
        return result("unavailable", "owner_not_verifiable", snapshot)
    except OSError:
        return result("unavailable", "owner_not_verifiable", snapshot)
    return result("fresh", "owner_observed", snapshot)


class DesktopStatusWriter:
    """One owner, one coalescing task, and an advisory lock held for its lifetime."""

    def __init__(self, path: Path, *, owner_id: str, owner_pid: int, repo_root: Path,
                 seat: Mapping[str, str | None] | None = None) -> None:
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("absolute_status_path_required")
        self.path = path
        self._state: dict[str, Any] = {
            "schema_version": STATUS_SCHEMA,
            "owner": {"id": owner_id, "pid": owner_pid, "epoch": uuid.uuid4().hex},
            "phase": "starting", "session_id": None, "request_id": None,
            "route": {"requested_provider_id": None, "requested_model_id": None},
            "pending_approvals": None,
            "repo_root": str(repo_root),
            "seat": _seat((seat or {}).get("tmux_socket"), (seat or {}).get("tmux_session")),
            "authority": "observation_only",
        }
        self._sequence = 0
        self._parent: int | None = None
        self._lock: int | None = None
        self._lock_name = f".{path.name}.lock"
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._closing = False

    @classmethod
    def from_environment(cls, *, owner_id: str, owner_pid: int, repo_root: Path) -> DesktopStatusWriter | None:
        configured = os.environ.get(STATUS_FILE_ENV)
        if not configured:
            return None
        return cls(Path(configured), owner_id=owner_id, owner_pid=owner_pid,
                   repo_root=repo_root, seat={
                       "tmux_socket": os.environ.get("DHARMA_TERMINAL_TMUX_SOCKET") or None,
                       "tmux_session": os.environ.get("DHARMA_TERMINAL_TMUX_SESSION") or None,
                   })

    def _acquire(self) -> None:
        self._parent = _parent_fd(self.path, create=True)
        try:
            self._lock = os.open(self._lock_name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 0o600, dir_fd=self._parent)
            _private_regular(os.fstat(self._lock))
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self._release()
            raise

    def _release(self) -> None:
        # Never unlink the lock: another owner may already have its inode open.
        if self._lock is not None:
            os.close(self._lock)
            self._lock = None
        if self._parent is not None:
            os.close(self._parent)
            self._parent = None

    def _write(self, snapshot: dict[str, Any]) -> None:
        assert self._parent is not None and self._lock is not None
        actual = os.stat(self._lock_name, dir_fd=self._parent, follow_symlinks=False)
        held = os.fstat(self._lock)
        if (actual.st_dev, actual.st_ino) != (held.st_dev, held.st_ino):
            raise ValueError("status_lock_replaced")
        try:
            _private_regular(os.stat(self.path.name, dir_fd=self._parent, follow_symlinks=False))
        except FileNotFoundError:
            pass
        raw = json.dumps(snapshot, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        if len(raw) > MAX_STATUS_BYTES:
            raise ValueError("status_too_large")
        temporary = f".{self.path.name}.{uuid.uuid4().hex}.tmp"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self._parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
            os.replace(temporary, self.path.name, src_dir_fd=self._parent, dst_dir_fd=self._parent)
        finally:
            try:
                os.unlink(temporary, dir_fd=self._parent)
            except FileNotFoundError:
                pass

    async def _publish(self) -> None:
        now = datetime.now(timezone.utc)
        self._sequence += 1
        snapshot = {**self._state, "sequence": self._sequence,
                    "observed_at": now.isoformat(),
                    "expires_at": (now + timedelta(seconds=EXPIRY_SECONDS)).isoformat()}
        validate_snapshot(snapshot, now=now)
        await _offload(self._write, snapshot)

    async def start(self) -> None:
        if self._task is not None or self._closing:
            raise RuntimeError("desktop_status_already_started")
        try:
            await _offload(self._acquire)
            await self._publish()
        except BaseException:
            await _offload(self._release)
            raise
        self._task = asyncio.create_task(self._run(), name="helm-desktop-status")

    async def _run(self) -> None:
        try:
            while True:
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=HEARTBEAT_SECONDS)
                    if not self._closing:
                        await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
                except asyncio.TimeoutError:
                    pass
                self._wake.clear()
                await self._publish()
                if self._closing:
                    return
        except (OSError, ValueError):
            _LOGGER.warning("Helm desktop status disabled after a snapshot write failure")
        finally:
            await _offload(self._release)

    def _update(self, **fields: Any) -> None:
        if not self._closing and any(self._state[key] != value for key, value in fields.items()):
            self._state.update(fields)
            self._wake.set()

    def begin_session(self, *, session_id: str, request_id: str,
                      requested_provider_id: str, requested_model_id: str) -> None:
        self._update(phase="starting", session_id=_identifier(session_id), request_id=_identifier(request_id),
                     route={"requested_provider_id": _identifier(requested_provider_id),
                            "requested_model_id": _identifier(requested_model_id)})

    def cancel_session(self) -> None:
        if self._state["session_id"] is not None:
            self._update(phase="cancelling")

    def clear_session(self) -> None:
        self._update(phase="idle", session_id=None, request_id=None)

    def observe(self, event: Mapping[str, Any]) -> None:
        """Ignore narration, tool payloads, permission history pages, and served IDs."""

        kind = event.get("type")
        if not isinstance(kind, str):
            return
        if kind == "bridge.ready" and self._state["phase"] == "starting" and self._state["session_id"] is None:
            self._update(phase="idle")
        elif kind in {"session.ack", "session_start"}:
            if (self._state["phase"] == "starting" and self._state["session_id"] is not None
                    and event.get("session_id") == self._state["session_id"]
                    and _identifier(event.get("request_id")) == self._state["request_id"]):
                self._update(phase="running")
        elif kind == "handshake.result" and self._state["session_id"] is None:
            self._update(route={"requested_provider_id": _identifier(event.get("default_provider")),
                                "requested_model_id": _identifier(event.get("default_model"))})

    async def close(self) -> None:
        if self._task is None:
            return
        self._closing = True
        self._state.update(phase="closed", session_id=None, request_id=None)
        self._wake.set()
        await asyncio.shield(self._task)


async def start_desktop_status(*, owner_id: str, owner_pid: int, repo_root: Path) -> DesktopStatusWriter | None:
    """An optional observer failure must not prevent the bridge from serving."""

    try:
        writer = DesktopStatusWriter.from_environment(owner_id=owner_id, owner_pid=owner_pid, repo_root=repo_root)
        if writer is not None:
            await writer.start()
        return writer
    except (OSError, ValueError):
        _LOGGER.warning("Helm desktop status unavailable; bridge continues without desktop projection")
        return None
