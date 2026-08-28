from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

import dharma_swarm.governed_patch_effect as effect_impl
import dharma_swarm.mission_control_effect_completion as completion_module
import dharma_swarm.mission_control_recovery as recovery_module
from dharma_swarm.mission_control_contract import (
    GOVERNED_PATCH_COMPLETION_CONTRACT,
    GOVERNED_PATCH_COMPLETION_PROOF_SCHEMA,
    GOVERNED_PATCH_COMPLETION_RESULT,
    SCHEMA_VERSION,
    TERMINAL_RECEIPT_TYPE,
    MissionControlError,
    stable_id,
)
from dharma_swarm.mission_control_effect_records import (
    EffectRefusal,
    EffectTerminalRecord,
)
from dharma_swarm.mission_control_effect_owner import inspect_owner_stores, owner_transaction
from dharma_swarm.mission_control_effect_owner_recovery import (
    observe_expired_proposal_for_effect_recovery_from_connection,
)
from dharma_swarm.models import TaskStatus
from dharma_swarm.runtime_state_effect_fence import (
    EFFECT_FENCE_TABLE,
    EFFECT_RECEIPT_ID_PREFIX,
)
from dharma_swarm.task_board import TaskBoardError
from tests.test_mission_control_effect_fence import (
    EffectHarness,
    _fresh_recovery_authority,
    _issue,
    _shorten_claim,
    _wait_past,
    effect_harness as effect_harness,
)

_PROOF_METADATA_FIELDS = {
    "schema_version",
    "mission_id",
    "attempt_id",
    "attempt_key",
    "completion_contract",
    "proof_schema",
    "effect_key",
    "effect_terminal_id",
    "effect_terminal_receipt_id",
    "effect_terminal_receipt_sha256",
    "effect_fence_id",
    "effect_binding_sha256",
    "candidate_bundle_sha256",
    "diff_sha256",
    "base_sha",
    "postimage_sha256",
}


def _consume(harness: EffectHarness) -> EffectTerminalRecord:
    warrant = _issue(harness)
    terminal = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )
    assert isinstance(terminal, EffectTerminalRecord)
    return terminal


async def _finish(harness: EffectHarness):
    return await harness.control.finish_attempt_from_patch_effect(
        harness.binding.mission_id,
        harness.binding.task_id,
        harness.binding.executor_agent_uid,
        attempt_id=harness.binding.mission_attempt_id,
        effect_key=harness.binding.effect_key,
    )


async def _assert_no_parent_terminal(harness: EffectHarness) -> None:
    receipts = await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    )
    identity = await harness.runtime.get_execution_identity(
        harness.binding.mission_attempt_id
    )
    assert identity is not None
    ownership = await harness.runtime.get_idempotency_record(
        identity.idempotency_key,
        f"mission_control:{identity.run_id}:terminal",
    )
    assert receipts == []
    assert ownership is None


def _expected_proof_metadata(
    harness: EffectHarness,
    terminal: EffectTerminalRecord,
) -> dict[str, str]:
    return {
        "schema_version": SCHEMA_VERSION,
        "mission_id": harness.binding.mission_id,
        "attempt_id": harness.binding.mission_attempt_id,
        "attempt_key": harness.expected.attempt_key,
        "completion_contract": GOVERNED_PATCH_COMPLETION_CONTRACT,
        "proof_schema": GOVERNED_PATCH_COMPLETION_PROOF_SCHEMA,
        "effect_key": terminal.effect_key,
        "effect_terminal_id": terminal.terminal_id,
        "effect_terminal_receipt_id": terminal.terminal_receipt_id,
        "effect_terminal_receipt_sha256": terminal.terminal_receipt_sha256,
        "effect_fence_id": terminal.fence_id,
        "effect_binding_sha256": terminal.binding_sha256,
        "candidate_bundle_sha256": terminal.candidate_bundle_sha256,
        "diff_sha256": terminal.diff_sha256,
        "base_sha": terminal.base_sha,
        "postimage_sha256": terminal.postimage_sha256,
    }


@pytest.mark.asyncio
async def test_effect_harness_marks_contract_before_attempt_creation(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    task = await harness.board.get(harness.binding.task_id)
    identity = await harness.runtime.get_execution_identity(
        harness.binding.mission_attempt_id
    )
    run = await harness.runtime.get_delegation_run(
        harness.binding.mission_attempt_id
    )
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert task is not None and identity is not None
    assert run is not None and claim is not None
    assert {
        task.metadata["completion_contract"],
        identity.metadata["completion_contract"],
        run.metadata["completion_contract"],
        claim.metadata["completion_contract"],
    } == {GOVERNED_PATCH_COMPLETION_CONTRACT}


@pytest.mark.asyncio
async def test_consumed_effect_proof_completes_once_and_replays_exactly(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    terminal = _consume(harness)

    first = await _finish(harness)
    replay = await _finish(harness)

    assert replay == first
    assert first.receipt_id == stable_id(
        "receipt", harness.binding.mission_attempt_id, "succeeded"
    )
    assert first.receipt_type == TERMINAL_RECEIPT_TYPE
    assert first.status == "succeeded"
    assert first.payload == {
        "schema_version": SCHEMA_VERSION,
        "mission_id": harness.binding.mission_id,
        "attempt_id": harness.binding.mission_attempt_id,
        "result": GOVERNED_PATCH_COMPLETION_RESULT,
        "failure_code": "",
        "metadata": _expected_proof_metadata(harness, terminal),
    }
    assert set(first.payload["metadata"]) == _PROOF_METADATA_FIELDS

    task = await harness.board.get(harness.binding.task_id)
    run = await harness.runtime.get_delegation_run(
        harness.binding.mission_attempt_id
    )
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    identity = await harness.runtime.get_execution_identity(
        harness.binding.mission_attempt_id
    )
    assert task is not None and task.status == TaskStatus.COMPLETED
    assert task.result == GOVERNED_PATCH_COMPLETION_RESULT
    assert run is not None and run.status == "completed"
    assert run.failure_code == ""
    assert claim is not None and claim.status == "completed"
    assert identity is not None
    ownership = await harness.runtime.get_idempotency_record(
        identity.idempotency_key,
        f"mission_control:{identity.run_id}:terminal",
    )
    assert ownership is not None and ownership.status == "completed"
    assert ownership.result_receipt_id == first.receipt_id
    receipts = await harness.runtime.list_runtime_receipts(
        run_id=identity.run_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    )
    assert [receipt.receipt_id for receipt in receipts] == [first.receipt_id]
    snapshot = await harness.control.get_snapshot(harness.binding.mission_id)
    assert snapshot is not None
    assert snapshot.reconciliation.value == "coherent"


@pytest.mark.asyncio
async def test_proof_completion_retry_repairs_task_and_claim_projection_crash(
    effect_harness: EffectHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = effect_harness
    _consume(harness)
    original_complete = harness.board.complete

    async def crash_before_task_projection(*args: Any, **kwargs: Any) -> None:
        raise TaskBoardError("simulated proof task projection crash")

    monkeypatch.setattr(harness.board, "complete", crash_before_task_projection)
    with pytest.raises(MissionControlError, match="proof task projection crash"):
        await _finish(harness)

    receipts = await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    )
    task = await harness.board.get(harness.binding.task_id)
    run = await harness.runtime.get_delegation_run(
        harness.binding.mission_attempt_id
    )
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert len(receipts) == 1
    assert task is not None and task.status == TaskStatus.RUNNING
    assert run is not None and run.status == "completed"
    assert claim is not None and claim.status == "active"

    monkeypatch.setattr(harness.board, "complete", original_complete)
    replay = await _finish(harness)
    assert replay.receipt_id == receipts[0].receipt_id
    repaired_task = await harness.board.get(harness.binding.task_id)
    repaired_claim = await harness.runtime.get_task_claim(
        harness.binding.mission_claim_id
    )
    assert repaired_task is not None and repaired_task.status == TaskStatus.COMPLETED
    assert repaired_claim is not None and repaired_claim.status == "completed"
    snapshot = await harness.control.get_snapshot(harness.binding.mission_id)
    assert snapshot is not None and snapshot.reconciliation.value == "coherent"


@pytest.mark.asyncio
async def test_same_key_restart_repairs_committed_parent_before_returning(
    effect_harness: EffectHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = effect_harness
    _consume(harness)
    original_complete = harness.board.complete

    async def crash_before_task_projection(*args: Any, **kwargs: Any) -> None:
        raise TaskBoardError("simulated responder restart window")

    monkeypatch.setattr(harness.board, "complete", crash_before_task_projection)
    with pytest.raises(MissionControlError, match="responder restart window"):
        await _finish(harness)
    monkeypatch.setattr(harness.board, "complete", original_complete)

    restarted = await harness.control.start_attempt(
        harness.binding.mission_id,
        harness.binding.task_id,
        harness.binding.executor_agent_uid,
        attempt_key=harness.expected.attempt_key,
    )

    task = await harness.board.get(harness.binding.task_id)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    snapshot = await harness.control.get_snapshot(harness.binding.mission_id)
    assert restarted.status == "succeeded"
    assert task is not None and task.status == TaskStatus.COMPLETED
    assert claim is not None and claim.status == "completed"
    assert snapshot is not None and snapshot.reconciliation.value == "coherent"


@pytest.mark.asyncio
async def test_parent_receipt_never_predates_observed_effect_under_clock_skew(
    effect_harness: EffectHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = effect_harness
    terminal = _consume(harness)

    class LaggingClock:
        @classmethod
        def now(cls, tz=None):
            del cls, tz
            return terminal.consumed_at - timedelta(seconds=5)

    monkeypatch.setattr(completion_module, "datetime", LaggingClock)
    await _finish(harness)
    parents = await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    )
    assert len(parents) == 1
    assert terminal.consumed_at <= parents[0].created_at
    snapshot = await harness.control.get_snapshot(harness.binding.mission_id)
    assert snapshot is not None and snapshot.reconciliation.value == "coherent"


@pytest.mark.parametrize(
    "drift",
    ("run_metadata", "claim_metadata", "completed_at", "failure_code", "task_agent"),
)
@pytest.mark.asyncio
async def test_completed_owner_drift_is_never_reported_coherent_or_replayed(
    effect_harness: EffectHarness,
    drift: str,
) -> None:
    harness = effect_harness
    _consume(harness)
    await _finish(harness)
    run = await harness.runtime.get_delegation_run(
        harness.binding.mission_attempt_id
    )
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert run is not None and claim is not None
    if drift == "run_metadata":
        await harness.runtime.record_delegation_run(
            replace(run, metadata={**run.metadata, "effect_key": "foreign-effect"})
        )
    elif drift == "claim_metadata":
        await harness.runtime.record_task_claim(
            replace(
                claim,
                metadata={**claim.metadata, "effect_key": "foreign-effect"},
            )
        )
    elif drift == "completed_at":
        await harness.runtime.record_delegation_run(replace(run, completed_at=None))
    elif drift == "failure_code":
        await harness.runtime.record_delegation_run(
            replace(run, failure_code="foreign-failure")
        )
    else:
        await harness.board.update_task(
            harness.binding.task_id,
            assigned_to="foreign-terminal-agent",
        )

    snapshot = await harness.control.get_snapshot(harness.binding.mission_id)
    assert snapshot is not None
    assert snapshot.reconciliation.value == "conflicting_terminal_evidence"
    with pytest.raises(MissionControlError):
        await _finish(harness)


@pytest.mark.parametrize("drift", ("fence", "effect_idempotency"))
@pytest.mark.asyncio
async def test_snapshot_rejoins_live_exact_effect_terminal_triple(
    effect_harness: EffectHarness,
    drift: str,
) -> None:
    harness = effect_harness
    terminal = _consume(harness)
    await _finish(harness)
    with sqlite3.connect(harness.runtime_path) as database:
        if drift == "fence":
            database.execute(
                f"DELETE FROM {EFFECT_FENCE_TABLE} WHERE effect_key=?",
                (harness.binding.effect_key,),
            )
        else:
            database.execute(
                "UPDATE idempotency_records SET status='foreign'"
                " WHERE side_effect_key=? AND result_receipt_id=?",
                (harness.binding.effect_key, terminal.terminal_receipt_id),
            )
        database.commit()

    snapshot = await harness.control.get_snapshot(harness.binding.mission_id)
    assert snapshot is not None
    assert snapshot.reconciliation.value == "conflicting_terminal_evidence"


@pytest.mark.asyncio
async def test_replay_refuses_foreign_same_status_task_projection(
    effect_harness: EffectHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = effect_harness
    _consume(harness)
    original_complete = harness.board.complete

    async def crash_before_task_projection(*args: Any, **kwargs: Any) -> None:
        raise TaskBoardError("simulated proof task projection crash")

    monkeypatch.setattr(harness.board, "complete", crash_before_task_projection)
    with pytest.raises(MissionControlError, match="proof task projection crash"):
        await _finish(harness)
    monkeypatch.setattr(harness.board, "complete", original_complete)
    await harness.board.complete(harness.binding.task_id, result="caller assertion")

    with pytest.raises(MissionControlError, match="conflicting terminal projection"):
        await _finish(harness)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    snapshot = await harness.control.get_snapshot(harness.binding.mission_id)
    assert claim is not None and claim.status == "active"
    assert snapshot is not None
    assert snapshot.reconciliation.value == "conflicting_terminal_evidence"


@pytest.mark.asyncio
async def test_replay_refuses_conflicting_terminal_claim_without_task_mutation(
    effect_harness: EffectHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = effect_harness
    _consume(harness)
    original_complete = harness.board.complete

    async def crash_before_task_projection(*args: Any, **kwargs: Any) -> None:
        raise TaskBoardError("simulated proof task projection crash")

    monkeypatch.setattr(harness.board, "complete", crash_before_task_projection)
    with pytest.raises(MissionControlError, match="proof task projection crash"):
        await _finish(harness)
    monkeypatch.setattr(harness.board, "complete", original_complete)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert claim is not None
    await harness.runtime.record_task_claim(replace(claim, status="failed"))

    with pytest.raises(MissionControlError, match="completed owner CAS"):
        await _finish(harness)
    task = await harness.board.get(harness.binding.task_id)
    assert task is not None and task.status == TaskStatus.RUNNING


@pytest.mark.asyncio
async def test_snapshot_refuses_malformed_preterminal_effect_receipt(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    terminal = _consume(harness)
    with sqlite3.connect(harness.runtime_path) as database:
        database.execute(
            "UPDATE runtime_receipts SET payload_json='{}' WHERE receipt_id=?",
            (terminal.terminal_receipt_id,),
        )
        database.commit()

    snapshot = await harness.control.get_snapshot(harness.binding.mission_id)
    assert snapshot is not None
    assert snapshot.reconciliation.value == "foreign_runtime_record"


@pytest.mark.asyncio
async def test_effect_owner_recovery_observes_proof_bound_terminal(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    _consume(harness)
    await _finish(harness)
    owners = inspect_owner_stores(harness.runtime_path, harness.task_path)
    with owner_transaction(owners) as database:
        observation = observe_expired_proposal_for_effect_recovery_from_connection(
            database,
            harness.expected,
            mission_attempt_id=harness.binding.mission_attempt_id,
            mission_claim_id=harness.binding.mission_claim_id,
            proposal_receipt_id=harness.binding.proposal_receipt_id,
            proposal_receipt_sha256=harness.binding.proposal_receipt_sha256,
        )
        database.rollback()
    assert observation.owner_transition == "canonical_terminal"
    assert observation.owner_reconciliation == "coherent"


@pytest.mark.asyncio
async def test_expired_effect_recovery_replays_parent_proof_that_wins_race(
    effect_harness: EffectHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = effect_harness
    _consume(harness)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert claim is not None
    fresh_until = datetime.now(timezone.utc) + timedelta(seconds=60)
    claim = await harness.runtime.record_task_claim(
        replace(claim, stale_after=fresh_until)
    )
    recovery_now = fresh_until + timedelta(seconds=1)
    monkeypatch.setattr(recovery_module, "utc_now", lambda: recovery_now)
    original_inspect = completion_module.inspect_owner_stores

    def commit_parent_proof(runtime_path, task_path):
        owners = original_inspect(runtime_path, task_path)
        with owner_transaction(owners) as database:
            harness.control._promote_patch_effect(
                database,
                owners,
                mission_id=harness.binding.mission_id,
                task_id=harness.binding.task_id,
                agent_id=harness.binding.executor_agent_uid,
                attempt_id=harness.binding.mission_attempt_id,
                effect_key=harness.binding.effect_key,
            )
            database.commit()
        return owners

    monkeypatch.setattr(completion_module, "inspect_owner_stores", commit_parent_proof)
    repaired = await harness.control._recover_expired_claim(
        harness.binding.mission_id,
        claim,
        recovered_at=recovery_now,
    )

    run = await harness.runtime.get_delegation_run(harness.binding.mission_attempt_id)
    current_claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    terminal_receipts = await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    )
    recovery_receipts = await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type="mission_attempt_recovery",
    )
    assert repaired is True
    assert run is not None and run.status == "completed"
    assert current_claim is not None and current_claim.status == "completed"
    assert len(terminal_receipts) == 1
    assert recovery_receipts == []


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["missing", "wrong", "nonconsumed"])
async def test_completion_refuses_missing_wrong_or_nonconsumed_effect(
    effect_harness: EffectHarness,
    case: str,
) -> None:
    harness = effect_harness
    if case == "nonconsumed":
        _issue(harness)
        effect_key = harness.binding.effect_key
    elif case == "wrong":
        effect_key = "governed_patch_effect:" + "f" * 64
    else:
        effect_key = ""

    with pytest.raises(MissionControlError):
        await harness.control.finish_attempt_from_patch_effect(
            harness.binding.mission_id,
            harness.binding.task_id,
            harness.binding.executor_agent_uid,
            attempt_id=harness.binding.mission_attempt_id,
            effect_key=effect_key,
        )
    await _assert_no_parent_terminal(harness)


@pytest.mark.asyncio
async def test_completion_refuses_quarantined_effect_slot(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    warrant = _issue(harness)
    digest = hashlib.sha256(harness.binding.effect_key.encode()).hexdigest()
    receipt_id = EFFECT_RECEIPT_ID_PREFIX + digest
    with sqlite3.connect(harness.runtime_path) as database:
        database.execute(
            "INSERT INTO runtime_receipts"
            " (receipt_id,receipt_type,run_id,task_id,trace_id,correlation_id,"
            " causation_id,parent_run_id,agent_id,idempotency_key,side_effect_key,"
            " status,payload_json,created_at)"
            " VALUES (?,?,'','','','','','','','','','occupied','{}',datetime('now'))",
            (receipt_id, "hostile_alias"),
        )
        database.commit()
    refused = harness.fence.consume_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        warrant,
        harness.candidate,
        claimed_by="effect-supervisor",
    )
    assert isinstance(refused, EffectRefusal)

    with pytest.raises(MissionControlError):
        await _finish(harness)
    await _assert_no_parent_terminal(harness)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["fence", "receipt", "idempotency"])
async def test_completion_refuses_tampered_effect_terminal_triple(
    effect_harness: EffectHarness,
    surface: str,
) -> None:
    harness = effect_harness
    terminal = _consume(harness)
    with sqlite3.connect(harness.runtime_path) as database:
        if surface == "fence":
            raw = database.execute(
                "SELECT terminal_record_json FROM mission_control_effect_fences"
                " WHERE effect_key=?",
                (terminal.effect_key,),
            ).fetchone()[0]
            payload = json.loads(raw)
            payload["postimage_sha256"] = "0" * 64
            database.execute(
                "UPDATE mission_control_effect_fences SET terminal_record_json=?"
                " WHERE effect_key=?",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")), terminal.effect_key),
            )
        elif surface == "receipt":
            database.execute(
                "UPDATE runtime_receipts SET payload_json='{}' WHERE receipt_id=?",
                (terminal.terminal_receipt_id,),
            )
        else:
            database.execute(
                "UPDATE idempotency_records SET result_receipt_id='rr_foreign'"
                " WHERE side_effect_key=?",
                (terminal.effect_key,),
            )
        database.commit()

    with pytest.raises(MissionControlError):
        await _finish(harness)
    await _assert_no_parent_terminal(harness)


@pytest.mark.asyncio
async def test_completion_refuses_generic_parent_terminal_collision(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    _consume(harness)
    identity = await harness.runtime.get_execution_identity(
        harness.binding.mission_attempt_id
    )
    assert identity is not None
    await harness.runtime.record_receipt_for_identity(
        identity,
        receipt_type=TERMINAL_RECEIPT_TYPE,
        status="succeeded",
        side_effect_key=f"mission_control:{identity.run_id}:terminal",
        receipt_id=stable_id("receipt", identity.run_id, "succeeded"),
        payload={"caller_claim": "not effect proof"},
    )

    with pytest.raises(MissionControlError):
        await _finish(harness)
    receipts = await harness.runtime.list_runtime_receipts(
        run_id=identity.run_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    )
    assert len(receipts) == 1
    assert receipts[0].payload == {"caller_claim": "not effect proof"}
    assert (
        await harness.runtime.get_idempotency_record(
            identity.idempotency_key,
            f"mission_control:{identity.run_id}:terminal",
        )
        is None
    )


@pytest.mark.asyncio
async def test_completion_refuses_expired_claim(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    _consume(harness)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert claim is not None
    await harness.runtime.record_task_claim(
        replace(
            claim,
            stale_after=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )

    with pytest.raises(MissionControlError, match="fresh active claim"):
        await _finish(harness)
    await _assert_no_parent_terminal(harness)


@pytest.mark.asyncio
async def test_completion_refuses_second_run_scoped_effect_receipt(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    terminal = _consume(harness)
    with sqlite3.connect(harness.runtime_path) as database:
        database.execute(
            "INSERT INTO runtime_receipts SELECT ?,receipt_type,run_id,task_id,"
            "trace_id,correlation_id,causation_id,parent_run_id,agent_id,?,?,status,"
            "payload_json,created_at FROM runtime_receipts WHERE receipt_id=?",
            (
                "rr_foreign_run_scoped_effect",
                "idem_rr_foreign_run_scoped_effect",
                "governed_patch_effect:foreign-run-scoped-evidence",
                terminal.terminal_receipt_id,
            ),
        )
        database.commit()

    with pytest.raises(MissionControlError, match="run-scoped effect receipt"):
        await _finish(harness)
    await _assert_no_parent_terminal(harness)


@pytest.mark.asyncio
async def test_internal_recovery_promotes_only_expired_active_consumed_effect(
    effect_harness: EffectHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = effect_harness
    terminal = _consume(harness)
    with pytest.raises(MissionControlError, match="expired active"):
        await harness.control._recover_attempt_from_patch_effect(
            harness.binding.mission_id,
            harness.binding.task_id,
            harness.binding.executor_agent_uid,
            attempt_id=harness.binding.mission_attempt_id,
            effect_key=harness.binding.effect_key,
        )
    expiry = terminal.consumed_at + timedelta(seconds=30)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert claim is not None
    await harness.runtime.record_task_claim(replace(claim, stale_after=expiry))

    class ExpiredClock:
        @classmethod
        def now(cls, tz=None):
            del cls, tz
            return expiry + timedelta(seconds=1)

    monkeypatch.setattr(completion_module, "datetime", ExpiredClock)
    with pytest.raises(MissionControlError, match="fresh active"):
        await _finish(harness)
    await _assert_no_parent_terminal(harness)

    run = await harness.runtime.get_delegation_run(harness.binding.mission_attempt_id)
    assert run is not None
    partial_successor = replace(
        run,
        run_id="attempt_partial_successor",
        claim_id="lease_partial_successor",
        status="queued",
        started_at=run.started_at,
    )
    await harness.runtime.record_delegation_run(partial_successor)
    with pytest.raises(MissionControlError, match="run was superseded"):
        await harness.control._recover_attempt_from_patch_effect(
            harness.binding.mission_id,
            harness.binding.task_id,
            harness.binding.executor_agent_uid,
            attempt_id=harness.binding.mission_attempt_id,
            effect_key=harness.binding.effect_key,
        )
    await _assert_no_parent_terminal(harness)
    await harness.runtime.record_delegation_run(
        replace(partial_successor, started_at=run.started_at - timedelta(seconds=1))
    )
    with pytest.raises(MissionControlError, match="run was superseded"):
        await harness.control._recover_attempt_from_patch_effect(
            harness.binding.mission_id,
            harness.binding.task_id,
            harness.binding.executor_agent_uid,
            attempt_id=harness.binding.mission_attempt_id,
            effect_key=harness.binding.effect_key,
        )
    await _assert_no_parent_terminal(harness)
    with sqlite3.connect(harness.runtime_path) as database:
        database.execute(
            "DELETE FROM delegation_runs WHERE run_id=?",
            (partial_successor.run_id,),
        )
        database.commit()

    receipt = await harness.control._recover_attempt_from_patch_effect(
        harness.binding.mission_id,
        harness.binding.task_id,
        harness.binding.executor_agent_uid,
        attempt_id=harness.binding.mission_attempt_id,
        effect_key=harness.binding.effect_key,
    )
    assert receipt.status == "succeeded"
    task = await harness.board.get(harness.binding.task_id)
    run = await harness.runtime.get_delegation_run(harness.binding.mission_attempt_id)
    closed_claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert task is not None and task.status == TaskStatus.COMPLETED
    assert run is not None and run.status == "completed"
    assert closed_claim is not None and closed_claim.status == "completed"


@pytest.mark.asyncio
async def test_internal_recovery_accepts_late_expired_active_recovery_terminal(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    deadline = await _shorten_claim(
        harness, harness.binding.mission_claim_id, seconds=0.5
    )
    warrant = _issue(harness)
    effect_impl._perform_prevalidated_effect(warrant.binding, harness.candidate)
    _wait_past(deadline)
    terminal = harness.fence.recover_effect_slot(
        harness.runtime_path,
        harness.task_path,
        harness.expected,
        harness.binding.effect_key,
        harness.candidate,
        _fresh_recovery_authority(harness),
        claimed_by="effect-supervisor",
    )
    assert isinstance(terminal, EffectTerminalRecord)
    assert terminal.recovery_finalized is True
    assert terminal.recovery_owner_basis == "expired_active"
    assert terminal.consumed_at >= deadline

    receipt = await harness.control._recover_attempt_from_patch_effect(
        harness.binding.mission_id,
        harness.binding.task_id,
        harness.binding.executor_agent_uid,
        attempt_id=harness.binding.mission_attempt_id,
        effect_key=harness.binding.effect_key,
    )
    assert receipt.status == "succeeded"


@pytest.mark.asyncio
async def test_same_attempt_key_restart_promotes_committed_effect(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    terminal = _consume(harness)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert claim is not None
    await harness.runtime.record_task_claim(
        replace(
            claim,
            stale_after=terminal.consumed_at + timedelta(microseconds=1),
        )
    )

    repaired = await harness.control.start_attempt(
        harness.binding.mission_id,
        harness.binding.task_id,
        harness.binding.executor_agent_uid,
        attempt_key=harness.expected.attempt_key,
        assigned_by=harness.expected.assigned_by,
    )

    assert repaired.attempt_id == harness.binding.mission_attempt_id
    assert repaired.status == "succeeded"
    task = await harness.board.get(harness.binding.task_id)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    receipts = await harness.runtime.list_runtime_receipts(
        run_id=harness.binding.mission_attempt_id,
        receipt_type=TERMINAL_RECEIPT_TYPE,
    )
    assert task is not None and task.status == TaskStatus.COMPLETED
    assert claim is not None and claim.status == "completed"
    assert len(receipts) == 1


@pytest.mark.asyncio
async def test_successor_start_repairs_effect_then_refuses_new_lineage(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    terminal = _consume(harness)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert claim is not None
    await harness.runtime.record_task_claim(
        replace(
            claim,
            stale_after=terminal.consumed_at + timedelta(microseconds=1),
        )
    )

    with pytest.raises(MissionControlError, match="cannot start from 'completed'"):
        await harness.control.start_attempt(
            harness.binding.mission_id,
            harness.binding.task_id,
            "successor-agent",
            attempt_key="must-not-mint-successor",
        )

    snapshot = await harness.control.get_snapshot(harness.binding.mission_id)
    assert snapshot is not None
    assert snapshot.reconciliation.value == "coherent"
    assert len(snapshot.attempts) == 1
    assert snapshot.attempts[0].attempt_id == harness.binding.mission_attempt_id
    assert snapshot.attempts[0].status == "succeeded"


@pytest.mark.asyncio
async def test_completion_refuses_superseded_claim(
    effect_harness: EffectHarness,
) -> None:
    harness = effect_harness
    _consume(harness)
    claim = await harness.runtime.get_task_claim(harness.binding.mission_claim_id)
    assert claim is not None
    superseded_at = datetime.now(timezone.utc) + timedelta(seconds=1)
    await harness.runtime.record_task_claim(
        replace(
            claim,
            claim_id="lease_superseding_closed_lineage",
            status="stale_recovered",
            claimed_at=superseded_at,
            acked_at=superseded_at,
            heartbeat_at=superseded_at,
            stale_after=superseded_at,
            recovered_at=superseded_at,
        )
    )

    with pytest.raises(MissionControlError):
        await _finish(harness)
    await _assert_no_parent_terminal(harness)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "surface", ["task", "identity", "identity_extra", "run", "claim"]
)
async def test_completion_refuses_completion_contract_marker_drift(
    effect_harness: EffectHarness,
    surface: str,
) -> None:
    harness = effect_harness
    _consume(harness)
    if surface == "task":
        task = await harness.board.get(harness.binding.task_id)
        assert task is not None
        metadata = dict(task.metadata)
        metadata.pop("completion_contract")
        await harness.board.update_task(task.id, metadata=metadata)
    else:
        table, key_column, key = {
            "identity": (
                "execution_identities",
                "run_id",
                harness.binding.mission_attempt_id,
            ),
            "identity_extra": (
                "execution_identities",
                "run_id",
                harness.binding.mission_attempt_id,
            ),
            "run": (
                "delegation_runs",
                "run_id",
                harness.binding.mission_attempt_id,
            ),
            "claim": (
                "task_claims",
                "claim_id",
                harness.binding.mission_claim_id,
            ),
        }[surface]
        with sqlite3.connect(harness.runtime_path) as database:
            raw = database.execute(
                f"SELECT metadata_json FROM {table} WHERE {key_column}=?",
                (key,),
            ).fetchone()[0]
            metadata = json.loads(raw)
            if surface == "identity_extra":
                metadata["caller_claim"] = "not parent authority"
            else:
                metadata.pop("completion_contract")
            database.execute(
                f"UPDATE {table} SET metadata_json=? WHERE {key_column}=?",
                (json.dumps(metadata, sort_keys=True, separators=(",", ":")), key),
            )
            database.commit()

    with pytest.raises(MissionControlError):
        await _finish(harness)
    await _assert_no_parent_terminal(harness)
