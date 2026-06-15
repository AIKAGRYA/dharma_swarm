from __future__ import annotations

import asyncio

from dharma_swarm.runtime_state import RUNTIME_RECEIPT_TYPES, RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.spine.warrant import RuntimeWarrantDenied, issue_runtime_warrant


def _identity() -> ExecutionIdentity:
    return ExecutionIdentity.new(
        task_id="task-warrant",
        trace_id="trace-warrant",
        correlation_id="corr-warrant",
        run_id="run-warrant",
        claim_id="claim-warrant",
        idempotency_key="idem-warrant",
        agent_id="codex",
    )


def _claim_idempotency(store: RuntimeStateStore, identity: ExecutionIdentity, side_effect_key: str) -> None:
    assert store.try_begin_idempotent_side_effect_sync(identity, side_effect_key) is True


def test_runtime_warrant_receipt_type_is_registered() -> None:
    assert "runtime_warrant" in RUNTIME_RECEIPT_TYPES


def test_issue_runtime_warrant_grants_and_persists_receipt(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()
    side_effect_key = "a2a_send.publish:dharma.a2a.codex:pkt"
    _claim_idempotency(store, identity, side_effect_key)

    warrant = issue_runtime_warrant(
        store=store,
        identity=identity,
        surface="scripts/runtime/a2a_send.py",
        action="publish",
        side_effect_key=side_effect_key,
        idempotency_inserted=True,
        requested_claims=("a2a_publish_attempt", "runtime_receipt_pending"),
        metadata={"packet_id": "pkt"},
    )

    receipts = asyncio.run(store.list_runtime_receipts(receipt_type="runtime_warrant"))
    assert warrant.status == "granted"
    assert warrant.receipt_id
    assert warrant.to_ref()["status"] == "granted"
    warrant_receipts = [receipt for receipt in receipts if receipt.receipt_type == "runtime_warrant"]
    assert len(warrant_receipts) == 1
    assert warrant_receipts[0].receipt_id == warrant.receipt_id
    assert warrant_receipts[0].payload["requested_claims"] == [
        "a2a_publish_attempt",
        "runtime_receipt_pending",
    ]
    assert warrant.to_ref()["idempotency_record_ref"] == f"idempotency_records:{identity.idempotency_key}:{side_effect_key}"


def test_issue_runtime_warrant_blocks_without_idempotency_claim(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")

    try:
        issue_runtime_warrant(
            store=store,
            identity=_identity(),
            surface="scripts/runtime/autonomy_spine.py",
            action="kernel_wake",
            side_effect_key="ds_goal.run:mission:task",
            idempotency_inserted=False,
            requested_claims=("kernel_wake_attempt",),
        )
    except RuntimeWarrantDenied as exc:
        assert "idempotency" in str(exc)
        assert exc.warrant is not None
        assert exc.warrant.status == "blocked"
    else:
        raise AssertionError("expected warrant denial")

    receipts = asyncio.run(store.list_runtime_receipts(receipt_type="runtime_warrant"))
    assert receipts[0].status == "blocked"
    assert receipts[0].payload["blocked_claims"] == ["kernel_wake_attempt"]


def test_issue_runtime_warrant_records_denial_for_missing_side_effect_key(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")

    try:
        issue_runtime_warrant(
            store=store,
            identity=_identity(),
            surface="scripts/runtime/a2a_send.py",
            action="publish",
            side_effect_key="",
            idempotency_inserted=True,
            requested_claims=("a2a_publish_attempt",),
        )
    except RuntimeWarrantDenied as exc:
        assert "side_effect_key" in str(exc)
        assert exc.warrant is not None
        assert exc.warrant.receipt_id
    else:
        raise AssertionError("expected missing side_effect_key denial")

    receipts = asyncio.run(store.list_runtime_receipts(receipt_type="runtime_warrant"))
    assert receipts[0].status == "blocked"
    assert receipts[0].side_effect_key == ""


def test_issue_runtime_warrant_blocks_pre_action_overclaim(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()
    side_effect_key = "a2a_send.publish:dharma.a2a.codex:pkt"
    _claim_idempotency(store, identity, side_effect_key)

    try:
        issue_runtime_warrant(
            store=store,
            identity=identity,
            surface="scripts/runtime/a2a_send.py",
            action="publish",
            side_effect_key=side_effect_key,
            idempotency_inserted=True,
            requested_claims=("a2a_publish_attempt", "completed", "live_contact"),
        )
    except RuntimeWarrantDenied as exc:
        assert "not allowed" in str(exc)
        assert exc.warrant is not None
        assert exc.warrant.blocked_claims == ("completed", "live_contact")
    else:
        raise AssertionError("expected warrant denial")

    receipts = asyncio.run(store.list_runtime_receipts(receipt_type="runtime_warrant"))
    assert receipts[0].status == "blocked"
    assert receipts[0].payload["blocked_claims"] == ["completed", "live_contact"]


def test_issue_runtime_warrant_blocks_forged_idempotency_inserted_flag(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")

    try:
        issue_runtime_warrant(
            store=store,
            identity=_identity(),
            surface="scripts/runtime/a2a_send.py",
            action="publish",
            side_effect_key="a2a_send.publish:dharma.a2a.codex:pkt",
            idempotency_inserted=True,
            requested_claims=("a2a_publish_attempt",),
        )
    except RuntimeWarrantDenied as exc:
        assert "idempotency record missing" in str(exc)
        assert exc.warrant is not None
        assert exc.warrant.status == "blocked"
    else:
        raise AssertionError("expected warrant denial")


def test_issue_runtime_warrant_blocks_idempotency_record_identity_mismatch(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()
    side_effect_key = "a2a_send.publish:dharma.a2a.codex:pkt"
    _claim_idempotency(store, identity, side_effect_key)
    mismatched_identity = identity.with_updates(run_id="run-other")

    try:
        issue_runtime_warrant(
            store=store,
            identity=mismatched_identity,
            surface="scripts/runtime/a2a_send.py",
            action="publish",
            side_effect_key=side_effect_key,
            idempotency_inserted=True,
            requested_claims=("a2a_publish_attempt",),
        )
    except RuntimeWarrantDenied as exc:
        assert "does not match execution identity" in str(exc)
        assert exc.warrant is not None
        assert exc.warrant.status == "blocked"
        assert exc.warrant.metadata["idempotency_mismatches"] == ["run_id"]
    else:
        raise AssertionError("expected mismatched idempotency identity denial")


def test_issue_runtime_warrant_normalizes_claim_names_before_policy_check(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()
    side_effect_key = "a2a_send.publish:dharma.a2a.codex:pkt"
    _claim_idempotency(store, identity, side_effect_key)

    try:
        issue_runtime_warrant(
            store=store,
            identity=identity,
            surface="scripts/runtime/a2a_send.py",
            action="publish",
            side_effect_key=side_effect_key,
            idempotency_inserted=True,
            requested_claims=("A2A Publish Attempt", "LIVE-CONTACT", "Runtime Receipt Pending"),
        )
    except RuntimeWarrantDenied as exc:
        assert exc.warrant is not None
        assert exc.warrant.requested_claims == (
            "a2a_publish_attempt",
            "live_contact",
            "runtime_receipt_pending",
        )
        assert exc.warrant.blocked_claims == ("live_contact",)
    else:
        raise AssertionError("expected normalized live-contact overclaim to be denied")


def test_issue_runtime_warrant_fails_closed_for_unknown_surface_action(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")

    try:
        issue_runtime_warrant(
            store=store,
            identity=_identity(),
            surface="scripts/runtime/unknown.py",
            action="publish",
            side_effect_key="unknown.publish:pkt",
            idempotency_inserted=True,
            requested_claims=("a2a_publish_attempt",),
        )
    except RuntimeWarrantDenied as exc:
        assert "no runtime warrant policy" in str(exc)
        assert exc.warrant is not None
        assert exc.warrant.status == "blocked"
    else:
        raise AssertionError("expected unknown warrant policy to be denied")


def test_issue_runtime_warrant_requires_requested_claim_boundary(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")

    try:
        issue_runtime_warrant(
            store=store,
            identity=_identity(),
            surface="scripts/runtime/a2a_send.py",
            action="publish",
            side_effect_key="a2a_send.publish:dharma.a2a.codex:pkt",
            idempotency_inserted=True,
            requested_claims=(),
        )
    except RuntimeWarrantDenied as exc:
        assert "at least one requested claim" in str(exc)
        assert exc.warrant is not None
        assert exc.warrant.status == "blocked"
    else:
        raise AssertionError("expected empty warrant claim boundary to be denied")
