"""Control Surface API — declared intent vs observed reality.

GET  /api/control-surface/summary         -> coherence summary (envelope)
GET  /api/control-surface/rows            -> full list of ControlSurfaceRow (envelope)
GET  /api/control-surface/rows/{id}       -> single row by id (envelope)
GET  /api/control-surface/ds-goal/cards   -> ds-goal ledgers as BoardStore cards (envelope)
GET  /api/control-surface/agentops/cards  -> AgentOps work packets as BoardStore cards (envelope)
GET  /api/control-surface/a2a/cards       -> A2A receipts as BoardStore cards (envelope)
GET  /api/control-surface/semantic-receipts/cards -> SemanticReceipt artifacts as BoardStore cards (envelope)
GET  /api/control-surface/missions/{id}/snapshot -> one injected read-only MissionSnapshot
POST /api/control-surface/rows/{id}/handoff-prompt -> agent handoff prompt
GET  /api/control-surface/stream          -> SSE stream of updated rows

ACTIVE_SURFACE_MANIFEST.yaml declares intent; observed reality comes from
runtime/code/evidence adapters.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from dharma_swarm.daemon_config import runtime_report_dir
from dharma_swarm.mission_control_contract import (
    ACTIVE_CLAIM_STATUSES,
    OPEN_CLAIM_STATUSES,
    OWNER_TERMINAL_ATTEMPT_STATUSES,
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION,
    TERMINAL_RECEIPT_TYPE,
    ReconciliationState,
    public_attempt_status,
    stable_id,
)
from dharma_swarm.models import TaskPriority, TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/control-surface", tags=["control-surface"])
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DS_GOAL_STATE_ROOT = Path.home() / ".dharma" / "ds_goals"
_AGENTOPS_WORK_PACKET_ROOT = _REPO_ROOT / "reports" / "agentops" / "work_packets"
_A2A_SEND_RECEIPT_ROOT = runtime_report_dir("a2a", "send_receipts")
_A2A_INBOX_BRIDGE_RECEIPT_ROOT = runtime_report_dir("a2a", "inbox_bridge_receipts")
_A2A_DOMAIN_REPLY_RECEIPT_ROOT = runtime_report_dir("a2a", "domain_reply_receipts")
_A2A_REPLY_RECEIPT_ROOT = runtime_report_dir("a2a", "reply_receipts")
_SEMANTIC_RECEIPT_ROOT = runtime_report_dir("agentops", "semantic_receipts")
_IMPORT_LOCK = threading.Lock()
_ENVELOPE_TYPES: tuple[Any, Any, Any] | None = None
_CONTROL_SURFACE_FUNCS: tuple[Any, Any, Any] | None = None
_DS_GOAL_CARD_LOADER: Any | None = None
_AGENTOPS_CARD_LOADER: Any | None = None
_A2A_SEND_CARD_LOADER: Any | None = None
_SEMANTIC_RECEIPT_CARD_LOADER: Any | None = None
_MISSION_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}")
_SAFE_ERROR_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,79}")
_MISSION_AUTHORITY = "TaskBoard+RuntimeStateStore"
_TASK_STATUSES = frozenset(member.value for member in TaskStatus)
_TASK_PRIORITIES = frozenset(member.value for member in TaskPriority)
_ATTEMPT_STATUSES = frozenset(
    {"queued", "running"}
    | {public_attempt_status(status) for status in OWNER_TERMINAL_ATTEMPT_STATUSES}
)
_LEASE_STATUSES = frozenset(
    {*OPEN_CLAIM_STATUSES, "completed", "failed", "stale_recovered"}
)
_RECONCILIATION_STATES = frozenset(member.value for member in ReconciliationState)
_MISSION_SNAPSHOT_FIELDS = frozenset(
    {
        "mission",
        "tasks",
        "attempts",
        "leases",
        "receipts",
        "reconciliation",
        "observed_at",
        "authority",
        "proves_executor_liveness",
    }
)


def _get_envelope_types() -> tuple[Any, Any, Any]:
    global _ENVELOPE_TYPES
    if _ENVELOPE_TYPES is None:
        with _IMPORT_LOCK:
            if _ENVELOPE_TYPES is None:
                from dharma_swarm.operator_core.control_surface_models import (
                    ControlSurfaceEnvelope,
                    SourceError,
                    _utc_now_iso,
                )

                _ENVELOPE_TYPES = (ControlSurfaceEnvelope, SourceError, _utc_now_iso)
    return _ENVELOPE_TYPES


def _get_control_surface_funcs() -> tuple[Any, Any, Any]:
    global _CONTROL_SURFACE_FUNCS
    if _CONTROL_SURFACE_FUNCS is None:
        with _IMPORT_LOCK:
            if _CONTROL_SURFACE_FUNCS is None:
                from dharma_swarm.operator_core.control_surface import (
                    build_control_surface_rows,
                    build_control_surface_summary,
                    generate_handoff_prompt,
                )

                _CONTROL_SURFACE_FUNCS = (
                    build_control_surface_rows,
                    build_control_surface_summary,
                    generate_handoff_prompt,
                )
    return _CONTROL_SURFACE_FUNCS


def _get_ds_goal_card_loader():  # noqa: ANN202
    global _DS_GOAL_CARD_LOADER
    if _DS_GOAL_CARD_LOADER is None:
        with _IMPORT_LOCK:
            if _DS_GOAL_CARD_LOADER is None:
                from dharma_swarm.board.adapters.ds_goal_adapter import load_ds_goal_cards

                _DS_GOAL_CARD_LOADER = load_ds_goal_cards
    return _DS_GOAL_CARD_LOADER


def _get_agentops_card_loader():  # noqa: ANN202
    global _AGENTOPS_CARD_LOADER
    if _AGENTOPS_CARD_LOADER is None:
        with _IMPORT_LOCK:
            if _AGENTOPS_CARD_LOADER is None:
                from dharma_swarm.board.adapters.agentops_adapter import load_agentops_cards

                _AGENTOPS_CARD_LOADER = load_agentops_cards
    return _AGENTOPS_CARD_LOADER


def _get_a2a_send_card_loader():  # noqa: ANN202
    global _A2A_SEND_CARD_LOADER
    if _A2A_SEND_CARD_LOADER is None:
        with _IMPORT_LOCK:
            if _A2A_SEND_CARD_LOADER is None:
                from dharma_swarm.board.adapters.a2a_send_adapter import load_a2a_send_cards

                _A2A_SEND_CARD_LOADER = load_a2a_send_cards
    return _A2A_SEND_CARD_LOADER


def _get_semantic_receipt_card_loader():  # noqa: ANN202
    global _SEMANTIC_RECEIPT_CARD_LOADER
    if _SEMANTIC_RECEIPT_CARD_LOADER is None:
        with _IMPORT_LOCK:
            if _SEMANTIC_RECEIPT_CARD_LOADER is None:
                from dharma_swarm.board.adapters.semantic_receipt_adapter import (
                    load_semantic_receipt_cards,
                )

                _SEMANTIC_RECEIPT_CARD_LOADER = load_semantic_receipt_cards
    return _SEMANTIC_RECEIPT_CARD_LOADER


def _build_envelope(data: Any, source_errors: list[dict[str, str]] | None = None) -> dict[str, Any]:
    ControlSurfaceEnvelope, SourceError, _utc_now_iso = _get_envelope_types()
    errors = [SourceError(**e) for e in (source_errors or [])]
    envelope = ControlSurfaceEnvelope(
        schema_version="0.2.0",
        request_id=str(uuid.uuid4()),
        generated_at=_utc_now_iso(),
        source_errors=errors,
        data=data,
    )
    return envelope.model_dump()


def _build_rows_with_errors(
    *,
    memory_depth: str = "snapshot",
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Build rows and collect any source errors encountered."""
    build_control_surface_rows, _, _ = _get_control_surface_funcs()
    source_errors: list[dict[str, str]] = []
    try:
        rows = build_control_surface_rows(memory_depth=memory_depth)
    except Exception as exc:
        logger.exception("control-surface projection failed")
        source_errors.append({"source": "projection_engine", "error": str(exc)})
        return [], source_errors
    return [row.to_dict() for row in rows], source_errors


def _build_rows(*, memory_depth: str = "snapshot") -> list[dict[str, Any]]:
    rows, _ = _build_rows_with_errors(memory_depth=memory_depth)
    return rows


def _find_row_object(row_id: str, *, memory_depth: str = "snapshot"):  # noqa: ANN202
    build_control_surface_rows, _, _ = _get_control_surface_funcs()
    rows = build_control_surface_rows(memory_depth=memory_depth)
    for row in rows:
        if row.id == row_id:
            return row
    return None


def _mission_snapshot_projection(
    mission_id: str,
    *,
    state: str,
    snapshot: dict[str, Any] | None = None,
    runtime_projection_mode: str = "unavailable",
) -> dict[str, Any]:
    """Build a non-promotional read model for one explicit mission."""
    return {
        "schema_version": "dharma.control_surface.mission_snapshot_projection.v1",
        "mission_id": mission_id,
        "state": state,
        "authority": _MISSION_AUTHORITY,
        "source_mode": "injected_read_only",
        "runtime_projection_mode": runtime_projection_mode,
        "simulation": False,
        "snapshot": snapshot,
        # Lifecycle rows, leases, heartbeats, acks, and receipts do not prove
        # that an executor process is alive at observation time.
        "proves_executor_liveness": False,
    }


def _validated_public_view(
    value: Any,
    *,
    view_name: str,
    string_fields: tuple[str, ...],
    mapping_fields: tuple[str, ...] = (),
    boolean_fields: tuple[str, ...] = (),
    nullable_string_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Return only fields in one public view after validating their wire types."""
    if not isinstance(value, dict):
        raise TypeError(f"mission snapshot {view_name} must be an object")
    for field in string_fields:
        if field not in value or not isinstance(value[field], str):
            raise TypeError(f"mission snapshot {view_name}.{field} must be a string")
    for field in mapping_fields:
        if field not in value or not isinstance(value[field], dict):
            raise TypeError(f"mission snapshot {view_name}.{field} must be an object")
    for field in boolean_fields:
        if field not in value or not isinstance(value[field], bool):
            raise TypeError(f"mission snapshot {view_name}.{field} must be a boolean")
    for field in nullable_string_fields:
        if field not in value:
            raise TypeError(
                f"mission snapshot {view_name}.{field} must be a string or null"
            )
        candidate = value.get(field)
        if candidate is not None:
            _validated_iso_timestamp(candidate, field=f"{view_name}.{field}")
    public_fields = string_fields + mapping_fields + boolean_fields + nullable_string_fields
    return {field: value[field] for field in public_fields}


def _validated_public_collection(
    projected: dict[str, Any],
    *,
    field: str,
    mission_id: str,
    expected_session_id: str | None = None,
    string_fields: tuple[str, ...],
    mapping_fields: tuple[str, ...] = (),
    boolean_fields: tuple[str, ...] = (),
    nullable_string_fields: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    values = projected.get(field)
    if not isinstance(values, list):
        raise TypeError(f"mission snapshot field {field!r} must be a list")
    result: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        public_view = _validated_public_view(
            value,
            view_name=f"{field}[{index}]",
            string_fields=string_fields,
            mapping_fields=mapping_fields,
            boolean_fields=boolean_fields,
            nullable_string_fields=nullable_string_fields,
        )
        if public_view["mission_id"] != mission_id:
            raise ValueError(f"mission snapshot {field}[{index}] has foreign identity")
        if (
            expected_session_id is not None
            and public_view.get("session_id") != expected_session_id
        ):
            raise ValueError(f"mission snapshot {field}[{index}] has foreign session")
        result.append(public_view)
    return result


def _index_public_views(
    values: list[dict[str, Any]], *, identity_field: str, view_name: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        identity = value[identity_field]
        if not identity or any(char.isspace() for char in identity):
            raise ValueError(f"mission snapshot {view_name} identity is not canonical")
        if identity in result:
            raise ValueError(f"mission snapshot {view_name} identity is duplicated")
        result[identity] = value
    return result


def _has_expected_fields(value: dict[str, Any], **expected: Any) -> bool:
    return all(value.get(field) == item for field, item in expected.items())


def _receipt_matches_projected_contract(receipt: dict[str, Any], attempt: dict[str, Any]) -> bool:
    payload, status = receipt["payload"], receipt["status"]
    common = (
        receipt["receipt_id"] == stable_id("receipt", attempt["attempt_id"], status)
        and _has_expected_fields(
            payload, schema_version=SCHEMA_VERSION,
            mission_id=receipt["mission_id"], attempt_id=attempt["attempt_id"],
        )
    )
    if receipt["receipt_type"] == TERMINAL_RECEIPT_TYPE:
        metadata = payload.get("metadata")
        return (
            common
            and status in {"succeeded", "failed"}
            and isinstance(payload.get("result"), str)
            and isinstance(payload.get("failure_code"), str)
            and isinstance(metadata, dict)
            and _has_expected_fields(
                metadata, schema_version=SCHEMA_VERSION,
                mission_id=receipt["mission_id"], attempt_id=attempt["attempt_id"],
                attempt_key=receipt["idempotency_key"],
            )
        )
    return receipt["receipt_type"] != RECOVERY_RECEIPT_TYPE or (
        common
        and status == "stale_recovered"
        and _has_expected_fields(payload, recovered_claim_id=attempt["claim_id"], reason="expired_lease")
    )


def _validate_snapshot_lineage(
    *,
    tasks: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    leases: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    reconciliation: str,
    observed_at: datetime,
) -> None:
    task_by_id = _index_public_views(tasks, identity_field="task_id", view_name="task")
    attempt_by_id = _index_public_views(attempts, identity_field="attempt_id", view_name="attempt")
    lease_by_claim = _index_public_views(leases, identity_field="claim_id", view_name="lease")
    _index_public_views(receipts, identity_field="receipt_id", view_name="receipt")
    if reconciliation != ReconciliationState.COHERENT.value:
        return

    receipts_by_attempt: dict[str, list[dict[str, Any]]] = {}
    attempts_by_task: dict[str, list[dict[str, Any]]] = {}
    receipts_by_task: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts:
        attempts_by_task.setdefault(attempt["task_id"], []).append(attempt)
    for receipt in receipts:
        receipts_by_attempt.setdefault(receipt["attempt_id"], []).append(receipt)
        receipts_by_task.setdefault(receipt["task_id"], []).append(receipt)
    for attempt in attempts:
        lease = lease_by_claim.get(attempt["claim_id"])
        stale_after = lease["stale_after"] if lease else None
        lease_is_expired = stale_after is not None and _validated_iso_timestamp(
            stale_after, field="lease.stale_after"
        ) <= observed_at
        if (
            attempt["task_id"] not in task_by_id
            or not attempt["assigned_to"]
            or not attempt["idempotency_key"]
            or not _has_expected_fields(
                attempt["metadata"], schema_version=SCHEMA_VERSION,
                mission_id=attempt["mission_id"],
            )
            or lease is None
            or lease["attempt_id"] != attempt["attempt_id"]
            or lease["task_id"] != attempt["task_id"]
            or lease["agent_id"] != attempt["assigned_to"]
            or lease["expired"] != lease_is_expired
        ):
            raise ValueError("coherent mission snapshot has orphaned attempt lineage")
        status = attempt["status"]
        if status == "queued":
            lease_matches_status = (
                lease["status"] == "claimed"
                and not lease["active"]
                and not lease["expired"]
            )
        elif status == "running":
            lease_matches_status = (
                lease["status"] in ACTIVE_CLAIM_STATUSES
                and lease["active"]
                and not lease["expired"]
            )
        else:
            expected_lease_status = "completed" if status == "succeeded" else status
            lease_matches_status = (
                lease["status"] == expected_lease_status and not lease["active"]
            )
        evidence = [
            receipt
            for receipt in receipts_by_attempt.get(attempt["attempt_id"], [])
            if receipt["receipt_type"]
            in {TERMINAL_RECEIPT_TYPE, RECOVERY_RECEIPT_TYPE}
        ]
        if status in {"succeeded", "failed"}:
            evidence_matches_status = (
                len(evidence) == 1
                and evidence[0]["receipt_type"] == TERMINAL_RECEIPT_TYPE
                and evidence[0]["status"] == status
            )
        elif status == "stale_recovered":
            evidence_matches_status = (
                len(evidence) == 1
                and evidence[0]["receipt_type"] == RECOVERY_RECEIPT_TYPE
                and evidence[0]["status"] == status
            )
        else:
            evidence_matches_status = not evidence
        if not lease_matches_status or not evidence_matches_status:
            raise ValueError("coherent mission snapshot attempt evidence conflicts")
    for task in tasks:
        task_attempts = attempts_by_task.get(task["task_id"], [])
        if task["status"] in {"assigned", "running"}:
            expected_attempt_status = "queued" if task["status"] == "assigned" else "running"
            matching = [
                attempt
                for attempt in task_attempts
                if attempt["status"] == expected_attempt_status
                and attempt["assigned_to"] == task["assigned_to"]
                and task["metadata"].get("mission_attempt_id")
                == attempt["attempt_id"]
                and task["metadata"].get("mission_claim_id") == attempt["claim_id"]
            ]
            task_is_coherent = len(matching) == 1 and all(
                attempt in matching or attempt["status"] == "stale_recovered"
                for attempt in task_attempts
            )
        elif task["status"] in {"completed", "failed"}:
            expected_receipt_status = "succeeded" if task["status"] == "completed" else "failed"
            task_is_coherent = (
                sum(
                    receipt["receipt_type"] == TERMINAL_RECEIPT_TYPE
                    and receipt["status"] == expected_receipt_status
                    for receipt in receipts_by_task.get(task["task_id"], [])
                )
                == 1
                and all(
                    attempt["status"]
                    in {expected_receipt_status, "stale_recovered"}
                    for attempt in task_attempts
                )
            )
        else:
            task_is_coherent = task["status"] == "pending" and all(
                attempt["status"] == "stale_recovered" for attempt in task_attempts
            )
        if not task_is_coherent:
            raise ValueError("coherent mission snapshot task evidence conflicts")
    for lease in leases:
        attempt = attempt_by_id.get(lease["attempt_id"])
        if (
            lease["task_id"] not in task_by_id
            or not lease["agent_id"]
            or attempt is None
            or attempt["claim_id"] != lease["claim_id"]
            or attempt["task_id"] != lease["task_id"]
            or attempt["assigned_to"] != lease["agent_id"]
            or not _has_expected_fields(
                lease["metadata"], schema_version=SCHEMA_VERSION,
                mission_id=lease["mission_id"], attempt_id=lease["attempt_id"],
            )
        ):
            raise ValueError("coherent mission snapshot has orphaned lease lineage")
    for receipt in receipts:
        attempt = attempt_by_id.get(receipt["attempt_id"])
        lease = lease_by_claim.get(attempt["claim_id"]) if attempt else None
        if (
            receipt["task_id"] not in task_by_id
            or not receipt["agent_id"]
            or attempt is None
            or lease is None
            or receipt["task_id"] != attempt["task_id"]
            or receipt["agent_id"] != attempt["assigned_to"]
            or receipt["idempotency_key"] != attempt["idempotency_key"]
            or not _receipt_matches_projected_contract(receipt, attempt)
        ):
            raise ValueError("coherent mission snapshot has orphaned receipt lineage")


def _validated_iso_timestamp(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"mission snapshot {field} must be an ISO timestamp")
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"mission snapshot {field} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"mission snapshot {field} must include a timezone")
    return parsed


def _project_injected_snapshot(snapshot: Any, mission_id: str) -> dict[str, Any]:
    projected = jsonable_encoder(snapshot)
    if not isinstance(projected, dict):
        raise TypeError("mission snapshot provider returned a non-object")
    if set(projected) != _MISSION_SNAPSHOT_FIELDS:
        raise ValueError("mission snapshot fields do not match the public contract")
    expected_session_id = f"mission:{mission_id}"
    mission = _validated_public_view(
        projected.get("mission"),
        view_name="mission",
        string_fields=(
            "mission_id", "session_id", "title", "goal", "operator_id", "status",
        ),
        mapping_fields=("metadata",),
        nullable_string_fields=("created_at", "updated_at"),
    )
    if mission["mission_id"] != mission_id:
        raise ValueError("mission snapshot identity does not match the request")
    if mission["session_id"] != expected_session_id:
        raise ValueError("mission snapshot session does not match the request")
    if not _has_expected_fields(mission["metadata"], schema_version=SCHEMA_VERSION, mission_id=mission_id):
        raise ValueError("mission snapshot metadata is not canonical")
    tasks = _validated_public_collection(
        projected,
        field="tasks",
        mission_id=mission_id,
        string_fields=(
            "task_id", "mission_id", "title", "description",
            "status", "priority", "assigned_to", "result",
        ),
        mapping_fields=("metadata",),
        nullable_string_fields=("created_at", "updated_at"),
    )
    if any(task["status"] not in _TASK_STATUSES for task in tasks):
        raise ValueError("mission snapshot task status is not canonical")
    if any(task["priority"] not in _TASK_PRIORITIES for task in tasks):
        raise ValueError("mission snapshot task priority is not canonical")
    if any(
        not _has_expected_fields(
            task["metadata"], schema_version=SCHEMA_VERSION, mission_id=mission_id
        )
        for task in tasks
    ):
        raise ValueError("mission snapshot task metadata is not canonical")
    attempts = _validated_public_collection(
        projected,
        field="attempts",
        mission_id=mission_id,
        expected_session_id=expected_session_id,
        string_fields=(
            "attempt_id", "mission_id", "session_id", "task_id", "claim_id",
            "assigned_to", "assigned_by", "status", "failure_code", "idempotency_key",
        ),
        mapping_fields=("metadata",),
        nullable_string_fields=("started_at", "completed_at"),
    )
    if any(attempt["status"] not in _ATTEMPT_STATUSES for attempt in attempts):
        raise ValueError("mission snapshot attempt status is not canonical")
    leases = _validated_public_collection(
        projected,
        field="leases",
        mission_id=mission_id,
        expected_session_id=expected_session_id,
        string_fields=(
            "claim_id", "mission_id", "session_id", "task_id",
            "agent_id", "attempt_id", "status",
        ),
        mapping_fields=("metadata",),
        boolean_fields=("active", "expired"),
        nullable_string_fields=("heartbeat_at", "stale_after"),
    )
    if any(lease["status"] not in _LEASE_STATUSES for lease in leases):
        raise ValueError("mission snapshot lease status is not canonical")
    receipts = _validated_public_collection(
        projected,
        field="receipts",
        mission_id=mission_id,
        string_fields=(
            "receipt_id", "mission_id", "task_id", "attempt_id",
            "agent_id", "receipt_type", "status", "idempotency_key",
        ),
        mapping_fields=("payload",),
        nullable_string_fields=("created_at",),
    )
    reconciliation = projected.get("reconciliation")
    if not isinstance(reconciliation, str):
        raise TypeError("mission snapshot reconciliation must be a string")
    if reconciliation not in _RECONCILIATION_STATES:
        raise ValueError("mission snapshot reconciliation is not canonical")
    observed_at = projected["observed_at"]
    observed_time = _validated_iso_timestamp(observed_at, field="observed_at")
    _validate_snapshot_lineage(
        tasks=tasks,
        attempts=attempts,
        leases=leases,
        receipts=receipts,
        reconciliation=reconciliation,
        observed_at=observed_time,
    )
    if projected.get("authority") != _MISSION_AUTHORITY:
        raise ValueError("mission snapshot authority is not canonical")
    if projected.get("proves_executor_liveness") is not False:
        raise ValueError("mission snapshot cannot claim executor liveness")
    return {
        "mission": mission,
        "tasks": tasks,
        "attempts": attempts,
        "leases": leases,
        "receipts": receipts,
        "reconciliation": reconciliation,
        "observed_at": observed_at,
        "authority": projected["authority"],
        "proves_executor_liveness": False,
    }


@router.get("/summary")
def control_surface_summary(
    memory_depth: str = Query(
        "snapshot",
        pattern="^(snapshot|deep)$",
        description="MemoryKernel projection depth. Use deep only for explicit readiness verification.",
    ),
) -> dict[str, Any]:
    """Lightweight coherence summary with counts by state."""
    try:
        build_control_surface_rows, build_control_surface_summary, _ = _get_control_surface_funcs()
        rows = build_control_surface_rows(memory_depth=memory_depth)
        summary = build_control_surface_summary(rows)
        summary["memory_depth"] = memory_depth
        return _build_envelope(summary)
    except Exception as e:
        logger.exception("control-surface/summary failed")
        return _build_envelope(None, [{"source": "summary", "error": str(e)}])


@router.get("/stream")
async def control_surface_stream():
    """SSE stream pushing updated rows when the projection changes."""
    async def event_generator():  # noqa: ANN202
        last_hash: int | None = None
        while True:
            try:
                row_dicts = _build_rows(memory_depth="snapshot")
                payload = json.dumps(row_dicts, sort_keys=True)
                current_hash = hash(payload)
                if current_hash != last_hash:
                    yield f"data: {payload}\n\n"
                    last_hash = current_hash
            except Exception:
                logger.exception("control-surface/stream iteration failed")
            await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/rows")
def control_surface_rows(
    memory_depth: str = Query(
        "snapshot",
        pattern="^(snapshot|deep)$",
        description="MemoryKernel projection depth. Use deep only for explicit readiness verification.",
    ),
) -> dict[str, Any]:
    """All control surface rows — declared intent reconciled with observed reality."""
    try:
        row_dicts, source_errors = _build_rows_with_errors(memory_depth=memory_depth)
        return _build_envelope(row_dicts, source_errors)
    except Exception as e:
        logger.exception("control-surface/rows failed")
        return _build_envelope(None, [{"source": "rows", "error": str(e)}])


@router.get("/ds-goal/cards")
def control_surface_ds_goal_cards(
    mission_id: str = Query("", description="Optional ds-goal mission id filter."),
) -> dict[str, Any]:
    """Project ds-goal mission ledgers into existing BoardStore Card JSON."""
    try:
        load_ds_goal_cards = _get_ds_goal_card_loader()
        cards = [
            card.model_dump(mode="json")
            for card in load_ds_goal_cards(_DS_GOAL_STATE_ROOT, mission_id=mission_id)
        ]
        return _build_envelope(
            {
                "state_root": str(_DS_GOAL_STATE_ROOT),
                "mission_id": mission_id or None,
                "card_count": len(cards),
                "cards": cards,
            }
        )
    except Exception as e:
        logger.exception("control-surface/ds-goal/cards failed")
        return _build_envelope(
            {
                "state_root": str(_DS_GOAL_STATE_ROOT),
                "mission_id": mission_id or None,
                "card_count": 0,
                "cards": [],
            },
            [{"source": "ds_goal_cards", "error": str(e)}],
        )


@router.get("/agentops/cards")
def control_surface_agentops_cards(
    packet_id: str = Query("", description="Optional AgentOps packet id filter."),
    limit: int = Query(0, ge=0, le=200, description="Optional maximum card count."),
) -> dict[str, Any]:
    """Project AgentOps work packets into existing BoardStore Card JSON."""
    try:
        load_agentops_cards = _get_agentops_card_loader()
        cards = [
            card.model_dump(mode="json")
            for card in load_agentops_cards(
                _AGENTOPS_WORK_PACKET_ROOT,
                packet_id=packet_id,
                limit=limit,
            )
        ]
        return _build_envelope(
            {
                "work_packet_root": str(_AGENTOPS_WORK_PACKET_ROOT),
                "packet_id": packet_id or None,
                "card_count": len(cards),
                "cards": cards,
            }
        )
    except Exception as e:
        logger.exception("control-surface/agentops/cards failed")
        return _build_envelope(
            {
                "work_packet_root": str(_AGENTOPS_WORK_PACKET_ROOT),
                "packet_id": packet_id or None,
                "card_count": 0,
                "cards": [],
            },
            [{"source": "agentops_cards", "error": str(e)}],
        )


@router.get("/a2a/cards")
def control_surface_a2a_cards(
    target: str = Query("", description="Optional A2A target filter."),
    limit: int = Query(0, ge=0, le=200, description="Optional maximum card count."),
) -> dict[str, Any]:
    """Project A2A send/bridge receipts into existing BoardStore Card JSON."""
    try:
        load_a2a_send_cards = _get_a2a_send_card_loader()
        cards = [
            card.model_dump(mode="json")
            for card in load_a2a_send_cards(
                _A2A_SEND_RECEIPT_ROOT,
                bridge_receipt_root=_A2A_INBOX_BRIDGE_RECEIPT_ROOT,
                domain_reply_receipt_root=_A2A_DOMAIN_REPLY_RECEIPT_ROOT,
                reply_receipt_root=_A2A_REPLY_RECEIPT_ROOT,
                target=target,
                limit=limit,
            )
        ]
        return _build_envelope(
            {
                "receipt_root": str(_A2A_SEND_RECEIPT_ROOT),
                "bridge_receipt_root": str(_A2A_INBOX_BRIDGE_RECEIPT_ROOT),
                "domain_reply_receipt_root": str(_A2A_DOMAIN_REPLY_RECEIPT_ROOT),
                "reply_receipt_root": str(_A2A_REPLY_RECEIPT_ROOT),
                "target": target or None,
                "card_count": len(cards),
                "cards": cards,
            }
        )
    except Exception as e:
        logger.exception("control-surface/a2a/cards failed")
        return _build_envelope(
            {
                "receipt_root": str(_A2A_SEND_RECEIPT_ROOT),
                "bridge_receipt_root": str(_A2A_INBOX_BRIDGE_RECEIPT_ROOT),
                "domain_reply_receipt_root": str(_A2A_DOMAIN_REPLY_RECEIPT_ROOT),
                "reply_receipt_root": str(_A2A_REPLY_RECEIPT_ROOT),
                "target": target or None,
                "card_count": 0,
                "cards": [],
            },
            [{"source": "a2a_cards", "error": str(e)}],
        )


@router.get("/semantic-receipts/cards")
def control_surface_semantic_receipt_cards(
    model: str = Query("", description="Optional model filter."),
    verdict: str = Query("", description="Optional verdict filter."),
    limit: int = Query(0, ge=0, le=200, description="Optional maximum card count."),
) -> dict[str, Any]:
    """Project SemanticReceipt artifacts into existing BoardStore Card JSON."""
    try:
        load_semantic_receipt_cards = _get_semantic_receipt_card_loader()
        cards = [
            card.model_dump(mode="json")
            for card in load_semantic_receipt_cards(
                _SEMANTIC_RECEIPT_ROOT,
                model=model,
                verdict=verdict,
                limit=limit,
            )
        ]
        return _build_envelope(
            {
                "receipt_root": str(_SEMANTIC_RECEIPT_ROOT),
                "model": model or None,
                "verdict": verdict or None,
                "card_count": len(cards),
                "cards": cards,
            }
        )
    except Exception as e:
        logger.exception("control-surface/semantic-receipts/cards failed")
        return _build_envelope(
            {
                "receipt_root": str(_SEMANTIC_RECEIPT_ROOT),
                "model": model or None,
                "verdict": verdict or None,
                "card_count": 0,
                "cards": [],
            },
            [{"source": "semantic_receipt_cards", "error": str(e)}],
        )


@router.get("/missions/{mission_id}/snapshot")
async def control_surface_mission_snapshot(
    mission_id: str,
    request: Request,
) -> dict[str, Any]:
    """Project one canonical MissionSnapshot through an injected reader only.

    A request never constructs MissionControl, TaskBoard, RuntimeStateStore,
    an MCP client, or a background worker. The embedding application must
    explicitly supply its already-governed read-only provider.
    """
    mission_id = mission_id.strip()
    if _MISSION_IDENTIFIER.fullmatch(mission_id) is None:
        raise HTTPException(
            status_code=422,
            detail="mission_id must be a bounded identifier",
        )

    provider = getattr(request.app.state, "mission_snapshot_provider", None)
    if provider is None:
        return _build_envelope(
            _mission_snapshot_projection(mission_id, state="uninitialized"),
            [
                {
                    "source": "mission_snapshot_provider",
                    "error": "read-only provider is not injected",
                }
            ],
        )

    reader = getattr(provider, "get_snapshot", None)
    if reader is None and callable(provider):
        reader = provider
    if not callable(reader):
        return _build_envelope(
            _mission_snapshot_projection(mission_id, state="unknown"),
            [
                {
                    "source": "mission_snapshot_provider",
                    "error": "injected provider has no read-only get_snapshot callable",
                }
            ],
        )

    try:
        candidate = (
            reader(mission_id)
            if inspect.iscoroutinefunction(reader)
            else await run_in_threadpool(reader, mission_id)
        )
        snapshot = await candidate if inspect.isawaitable(candidate) else candidate
        if snapshot is None:
            return _build_envelope(
                _mission_snapshot_projection(mission_id, state="unknown"),
                [
                    {
                        "source": "mission_snapshot",
                        "error": "canonical state was not observed for this mission",
                    }
                ],
            )
        projected = _project_injected_snapshot(snapshot, mission_id)
        provider_mode = getattr(provider, "runtime_projection_mode", None)
        runtime_projection_mode = (
            provider_mode
            if provider_mode in {"immutable_copy", "owner_supplied_read_only"}
            else "unavailable"
        )
        return _build_envelope(
            _mission_snapshot_projection(
                mission_id,
                state="observed",
                snapshot=projected,
                runtime_projection_mode=runtime_projection_mode,
            )
        )
    except Exception as exc:
        # The identifier and provider exception are deliberately excluded from
        # logs: both cross an injection boundary and may contain forged lines.
        logger.warning("mission snapshot provider failed (kind=read_failed)")
        error_type = type(exc).__name__
        if _SAFE_ERROR_TYPE.fullmatch(error_type) is None:
            error_type = "ProviderError"
        return _build_envelope(
            _mission_snapshot_projection(mission_id, state="unknown"),
            [
                {
                    "source": "mission_snapshot_provider",
                    "error": f"read failed ({error_type})",
                }
            ],
        )


@router.post("/rows/{row_id:path}/handoff-prompt")
def control_surface_handoff_prompt(
    row_id: str,
    memory_depth: str = Query(
        "snapshot",
        pattern="^(snapshot|deep)$",
        description="MemoryKernel projection depth for locating the row.",
    ),
) -> dict[str, Any]:
    """Generate a scoped agent handoff prompt for a control surface row."""
    try:
        _, _, generate_handoff_prompt = _get_control_surface_funcs()
        row = _find_row_object(row_id, memory_depth=memory_depth)
        if row is None:
            raise HTTPException(status_code=404, detail=f"row '{row_id}' not found")
        prompt = generate_handoff_prompt(row)
        return _build_envelope(prompt.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("control-surface/handoff-prompt failed")
        return _build_envelope(None, [{"source": f"handoff/{row_id}", "error": str(e)}])


@router.get("/rows/{row_id:path}")
def control_surface_row(
    row_id: str,
    memory_depth: str = Query(
        "snapshot",
        pattern="^(snapshot|deep)$",
        description="MemoryKernel projection depth. Use deep only for explicit readiness verification.",
    ),
) -> dict[str, Any]:
    """Single control surface row by ID."""
    try:
        row_dicts, source_errors = _build_rows_with_errors(memory_depth=memory_depth)
        for row in row_dicts:
            if row["id"] == row_id:
                return _build_envelope(row, source_errors)
        raise HTTPException(status_code=404, detail=f"row '{row_id}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("control-surface/rows/<id> failed")
        return _build_envelope(None, [{"source": f"row/{row_id}", "error": str(e)}])
