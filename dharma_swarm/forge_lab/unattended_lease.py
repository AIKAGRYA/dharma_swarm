"""Renewable singleton lease with monotonic fencing for unattended RSI."""

from __future__ import annotations

import fcntl
import os
import socket
import stat
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from uuid import uuid4

from dharma_swarm.forge_lab.state_io import atomic_json, validate_digest, validate_safe_id
from dharma_swarm.forge_lab.unattended_receipts import (
    UnattendedError,
    append_chain,
    read_chain,
)

LEASE_SCHEMA = "rsi_lab.fenced_lease_chain.v1"
DEFAULT_LEASE_TTL_SECONDS = 45
DEFAULT_RENEW_INTERVAL_SECONDS = 10
# Durable phases bracket a child with a 3,000-second hard maximum plus at most
# two 10-second termination waits.  Keep the progress fuse beyond that exact
# valid interval while the 10-second lease/systemd heartbeat still proves life.
DEFAULT_PROGRESS_TIMEOUT_SECONDS = 3_060


def _parse_time(value: object) -> datetime:
    try:
        instant = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise UnattendedError("LEASE_TIME_INVALID", str(value)) from exc
    if instant.tzinfo is None:
        raise UnattendedError("LEASE_TIME_INVALID", "lease timestamp lacks offset")
    return instant.astimezone(timezone.utc)


def _stamp(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _now() -> str:
    return _stamp(datetime.now(timezone.utc))


def _paths(control_root: Path) -> tuple[Path, Path, Path]:
    return (
        control_root / "manager_lease.json",
        control_root / "lease_events.jsonl",
        control_root / "lease_mutation.lock",
    )


@contextmanager
def _mutation_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise UnattendedError("LEASE_LOCK_UNSAFE", str(path)) from exc
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
            or info.st_nlink != 1
        ):
            raise UnattendedError("LEASE_LOCK_UNSAFE", str(path))
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _rows(control_root: Path) -> list[dict[str, Any]]:
    _projection, events, _lock = _paths(control_root)
    rows = read_chain(events, schema=LEASE_SCHEMA, digest_field="lease_event_digest")
    active: dict[str, Any] | None = None
    last_fence = 0
    for row in rows:
        event_at = _parse_time(row.get("at"))
        for field in ("run_id", "holder_id", "lease_id"):
            try:
                validate_safe_id(str(row.get(field) or ""), field=field)
            except ValueError as exc:
                raise UnattendedError("LEASE_CHAIN_SEMANTICS", f"invalid {field}") from exc
        fence_value = row.get("fence")
        if type(fence_value) is not int:
            raise UnattendedError("LEASE_CHAIN_SEMANTICS", "fence is not an integer")
        fence = fence_value
        if fence <= 0 or fence < last_fence:
            raise UnattendedError("LEASE_CHAIN_SEMANTICS", "non-monotonic fence")
        last_fence = max(last_fence, fence)
        kind = row.get("kind")
        if kind == "acquired":
            if active is not None:
                raise UnattendedError("LEASE_CHAIN_SEMANTICS", "acquire while active")
            active = row
        elif kind == "renewed":
            if active is None or row.get("lease_id") != active.get("lease_id") or fence != int(active["fence"]):
                raise UnattendedError("LEASE_CHAIN_SEMANTICS", "stale renewal")
            active = row
        elif kind in {"released", "expired"}:
            if active is None or row.get("lease_id") != active.get("lease_id") or fence != int(active["fence"]):
                raise UnattendedError("LEASE_CHAIN_SEMANTICS", "stale terminal lease event")
            active = None
        else:
            raise UnattendedError("LEASE_CHAIN_SEMANTICS", f"unknown event: {kind}")
        if kind in {"acquired", "renewed"}:
            ttl = row.get("ttl_seconds")
            if type(ttl) is not int or ttl < 6 or ttl > 300:
                raise UnattendedError("LEASE_CHAIN_SEMANTICS", "invalid lease TTL")
            heartbeat = _parse_time(row.get("heartbeat_at"))
            expires = _parse_time(row.get("expires_at"))
            if heartbeat != event_at or expires <= heartbeat:
                raise UnattendedError("LEASE_CHAIN_SEMANTICS", "invalid heartbeat/expiry interval")
        if kind == "renewed":
            progress = row.get("progress_sequence")
            if type(progress) is not int or progress < 0:
                raise UnattendedError("LEASE_CHAIN_SEMANTICS", "invalid progress sequence")
        if kind == "expired" and _parse_time(row.get("expired_at")) > event_at:
            raise UnattendedError("LEASE_CHAIN_SEMANTICS", "expiry event predates expiration")
        if kind == "released":
            try:
                validate_digest(str(row.get("terminal_receipt_digest") or ""))
            except ValueError as exc:
                raise UnattendedError(
                    "LEASE_CHAIN_SEMANTICS", "invalid terminal receipt digest"
                ) from exc
    return rows


def _active(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    active: dict[str, Any] | None = None
    for row in rows:
        if row["kind"] in {"acquired", "renewed"}:
            active = row
        else:
            active = None
    return active


def _project(control_root: Path, event: dict[str, Any] | None) -> None:
    projection, _events, _lock = _paths(control_root)
    atomic_json(
        projection,
        {
            "schema": "rsi_lab.fenced_lease_projection.v1",
            "active": event is not None,
            "lease": event,
            "source_event_digest": event.get("lease_event_digest") if event else None,
        },
    )


def acquire_lease(
    control_root: Path,
    *,
    run_id: str,
    holder_id: str,
    at: str | None = None,
    ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
) -> dict[str, Any]:
    run_id = validate_safe_id(run_id, field="run_id")
    holder_id = validate_safe_id(holder_id, field="holder_id")
    if type(ttl_seconds) is not int or ttl_seconds < 6 or ttl_seconds > 300:
        raise UnattendedError("LEASE_POLICY_INVALID", "ttl must be 6..300 seconds")
    now = _parse_time(at or _now())
    _projection, events_path, lock_path = _paths(control_root)
    with _mutation_lock(lock_path):
        rows = _rows(control_root)
        current = _active(rows)
        if current is not None and _parse_time(current["expires_at"]) <= now:
            append_chain(
                events_path,
                {
                    "kind": "expired",
                    "at": _stamp(now),
                    "run_id": current["run_id"],
                    "holder_id": current["holder_id"],
                    "lease_id": current["lease_id"],
                    "fence": current["fence"],
                    "expired_at": current["expires_at"],
                },
                schema=LEASE_SCHEMA,
                digest_field="lease_event_digest",
            )
            rows = _rows(control_root)
            current = None
        if current is not None:
            if current.get("run_id") == run_id and current.get("holder_id") == holder_id:
                return {**current, "idempotent": True}
            raise UnattendedError(
                "LEASE_HELD",
                f"fence={current['fence']} holder={current['holder_id']} expires={current['expires_at']}",
            )
        fence = max((int(row.get("fence") or 0) for row in rows), default=0) + 1
        event = append_chain(
            events_path,
            {
                "kind": "acquired",
                "at": _stamp(now),
                "run_id": run_id,
                "holder_id": holder_id,
                "lease_id": "lease-" + uuid4().hex,
                "fence": fence,
                "authority_mode": "active",
                "heartbeat_at": _stamp(now),
                "expires_at": _stamp(now + timedelta(seconds=ttl_seconds)),
                "ttl_seconds": ttl_seconds,
                "reclaimed_after_expiry": any(row.get("kind") == "expired" for row in rows[-1:]),
            },
            schema=LEASE_SCHEMA,
            digest_field="lease_event_digest",
        )
        _project(control_root, event)
        return event


def renew_lease(
    control_root: Path,
    *,
    lease_id: str,
    holder_id: str,
    fence: int,
    at: str | None = None,
    progress_sequence: int = 0,
    progress_phase: str = "running",
) -> dict[str, Any]:
    if type(fence) is not int or type(progress_sequence) is not int or progress_sequence < 0:
        raise UnattendedError("LEASE_POLICY_INVALID", "fence/progress must be integers")
    now = _parse_time(at or _now())
    _projection, events_path, lock_path = _paths(control_root)
    with _mutation_lock(lock_path):
        rows = _rows(control_root)
        current = _active(rows)
        if current is None:
            raise UnattendedError("LEASE_LOST", "no active lease")
        identity = (current.get("lease_id"), current.get("holder_id"), int(current.get("fence") or 0))
        if identity != (lease_id, holder_id, int(fence)):
            raise UnattendedError("LEASE_STALE_WRITER", f"expected active fence {identity[2]}")
        if _parse_time(current["expires_at"]) <= now:
            raise UnattendedError("LEASE_EXPIRED", current["expires_at"])
        ttl = int(current["ttl_seconds"])
        event = append_chain(
            events_path,
            {
                "kind": "renewed",
                "at": _stamp(now),
                "run_id": current["run_id"],
                "holder_id": holder_id,
                "lease_id": lease_id,
                "fence": int(fence),
                "authority_mode": current["authority_mode"],
                "heartbeat_at": _stamp(now),
                "expires_at": _stamp(now + timedelta(seconds=ttl)),
                "ttl_seconds": ttl,
                "progress_sequence": progress_sequence,
                "progress_phase": str(progress_phase)[:96],
            },
            schema=LEASE_SCHEMA,
            digest_field="lease_event_digest",
        )
        _project(control_root, event)
        return event


def release_lease(
    control_root: Path,
    *,
    lease_id: str,
    holder_id: str,
    fence: int,
    at: str | None = None,
    terminal_receipt_digest: str,
) -> dict[str, Any]:
    if type(fence) is not int:
        raise UnattendedError("LEASE_POLICY_INVALID", "fence must be an integer")
    now = _parse_time(at or _now())
    _projection, events_path, lock_path = _paths(control_root)
    with _mutation_lock(lock_path):
        rows = _rows(control_root)
        current = _active(rows)
        if current is None:
            prior = next(
                (row for row in reversed(rows) if row.get("kind") == "released" and row.get("lease_id") == lease_id),
                None,
            )
            if prior is not None:
                return prior
            raise UnattendedError("LEASE_LOST", "no active lease")
        identity = (current.get("lease_id"), current.get("holder_id"), int(current.get("fence") or 0))
        if identity != (lease_id, holder_id, int(fence)):
            raise UnattendedError("LEASE_STALE_WRITER", "release identity does not own current lease")
        event = append_chain(
            events_path,
            {
                "kind": "released",
                "at": _stamp(now),
                "run_id": current["run_id"],
                "holder_id": holder_id,
                "lease_id": lease_id,
                "fence": int(fence),
                "terminal_receipt_digest": terminal_receipt_digest,
            },
            schema=LEASE_SCHEMA,
            digest_field="lease_event_digest",
        )
        _project(control_root, None)
        return event


def lease_status(control_root: Path, *, at: str | None = None) -> dict[str, Any]:
    rows = _rows(control_root)
    current = _active(rows)
    now = _parse_time(at or _now())
    expired = bool(current and _parse_time(current["expires_at"]) <= now)
    return {
        "ready": current is None or not expired,
        "active": current is not None,
        "expired": expired,
        "lease": current,
        "fence_high_watermark": max((int(row.get("fence") or 0) for row in rows), default=0),
        "event_count": len(rows),
        "last_event_digest": rows[-1]["lease_event_digest"] if rows else None,
    }


def systemd_notify(message: str) -> bool:
    address = os.environ.get("NOTIFY_SOCKET", "")
    if not address:
        return False
    target = "\0" + address[1:] if address.startswith("@") else address
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.connect(target)
            client.sendall(message.encode("utf-8"))
        return True
    except OSError:
        return False


class LeaseHeartbeat:
    """Renew a lease and systemd watchdog without treating liveness as progress."""

    def __init__(
        self,
        control_root: Path,
        lease: dict[str, Any],
        *,
        interval_seconds: int = DEFAULT_RENEW_INTERVAL_SECONDS,
        progress_timeout_seconds: int = DEFAULT_PROGRESS_TIMEOUT_SECONDS,
        on_failure: Callable[[UnattendedError], None] | None = None,
    ):
        ttl = lease.get("ttl_seconds")
        if (
            type(ttl) is not int
            or type(interval_seconds) is not int
            or type(progress_timeout_seconds) is not int
            or interval_seconds <= 0
            or progress_timeout_seconds <= 0
            or interval_seconds * 3 > ttl
        ):
            raise UnattendedError("LEASE_POLICY_INVALID", "renewal must be no slower than ttl/3")
        self.control_root = control_root
        self.lease = lease
        self.interval_seconds = interval_seconds
        self.progress_timeout_seconds = progress_timeout_seconds
        self.on_failure = on_failure
        self.error: UnattendedError | None = None
        self.progress_sequence = 0
        self.progress_phase = "admitted"
        self._last_progress = time.monotonic()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="rsi-lease-heartbeat", daemon=True)

    def progress(self, phase: str) -> None:
        self.progress_sequence += 1
        self.progress_phase = str(phase)[:96]
        self._last_progress = time.monotonic()
        systemd_notify(f"STATUS=RSI {self.progress_phase} fence={self.lease['fence']}")

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                age = time.monotonic() - self._last_progress
                if age > self.progress_timeout_seconds:
                    raise UnattendedError(
                        "PROGRESS_WATCHDOG_STALE",
                        f"no durable phase progress for {round(age)} seconds",
                    )
                self.lease = renew_lease(
                    self.control_root,
                    lease_id=str(self.lease["lease_id"]),
                    holder_id=str(self.lease["holder_id"]),
                    fence=int(self.lease["fence"]),
                    progress_sequence=self.progress_sequence,
                    progress_phase=self.progress_phase,
                )
                systemd_notify(
                    f"WATCHDOG=1\nSTATUS=RSI {self.progress_phase} fence={self.lease['fence']}"
                )
            except UnattendedError as exc:
                self.error = exc
                if self.on_failure is not None:
                    self.on_failure(exc)
                return

    def __enter__(self) -> "LeaseHeartbeat":
        systemd_notify(f"READY=1\nSTATUS=RSI admitted fence={self.lease['fence']}")
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=max(1, self.interval_seconds + 1))
        systemd_notify("STOPPING=1\nSTATUS=RSI terminal closeout")


__all__ = [
    "DEFAULT_LEASE_TTL_SECONDS",
    "DEFAULT_PROGRESS_TIMEOUT_SECONDS",
    "DEFAULT_RENEW_INTERVAL_SECONDS",
    "LEASE_SCHEMA",
    "LeaseHeartbeat",
    "acquire_lease",
    "lease_status",
    "release_lease",
    "renew_lease",
    "systemd_notify",
]
