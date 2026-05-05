"""Read-only store readers for Trace Attractor Ledger events.

These adapters normalize existing ontology, runtime, and telemetry records into
AttractorEvent objects.  They do not initialize schemas, write rows, subscribe
to SignalBus, or project packets.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.ontology import OntologyObj, OntologyRegistry
from dharma_swarm.trace_attractor.models import AttractorEvent


DEFAULT_ONTOLOGY_TYPES = (
    "KnowledgeArtifact",
    "WitnessLog",
    "ActionProposal",
    "GateDecisionRecord",
    "Outcome",
    "ValueEvent",
    "Contribution",
    "AgentIdentity",
    "TypedTask",
)


def _json_load(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _json_load_dict(raw: str | None) -> dict[str, Any]:
    data = _json_load(raw, {})
    return data if isinstance(data, dict) else {}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _nested_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _extract_trace_id(data: dict[str, Any]) -> str:
    direct = _text(data.get("trace_id"))
    if direct:
        return direct
    for key in ("metadata", "correlation", "context", "provenance"):
        nested = _nested_mapping(data, key)
        trace_id = _text(nested.get("trace_id"))
        if trace_id:
            return trace_id
    return ""


def _extract_session_id(data: dict[str, Any]) -> str:
    direct = _text(data.get("session_id"))
    if direct:
        return direct
    for key in ("metadata", "correlation", "context", "provenance"):
        nested = _nested_mapping(data, key)
        session_id = _text(nested.get("session_id"))
        if session_id:
            return session_id
    return ""


def _extract_proposal_id(data: dict[str, Any], *, fallback: str = "") -> str:
    direct = _text(data.get("proposal_id"))
    if direct:
        return direct
    for key in ("metadata", "correlation", "context", "provenance"):
        nested = _nested_mapping(data, key)
        proposal_id = _text(nested.get("proposal_id"))
        if proposal_id:
            return proposal_id
    return fallback


def _camel_to_snake(value: str) -> str:
    step = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", value)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", step).lower()


def _event_id(source_store: str, source_type: str, object_id: str) -> str:
    return f"evt:{source_store}:{source_type}:{object_id}"


def _sqlite_ro(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.exists():
        return None
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _metadata_for_row(row: sqlite3.Row) -> dict[str, Any]:
    keys = set(row.keys())
    if "metadata_json" not in keys:
        return {}
    return _json_load_dict(row["metadata_json"])


def _row_trace_id(row: sqlite3.Row) -> str:
    data = _row_dict(row)
    trace_id = _text(data.get("trace_id"))
    if trace_id:
        return trace_id
    metadata = _metadata_for_row(row)
    return _extract_trace_id(metadata)


def _matches_trace(row: sqlite3.Row, trace_id: str) -> bool:
    return _row_trace_id(row) == trace_id


def _query_rows(
    conn: sqlite3.Connection,
    table: str,
    *,
    order_column: str,
    limit: int,
) -> list[sqlite3.Row]:
    if not _table_exists(conn, table):
        return []
    columns = _table_columns(conn, table)
    order = order_column if order_column in columns else next(iter(columns))
    return list(conn.execute(
        f"SELECT * FROM {table} ORDER BY {order} DESC LIMIT ?",
        (max(1, limit),),
    ))


def _ontology_event(obj: OntologyObj) -> AttractorEvent:
    properties = dict(obj.properties)
    trace_id = _extract_trace_id(properties)
    proposal_id = _extract_proposal_id(
        properties,
        fallback=obj.id if obj.type_name == "ActionProposal" else "",
    )
    session_id = _extract_session_id(properties)
    attributes = {
        **properties,
        "ontology_object_id": obj.id,
        "type_name": obj.type_name,
        "created_by": obj.created_by,
        "version": obj.version,
    }
    return AttractorEvent(
        event_id=_event_id("ontology", obj.type_name, obj.id),
        trace_id=trace_id,
        proposal_id=proposal_id,
        session_id=session_id,
        source_store="ontology",
        source_table_or_type=obj.type_name,
        source_object_id=obj.id,
        event_type=f"{_camel_to_snake(obj.type_name)}_recorded",
        subject=obj.id,
        occurred_at=obj.created_at.isoformat(),
        attributes=attributes,
    )


def read_ontology_events(
    registry: OntologyRegistry,
    trace_id: str,
    *,
    type_names: Iterable[str] = DEFAULT_ONTOLOGY_TYPES,
) -> list[AttractorEvent]:
    """Read trace-tagged ontology objects by type metadata."""
    events: list[AttractorEvent] = []
    for type_name in type_names:
        for obj in registry.get_objects_by_type(type_name):
            event = _ontology_event(obj)
            if event.trace_id == trace_id:
                events.append(event)
    return sorted(events, key=lambda event: (event.occurred_at, event.event_id))


def _task_claim_event(row: sqlite3.Row) -> AttractorEvent:
    metadata = _metadata_for_row(row)
    trace_id = _row_trace_id(row)
    proposal_id = _extract_proposal_id(metadata)
    claim_id = _text(row["claim_id"])
    attributes = {
        "claim_id": claim_id,
        "task_id": _text(row["task_id"]),
        "agent_id": _text(row["agent_id"]),
        "status": _text(row["status"]),
        "claimed_at": _text(row["claimed_at"]),
        "acked_at": _text(row["acked_at"]),
        "heartbeat_at": _text(row["heartbeat_at"]),
        "stale_after": _text(row["stale_after"]),
        "recovered_at": _text(row["recovered_at"]),
        "retry_count": int(row["retry_count"] or 0),
        "metadata": metadata,
    }
    if proposal_id:
        attributes["proposal_id"] = proposal_id
    return AttractorEvent(
        event_id=_event_id("runtime_state", "task_claims", claim_id),
        trace_id=trace_id,
        proposal_id=proposal_id,
        session_id=_text(row["session_id"]) or _extract_session_id(metadata),
        source_store="runtime_state",
        source_table_or_type="task_claims",
        source_object_id=claim_id,
        event_type="task_claim_recorded",
        subject=claim_id,
        occurred_at=_text(row["claimed_at"]),
        attributes=attributes,
    )


def _delegation_run_event(row: sqlite3.Row) -> AttractorEvent:
    metadata = _metadata_for_row(row)
    trace_id = _row_trace_id(row)
    proposal_id = _extract_proposal_id(metadata)
    run_id = _text(row["run_id"])
    attributes = {
        "run_id": run_id,
        "task_id": _text(row["task_id"]),
        "claim_id": _text(row["claim_id"]),
        "parent_run_id": _text(row["parent_run_id"]),
        "assigned_by": _text(row["assigned_by"]),
        "assigned_to": _text(row["assigned_to"]),
        "agent_id": _text(row["assigned_to"]),
        "requested_output": _json_load(row["requested_output_json"], []),
        "artifact_id": _text(row["current_artifact_id"]),
        "current_artifact_id": _text(row["current_artifact_id"]),
        "status": _text(row["status"]),
        "started_at": _text(row["started_at"]),
        "completed_at": _text(row["completed_at"]),
        "failure_code": _text(row["failure_code"]),
        "metadata": metadata,
    }
    if proposal_id:
        attributes["proposal_id"] = proposal_id
    return AttractorEvent(
        event_id=_event_id("runtime_state", "delegation_runs", run_id),
        trace_id=trace_id,
        proposal_id=proposal_id,
        session_id=_text(row["session_id"]) or _extract_session_id(metadata),
        source_store="runtime_state",
        source_table_or_type="delegation_runs",
        source_object_id=run_id,
        event_type="delegation_run_recorded",
        subject=run_id,
        occurred_at=_text(row["started_at"]),
        attributes=attributes,
    )


def _artifact_event(row: sqlite3.Row) -> AttractorEvent:
    metadata = _metadata_for_row(row)
    trace_id = _row_trace_id(row)
    proposal_id = _extract_proposal_id(metadata)
    artifact_id = _text(row["artifact_id"])
    attributes = {
        "artifact_id": artifact_id,
        "artifact_kind": _text(row["artifact_kind"]),
        "task_id": _text(row["task_id"]),
        "run_id": _text(row["run_id"]),
        "manifest_path": _text(row["manifest_path"]),
        "payload_path": _text(row["payload_path"]),
        "checksum": _text(row["checksum"]),
        "parent_artifact_id": _text(row["parent_artifact_id"]),
        "promotion_state": _text(row["promotion_state"]),
        "metadata": metadata,
    }
    if proposal_id:
        attributes["proposal_id"] = proposal_id
    return AttractorEvent(
        event_id=_event_id("runtime_state", "artifact_records", artifact_id),
        trace_id=trace_id,
        proposal_id=proposal_id,
        session_id=_text(row["session_id"]) or _extract_session_id(metadata),
        source_store="runtime_state",
        source_table_or_type="artifact_records",
        source_object_id=artifact_id,
        event_type="artifact_recorded",
        subject=artifact_id,
        occurred_at=_text(row["created_at"]),
        attributes=attributes,
    )


def read_runtime_events(
    db_path: str | Path,
    trace_id: str,
    *,
    limit_per_table: int = 500,
) -> list[AttractorEvent]:
    """Read runtime task claims, delegation runs, and artifacts for a trace."""
    conn = _sqlite_ro(Path(db_path))
    if conn is None:
        return []
    try:
        events: list[AttractorEvent] = []
        for row in _query_rows(
            conn,
            "task_claims",
            order_column="claimed_at",
            limit=limit_per_table,
        ):
            if _matches_trace(row, trace_id):
                events.append(_task_claim_event(row))
        for row in _query_rows(
            conn,
            "delegation_runs",
            order_column="started_at",
            limit=limit_per_table,
        ):
            if _matches_trace(row, trace_id):
                events.append(_delegation_run_event(row))
        for row in _query_rows(
            conn,
            "artifact_records",
            order_column="created_at",
            limit=limit_per_table,
        ):
            if _matches_trace(row, trace_id):
                events.append(_artifact_event(row))
        return sorted(events, key=lambda event: (event.occurred_at, event.event_id))
    finally:
        conn.close()


def _economic_event(row: sqlite3.Row) -> AttractorEvent:
    metadata = _metadata_for_row(row)
    trace_id = _row_trace_id(row)
    proposal_id = _extract_proposal_id(metadata)
    event_id = _text(row["event_id"])
    attributes = {
        "economic_event_id": event_id,
        "event_id": event_id,
        "event_kind": _text(row["event_kind"]),
        "amount": float(row["amount"] or 0.0),
        "currency": _text(row["currency"]) or "USD",
        "counterparty": _text(row["counterparty"]),
        "summary": _text(row["summary"]),
        "task_id": _text(row["task_id"]),
        "run_id": _text(row["run_id"]),
        "metadata": metadata,
    }
    for key in ("value_event_id", "outcome_id", "agent_id", "cell_id"):
        value = _text(metadata.get(key))
        if value:
            attributes[key] = value
    if proposal_id:
        attributes["proposal_id"] = proposal_id
    return AttractorEvent(
        event_id=_event_id("telemetry_plane", "economic_events", event_id),
        trace_id=trace_id,
        proposal_id=proposal_id,
        session_id=_text(row["session_id"]) or _extract_session_id(metadata),
        source_store="telemetry_plane",
        source_table_or_type="economic_events",
        source_object_id=event_id,
        event_type="economic_event_recorded",
        subject=event_id,
        occurred_at=_text(row["created_at"]),
        attributes=attributes,
    )


def read_telemetry_events(
    db_path: str | Path,
    trace_id: str,
    *,
    limit_per_table: int = 500,
) -> list[AttractorEvent]:
    """Read economic telemetry events for a trace."""
    conn = _sqlite_ro(Path(db_path))
    if conn is None:
        return []
    try:
        events: list[AttractorEvent] = []
        for row in _query_rows(
            conn,
            "economic_events",
            order_column="created_at",
            limit=limit_per_table,
        ):
            if _matches_trace(row, trace_id):
                events.append(_economic_event(row))
        return sorted(events, key=lambda event: (event.occurred_at, event.event_id))
    finally:
        conn.close()


@dataclass(frozen=True)
class TraceAttractorStoreReader:
    """Facade for collecting read-only AttractorEvents across stores."""

    registry: OntologyRegistry | None = None
    runtime_db_path: Path | None = None
    telemetry_db_path: Path | None = None
    ontology_type_names: tuple[str, ...] = DEFAULT_ONTOLOGY_TYPES
    limit_per_table: int = 500

    def read_events(self, trace_id: str) -> list[AttractorEvent]:
        events: list[AttractorEvent] = []
        if self.registry is not None:
            events.extend(read_ontology_events(
                self.registry,
                trace_id,
                type_names=self.ontology_type_names,
            ))
        if self.runtime_db_path is not None:
            events.extend(read_runtime_events(
                self.runtime_db_path,
                trace_id,
                limit_per_table=self.limit_per_table,
            ))
        if self.telemetry_db_path is not None:
            events.extend(read_telemetry_events(
                self.telemetry_db_path,
                trace_id,
                limit_per_table=self.limit_per_table,
            ))
        return sorted(events, key=lambda event: (event.occurred_at, event.event_id))
