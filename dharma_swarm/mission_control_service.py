"""Single-writer service loop and derived read model for mission campaigns.

The JSON projection in this module is deliberately not a ledger.  It is one
atomically replaced view of the canonical TaskBoard and RuntimeStateStore
records assembled by :class:`CampaignSupervisor`.
"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
import tempfile
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.mission_control_campaign import (
    CampaignSnapshot,
    CampaignSupervisor,
)
from dharma_swarm.mission_control_auto_verifier import (
    AutomaticCandidateVerifier,
    CandidateReconcileOutcome,
)

CAMPAIGN_PROJECTION_SCHEMA_VERSION = "dharma.mission_control.read_model.v1"
CAMPAIGN_WRITER_IDENTITY_SCHEMA_VERSION = "dharma.mission_control.writer.v1"
MAX_CAMPAIGN_PROJECTION_BYTES = 32 * 1024 * 1024


class CampaignWriterBusy(RuntimeError):
    """Raised immediately when another campaign writer owns the lock."""


class CampaignProjectionError(RuntimeError):
    """Raised when the derived projection cannot be decoded safely."""


@dataclass(frozen=True, slots=True)
class CampaignPaths:
    """Pairwise-distinct filesystem surfaces for one campaign process."""

    lock_path: Path
    control_gate_path: Path
    projection_path: Path
    log_path: Path

    def __post_init__(self) -> None:
        resolved = {
            path.expanduser().resolve(strict=False)
            for path in (
                self.lock_path,
                self.control_gate_path,
                self.projection_path,
                self.log_path,
            )
        }
        if len(resolved) != 4:
            raise ValueError(
                "campaign lock, control, projection, and log paths must differ"
            )


@dataclass(frozen=True, slots=True)
class CampaignServiceResult:
    status: str
    completed_cycles: int
    snapshot: CampaignSnapshot
    lock_path: Path
    control_gate_path: Path
    projection_path: Path


class CampaignWriterLock:
    """One nonblocking advisory writer lock held by an open file descriptor."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path).expanduser()
        self._fd: int | None = None

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self) -> None:
        if self._fd is not None:
            raise RuntimeError("campaign writer lock is already held")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.ftruncate(fd, 0)
            os.fsync(fd)
        except BlockingIOError as exc:
            os.close(fd)
            raise CampaignWriterBusy(
                f"campaign writer lock is already held: {self.path}"
            ) from exc
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def bind(self, snapshot: CampaignSnapshot) -> dict[str, Any]:
        if self._fd is None:
            raise RuntimeError("campaign writer identity requires a held lock")
        payload = {
            "schema_version": CAMPAIGN_WRITER_IDENTITY_SCHEMA_VERSION,
            "mission_id": snapshot.mission_id,
            "session_id": snapshot.session_id,
            "config_digest": snapshot.config_digest,
            "generation": snapshot.generation,
        }
        encoded = (
            json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"
        ).encode()
        os.lseek(self._fd, 0, os.SEEK_SET)
        os.ftruncate(self._fd, 0)
        written = 0
        while written < len(encoded):
            written += os.write(self._fd, encoded[written:])
        os.fsync(self._fd)
        return payload

    def __enter__(self) -> CampaignWriterLock:
        self.acquire()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()


class CampaignControlGate:
    """Short-lived cross-process fence serializing control and owner effects."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path).expanduser()
        self._fd: int | None = None

    def acquire(self) -> None:
        if self._fd is not None:
            raise RuntimeError("campaign control gate is already held")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd

    def try_acquire(self) -> bool:
        """Attempt ownership without leaving an uncancellable blocking thread."""
        if self._fd is not None:
            raise RuntimeError("campaign control gate is already held")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return False
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        return True

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    async def __aenter__(self) -> CampaignControlGate:
        while not self.try_acquire():
            await asyncio.sleep(0.01)
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.release()


def writer_lock_is_held(path: Path | str) -> bool:
    """Probe current lock ownership without trusting a PID or status file."""
    lock_path = Path(path).expanduser()
    try:
        fd = os.open(lock_path, os.O_RDWR)
    except FileNotFoundError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def read_writer_lock_identity(path: Path | str) -> dict[str, Any] | None:
    """Read the identity bound to a held writer inode; malformed data is absent."""
    try:
        raw = Path(path).expanduser().read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "mission_id",
        "session_id",
        "config_digest",
        "generation",
    }:
        return None
    if payload.get("schema_version") != CAMPAIGN_WRITER_IDENTITY_SCHEMA_VERSION:
        return None
    if not all(
        isinstance(payload.get(field), str) and bool(payload[field])
        for field in ("mission_id", "session_id", "config_digest")
    ):
        return None
    generation = payload.get("generation")
    if (
        isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 1
    ):
        return None
    return payload


def _projection_content_digest(payload: Mapping[str, Any]) -> str:
    canonical = dict(payload)
    canonical.pop("projection_content_digest", None)
    encoded = json.dumps(
        canonical,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _projection_payload(snapshot: CampaignSnapshot) -> dict[str, Any]:
    freshness = snapshot.freshness_seconds
    if (
        isinstance(freshness, bool)
        or not isinstance(freshness, (int, float))
        or not 0 < freshness <= 3600
    ):
        raise CampaignProjectionError("projection freshness must be from 0 to 3600")
    fresh_until = (
        snapshot.latest_cycle_at + timedelta(seconds=freshness)
        if snapshot.latest_cycle_at is not None
        else None
    )
    payload = {
        **snapshot.to_dict(),
        "projection_schema_version": CAMPAIGN_PROJECTION_SCHEMA_VERSION,
        "projection_kind": "derived_read_model",
        "canonical_state_copied": False,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "fresh_until": fresh_until.isoformat() if fresh_until is not None else None,
    }
    sequence = payload.get("cycle_sequence")
    if (
        isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or sequence < 0
        or (sequence == 0) != (snapshot.latest_cycle_at is None)
    ):
        raise CampaignProjectionError("campaign cycle sequence is invalid")
    payload["projection_content_digest"] = _projection_content_digest(payload)
    return payload


def publish_campaign_projection(
    snapshot: CampaignSnapshot,
    path: Path | str,
) -> dict[str, Any]:
    """Atomically replace the sole JSON read model for one campaign."""
    projection_path = Path(path).expanduser()
    projection_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _projection_payload(snapshot)
    previous = read_campaign_projection(projection_path)
    if previous is not None and all(
        previous.get(field) == payload.get(field)
        for field in ("mission_id", "config_digest", "generation", "cycle_sequence")
    ):
        if "mission_snapshot" not in previous:
            raise CampaignProjectionError(
                "equal-position projection has no mission snapshot"
            )
        payload["mission_snapshot"] = previous["mission_snapshot"]
        payload["projection_content_digest"] = _projection_content_digest(payload)
    encoded = (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    if len(encoded) > MAX_CAMPAIGN_PROJECTION_BYTES:
        raise CampaignProjectionError("campaign projection exceeds 32 MiB")
    fd, temporary_name = tempfile.mkstemp(
        dir=projection_path.parent,
        prefix=f".{projection_path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, projection_path)
        directory_fd = os.open(projection_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return payload


def read_campaign_projection(path: Path | str) -> dict[str, Any] | None:
    """Read the derived JSON view without opening either canonical database."""
    projection_path = Path(path).expanduser()
    try:
        raw = projection_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CampaignProjectionError(
            f"campaign projection is not valid JSON: {projection_path}"
        ) from exc
    if not isinstance(payload, dict):
        raise CampaignProjectionError("campaign projection must be a JSON object")
    if payload.get("projection_schema_version") != CAMPAIGN_PROJECTION_SCHEMA_VERSION:
        raise CampaignProjectionError("campaign projection schema is unsupported")
    try:
        expected_digest = _projection_content_digest(payload)
    except (TypeError, ValueError) as exc:
        raise CampaignProjectionError(
            "campaign projection is not canonical JSON"
        ) from exc
    if payload.get("projection_content_digest") != expected_digest:
        raise CampaignProjectionError("campaign projection content digest is invalid")
    return payload


def projection_confirms_start(
    projection: Mapping[str, Any] | None,
    *,
    requested_at: datetime,
    writer_lock_held: bool,
    writer_lock_identity: Mapping[str, Any] | None,
    expected_mission_id: str,
    expected_config_digest: str,
    expected_generation: int | None,
) -> bool:
    """Confirm a start from a fresh cycle plus a separately probed live lock."""
    if requested_at.tzinfo is None:
        raise ValueError("requested_at must be timezone-aware")
    if not writer_lock_held or projection is None:
        return False
    if (
        projection.get("projection_schema_version")
        != CAMPAIGN_PROJECTION_SCHEMA_VERSION
        or projection.get("writer_lock_held") is not True
        or projection.get("supervisor_state") != "running"
        or projection.get("mission_id") != expected_mission_id
        or projection.get("config_digest") != expected_config_digest
        or writer_lock_identity is None
        or writer_lock_identity.get("schema_version")
        != CAMPAIGN_WRITER_IDENTITY_SCHEMA_VERSION
        or writer_lock_identity.get("mission_id") != expected_mission_id
        or writer_lock_identity.get("session_id") != projection.get("session_id")
        or writer_lock_identity.get("config_digest") != expected_config_digest
        or writer_lock_identity.get("generation") != projection.get("generation")
        or (
            expected_generation is not None
            and projection.get("generation") != expected_generation
        )
    ):
        return False
    raw_latest = projection.get("latest_cycle_at")
    if not isinstance(raw_latest, str):
        return False
    try:
        latest = datetime.fromisoformat(raw_latest)
    except ValueError:
        return False
    if latest.tzinfo is None:
        return False
    return latest.astimezone(timezone.utc) >= requested_at.astimezone(timezone.utc)


def materialize_projection_liveness(
    projection: Mapping[str, Any],
    *,
    now: datetime,
    writer_lock_held: bool,
    writer_lock_identity: Mapping[str, Any] | None,
    expected_mission_id: str,
    expected_config_digest: str | None = None,
) -> dict[str, Any]:
    """Recompute ephemeral process truth from the read model and live lock."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    identity_matches = projection.get("mission_id") == expected_mission_id and (
        expected_config_digest is None
        or projection.get("config_digest") == expected_config_digest
    )
    raw_fresh_until = projection.get("fresh_until")
    try:
        fresh_until = (
            datetime.fromisoformat(raw_fresh_until)
            if isinstance(raw_fresh_until, str)
            else None
        )
    except ValueError:
        fresh_until = None
    fresh = bool(
        fresh_until is not None
        and fresh_until.tzinfo is not None
        and now.astimezone(timezone.utc) <= fresh_until.astimezone(timezone.utc)
    )
    campaign_stopped = (
        projection.get("campaign_status") == "stopped"
        or projection.get("supervisor_state") == "stopped"
    )
    embedded_running = (
        projection.get("supervisor_state") == "running"
        and projection.get("writer_lock_held") is True
    )
    lock_identity_matches = bool(
        writer_lock_identity is not None
        and writer_lock_identity.get("schema_version")
        == CAMPAIGN_WRITER_IDENTITY_SCHEMA_VERSION
        and writer_lock_identity.get("mission_id") == projection.get("mission_id")
        and writer_lock_identity.get("session_id") == projection.get("session_id")
        and writer_lock_identity.get("config_digest") == projection.get("config_digest")
        and writer_lock_identity.get("generation") == projection.get("generation")
    )
    if not identity_matches:
        state = "foreign_projection"
    elif campaign_stopped:
        state = "stopped"
    elif not writer_lock_held:
        state = "not_running"
    elif not embedded_running or not lock_identity_matches:
        state = "lock_identity_mismatch"
    elif not fresh:
        state = "stale_lock"
    else:
        state = "running"
    return {
        **dict(projection),
        "status": state,
        "supervisor_state": state,
        "writer_lock_held": writer_lock_held,
        "proves_process_liveness": state == "running",
        "projection_identity_matches": identity_matches,
        "writer_lock_identity_matches": lock_identity_matches,
        "projection_cycle_fresh": fresh,
    }


def _terminal_service_snapshot(snapshot: CampaignSnapshot) -> CampaignSnapshot:
    return replace(
        snapshot,
        supervisor_state=(
            "stopped" if snapshot.campaign_status == "stopped" else "not_running"
        ),
        writer_lock_held=False,
        observed_at=datetime.now(timezone.utc),
        proves_process_liveness=False,
    )


class CampaignService:
    """Run campaign cycles while holding one nonblocking writer lock."""

    def __init__(
        self,
        supervisor: CampaignSupervisor,
        *,
        lock_path: Path | str,
        projection_path: Path | str,
        control_gate_path: Path | str | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        writer_lock: CampaignWriterLock | None = None,
        candidate_verifier: AutomaticCandidateVerifier | None = None,
        activation_barrier: Callable[[], Awaitable[None]] | None = None,
        operator_control_reconciler: Any | None = None,
    ) -> None:
        self._supervisor = supervisor
        self.lock_path = Path(lock_path).expanduser()
        self.projection_path = Path(projection_path).expanduser()
        self.control_gate_path = Path(
            control_gate_path or f"{self.lock_path}.control"
        ).expanduser()
        resolved_paths = {
            path.resolve(strict=False)
            for path in (self.lock_path, self.control_gate_path, self.projection_path)
        }
        if len(resolved_paths) != 3:
            raise ValueError(
                "lock, control gate, and projection paths must be different"
            )
        self._sleep = sleep
        self._control_gate = CampaignControlGate(self.control_gate_path)
        self._lock = writer_lock or CampaignWriterLock(self.lock_path)
        self._candidate_verifier = candidate_verifier
        self._activation_barrier = activation_barrier
        self._operator_control_reconciler = operator_control_reconciler
        if self._lock.path.absolute() != self.lock_path.absolute():
            raise ValueError("writer_lock must own lock_path")
        self._running = False

    async def _reconcile_operator_controls(self) -> None:
        if self._operator_control_reconciler is None:
            return
        from dharma_swarm.mission_control_operator_control import (  # noqa: PLC0415
            SupervisorControlCallbacks,
        )

        await self._operator_control_reconciler.reconcile_once(
            SupervisorControlCallbacks(apply=self._supervisor.apply_operator_control)
        )

    async def _effects_enabled(self) -> bool:
        probe = getattr(self._supervisor, "effects_enabled", None)
        if probe is None:
            return True
        enabled = await probe()
        if not isinstance(enabled, bool):
            raise RuntimeError(
                "campaign effects-enabled probe returned a foreign value"
            )
        return enabled

    async def _begin_candidate_reconcile(
        self,
        snapshot: CampaignSnapshot,
    ) -> tuple[
        CandidateReconcileOutcome | None,
        asyncio.Task[CandidateReconcileOutcome] | None,
    ]:
        """Reach durable verifier intent/effect submission while fenced by control."""
        if self._candidate_verifier is None or not snapshot.candidate_task_ids:
            return None, None
        ready = asyncio.Event()
        task = asyncio.create_task(
            self._candidate_verifier.reconcile(snapshot, effect_ready=ready.set)
        )
        ready_waiter = asyncio.create_task(ready.wait())
        try:
            done, _ = await asyncio.wait(
                (task, ready_waiter),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if task in done:
                return task.result(), None
            return None, task
        finally:
            if not ready_waiter.done():
                ready_waiter.cancel()
            try:
                await ready_waiter
            except asyncio.CancelledError:
                pass

    @property
    def writer_lock_held(self) -> bool:
        return self._lock.held

    async def run(
        self,
        *,
        max_cycles: int | None = None,
        start_campaign: bool = True,
    ) -> CampaignServiceResult:
        if max_cycles is not None and (
            isinstance(max_cycles, bool)
            or not isinstance(max_cycles, int)
            or max_cycles < 1
        ):
            raise ValueError("max_cycles must be a positive integer or None")
        if self._running:
            raise RuntimeError("campaign service is already running")
        self._running = True
        if not self._lock.held:
            try:
                self._lock.acquire()
            except BaseException:
                self._running = False
                raise
        completed_cycles = 0
        snapshot: CampaignSnapshot | None = None
        terminal_snapshot: CampaignSnapshot | None = None
        try:
            if start_campaign:
                async with self._control_gate:
                    await self._supervisor.start()
            while max_cycles is None or completed_cycles < max_cycles:
                outcome: CandidateReconcileOutcome | None = None
                pending_verifier: asyncio.Task[CandidateReconcileOutcome] | None = None
                async with self._control_gate:
                    await self._reconcile_operator_controls()
                    effects_enabled = await self._effects_enabled()
                    if effects_enabled and self._activation_barrier is not None:
                        await self._activation_barrier()
                    snapshot = await self._supervisor.cycle(writer_lock_held=True)
                    if effects_enabled and snapshot.campaign_status == "active":
                        (
                            outcome,
                            pending_verifier,
                        ) = await self._begin_candidate_reconcile(snapshot)
                if pending_verifier is not None:
                    outcome = await pending_verifier
                if outcome is not None:
                    reconcile_errors = (
                        snapshot.errors
                        + (
                            f"verify:{outcome.task_id}:{outcome.status}:{outcome.error}",
                        )
                        if outcome.error
                        else snapshot.errors
                    )
                    if outcome.acceptance is not None:
                        async with self._control_gate:
                            try:
                                await self._supervisor.accept(outcome.acceptance)
                            except Exception as exc:
                                reconcile_errors += (
                                    f"accept:{outcome.task_id}:{type(exc).__name__}:{exc}",
                                )
                            snapshot = await self._supervisor.status(
                                writer_lock_held=True
                            )
                    snapshot = replace(snapshot, errors=reconcile_errors)
                self._lock.bind(snapshot)
                publish_campaign_projection(snapshot, self.projection_path)
                completed_cycles += 1
                if snapshot.campaign_status == "stopped":
                    break
                if max_cycles is None or completed_cycles < max_cycles:
                    await self._sleep(self._supervisor.config.cycle_interval_seconds)
            if snapshot is None:  # pragma: no cover - guarded by validation
                raise RuntimeError("campaign service completed without a cycle")
            terminal_snapshot = _terminal_service_snapshot(snapshot)
            return CampaignServiceResult(
                status=(
                    "stopped" if snapshot.campaign_status == "stopped" else "completed"
                ),
                completed_cycles=completed_cycles,
                snapshot=terminal_snapshot,
                lock_path=self.lock_path,
                control_gate_path=self.control_gate_path,
                projection_path=self.projection_path,
            )
        finally:
            try:
                if snapshot is not None:
                    publish_campaign_projection(
                        terminal_snapshot or _terminal_service_snapshot(snapshot),
                        self.projection_path,
                    )
            finally:
                self._lock.release()
                self._running = False


__all__ = [
    "CAMPAIGN_PROJECTION_SCHEMA_VERSION",
    "CAMPAIGN_WRITER_IDENTITY_SCHEMA_VERSION",
    "MAX_CAMPAIGN_PROJECTION_BYTES",
    "CampaignProjectionError",
    "CampaignPaths",
    "CampaignControlGate",
    "CampaignService",
    "CampaignServiceResult",
    "CampaignWriterBusy",
    "CampaignWriterLock",
    "projection_confirms_start",
    "materialize_projection_liveness",
    "publish_campaign_projection",
    "read_campaign_projection",
    "read_writer_lock_identity",
    "writer_lock_is_held",
]
