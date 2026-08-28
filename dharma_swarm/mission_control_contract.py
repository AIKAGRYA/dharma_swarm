"""Typed contract and identity helpers for Dharma Mission Control."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from dharma_swarm.models import Task, TaskPriority, TaskStatus
from dharma_swarm.runtime_state import (
    DelegationRun,
    RuntimeReceipt,
    SessionState,
    TaskClaim,
)
from dharma_swarm.spine.identity import ExecutionIdentity


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
MAX_LEASE_SECONDS = 15 * 60
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
    EVIDENCE_SCAN_SATURATED = "evidence_scan_saturated"
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


def mission_view(session: SessionState) -> MissionView:
    mission_id = str(session.metadata.get("mission_id") or "")
    return MissionView(
        mission_id=mission_id,
        session_id=session.session_id,
        title=str(session.metadata.get("title") or ""),
        goal=str(session.metadata.get("goal") or ""),
        operator_id=session.operator_id,
        status=session.status,
        metadata=dict(session.metadata),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def task_view(task: Task, mission_id: str) -> TaskView:
    return TaskView(
        task_id=task.id,
        mission_id=mission_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        assigned_to=str(task.assigned_to or ""),
        result=str(task.result or ""),
        metadata=dict(task.metadata),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def attempt_view(
    run: DelegationRun, identity: ExecutionIdentity | None
) -> AttemptView:
    return AttemptView(
        attempt_id=run.run_id,
        mission_id=str(run.metadata.get("mission_id") or ""),
        session_id=run.session_id,
        task_id=run.task_id,
        claim_id=run.claim_id,
        assigned_to=run.assigned_to,
        assigned_by=run.assigned_by,
        status=public_attempt_status(run.status),
        failure_code=run.failure_code,
        idempotency_key=identity.idempotency_key if identity is not None else "",
        metadata=dict(run.metadata),
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def lease_view(claim: TaskClaim, *, now: datetime) -> AgentLeaseView:
    return AgentLeaseView(
        claim_id=claim.claim_id,
        mission_id=str(claim.metadata.get("mission_id") or ""),
        session_id=claim.session_id,
        task_id=claim.task_id,
        agent_id=claim.agent_id,
        attempt_id=str(claim.metadata.get("attempt_id") or ""),
        status=claim.status,
        active=claim_is_active(claim, now),
        expired=claim_is_expired(claim, now),
        heartbeat_at=claim.heartbeat_at,
        stale_after=claim.stale_after,
        metadata=dict(claim.metadata),
    )


def receipt_view(receipt: RuntimeReceipt, mission_id: str) -> ReceiptView:
    return ReceiptView(
        receipt_id=receipt.receipt_id,
        mission_id=str(receipt.payload.get("mission_id") or mission_id),
        task_id=receipt.task_id,
        attempt_id=receipt.run_id,
        agent_id=receipt.agent_id,
        receipt_type=receipt.receipt_type,
        status=receipt.status,
        idempotency_key=receipt.idempotency_key,
        payload=dict(receipt.payload),
        created_at=receipt.created_at,
    )


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


def receipt_matches_identity(
    receipt: RuntimeReceipt, identity: ExecutionIdentity
) -> bool:
    return (
        receipt.run_id == identity.run_id
        and receipt.task_id == identity.task_id
        and receipt.trace_id == identity.trace_id
        and receipt.correlation_id == identity.correlation_id
        and receipt.causation_id == identity.causation_id
        and receipt.parent_run_id == identity.parent_run_id
        and receipt.agent_id == identity.agent_id
        and receipt.idempotency_key == identity.idempotency_key
    )


def terminal_receipt_contract(
    receipt: RuntimeReceipt,
    identity: ExecutionIdentity,
    mission_id: str,
) -> tuple[str, str, str, str, dict[str, Any]]:
    """Validate terminal evidence and return its projection fields."""
    payload = receipt.payload
    metadata = payload.get("metadata")
    status = receipt.status
    if (
        not receipt_matches_identity(receipt, identity)
        or receipt.receipt_type != TERMINAL_RECEIPT_TYPE
        or status not in {"succeeded", "failed"}
        or receipt.receipt_id != stable_id("receipt", identity.run_id, status)
        or receipt.side_effect_key != f"mission_control:{identity.run_id}:terminal"
        or payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("mission_id") != mission_id
        or payload.get("attempt_id") != identity.run_id
        or not isinstance(payload.get("result"), str)
        or not isinstance(payload.get("failure_code"), str)
        or not isinstance(metadata, dict)
        or metadata.get("schema_version") != SCHEMA_VERSION
        or metadata.get("mission_id") != mission_id
        or metadata.get("attempt_id") != identity.run_id
        or metadata.get("attempt_key") != identity.idempotency_key
    ):
        raise MissionControlError(
            f"attempt {identity.run_id!r} has conflicting terminal evidence"
        )
    owner_status = "completed" if status == "succeeded" else "failed"
    return (
        status,
        owner_status,
        payload["result"],
        payload["failure_code"],
        dict(metadata),
    )


def recovery_receipt_matches_contract(
    receipt: RuntimeReceipt,
    identity: ExecutionIdentity,
    mission_id: str,
) -> bool:
    """Return whether a recovery receipt is canonical for its exact claim."""
    return (
        receipt_matches_identity(receipt, identity)
        and receipt.receipt_type == RECOVERY_RECEIPT_TYPE
        and receipt.status == "stale_recovered"
        and receipt.receipt_id
        == stable_id("receipt", identity.run_id, "stale_recovered")
        and receipt.side_effect_key
        == f"mission_control:{identity.run_id}:stale_recovery"
        and receipt.payload.get("schema_version") == SCHEMA_VERSION
        and receipt.payload.get("mission_id") == mission_id
        and receipt.payload.get("attempt_id") == identity.run_id
        and receipt.payload.get("recovered_claim_id") == identity.claim_id
        and receipt.payload.get("reason") == "expired_lease"
    )


def terminal_operation_metadata(
    receipt: RuntimeReceipt,
    identity: ExecutionIdentity,
    mission_id: str,
) -> tuple[str, dict[str, Any]]:
    """Reconstruct the exact finish CAS metadata from durable evidence."""
    operation = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission_id,
        "attempt_id": identity.run_id,
        "task_id": identity.task_id,
        "agent_id": identity.agent_id,
        "status": receipt.status,
        "receipt_id": receipt.receipt_id,
        "payload": receipt.payload,
    }
    operation_hash = hashlib.sha256(
        json.dumps(
            operation,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return operation_hash, {
        "operation_hash": operation_hash,
        "schema_version": SCHEMA_VERSION,
        "mission_id": mission_id,
        "attempt_id": identity.run_id,
        "task_id": identity.task_id,
        "agent_id": identity.agent_id,
        "terminal_status": receipt.status,
    }


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
    "MAX_LEASE_SECONDS",
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
    "attempt_view",
    "claim_is_active",
    "claim_is_expired",
    "claim_is_open",
    "clean_identifier",
    "lease_view",
    "mission_view",
    "public_attempt_status",
    "receipt_view",
    "session_id",
    "stable_id",
    "task_view",
    "utc_now",
]
