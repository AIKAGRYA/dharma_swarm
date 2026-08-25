#!/usr/bin/env python3
"""Bounded, allowlisted memory-pressure response for small Linux hosts.

The guard observes Linux's global ``MemAvailable`` metric.  It may restart at
most one explicitly configured systemd service or Docker container per cycle.
It deliberately has no generic command, PID, cache, prune, or volume action.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime as dt
import enum
import fcntl
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import uuid
from collections.abc import Callable, Mapping, Sequence
from typing import Any


DEFAULT_CONFIG_PATH = Path("/etc/vps-resource-guard/config.toml")
DEFAULT_DOCKER_OPERATION_LOCK_PATH = Path("/var/lib/vps-resource-guard/operation.lock")
DEFAULT_POLL_SECONDS = 5.0
RECEIPT_HEARTBEAT_SECONDS = 300.0
GLOBAL_SETTLE_SECONDS = 60.0
CRITICAL_GLOBAL_SETTLE_SECONDS = 15.0
MAX_FUTURE_TIMESTAMP_SKEW_SECONDS = 300.0
MINIMUM_CANDIDATE_MEMORY_BYTES = 128 * 1024 * 1024
MAX_QUERY_WORKERS = 8
QUERY_COMMAND_TIMEOUT_SECONDS = 5.0
SUPPORTED_ACTIONS = frozenset(
    {"systemd-restart", "systemd-user-restart", "docker-restart"}
)

_HOST_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,62}\Z")
_EXPECTED_HOSTNAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z")
_TARGET_ID_RE = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}\Z")
_SYSTEMD_SERVICE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@:-]*\.service\Z")
_DOCKER_CONTAINER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_EVENT_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
_SECRET_DIAGNOSTIC_RE = re.compile(
    r"(?i)(bearer\s+|(?:api[_-]?key|token|password)\s*[=:]\s*)\S+"
)


def sanitize_diagnostic(value: object, *, max_chars: int = 240) -> str:
    """Return a bounded, single-line diagnostic with common secrets redacted."""

    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value)
    text = _SECRET_DIAGNOSTIC_RE.sub(r"\1[REDACTED]", text)
    text = " ".join(text.split())
    if len(text) > max_chars:
        return f"{text[: max_chars - 3]}..."
    return text


def _new_event_id() -> str:
    return uuid.uuid4().hex


def _fsync_directory(path: Path) -> None:
    """Durably publish namespace changes below *path*."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(path, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


class GuardError(RuntimeError):
    """Base class for expected, fail-closed guard errors."""


class ConfigError(GuardError):
    """The TOML configuration is malformed or outside the action grammar."""


class StateError(GuardError):
    """Persistent cooldown state cannot be trusted."""


class HostBindingError(GuardError):
    """The runtime hostname does not match the host-bound configuration."""


class QueryError(GuardError):
    """A target's current memory could not be queried safely."""


class ActionError(GuardError):
    """An action request is not in the configured allowlist."""


class InstanceLock:
    """Keep one controller bound to a state/receipt namespace."""

    def __init__(
        self,
        path: Path,
        *,
        busy_message: str = "another guard instance already owns this state",
    ) -> None:
        self.path = path
        self.busy_message = busy_message
        self._descriptor: int | None = None

    def __enter__(self) -> InstanceLock:
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(self.path, flags, 0o600)
            os.fchmod(descriptor, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            if "descriptor" in locals():
                os.close(descriptor)
            raise GuardError(self.busy_message) from exc
        except OSError as exc:
            if "descriptor" in locals():
                os.close(descriptor)
            raise GuardError(
                f"cannot acquire the guard instance lock: {type(exc).__name__}"
            ) from exc
        self._descriptor = descriptor
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        if self._descriptor is not None:
            os.close(self._descriptor)
            self._descriptor = None


@dataclasses.dataclass(frozen=True, slots=True)
class Target:
    id: str
    action: str
    target: str
    priority: int


@dataclasses.dataclass(frozen=True, slots=True)
class GuardConfig:
    host: str
    expected_hostname: str
    memory_ceiling_percent: float
    recovery_percent: float
    critical_percent: float
    minimum_candidate_memory_bytes: int
    poll_interval_seconds: float
    cooldown_seconds: float
    state_file: Path
    receipt_file: Path
    receipt_max_bytes: int
    targets: tuple[Target, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class MemorySnapshot:
    total_bytes: int
    available_bytes: int

    @property
    def used_percent(self) -> float:
        return 100.0 * (self.total_bytes - self.available_bytes) / self.total_bytes


class PressureLevel(str, enum.Enum):
    NORMAL = "normal"
    HYSTERESIS = "hysteresis"
    PRESSURE = "pressure"
    CRITICAL = "critical"
    RECOVERED = "recovered"


@dataclasses.dataclass(slots=True)
class GuardState:
    pressure_active: bool = False
    last_attempt_epoch: dict[str, float] = dataclasses.field(default_factory=dict)
    last_global_attempt_epoch: float | None = None
    pending_state_fault: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class ActionResult:
    succeeded: bool
    returncode: int | None
    error: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class CycleResult:
    level: PressureLevel
    pressure_active: bool
    decision: str
    selected_target_id: str | None
    action_result: ActionResult | None


def _strict_table(
    value: object,
    *,
    location: str,
    required: set[str],
    allowed: set[str],
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{location} must be a TOML table")
    keys = set(value)
    missing = sorted(required - keys)
    unknown = sorted(keys - allowed)
    if missing:
        raise ConfigError(f"{location} is missing required keys: {', '.join(missing)}")
    if unknown:
        raise ConfigError(f"{location} has unknown keys: {', '.join(unknown)}")
    return value


def _number(value: object, *, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{location} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ConfigError(f"{location} must be finite")
    return result


def _integer(value: object, *, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{location} must be an integer")
    return value


def _string(value: object, *, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{location} must be a non-empty string")
    return value


def _absolute_path(value: object, *, location: str) -> Path:
    path = Path(_string(value, location=location))
    if not path.is_absolute():
        raise ConfigError(f"{location} must be an absolute path")
    return path


def parse_config(data: Mapping[str, Any]) -> GuardConfig:
    """Parse already-decoded TOML data using a closed configuration schema."""

    root = _strict_table(
        data,
        location="configuration",
        required={"guard", "targets"},
        allowed={"guard", "targets"},
    )
    guard = _strict_table(
        root["guard"],
        location="[guard]",
        required={
            "host",
            "expected_hostname",
            "memory_ceiling_percent",
            "recovery_percent",
            "critical_percent",
            "minimum_candidate_memory_bytes",
            "poll_interval_seconds",
            "cooldown_seconds",
            "state_file",
            "receipt_file",
            "receipt_max_bytes",
        },
        allowed={
            "host",
            "expected_hostname",
            "memory_ceiling_percent",
            "recovery_percent",
            "critical_percent",
            "minimum_candidate_memory_bytes",
            "poll_interval_seconds",
            "cooldown_seconds",
            "state_file",
            "receipt_file",
            "receipt_max_bytes",
        },
    )

    host = _string(guard["host"], location="guard.host")
    if not _HOST_RE.fullmatch(host):
        raise ConfigError("guard.host must match [a-z0-9][a-z0-9-]{0,62}")
    expected_hostname = _string(
        guard["expected_hostname"], location="guard.expected_hostname"
    )
    if not _EXPECTED_HOSTNAME_RE.fullmatch(expected_hostname):
        raise ConfigError(
            "guard.expected_hostname contains unsupported hostname characters"
        )

    recovery = _number(guard["recovery_percent"], location="guard.recovery_percent")
    ceiling = _number(
        guard["memory_ceiling_percent"], location="guard.memory_ceiling_percent"
    )
    critical = _number(guard["critical_percent"], location="guard.critical_percent")
    if not 0.0 < recovery < ceiling < critical <= 100.0:
        raise ConfigError(
            "memory thresholds must satisfy "
            "0 < recovery_percent < memory_ceiling_percent < critical_percent <= 100"
        )

    minimum_candidate_memory_bytes = _integer(
        guard["minimum_candidate_memory_bytes"],
        location="guard.minimum_candidate_memory_bytes",
    )
    if minimum_candidate_memory_bytes < MINIMUM_CANDIDATE_MEMORY_BYTES:
        raise ConfigError(
            "guard.minimum_candidate_memory_bytes must be at least "
            f"{MINIMUM_CANDIDATE_MEMORY_BYTES} bytes"
        )

    poll = _number(
        guard["poll_interval_seconds"], location="guard.poll_interval_seconds"
    )
    if poll != DEFAULT_POLL_SECONDS:
        raise ConfigError(
            f"guard.poll_interval_seconds must be {DEFAULT_POLL_SECONDS:g} seconds"
        )
    cooldown = _number(guard["cooldown_seconds"], location="guard.cooldown_seconds")
    if cooldown < poll:
        raise ConfigError("guard.cooldown_seconds must be at least one poll interval")

    receipt_max_bytes = _integer(
        guard["receipt_max_bytes"], location="guard.receipt_max_bytes"
    )
    if receipt_max_bytes <= 0:
        raise ConfigError("guard.receipt_max_bytes must be greater than zero")

    state_file = _absolute_path(guard["state_file"], location="guard.state_file")
    receipt_file = _absolute_path(guard["receipt_file"], location="guard.receipt_file")
    if state_file == receipt_file:
        raise ConfigError("guard.state_file and guard.receipt_file must be different")

    raw_targets = root["targets"]
    if not isinstance(raw_targets, list) or not raw_targets:
        raise ConfigError("[[targets]] must contain at least one target")

    targets: list[Target] = []
    ids: set[str] = set()
    action_targets: set[tuple[str, str]] = set()
    for index, raw_target in enumerate(raw_targets):
        location = f"targets[{index}]"
        table = _strict_table(
            raw_target,
            location=location,
            required={"id", "action", "target", "priority"},
            allowed={"id", "action", "target", "priority"},
        )
        target_id = _string(table["id"], location=f"{location}.id")
        if not _TARGET_ID_RE.fullmatch(target_id):
            raise ConfigError(f"{location}.id must match [a-z0-9][a-z0-9_.-]{{0,63}}")
        if target_id in ids:
            raise ConfigError(f"duplicate target id: {target_id}")

        action = _string(table["action"], location=f"{location}.action")
        if action not in SUPPORTED_ACTIONS:
            raise ConfigError(
                f"{location}.action is unsupported; allowed actions are: "
                + ", ".join(sorted(SUPPORTED_ACTIONS))
            )
        target_name = _string(table["target"], location=f"{location}.target")
        if action in {"systemd-restart", "systemd-user-restart"} and not (
            _SYSTEMD_SERVICE_RE.fullmatch(target_name)
        ):
            raise ConfigError(
                f"{location}.target must be an explicit systemd .service unit"
            )
        if action == "docker-restart" and not _DOCKER_CONTAINER_RE.fullmatch(
            target_name
        ):
            raise ConfigError(
                f"{location}.target must be an explicit Docker container name"
            )

        priority = _integer(table["priority"], location=f"{location}.priority")
        if priority < 0:
            raise ConfigError(f"{location}.priority must be non-negative")
        identity = (action, target_name)
        if identity in action_targets:
            raise ConfigError(f"duplicate configured action target: {target_name}")

        ids.add(target_id)
        action_targets.add(identity)
        targets.append(Target(target_id, action, target_name, priority))

    return GuardConfig(
        host=host,
        expected_hostname=expected_hostname,
        memory_ceiling_percent=ceiling,
        recovery_percent=recovery,
        critical_percent=critical,
        minimum_candidate_memory_bytes=minimum_candidate_memory_bytes,
        poll_interval_seconds=poll,
        cooldown_seconds=cooldown,
        state_file=state_file,
        receipt_file=receipt_file,
        receipt_max_bytes=receipt_max_bytes,
        targets=tuple(targets),
    )


def load_config(path: Path) -> GuardConfig:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"malformed TOML in {path}: {exc}") from exc
    return parse_config(data)


def verify_runtime_host(config: GuardConfig, actual_hostname: str | None = None) -> str:
    """Fail closed unless this configuration is running on its bound host."""

    actual = socket.gethostname() if actual_hostname is None else actual_hostname
    if actual != config.expected_hostname:
        raise HostBindingError(
            "runtime hostname mismatch: "
            f"expected {config.expected_hostname!r}, observed {actual!r}"
        )
    return actual


def read_memory_snapshot(path: Path = Path("/proc/meminfo")) -> MemorySnapshot:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise QueryError(f"cannot read {path}: {exc}") from exc

    values: dict[str, int] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        if key not in {"MemTotal", "MemAvailable"}:
            continue
        fields = raw_value.split()
        if len(fields) != 2 or fields[1] != "kB" or not fields[0].isdigit():
            raise QueryError(f"invalid {key} entry in {path}")
        values[key] = int(fields[0]) * 1024

    if "MemTotal" not in values or "MemAvailable" not in values:
        raise QueryError(f"{path} is missing MemTotal or MemAvailable")
    total = values["MemTotal"]
    available = values["MemAvailable"]
    if total <= 0 or available < 0 or available > total:
        raise QueryError(f"{path} contains an invalid memory range")
    return MemorySnapshot(total, available)


def evaluate_pressure(
    used_percent: float,
    *,
    was_active: bool,
    config: GuardConfig,
) -> tuple[bool, PressureLevel]:
    """Apply ceiling/recovery hysteresis and label critical pressure."""

    if not math.isfinite(used_percent) or not 0.0 <= used_percent <= 100.0:
        raise QueryError("used memory percent must be finite and within 0..100")
    if used_percent >= config.critical_percent:
        return True, PressureLevel.CRITICAL
    if was_active:
        if used_percent <= config.recovery_percent:
            return False, PressureLevel.RECOVERED
        if used_percent >= config.memory_ceiling_percent:
            return True, PressureLevel.PRESSURE
        return True, PressureLevel.HYSTERESIS
    if used_percent >= config.memory_ceiling_percent:
        return True, PressureLevel.PRESSURE
    return False, PressureLevel.NORMAL


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, *, now: float | None = None) -> GuardState:
        current_epoch = time.time() if now is None else now
        if not math.isfinite(current_epoch) or current_epoch < 0:
            raise StateError("cannot validate state against an invalid current time")
        if not self.path.exists():
            return GuardState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StateError(f"cannot trust state file {self.path}: {exc}") from exc
        if not isinstance(data, dict) or data.get("version") != 1:
            raise StateError(f"cannot trust state file {self.path}: invalid version")
        pressure_active = data.get("pressure_active")
        attempts = data.get("last_attempt_epoch")
        global_attempt = data.get("last_global_attempt_epoch")
        pending_state_fault = data.get("pending_state_fault")
        if not isinstance(pressure_active, bool) or not isinstance(attempts, dict):
            raise StateError(f"cannot trust state file {self.path}: invalid schema")
        clamped = False

        def checked_epoch(value: object, *, label: str) -> float:
            nonlocal clamped
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise StateError(
                    f"cannot trust state file {self.path}: invalid {label}"
                )
            epoch = float(value)
            if not math.isfinite(epoch) or epoch < 0:
                raise StateError(
                    f"cannot trust state file {self.path}: invalid {label}"
                )
            future_seconds = epoch - current_epoch
            if future_seconds > MAX_FUTURE_TIMESTAMP_SKEW_SECONDS:
                raise StateError(
                    f"cannot trust state file {self.path}: {label} is too far future"
                )
            if future_seconds > 0:
                clamped = True
                return current_epoch
            return epoch

        checked_attempts: dict[str, float] = {}
        for target_id, value in attempts.items():
            if not isinstance(target_id, str):
                raise StateError(
                    f"cannot trust state file {self.path}: invalid target id"
                )
            checked_attempts[target_id] = checked_epoch(value, label="cooldown value")
        checked_global_attempt: float | None = None
        if global_attempt is not None:
            checked_global_attempt = checked_epoch(
                global_attempt, label="global cooldown"
            )
        if pending_state_fault is not None and not isinstance(pending_state_fault, str):
            raise StateError(
                f"cannot trust state file {self.path}: invalid pending state fault"
            )
        checked_pending_fault = (
            sanitize_diagnostic(pending_state_fault)
            if pending_state_fault is not None
            else None
        )
        state = GuardState(
            pressure_active,
            checked_attempts,
            checked_global_attempt,
            checked_pending_fault,
        )
        if clamped:
            self.save(state)
        return state

    def quarantine_corrupt(self) -> Path:
        """Atomically retain one bounded corrupt-state artifact."""

        corrupt_path = self.path.with_name(f"{self.path.name}.corrupt")
        try:
            os.replace(self.path, corrupt_path)
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as exc:
            raise StateError(
                f"cannot quarantine corrupt state file {self.path}: {exc}"
            ) from exc
        return corrupt_path

    def save(self, state: GuardState) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "version": 1,
                "pressure_active": state.pressure_active,
                "last_attempt_epoch": state.last_attempt_epoch,
                "last_global_attempt_epoch": state.last_global_attempt_epoch,
                "pending_state_fault": state.pending_state_fault,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as handle:
                temporary_name = handle.name
                os.chmod(temporary_name, 0o600)
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
            temporary_name = None
            _fsync_directory(self.path.parent)
        except OSError as exc:
            raise StateError(f"cannot persist state file {self.path}: {exc}") from exc
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name)
                except OSError:
                    pass


class ReceiptWriter:
    """Append JSONL receipts while bounding disk use to two files."""

    def __init__(self, path: Path, max_bytes: int) -> None:
        self.path = path
        self.max_bytes = max_bytes

    def append(self, record: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        encoded = line.encode("utf-8")
        if len(encoded) > self.max_bytes:
            raise GuardError("one receipt exceeds the configured receipt byte bound")
        try:
            current_size = self.path.stat().st_size
        except FileNotFoundError:
            current_size = 0
        except OSError as exc:
            raise GuardError(f"cannot inspect receipt file {self.path}: {exc}") from exc
        if current_size and current_size + len(encoded) > self.max_bytes:
            rotated = self.path.with_name(f"{self.path.name}.1")
            try:
                os.replace(self.path, rotated)
                _fsync_directory(self.path.parent)
            except OSError as exc:
                raise GuardError(
                    f"cannot rotate receipt file {self.path}: {exc}"
                ) from exc
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "ab") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            _fsync_directory(self.path.parent)
        except OSError as exc:
            raise GuardError(f"cannot append receipt file {self.path}: {exc}") from exc


def parse_memory_size(value: str) -> int:
    """Parse the current-use side of Docker's ``MemUsage`` value."""

    current = value.split("/", 1)[0].strip()
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([kKMGTPE]?i?B)", current)
    if match is None:
        raise QueryError(
            "unrecognized Docker memory value: " + sanitize_diagnostic(value)
        )
    magnitude = float(match.group(1))
    unit = match.group(2)
    decimal_units = {
        "B": 1,
        "kB": 1000,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "PB": 1000**5,
        "EB": 1000**6,
    }
    binary_units = {
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": 1024**3,
        "TiB": 1024**4,
        "PiB": 1024**5,
        "EiB": 1024**6,
    }
    multiplier = {**decimal_units, **binary_units}[unit]
    result = int(magnitude * multiplier)
    if result < 0:
        raise QueryError("invalid Docker memory value: " + sanitize_diagnostic(value))
    return result


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class TargetMemoryQuery:
    def __init__(self, runner: CommandRunner = subprocess.run) -> None:
        self._runner = runner

    def _run(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        try:
            result = self._runner(
                list(command),
                capture_output=True,
                text=True,
                timeout=QUERY_COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            detail_source = getattr(exc, "stderr", None) or str(exc)
            detail = sanitize_diagnostic(detail_source)
            suffix = f": {detail}" if detail else ""
            raise QueryError(
                f"memory query failed ({type(exc).__name__}){suffix}"
            ) from exc
        if result.returncode != 0:
            stderr = sanitize_diagnostic(result.stderr)
            suffix = f": {stderr}" if stderr else ""
            raise QueryError(f"memory query exited {result.returncode}{suffix}")
        return result

    def memory_bytes(self, target: Target) -> int:
        if target.action in {"systemd-restart", "systemd-user-restart"}:
            systemctl = ["systemctl"]
            if target.action == "systemd-user-restart":
                systemctl.append("--user")
            active = self._run(
                [
                    *systemctl,
                    "show",
                    "--property=ActiveState",
                    "--value",
                    "--",
                    target.target,
                ]
            ).stdout.strip()
            if active != "active":
                raise QueryError(f"systemd target {target.id} is not active")
            value = self._run(
                [
                    *systemctl,
                    "show",
                    "--property=MemoryCurrent",
                    "--value",
                    "--",
                    target.target,
                ]
            ).stdout.strip()
            if not value.isdigit():
                raise QueryError(
                    f"systemd target {target.id} has no numeric MemoryCurrent"
                )
            return int(value)
        if target.action == "docker-restart":
            value = self._run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format={{.MemUsage}}",
                    "--",
                    target.target,
                ]
            ).stdout.strip()
            return parse_memory_size(value)
        raise QueryError(f"unsupported action in memory query: {target.action}")


def query_target_memories(
    targets: Sequence[Target],
    target_query: TargetMemoryQuery,
) -> dict[str, tuple[int | None, str | None]]:
    """Query targets concurrently and return results in configured order."""

    if not targets:
        return {}
    worker_count = min(len(targets), MAX_QUERY_WORKERS)
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
        pending = {
            target.id: pool.submit(target_query.memory_bytes, target)
            for target in targets
        }
        results: dict[str, tuple[int | None, str | None]] = {}
        for target in targets:
            try:
                results[target.id] = (pending[target.id].result(), None)
            except QueryError as exc:
                results[target.id] = (None, str(exc))
            except Exception as exc:  # Defensive boundary around injected query code.
                results[target.id] = (
                    None,
                    f"unexpected query failure: {type(exc).__name__}",
                )
    return results


class ActionExecutor:
    """Execute only identities present in the immutable configured allowlist."""

    def __init__(
        self,
        targets: Sequence[Target],
        runner: CommandRunner = subprocess.run,
        docker_operation_lock_path: Path = DEFAULT_DOCKER_OPERATION_LOCK_PATH,
    ) -> None:
        self._targets = {target.id: target for target in targets}
        self._runner = runner
        self._docker_operation_lock_path = docker_operation_lock_path

    def _run(self, command: list[str]) -> ActionResult:
        try:
            result = self._runner(
                command,
                capture_output=True,
                text=True,
                timeout=30.0,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ActionResult(False, None, "timeout-unknown")
        except OSError as exc:
            return ActionResult(False, None, type(exc).__name__)
        if result.returncode == 0:
            return ActionResult(True, 0)
        return ActionResult(False, result.returncode, "nonzero-exit")

    def execute(self, target_id: str) -> ActionResult:
        target = self._targets.get(target_id)
        if target is None:
            raise ActionError(f"target id is not allowlisted: {target_id}")
        if target.action == "systemd-restart":
            command = ["systemctl", "restart", "--", target.target]
        elif target.action == "systemd-user-restart":
            command = [
                "systemctl",
                "--user",
                "restart",
                "--",
                target.target,
            ]
        elif target.action == "docker-restart":
            command = ["docker", "restart", "--timeout", "10", "--", target.target]
        else:
            # This remains checked even though config loading uses a closed schema.
            raise ActionError(f"action is not allowlisted: {target.action}")
        if target.action != "docker-restart":
            return self._run(command)
        try:
            with InstanceLock(
                self._docker_operation_lock_path,
                busy_message="Docker scope policy operation is already in progress",
            ):
                return self._run(command)
        except GuardError:
            return ActionResult(False, None, "operation-lock-busy")


class GuardController:
    def __init__(
        self,
        config: GuardConfig,
        *,
        dry_run: bool = False,
        state_store: StateStore | None = None,
        receipt_writer: ReceiptWriter | None = None,
        memory_reader: Callable[[], MemorySnapshot] = read_memory_snapshot,
        target_query: TargetMemoryQuery | None = None,
        executor: ActionExecutor | None = None,
        clock: Callable[[], float] = time.time,
        hostname_reader: Callable[[], str] = socket.gethostname,
        event_id_factory: Callable[[], str] = _new_event_id,
    ) -> None:
        self.config = config
        self.runtime_hostname = verify_runtime_host(config, hostname_reader())
        self.dry_run = dry_run
        self.state_store = state_store or StateStore(config.state_file)
        self.receipt_writer = receipt_writer or ReceiptWriter(
            config.receipt_file, config.receipt_max_bytes
        )
        self.memory_reader = memory_reader
        self.target_query = target_query or TargetMemoryQuery()
        self.executor = executor or ActionExecutor(config.targets)
        self.clock = clock
        self.event_id_factory = event_id_factory
        self._last_receipt_epoch: float | None = None
        self._last_receipt_level: PressureLevel | None = None
        self._last_significant_observations: tuple[tuple[str, str, str], ...] = ()
        startup_epoch = self.clock()
        try:
            self.state = self.state_store.load(now=startup_epoch)
        except StateError as exc:
            corrupt_path = self.state_store.quarantine_corrupt()
            fault = sanitize_diagnostic(
                f"{type(exc).__name__}: {exc}; quarantined={corrupt_path.name}"
            )
            self.state = GuardState(
                pressure_active=True,
                last_global_attempt_epoch=startup_epoch,
                pending_state_fault=fault,
            )
            self.state_store.save(self.state)
        if self.state.pending_state_fault is not None:
            fault_receipt = {
                "schema": "vps-resource-guard.receipt.v1",
                "timestamp": dt.datetime.fromtimestamp(
                    startup_epoch, tz=dt.timezone.utc
                )
                .isoformat()
                .replace("+00:00", "Z"),
                "host": self.config.host,
                "dry_run": self.dry_run,
                "receipt_reasons": ["state-fault"],
                "pressure_active": True,
                "decision": "state-fault-fail-safe",
                "error": self.state.pending_state_fault,
                "quarantined_state_file": str(
                    self.state_store.path.with_name(
                        f"{self.state_store.path.name}.corrupt"
                    )
                ),
            }
            self.receipt_writer.append(fault_receipt)
            self.state.pending_state_fault = None
            self.state_store.save(self.state)

    @staticmethod
    def _significant_observations(
        observations: Sequence[Mapping[str, Any]],
    ) -> tuple[tuple[str, str, str], ...]:
        """Return stable query findings that warrant an event receipt.

        Cooldown and successful candidate measurements are routine. Query
        failures and targets reporting no memory are exceptional, and their
        transitions are receipted without repeating the same event every poll.
        """

        significant: list[tuple[str, str, str]] = []
        for observation in observations:
            status = observation.get("status")
            if status not in {
                "below-minimum-memory",
                "query-error",
                "zero-memory",
            }:
                continue
            significant.append(
                (
                    str(observation.get("id", "")),
                    str(status),
                    str(observation.get("error", "")),
                )
            )
        return tuple(significant)

    def _receipt_reasons(
        self,
        *,
        now: float,
        level: PressureLevel,
        selected: Target | None,
        observations: Sequence[Mapping[str, Any]],
    ) -> tuple[tuple[str, ...], tuple[tuple[str, str, str], ...]]:
        significant = self._significant_observations(observations)
        reasons: list[str] = []
        if self._last_receipt_epoch is None:
            reasons.append("first-cycle")
        if (
            self._last_receipt_level is not None
            and level is not self._last_receipt_level
        ):
            reasons.append("level-transition")
        if selected is not None:
            reasons.append("action")
        if significant != self._last_significant_observations and (
            significant or self._last_significant_observations
        ):
            reasons.append("query-status-transition")

        if not reasons and self._last_receipt_epoch is not None:
            elapsed = now - self._last_receipt_epoch
            if elapsed < 0 or elapsed >= RECEIPT_HEARTBEAT_SECONDS:
                reasons.append("heartbeat")
        return tuple(reasons), significant

    def _append_cycle_receipt(
        self,
        *,
        now: float,
        snapshot: MemorySnapshot,
        level: PressureLevel,
        pressure_active: bool,
        decision: str,
        receipt_reasons: Sequence[str],
        observations: Sequence[Mapping[str, Any]],
        selected: Target | None,
        selected_memory: int | None,
        action_result: ActionResult | None = None,
        event_id: str | None = None,
        action_phase: str | None = None,
        postcondition: Mapping[str, Any] | None = None,
    ) -> None:
        timestamp = dt.datetime.fromtimestamp(now, tz=dt.timezone.utc)
        receipt: dict[str, Any] = {
            "schema": "vps-resource-guard.receipt.v1",
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "host": self.config.host,
            "dry_run": self.dry_run,
            "receipt_reasons": list(receipt_reasons),
            "total_bytes": snapshot.total_bytes,
            "available_bytes": snapshot.available_bytes,
            "used_percent": round(snapshot.used_percent, 3),
            "level": level.value,
            "pressure_active": pressure_active,
            "decision": decision,
            "candidates": list(observations),
            "selected_target_id": selected.id if selected else None,
            "selected_action": selected.action if selected else None,
            "selected_target": selected.target if selected else None,
            "selected_memory_bytes": selected_memory,
        }
        if event_id is not None:
            receipt["event_id"] = event_id
        if action_phase is not None:
            receipt["action_phase"] = action_phase
        if action_result is not None:
            receipt["action"] = dataclasses.asdict(action_result)
        if postcondition is not None:
            receipt["postcondition"] = dict(postcondition)
        self.receipt_writer.append(receipt)
        self._last_receipt_epoch = now
        self._last_receipt_level = level

    def _post_action_observation(self, selected: Target) -> dict[str, Any]:
        try:
            memory_bytes = self.target_query.memory_bytes(selected)
        except QueryError as exc:
            return {
                "status": "query-error",
                "error": sanitize_diagnostic(exc),
            }
        except Exception as exc:  # Defensive boundary around injected query code.
            return {
                "status": "query-error",
                "error": f"unexpected query failure: {type(exc).__name__}",
            }
        return {
            "status": "ok",
            "memory_bytes": memory_bytes,
        }

    def _eligible_candidates(
        self, now: float
    ) -> tuple[list[tuple[Target, int]], list[dict[str, Any]]]:
        eligible: list[tuple[Target, int]] = []
        observations: list[dict[str, Any]] = []
        query_targets: list[Target] = []
        cooldown_observations: dict[str, dict[str, Any]] = {}
        for target in self.config.targets:
            last_attempt = self.state.last_attempt_epoch.get(target.id)
            if last_attempt is not None:
                remaining = self.config.cooldown_seconds - (now - last_attempt)
                if remaining > 0:
                    cooldown_observations[target.id] = {
                        "id": target.id,
                        "status": "cooldown",
                        "cooldown_remaining_seconds": round(remaining, 3),
                    }
                    continue
            query_targets.append(target)

        query_results = query_target_memories(query_targets, self.target_query)
        for target in self.config.targets:
            cooldown_observation = cooldown_observations.get(target.id)
            if cooldown_observation is not None:
                observations.append(cooldown_observation)
                continue
            memory_bytes, error = query_results[target.id]
            if error is not None:
                observations.append(
                    {"id": target.id, "status": "query-error", "error": error}
                )
                continue
            assert memory_bytes is not None
            if memory_bytes <= 0:
                observations.append(
                    {"id": target.id, "status": "zero-memory", "memory_bytes": 0}
                )
                continue
            if memory_bytes < self.config.minimum_candidate_memory_bytes:
                observations.append(
                    {
                        "id": target.id,
                        "status": "below-minimum-memory",
                        "memory_bytes": memory_bytes,
                        "minimum_candidate_memory_bytes": (
                            self.config.minimum_candidate_memory_bytes
                        ),
                    }
                )
                continue
            observations.append(
                {
                    "id": target.id,
                    "status": "eligible",
                    "memory_bytes": memory_bytes,
                    "priority": target.priority,
                }
            )
            eligible.append((target, memory_bytes))
        # Lowest configured priority sheds first.  Equal-priority targets are
        # ordered by most current memory, then stable target id.
        eligible.sort(key=lambda item: (item[0].priority, -item[1], item[0].id))
        return eligible, observations

    def run_cycle(self) -> CycleResult:
        now = self.clock()
        snapshot = self.memory_reader()
        previous_pressure = self.state.pressure_active
        pressure_active, level = evaluate_pressure(
            snapshot.used_percent,
            was_active=previous_pressure,
            config=self.config,
        )
        self.state.pressure_active = pressure_active

        decision = "below-ceiling"
        selected: Target | None = None
        selected_memory: int | None = None
        action_result: ActionResult | None = None
        action_event_id: str | None = None
        postcondition: dict[str, Any] | None = None
        observations: list[dict[str, Any]] = []

        if snapshot.used_percent >= self.config.memory_ceiling_percent:
            global_attempt = self.state.last_global_attempt_epoch
            global_settle_remaining = 0.0
            settle_seconds = (
                CRITICAL_GLOBAL_SETTLE_SECONDS
                if level is PressureLevel.CRITICAL
                else GLOBAL_SETTLE_SECONDS
            )
            if global_attempt is not None:
                global_settle_remaining = settle_seconds - (now - global_attempt)
            if global_settle_remaining > 0:
                decision = "global-settle"
                observations = [
                    {
                        "status": "global-settle",
                        "cooldown_remaining_seconds": round(global_settle_remaining, 3),
                    }
                ]
            else:
                candidates, observations = self._eligible_candidates(now)
                if candidates:
                    selected, selected_memory = candidates[0]
                    if self.dry_run:
                        decision = "dry-run-would-restart"
                        action_result = ActionResult(True, None, "dry-run")
                    else:
                        action_event_id = self.event_id_factory()
                        if not _EVENT_ID_RE.fullmatch(action_event_id):
                            raise GuardError("event id factory returned an invalid id")
                        # Persist both cooldown clocks before invoking an external
                        # action. If persistence fails, the action is not executed.
                        self.state.last_attempt_epoch[selected.id] = now
                        self.state.last_global_attempt_epoch = now
                        self.state_store.save(self.state)
                        self._append_cycle_receipt(
                            now=now,
                            snapshot=snapshot,
                            level=level,
                            pressure_active=pressure_active,
                            decision="restart-intent",
                            receipt_reasons=("action-intent",),
                            observations=observations,
                            selected=selected,
                            selected_memory=selected_memory,
                            event_id=action_event_id,
                            action_phase="intent",
                        )
                        action_result = self.executor.execute(selected.id)
                        postcondition = self._post_action_observation(selected)
                        if action_result.succeeded:
                            decision = (
                                "restart-completed"
                                if postcondition.get("status") == "ok"
                                else "restart-completed-postcheck-failed"
                            )
                        elif action_result.error == "timeout-unknown":
                            decision = "restart-outcome-unknown"
                        else:
                            decision = "restart-rejected"
                else:
                    decision = "no-eligible-target"
        elif pressure_active:
            decision = "hysteresis-hold"
        elif level is PressureLevel.RECOVERED:
            decision = "recovered"

        if (
            not self.dry_run
            and selected is None
            and (previous_pressure != self.state.pressure_active)
        ):
            self.state_store.save(self.state)

        receipt_reasons, significant_observations = self._receipt_reasons(
            now=now,
            level=level,
            selected=selected,
            observations=observations,
        )
        if action_event_id is not None:
            receipt_reasons = ("action-outcome",)
        if receipt_reasons:
            self._append_cycle_receipt(
                now=now,
                snapshot=snapshot,
                level=level,
                pressure_active=pressure_active,
                decision=decision,
                receipt_reasons=receipt_reasons,
                observations=observations,
                selected=selected,
                selected_memory=selected_memory,
                action_result=action_result,
                event_id=action_event_id,
                action_phase="outcome" if action_event_id is not None else None,
                postcondition=postcondition,
            )
        self._last_significant_observations = significant_observations

        return CycleResult(
            level=level,
            pressure_active=pressure_active,
            decision=decision,
            selected_target_id=selected.id if selected else None,
            action_result=action_result,
        )


def _validation_summary(config: GuardConfig) -> str:
    return json.dumps(
        {
            "valid": True,
            "host": config.host,
            "expected_hostname": config.expected_hostname,
            "minimum_candidate_memory_bytes": (config.minimum_candidate_memory_bytes),
            "poll_interval_seconds": config.poll_interval_seconds,
            "targets": [target.id for target in config.targets],
        },
        sort_keys=True,
    )


def _host_verification_summary(config: GuardConfig, actual_hostname: str) -> str:
    return json.dumps(
        {
            "valid": True,
            "host": config.host,
            "expected_hostname": config.expected_hostname,
            "actual_hostname": actual_hostname,
        },
        sort_keys=True,
    )


def self_test_targets(
    config: GuardConfig,
    *,
    target_query: TargetMemoryQuery | None = None,
    actual_hostname: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Verify host binding and target control-plane queries without mutation."""

    runtime_hostname = verify_runtime_host(config, actual_hostname)
    query = target_query or TargetMemoryQuery()
    results = query_target_memories(config.targets, query)
    target_summaries: list[dict[str, Any]] = []
    succeeded = True
    for target in config.targets:
        memory_bytes, error = results[target.id]
        summary: dict[str, Any] = {
            "id": target.id,
            "action": target.action,
            "target": target.target,
        }
        if error is None:
            summary.update(status="ok", memory_bytes=memory_bytes)
        else:
            succeeded = False
            summary.update(status="error", error=error)
        target_summaries.append(summary)
    return succeeded, {
        "valid": succeeded,
        "host": config.host,
        "expected_hostname": config.expected_hostname,
        "actual_hostname": runtime_hostname,
        "targets": target_summaries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run exactly one cycle")
    mode.add_argument(
        "--validate-config",
        action="store_true",
        help="validate TOML without querying memory or writing state",
    )
    mode.add_argument(
        "--verify-host",
        action="store_true",
        help="validate TOML and verify the exact runtime hostname",
    )
    mode.add_argument(
        "--self-test-targets",
        action="store_true",
        help="verify host binding and query every target without mutation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="evaluate and receipt actions without invoking a restart",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if (
        args.validate_config or args.verify_host or args.self_test_targets
    ) and args.dry_run:
        print(
            "error: --dry-run cannot be combined with a validation mode",
            file=sys.stderr,
        )
        return 2
    try:
        config = load_config(args.config)
        if args.validate_config:
            print(_validation_summary(config))
            return 0
        if args.verify_host:
            actual_hostname = verify_runtime_host(config)
            print(_host_verification_summary(config, actual_hostname))
            return 0
        if args.self_test_targets:
            succeeded, summary = self_test_targets(config)
            print(json.dumps(summary, sort_keys=True))
            return 0 if succeeded else 1
        lock_path = config.state_file.with_name(f"{config.state_file.name}.lock")
        with InstanceLock(lock_path):
            controller = GuardController(config, dry_run=args.dry_run)
            if args.once:
                result = controller.run_cycle()
                print(
                    json.dumps(
                        {
                            "host": config.host,
                            "level": result.level.value,
                            "decision": result.decision,
                            "selected_target_id": result.selected_target_id,
                        },
                        sort_keys=True,
                    )
                )
                if (
                    result.action_result is not None
                    and not result.action_result.succeeded
                ):
                    return 1
                return 0

            stop = threading.Event()

            def request_stop(_signum: int, _frame: object) -> None:
                stop.set()

            signal.signal(signal.SIGTERM, request_stop)
            signal.signal(signal.SIGINT, request_stop)
            while not stop.is_set():
                cycle_started = time.monotonic()
                try:
                    controller.run_cycle()
                except GuardError as exc:
                    print(f"vps-resource-guard: {exc}", file=sys.stderr)
                elapsed = time.monotonic() - cycle_started
                stop.wait(max(0.0, config.poll_interval_seconds - elapsed))
            return 0
    except GuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
