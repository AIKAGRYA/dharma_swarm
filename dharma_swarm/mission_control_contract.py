"""Typed contract and identity helpers for Dharma Mission Control."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from dharma_swarm.models import TaskPriority, TaskStatus
from dharma_swarm.runtime_state import TaskClaim


SCHEMA_VERSION = "dharma.mission_control.v1"
SESSION_PREFIX = "mission:"
OPEN_CLAIM_STATUSES = frozenset(
    {"active", "claimed", "acknowledged", "running", "leased"}
)
ACTIVE_CLAIM_STATUSES = OPEN_CLAIM_STATUSES - {"claimed"}
PUBLIC_TERMINAL_ATTEMPT_STATUSES = frozenset({"succeeded", "failed"})
OWNER_TERMINAL_ATTEMPT_STATUSES = frozenset(
    {"completed", "failed", "stale_recovered"}
)
TERMINAL_RECEIPT_TYPE = "mission_attempt_terminal"
RECOVERY_RECEIPT_TYPE = "mission_attempt_recovery"
TASK_SCAN_LIMIT = 10_000
RUNTIME_SCAN_LIMIT = 10_000
TERMINAL_CAS_STALE_AFTER_SECONDS = 30.0


class MissionControlError(RuntimeError):
    """Raised when a Mission Control identity or lifecycle invariant fails."""


class ReconciliationState(str, Enum):
    """Honest relationship between canonical runtime and task projections."""

    COHERENT = "coherent"
    NEEDS_TASK_PROJECTION = "needs_task_projection"
    MISSING_TERMINAL_RECEIPT = "missing_terminal_receipt"
    CONFLICTING_ACTIVE_CLAIMS = "conflicting_active_claims"
    ACTIVE_CLAIM_WITHOUT_RUN = "active_claim_without_run"
    EXPIRED_LEASE = "expired_lease"
    FOREIGN_RUNTIME_RECORD = "foreign_runtime_record"
    CONFLICTING_TERMINAL_EVIDENCE = "conflicting_terminal_evidence"


@dataclass(frozen=True, slots=True)
class MissionView:
    mission_id: str
    session_id: str
    title: str
    goal: str
    operator_id: str
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TaskView:
    task_id: str
    mission_id: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    assigned_to: str
    result: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AttemptView:
    attempt_id: str
    mission_id: str
    session_id: str
    task_id: str
    claim_id: str
    assigned_to: str
    assigned_by: str
    status: str
    failure_code: str
    idempotency_key: str
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AgentLeaseView:
    claim_id: str
    mission_id: str
    session_id: str
    task_id: str
    agent_id: str
    attempt_id: str
    status: str
    active: bool
    expired: bool
    heartbeat_at: datetime | None = None
    stale_after: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReceiptView:
    receipt_id: str
    mission_id: str
    task_id: str
    attempt_id: str
    agent_id: str
    receipt_type: str
    status: str
    idempotency_key: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MissionSnapshot:
    mission: MissionView
    tasks: tuple[TaskView, ...]
    attempts: tuple[AttemptView, ...]
    leases: tuple[AgentLeaseView, ...]
    receipts: tuple[ReceiptView, ...]
    reconciliation: ReconciliationState
    observed_at: datetime
    authority: str = "TaskBoard+RuntimeStateStore"
    proves_executor_liveness: bool = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clean_identifier(value: str, label: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise MissionControlError(f"{label} is required")
    if any(char.isspace() for char in cleaned):
        raise MissionControlError(f"{label} must not contain whitespace")
    return cleaned


def session_id(mission_id: str) -> str:
    return f"{SESSION_PREFIX}{clean_identifier(mission_id, 'mission_id')}"


def stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def claim_is_expired(claim: TaskClaim, now: datetime) -> bool:
    return claim.stale_after is not None and claim.stale_after <= now


def claim_is_active(claim: TaskClaim, now: datetime) -> bool:
    return (
        claim.status.lower() in ACTIVE_CLAIM_STATUSES
        and claim.acked_at is not None
        and not claim_is_expired(claim, now)
    )


def claim_is_open(claim: TaskClaim, now: datetime) -> bool:
    return claim.status.lower() in OPEN_CLAIM_STATUSES and not claim_is_expired(
        claim, now
    )


def public_attempt_status(owner_status: str) -> str:
    return "succeeded" if owner_status == "completed" else owner_status


__all__ = [
    "ACTIVE_CLAIM_STATUSES",
    "AgentLeaseView",
    "AttemptView",
    "MissionControlError",
    "MissionSnapshot",
    "MissionView",
    "OPEN_CLAIM_STATUSES",
    "OWNER_TERMINAL_ATTEMPT_STATUSES",
    "PUBLIC_TERMINAL_ATTEMPT_STATUSES",
    "RECOVERY_RECEIPT_TYPE",
    "RUNTIME_SCAN_LIMIT",
    "ReceiptView",
    "ReconciliationState",
    "SCHEMA_VERSION",
    "TASK_SCAN_LIMIT",
    "TERMINAL_CAS_STALE_AFTER_SECONDS",
    "TERMINAL_RECEIPT_TYPE",
    "TaskView",
    "claim_is_active",
    "claim_is_expired",
    "claim_is_open",
    "clean_identifier",
    "public_attempt_status",
    "session_id",
    "stable_id",
    "utc_now",
]
