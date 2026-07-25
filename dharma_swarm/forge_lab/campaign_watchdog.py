"""External, closure-only watchdog for governed Forge Lab campaigns.

The worker deliberately has no provider imports, credentials, or dispatch API.
It observes controller-owned JSON files and can only change an exact, current
authority gate from open to closed.  All writers of the gate and heartbeat
should use the same ``watchdog.lock`` file.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Iterator
from uuid import uuid4


GATE_SCHEMA = "forge_lab.campaign_authority_gate.v1"
HEARTBEAT_SCHEMA = "forge_lab.watchdog_heartbeat.v1"
TRIP_SCHEMA = "forge_lab.watchdog_trip.v1"
EVENT_SCHEMA = "forge_lab.watchdog_event.v1"

EXIT_OK = 0
EXIT_TRIPPED = 10
EXIT_STALE = 11
EXIT_INVALID = 12

_CAMPAIGN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class WatchdogError(RuntimeError):
    """A fail-closed watchdog configuration or state error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _parse_timestamp(value: str, *, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise WatchdogError("INVALID_TIMESTAMP", f"{field} must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WatchdogError("INVALID_TIMESTAMP", f"{field} is not RFC3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise WatchdogError("INVALID_TIMESTAMP", f"{field} must be UTC")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class WatchdogConfig:
    """Identity and hard-stop policy observed by one watchdog fence."""

    state_root: Path
    campaign_id: str
    manifest_digest: str
    fence: int
    deadline: str
    heartbeat_timeout_s: float
    poll_interval_s: float = 0.25

    def __post_init__(self) -> None:
        root = Path(self.state_root)
        if not root.is_absolute():
            raise WatchdogError("INVALID_STATE_ROOT", "state_root must be explicit and absolute")
        if not _CAMPAIGN_RE.fullmatch(self.campaign_id):
            raise WatchdogError("INVALID_CAMPAIGN_ID", "campaign_id is not path-safe")
        if not _DIGEST_RE.fullmatch(self.manifest_digest):
            raise WatchdogError("INVALID_MANIFEST_DIGEST", "manifest_digest must be sha256:<hex>")
        if isinstance(self.fence, bool) or not isinstance(self.fence, int) or self.fence < 1:
            raise WatchdogError("INVALID_FENCE", "fence must be a positive integer")
        _parse_timestamp(self.deadline, field="deadline")
        if self.heartbeat_timeout_s <= 0:
            raise WatchdogError("INVALID_HEARTBEAT_TIMEOUT", "heartbeat timeout must be positive")
        if self.poll_interval_s <= 0 or self.poll_interval_s > self.heartbeat_timeout_s:
            raise WatchdogError(
                "INVALID_POLL_INTERVAL",
                "poll interval must be positive and no greater than heartbeat timeout",
            )
        object.__setattr__(self, "state_root", root.resolve())

    @property
    def deadline_at(self) -> datetime:
        return _parse_timestamp(self.deadline, field="deadline")


def campaign_control_dir(state_root: Path, campaign_id: str) -> Path:
    """Return the interoperable controller/watchdog directory (no HOME fallback)."""

    root = Path(state_root)
    if not root.is_absolute():
        raise WatchdogError("INVALID_STATE_ROOT", "state_root must be explicit and absolute")
    if not _CAMPAIGN_RE.fullmatch(campaign_id):
        raise WatchdogError("INVALID_CAMPAIGN_ID", "campaign_id is not path-safe")
    return root.resolve() / ".dharma" / "forge_lab" / "campaigns" / campaign_id / "control"


def authority_gate_path(state_root: Path, campaign_id: str) -> Path:
    return campaign_control_dir(state_root, campaign_id) / "authority_gate.json"


def heartbeat_path(state_root: Path, campaign_id: str) -> Path:
    return campaign_control_dir(state_root, campaign_id) / "heartbeat.json"


def _paths(config: WatchdogConfig) -> dict[str, Path]:
    control = campaign_control_dir(config.state_root, config.campaign_id)
    campaign = control.parent
    suffix = f"fence-{config.fence:020d}.json"
    return {
        "control": control,
        "gate": control / "authority_gate.json",
        "heartbeat": control / "heartbeat.json",
        "lock": control / "watchdog.lock",
        "current_trip": control / "watchdog_trip.json",
        "trip": campaign / "receipts" / "watchdog" / suffix,
        "event": campaign / "events" / f"watchdog-{suffix}",
    }


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid4().hex}")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            os.fsync(directory_fd)
            os.close(directory_fd)
        except OSError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise WatchdogError("UNSAFE_STATE_PATH", f"refusing symlink state file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WatchdogError("STATE_MISSING", f"required state file is missing: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise WatchdogError("STATE_INVALID", f"cannot read state file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WatchdogError("STATE_INVALID", f"state file must contain an object: {path}")
    return payload


@contextmanager
def authority_lock(state_root: Path, campaign_id: str) -> Iterator[None]:
    """Serialize controller heartbeats and watchdog gate closure."""

    control = campaign_control_dir(state_root, campaign_id)
    control.mkdir(parents=True, exist_ok=True)
    lock_path = control / "watchdog.lock"
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _identity_status(gate: dict[str, Any], config: WatchdogConfig) -> str | None:
    if gate.get("campaign_id") != config.campaign_id:
        return "campaign_mismatch"
    if gate.get("manifest_digest") != config.manifest_digest:
        return "manifest_mismatch"
    gate_fence = gate.get("fence")
    if isinstance(gate_fence, bool) or not isinstance(gate_fence, int):
        return "invalid_gate_fence"
    if gate_fence > config.fence:
        return "stale_watchdog_fence"
    if gate_fence < config.fence:
        return "uninstalled_watchdog_fence"
    return None


def _decision(config: WatchdogConfig, status: str, **extra: Any) -> dict[str, Any]:
    return {
        "schema": "forge_lab.watchdog_decision.v1",
        "campaign_id": config.campaign_id,
        "manifest_digest": config.manifest_digest,
        "fence": config.fence,
        "status": status,
        **extra,
    }


def _receipt_from_closure(
    config: WatchdogConfig, closure: dict[str, Any], *, gate_revision: int
) -> dict[str, Any]:
    payload = {
        "schema": TRIP_SCHEMA,
        "campaign_id": config.campaign_id,
        "manifest_digest": config.manifest_digest,
        "fence": config.fence,
        "reason": closure["reason"],
        "observed_at": closure["observed_at"],
        "deadline": config.deadline,
        "heartbeat_timeout_s": config.heartbeat_timeout_s,
        "last_heartbeat_at": closure.get("last_heartbeat_at"),
        "watchdog_pid": closure["watchdog_pid"],
        "authority_scope": "close_provider_dispatch_only",
        "provider_dispatch_authority": False,
        "gate_revision": gate_revision,
    }
    payload["receipt_digest"] = f"sha256:{hashlib.sha256(_canonical_json(payload)).hexdigest()}"
    return payload


def _ensure_trip_artifacts(
    config: WatchdogConfig, closure: dict[str, Any], *, gate_revision: int
) -> dict[str, Any]:
    paths = _paths(config)
    receipt = _receipt_from_closure(config, closure, gate_revision=gate_revision)
    if paths["trip"].exists():
        existing = _read_json(paths["trip"])
        if existing.get("receipt_digest") != receipt["receipt_digest"]:
            raise WatchdogError("TRIP_CONFLICT", "immutable watchdog trip receipt conflicts")
        receipt = existing
    else:
        _atomic_json(paths["trip"], receipt)
    event = {
        "schema": EVENT_SCHEMA,
        "event_type": "WATCHDOG_AUTHORITY_CLOSED",
        "campaign_id": config.campaign_id,
        "manifest_digest": config.manifest_digest,
        "fence": config.fence,
        "observed_at": receipt["observed_at"],
        "reason": receipt["reason"],
        "receipt_digest": receipt["receipt_digest"],
        "authority_scope": "close_provider_dispatch_only",
    }
    if not paths["event"].exists():
        _atomic_json(paths["event"], event)
    if not paths["current_trip"].exists() or _read_json(paths["current_trip"]) != receipt:
        _atomic_json(paths["current_trip"], receipt)
    return receipt


def _trip(
    config: WatchdogConfig,
    gate: dict[str, Any],
    *,
    reason: str,
    observed_at: datetime,
    last_heartbeat_at: str | None,
) -> dict[str, Any]:
    revision = gate.get("revision", 0)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        revision = 0
    closure = {
        "reason": reason,
        "observed_at": _timestamp(observed_at),
        "last_heartbeat_at": last_heartbeat_at,
        "watchdog_pid": os.getpid(),
    }
    closed = dict(gate)
    closed.update(
        {
            "schema": GATE_SCHEMA,
            "dispatch_allowed": False,
            "authority_mode": "closed",
            "revision": revision + 1,
            "updated_at": closure["observed_at"],
            "watchdog_closure": closure,
        }
    )
    _atomic_json(_paths(config)["gate"], closed)
    receipt = _ensure_trip_artifacts(config, closure, gate_revision=revision + 1)
    return _decision(
        config,
        "tripped",
        reason=reason,
        receipt_digest=receipt["receipt_digest"],
        receipt_path=str(_paths(config)["trip"]),
    )


def watch_once(
    config: WatchdogConfig,
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Observe once and close only the exact current fence when a fuse is due."""

    now = (observed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    paths = _paths(config)
    initial_gate = _read_json(paths["gate"])
    mismatch = _identity_status(initial_gate, config)
    if mismatch:
        return _decision(config, "stale", reason=mismatch)
    with authority_lock(config.state_root, config.campaign_id):
        gate = _read_json(paths["gate"])
        mismatch = _identity_status(gate, config)
        if mismatch:
            return _decision(config, "stale", reason=mismatch)

        if paths["trip"].exists():
            receipt = _read_json(paths["trip"])
            if receipt.get("manifest_digest") != config.manifest_digest:
                raise WatchdogError("TRIP_CONFLICT", "trip receipt manifest mismatch")
            closure = {
                "reason": receipt["reason"],
                "observed_at": receipt["observed_at"],
                "last_heartbeat_at": receipt.get("last_heartbeat_at"),
                "watchdog_pid": receipt["watchdog_pid"],
            }
            if gate.get("dispatch_allowed") is True:
                gate = dict(gate)
                gate["dispatch_allowed"] = False
                gate["authority_mode"] = "closed"
                gate["revision"] = max(int(gate.get("revision", 0)), receipt["gate_revision"])
                gate["watchdog_closure"] = closure
                _atomic_json(paths["gate"], gate)
            _ensure_trip_artifacts(config, closure, gate_revision=receipt["gate_revision"])
            return _decision(
                config,
                "already_tripped",
                reason=receipt["reason"],
                receipt_digest=receipt["receipt_digest"],
            )

        if gate.get("dispatch_allowed") is not True:
            closure = gate.get("watchdog_closure")
            required = {"reason", "observed_at", "watchdog_pid"}
            if isinstance(closure, dict) and required <= closure.keys():
                receipt = _ensure_trip_artifacts(
                    config, closure, gate_revision=int(gate.get("revision", 0))
                )
                return _decision(
                    config,
                    "already_tripped",
                    reason=receipt["reason"],
                    receipt_digest=receipt["receipt_digest"],
                )
            return _decision(config, "closed", reason="authority_gate_already_closed")

        def trip(reason: str, heartbeat_at: str | None = None) -> dict[str, Any]:
            return _trip(
                config,
                gate,
                reason=reason,
                observed_at=now,
                last_heartbeat_at=heartbeat_at,
            )

        if now >= config.deadline_at:
            return trip("DEADLINE_EXCEEDED")

        try:
            heartbeat = _read_json(paths["heartbeat"])
        except WatchdogError as exc:
            reason = "HEARTBEAT_MISSING" if exc.code == "STATE_MISSING" else "HEARTBEAT_INVALID"
            return trip(reason)
        heartbeat_fence = heartbeat.get("fence")
        if isinstance(heartbeat_fence, int) and heartbeat_fence > config.fence:
            return _decision(config, "stale", reason="newer_heartbeat_fence")
        if (
            heartbeat.get("campaign_id") != config.campaign_id
            or heartbeat.get("manifest_digest") != config.manifest_digest
            or heartbeat_fence != config.fence
        ):
            return trip("HEARTBEAT_IDENTITY_MISMATCH", heartbeat.get("observed_at"))
        try:
            heartbeat_at = _parse_timestamp(
                heartbeat.get("observed_at"), field="heartbeat.observed_at"
            )
        except WatchdogError:
            return trip("HEARTBEAT_INVALID", heartbeat.get("observed_at"))
        age = (now - heartbeat_at).total_seconds()
        if age < -5:
            return trip("HEARTBEAT_CLOCK_INVALID", _timestamp(heartbeat_at))
        if age >= config.heartbeat_timeout_s:
            return trip("HEARTBEAT_TIMEOUT", _timestamp(heartbeat_at))
        return _decision(config, "armed", heartbeat_age_s=max(0.0, age), deadline=config.deadline)


def record_heartbeat(
    config: WatchdogConfig, *, sequence: int, observed_at: datetime | None = None
) -> dict[str, Any]:
    """Controller-side fenced heartbeat writer; never opens an authority gate."""

    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise WatchdogError("INVALID_HEARTBEAT_SEQUENCE", "sequence must be positive")
    now = (observed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    paths = _paths(config)
    with authority_lock(config.state_root, config.campaign_id):
        gate = _read_json(paths["gate"])
        mismatch = _identity_status(gate, config)
        if mismatch:
            raise WatchdogError("STALE_FENCE", mismatch)
        if gate.get("dispatch_allowed") is not True:
            raise WatchdogError("AUTHORITY_CLOSED", "cannot heartbeat a closed authority gate")
        if paths["heartbeat"].exists():
            previous = _read_json(paths["heartbeat"])
            old = previous.get("sequence")
            if isinstance(old, int) and sequence <= old:
                if sequence == old:
                    return previous
                raise WatchdogError("STALE_HEARTBEAT", "heartbeat sequence must increase")
        payload = {
            "schema": HEARTBEAT_SCHEMA,
            "campaign_id": config.campaign_id,
            "manifest_digest": config.manifest_digest,
            "fence": config.fence,
            "sequence": sequence,
            "observed_at": _timestamp(now),
        }
        _atomic_json(paths["heartbeat"], payload)
        return payload


def run_watchdog(config: WatchdogConfig, *, once: bool = False) -> tuple[int, dict[str, Any]]:
    while True:
        decision = watch_once(config)
        status = decision["status"]
        if status == "armed" and not once:
            time.sleep(config.poll_interval_s)
            continue
        if status == "tripped":
            return EXIT_TRIPPED, decision
        if status == "stale":
            return EXIT_STALE, decision
        return EXIT_OK, decision


def spawn_watchdog(config: WatchdogConfig) -> Any:
    """Spawn the credential-free entrypoint in a separate process session."""

    from dharma_swarm.forge_lab.campaign_watchdog_cli import spawn_watchdog_process

    return spawn_watchdog_process(config)


def main(argv: list[str] | None = None) -> int:
    from dharma_swarm.forge_lab.campaign_watchdog_cli import main as cli_main

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
