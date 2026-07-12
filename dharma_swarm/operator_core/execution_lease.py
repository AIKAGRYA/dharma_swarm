"""File-backed execution leases for local A2A wake loops.

This module is intentionally small and boring.  It is not the superseded
``coordination_substrate`` lease stack; it is the Phase-A local lease primitive
described by the receipted A2A/NATS loop spec.

Version 1 is a scoped, checksummed local capability receipt.  Its
``content_hash`` detects accidental/tampered-at-rest changes; it is *not* an
operator signature and must not be represented as cryptographic authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "dharma.execution_lease.v1"
DEFAULT_FORBIDDEN_ACTIONS = (
    "external_contact",
    "spend",
    "git_push",
    "launchd_install",
    "broker_topology_change",
    "self_approve_execution_lease",
)
SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


class ExecutionLeaseError(RuntimeError):
    """Raised when a lease cannot be loaded or written safely."""


@dataclass(frozen=True)
class LeaseValidation:
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    lease_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "lease_id": self.lease_id,
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        raw = str(value)
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value


def content_hash(payload: Mapping[str, Any]) -> str:
    stable = {key: value for key, value in payload.items() if key != "content_hash"}
    encoded = json.dumps(_json_ready(stable), ensure_ascii=True, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def safe_lease_id(value: str) -> str:
    token = SAFE_TOKEN_RE.sub("_", str(value or "").strip()).strip("._")
    if not token:
        raise ExecutionLeaseError("lease_id is required")
    if token in {".", ".."} or "/" in token or "\\" in token:
        raise ExecutionLeaseError(f"unsafe lease_id: {value!r}")
    return token[:160]


def lease_path(root: str | Path, lease_id: str) -> Path:
    return Path(root).expanduser() / f"{safe_lease_id(lease_id)}.json"


def default_lease_root(dharma_home: str | Path | None = None) -> Path:
    if dharma_home is None:
        from dharma_swarm.daemon_config import dharma_state_dir

        return dharma_state_dir() / "a2a_bus" / "leases"
    return Path(dharma_home).expanduser() / "a2a_bus" / "leases"


def _as_list(values: Iterable[str] | None) -> list[str]:
    return [str(value) for value in (values or []) if str(value)]


def build_execution_lease(
    *,
    issued_to: str,
    issuer: str = "operator",
    task_id: str = "",
    correlation_id: str = "",
    custody_grade: str = "Q1",
    allowed_actions: Sequence[str] | None = None,
    allowed_paths: Sequence[str | Path] | None = None,
    forbidden_actions: Sequence[str] | None = None,
    max_seconds: int = 900,
    max_model_calls: int = 3,
    max_usd: float = 0.0,
    issued_at: str | datetime | None = None,
    expires_at: str | datetime | None = None,
    lease_id: str = "",
) -> dict[str, Any]:
    issued = parse_time(issued_at) or utc_now()
    expires = parse_time(expires_at) or (issued + timedelta(seconds=max_seconds))
    if not lease_id:
        seed = json.dumps(
            {
                "issued_to": issued_to,
                "issuer": issuer,
                "task_id": task_id,
                "correlation_id": correlation_id,
                "issued_at": issued.isoformat(),
                "expires_at": expires.isoformat(),
            },
            sort_keys=True,
        )
        lease_id = f"lease_{issued.strftime('%Y%m%dT%H%M%SZ')}_{hashlib.sha256(seed.encode()).hexdigest()[:12]}"
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "lease_id": safe_lease_id(lease_id),
        "issued_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
        "issuer": issuer,
        "issued_to": issued_to,
        "task_id": task_id,
        "correlation_id": correlation_id,
        "custody_grade": custody_grade,
        "allowed_actions": _as_list(allowed_actions),
        "allowed_paths": [str(Path(path).expanduser()) for path in (allowed_paths or [])],
        # Callers may add denials but cannot remove the baseline denials.
        "forbidden_actions": sorted(
            set(DEFAULT_FORBIDDEN_ACTIONS) | set(_as_list(forbidden_actions))
        ),
        "budget": {
            "max_seconds": int(max_seconds),
            "max_model_calls": int(max_model_calls),
            "max_usd": float(max_usd),
        },
        "verifier_policy": {
            "worker_cannot_self_verify": True,
            "required_verifiers": ["deterministic"],
        },
        "authority": "read_only_until_execution_lease",
    }
    payload["content_hash"] = content_hash(payload)
    return payload


def _path_allowed(path: str | Path, allowed_paths: Sequence[str]) -> bool:
    if not allowed_paths:
        return False
    candidate = Path(path).expanduser().resolve(strict=False)
    for allowed in allowed_paths:
        base = Path(allowed).expanduser().resolve(strict=False)
        if candidate == base or base in candidate.parents:
            return True
    return False


def validate_execution_lease(
    lease: Mapping[str, Any],
    *,
    now: str | datetime | None = None,
    agent_uid: str = "",
    task_id: str = "",
    requested_actions: Sequence[str] | None = None,
    requested_paths: Sequence[str | Path] | None = None,
    revoked_lease_ids: Iterable[str] | None = None,
) -> LeaseValidation:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(lease, Mapping):
        return LeaseValidation(False, ("lease must be an object",))
    lease_id = str(lease.get("lease_id") or "")
    if lease.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not lease_id:
        errors.append("lease_id is required")
    else:
        try:
            safe_lease_id(lease_id)
        except ExecutionLeaseError as exc:
            errors.append(str(exc))
    expected_hash = content_hash(lease)
    if lease.get("content_hash") != expected_hash:
        errors.append("content_hash does not match lease payload")
    issued_to = str(lease.get("issued_to") or "")
    if agent_uid and issued_to != agent_uid:
        errors.append(f"lease issued_to {issued_to!r} does not match agent {agent_uid!r}")
    lease_task_id = str(lease.get("task_id") or "")
    if task_id and lease_task_id and lease_task_id != task_id:
        errors.append(f"lease task_id {lease_task_id!r} does not match task {task_id!r}")
    issued_at = parse_time(lease.get("issued_at"))
    expires_at = parse_time(lease.get("expires_at"))
    current = parse_time(now) or utc_now()
    if issued_at is None:
        errors.append("issued_at is invalid or missing")
    if expires_at is None:
        errors.append("expires_at is invalid or missing")
    elif expires_at <= current:
        errors.append("lease is expired")
    if issued_at and expires_at and expires_at <= issued_at:
        errors.append("expires_at must be after issued_at")
    revoked = set(str(item) for item in (revoked_lease_ids or []))
    if lease_id and lease_id in revoked:
        errors.append("lease is revoked")

    raw_allowed_actions = lease.get("allowed_actions")
    raw_forbidden_actions = lease.get("forbidden_actions")
    if not isinstance(raw_allowed_actions, list):
        errors.append("allowed_actions must be a list")
        raw_allowed_actions = []
    if not isinstance(raw_forbidden_actions, list):
        errors.append("forbidden_actions must be a list")
        raw_forbidden_actions = []
    allowed_actions = set(str(item) for item in raw_allowed_actions)
    forbidden_actions = set(str(item) for item in raw_forbidden_actions)
    missing_baseline_denials = set(DEFAULT_FORBIDDEN_ACTIONS) - forbidden_actions
    if missing_baseline_denials:
        errors.append("forbidden_actions must include the baseline denials")
    if requested_actions and not allowed_actions:
        errors.append("requested actions require a non-empty allowed_actions scope")
    for action in requested_actions or []:
        action = str(action)
        if action in forbidden_actions:
            errors.append(f"requested action is forbidden: {action}")
        elif action not in allowed_actions:
            errors.append(f"requested action is not allowed: {action}")
    raw_allowed_paths = lease.get("allowed_paths")
    if not isinstance(raw_allowed_paths, list):
        errors.append("allowed_paths must be a list")
        raw_allowed_paths = []
    allowed_paths = [str(item) for item in raw_allowed_paths]
    if requested_paths and not allowed_paths:
        errors.append("requested paths require a non-empty allowed_paths scope")
    for path in requested_paths or []:
        if not _path_allowed(path, allowed_paths):
            errors.append(f"requested path is outside lease allowed_paths: {path}")
    budget = lease.get("budget")
    if not isinstance(budget, Mapping):
        errors.append("budget must be an object")
    elif float(budget.get("max_usd") or 0) > 0:
        warnings.append("lease permits nonzero spend")
    return LeaseValidation(not errors, tuple(errors), tuple(warnings), lease_id=lease_id)


def write_execution_lease(lease: Mapping[str, Any], root: str | Path) -> Path:
    validation = validate_execution_lease(lease)
    if not validation.valid:
        raise ExecutionLeaseError("; ".join(validation.errors))
    root_path = Path(root).expanduser()
    root_path.mkdir(parents=True, exist_ok=True)
    path = lease_path(root_path, validation.lease_id)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(_json_ready(dict(lease)), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    index = root_path / "index.jsonl"
    with index.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "event": "lease_written",
                    "lease_id": validation.lease_id,
                    "path": str(path),
                    "timestamp": iso_now(),
                    "issued_to": lease.get("issued_to"),
                    "task_id": lease.get("task_id"),
                },
                sort_keys=True,
            )
            + "\n"
        )
    return path


def load_execution_lease(root: str | Path, lease_id: str) -> dict[str, Any]:
    path = lease_path(root, lease_id)
    if not path.exists():
        raise ExecutionLeaseError(f"lease not found: {lease_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ExecutionLeaseError(f"lease payload is not an object: {lease_id}")
    return payload


def iter_execution_leases(root: str | Path) -> Iterable[tuple[Path, dict[str, Any]]]:
    """Yield lease JSON payloads from a lease root, skipping indexes.

    This is intentionally filesystem-backed for Phase A. It lets a delivered
    packet be matched to an operator-issued lease by task/correlation id without
    editing the packet after delivery.
    """
    root_path = Path(root).expanduser()
    if not root_path.exists():
        return
    for path in sorted(root_path.glob("*.json")):
        if path.name.startswith("."):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("schema_version") == SCHEMA_VERSION:
            yield path, payload


def find_execution_lease_for_task(
    root: str | Path,
    *,
    agent_uid: str,
    task_id: str = "",
    correlation_id: str = "",
    now: str | datetime | None = None,
) -> tuple[Path, dict[str, Any], LeaseValidation] | None:
    """Find a valid lease whose task or correlation id matches exactly."""
    if not task_id and not correlation_id:
        return None
    revoked = load_revoked_lease_ids(root)
    for path, lease in iter_execution_leases(root):
        lease_task_id = str(lease.get("task_id") or "")
        lease_correlation_id = str(lease.get("correlation_id") or "")
        task_matches = bool(task_id and lease_task_id and lease_task_id == task_id)
        correlation_matches = bool(correlation_id and lease_correlation_id and lease_correlation_id == correlation_id)
        if not task_matches and not correlation_matches:
            continue
        validation = validate_execution_lease(
            lease,
            now=now,
            agent_uid=agent_uid,
            task_id=task_id if task_matches else "",
            revoked_lease_ids=revoked,
        )
        if validation.valid:
            return path, lease, validation
    return None


def revocations_path(root: str | Path) -> Path:
    return Path(root).expanduser() / "revocations.jsonl"


def record_lease_revocation(root: str | Path, lease_id: str, *, reason: str = "") -> Path:
    root_path = Path(root).expanduser()
    root_path.mkdir(parents=True, exist_ok=True)
    path = revocations_path(root_path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "event": "lease_revoked",
                    "lease_id": safe_lease_id(lease_id),
                    "reason": reason,
                    "timestamp": iso_now(),
                },
                sort_keys=True,
            )
            + "\n"
        )
    return path


def load_revoked_lease_ids(root: str | Path) -> set[str]:
    path = revocations_path(root)
    if not path.exists():
        return set()
    revoked: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("lease_id"):
            revoked.add(str(payload["lease_id"]))
    return revoked
