"""Read-only runtime truth projections over existing runtime owners.

This module deliberately does not initialize or migrate runtime state. It
opens runtime.db in SQLite read-only mode and projects what is already there
into RuntimeTruthPacket rows.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .contracts import RuntimeTruthPacket, RuntimeTruthState


RUNTIME_DB_SOURCE = "dharma_swarm/runtime_state.py"
REQUIRED_RUNTIME_TABLES = ("runtime_receipts", "idempotency_records")
TERMINAL_SUCCESS_STATUSES = {"completed", "complete", "succeeded", "success", "ok"}
TERMINAL_BLOCKED_STATUSES = {
    "blocked",
    "failed",
    "failure",
    "error",
    "cancelled",
    "canceled",
}
ACTIVE_RUN_STATUSES = {
    "active",
    "claimed",
    "pending",
    "queued",
    "running",
    "started",
    "in_progress",
}
TERMINAL_RECEIPT_TYPES = {
    "a2a_task",
    "delegation_run",
    "runtime_completion",
    "task_completion",
    "task_run",
}


def runtime_db_path_from_env() -> Path:
    """Return the runtime DB path without creating it."""

    state_dir = os.environ.get("DHARMA_STATE_DIR")
    if state_dir:
        return Path(state_dir).expanduser() / "runtime.db"
    return Path.home() / ".dharma" / "state" / "runtime.db"


def runtime_truth_packets_from_runtime_db(
    db_path: Path | str | None = None,
    *,
    observed_at: str | None = None,
) -> list[RuntimeTruthPacket]:
    """Project existing runtime.db facts into read-only truth packets.

    Missing or malformed local state is rendered as NOT_READY/UNKNOWN instead
    of being repaired. That preserves the line between projection and authority.
    """

    path = Path(db_path).expanduser() if db_path is not None else runtime_db_path_from_env()
    observed = observed_at or _now_iso()
    if not path.exists():
        return [_store_packet(path, observed, present=False)]

    try:
        with _connect_read_only(path) as conn:
            conn.row_factory = sqlite3.Row
            tables = _tables(conn)
            counts = _table_counts(conn, tables)
            store_packet = _store_packet(
                path,
                observed,
                present=True,
                tables=tables,
                counts=counts,
            )
            latest = _latest_runtime_receipt(conn, tables)
            if latest is None:
                return [
                    _with_missing(
                        store_packet,
                        [
                            "latest_runtime_receipt",
                            "run_id",
                            "task_id",
                            "correlation_id",
                        ],
                    )
                ]
            return [
                store_packet,
                _packet_from_latest_runtime_receipt(
                    conn,
                    tables,
                    latest,
                    path=path,
                    observed_at=observed,
                    counts=counts,
                ),
            ]
    except Exception as exc:
        return [
            _store_packet(
                path,
                observed,
                present=True,
                probe_ok=False,
                probe_error=f"{type(exc).__name__}: {exc}",
            )
        ]


def summarize_runtime_truth_packets(
    packets: list[RuntimeTruthPacket],
) -> dict[str, Any]:
    """Return a compact operator summary from packet rows."""

    runtime_packets = [
        packet for packet in packets if packet.surface_id.startswith("runtime_state.")
    ]
    latest = next(
        (
            packet
            for packet in runtime_packets
            if packet.surface_id == "runtime_state.latest_receipt"
        ),
        None,
    )
    store = next(
        (
            packet
            for packet in runtime_packets
            if packet.surface_id == "runtime_state.store"
        ),
        None,
    )
    if latest is not None:
        return {
            "runtime_db": (latest.metadata or {}).get("runtime_db"),
            "readiness": latest.readiness_state.value,
            "latest_receipt": (latest.receipt_refs or [""])[0],
            "run_id": latest.run_id,
            "task_id": latest.task_id,
            "correlation_id": latest.correlation_id,
            "heartbeat": latest.heartbeat_state.value,
            "progress": latest.progress_state.value,
            "completion": latest.completion_state.value,
            "retry": latest.retry_state.value,
            "missing": latest.missing_machine_fields,
        }
    if store is not None:
        return {
            "runtime_db": (store.metadata or {}).get("runtime_db"),
            "readiness": store.readiness_state.value,
            "latest_receipt": None,
            "run_id": None,
            "task_id": None,
            "correlation_id": None,
            "heartbeat": store.heartbeat_state.value,
            "progress": store.progress_state.value,
            "completion": store.completion_state.value,
            "retry": store.retry_state.value,
            "missing": store.missing_machine_fields,
        }
    return {"runtime_db": None, "readiness": "unknown", "missing": ["runtime_packet"]}


def connect_runtime_db_read_only(path: Path | str) -> sqlite3.Connection:
    """Open an existing runtime.db in read-only SQLite mode."""

    return _connect_read_only(Path(path).expanduser())


def _connect_read_only(path: Path) -> sqlite3.Connection:
    uri = f"file:{quote(path.as_posix(), safe='/:')}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row[0]) for row in rows}


def _table_counts(conn: sqlite3.Connection, tables: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in (
        "runtime_receipts",
        "idempotency_records",
        "task_claims",
        "delegation_runs",
        "artifact_records",
        "execution_identities",
    ):
        if table not in tables:
            continue
        counts[table] = int(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        )
    return counts


def _latest_runtime_receipt(
    conn: sqlite3.Connection,
    tables: set[str],
) -> sqlite3.Row | None:
    if "runtime_receipts" not in tables:
        return None
    return conn.execute(
        "SELECT receipt_id, receipt_type, run_id, task_id, trace_id,"
        " correlation_id, causation_id, parent_run_id, agent_id,"
        " idempotency_key, side_effect_key, status, payload_json, created_at"
        " FROM runtime_receipts ORDER BY created_at DESC LIMIT 1"
    ).fetchone()


def _store_packet(
    path: Path,
    observed_at: str,
    *,
    present: bool,
    tables: set[str] | None = None,
    counts: dict[str, int] | None = None,
    probe_ok: bool | None = None,
    probe_error: str | None = None,
) -> RuntimeTruthPacket:
    table_set = tables or set()
    missing = [] if present else ["runtime_db"]
    missing_required_tables = [
        table for table in REQUIRED_RUNTIME_TABLES if present and table not in table_set
    ]
    if probe_error is None:
        missing.extend(f"{table}_table" for table in missing_required_tables)
    ok = (
        present and not missing_required_tables
        if probe_ok is None
        else probe_ok
    )
    readiness = RuntimeTruthState.READY_BY_PROBE
    if probe_error:
        readiness = RuntimeTruthState.UNKNOWN_BY_PROBE_ERROR
    elif not present or missing_required_tables:
        readiness = RuntimeTruthState.NOT_READY_BY_PROBE
    return RuntimeTruthPacket(
        surface_id="runtime_state.store",
        kind="local_runtime_store_probe",
        observed_at=observed_at,
        owner_surface=RUNTIME_DB_SOURCE,
        source_kind="sqlite_read_only_probe",
        source_refs=[RUNTIME_DB_SOURCE, str(path)],
        readiness_state=readiness,
        heartbeat_state=RuntimeTruthState.UNKNOWN,
        progress_state=RuntimeTruthState.UNKNOWN,
        completion_state=RuntimeTruthState.UNKNOWN,
        authority_state=RuntimeTruthState.PROJECTION_ONLY,
        source_state=RuntimeTruthState.OBSERVED if present else RuntimeTruthState.MISSING,
        probe_ok=ok,
        probe_error=probe_error,
        missing_machine_fields=missing,
        metadata={
            "runtime_db": str(path),
            "tables": sorted(table_set),
            "counts": counts or {},
            "read_only_probe": True,
        },
    )


def _packet_from_latest_runtime_receipt(
    conn: sqlite3.Connection,
    tables: set[str],
    receipt: sqlite3.Row,
    *,
    path: Path,
    observed_at: str,
    counts: dict[str, int],
) -> RuntimeTruthPacket:
    run_id = _nonempty(receipt["run_id"])
    task_id = _nonempty(receipt["task_id"])
    trace_id = _nonempty(receipt["trace_id"])
    correlation_id = _nonempty(receipt["correlation_id"])
    idempotency_key = _nonempty(receipt["idempotency_key"])
    side_effect_key = _nonempty(receipt["side_effect_key"])

    identity = _identity_for_run(conn, tables, run_id) if run_id else None
    run = _delegation_run(conn, tables, run_id, task_id)
    claim = _task_claim(conn, tables, identity, run, task_id)
    idem = _idempotency_record(
        conn,
        tables,
        run_id=run_id,
        idempotency_key=idempotency_key,
        side_effect_key=side_effect_key,
    )
    artifacts = _artifacts(conn, tables, run_id=run_id, task_id=task_id, trace_id=trace_id)
    receipt_payload = _json_map(receipt["payload_json"])

    task_id = task_id or _field(identity, "task_id") or _field(run, "task_id")
    run_id = run_id or _field(identity, "run_id") or _field(run, "run_id")
    correlation_id = correlation_id or _field(identity, "correlation_id")
    claim_id = _field(identity, "claim_id") or _field(run, "claim_id") or _field(claim, "claim_id")
    runner_id = (
        _field(identity, "agent_id")
        or _field(run, "assigned_to")
        or _field(claim, "agent_id")
        or _nonempty(receipt["agent_id"])
    )
    mission_id = _first_metadata_value(
        "mission_id",
        receipt_payload,
        _json_map(_field(identity, "metadata_json")),
        _json_map(_field(run, "metadata_json")),
        _json_map(_field(claim, "metadata_json")),
    )

    stale = _is_stale(_field(claim, "stale_after"))
    latest_artifact_at = _field(artifacts[0], "created_at") if artifacts else ""
    receipt_ref = f"runtime_receipts:{receipt['receipt_id']}"
    artifact_refs = [
        _artifact_ref(artifact)
        for artifact in artifacts
    ]
    missing = _missing_fields(
        run_id=run_id,
        task_id=task_id,
        correlation_id=correlation_id,
        receipt_refs=[receipt_ref],
        mission_id=mission_id,
        idempotency=idem,
        claim=claim,
        run=run,
        artifacts=artifacts,
    )
    return RuntimeTruthPacket(
        surface_id="runtime_state.latest_receipt",
        kind="runtime_state_reconciliation",
        observed_at=observed_at,
        owner_surface=RUNTIME_DB_SOURCE,
        source_kind="sqlite_read_only_probe",
        run_id=run_id,
        mission_id=mission_id,
        mission_id_missing=mission_id is None,
        correlation_id=correlation_id,
        correlation_id_inferred=False,
        task_id=task_id,
        claim_id=claim_id,
        runner_id=runner_id,
        receipt_refs=[receipt_ref],
        artifact_refs=artifact_refs,
        source_refs=[RUNTIME_DB_SOURCE, str(path)],
        heartbeat_state=_heartbeat_state(claim, stale=stale),
        readiness_state=RuntimeTruthState.READY_BY_PROBE,
        progress_state=_progress_state(run, artifacts, stale=stale),
        completion_state=_completion_state(receipt, run),
        authority_state=RuntimeTruthState.PROJECTION_ONLY,
        source_state=RuntimeTruthState.OBSERVED,
        projection_state=RuntimeTruthState.PROJECTION_ONLY,
        retry_state=_retry_state(idem),
        probe_ok=True,
        stale_after=_field(claim, "stale_after") or None,
        stale_reason="task_claim_stale_after_elapsed" if stale else None,
        last_heartbeat_at=_field(claim, "heartbeat_at") or None,
        last_progress_at=latest_artifact_at or _field(run, "started_at") or None,
        last_receipt_at=str(receipt["created_at"] or "") or None,
        retry_intent_key=idempotency_key or None,
        missing_machine_fields=missing,
        metadata={
            "runtime_db": str(path),
            "runtime_table_counts": counts,
            "receipt_id": str(receipt["receipt_id"]),
            "receipt_type": str(receipt["receipt_type"]),
            "receipt_status": str(receipt["status"]),
            "idempotency_status": _field(idem, "status"),
            "side_effect_key": side_effect_key,
            "delegation_status": _field(run, "status"),
            "task_claim_status": _field(claim, "status"),
            "artifact_count_for_latest": len(artifacts),
            "read_only_probe": True,
        },
    )


def _identity_for_run(
    conn: sqlite3.Connection,
    tables: set[str],
    run_id: str | None,
) -> sqlite3.Row | None:
    if not run_id or "execution_identities" not in tables:
        return None
    return conn.execute(
        "SELECT run_id, trace_id, correlation_id, task_id, claim_id,"
        " idempotency_key, causation_id, parent_run_id, agent_id,"
        " session_id, external_a2a_task_id, message_id, event_id,"
        " artifact_id, proposal_id, metadata_json"
        " FROM execution_identities WHERE run_id = ?",
        (run_id,),
    ).fetchone()


def _delegation_run(
    conn: sqlite3.Connection,
    tables: set[str],
    run_id: str | None,
    task_id: str | None,
) -> sqlite3.Row | None:
    if "delegation_runs" not in tables:
        return None
    if run_id:
        row = conn.execute(
            "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
            " assigned_by, assigned_to, current_artifact_id, status,"
            " started_at, completed_at, failure_code, metadata_json"
            " FROM delegation_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is not None:
            return row
    if task_id:
        return conn.execute(
            "SELECT run_id, session_id, task_id, claim_id, parent_run_id,"
            " assigned_by, assigned_to, current_artifact_id, status,"
            " started_at, completed_at, failure_code, metadata_json"
            " FROM delegation_runs WHERE task_id = ?"
            " ORDER BY started_at DESC LIMIT 1",
            (task_id,),
        ).fetchone()
    return None


def _task_claim(
    conn: sqlite3.Connection,
    tables: set[str],
    identity: sqlite3.Row | None,
    run: sqlite3.Row | None,
    task_id: str | None,
) -> sqlite3.Row | None:
    if "task_claims" not in tables:
        return None
    claim_id = _field(identity, "claim_id") or _field(run, "claim_id")
    if claim_id:
        row = conn.execute(
            "SELECT claim_id, task_id, agent_id, status, session_id,"
            " claimed_at, acked_at, heartbeat_at, stale_after, recovered_at,"
            " retry_count, metadata_json, trace_id"
            " FROM task_claims WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if row is not None:
            return row
    if task_id:
        return conn.execute(
            "SELECT claim_id, task_id, agent_id, status, session_id,"
            " claimed_at, acked_at, heartbeat_at, stale_after, recovered_at,"
            " retry_count, metadata_json, trace_id"
            " FROM task_claims WHERE task_id = ?"
            " ORDER BY claimed_at DESC LIMIT 1",
            (task_id,),
        ).fetchone()
    return None


def _idempotency_record(
    conn: sqlite3.Connection,
    tables: set[str],
    *,
    run_id: str | None,
    idempotency_key: str | None,
    side_effect_key: str | None,
) -> sqlite3.Row | None:
    if "idempotency_records" not in tables:
        return None
    if idempotency_key and side_effect_key:
        row = conn.execute(
            "SELECT idempotency_key, side_effect_key, run_id, task_id,"
            " trace_id, correlation_id, status, result_receipt_id,"
            " metadata_json, created_at, updated_at"
            " FROM idempotency_records"
            " WHERE idempotency_key = ? AND side_effect_key = ?",
            (idempotency_key, side_effect_key),
        ).fetchone()
        if row is not None:
            return row
    if run_id:
        return conn.execute(
            "SELECT idempotency_key, side_effect_key, run_id, task_id,"
            " trace_id, correlation_id, status, result_receipt_id,"
            " metadata_json, created_at, updated_at"
            " FROM idempotency_records WHERE run_id = ?"
            " ORDER BY updated_at DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    return None


def _artifacts(
    conn: sqlite3.Connection,
    tables: set[str],
    *,
    run_id: str | None,
    task_id: str | None,
    trace_id: str | None,
) -> list[sqlite3.Row]:
    if "artifact_records" not in tables:
        return []
    clauses: list[str] = []
    params: list[str] = []
    for column, value in (
        ("run_id", run_id),
        ("task_id", task_id),
        ("trace_id", trace_id),
    ):
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    if not clauses:
        return []
    return conn.execute(
        "SELECT artifact_id, artifact_kind, session_id, task_id, run_id,"
        " trace_id, manifest_path, payload_path, checksum, parent_artifact_id,"
        " promotion_state, created_at, metadata_json"
        f" FROM artifact_records WHERE {' OR '.join(clauses)}"
        " ORDER BY created_at DESC LIMIT 20",
        params,
    ).fetchall()


def _with_missing(
    packet: RuntimeTruthPacket,
    missing: list[str],
) -> RuntimeTruthPacket:
    return replace(
        packet,
        missing_machine_fields=[
            *packet.missing_machine_fields,
            *[field for field in missing if field not in packet.missing_machine_fields],
        ],
    )


def _nonempty(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _field(row: sqlite3.Row | None, name: str) -> str:
    if row is None:
        return ""
    try:
        return str(row[name] or "")
    except (IndexError, KeyError):
        return ""


def _json_map(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        loaded = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _first_metadata_value(key: str, *maps: dict[str, Any]) -> str | None:
    for item in maps:
        value = item.get(key)
        if value:
            return str(value)
    return None


def _is_stale(stale_after: str) -> bool:
    if not stale_after:
        return False
    parsed = _parse_datetime(stale_after)
    return bool(parsed and parsed < datetime.now(timezone.utc))


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = f"{value[:-1]}+00:00"
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _heartbeat_state(
    claim: sqlite3.Row | None,
    *,
    stale: bool,
) -> RuntimeTruthState:
    if claim is None:
        return RuntimeTruthState.UNKNOWN
    if stale:
        return RuntimeTruthState.STALLED_BY_ARTIFACT_PROGRESS
    if _field(claim, "heartbeat_at"):
        return RuntimeTruthState.RUNNING_BY_HEARTBEAT
    return RuntimeTruthState.OBSERVED


def _progress_state(
    run: sqlite3.Row | None,
    artifacts: list[sqlite3.Row],
    *,
    stale: bool,
) -> RuntimeTruthState:
    if stale:
        return RuntimeTruthState.STALLED_BY_ARTIFACT_PROGRESS
    if artifacts or _field(run, "current_artifact_id"):
        return RuntimeTruthState.PROGRESSING_BY_ARTIFACT
    status = _field(run, "status").lower()
    if status in {"blocked", "failed", "failure", "error"}:
        return RuntimeTruthState.BLOCKED_BY_RECEIPT
    return RuntimeTruthState.UNKNOWN


def _completion_state(
    receipt: sqlite3.Row,
    run: sqlite3.Row | None,
) -> RuntimeTruthState:
    receipt_status = str(receipt["status"] or "").lower()
    receipt_type = str(receipt["receipt_type"] or "").lower()
    run_status = _field(run, "status").lower()
    if run_status in TERMINAL_BLOCKED_STATUSES:
        return RuntimeTruthState.BLOCKED_BY_RECEIPT
    if run_status in TERMINAL_SUCCESS_STATUSES or _field(run, "completed_at"):
        return RuntimeTruthState.COMPLETED_BY_RECEIPT
    if run_status in ACTIVE_RUN_STATUSES:
        return RuntimeTruthState.UNKNOWN
    if (
        receipt_type in TERMINAL_RECEIPT_TYPES
        and receipt_status in TERMINAL_BLOCKED_STATUSES
    ):
        return RuntimeTruthState.BLOCKED_BY_RECEIPT
    if (
        receipt_type in TERMINAL_RECEIPT_TYPES
        and receipt_status in TERMINAL_SUCCESS_STATUSES
    ):
        return RuntimeTruthState.COMPLETED_BY_RECEIPT
    return RuntimeTruthState.UNKNOWN


def _retry_state(record: sqlite3.Row | None) -> RuntimeTruthState:
    status = _field(record, "status").lower()
    if not status:
        return RuntimeTruthState.UNKNOWN
    if status in {"completed", "skipped"}:
        return RuntimeTruthState.RETRY_EQUIVALENT
    if status in {"parameter_mismatch", "conflict"}:
        return RuntimeTruthState.RETRY_PARAMETER_MISMATCH
    return RuntimeTruthState.OBSERVED


def _artifact_ref(artifact: sqlite3.Row) -> str:
    path = _field(artifact, "payload_path") or _field(artifact, "manifest_path")
    if path:
        return f"artifact_records:{artifact['artifact_id']}:{path}"
    return f"artifact_records:{artifact['artifact_id']}"


def _missing_fields(
    *,
    run_id: str | None,
    task_id: str | None,
    correlation_id: str | None,
    receipt_refs: list[str],
    mission_id: str | None,
    idempotency: sqlite3.Row | None,
    claim: sqlite3.Row | None,
    run: sqlite3.Row | None,
    artifacts: list[sqlite3.Row],
) -> list[str]:
    fields: list[str] = []
    if not run_id:
        fields.append("run_id")
    if not task_id:
        fields.append("task_id")
    if not correlation_id:
        fields.append("correlation_id")
    if not receipt_refs:
        fields.append("receipt_refs")
    if not mission_id:
        fields.append("mission_id")
    if idempotency is None:
        fields.append("idempotency_record")
    if claim is None:
        fields.append("task_claim")
    if run is None:
        fields.append("delegation_run")
    if not artifacts:
        fields.append("artifact_refs")
    return fields
