"""Read-only SQLite projection for operator runtime activity.

This module owns persistence mechanics.  Lease classification and public data
types remain in the sibling ``runtime_activity`` module so consumers have one
stable API surface.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from dharma_swarm.runtime_activity import (
    TERMINAL_STATUSES,
    RuntimeActivityObservation,
    RuntimeActivitySnapshot,
    _as_utc,
    _lease_is_current,
    _lease_policy,
    _normalized_status,
    classify_runtime_activity,
)
from dharma_swarm.runtime_state import DelegationRun, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity


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
        competing = (
            []
            if claim is None
            else [
                candidate
                for candidate in related_claims.get(claim.task_id, [])
                if candidate.claim_id != claim.claim_id
            ]
        )
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
