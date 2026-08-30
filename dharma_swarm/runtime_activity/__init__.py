"""Lease-aware runtime activity observations for operator read models.

Persisted statuses are observations, not process-liveness evidence.  This
module is deliberately read-only: it reconciles the canonical runtime rows
without updating, recovering, or adopting any of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Sequence

from dharma_swarm.runtime_state import DelegationRun, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


ACTIVITY_SEMANTICS = "runtime_activity.v1"
OPEN_RUN_STATUSES = frozenset(
    {
        "active",
        "acknowledged",
        "claimed",
        "in_progress",
        "leased",
        "pending",
        "queued",
        "running",
    }
)
CURRENT_CLAIM_STATUSES = frozenset(
    {"active", "acknowledged", "in_progress", "leased", "running"}
)
TERMINAL_STATUSES = frozenset(
    {
        "cancelled",
        "canceled",
        "completed",
        "error",
        "errored",
        "failed",
        "recovered",
        "stale_recovered",
        "succeeded",
        "success",
    }
)


class RuntimeActivityState(StrEnum):
    TERMINAL_EVIDENCE = "terminal_evidence"
    CURRENT_LEASE = "current_lease"
    EXPIRED_OR_UNPROVEN = "expired_or_unproven"


class RuntimeIdentityState(StrEnum):
    MATCHED = "matched"
    MISSING = "missing"
    CONFLICT = "conflict"


class RuntimeLeasePolicy(StrEnum):
    MISSION_CONTROL_STRICT = "mission_control_strict"
    ORCHESTRATOR_HEARTBEAT_WINDOW = "orchestrator_heartbeat_window"
    UNKNOWN_STRICT = "unknown_strict"


@dataclass(frozen=True, slots=True)
class RuntimeActivityObservation:
    run_id: str
    session_id: str
    task_id: str
    claim_id: str
    assigned_to: str
    run_status: str
    claim_status: str | None
    lease_policy: RuntimeLeasePolicy
    state: RuntimeActivityState
    identity_state: RuntimeIdentityState
    observed_nonterminal: bool
    terminal_evidence: bool
    lease_acknowledged: bool
    heartbeat_at: datetime | None
    stale_after: datetime | None
    reason_codes: tuple[str, ...]
    run_record: DelegationRun = field(repr=False, compare=False)
    terminal_evidence_conflict: bool = False
    proves_executor_liveness: bool = field(default=False, init=False)

    @property
    def current_lease(self) -> bool:
        return self.state is RuntimeActivityState.CURRENT_LEASE

    def to_dict(self) -> dict[str, object]:
        return {
            "semantics": ACTIVITY_SEMANTICS,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "claim_id": self.claim_id,
            "assigned_to": self.assigned_to,
            "run_status": self.run_status,
            "claim_status": self.claim_status,
            "lease_policy": self.lease_policy.value,
            "state": self.state.value,
            "identity_state": self.identity_state.value,
            "observed_nonterminal": self.observed_nonterminal,
            "terminal_evidence": self.terminal_evidence,
            "terminal_evidence_conflict": self.terminal_evidence_conflict,
            "current_lease": self.current_lease,
            "lease_acknowledged": self.lease_acknowledged,
            "heartbeat_at": _dt_iso(self.heartbeat_at),
            "stale_after": _dt_iso(self.stale_after),
            "reason_codes": list(self.reason_codes),
            "executor_liveness": "unproven",
            "proves_executor_liveness": self.proves_executor_liveness,
        }


@dataclass(frozen=True, slots=True)
class RuntimeActivitySnapshot:
    observations: tuple[RuntimeActivityObservation, ...]
    observed_at: datetime
    semantics: str = ACTIVITY_SEMANTICS
    proves_executor_liveness: bool = field(default=False, init=False)

    @property
    def by_run_id(self) -> dict[str, RuntimeActivityObservation]:
        return {item.run_id: item for item in self.observations}

    @property
    def current_leases(self) -> tuple[RuntimeActivityObservation, ...]:
        return tuple(item for item in self.observations if item.current_lease)

    @property
    def observed_nonterminal(self) -> tuple[RuntimeActivityObservation, ...]:
        return tuple(item for item in self.observations if item.observed_nonterminal)

    @property
    def expired_or_unproven(self) -> tuple[RuntimeActivityObservation, ...]:
        return tuple(
            item
            for item in self.observations
            if item.state is RuntimeActivityState.EXPIRED_OR_UNPROVEN
        )

    @property
    def current_session_ids(self) -> frozenset[str]:
        return frozenset(item.session_id for item in self.current_leases if item.session_id)

    @property
    def current_agent_ids(self) -> frozenset[str]:
        return frozenset(item.assigned_to for item in self.current_leases if item.assigned_to)

    @property
    def current_runs(self) -> tuple[DelegationRun, ...]:
        return tuple(item.run_record for item in self.current_leases)

    @property
    def current_claim_ids(self) -> frozenset[str]:
        return frozenset(item.claim_id for item in self.current_leases if item.claim_id)

    def summary(self) -> dict[str, object]:
        current_count = len(self.current_leases)
        return {
            "activity_semantics": self.semantics,
            "observed_nonterminal_run_count": len(self.observed_nonterminal),
            "current_lease_run_count": current_count,
            "current_lease_claim_count": len(self.current_claim_ids),
            "expired_or_unproven_run_count": len(self.expired_or_unproven),
            "terminal_evidence_conflict_count": sum(
                1 for item in self.observations if item.terminal_evidence_conflict
            ),
            "active_run_count": current_count,
            "active_session_count": len(self.current_session_ids),
            "activity_observed_at": self.observed_at.isoformat(),
            "proves_executor_liveness": self.proves_executor_liveness,
        }


def _normalized_status(value: str | None) -> str:
    return str(value or "").strip().lower()


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _dt_iso(value: datetime | None) -> str | None:
    normalized = _as_utc(value)
    return normalized.isoformat() if normalized is not None else None


def _lease_policy(run: DelegationRun, claim: TaskClaim | None) -> RuntimeLeasePolicy:
    claim_metadata = claim.metadata if claim is not None else {}
    schema = str(
        claim_metadata.get("schema_version")
        or run.metadata.get("schema_version")
        or ""
    ).strip()
    if schema == "dharma.mission_control.v1":
        return RuntimeLeasePolicy.MISSION_CONTROL_STRICT
    source = str(
        claim_metadata.get("source") or run.metadata.get("source") or ""
    ).strip().lower()
    if source == "orchestrator":
        return RuntimeLeasePolicy.ORCHESTRATOR_HEARTBEAT_WINDOW
    return RuntimeLeasePolicy.UNKNOWN_STRICT


def _lease_is_current(
    *,
    policy: RuntimeLeasePolicy,
    claimed_at: datetime | None,
    heartbeat_at: datetime | None,
    stale_after: datetime | None,
    observed_at: datetime,
) -> tuple[bool, str]:
    if stale_after is None:
        return False, "lease_expiry_missing"
    if observed_at < stale_after:
        return True, "stored_lease_deadline_current"
    if policy is not RuntimeLeasePolicy.ORCHESTRATOR_HEARTBEAT_WINDOW:
        return False, "lease_expired"
    if claimed_at is None or heartbeat_at is None:
        return False, "heartbeat_window_unproven"
    lease_window = stale_after - claimed_at
    if lease_window.total_seconds() <= 0:
        return False, "heartbeat_window_invalid"
    if observed_at - heartbeat_at < lease_window:
        return True, "heartbeat_window_extends_deadline"
    return False, "heartbeat_window_expired"


def _claim_matches(run: DelegationRun, claim: TaskClaim | None) -> bool:
    return bool(
        claim is not None
        and run.claim_id
        and run.claim_id == claim.claim_id
        and run.task_id == claim.task_id
        and run.session_id == claim.session_id
        and run.assigned_to == claim.agent_id
    )


def _identity_state(
    run: DelegationRun,
    identity: ExecutionIdentity | None,
) -> RuntimeIdentityState:
    if identity is None:
        return RuntimeIdentityState.MISSING
    try:
        identity.require_for_dispatch()
    except MissingExecutionIdentity:
        return RuntimeIdentityState.CONFLICT
    if (
        identity.run_id != run.run_id
        or identity.task_id != run.task_id
        or identity.claim_id != run.claim_id
        or identity.agent_id != run.assigned_to
        or identity.session_id != run.session_id
    ):
        return RuntimeIdentityState.CONFLICT
    return RuntimeIdentityState.MATCHED


def classify_runtime_activity(
    run: DelegationRun,
    *,
    claim: TaskClaim | None,
    identity: ExecutionIdentity | None,
    observed_at: datetime,
    terminal_receipt: bool = False,
    superseded: bool = False,
    claim_order_ambiguous: bool = False,
    competing_open_claim: bool = False,
) -> RuntimeActivityObservation:
    """Classify one persisted run without promoting it to process liveness."""

    now = _as_utc(observed_at) or datetime.now(timezone.utc)
    run_status = _normalized_status(run.status)
    claim_status = _normalized_status(claim.status) if claim is not None else None
    claim_matches = _claim_matches(run, claim)
    identity_state = _identity_state(run, identity)
    lease_policy = _lease_policy(run, claim)
    observed_nonterminal = run_status not in TERMINAL_STATUSES
    terminal_evidence = bool(
        run_status in TERMINAL_STATUSES
        or run.completed_at is not None
        or terminal_receipt
        or (
            claim_matches
            and claim_status in TERMINAL_STATUSES
        )
    )
    reasons: list[str] = []
    if run_status in TERMINAL_STATUSES:
        reasons.append("run_status_terminal")
    if run.completed_at is not None:
        reasons.append("run_completed_at_present")
    if terminal_receipt:
        reasons.append("identity_bound_terminal_receipt")
    if claim_matches and claim_status in TERMINAL_STATUSES:
        reasons.append("matching_claim_terminal")
    terminal_conflict = terminal_evidence and observed_nonterminal
    if terminal_conflict:
        reasons.append("terminal_evidence_conflicts_with_run_status")
    if terminal_evidence:
        return RuntimeActivityObservation(
            run_id=run.run_id,
            session_id=run.session_id,
            task_id=run.task_id,
            claim_id=run.claim_id,
            assigned_to=run.assigned_to,
            run_status=run_status,
            claim_status=claim_status,
            lease_policy=lease_policy,
            state=RuntimeActivityState.TERMINAL_EVIDENCE,
            identity_state=identity_state,
            observed_nonterminal=observed_nonterminal,
            terminal_evidence=True,
            terminal_evidence_conflict=terminal_conflict,
            lease_acknowledged=bool(claim and claim.acked_at),
            heartbeat_at=claim.heartbeat_at if claim else None,
            stale_after=claim.stale_after if claim else None,
            reason_codes=tuple(reasons),
            run_record=run,
        )

    if run_status not in OPEN_RUN_STATUSES:
        reasons.append("run_status_not_recognized_open")
    if not all((run.run_id, run.session_id, run.task_id, run.claim_id, run.assigned_to)):
        reasons.append("run_identity_fields_incomplete")
    if claim is None:
        reasons.append("claim_missing")
    elif not claim_matches:
        reasons.append("claim_identity_conflict")
    if identity_state is RuntimeIdentityState.MISSING:
        reasons.append("execution_identity_missing")
    elif identity_state is RuntimeIdentityState.CONFLICT:
        reasons.append("execution_identity_conflict")

    claimed_at = _as_utc(claim.claimed_at) if claim_matches and claim else None
    acked_at = _as_utc(claim.acked_at) if claim_matches and claim else None
    heartbeat_at = _as_utc(claim.heartbeat_at) if claim_matches and claim else None
    stale_after = _as_utc(claim.stale_after) if claim_matches and claim else None
    lease_current, lease_reason = _lease_is_current(
        policy=lease_policy,
        claimed_at=claimed_at,
        heartbeat_at=heartbeat_at,
        stale_after=stale_after,
        observed_at=now,
    )
    if claim_matches and claim is not None:
        if claim_status not in CURRENT_CLAIM_STATUSES:
            reasons.append("claim_status_not_current")
        if claim.recovered_at is not None:
            reasons.append("claim_recovered")
        if acked_at is None:
            reasons.append("claim_unacknowledged")
        if heartbeat_at is None:
            reasons.append("heartbeat_missing")
        if (
            claimed_at is not None
            and acked_at is not None
            and claimed_at > acked_at
        ):
            reasons.append("ack_precedes_claim")
        if (
            claimed_at is not None
            and heartbeat_at is not None
            and claimed_at > heartbeat_at
        ):
            reasons.append("heartbeat_precedes_claim")
        if acked_at is not None and acked_at > now:
            reasons.append("ack_in_future")
        if heartbeat_at is not None and heartbeat_at > now:
            reasons.append("heartbeat_in_future")
        reasons.append(lease_reason)
    if superseded:
        reasons.append("superseded_by_later_claim")
    if claim_order_ambiguous:
        reasons.append("claim_order_ambiguous")
    if competing_open_claim:
        reasons.append("competing_open_claim")

    current = bool(
        run_status in OPEN_RUN_STATUSES
        and all((run.run_id, run.session_id, run.task_id, run.claim_id, run.assigned_to))
        and claim_matches
        and claim is not None
        and claim_status in CURRENT_CLAIM_STATUSES
        and claim.recovered_at is None
        and identity_state is RuntimeIdentityState.MATCHED
        and claimed_at is not None
        and acked_at is not None
        and heartbeat_at is not None
        and stale_after is not None
        and claimed_at <= acked_at <= now
        and claimed_at <= heartbeat_at <= now
        and lease_current
        and not superseded
        and not claim_order_ambiguous
        and not competing_open_claim
    )
    if current:
        reasons.append("identity_bound_current_lease")
    elif not reasons:
        reasons.append("current_lease_unproven")
    return RuntimeActivityObservation(
        run_id=run.run_id,
        session_id=run.session_id,
        task_id=run.task_id,
        claim_id=run.claim_id,
        assigned_to=run.assigned_to,
        run_status=run_status,
        claim_status=claim_status,
        lease_policy=lease_policy,
        state=(
            RuntimeActivityState.CURRENT_LEASE
            if current
            else RuntimeActivityState.EXPIRED_OR_UNPROVEN
        ),
        identity_state=identity_state,
        observed_nonterminal=observed_nonterminal,
        terminal_evidence=False,
        lease_acknowledged=acked_at is not None,
        heartbeat_at=heartbeat_at,
        stale_after=stale_after,
        reason_codes=tuple(reasons),
        run_record=run,
    )


def load_runtime_activity(
    db_path: str | Path,
    *,
    run_ids: Sequence[str] | None = None,
    session_id: str | None = None,
    observed_at: datetime | None = None,
    limit: int | None = None,
) -> RuntimeActivitySnapshot:
    """Load a bounded, joined activity projection from the runtime database."""

    # Keep this public entry point stable while isolating persistence/query
    # mechanics from the lease-classification contract above.
    from dharma_swarm.runtime_activity.store import load_runtime_activity as _load

    return _load(
        db_path,
        run_ids=run_ids,
        session_id=session_id,
        observed_at=observed_at,
        limit=limit,
    )


__all__ = [
    "ACTIVITY_SEMANTICS",
    "RuntimeActivityObservation",
    "RuntimeActivitySnapshot",
    "RuntimeActivityState",
    "RuntimeIdentityState",
    "RuntimeLeasePolicy",
    "classify_runtime_activity",
    "load_runtime_activity",
]
