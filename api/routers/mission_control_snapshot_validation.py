"""Prove ``PubliclyWitnessed[State]`` while trusting hidden owner identity."""

from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

from fastapi.encoders import jsonable_encoder

from api.routers.mission_control_reconciliation_validation import (
    is_canonical_identifier,
    lease_deadline,
    receipt_matches_contract,
    terminal_receipt_matches_projection,
    validate_public_noncoherent_reconciliation,
)
from dharma_swarm.mission_control_contract import (
    ACTIVE_CLAIM_STATUSES,
    OPEN_CLAIM_STATUSES,
    OWNER_TERMINAL_ATTEMPT_STATUSES,
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION,
    TERMINAL_RECEIPT_TYPE,
    ReconciliationState,
    public_attempt_status,
)
from dharma_swarm.models import TaskPriority, TaskStatus

MISSION_AUTHORITY = "TaskBoard+RuntimeStateStore"
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


def _validate_finite_numbers(value: Any, *, field: str) -> None:
    """Reject JSON values that strict response serialization cannot represent."""
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"mission snapshot {field} contains a non-finite number")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_finite_numbers(key, field=field)
            _validate_finite_numbers(item, field=field)
        return
    if isinstance(value, list):
        for item in value:
            _validate_finite_numbers(item, field=field)


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


def _validated_public_view(
    value: Any,
    *,
    view_name: str,
    string_fields: tuple[str, ...],
    mapping_fields: tuple[str, ...] = (),
    boolean_fields: tuple[str, ...] = (),
    nullable_string_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"mission snapshot {view_name} must be an object")
    for field in string_fields:
        if not isinstance(value.get(field), str):
            raise TypeError(f"mission snapshot {view_name}.{field} must be a string")
    for field in mapping_fields:
        if not isinstance(value.get(field), dict):
            raise TypeError(f"mission snapshot {view_name}.{field} must be an object")
        _validate_finite_numbers(value[field], field=f"{view_name}.{field}")
    for field in boolean_fields:
        if not isinstance(value.get(field), bool):
            raise TypeError(f"mission snapshot {view_name}.{field} must be a boolean")
    for field in nullable_string_fields:
        if field not in value:
            raise TypeError(
                f"mission snapshot {view_name}.{field} must be a string or null"
            )
        candidate = value.get(field)
        if candidate is not None:
            _validated_iso_timestamp(candidate, field=f"{view_name}.{field}")
    public_fields = (
        string_fields + mapping_fields + boolean_fields + nullable_string_fields
    )
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


def _receipt_groups(
    receipts: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for receipt in receipts:
        grouped.setdefault(receipt["attempt_id"], []).append(receipt)
    return grouped


def _validate_coherent_lineage(
    *,
    tasks: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    leases: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    observed_at: datetime,
) -> None:
    task_by_id = _index_public_views(tasks, identity_field="task_id", view_name="task")
    attempt_by_id = _index_public_views(
        attempts, identity_field="attempt_id", view_name="attempt"
    )
    lease_by_claim = _index_public_views(
        leases, identity_field="claim_id", view_name="lease"
    )
    _index_public_views(receipts, identity_field="receipt_id", view_name="receipt")
    receipts_by_attempt = _receipt_groups(receipts)
    attempts_by_task: dict[str, list[dict[str, Any]]] = {}
    receipts_by_task: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts:
        attempts_by_task.setdefault(attempt["task_id"], []).append(attempt)
    for receipt in receipts:
        receipts_by_task.setdefault(receipt["task_id"], []).append(receipt)
    for attempt in attempts:
        lease = lease_by_claim.get(attempt["claim_id"])
        deadline, lease_is_expired = (
            lease_deadline(lease, observed_at=observed_at)
            if lease is not None
            else (None, False)
        )
        if (
            attempt["task_id"] not in task_by_id
            or not attempt["assigned_to"]
            or not is_canonical_identifier(attempt["idempotency_key"])
            or not _has_expected_fields(
                attempt["metadata"],
                schema_version=SCHEMA_VERSION,
                mission_id=attempt["mission_id"],
                attempt_id=attempt["attempt_id"],
                attempt_key=attempt["idempotency_key"],
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
            heartbeat = (
                _validated_iso_timestamp(
                    lease["heartbeat_at"], field="lease.heartbeat_at"
                )
                if lease["heartbeat_at"] is not None
                else None
            )
            lease_matches_status = (
                lease["status"] in ACTIVE_CLAIM_STATUSES
                and lease["active"]
                and not lease["expired"]
                and heartbeat is not None
                and deadline is not None
                and heartbeat <= observed_at < deadline
            )
        else:
            expected_lease_status = "completed" if status == "succeeded" else status
            lease_matches_status = (
                lease["status"] == expected_lease_status
                and not lease["active"]
                and (
                    status != "stale_recovered"
                    or (lease["expired"] and lease_is_expired)
                )
            )
        evidence = [
            receipt
            for receipt in receipts_by_attempt.get(attempt["attempt_id"], [])
            if receipt["receipt_type"] in {TERMINAL_RECEIPT_TYPE, RECOVERY_RECEIPT_TYPE}
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
            expected_attempt_status = (
                "queued" if task["status"] == "assigned" else "running"
            )
            matching = [
                attempt
                for attempt in task_attempts
                if attempt["status"] == expected_attempt_status
                and attempt["assigned_to"] == task["assigned_to"]
                and task["metadata"].get("mission_attempt_id") == attempt["attempt_id"]
                and task["metadata"].get("mission_claim_id") == attempt["claim_id"]
            ]
            task_is_coherent = len(matching) == 1 and all(
                attempt in matching or attempt["status"] == "stale_recovered"
                for attempt in task_attempts
            )
        elif task["status"] in {"completed", "failed"}:
            expected_receipt_status = (
                "succeeded" if task["status"] == "completed" else "failed"
            )
            task_is_coherent = sum(
                receipt["receipt_type"] == TERMINAL_RECEIPT_TYPE
                and receipt["status"] == expected_receipt_status
                for receipt in receipts_by_task.get(task["task_id"], [])
            ) == 1 and all(
                attempt["status"] in {expected_receipt_status, "stale_recovered"}
                for attempt in task_attempts
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
                lease["metadata"],
                schema_version=SCHEMA_VERSION,
                mission_id=lease["mission_id"],
                attempt_id=lease["attempt_id"],
                attempt_key=attempt["idempotency_key"],
            )
        ):
            raise ValueError("coherent mission snapshot has orphaned lease lineage")
    for receipt in receipts:
        attempt = attempt_by_id.get(receipt["attempt_id"])
        lease = lease_by_claim.get(attempt["claim_id"]) if attempt else None
        task = task_by_id.get(receipt["task_id"])
        if (
            receipt["task_id"] not in task_by_id
            or not receipt["agent_id"]
            or attempt is None
            or lease is None
            or task is None
            or receipt["task_id"] != attempt["task_id"]
            or receipt["agent_id"] != attempt["assigned_to"]
            or receipt["idempotency_key"] != attempt["idempotency_key"]
            or not receipt_matches_contract(receipt, attempt)
            or (
                receipt["receipt_type"] == TERMINAL_RECEIPT_TYPE
                and not terminal_receipt_matches_projection(receipt, attempt, task)
            )
        ):
            raise ValueError("coherent mission snapshot has orphaned receipt lineage")


def _validate_snapshot_lineage(
    *,
    tasks: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    leases: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    reconciliation: str,
    observed_at: datetime,
) -> None:
    _index_public_views(tasks, identity_field="task_id", view_name="task")
    _index_public_views(attempts, identity_field="attempt_id", view_name="attempt")
    _index_public_views(leases, identity_field="claim_id", view_name="lease")
    _index_public_views(receipts, identity_field="receipt_id", view_name="receipt")
    if any(
        attempt["status"] == "stale_recovered"
        and attempt["failure_code"] != "stale_lease_recovered"
        for attempt in attempts
    ):
        raise ValueError(
            "mission snapshot stale recovery failure code is not canonical"
        )
    for lease in leases:
        if lease["active"] and lease["status"] not in ACTIVE_CLAIM_STATUSES:
            raise ValueError("mission snapshot lease activity projection conflicts")
        _, actually_expired = lease_deadline(lease, observed_at=observed_at)
        if lease["expired"] != actually_expired or (
            actually_expired and lease["active"]
        ):
            raise ValueError("mission snapshot lease timing projection conflicts")
    if reconciliation == ReconciliationState.COHERENT.value:
        _validate_coherent_lineage(
            tasks=tasks,
            attempts=attempts,
            leases=leases,
            receipts=receipts,
            observed_at=observed_at,
        )
        return
    validate_public_noncoherent_reconciliation(
        tasks=tasks,
        attempts=attempts,
        leases=leases,
        receipts=receipts,
        reconciliation=reconciliation,
        observed_at=observed_at,
    )


def project_injected_mission_snapshot(snapshot: Any, mission_id: str) -> dict[str, Any]:
    """Validate an injected provider result against the public snapshot contract."""
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
            "mission_id",
            "session_id",
            "title",
            "goal",
            "operator_id",
            "status",
        ),
        mapping_fields=("metadata",),
        nullable_string_fields=("created_at", "updated_at"),
    )
    if mission["mission_id"] != mission_id:
        raise ValueError("mission snapshot identity does not match the request")
    if mission["session_id"] != expected_session_id:
        raise ValueError("mission snapshot session does not match the request")
    if not _has_expected_fields(
        mission["metadata"], schema_version=SCHEMA_VERSION, mission_id=mission_id
    ):
        raise ValueError("mission snapshot metadata is not canonical")
    tasks = _validated_public_collection(
        projected,
        field="tasks",
        mission_id=mission_id,
        string_fields=(
            "task_id",
            "mission_id",
            "title",
            "description",
            "status",
            "priority",
            "assigned_to",
            "result",
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
            "attempt_id",
            "mission_id",
            "session_id",
            "task_id",
            "claim_id",
            "assigned_to",
            "assigned_by",
            "status",
            "failure_code",
            "idempotency_key",
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
            "claim_id",
            "mission_id",
            "session_id",
            "task_id",
            "agent_id",
            "attempt_id",
            "status",
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
            "receipt_id",
            "mission_id",
            "task_id",
            "attempt_id",
            "agent_id",
            "receipt_type",
            "status",
            "idempotency_key",
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
    if projected.get("authority") != MISSION_AUTHORITY:
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


__all__ = ["MISSION_AUTHORITY", "project_injected_mission_snapshot"]
