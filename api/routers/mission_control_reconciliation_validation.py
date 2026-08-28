"""Validate publicly witnessed Mission Control reconciliation states."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from dharma_swarm.mission_control_contract import (
    ACTIVE_CLAIM_STATUSES,
    OPEN_CLAIM_STATUSES,
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION,
    TERMINAL_RECEIPT_TYPE,
    ReconciliationState,
    stable_id,
)


def _has_expected_fields(value: dict[str, Any], **expected: Any) -> bool:
    return all(value.get(field) == item for field, item in expected.items())


def is_canonical_identifier(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not any(char.isspace() for char in value)
    )


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


def receipt_matches_contract(
    receipt: dict[str, Any],
    attempt: dict[str, Any],
) -> bool:
    """Check lifecycle evidence fields retained in the public projection."""
    payload, status = receipt["payload"], receipt["status"]
    common = receipt["receipt_id"] == stable_id(
        "receipt", attempt["attempt_id"], status
    ) and _has_expected_fields(
        payload,
        schema_version=SCHEMA_VERSION,
        mission_id=receipt["mission_id"],
        attempt_id=attempt["attempt_id"],
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
                metadata,
                schema_version=SCHEMA_VERSION,
                mission_id=receipt["mission_id"],
                attempt_id=attempt["attempt_id"],
                attempt_key=receipt["idempotency_key"],
            )
        )
    return receipt["receipt_type"] != RECOVERY_RECEIPT_TYPE or (
        common
        and status == "stale_recovered"
        and _has_expected_fields(
            payload,
            recovered_claim_id=attempt["claim_id"],
            reason="expired_lease",
        )
    )


def terminal_receipt_matches_projection(
    receipt: dict[str, Any],
    attempt: dict[str, Any],
    task: dict[str, Any],
) -> bool:
    """Bind terminal payload values to their projected task and attempt."""
    return (
        receipt["receipt_type"] == TERMINAL_RECEIPT_TYPE
        and receipt["payload"].get("result") == task["result"]
        and receipt["payload"].get("failure_code") == attempt["failure_code"]
    )


def lease_deadline(
    lease: dict[str, Any], *, observed_at: datetime
) -> tuple[datetime | None, bool]:
    """Return a public lease deadline and whether it has elapsed."""
    value = lease["stale_after"]
    deadline = (
        _validated_iso_timestamp(value, field="lease.stale_after")
        if value is not None
        else None
    )
    return deadline, deadline is not None and deadline <= observed_at


def _lease_is_open_and_current(lease: dict[str, Any], *, observed_at: datetime) -> bool:
    _, actually_expired = lease_deadline(lease, observed_at=observed_at)
    return (
        lease["status"] in OPEN_CLAIM_STATUSES
        and not lease["expired"]
        and not actually_expired
    )


def _lifecycle_receipt_groups(
    receipts: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    terminals: dict[str, list[dict[str, Any]]] = {}
    recoveries: dict[str, list[dict[str, Any]]] = {}
    for receipt in receipts:
        if receipt["receipt_type"] == TERMINAL_RECEIPT_TYPE:
            terminals.setdefault(receipt["attempt_id"], []).append(receipt)
        elif receipt["receipt_type"] == RECOVERY_RECEIPT_TYPE:
            recoveries.setdefault(receipt["attempt_id"], []).append(receipt)
    return terminals, recoveries


def _has_visible_foreign_runtime_record(
    *,
    tasks: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    leases: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
) -> bool:
    task_by_id = {task["task_id"]: task for task in tasks}
    attempt_by_id = {attempt["attempt_id"]: attempt for attempt in attempts}
    lease_by_claim = {lease["claim_id"]: lease for lease in leases}
    leases_by_attempt: dict[str, list[dict[str, Any]]] = {}
    for lease in leases:
        leases_by_attempt.setdefault(lease["attempt_id"], []).append(lease)

    for attempt in attempts:
        lease = lease_by_claim.get(attempt["claim_id"])
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
            or (lease is None and attempt["status"] in {"queued", "running"})
            or (
                lease is not None
                and (
                    lease["attempt_id"] != attempt["attempt_id"]
                    or lease["task_id"] != attempt["task_id"]
                    or lease["agent_id"] != attempt["assigned_to"]
                )
            )
        ):
            return True

    for lease in leases:
        attempt = attempt_by_id.get(lease["attempt_id"])
        if (
            lease["task_id"] not in task_by_id
            or not lease["agent_id"]
            or not is_canonical_identifier(lease["attempt_id"])
            or not _has_expected_fields(
                lease["metadata"],
                schema_version=SCHEMA_VERSION,
                mission_id=lease["mission_id"],
                attempt_id=lease["attempt_id"],
            )
            or (
                attempt is not None
                and not _has_expected_fields(
                    lease["metadata"], attempt_key=attempt["idempotency_key"]
                )
            )
            or (attempt is None and lease["status"] not in OPEN_CLAIM_STATUSES)
            or (
                attempt is not None
                and (
                    attempt["claim_id"] != lease["claim_id"]
                    or attempt["task_id"] != lease["task_id"]
                    or attempt["assigned_to"] != lease["agent_id"]
                )
            )
        ):
            return True

    for receipt in receipts:
        attempt = attempt_by_id.get(receipt["attempt_id"])
        if attempt is None:
            if receipt["receipt_type"] in {
                TERMINAL_RECEIPT_TYPE,
                RECOVERY_RECEIPT_TYPE,
            } and leases_by_attempt.get(receipt["attempt_id"]):
                continue
            return True
        if (
            receipt["task_id"] != attempt["task_id"]
            or receipt["agent_id"] != attempt["assigned_to"]
            or receipt["idempotency_key"] != attempt["idempotency_key"]
        ):
            return True
    return False


def _has_structural_terminal_conflict(
    *,
    tasks: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    leases: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
) -> bool:
    task_by_id = {task["task_id"]: task for task in tasks}
    attempt_by_id = {attempt["attempt_id"]: attempt for attempt in attempts}
    lease_by_claim = {lease["claim_id"]: lease for lease in leases}
    terminals, recoveries = _lifecycle_receipt_groups(receipts)
    if any(len(group) != 1 for group in terminals.values()) or any(
        len(group) != 1 for group in recoveries.values()
    ):
        return True
    if set(terminals) & set(recoveries):
        return True
    for receipt in receipts:
        if receipt["receipt_type"] not in {
            TERMINAL_RECEIPT_TYPE,
            RECOVERY_RECEIPT_TYPE,
        }:
            continue
        attempt = attempt_by_id.get(receipt["attempt_id"])
        task = task_by_id.get(receipt["task_id"])
        lease = lease_by_claim.get(attempt["claim_id"]) if attempt else None
        if (
            attempt is None
            or task is None
            or lease is None
            or not receipt_matches_contract(receipt, attempt)
        ):
            return True
    return False


def _public_noncoherent_witness(
    *,
    tasks: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    leases: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    observed_at: datetime,
) -> ReconciliationState | None:
    """Classify visible drift in canonical priority; hidden identity stays trusted."""
    task_by_id = {task["task_id"]: task for task in tasks}
    attempt_by_id = {attempt["attempt_id"]: attempt for attempt in attempts}
    lease_by_claim = {lease["claim_id"]: lease for lease in leases}
    terminals, recoveries = _lifecycle_receipt_groups(receipts)
    receipts_by_task: dict[str, list[dict[str, Any]]] = {}
    attempts_by_task: dict[str, list[dict[str, Any]]] = {}
    for receipt in receipts:
        receipts_by_task.setdefault(receipt["task_id"], []).append(receipt)
    for attempt in attempts:
        attempts_by_task.setdefault(attempt["task_id"], []).append(attempt)

    if _has_visible_foreign_runtime_record(
        tasks=tasks,
        attempts=attempts,
        leases=leases,
        receipts=receipts,
    ):
        return ReconciliationState.FOREIGN_RUNTIME_RECORD
    if _has_structural_terminal_conflict(
        tasks=tasks,
        attempts=attempts,
        leases=leases,
        receipts=receipts,
    ):
        return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE

    open_claim_counts = Counter(
        lease["task_id"]
        for lease in leases
        if lease["task_id"] in task_by_id
        and _lease_is_open_and_current(lease, observed_at=observed_at)
    )
    if any(count > 1 for count in open_claim_counts.values()):
        return ReconciliationState.CONFLICTING_ACTIVE_CLAIMS

    for lease in leases:
        if lease["status"] not in OPEN_CLAIM_STATUSES:
            continue
        attempt = attempt_by_id.get(lease["attempt_id"])
        task = task_by_id.get(lease["task_id"])
        attempt_is_terminal = attempt is not None and attempt["status"] in {
            "succeeded",
            "failed",
            "stale_recovered",
        }
        task_is_terminal = task is not None and task["status"] in {
            "completed",
            "failed",
        }
        if not attempt_is_terminal and not task_is_terminal:
            continue
        has_lifecycle_evidence = bool(
            terminals.get(lease["attempt_id"]) or recoveries.get(lease["attempt_id"])
        )
        return (
            ReconciliationState.NEEDS_TASK_PROJECTION
            if has_lifecycle_evidence
            else ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        )

    attempt_claim_ids = {attempt["claim_id"] for attempt in attempts}
    if any(
        _lease_is_open_and_current(lease, observed_at=observed_at)
        and lease["claim_id"] not in attempt_claim_ids
        for lease in leases
    ):
        return ReconciliationState.ACTIVE_CLAIM_WITHOUT_RUN

    for attempt in attempts:
        attempt_terminals = terminals.get(attempt["attempt_id"], [])
        attempt_recoveries = recoveries.get(attempt["attempt_id"], [])
        if (attempt["status"] in {"succeeded", "failed"} and not attempt_terminals) or (
            attempt["status"] == "stale_recovered" and not attempt_recoveries
        ):
            return ReconciliationState.MISSING_TERMINAL_RECEIPT

        task = task_by_id[attempt["task_id"]]
        lease = lease_by_claim.get(attempt["claim_id"])
        if attempt_terminals:
            receipt = attempt_terminals[0]
            expected_attempt = receipt["status"]
            expected_task = (
                "completed" if receipt["status"] == "succeeded" else "failed"
            )
            expected_lease = expected_task
            if (
                attempt["status"] in {"succeeded", "failed"}
                and attempt["status"] != expected_attempt
            ):
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if lease is None:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if lease["status"] in OPEN_CLAIM_STATUSES:
                return ReconciliationState.NEEDS_TASK_PROJECTION
            if lease["status"] != expected_lease:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if (
                attempt["status"] not in {"succeeded", "failed"}
                or task["status"] != expected_task
            ):
                return ReconciliationState.NEEDS_TASK_PROJECTION
            if not terminal_receipt_matches_projection(receipt, attempt, task):
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        elif attempt_recoveries:
            if lease is None:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if lease["status"] in OPEN_CLAIM_STATUSES:
                return ReconciliationState.NEEDS_TASK_PROJECTION
            if lease["status"] != "stale_recovered":
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if attempt["status"] != "stale_recovered":
                return ReconciliationState.NEEDS_TASK_PROJECTION
            if task["status"] in {"completed", "failed"} and not any(
                receipt["receipt_type"] == TERMINAL_RECEIPT_TYPE
                for receipt in receipts_by_task.get(task["task_id"], [])
            ):
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
            if (
                task["status"] in {"assigned", "running"}
                and task["metadata"].get("mission_attempt_id") == attempt["attempt_id"]
            ):
                return ReconciliationState.NEEDS_TASK_PROJECTION
        elif attempt["status"] == "running" and task["status"] != "running":
            return ReconciliationState.NEEDS_TASK_PROJECTION
        elif attempt["status"] == "queued" and (
            task["status"] != "assigned"
            or task["assigned_to"] != attempt["assigned_to"]
        ):
            return ReconciliationState.NEEDS_TASK_PROJECTION

        if attempt["status"] == "queued" and lease is not None:
            if lease["status"] in OPEN_CLAIM_STATUSES:
                if lease["status"] != "claimed":
                    return ReconciliationState.NEEDS_TASK_PROJECTION
            else:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        if attempt["status"] == "running" and lease is not None:
            if lease["status"] in OPEN_CLAIM_STATUSES:
                _, actually_expired = lease_deadline(lease, observed_at=observed_at)
                if lease["status"] not in ACTIVE_CLAIM_STATUSES or (
                    not lease["active"] and not actually_expired
                ):
                    return ReconciliationState.NEEDS_TASK_PROJECTION
            else:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE

    for task in tasks:
        task_attempts = attempts_by_task.get(task["task_id"], [])
        if task["status"] in {"assigned", "running"}:
            expected_status = "queued" if task["status"] == "assigned" else "running"
            matching = [
                attempt
                for attempt in task_attempts
                if attempt["status"] == expected_status
                and attempt["assigned_to"] == task["assigned_to"]
                and task["metadata"].get("mission_attempt_id") == attempt["attempt_id"]
                and task["metadata"].get("mission_claim_id") == attempt["claim_id"]
            ]
            if len(matching) != 1:
                return ReconciliationState.NEEDS_TASK_PROJECTION
        elif task["status"] in {"completed", "failed"}:
            expected_receipt = (
                "succeeded" if task["status"] == "completed" else "failed"
            )
            matching = [
                receipt
                for receipt in receipts_by_task.get(task["task_id"], [])
                if receipt["receipt_type"] == TERMINAL_RECEIPT_TYPE
                and receipt["status"] == expected_receipt
            ]
            if len(matching) != 1:
                return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE
        elif task["status"] != "pending":
            return ReconciliationState.CONFLICTING_TERMINAL_EVIDENCE

    if any(
        lease["status"] in OPEN_CLAIM_STATUSES
        and lease["expired"]
        and not lease["active"]
        and lease_deadline(lease, observed_at=observed_at)[1]
        for lease in leases
    ):
        return ReconciliationState.EXPIRED_LEASE
    return None


def validate_public_noncoherent_reconciliation(
    *,
    tasks: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    leases: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    reconciliation: str,
    observed_at: datetime,
) -> None:
    """Require the reported label to match its first visible canonical witness."""
    state = ReconciliationState(reconciliation)
    if state is ReconciliationState.EVIDENCE_SCAN_SATURATED:
        raise ValueError(
            "mission snapshot saturation is not provable from the public v1 shape"
        )
    witnessed = _public_noncoherent_witness(
        tasks=tasks,
        attempts=attempts,
        leases=leases,
        receipts=receipts,
        observed_at=observed_at,
    )
    if witnessed is not state:
        raise ValueError(
            "mission snapshot reconciliation lacks canonical public evidence"
        )


__all__ = [
    "is_canonical_identifier",
    "lease_deadline",
    "receipt_matches_contract",
    "terminal_receipt_matches_projection",
    "validate_public_noncoherent_reconciliation",
]
