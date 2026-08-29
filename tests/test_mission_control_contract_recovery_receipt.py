"""Legacy/current recovery-receipt contract compatibility regression."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dharma_swarm.mission_control_contract import (
    RECOVERY_RECEIPT_TYPE,
    SCHEMA_VERSION,
    recovery_receipt_matches_contract,
)
from dharma_swarm.runtime_state import RuntimeReceipt
from dharma_swarm.spine.identity import ExecutionIdentity

MISSION_ID = "mission-1"
TASK_ID = "task-1"
RUN_ID = "run-1"
CLAIM_ID = "claim-1"


def _identity() -> ExecutionIdentity:
    return ExecutionIdentity(
        trace_id="trace-1",
        correlation_id="trace-1",
        task_id=TASK_ID,
        run_id=RUN_ID,
        claim_id=CLAIM_ID,
        idempotency_key="idem-1",
    )


def _receipt(payload: dict[str, object], *, created_at: datetime) -> RuntimeReceipt:
    identity = _identity()
    return RuntimeReceipt(
        receipt_id=_receipt_id(),
        receipt_type=RECOVERY_RECEIPT_TYPE,
        status="stale_recovered",
        run_id=identity.run_id,
        task_id=identity.task_id,
        trace_id=identity.trace_id,
        correlation_id=identity.correlation_id,
        causation_id=identity.causation_id,
        parent_run_id=identity.parent_run_id,
        agent_id=identity.agent_id,
        idempotency_key=identity.idempotency_key,
        side_effect_key=f"mission_control:{identity.run_id}:stale_recovery",
        payload=payload,
        created_at=created_at,
    )


def _receipt_id() -> str:
    from dharma_swarm.mission_control_contract import stable_id

    return stable_id("receipt", RUN_ID, "stale_recovered")


def test_current_schema_recovery_receipt_matches_with_expired_stale_after() -> None:
    identity = _identity()
    now = datetime.now(timezone.utc)
    stale_after = now - timedelta(seconds=5)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": MISSION_ID,
        "attempt_id": RUN_ID,
        "recovered_claim_id": CLAIM_ID,
        "reason": "expired_lease",
        "expired_stale_after": stale_after.isoformat(),
    }
    receipt = _receipt(payload, created_at=now)
    assert recovery_receipt_matches_contract(
        receipt, identity, MISSION_ID, expired_stale_after=stale_after,
    )


def test_legacy_recovery_receipt_without_expired_stale_after_matches() -> None:
    """Pre-upgrade receipts legitimately omit ``expired_stale_after``."""
    identity = _identity()
    now = datetime.now(timezone.utc)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": MISSION_ID,
        "attempt_id": RUN_ID,
        "recovered_claim_id": CLAIM_ID,
        "reason": "expired_lease",
    }
    receipt = _receipt(payload, created_at=now)
    assert recovery_receipt_matches_contract(receipt, identity, MISSION_ID)


def test_legacy_recovery_receipt_refuses_future_caller_supplied_deadline() -> None:
    identity = _identity()
    now = datetime.now(timezone.utc)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": MISSION_ID,
        "attempt_id": RUN_ID,
        "recovered_claim_id": CLAIM_ID,
        "reason": "expired_lease",
    }
    receipt = _receipt(payload, created_at=now)
    future = now + timedelta(seconds=5)
    assert not recovery_receipt_matches_contract(
        receipt, identity, MISSION_ID, expired_stale_after=future,
    )


def test_legacy_recovery_receipt_refuses_extraneous_or_missing_fields() -> None:
    identity = _identity()
    now = datetime.now(timezone.utc)

    missing_reason = _receipt(
        {
            "schema_version": SCHEMA_VERSION,
            "mission_id": MISSION_ID,
            "attempt_id": RUN_ID,
            "recovered_claim_id": CLAIM_ID,
        },
        created_at=now,
    )
    assert not recovery_receipt_matches_contract(missing_reason, identity, MISSION_ID)

    extraneous = _receipt(
        {
            "schema_version": SCHEMA_VERSION,
            "mission_id": MISSION_ID,
            "attempt_id": RUN_ID,
            "recovered_claim_id": CLAIM_ID,
            "reason": "expired_lease",
            "unexpected_field": "x",
        },
        created_at=now,
    )
    assert not recovery_receipt_matches_contract(extraneous, identity, MISSION_ID)


def test_current_schema_recovery_receipt_rejects_malformed_or_future_deadline() -> None:
    identity = _identity()
    now = datetime.now(timezone.utc)

    malformed = _receipt(
        {
            "schema_version": SCHEMA_VERSION,
            "mission_id": MISSION_ID,
            "attempt_id": RUN_ID,
            "recovered_claim_id": CLAIM_ID,
            "reason": "expired_lease",
            "expired_stale_after": "not-a-timestamp",
        },
        created_at=now,
    )
    assert not recovery_receipt_matches_contract(malformed, identity, MISSION_ID)

    future_deadline = now + timedelta(seconds=5)
    future = _receipt(
        {
            "schema_version": SCHEMA_VERSION,
            "mission_id": MISSION_ID,
            "attempt_id": RUN_ID,
            "recovered_claim_id": CLAIM_ID,
            "reason": "expired_lease",
            "expired_stale_after": future_deadline.isoformat(),
        },
        created_at=now,
    )
    assert not recovery_receipt_matches_contract(future, identity, MISSION_ID)
