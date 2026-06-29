"""Read-only runtime truth projections over existing runtime owners.

This module deliberately does not initialize or migrate runtime state. It
opens runtime.db in SQLite read-only mode and projects what is already there
into ProjectionRuntimeTruthPacket rows.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .contracts import RuntimeTruthPacket as ProjectionRuntimeTruthPacket, RuntimeTruthState as ProjectionRuntimeTruthState


class RuntimeTruthState(StrEnum):
    RUNNING_BY_HEARTBEAT = "RUNNING_BY_HEARTBEAT"
    PROGRESSING_BY_ARTIFACT = "PROGRESSING_BY_ARTIFACT"
    STALLED_BY_ARTIFACT_PROGRESS = "STALLED_BY_ARTIFACT_PROGRESS"
    BLOCKED_BY_RECEIPT = "BLOCKED_BY_RECEIPT"
    COMPLETED_BY_RECEIPT = "COMPLETED_BY_RECEIPT"
    EXTERNAL_GATED = "EXTERNAL_GATED"
    DEGRADED_BY_PROBE_FAILURE = "DEGRADED_BY_PROBE_FAILURE"
    PROJECTION_ONLY = "PROJECTION_ONLY"
    CACHE_ONLY_NON_AUTHORITATIVE = "CACHE_ONLY_NON_AUTHORITATIVE"
    UNKNOWN = "UNKNOWN"


class ProofGrade(StrEnum):
    """Scoped proof verdict for a runtime truth — the read-only projection of the
    graded claim/evidence binding (docs/governance/evidence_grades.yaml, enforced
    by scripts/governance/check_track_status.py). This is NOT authority: it
    reports the strongest evidence grade that a claim's truth currently rests on,
    so an operator can see at a glance whether a packet is locally proven,
    CI-proven, externally gated, unproven, or quarantined.
    """

    LOCAL_PROVEN = "LOCAL_PROVEN"          # verified machine receipt, locally
    CI_PROVEN = "CI_PROVEN"                # proven by independent CI / verifier
    EXTERNAL_GATED = "EXTERNAL_GATED"      # awaiting an external acted receipt
    MISSING = "MISSING"                    # no evidence binding yet
    QUARANTINED = "QUARANTINED"            # evidence present but tamper/stale -> distrust


class RuntimeSourceKind(StrEnum):
    DIRECT_PROBE = "direct_probe"
    RECEIPT = "receipt"
    ARTIFACT = "artifact"
    CACHE_FILE = "cache_file"
    DECLARED_INTENT = "declared_intent"
    DERIVED_RECONCILIATION = "derived_reconciliation"
    EXTERNAL_OPERATOR_STATE = "external_operator_state"
    PROBE_FAILURE = "probe_failure"
    PROBE_SKIPPED = "probe_skipped"
    MANUAL_FIXTURE = "manual_fixture"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def stable_payload_hash(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(data.encode('utf-8')).hexdigest()}"


def file_ref(path: Path | str, *, repo_root: Path | None = None, kind: str = "artifact") -> dict[str, Any]:
    resolved = Path(path).expanduser()
    display = str(resolved)
    if repo_root is not None:
        try:
            display = str(resolved.relative_to(repo_root))
        except ValueError:
            display = str(resolved)
    exists = resolved.exists()
    return {
        "kind": kind,
        "path": display,
        "exists": exists,
        "sha256": sha256_file(resolved) if exists and resolved.is_file() else "",
    }


@dataclass(slots=True)
class ProbeTruth:
    command: list[str] = field(default_factory=list)
    observed_at: str = ""
    ok: bool | None = None
    returncode: int | None = None
    error: str = ""
    source_kind: str = RuntimeSourceKind.DIRECT_PROBE.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MutationTruth:
    repo_files_changed: bool = False
    external_actions: bool = False
    process_actions: bool = False
    archive_fitness_mutated: bool = False
    payment_or_publish: bool = False
    push_merge: bool = False
    dry_run_only: bool = False
    human_review_candidate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RuntimeTruthPacket:
    surface_id: str
    kind: str
    run_id: str = ""
    mission_id: str = ""
    correlation_id: str = ""
    correlation_id_inferred: bool = False
    task_id: str = ""
    claim_id: str = ""
    runner_id: str = ""
    receipt_refs: list[dict[str, Any]] = field(default_factory=list)
    artifact_refs: list[dict[str, Any]] = field(default_factory=list)
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    heartbeat_state: str = RuntimeTruthState.UNKNOWN.value
    progress_state: str = RuntimeTruthState.UNKNOWN.value
    completion_state: str = RuntimeTruthState.UNKNOWN.value
    authority_state: str = RuntimeTruthState.PROJECTION_ONLY.value
    mutation_truth: MutationTruth = field(default_factory=MutationTruth)
    source_kind: str = RuntimeSourceKind.DERIVED_RECONCILIATION.value
    probe_truth: ProbeTruth = field(default_factory=ProbeTruth)
    missing_machine_fields: list[str] = field(default_factory=list)
    # Read-only scoped proof verdict — strongest evidence grade this truth rests
    # on. Projection only; never an authority surface (see ProofGrade docstring).
    proof_grade: str = ProofGrade.MISSING.value

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mutation_truth"] = self.mutation_truth.to_dict()
        payload["probe_truth"] = self.probe_truth.to_dict()
        return payload


def task_counts(tasks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"open": 0, "claimed": 0, "completed": 0, "failed": 0, "blocked": 0}
    for task in tasks:
        status = str(task.get("status") or "open")
        counts[status] = counts.get(status, 0) + 1
    counts["total"] = len(tasks)
    return counts


def reconcile_tasks_from_receipts(
    tasks: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    *,
    closing_statuses: set[str],
    nonclosing_statuses: set[str],
    observed_at: str | None = None,
) -> dict[str, Any]:
    observed = observed_at or utc_now()
    raw_counts = task_counts(tasks)
    latest_by_task: dict[str, dict[str, Any]] = {}
    closing_seen: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        task_id = str(receipt.get("task_id") or "")
        status = str(receipt.get("status") or "")
        if task_id and (status in closing_statuses or status in nonclosing_statuses):
            latest_by_task[task_id] = receipt
        if task_id and status in closing_statuses:
            closing_seen[task_id] = receipt

    reconciled_tasks = copy.deepcopy(tasks)
    changes: list[dict[str, Any]] = []
    terminal_receipts: list[dict[str, Any]] = []
    superseded_terminal_receipts: list[dict[str, Any]] = []
    missing_machine_fields: list[str] = []
    for task in reconciled_tasks:
        task_id = str(task.get("task_id") or "")
        if not task_id:
            missing_machine_fields.append("task_id")
            continue
        latest = latest_by_task.get(task_id)
        closing = closing_seen.get(task_id)
        if closing and latest is not closing:
            superseded_terminal_receipts.append(
                {
                    "task_id": task_id,
                    "receipt_id": str(closing.get("receipt_id") or ""),
                    "terminal_status": str(closing.get("status") or ""),
                    "superseded_by_status": str(latest.get("status") or "") if latest else "",
                    "superseded_by_receipt_id": str(latest.get("receipt_id") or "") if latest else "",
                }
            )
        if not latest or str(latest.get("status") or "") not in closing_statuses:
            continue
        old_status = str(task.get("status") or "open")
        receipt_status = str(latest.get("status") or "")
        task["status"] = receipt_status
        task["updated_at"] = str(latest.get("created_at") or observed)
        task["closed_by_receipt"] = True
        task["receipt_id"] = str(latest.get("receipt_id") or "")
        terminal_receipts.append(
            {
                "task_id": task_id,
                "receipt_id": task["receipt_id"],
                "status": receipt_status,
                "artifact_path": str(latest.get("artifact_path") or ""),
                "evidence_present": bool(latest.get("evidence")),
            }
        )
        if receipt_status == "completed" and not latest.get("evidence"):
            missing_machine_fields.append(f"completed_evidence:{task_id}")
        if old_status != receipt_status:
            changes.append(
                {
                    "task_id": task_id,
                    "from": old_status,
                    "to": receipt_status,
                    "receipt_id": task["receipt_id"],
                }
            )

    reconciled_counts = task_counts(reconciled_tasks)
    progress_states: list[str] = []
    if reconciled_counts.get("completed", 0):
        progress_states.append(RuntimeTruthState.COMPLETED_BY_RECEIPT.value)
    if reconciled_counts.get("blocked", 0) or reconciled_counts.get("failed", 0):
        progress_states.append(RuntimeTruthState.BLOCKED_BY_RECEIPT.value)
    if raw_counts.get("claimed", 0) and not changes:
        progress_states.append(RuntimeTruthState.RUNNING_BY_HEARTBEAT.value)
    if changes:
        progress_states.append(RuntimeTruthState.PROGRESSING_BY_ARTIFACT.value)
    if not progress_states:
        progress_states.append(RuntimeTruthState.UNKNOWN.value)

    summary = {
        "schema_version": "dharma.autonomy_reconciled_task_summary.v1",
        "observed_at": observed,
        "authority_state": RuntimeTruthState.PROJECTION_ONLY.value,
        "source_kind": RuntimeSourceKind.DERIVED_RECONCILIATION.value,
        "raw_counts": raw_counts,
        "reconciled_counts": reconciled_counts,
        "raw_reconciled_mismatch": raw_counts != reconciled_counts,
        "changed_task_ids": [change["task_id"] for change in changes],
        "changes": changes,
        "terminal_receipts": terminal_receipts,
        "superseded_terminal_receipts": superseded_terminal_receipts,
        "progress_states": progress_states,
        "missing_machine_fields": sorted(set(missing_machine_fields)),
    }
    summary["idempotency_key"] = stable_payload_hash(
        {
            "raw_counts": raw_counts,
            "reconciled_counts": reconciled_counts,
            "changes": changes,
            "terminal_receipts": terminal_receipts,
            "superseded_terminal_receipts": superseded_terminal_receipts,
        }
    )

    return {
        **summary,
        "tasks": reconciled_tasks,
        "summary": summary,
    }



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
) -> list[ProjectionRuntimeTruthPacket]:
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
    packets: list[ProjectionRuntimeTruthPacket],
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
            "mission_id": latest.mission_id,
            "artifact_refs": list(latest.artifact_refs or ()),
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
            "mission_id": None,
            "artifact_refs": [],
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
) -> ProjectionRuntimeTruthPacket:
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
    readiness = ProjectionRuntimeTruthState.READY_BY_PROBE
    if probe_error:
        readiness = ProjectionRuntimeTruthState.UNKNOWN_BY_PROBE_ERROR
    elif not present or missing_required_tables:
        readiness = ProjectionRuntimeTruthState.NOT_READY_BY_PROBE
    return ProjectionRuntimeTruthPacket(
        surface_id="runtime_state.store",
        kind="local_runtime_store_probe",
        observed_at=observed_at,
        owner_surface=RUNTIME_DB_SOURCE,
        source_kind="sqlite_read_only_probe",
        source_refs=[RUNTIME_DB_SOURCE, str(path)],
        readiness_state=readiness,
        heartbeat_state=ProjectionRuntimeTruthState.UNKNOWN,
        progress_state=ProjectionRuntimeTruthState.UNKNOWN,
        completion_state=ProjectionRuntimeTruthState.UNKNOWN,
        authority_state=ProjectionRuntimeTruthState.PROJECTION_ONLY,
        source_state=ProjectionRuntimeTruthState.OBSERVED if present else ProjectionRuntimeTruthState.MISSING,
        probe_ok=ok,
        probe_error=probe_error,
        missing_machine_fields=missing,
        proof_grade=ProofGrade.MISSING.value,
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
) -> ProjectionRuntimeTruthPacket:
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
    no_artifact_refs_reason = _first_metadata_value(
        "no_artifact_refs_reason",
        receipt_payload,
        _json_map(_field(identity, "metadata_json")),
        _json_map(_field(run, "metadata_json")),
        _json_map(_field(claim, "metadata_json")),
    )

    stale = _is_stale(_field(claim, "stale_after"))
    latest_artifact_at = _field(artifacts[0], "created_at") if artifacts else ""
    receipt_ref = f"runtime_receipts:{receipt['receipt_id']}"
    artifact_refs = _artifact_refs(artifacts, run)
    missing = _missing_fields(
        run_id=run_id,
        task_id=task_id,
        correlation_id=correlation_id,
        receipt_refs=[receipt_ref],
        mission_id=mission_id,
        idempotency=idem,
        claim=claim,
        run=run,
        artifact_refs=artifact_refs,
        no_artifact_refs_reason=no_artifact_refs_reason or "",
    )
    return ProjectionRuntimeTruthPacket(
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
        source_refs=[
            RUNTIME_DB_SOURCE,
            str(path),
            *([_idempotency_ref(idem)] if idem is not None else []),
        ],
        heartbeat_state=_heartbeat_state(claim, stale=stale),
        readiness_state=ProjectionRuntimeTruthState.READY_BY_PROBE,
        progress_state=_progress_state(run, artifacts, stale=stale),
        completion_state=_completion_state(receipt, run),
        authority_state=ProjectionRuntimeTruthState.PROJECTION_ONLY,
        source_state=ProjectionRuntimeTruthState.OBSERVED,
        projection_state=ProjectionRuntimeTruthState.PROJECTION_ONLY,
        retry_state=_retry_state(idem),
        probe_ok=True,
        stale_after=_field(claim, "stale_after") or None,
        stale_reason="task_claim_stale_after_elapsed" if stale else None,
        last_heartbeat_at=_field(claim, "heartbeat_at") or None,
        last_progress_at=latest_artifact_at or _field(run, "started_at") or None,
        last_receipt_at=str(receipt["created_at"] or "") or None,
        retry_intent_key=idempotency_key or None,
        missing_machine_fields=missing,
        proof_grade=ProofGrade.MISSING.value,
        metadata={
            "runtime_db": str(path),
            "runtime_table_counts": counts,
            "receipt_id": str(receipt["receipt_id"]),
            "receipt_type": str(receipt["receipt_type"]),
            "receipt_status": str(receipt["status"]),
            "idempotency_status": _field(idem, "status"),
            "idempotency_record_ref": _idempotency_ref(idem) if idem is not None else "",
            "idempotency_result_receipt_ref": (
                f"runtime_receipts:{_field(idem, 'result_receipt_id')}"
                if _field(idem, "result_receipt_id")
                else ""
            ),
            "side_effect_key": side_effect_key,
            "delegation_status": _field(run, "status"),
            "task_claim_status": _field(claim, "status"),
            "artifact_count_for_latest": len(artifacts),
            "no_artifact_refs_reason": no_artifact_refs_reason or "",
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
    packet: ProjectionRuntimeTruthPacket,
    missing: list[str],
) -> ProjectionRuntimeTruthPacket:
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
) -> ProjectionRuntimeTruthState:
    if claim is None:
        return ProjectionRuntimeTruthState.UNKNOWN
    if stale:
        return ProjectionRuntimeTruthState.STALLED_BY_ARTIFACT_PROGRESS
    if _field(claim, "heartbeat_at"):
        return ProjectionRuntimeTruthState.RUNNING_BY_HEARTBEAT
    return ProjectionRuntimeTruthState.OBSERVED


def _progress_state(
    run: sqlite3.Row | None,
    artifacts: list[sqlite3.Row],
    *,
    stale: bool,
) -> ProjectionRuntimeTruthState:
    if stale:
        return ProjectionRuntimeTruthState.STALLED_BY_ARTIFACT_PROGRESS
    if artifacts or _field(run, "current_artifact_id"):
        return ProjectionRuntimeTruthState.PROGRESSING_BY_ARTIFACT
    status = _field(run, "status").lower()
    if status in {"blocked", "failed", "failure", "error"}:
        return ProjectionRuntimeTruthState.BLOCKED_BY_RECEIPT
    return ProjectionRuntimeTruthState.UNKNOWN


def _completion_state(
    receipt: sqlite3.Row,
    run: sqlite3.Row | None,
) -> ProjectionRuntimeTruthState:
    receipt_status = str(receipt["status"] or "").lower()
    receipt_type = str(receipt["receipt_type"] or "").lower()
    run_status = _field(run, "status").lower()
    if run_status in TERMINAL_BLOCKED_STATUSES:
        return ProjectionRuntimeTruthState.BLOCKED_BY_RECEIPT
    if run_status in TERMINAL_SUCCESS_STATUSES or _field(run, "completed_at"):
        return ProjectionRuntimeTruthState.COMPLETED_BY_RECEIPT
    if run_status in ACTIVE_RUN_STATUSES:
        return ProjectionRuntimeTruthState.UNKNOWN
    if (
        receipt_type in TERMINAL_RECEIPT_TYPES
        and receipt_status in TERMINAL_BLOCKED_STATUSES
    ):
        return ProjectionRuntimeTruthState.BLOCKED_BY_RECEIPT
    if (
        receipt_type in TERMINAL_RECEIPT_TYPES
        and receipt_status in TERMINAL_SUCCESS_STATUSES
    ):
        return ProjectionRuntimeTruthState.COMPLETED_BY_RECEIPT
    return ProjectionRuntimeTruthState.UNKNOWN


def _retry_state(record: sqlite3.Row | None) -> ProjectionRuntimeTruthState:
    status = _field(record, "status").lower()
    if not status:
        return ProjectionRuntimeTruthState.UNKNOWN
    if status in {"completed", "skipped"}:
        return ProjectionRuntimeTruthState.RETRY_EQUIVALENT
    if status in {"parameter_mismatch", "conflict"}:
        return ProjectionRuntimeTruthState.RETRY_PARAMETER_MISMATCH
    return ProjectionRuntimeTruthState.OBSERVED


def _artifact_refs(artifacts: list[sqlite3.Row], run: sqlite3.Row | None) -> list[str]:
    refs = [_artifact_ref(artifact) for artifact in artifacts]
    current_artifact_id = _field(run, "current_artifact_id")
    if current_artifact_id and not any(current_artifact_id in ref for ref in refs):
        run_id = _field(run, "run_id")
        refs.append(f"delegation_runs:{run_id}:current_artifact_id:{current_artifact_id}")
    return refs


def _artifact_ref(artifact: sqlite3.Row) -> str:
    path = _field(artifact, "payload_path") or _field(artifact, "manifest_path")
    if path:
        return f"artifact_records:{artifact['artifact_id']}:{path}"
    return f"artifact_records:{artifact['artifact_id']}"


def _idempotency_ref(idempotency: sqlite3.Row) -> str:
    return (
        "idempotency_records:"
        f"{_field(idempotency, 'idempotency_key')}:"
        f"{_field(idempotency, 'side_effect_key')}"
    )


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
    artifact_refs: list[str],
    no_artifact_refs_reason: str = "",
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
    if not artifact_refs and not str(no_artifact_refs_reason or "").strip():
        fields.append("artifact_refs")
    return fields


__all__ = [
    "MutationTruth",
    "ProbeTruth",
    "RuntimeSourceKind",
    "RuntimeTruthPacket",
    "RuntimeTruthState",
    "connect_runtime_db_read_only",
    "file_ref",
    "reconcile_tasks_from_receipts",
    "runtime_db_path_from_env",
    "runtime_truth_packets_from_runtime_db",
    "sha256_file",
    "stable_payload_hash",
    "summarize_runtime_truth_packets",
    "task_counts",
    "utc_now",
]
