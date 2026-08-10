"""Single-flight and host-resource guard for foreground RSI campaigns.

The guard owns no provider credentials and launches no subprocesses.  It is a
small, reusable boundary that must be entered before scratch creation or model
spend.  A stable inode carries the advisory lock; a separate atomic state file
is the operator-facing projection so replacing it cannot accidentally drop the
lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any, Callable, Mapping
from uuid import uuid4


RUN_STATE_SCHEMA = "forge_lab.run_state.v1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_IDENTITY_FIELDS = (
    "schema",
    "run_id",
    "campaign_id",
    "request_id",
    "release_commit",
    "config_digest",
    "pid",
    "boot_id",
    "nonce",
    "started_at",
    "wall_seconds",
)


class RunGuardError(RuntimeError):
    """Stable, machine-readable refusal raised before any paid operation."""

    def __init__(self, code: str, message: str, *, detail: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class RunLimits:
    """Validated ceilings used by both supervised and scheduled runs."""

    generations: int
    children_per_generation: int
    tasks_per_split: int
    repeat_count: int
    total_tokens: int
    total_usd_micros: int
    total_requests: int
    wall_seconds: int

    def validate(self) -> "RunLimits":
        fields = {
            "generations": (self.generations, 1_000),
            "children_per_generation": (self.children_per_generation, 64),
            "tasks_per_split": (self.tasks_per_split, 2_000),
            "repeat_count": (self.repeat_count, 64),
            "total_tokens": (self.total_tokens, 1_000_000_000),
            "total_usd_micros": (self.total_usd_micros, 1_000_000_000_000),
            "total_requests": (self.total_requests, 1_000_000),
            "wall_seconds": (self.wall_seconds, 7 * 24 * 60 * 60),
        }
        for name, (value, maximum) in fields.items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise RunGuardError("INVALID_RUN_LIMIT", f"{name} must be a positive integer")
            if value > maximum:
                raise RunGuardError(
                    "RUN_LIMIT_TOO_LARGE",
                    f"{name} exceeds the harness safety maximum",
                    detail={"field": name, "value": value, "maximum": maximum},
                )
        planned_cells = (
            (1 + self.generations * self.children_per_generation)
            * self.tasks_per_split
            * self.repeat_count
        )
        if planned_cells > 2_000_000:
            raise RunGuardError(
                "RUN_SHAPE_TOO_LARGE",
                "planned paired evaluation cells exceed the harness maximum",
                detail={"planned_cells": planned_cells, "maximum": 2_000_000},
            )
        return self


@dataclass(frozen=True)
class HostResources:
    mem_available_bytes: int
    swap_free_bytes: int
    cpu_count: int
    load_1m: float


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _proc_meminfo(path: Path = Path("/proc/meminfo")) -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RunGuardError("HOST_RESOURCE_UNAVAILABLE", f"cannot read {path}: {exc}") from exc
    for row in rows:
        key, separator, raw = row.partition(":")
        if not separator:
            continue
        parts = raw.strip().split()
        if not parts:
            continue
        try:
            amount = int(parts[0])
        except ValueError:
            continue
        multiplier = 1024 if len(parts) > 1 and parts[1].lower() == "kb" else 1
        values[key] = amount * multiplier
    return values


def host_resources(
    *,
    meminfo_path: Path = Path("/proc/meminfo"),
    load_reader: Callable[[], tuple[float, float, float]] = os.getloadavg,
) -> HostResources:
    info = _proc_meminfo(meminfo_path)
    if "MemAvailable" not in info or "SwapFree" not in info:
        raise RunGuardError("HOST_RESOURCE_UNAVAILABLE", "MemAvailable and SwapFree are required")
    try:
        load = float(load_reader()[0])
    except (OSError, TypeError, ValueError) as exc:
        raise RunGuardError("HOST_RESOURCE_UNAVAILABLE", f"cannot read host load: {exc}") from exc
    return HostResources(
        mem_available_bytes=info["MemAvailable"],
        swap_free_bytes=info["SwapFree"],
        cpu_count=max(1, int(os.cpu_count() or 1)),
        load_1m=load,
    )


def require_host_resources(
    snapshot: HostResources,
    *,
    min_mem_available_bytes: int,
    min_swap_free_bytes: int,
    max_load_per_cpu: float = 2.0,
) -> None:
    requirements = (min_mem_available_bytes, min_swap_free_bytes)
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in requirements):
        raise RunGuardError("INVALID_HOST_CAP", "host byte floors must be non-negative integers")
    failures: list[dict[str, Any]] = []
    if snapshot.mem_available_bytes < min_mem_available_bytes:
        failures.append(
            {
                "resource": "mem_available_bytes",
                "observed": snapshot.mem_available_bytes,
                "required": min_mem_available_bytes,
            }
        )
    if snapshot.swap_free_bytes < min_swap_free_bytes:
        failures.append(
            {
                "resource": "swap_free_bytes",
                "observed": snapshot.swap_free_bytes,
                "required": min_swap_free_bytes,
            }
        )
    load_limit = snapshot.cpu_count * float(max_load_per_cpu)
    if snapshot.load_1m > load_limit:
        failures.append(
            {"resource": "load_1m", "observed": snapshot.load_1m, "maximum": load_limit}
        )
    if failures:
        raise RunGuardError(
            "HOST_RESOURCE_GATE_FAILED",
            "host resources do not satisfy the declared campaign floor",
            detail=failures,
        )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid4().hex}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _boot_id() -> str:
    try:
        value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    except OSError:
        value = "unavailable"
    return value or "unavailable"


def run_state_identity_digest(state: Mapping[str, Any]) -> str:
    """Digest only immutable run identity, never mutable status fields."""

    identity = {field: state.get(field) for field in _IDENTITY_FIELDS}
    return "sha256:" + sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class RunGuard:
    """Non-blocking single-flight lease with durable status and deadline."""

    def __init__(
        self,
        state_root: Path,
        *,
        campaign_id: str,
        request_id: str,
        release_commit: str,
        config_digest: str,
        wall_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not state_root.is_absolute():
            raise RunGuardError("STATE_ROOT_NOT_ABSOLUTE", "run state root must be absolute")
        for name, value in (("campaign_id", campaign_id), ("request_id", request_id)):
            if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
                raise RunGuardError("INVALID_RUN_ID", f"{name} is not filesystem/receipt safe")
        if not re.fullmatch(r"[0-9a-f]{40}", release_commit):
            raise RunGuardError("INVALID_RELEASE_ID", "release_commit must be a full Git SHA")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", config_digest):
            raise RunGuardError("INVALID_CONFIG_DIGEST", "config_digest must be sha256:<64 hex>")
        if not isinstance(wall_seconds, int) or isinstance(wall_seconds, bool) or wall_seconds <= 0:
            raise RunGuardError("INVALID_RUN_LIMIT", "wall_seconds must be positive")
        try:
            resolved_state = state_root.resolve(strict=True)
        except OSError as exc:
            raise RunGuardError(
                "STATE_ROOT_UNAVAILABLE", f"run state root cannot be resolved: {exc}"
            ) from exc
        self.root = resolved_state / ".dharma" / "forge_lab" / "run_guard"
        self.lock_path = self.root / "single-flight.lock"
        self.state_path = self.root / "run_state.json"
        self.campaign_id = campaign_id
        self.request_id = request_id
        self.release_commit = release_commit
        self.config_digest = config_digest
        self.wall_seconds = wall_seconds
        self.clock = clock
        self._started_mono: float | None = None
        self._descriptor: int | None = None
        self._state: dict[str, Any] | None = None

    @property
    def state(self) -> dict[str, Any]:
        if self._state is None:
            raise RunGuardError("RUN_GUARD_NOT_ENTERED", "run guard is not active")
        return dict(self._state)

    def __enter__(self) -> "RunGuard":
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root_stat = self.root.lstat()
        if (
            self.root.is_symlink()
            or not stat.S_ISDIR(root_stat.st_mode)
            or root_stat.st_uid != os.geteuid()
            or root_stat.st_mode & 0o077
        ):
            raise RunGuardError(
                "RUN_GUARD_PATH_UNTRUSTED",
                "run guard directory must be private, owned, and non-symlinked",
            )
        os.chmod(self.root, 0o700)
        try:
            descriptor = os.open(
                self.lock_path,
                os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
            )
        except OSError as exc:
            raise RunGuardError(
                "RUN_GUARD_LOCK_UNTRUSTED",
                f"single-flight lock cannot be opened safely: {exc}",
            ) from exc
        lock_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(lock_stat.st_mode)
            or lock_stat.st_uid != os.geteuid()
            or lock_stat.st_nlink != 1
            or lock_stat.st_mode & 0o077
        ):
            os.close(descriptor)
            raise RunGuardError(
                "RUN_GUARD_LOCK_UNTRUSTED",
                "single-flight lock must be a private owned regular file",
            )
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(descriptor)
            prior: dict[str, Any] = {}
            try:
                prior = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
            raise RunGuardError(
                "RUN_ALREADY_ACTIVE", "another governed RSI campaign holds the global lease", detail=prior
            ) from exc
        self._descriptor = descriptor
        self._started_mono = self.clock()
        nonce = uuid4().hex
        state = {
            "schema": RUN_STATE_SCHEMA,
            "run_id": f"{self.campaign_id}:{nonce}",
            "campaign_id": self.campaign_id,
            "request_id": self.request_id,
            "release_commit": self.release_commit,
            "config_digest": self.config_digest,
            "pid": os.getpid(),
            "boot_id": _boot_id(),
            "nonce": nonce,
            "status": "running",
            "started_at": _utc_now(),
            "updated_at": _utc_now(),
            "wall_seconds": self.wall_seconds,
            "elapsed_seconds": 0.0,
            "error": None,
        }
        state["identity_digest"] = run_state_identity_digest(state)
        self._state = state
        _atomic_json(self.state_path, state)
        return self

    def checkpoint(self) -> dict[str, Any]:
        if self._state is None or self._started_mono is None:
            raise RunGuardError("RUN_GUARD_NOT_ENTERED", "run guard is not active")
        elapsed = max(0.0, self.clock() - self._started_mono)
        if elapsed >= self.wall_seconds:
            self._transition("wall_timeout", error="hard campaign wall deadline reached")
            raise RunGuardError(
                "CAMPAIGN_WALL_DEADLINE_REACHED",
                "hard campaign wall deadline reached before dispatch",
                detail={"elapsed_seconds": elapsed, "wall_seconds": self.wall_seconds},
            )
        self._state["elapsed_seconds"] = round(elapsed, 3)
        self._state["updated_at"] = _utc_now()
        _atomic_json(self.state_path, self._state)
        return dict(self._state)

    def _transition(self, status: str, *, error: str | None = None) -> None:
        if self._state is None:
            return
        elapsed = 0.0 if self._started_mono is None else max(0.0, self.clock() - self._started_mono)
        self._state.update(
            {
                "status": status,
                "error": error,
                "elapsed_seconds": round(elapsed, 3),
                "updated_at": _utc_now(),
                "finished_at": _utc_now(),
            }
        )
        _atomic_json(self.state_path, self._state)

    def __exit__(self, exc_type: Any, exc: BaseException | None, _traceback: Any) -> bool:
        try:
            if exc is None:
                if self._started_mono is None:
                    self._transition("failed", error="run guard lost its monotonic start")
                    raise RunGuardError(
                        "RUN_GUARD_STATE_INVALID",
                        "run guard lost its monotonic start before terminal accounting",
                    )
                elapsed = max(0.0, self.clock() - self._started_mono)
                if elapsed >= self.wall_seconds:
                    self._transition("wall_timeout", error="hard campaign wall deadline reached")
                    raise RunGuardError(
                        "CAMPAIGN_WALL_DEADLINE_REACHED",
                        "hard campaign wall deadline reached before successful closeout",
                        detail={
                            "elapsed_seconds": elapsed,
                            "wall_seconds": self.wall_seconds,
                        },
                    )
                self._transition("succeeded")
            elif isinstance(exc, (KeyboardInterrupt, SystemExit)):
                self._transition("interrupted", error=type(exc).__name__)
            elif self._state and self._state.get("status") != "wall_timeout":
                self._transition("failed", error=f"{type(exc).__name__}:{exc}")
        finally:
            if self._descriptor is not None:
                fcntl.flock(self._descriptor, fcntl.LOCK_UN)
                os.close(self._descriptor)
                self._descriptor = None
        return False


__all__ = [
    "HostResources",
    "RUN_STATE_SCHEMA",
    "RunGuard",
    "RunGuardError",
    "RunLimits",
    "host_resources",
    "require_host_resources",
    "run_state_identity_digest",
]
