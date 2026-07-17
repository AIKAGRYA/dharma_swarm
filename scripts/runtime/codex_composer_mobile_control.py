#!/usr/bin/env python3
"""Bounded root helper for phone-safe Codex Composer presence recovery.

The only accepted operations are ``status`` and ``reconcile``.  The helper
never accepts a host, unit, command, prompt, or repository path from its
caller.  It is designed for two host-unique forced-command SSH keys whose
sudoers entries name one exact argv each.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping


AGENT_UID = "codex_composer"
UNIT = "dharma-codex-composer-replica.service"
ENV_FILE = Path("/etc/dharma/codex-composer-replica.env")
STATE_DIR = Path("/var/lib/dharma-codex-composer")
HEARTBEAT_FILE = STATE_DIR / "heartbeat.json"
LOCK_FILE = STATE_DIR / "mobile-control.lock"
COOLDOWN_FILE = STATE_DIR / "mobile-control-cooldown.json"
RECEIPT_FILE = STATE_DIR / "mobile-control-receipts.jsonl"
SYSTEMCTL = "/usr/bin/systemctl"
FRESHNESS_SECONDS = 90.0
FUTURE_SKEW_SECONDS = 5.0
COOLDOWN_SECONDS = 300.0
VERIFY_TIMEOUT_SECONDS = 45.0
MAX_FILE_BYTES = 256 * 1024
_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]{0,62}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{8,128}")
_SSH_COMMAND = re.compile(
    r"cc-mobile-v1 (status|reconcile) ([A-Za-z0-9_-]{8,128}) "
    r"([0-9]{10}) ([0-9]{10})"
)


class ControlConfigurationError(RuntimeError):
    """The fixed local control contract cannot be proven."""


@dataclass(frozen=True, slots=True)
class ControlConfig:
    instance_id: str
    card_sha256: str
    memory_sha256: str
    state_dir: Path = STATE_DIR
    freshness_seconds: float = FRESHNESS_SECONDS
    cooldown_seconds: float = COOLDOWN_SECONDS
    verify_timeout_seconds: float = VERIFY_TIMEOUT_SECONDS

    @property
    def heartbeat_file(self) -> Path:
        return self.state_dir / "heartbeat.json"

    @property
    def lock_file(self) -> Path:
        return self.state_dir / "mobile-control.lock"

    @property
    def cooldown_file(self) -> Path:
        return self.state_dir / "mobile-control-cooldown.json"

    @property
    def receipt_file(self) -> Path:
        return self.state_dir / "mobile-control-receipts.jsonl"


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    healthy: bool
    reasons: tuple[str, ...]
    service_active: bool
    service_enabled: bool
    status: str = "missing"
    observed_at: str = ""
    heartbeat_age_seconds: float | None = None
    boot_id: str = ""
    sequence: int | None = None
    seat_state: str = ""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _run(args: list[str], *, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    )


def _read_regular_bytes(
    path: Path,
    *,
    max_bytes: int = MAX_FILE_BYTES,
    required_uid: int | None = 0,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ControlConfigurationError("control input is not a regular file")
        if required_uid is not None and metadata.st_uid != required_uid:
            raise ControlConfigurationError("control input has the wrong owner")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ControlConfigurationError("control input is not root-private")
        if metadata.st_size > max_bytes:
            raise ControlConfigurationError("control input exceeds the read limit")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        if remaining == 0:
            raise ControlConfigurationError("control input exceeds the read limit")
        current = os.stat(path, follow_symlinks=False)
        if current.st_dev != metadata.st_dev or current.st_ino != metadata.st_ino:
            raise ControlConfigurationError("control input changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _parse_env_file(path: Path, *, required_uid: int | None = 0) -> dict[str, str]:
    try:
        text = _read_regular_bytes(path, required_uid=required_uid).decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ControlConfigurationError("cannot read fixed replica environment") from exc
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z0-9_]+", key):
            raise ControlConfigurationError("invalid replica environment syntax")
        if key in values or any(char in value for char in "\x00\r\n"):
            raise ControlConfigurationError("ambiguous replica environment")
        values[key] = value
    return values


def load_config(
    path: Path = ENV_FILE,
    *,
    required_uid: int | None = 0,
) -> ControlConfig:
    values = _parse_env_file(path, required_uid=required_uid)
    instance = values.get("CODEX_COMPOSER_INSTANCE_ID", "")
    card = values.get("CODEX_COMPOSER_CARD_SHA256", "")
    memory = values.get("CODEX_COMPOSER_MEMORY_SHA256", "")
    state_dir = Path(
        values.get("CODEX_COMPOSER_STATE_DIR", str(STATE_DIR))
    )
    if not _TOKEN.fullmatch(instance):
        raise ControlConfigurationError("invalid configured instance")
    if not _SHA256.fullmatch(card) or not _SHA256.fullmatch(memory):
        raise ControlConfigurationError("invalid configured identity digest")
    if not state_dir.is_absolute() or state_dir != STATE_DIR:
        raise ControlConfigurationError("mobile control requires the fixed state directory")
    return ControlConfig(instance, card, memory, state_dir=state_dir)


def _parse_timestamp(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).timestamp()


def evaluate_health(
    config: ControlConfig,
    heartbeat: Mapping[str, Any] | None,
    *,
    service_active: bool,
    service_enabled: bool,
    now_epoch: float,
) -> HealthSnapshot:
    reasons: list[str] = []
    if not service_active:
        reasons.append("service_inactive")
    if not service_enabled:
        reasons.append("service_disabled")
    if heartbeat is None:
        reasons.append("heartbeat_unreadable")
        return HealthSnapshot(False, tuple(reasons), service_active, service_enabled)

    observed_at = heartbeat.get("observed_at")
    observed_epoch = _parse_timestamp(observed_at)
    age: float | None = None
    if observed_epoch is None:
        reasons.append("heartbeat_timestamp_invalid")
    else:
        age = now_epoch - observed_epoch
        if age < -FUTURE_SKEW_SECONDS:
            reasons.append("heartbeat_from_future")
        elif age > config.freshness_seconds:
            reasons.append("heartbeat_stale")

    seat = heartbeat.get("seat") if isinstance(heartbeat.get("seat"), Mapping) else {}
    if heartbeat.get("agent_uid") != AGENT_UID:
        reasons.append("agent_uid_mismatch")
    if heartbeat.get("instance_id") != config.instance_id:
        reasons.append("instance_mismatch")
    if heartbeat.get("card_sha256") != config.card_sha256:
        reasons.append("card_digest_mismatch")
    if heartbeat.get("memory_sha256") != config.memory_sha256:
        reasons.append("memory_digest_mismatch")
    if heartbeat.get("status") != "online":
        reasons.append("replica_not_online")
    if seat.get("ready") is not True or seat.get("state") != "ready":
        reasons.append("seat_not_ready")
    if seat.get("tmux_session") != AGENT_UID:
        reasons.append("seat_session_mismatch")

    sequence = heartbeat.get("sequence")
    return HealthSnapshot(
        not reasons,
        tuple(reasons),
        service_active,
        service_enabled,
        status=str(heartbeat.get("status", "missing"))[:32],
        observed_at=str(observed_at or "")[:64],
        heartbeat_age_seconds=round(age, 3) if age is not None else None,
        boot_id=str(heartbeat.get("boot_id", ""))[:64],
        sequence=sequence if isinstance(sequence, int) and sequence >= 0 else None,
        seat_state=str(seat.get("state", ""))[:64],
    )


def probe_health(
    config: ControlConfig,
    *,
    now_epoch: float | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    required_uid: int | None = 0,
) -> HealthSnapshot:
    active = runner([SYSTEMCTL, "is-active", "--quiet", UNIT], timeout=10).returncode == 0
    enabled = runner([SYSTEMCTL, "is-enabled", "--quiet", UNIT], timeout=10).returncode == 0
    heartbeat: Mapping[str, Any] | None = None
    try:
        loaded = json.loads(
            _read_regular_bytes(
                config.heartbeat_file,
                required_uid=required_uid,
            ).decode("utf-8")
        )
        if isinstance(loaded, dict):
            heartbeat = loaded
    except (OSError, UnicodeError, ValueError, ControlConfigurationError):
        heartbeat = None
    return evaluate_health(
        config,
        heartbeat,
        service_active=active,
        service_enabled=enabled,
        now_epoch=time.time() if now_epoch is None else now_epoch,
    )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    try:
        data = json.dumps(payload, sort_keys=True).encode("utf-8") + b"\n"
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)


def _rotate_receipts(path: Path, *, max_bytes: int = 5 * 1024 * 1024) -> None:
    if not path.exists() or path.stat().st_size < max_bytes:
        return
    path.with_name(f"{path.name}.4").unlink(missing_ok=True)
    for index in range(3, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        if source.exists():
            source.replace(path.with_name(f"{path.name}.{index + 1}"))
    path.replace(path.with_name(f"{path.name}.1"))


def _append_receipt(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _rotate_receipts(path)
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_APPEND
        | os.O_CREAT
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise ControlConfigurationError("receipt log is not private and regular")
        os.write(descriptor, _canonical_bytes(payload) + b"\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(
        path,
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise ControlConfigurationError("control lock is not private and regular")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _cooldown_remaining(
    config: ControlConfig,
    now_epoch: float,
    *,
    required_uid: int | None = 0,
) -> float:
    try:
        payload = json.loads(
            _read_regular_bytes(
                config.cooldown_file, required_uid=required_uid
            ).decode("utf-8")
        )
        if not isinstance(payload, dict) or payload.get("instance_id") != config.instance_id:
            raise ControlConfigurationError("cooldown state targets the wrong instance")
        raw_previous = payload.get("reconcile_started_epoch")
        if isinstance(raw_previous, bool) or not isinstance(raw_previous, (int, float)):
            raise ControlConfigurationError("invalid cooldown timestamp")
        previous = float(raw_previous)
        if (
            not math.isfinite(previous)
            or previous < 0
            or not math.isfinite(now_epoch)
            or previous > now_epoch + 30
        ):
            raise ControlConfigurationError("invalid cooldown timestamp")
    except FileNotFoundError:
        return 0.0
    except (OSError, UnicodeError, ValueError, TypeError, ControlConfigurationError) as exc:
        raise ControlConfigurationError("invalid cooldown state") from exc
    return max(0.0, config.cooldown_seconds - (now_epoch - previous))


def _result_payload(
    config: ControlConfig,
    *,
    operation: str,
    result: str,
    action: str,
    snapshot: HealthSnapshot,
    before: HealthSnapshot | None = None,
    cooldown_remaining: float = 0.0,
    request_id: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": "dharma.codex_composer.mobile_control.v1",
        "agent_uid": AGENT_UID,
        "instance_id": config.instance_id,
        "operation": operation,
        "result": result,
        "action": action,
        "healthy": snapshot.healthy,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "health": asdict(snapshot),
    }
    if request_id:
        payload["request_id"] = request_id
    if before is not None:
        payload["before"] = asdict(before)
    if cooldown_remaining:
        payload["cooldown_remaining_seconds"] = round(cooldown_remaining, 3)
    payload["receipt_sha256"] = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    return payload


def run_status(
    config: ControlConfig, *, request_id: str = ""
) -> tuple[dict[str, Any], int]:
    # Status never mutates the supervised service, but it does append one
    # bounded local audit record. Serialize that record with reconciliation so
    # concurrent phone/scheduled probes cannot race log rotation.
    with _exclusive_lock(config.lock_file):
        snapshot = probe_health(config)
        result = "healthy_noop" if snapshot.healthy else "reported_unhealthy"
        payload = _result_payload(
            config,
            operation="status",
            result=result,
            action="none",
            snapshot=snapshot,
            request_id=request_id,
        )
        _append_receipt(config.receipt_file, payload)
        return payload, 0 if snapshot.healthy else 3


def run_reconcile(
    config: ControlConfig,
    *,
    probe: Callable[[ControlConfig], HealthSnapshot] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = _run,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    request_id: str = "",
) -> tuple[dict[str, Any], int]:
    health_probe = probe or probe_health
    with _exclusive_lock(config.lock_file):
        before = health_probe(config)
        if before.healthy:
            payload = _result_payload(
                config,
                operation="reconcile",
                result="healthy_noop",
                action="none",
                snapshot=before,
                before=before,
                request_id=request_id,
            )
            _append_receipt(config.receipt_file, payload)
            return payload, 0

        now_epoch = clock()
        remaining = _cooldown_remaining(config, now_epoch)
        if remaining:
            payload = _result_payload(
                config,
                operation="reconcile",
                result="cooldown",
                action="none",
                snapshot=before,
                before=before,
                cooldown_remaining=remaining,
                request_id=request_id,
            )
            _append_receipt(config.receipt_file, payload)
            return payload, 3

        _atomic_json(
            config.cooldown_file,
            {"reconcile_started_epoch": now_epoch, "instance_id": config.instance_id},
        )
        action = "restart" if before.service_active else "start"
        runner([SYSTEMCTL, "reset-failed", UNIT], timeout=15)
        invoked = runner([SYSTEMCTL, action, UNIT], timeout=30)
        if invoked.returncode != 0:
            payload = _result_payload(
                config,
                operation="reconcile",
                result="systemd_action_failed",
                action=action,
                snapshot=before,
                before=before,
                request_id=request_id,
            )
            _append_receipt(config.receipt_file, payload)
            return payload, 3

        deadline = clock() + config.verify_timeout_seconds
        after = before
        while clock() < deadline:
            sleeper(2.0)
            after = health_probe(config)
            if after.healthy:
                break
        result = "reconciled_verified" if after.healthy else "reconcile_unverified"
        payload = _result_payload(
            config,
            operation="reconcile",
            result=result,
            action=action,
            snapshot=after,
            before=before,
            request_id=request_id,
        )
        _append_receipt(config.receipt_file, payload)
        return payload, 0 if after.healthy else 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("status", "reconcile", "ssh-gate"))
    parser.add_argument("expected_operation", nargs="?", choices=("status", "reconcile"))
    return parser


def validate_ssh_original_command(
    config: ControlConfig,
    expected_operation: str,
    *,
    environ: Mapping[str, str] | None = None,
    now_epoch: float | None = None,
) -> tuple[str, str]:
    env = os.environ if environ is None else environ
    original = str(env.get("SSH_ORIGINAL_COMMAND", ""))
    if not original or len(original.encode("utf-8", errors="replace")) > 256:
        raise ControlConfigurationError("invalid SSH original command")
    try:
        original.encode("ascii", errors="strict")
    except UnicodeError as exc:
        raise ControlConfigurationError("invalid SSH original command") from exc
    match = _SSH_COMMAND.fullmatch(original)
    if match is None:
        raise ControlConfigurationError("invalid SSH original command")
    operation, request_id, issued_text, expires_text = match.groups()
    if operation != expected_operation or not _REQUEST_ID.fullmatch(request_id):
        raise ControlConfigurationError("SSH operation mismatch")
    if not request_id.endswith(f"-{config.instance_id}"):
        raise ControlConfigurationError("SSH request targets the wrong instance")
    issued = int(issued_text)
    expires = int(expires_text)
    now = time.time() if now_epoch is None else now_epoch
    if issued > now + 30 or expires < now or not 1 <= expires - issued <= 300:
        raise ControlConfigurationError("SSH request is stale or outside its TTL")
    return operation, request_id


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if os.geteuid() != 0:
        print(
            json.dumps(
                {
                    "schema": "dharma.codex_composer.mobile_control.v1",
                    "result": "root_required",
                    "healthy": False,
                },
                sort_keys=True,
            )
        )
        return 2
    try:
        config = load_config()
        operation = arguments.operation
        request_id = ""
        if operation == "ssh-gate":
            if arguments.expected_operation is None:
                raise ControlConfigurationError("SSH gate requires a fixed operation")
            operation, request_id = validate_ssh_original_command(
                config, arguments.expected_operation
            )
        elif arguments.expected_operation is not None:
            raise ControlConfigurationError("unexpected operation argument")
        payload, exit_code = (
            run_status(config, request_id=request_id)
            if operation == "status"
            else run_reconcile(config, request_id=request_id)
        )
    except (ControlConfigurationError, OSError, subprocess.SubprocessError):
        payload = {
            "schema": "dharma.codex_composer.mobile_control.v1",
            "result": "control_configuration_error",
            "healthy": False,
        }
        exit_code = 2
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
