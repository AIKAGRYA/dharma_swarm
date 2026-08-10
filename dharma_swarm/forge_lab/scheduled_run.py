"""Fixed-state adapter used by the disabled-by-default RSI systemd timer."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
from typing import Any
from uuid import uuid4

from dharma_swarm.forge_lab.campaign_contract import resolve_state_root
from dharma_swarm.forge_lab.run_guard import (
    RunGuard,
    RunGuardError,
    host_resources,
    require_host_resources,
)


SCHEDULE_SCHEMA = "forge_lab.unattended_schedule.v1"
ATTEMPT_SCHEMA = "forge_lab.unattended_attempt.v1"
_CONFIG_KEYS = {
    "schema",
    "enabled",
    "manifest_digest",
    "operator_envelope_path",
    "identity_receipt_path",
    "provider_receipt_path",
    "min_mem_available_bytes",
    "min_swap_free_bytes",
    "max_load_per_cpu",
}
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
UNATTENDED_WALL_SECONDS = 21_000
# These are code-owned safety minimums, not suggestions in an operator file.
# A schedule may demand more memory/swap or a lower load, but it may never
# weaken the compiled unattended boundary.
MIN_UNATTENDED_MEM_AVAILABLE_BYTES = 900 * 1024 * 1024
MIN_UNATTENDED_SWAP_FREE_BYTES = 256 * 1024 * 1024
MAX_UNATTENDED_LOAD_PER_CPU = 2.0


class ScheduledRunError(RuntimeError):
    def __init__(self, code: str, message: str, *, result: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.result = result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid4().hex}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
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


def _private_regular(path: Path, *, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ScheduledRunError("SCHEDULE_EVIDENCE_MISSING", f"{label} is unavailable: {exc}") from exc
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise ScheduledRunError("SCHEDULE_EVIDENCE_UNSAFE", f"{label} must be a regular non-symlink file")
    if metadata.st_mode & 0o077:
        raise ScheduledRunError("SCHEDULE_EVIDENCE_UNSAFE", f"{label} must not be group/world accessible")


def _evidence_path(root: Path, raw: Any, *, label: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ScheduledRunError("INVALID_SCHEDULE", f"{label} must be an absolute path")
    candidate = Path(raw)
    if not candidate.is_absolute():
        raise ScheduledRunError("INVALID_SCHEDULE", f"{label} must be an absolute path")
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ScheduledRunError("SCHEDULE_EVIDENCE_MISSING", f"{label} is unavailable: {exc}") from exc
    if not resolved.is_relative_to(resolved_root):
        raise ScheduledRunError("SCHEDULE_EVIDENCE_OUTSIDE_STATE", f"{label} must remain inside canonical state")
    _private_regular(candidate, label=label)
    return candidate


def _load_schedule(root: Path) -> tuple[dict[str, Any], Path]:
    path = root / ".dharma" / "forge_lab" / "schedule" / "active.json"
    _private_regular(path, label="schedule")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScheduledRunError("INVALID_SCHEDULE", f"schedule JSON is invalid: {exc}") from exc
    if not isinstance(value, dict) or set(value) != _CONFIG_KEYS:
        raise ScheduledRunError("INVALID_SCHEDULE", "schedule has a non-exact shape")
    if value["schema"] != SCHEDULE_SCHEMA:
        raise ScheduledRunError("INVALID_SCHEDULE", "schedule schema is unsupported")
    if value["enabled"] is not True:
        raise ScheduledRunError("SCHEDULE_DISABLED", "unattended RSI execution is not enabled")
    if not isinstance(value["manifest_digest"], str) or not _DIGEST.fullmatch(value["manifest_digest"]):
        raise ScheduledRunError("INVALID_SCHEDULE", "manifest_digest is invalid")
    byte_floors = {
        "min_mem_available_bytes": MIN_UNATTENDED_MEM_AVAILABLE_BYTES,
        "min_swap_free_bytes": MIN_UNATTENDED_SWAP_FREE_BYTES,
    }
    for field, compiled_floor in byte_floors.items():
        amount = value[field]
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < compiled_floor:
            raise ScheduledRunError(
                "INVALID_SCHEDULE",
                f"{field} must be at least the compiled floor {compiled_floor}",
            )
    load = value["max_load_per_cpu"]
    if (
        not isinstance(load, (int, float))
        or isinstance(load, bool)
        or not 0 < float(load) <= MAX_UNATTENDED_LOAD_PER_CPU
    ):
        raise ScheduledRunError(
            "INVALID_SCHEDULE",
            f"max_load_per_cpu must be in (0, {MAX_UNATTENDED_LOAD_PER_CPU}]",
        )
    return value, path


def run_unattended(*, state_root: Path | None = None) -> dict[str, Any]:
    """Run exactly the fixed canonical schedule; no CLI-supplied paths are accepted."""

    from dharma_swarm.forge_lab import campaign_control

    root = state_root or resolve_state_root()
    if not root.is_absolute():
        raise ScheduledRunError("STATE_ROOT_NOT_ABSOLUTE", "canonical state must be absolute")
    attempt_id = f"{_now().replace(':', '').replace('-', '')}-{uuid4().hex}"
    attempts = root / ".dharma" / "forge_lab" / "schedule" / "attempts"
    receipt_path = attempts / f"{attempt_id}.json"
    payload: dict[str, Any] = {
        "schema": ATTEMPT_SCHEMA,
        "attempt_id": attempt_id,
        "started_at": _now(),
        "finished_at": None,
        "status": "starting",
        "schedule_path": str(root / ".dharma" / "forge_lab" / "schedule" / "active.json"),
        "manifest_digest": None,
        "campaign_receipt": None,
        "error": None,
        "receipt_path": str(receipt_path),
    }
    try:
        schedule, schedule_path = _load_schedule(root)
        payload["schedule_path"] = str(schedule_path)
        payload["manifest_digest"] = schedule["manifest_digest"]
        require_host_resources(
            host_resources(),
            min_mem_available_bytes=schedule["min_mem_available_bytes"],
            min_swap_free_bytes=schedule["min_swap_free_bytes"],
            max_load_per_cpu=float(schedule["max_load_per_cpu"]),
        )
        envelope = _evidence_path(root, schedule["operator_envelope_path"], label="operator envelope")
        identity = _evidence_path(root, schedule["identity_receipt_path"], label="identity receipt")
        provider = _evidence_path(root, schedule["provider_receipt_path"], label="provider receipt")
        request_id = f"scheduled-{schedule['manifest_digest'][-16:]}"
        manifest = campaign_control.load_manifest(schedule["manifest_digest"], state_root=root)
        release_commit = str((manifest.get("source") or {}).get("release_commit") or "")
        campaign_id = str(manifest.get("campaign_name") or "")
        with RunGuard(
            root,
            campaign_id=campaign_id,
            request_id=request_id,
            release_commit=release_commit,
            config_digest=schedule["manifest_digest"],
            wall_seconds=UNATTENDED_WALL_SECONDS,
        ) as guard:
            guard.checkpoint()
            result = campaign_control.run_campaign(
                schedule["manifest_digest"],
                request_id=request_id,
                envelope_path=str(envelope),
                identity_receipt_path=str(identity),
                provider_receipt_path=str(provider),
                state_root=root,
            )
            payload["campaign_receipt"] = result.get("receipt_path")
            if result.get("disposition") != "COMPLETED":
                raise ScheduledRunError(
                    "SCHEDULED_CAMPAIGN_BLOCKED",
                    "governed campaign did not complete",
                    result=result,
                )
        payload["status"] = "succeeded"
    except Exception as exc:
        known_refusal = isinstance(exc, (ScheduledRunError, RunGuardError))
        payload["status"] = "blocked" if known_refusal else "failed"
        payload["error"] = {
            "code": getattr(exc, "code", "SCHEDULED_RUN_FAILURE"),
            "message": str(exc),
        }
        payload["finished_at"] = _now()
        _atomic_json(receipt_path, payload)
        if isinstance(exc, ScheduledRunError):
            exc.result = {"attempt": payload, "cause": exc.result}
            raise
        if isinstance(exc, RunGuardError):
            raise ScheduledRunError(
                exc.code,
                str(exc),
                result={"attempt": payload, "cause": exc.detail},
            ) from exc
        raise ScheduledRunError(
            "SCHEDULED_RUN_FAILURE", str(exc), result={"attempt": payload}
        ) from exc
    payload["finished_at"] = _now()
    _atomic_json(receipt_path, payload)
    return payload


__all__ = [
    "ATTEMPT_SCHEMA",
    "MAX_UNATTENDED_LOAD_PER_CPU",
    "MIN_UNATTENDED_MEM_AVAILABLE_BYTES",
    "MIN_UNATTENDED_SWAP_FREE_BYTES",
    "SCHEDULE_SCHEMA",
    "UNATTENDED_WALL_SECONDS",
    "ScheduledRunError",
    "run_unattended",
]
