"""Row-to-record mappers + session-event builders.

Mechanical split from the former dharma_swarm/runtime_state.py (item 6a).
Zero logic change: bodies are verbatim.
"""

from __future__ import annotations

import hashlib
import sqlite3
from typing import Any

import aiosqlite

from dharma_swarm.spine.identity import ExecutionIdentity

from ._util import _json_dump, _json_load, _parse_dt, _utc_now
from .models import (
    ArtifactRecord,
    ContextBundleRecord,
    DelegationRun,
    IdempotencyRecord,
    MemoryFact,
    OperatorAction,
    RuntimeReceipt,
    SessionEventRecord,
    SessionState,
    TaskClaim,
    TopologyStateRecord,
    WorkspaceLease,
)


def _row_to_session(row: sqlite3.Row | aiosqlite.Row) -> SessionState:
    return SessionState(
        session_id=str(row["session_id"]),
        operator_id=str(row["operator_id"] or ""),
        status=str(row["status"]),
        current_task_id=str(row["current_task_id"] or ""),
        active_bundle_id=str(row["active_bundle_id"] or ""),
        metadata=_json_load(row["metadata_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
    )


def _row_to_claim(row: sqlite3.Row | aiosqlite.Row) -> TaskClaim:
    return TaskClaim(
        claim_id=str(row["claim_id"]),
        task_id=str(row["task_id"]),
        agent_id=str(row["agent_id"]),
        status=str(row["status"]),
        session_id=str(row["session_id"] or ""),
        claimed_at=_parse_dt(row["claimed_at"]) or _utc_now(),
        acked_at=_parse_dt(row["acked_at"]),
        heartbeat_at=_parse_dt(row["heartbeat_at"]),
        stale_after=_parse_dt(row["stale_after"]),
        recovered_at=_parse_dt(row["recovered_at"]),
        retry_count=int(row["retry_count"] or 0),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_run(row: sqlite3.Row | aiosqlite.Row) -> DelegationRun:
    return DelegationRun(
        run_id=str(row["run_id"]),
        task_id=str(row["task_id"]),
        assigned_to=str(row["assigned_to"]),
        status=str(row["status"]),
        session_id=str(row["session_id"] or ""),
        claim_id=str(row["claim_id"] or ""),
        parent_run_id=str(row["parent_run_id"] or ""),
        assigned_by=str(row["assigned_by"] or ""),
        requested_output=list(_json_load(row["requested_output_json"], [])),
        current_artifact_id=str(row["current_artifact_id"] or ""),
        started_at=_parse_dt(row["started_at"]) or _utc_now(),
        completed_at=_parse_dt(row["completed_at"]),
        failure_code=str(row["failure_code"] or ""),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_topology_state(row: sqlite3.Row | aiosqlite.Row) -> TopologyStateRecord:
    child_run_ids = _json_load(row["child_run_ids_json"], [])
    if not isinstance(child_run_ids, list):
        child_run_ids = []
    allowed = _json_load(row["allowed_handoffs_json"], {})
    if not isinstance(allowed, dict):
        allowed = {}
    normalized_allowed: dict[str, list[str]] = {}
    for key, value in allowed.items():
        if isinstance(value, (list, tuple, set)):
            normalized_allowed[str(key)] = [str(item) for item in value]
    handoffs = _json_load(row["handoff_receipts_json"], [])
    if not isinstance(handoffs, list):
        handoffs = []
    return TopologyStateRecord(
        run_id=str(row["run_id"]),
        session_id=str(row["session_id"] or ""),
        task_id=str(row["task_id"]),
        topology=str(row["topology"]),
        active_agent=str(row["active_agent"] or ""),
        current_node=str(row["current_node"] or ""),
        checkpoint_id=str(row["checkpoint_id"] or ""),
        parent_run_id=str(row["parent_run_id"] or ""),
        child_run_ids=[str(item) for item in child_run_ids],
        allowed_handoffs=normalized_allowed,
        handoff_receipts=[item for item in handoffs if isinstance(item, dict)],
        state=_json_load(row["state_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
    )


def _row_to_lease(row: sqlite3.Row | aiosqlite.Row) -> WorkspaceLease:
    return WorkspaceLease(
        lease_id=str(row["lease_id"]),
        zone_path=str(row["zone_path"]),
        mode=str(row["mode"]),
        holder_run_id=str(row["holder_run_id"] or ""),
        base_hash=str(row["base_hash"] or ""),
        acquired_at=_parse_dt(row["acquired_at"]) or _utc_now(),
        expires_at=_parse_dt(row["expires_at"]),
        released_at=_parse_dt(row["released_at"]),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_artifact(row: sqlite3.Row | aiosqlite.Row) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=str(row["artifact_id"]),
        artifact_kind=str(row["artifact_kind"]),
        session_id=str(row["session_id"] or ""),
        task_id=str(row["task_id"] or ""),
        run_id=str(row["run_id"] or ""),
        trace_id=str(row["trace_id"] or "") if "trace_id" in row.keys() else "",
        manifest_path=str(row["manifest_path"] or ""),
        payload_path=str(row["payload_path"] or ""),
        checksum=str(row["checksum"] or ""),
        parent_artifact_id=str(row["parent_artifact_id"] or ""),
        promotion_state=str(row["promotion_state"] or "ephemeral"),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_memory_fact(row: sqlite3.Row | aiosqlite.Row) -> MemoryFact:
    return MemoryFact(
        fact_id=str(row["fact_id"]),
        fact_kind=str(row["fact_kind"]),
        truth_state=str(row["truth_state"]),
        text=str(row["text"]),
        confidence=float(row["confidence"] or 0.0),
        session_id=str(row["session_id"] or ""),
        task_id=str(row["task_id"] or ""),
        valid_from=_parse_dt(row["valid_from"]),
        valid_to=_parse_dt(row["valid_to"]),
        source_event_id=str(row["source_event_id"] or ""),
        source_artifact_id=str(row["source_artifact_id"] or ""),
        provenance=_json_load(row["provenance_json"], {}),
        metadata=_json_load(row["metadata_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
    )


def _row_to_context_bundle(row: sqlite3.Row | aiosqlite.Row) -> ContextBundleRecord:
    return ContextBundleRecord(
        bundle_id=str(row["bundle_id"]),
        session_id=str(row["session_id"] or ""),
        task_id=str(row["task_id"] or ""),
        run_id=str(row["run_id"] or ""),
        token_budget=int(row["token_budget"] or 0),
        rendered_text=str(row["rendered_text"] or ""),
        sections=list(_json_load(row["sections_json"], [])),
        source_refs=list(_json_load(row["source_refs_json"], [])),
        checksum=str(row["checksum"] or ""),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_operator_action(row: sqlite3.Row | aiosqlite.Row) -> OperatorAction:
    return OperatorAction(
        action_id=str(row["action_id"]),
        action_name=str(row["action_name"]),
        actor=str(row["actor"]),
        session_id=str(row["session_id"] or ""),
        task_id=str(row["task_id"] or ""),
        run_id=str(row["run_id"] or ""),
        reason=str(row["reason"] or ""),
        payload=_json_load(row["payload_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
    )


def _row_to_session_event(row: sqlite3.Row | aiosqlite.Row) -> SessionEventRecord:
    return SessionEventRecord(
        event_id=str(row["event_id"]),
        session_id=str(row["session_id"] or ""),
        ledger_kind=str(row["ledger_kind"]),
        event_name=str(row["event_name"]),
        task_id=str(row["task_id"] or ""),
        run_id=str(row["run_id"] or ""),
        agent_id=str(row["agent_id"] or ""),
        summary=str(row["summary"] or ""),
        event_text=str(row["event_text"] or ""),
        payload=_json_load(row["payload_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
    )


def _row_to_execution_identity(row: sqlite3.Row | aiosqlite.Row) -> ExecutionIdentity:
    return ExecutionIdentity(
        trace_id=str(row["trace_id"]),
        correlation_id=str(row["correlation_id"]),
        task_id=str(row["task_id"]),
        run_id=str(row["run_id"]),
        claim_id=str(row["claim_id"] or ""),
        idempotency_key=str(row["idempotency_key"] or ""),
        causation_id=str(row["causation_id"] or ""),
        parent_run_id=str(row["parent_run_id"] or ""),
        agent_id=str(row["agent_id"] or ""),
        session_id=str(row["session_id"] or ""),
        external_a2a_task_id=str(row["external_a2a_task_id"] or ""),
        message_id=str(row["message_id"] or ""),
        event_id=str(row["event_id"] or ""),
        artifact_id=str(row["artifact_id"] or ""),
        proposal_id=str(row["proposal_id"] or ""),
        metadata=_json_load(row["metadata_json"], {}),
    )


def _row_to_runtime_receipt(row: sqlite3.Row | aiosqlite.Row) -> RuntimeReceipt:
    return RuntimeReceipt(
        receipt_id=str(row["receipt_id"]),
        receipt_type=str(row["receipt_type"]),
        status=str(row["status"]),
        run_id=str(row["run_id"] or ""),
        task_id=str(row["task_id"] or ""),
        trace_id=str(row["trace_id"] or ""),
        correlation_id=str(row["correlation_id"] or ""),
        causation_id=str(row["causation_id"] or ""),
        parent_run_id=str(row["parent_run_id"] or ""),
        agent_id=str(row["agent_id"] or ""),
        idempotency_key=str(row["idempotency_key"] or ""),
        side_effect_key=str(row["side_effect_key"] or ""),
        payload=_json_load(row["payload_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
    )


def _row_to_idempotency_record(row: sqlite3.Row | aiosqlite.Row) -> IdempotencyRecord:
    return IdempotencyRecord(
        idempotency_key=str(row["idempotency_key"]),
        side_effect_key=str(row["side_effect_key"]),
        status=str(row["status"]),
        run_id=str(row["run_id"] or ""),
        task_id=str(row["task_id"] or ""),
        trace_id=str(row["trace_id"] or ""),
        correlation_id=str(row["correlation_id"] or ""),
        result_receipt_id=str(row["result_receipt_id"] or ""),
        metadata=_json_load(row["metadata_json"], {}),
        created_at=_parse_dt(row["created_at"]) or _utc_now(),
        updated_at=_parse_dt(row["updated_at"]) or _utc_now(),
    )


def _flatten_search_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        parts: list[str] = []
        for key, inner in value.items():
            flattened = _flatten_search_text(inner)
            if flattened:
                parts.append(f"{key} {flattened}")
        return " ".join(parts)
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten_search_text(item) for item in value if _flatten_search_text(item))
    return str(value)


def _session_event_summary(payload: dict[str, Any], event_text: str) -> str:
    preferred_keys = (
        "summary",
        "reason",
        "failure_signature",
        "error",
        "status",
        "artifact",
        "result",
        "assigned_to",
        "assigned_by",
    )
    parts = [
        str(payload.get(key, "")).strip()
        for key in preferred_keys
        if str(payload.get(key, "")).strip()
    ]
    summary = " | ".join(parts) if parts else event_text.strip()
    return summary[:240]


def _ledger_record_event_id(session_id: str, ledger_kind: str, record: dict[str, Any]) -> str:
    existing = str(record.get("event_id", "")).strip()
    if existing:
        return existing
    canonical = {
        "session_id": session_id,
        "ledger_kind": ledger_kind,
        "record": record,
    }
    digest = hashlib.sha256(_json_dump(canonical).encode("utf-8")).hexdigest()[:24]
    return f"sevt_{digest}"


def build_session_event_from_ledger_record(
    *,
    session_id: str,
    ledger_kind: str,
    record: dict[str, Any],
) -> SessionEventRecord:
    payload = {
        key: value
        for key, value in dict(record).items()
        if key not in {"event_id", "session_id", "ledger_kind", "ts_utc", "event"}
    }
    event_name = str(record.get("event", "")).strip() or "unknown_event"
    task_id = str(payload.get("task_id", "") or "")
    run_id = str(payload.get("run_id", "") or "")
    agent_id = str(payload.get("agent_id", "") or payload.get("claimed_by", "") or "")
    event_text = " ".join(
        part
        for part in [
            event_name,
            task_id,
            run_id,
            agent_id,
            _flatten_search_text(payload),
        ]
        if str(part).strip()
    ).strip()
    created_at = _parse_dt(str(record.get("ts_utc", "")).strip()) or _utc_now()
    return SessionEventRecord(
        event_id=_ledger_record_event_id(session_id, ledger_kind, record),
        session_id=session_id,
        ledger_kind=ledger_kind,
        event_name=event_name,
        task_id=task_id,
        run_id=run_id,
        agent_id=agent_id,
        summary=_session_event_summary(payload, event_text),
        event_text=event_text,
        payload=payload,
        created_at=created_at,
    )
