"""Lease-aware runtime activity observations for operator read models.

Persisted statuses are observations, not process-liveness evidence.  This
module is deliberately read-only: it reconciles the canonical runtime rows
without updating, recovering, or adopting any of them.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Sequence

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


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        return _as_utc(datetime.fromisoformat(raw))
    except ValueError:
        return None


def _parse_json(value: object, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(str(value or ""))
    except (TypeError, ValueError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


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


def _claim_is_potentially_open(claim: TaskClaim, observed_at: datetime) -> bool:
    if (
        _normalized_status(claim.status) in TERMINAL_STATUSES
        or claim.recovered_at is not None
    ):
        return False
    claimed_at = _as_utc(claim.claimed_at)
    heartbeat_at = _as_utc(claim.heartbeat_at)
    stale_after = _as_utc(claim.stale_after)
    if heartbeat_at is not None and heartbeat_at > observed_at:
        return False
    policy = _lease_policy(
        DelegationRun(
            run_id="claim-open-probe",
            task_id=claim.task_id,
            assigned_to=claim.agent_id,
            session_id=claim.session_id,
            claim_id=claim.claim_id,
        ),
        claim,
    )
    current, _ = _lease_is_current(
        policy=policy,
        claimed_at=claimed_at,
        heartbeat_at=heartbeat_at,
        stale_after=stale_after,
        observed_at=observed_at,
    )
    return current


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


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _identity_columns(present: bool) -> str:
    names = (
        "trace_id",
        "correlation_id",
        "task_id",
        "run_id",
        "claim_id",
        "idempotency_key",
        "causation_id",
        "parent_run_id",
        "agent_id",
        "session_id",
    )
    if present:
        return ", ".join(f"i.{name} AS identity_{name}" for name in names)
    return ", ".join(f"NULL AS identity_{name}" for name in names)


def _terminal_receipt_expression(present: bool) -> str:
    if not present:
        return "0"
    return """
        EXISTS (
            SELECT 1
            FROM runtime_receipts rr
            WHERE rr.run_id = r.run_id
              AND rr.task_id = r.task_id
              AND rr.agent_id = r.assigned_to
              AND i.run_id IS NOT NULL
              AND rr.trace_id = i.trace_id
              AND rr.correlation_id = i.correlation_id
              AND rr.causation_id = i.causation_id
              AND rr.parent_run_id = i.parent_run_id
              AND rr.idempotency_key = i.idempotency_key
              AND (
                    (rr.receipt_type = 'mission_attempt_terminal'
                     AND lower(rr.status) IN ('succeeded', 'failed'))
                 OR (rr.receipt_type = 'mission_attempt_recovery'
                     AND lower(rr.status) = 'stale_recovered')
                 OR (rr.receipt_type = 'child_completed'
                     AND lower(rr.status) IN ('completed', 'failed'))
                 OR (rr.receipt_type = 'delegation_run'
                     AND lower(rr.status) IN ('completed', 'failed', 'stale_recovered'))
              )
        )
    """


def load_runtime_activity(
    db_path: str | Path,
    *,
    run_ids: Sequence[str] | None = None,
    session_id: str | None = None,
    observed_at: datetime | None = None,
    limit: int | None = None,
) -> RuntimeActivitySnapshot:
    """Load a bounded, joined activity projection from the runtime database."""

    now = _as_utc(observed_at) or datetime.now(timezone.utc)
    path = Path(db_path)
    if not path.exists() or (run_ids is not None and not run_ids):
        return RuntimeActivitySnapshot(observations=(), observed_at=now)
    uri = f"{path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only = ON")
        db.execute("BEGIN")
        has_identity = _table_exists(db, "execution_identities")
        has_receipts = has_identity and _table_exists(db, "runtime_receipts")
        identity_join = (
            "LEFT JOIN execution_identities i ON i.run_id = r.run_id"
            if has_identity
            else ""
        )
        query = f"""
            SELECT
                r.run_id,
                r.session_id AS run_session_id,
                r.task_id AS run_task_id,
                r.claim_id AS run_claim_id,
                r.parent_run_id,
                r.assigned_by,
                r.assigned_to,
                r.requested_output_json,
                r.current_artifact_id,
                r.status AS run_status,
                r.started_at,
                r.completed_at,
                r.failure_code,
                r.metadata_json AS run_metadata_json,
                c.claim_id AS joined_claim_id,
                c.session_id AS claim_session_id,
                c.task_id AS claim_task_id,
                c.agent_id AS claim_agent_id,
                c.status AS claim_status,
                c.claimed_at,
                c.acked_at,
                c.heartbeat_at,
                c.stale_after,
                c.recovered_at,
                c.retry_count AS claim_retry_count,
                c.metadata_json AS claim_metadata_json,
                {_identity_columns(has_identity)},
                {_terminal_receipt_expression(has_receipts)} AS terminal_receipt
            FROM delegation_runs r
            LEFT JOIN task_claims c ON c.claim_id = r.claim_id
            {identity_join}
            WHERE 1 = 1
        """
        params: list[object] = []
        if run_ids is not None:
            placeholders = ", ".join("?" for _ in run_ids)
            query += f" AND r.run_id IN ({placeholders})"
            params.extend(run_ids)
        if session_id is not None:
            query += " AND r.session_id = ?"
            params.append(session_id)
        query += " ORDER BY r.started_at DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(1, int(limit)))
        rows = db.execute(query, params).fetchall()

        related_claims: dict[str, list[TaskClaim]] = {}
        task_ids = sorted(
            {
                str(row["run_task_id"] or "")
                for row in rows
                if row["run_task_id"]
            }
        )
        for offset in range(0, len(task_ids), 800):
            batch = task_ids[offset : offset + 800]
            placeholders = ", ".join("?" for _ in batch)
            claim_rows = db.execute(
                "SELECT claim_id, session_id, task_id, agent_id, status, claimed_at,"
                " acked_at, heartbeat_at, stale_after, recovered_at, retry_count,"
                f" metadata_json FROM task_claims WHERE task_id IN ({placeholders})",
                batch,
            ).fetchall()
            for claim_row in claim_rows:
                related = TaskClaim(
                    claim_id=str(claim_row["claim_id"] or ""),
                    session_id=str(claim_row["session_id"] or ""),
                    task_id=str(claim_row["task_id"] or ""),
                    agent_id=str(claim_row["agent_id"] or ""),
                    status=str(claim_row["status"] or ""),
                    claimed_at=_parse_dt(claim_row["claimed_at"]) or now,
                    acked_at=_parse_dt(claim_row["acked_at"]),
                    heartbeat_at=_parse_dt(claim_row["heartbeat_at"]),
                    stale_after=_parse_dt(claim_row["stale_after"]),
                    recovered_at=_parse_dt(claim_row["recovered_at"]),
                    retry_count=int(claim_row["retry_count"] or 0),
                    metadata=_parse_json(claim_row["metadata_json"], {}),
                )
                related_claims.setdefault(related.task_id, []).append(related)

    observations: list[RuntimeActivityObservation] = []
    for row in rows:
        run = DelegationRun(
            run_id=str(row["run_id"] or ""),
            session_id=str(row["run_session_id"] or ""),
            task_id=str(row["run_task_id"] or ""),
            claim_id=str(row["run_claim_id"] or ""),
            parent_run_id=str(row["parent_run_id"] or ""),
            assigned_by=str(row["assigned_by"] or ""),
            assigned_to=str(row["assigned_to"] or ""),
            requested_output=list(_parse_json(row["requested_output_json"], [])),
            current_artifact_id=str(row["current_artifact_id"] or ""),
            status=str(row["run_status"] or ""),
            started_at=_parse_dt(row["started_at"]) or now,
            completed_at=_parse_dt(row["completed_at"]),
            failure_code=str(row["failure_code"] or ""),
            metadata=_parse_json(row["run_metadata_json"], {}),
        )
        claim = None
        if row["joined_claim_id"] is not None:
            claim = TaskClaim(
                claim_id=str(row["joined_claim_id"] or ""),
                session_id=str(row["claim_session_id"] or ""),
                task_id=str(row["claim_task_id"] or ""),
                agent_id=str(row["claim_agent_id"] or ""),
                status=str(row["claim_status"] or ""),
                claimed_at=_parse_dt(row["claimed_at"]) or now,
                acked_at=_parse_dt(row["acked_at"]),
                heartbeat_at=_parse_dt(row["heartbeat_at"]),
                stale_after=_parse_dt(row["stale_after"]),
                recovered_at=_parse_dt(row["recovered_at"]),
                retry_count=int(row["claim_retry_count"] or 0),
                metadata=_parse_json(row["claim_metadata_json"], {}),
            )
        identity = None
        if row["identity_run_id"] is not None:
            identity = ExecutionIdentity(
                trace_id=str(row["identity_trace_id"] or ""),
                correlation_id=str(row["identity_correlation_id"] or ""),
                task_id=str(row["identity_task_id"] or ""),
                run_id=str(row["identity_run_id"] or ""),
                claim_id=str(row["identity_claim_id"] or ""),
                idempotency_key=str(row["identity_idempotency_key"] or ""),
                causation_id=str(row["identity_causation_id"] or ""),
                parent_run_id=str(row["identity_parent_run_id"] or ""),
                agent_id=str(row["identity_agent_id"] or ""),
                session_id=str(row["identity_session_id"] or ""),
            )
        competing = [] if claim is None else [
            candidate
            for candidate in related_claims.get(claim.task_id, [])
            if candidate.claim_id != claim.claim_id
        ]
        superseded = bool(
            claim is not None
            and any(candidate.claimed_at > claim.claimed_at for candidate in competing)
        )
        claim_order_ambiguous = bool(
            claim is not None
            and any(candidate.claimed_at == claim.claimed_at for candidate in competing)
        )
        competing_open_claim = bool(
            claim is not None
            and any(
                candidate.claimed_at < claim.claimed_at
                and _claim_is_potentially_open(candidate, now)
                for candidate in competing
            )
        )
        observations.append(
            classify_runtime_activity(
                run,
                claim=claim,
                identity=identity,
                observed_at=now,
                terminal_receipt=bool(row["terminal_receipt"]),
                superseded=superseded,
                claim_order_ambiguous=claim_order_ambiguous,
                competing_open_claim=competing_open_claim,
            )
        )
    return RuntimeActivitySnapshot(observations=tuple(observations), observed_at=now)


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
