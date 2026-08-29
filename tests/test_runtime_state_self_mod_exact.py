from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from dataclasses import replace

import pytest

from dharma_swarm.runtime_state import (
    RuntimeReceipt,
    RuntimeStateStore,
    SessionEventRecord,
)
from dharma_swarm.spine.identity import ExecutionIdentity, MissingExecutionIdentity


class _DisguisedStr(str):
    def __str__(self) -> str:
        return "ordinary-looking"


class _ScalarInt(int):
    pass


class _ScalarFloat(float):
    pass


class _DuplicateLookingKey(str):
    def __new__(cls, token: str):
        value = super().__new__(cls, "x")
        value.token = token
        return value

    def __hash__(self) -> int:
        return hash((str.__hash__(self), self.token))

    def __eq__(self, other) -> bool:
        return self is other


class _CustomMapping(dict):
    pass


class _VaryingRuntimeReceipt(RuntimeReceipt):
    def __getattribute__(self, name: str):
        if name in {"receipt_type", "side_effect_key"}:
            state = object.__getattribute__(self, "__dict__")
            counts = state.setdefault("_varying_reads", {})
            count = counts.get(name, 0)
            counts[name] = count + 1
            if name == "receipt_type":
                return "artifact" if count == 0 else "self_mod_gate"
            return "artifact:ordinary" if count == 0 else "self_mod:proposal-exact:gate"
        return super().__getattribute__(name)


class _VaryingExecutionIdentity(ExecutionIdentity):
    def __getattribute__(self, name: str):
        if name == "agent_id":
            state = object.__getattribute__(self, "__dict__")
            count = state.get("_agent_reads", 0)
            state["_agent_reads"] = count + 1
            return object.__getattribute__(self, name) if count == 0 else "another-agent"
        return super().__getattribute__(name)


def _identity(
    suffix: str = "one",
    *,
    proposal_id: str = "proposal-exact",
) -> ExecutionIdentity:
    return ExecutionIdentity.new(
        task_id=f"task-{suffix}",
        run_id=f"run-{suffix}",
        trace_id=f"trace-{suffix}",
        correlation_id=f"correlation-{suffix}",
        claim_id=f"claim-{suffix}",
        idempotency_key=f"idempotency-{suffix}",
        causation_id=f"cause-{suffix}",
        parent_run_id=f"parent-{suffix}",
        agent_id=f"agent-{suffix}",
        session_id=f"session-{suffix}",
        external_a2a_task_id=f"a2a-{suffix}",
        message_id=f"message-{suffix}",
        event_id=f"event-{suffix}",
        artifact_id=f"artifact-{suffix}",
        proposal_id=proposal_id,
        metadata={"seat": suffix, "nested": {"ordinal": 1}},
    )


async def _prepared_store(tmp_path, *, suffix: str = "one") -> tuple[RuntimeStateStore, ExecutionIdentity]:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity(suffix)
    await store.record_execution_identity(identity, source="exact-self-mod-test")
    return store, identity


def _slot_receipt_id(proposal_id: str, stage: str) -> str:
    slot = json.dumps(
        {"proposal_id": proposal_id, "stage": stage},
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return f"rr_self_mod_exact_{hashlib.sha256(slot.encode('utf-8')).hexdigest()[:32]}"


def _pair_counts(store: RuntimeStateStore, side_effect_key: str) -> tuple[int, int]:
    with sqlite3.connect(store.db_path) as db:
        row = db.execute(
            "SELECT"
            " (SELECT COUNT(*) FROM runtime_receipts WHERE side_effect_key = ?),"
            " (SELECT COUNT(*) FROM idempotency_records WHERE side_effect_key = ?)",
            (side_effect_key, side_effect_key),
        ).fetchone()
    assert row is not None
    return int(row[0]), int(row[1])


def _verifier_identity(
    *,
    signer_public_key: str = "signer-key-one",
    process_boot_id: str = "boot-one",
) -> ExecutionIdentity:
    return replace(
        _identity("verifier"),
        metadata={
            "role": "foundry_verifier",
            "signer_public_key": signer_public_key,
            "process_boot_id": process_boot_id,
            "nested": {"ordinal": 1},
        },
    )


def _exact_identity_row(store: RuntimeStateStore, run_id: str) -> sqlite3.Row:
    with sqlite3.connect(store.db_path) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT * FROM execution_identities WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    assert row is not None
    return row


def test_exact_execution_identity_sync_insert_and_restart_replay(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _verifier_identity()

    first = store.record_execution_identity_exact_sync(
        identity,
        source="governed_patch.foundry_verifier",
    )
    first_row = _exact_identity_row(store, identity.run_id)
    restarted = RuntimeStateStore(store.db_path, include_memory_plane=False)
    replay = restarted.record_execution_identity_exact_sync(
        identity,
        source="governed_patch.foundry_verifier",
    )
    replay_row = _exact_identity_row(restarted, identity.run_id)

    assert first == replay == identity
    assert first_row["source"] == "exact:governed_patch.foundry_verifier"
    assert json.loads(first_row["metadata_json"]) == identity.metadata
    assert first_row["metadata_json"] == json.dumps(
        identity.metadata,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    assert first_row["created_at"] == replay_row["created_at"]
    assert first_row["updated_at"] == replay_row["updated_at"]


@pytest.mark.parametrize(
    "field_name",
    [
        "trace_id",
        "correlation_id",
        "task_id",
        "claim_id",
        "idempotency_key",
        "causation_id",
        "parent_run_id",
        "agent_id",
        "session_id",
        "external_a2a_task_id",
        "message_id",
        "event_id",
        "artifact_id",
        "proposal_id",
    ],
)
def test_exact_execution_identity_sync_rejects_every_changed_field(
    tmp_path,
    field_name: str,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _verifier_identity()
    store.record_execution_identity_exact_sync(identity, source="verifier-source")
    altered = replace(identity, **{field_name: f"changed-{field_name}"})

    with pytest.raises(ValueError, match="conflicting exact execution identity"):
        store.record_execution_identity_exact_sync(
            altered,
            source="verifier-source",
        )

    assert store.get_execution_identity_sync(identity.run_id) == identity


@pytest.mark.parametrize("conflict", ["signer", "process_boot_id", "source"])
def test_exact_execution_identity_sync_rejects_authority_conflicts(
    tmp_path,
    conflict: str,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _verifier_identity()
    source = "governed_patch.vibe_verifier"
    store.record_execution_identity_exact_sync(identity, source=source)
    altered = identity
    altered_source = source
    if conflict == "signer":
        altered = _verifier_identity(signer_public_key="signer-key-two")
    elif conflict == "process_boot_id":
        altered = _verifier_identity(process_boot_id="boot-two")
    else:
        altered_source = "foreign.verifier"

    with pytest.raises(ValueError, match="conflicting exact execution identity"):
        store.record_execution_identity_exact_sync(
            altered,
            source=altered_source,
        )

    row = _exact_identity_row(store, identity.run_id)
    assert row["source"] == f"exact:{source}"
    assert json.loads(row["metadata_json"]) == identity.metadata


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["async", "sync"])
async def test_generic_identity_writer_cannot_overwrite_exact_row(
    tmp_path,
    surface: str,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _verifier_identity()
    store.record_execution_identity_exact_sync(identity, source="verifier-source")
    before = dict(_exact_identity_row(store, identity.run_id))
    altered_metadata = {"signer_public_key": "foreign", "process_boot_id": "foreign"}

    with pytest.raises(ValueError, match="reserved by the exact writer"):
        if surface == "async":
            await store.record_execution_identity(
                identity,
                source="generic-writer",
                metadata=altered_metadata,
            )
        else:
            store.record_execution_identity_sync(
                identity,
                source="generic-writer",
                metadata=altered_metadata,
            )

    assert dict(_exact_identity_row(store, identity.run_id)) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["async", "sync"])
async def test_generic_identity_writer_cannot_mint_exact_source_marker(
    tmp_path,
    surface: str,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _verifier_identity()

    with pytest.raises(ValueError, match="reserved marker"):
        if surface == "async":
            await store.record_execution_identity(identity, source="exact:foreign")
        else:
            store.record_execution_identity_sync(identity, source="exact:foreign")

    assert store.get_execution_identity_sync(identity.run_id) is None


@pytest.mark.asyncio
async def test_exact_execution_identity_sync_concurrent_replay_inserts_once(
    tmp_path,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    store.init_db_sync()
    identity = _verifier_identity()

    results = await asyncio.gather(
        *(
            asyncio.to_thread(
                RuntimeStateStore(
                    store.db_path,
                    include_memory_plane=False,
                ).record_execution_identity_exact_sync,
                identity,
                source="race.verifier",
            )
            for _ in range(12)
        ),
    )

    assert results == [identity] * 12
    with sqlite3.connect(store.db_path) as db:
        count = db.execute(
            "SELECT COUNT(*) FROM execution_identities WHERE run_id = ?",
            (identity.run_id,),
        ).fetchone()[0]
    assert count == 1


@pytest.mark.asyncio
async def test_exact_execution_identity_sync_conflicting_race_has_one_winner(
    tmp_path,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    store.init_db_sync()
    contenders = (
        _verifier_identity(signer_public_key="signer-key-one"),
        _verifier_identity(signer_public_key="signer-key-two"),
    )

    results = await asyncio.gather(
        *(
            asyncio.to_thread(
                RuntimeStateStore(
                    store.db_path,
                    include_memory_plane=False,
                ).record_execution_identity_exact_sync,
                contender,
                source="race.verifier",
            )
            for contender in contenders
        ),
        return_exceptions=True,
    )

    winners = [result for result in results if isinstance(result, ExecutionIdentity)]
    refusals = [result for result in results if isinstance(result, ValueError)]
    assert len(winners) == len(refusals) == 1
    persisted = store.get_execution_identity_sync(contenders[0].run_id)
    assert persisted == winners[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["proposal", "gate", "promote"])
async def test_exact_self_mod_happy_path_writes_one_attestation_pair(
    tmp_path,
    stage: str,
) -> None:
    store, identity = await _prepared_store(tmp_path)

    receipt = await store.commit_self_mod_receipt_exact(
        identity,
        stage=stage,
        proposal_id=identity.proposal_id,
        status="passed",
        payload={"forge_digest": "abc123", "scores": (1, 2, 3)},
    )

    side_effect_key = f"self_mod:{identity.proposal_id}:{stage}"
    assert receipt.receipt_id == _slot_receipt_id(identity.proposal_id, stage)
    assert receipt.receipt_type == f"self_mod_{stage}"
    assert receipt.side_effect_key == side_effect_key
    assert receipt.payload == {
        "schema_version": "dharma.runtime.self_mod_exact.v1",
        "authority_semantics": "attestation_only",
        "proposal_id": identity.proposal_id,
        "stage": stage,
        "evidence": {"forge_digest": "abc123", "scores": [1, 2, 3]},
        "operation_hash": receipt.payload["operation_hash"],
    }
    assert len(receipt.payload["operation_hash"]) == 64
    assert _pair_counts(store, side_effect_key) == (1, 1)

    with sqlite3.connect(store.db_path) as db:
        db.row_factory = sqlite3.Row
        idempotency = db.execute(
            "SELECT * FROM idempotency_records WHERE side_effect_key = ?",
            (side_effect_key,),
        ).fetchone()
        persisted_payload = db.execute(
            "SELECT payload_json FROM runtime_receipts WHERE receipt_id = ?",
            (receipt.receipt_id,),
        ).fetchone()[0]
    assert idempotency is not None
    metadata = json.loads(idempotency["metadata_json"])
    assert idempotency["status"] == "completed"
    assert idempotency["result_receipt_id"] == receipt.receipt_id
    assert idempotency["created_at"] == idempotency["updated_at"] == receipt.created_at.isoformat()
    assert metadata == {
        "schema_version": "dharma.runtime.self_mod_exact.v1",
        "authority_semantics": "attestation_only",
        "stage": stage,
        "proposal_id": identity.proposal_id,
        "receipt_id": receipt.receipt_id,
        "operation_hash": receipt.payload["operation_hash"],
    }
    assert persisted_payload == json.dumps(
        receipt.payload,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    )


@pytest.mark.asyncio
async def test_exact_self_mod_restart_replay_returns_original_receipt(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)
    first = await store.commit_self_mod_receipt_exact(
        identity,
        stage="proposal",
        proposal_id=identity.proposal_id,
        status="proposed",
        payload={"candidate_digest": "candidate-1"},
    )

    restarted = RuntimeStateStore(store.db_path, include_memory_plane=False)
    replay = await restarted.commit_self_mod_receipt_exact(
        identity,
        stage="proposal",
        proposal_id=identity.proposal_id,
        status="proposed",
        payload={"candidate_digest": "candidate-1"},
    )

    assert replay == first
    assert _pair_counts(store, first.side_effect_key) == (1, 1)


@pytest.mark.asyncio
async def test_exact_self_mod_concurrent_replay_creates_one_pair(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)

    receipts = await asyncio.gather(
        *(
            RuntimeStateStore(store.db_path, include_memory_plane=False).commit_self_mod_receipt_exact(
                identity,
                stage="proposal",
                proposal_id=identity.proposal_id,
                status="proposed",
                payload={"candidate_digest": "candidate-1"},
            )
            for _ in range(12)
        )
    )

    assert len({receipt.receipt_id for receipt in receipts}) == 1
    assert len({receipt.created_at for receipt in receipts}) == 1
    assert len({receipt.payload["operation_hash"] for receipt in receipts}) == 1
    assert _pair_counts(store, receipts[0].side_effect_key) == (1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["proposal", "gate"])
@pytest.mark.parametrize(
    ("status", "payload"),
    [
        ("rejected", {"verdict": "ship"}),
        ("passed", {"verdict": "halt"}),
    ],
)
async def test_conflicting_replay_fails_without_replacing_original(
    tmp_path,
    stage: str,
    status: str,
    payload: dict[str, str],
) -> None:
    store, identity = await _prepared_store(tmp_path)
    original = await store.commit_self_mod_receipt_exact(
        identity,
        stage=stage,
        proposal_id=identity.proposal_id,
        status="passed",
        payload={"verdict": "ship"},
    )

    with pytest.raises(ValueError, match="conflicting exact self-mod receipt"):
        await store.commit_self_mod_receipt_exact(
            identity,
            stage=stage,
            proposal_id=identity.proposal_id,
            status=status,
            payload=payload,
        )

    [persisted] = await store.list_runtime_receipts(
        receipt_type=f"self_mod_{stage}",
        limit=10,
    )
    assert persisted == original
    assert _pair_counts(store, original.side_effect_key) == (1, 1)


@pytest.mark.asyncio
async def test_cross_idempotency_key_collision_fails_closed(tmp_path) -> None:
    store, first_identity = await _prepared_store(tmp_path, suffix="first")
    first = await store.commit_self_mod_receipt_exact(
        first_identity,
        stage="promote",
        proposal_id=first_identity.proposal_id,
        status="passed",
        payload={"candidate": "same"},
    )
    second_identity = _identity("second", proposal_id=first_identity.proposal_id)
    await store.record_execution_identity(second_identity, source="exact-self-mod-test")

    with pytest.raises(ValueError, match="conflicting exact self-mod receipt"):
        await store.commit_self_mod_receipt_exact(
            second_identity,
            stage="promote",
            proposal_id=second_identity.proposal_id,
            status="passed",
            payload={"candidate": "same"},
        )

    assert _pair_counts(store, first.side_effect_key) == (1, 1)


@pytest.mark.asyncio
async def test_missing_identity_fails_closed(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    identity = _identity()

    with pytest.raises(MissingExecutionIdentity, match="already-durable"):
        await store.commit_self_mod_receipt_exact(
            identity,
            stage="gate",
            proposal_id=identity.proposal_id,
            status="passed",
            payload={},
        )

    assert _pair_counts(store, f"self_mod:{identity.proposal_id}:gate") == (0, 0)


@pytest.mark.asyncio
async def test_nonexact_identity_fails_closed(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)
    altered = replace(identity, agent_id="another-agent")

    with pytest.raises(MissingExecutionIdentity, match="does not exactly match"):
        await store.commit_self_mod_receipt_exact(
            altered,
            stage="gate",
            proposal_id=altered.proposal_id,
            status="passed",
            payload={},
        )

    assert _pair_counts(store, f"self_mod:{identity.proposal_id}:gate") == (0, 0)


@pytest.mark.asyncio
async def test_nonexact_identity_subclass_cannot_vary_between_validation_and_insert(
    tmp_path,
) -> None:
    store, identity = await _prepared_store(tmp_path)
    varying_identity = _VaryingExecutionIdentity(**identity.to_dict())
    side_effect_key = f"self_mod:{identity.proposal_id}:gate"

    with pytest.raises(MissingExecutionIdentity, match="exact ExecutionIdentity"):
        await store.commit_self_mod_receipt_exact(
            varying_identity,
            stage="gate",
            proposal_id=identity.proposal_id,
            status="passed",
            payload={},
        )

    assert _pair_counts(store, side_effect_key) == (0, 0)
    assert varying_identity.__dict__.get("_agent_reads") is None


@pytest.mark.asyncio
async def test_nonexact_identity_proposal_binding_fails_before_write(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)

    with pytest.raises(MissingExecutionIdentity, match="proposal_id must exactly match"):
        await store.commit_self_mod_receipt_exact(
            identity,
            stage="gate",
            proposal_id="another-proposal",
            status="passed",
            payload={},
        )

    assert _pair_counts(store, "self_mod:another-proposal:gate") == (0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["proposal", "gate"])
@pytest.mark.parametrize("missing_table", ["receipt", "idempotency"])
async def test_partial_state_fails_closed(
    tmp_path,
    missing_table: str,
    stage: str,
) -> None:
    store, identity = await _prepared_store(tmp_path)
    receipt = await store.commit_self_mod_receipt_exact(
        identity,
        stage=stage,
        proposal_id=identity.proposal_id,
        status="passed",
        payload={"verdict": "ship"},
    )
    with sqlite3.connect(store.db_path) as db:
        if missing_table == "receipt":
            db.execute("DELETE FROM runtime_receipts WHERE receipt_id = ?", (receipt.receipt_id,))
        else:
            db.execute(
                "DELETE FROM idempotency_records WHERE side_effect_key = ?",
                (receipt.side_effect_key,),
            )
        db.commit()

    with pytest.raises(ValueError, match="partial exact self-mod evidence state"):
        await store.commit_self_mod_receipt_exact(
            identity,
            stage=stage,
            proposal_id=identity.proposal_id,
            status="passed",
            payload={"verdict": "ship"},
        )

    assert _pair_counts(store, receipt.side_effect_key) in {(1, 0), (0, 1)}


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_status", ["started", "stale", "conflict", "random"])
async def test_stale_state_is_not_reclaimed_or_repaired(tmp_path, legacy_status: str) -> None:
    store, identity = await _prepared_store(tmp_path)
    side_effect_key = f"self_mod:{identity.proposal_id}:promote"
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO idempotency_records (idempotency_key, side_effect_key, run_id,"
            " task_id, trace_id, correlation_id, status, result_receipt_id, metadata_json,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, '', '{}', ?, ?)",
            (
                identity.idempotency_key,
                side_effect_key,
                identity.run_id,
                identity.task_id,
                identity.trace_id,
                identity.correlation_id,
                legacy_status,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        db.commit()

    with pytest.raises(ValueError, match="partial exact self-mod evidence state"):
        await store.commit_self_mod_receipt_exact(
            identity,
            stage="promote",
            proposal_id=identity.proposal_id,
            status="passed",
            payload={},
        )

    assert _pair_counts(store, side_effect_key) == (0, 1)


@pytest.mark.asyncio
async def test_random_legacy_receipt_id_is_a_collision(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)
    side_effect_key = f"self_mod:{identity.proposal_id}:gate"
    with sqlite3.connect(store.db_path) as db:
        now = "2026-01-01T00:00:00+00:00"
        db.execute(
            "INSERT INTO runtime_receipts (receipt_id, receipt_type, run_id, task_id,"
            " trace_id, correlation_id, causation_id, parent_run_id, agent_id,"
            " idempotency_key, side_effect_key, status, payload_json, created_at)"
            " VALUES ('rr-random', 'self_mod_gate', ?, ?, ?, ?, ?, ?, ?, ?, ?,"
            " 'passed', '{}', ?)",
            (
                identity.run_id,
                identity.task_id,
                identity.trace_id,
                identity.correlation_id,
                identity.causation_id,
                identity.parent_run_id,
                identity.agent_id,
                identity.idempotency_key,
                side_effect_key,
                now,
            ),
        )
        db.execute(
            "INSERT INTO idempotency_records (idempotency_key, side_effect_key, run_id,"
            " task_id, trace_id, correlation_id, status, result_receipt_id, metadata_json,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'completed',"
            " 'rr-random', '{}', ?, ?)",
            (
                identity.idempotency_key,
                side_effect_key,
                identity.run_id,
                identity.task_id,
                identity.trace_id,
                identity.correlation_id,
                now,
                now,
            ),
        )
        db.commit()

    with pytest.raises(ValueError, match="conflicting exact self-mod receipt"):
        await store.commit_self_mod_receipt_exact(
            identity,
            stage="gate",
            proposal_id=identity.proposal_id,
            status="passed",
            payload={},
        )

    assert _pair_counts(store, side_effect_key) == (1, 1)


@pytest.mark.asyncio
async def test_wrong_type_same_logical_slot_receipt_blocks_exact_writer(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)
    side_effect_key = f"self_mod:{identity.proposal_id}:gate"
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "INSERT INTO runtime_receipts (receipt_id, receipt_type, side_effect_key,"
            " status, payload_json, created_at) VALUES"
            " ('rr-wrong-type', 'artifact', ?, 'recorded', '{}', ?)",
            (side_effect_key, "2026-01-01T00:00:00+00:00"),
        )
        db.commit()

    with pytest.raises(ValueError, match="partial exact self-mod evidence state"):
        await store.commit_self_mod_receipt_exact(
            identity,
            stage="gate",
            proposal_id=identity.proposal_id,
            status="passed",
            payload={},
        )

    with sqlite3.connect(store.db_path) as db:
        receipt_ids = db.execute(
            "SELECT receipt_id FROM runtime_receipts WHERE side_effect_key = ?",
            (side_effect_key,),
        ).fetchall()
    assert receipt_ids == [("rr-wrong-type",)]
    assert _pair_counts(store, side_effect_key) == (1, 0)


@pytest.mark.asyncio
async def test_second_insert_rollback_removes_first_insert(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)
    side_effect_key = f"self_mod:{identity.proposal_id}:promote"
    with sqlite3.connect(store.db_path) as db:
        db.execute(
            "CREATE TRIGGER reject_exact_idempotency BEFORE INSERT ON idempotency_records"
            " WHEN NEW.side_effect_key = 'self_mod:proposal-exact:promote' BEGIN"
            " SELECT RAISE(ABORT, 'forced second insert failure'); END"
        )
        db.commit()

    with pytest.raises(sqlite3.IntegrityError, match="forced second insert failure"):
        await store.commit_self_mod_receipt_exact(
            identity,
            stage="promote",
            proposal_id=identity.proposal_id,
            status="passed",
            payload={"candidate": "one"},
        )

    assert _pair_counts(store, side_effect_key) == (0, 0)


def _reserved_receipt(identity: ExecutionIdentity, *, by_type: bool = True) -> RuntimeReceipt:
    return RuntimeReceipt(
        receipt_id="rr-generic-bypass",
        receipt_type="self_mod_gate" if by_type else "artifact",
        status="passed",
        run_id=identity.run_id,
        task_id=identity.task_id,
        trace_id=identity.trace_id,
        correlation_id=identity.correlation_id,
        idempotency_key=identity.idempotency_key,
        side_effect_key=(
            "artifact:ordinary"
            if by_type
            else f"self_mod:{identity.proposal_id}:promote"
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("by_type", [True, False])
async def test_generic_writer_rejects_reserved_type_or_logical_slot(tmp_path, by_type: bool) -> None:
    store, identity = await _prepared_store(tmp_path)
    receipt = _reserved_receipt(identity, by_type=by_type)

    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.record_runtime_receipt(receipt)
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.record_runtime_receipt_sync(receipt)
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.build_runtime_receipt(
            identity,
            receipt_type=receipt.receipt_type,
            status="passed",
            side_effect_key=receipt.side_effect_key,
        )
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.record_receipt_for_identity(
            identity,
            receipt_type=receipt.receipt_type,
            status="passed",
            side_effect_key=receipt.side_effect_key,
        )
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.record_receipt_for_identity_sync(
            identity,
            receipt_type=receipt.receipt_type,
            status="passed",
            side_effect_key=receipt.side_effect_key,
        )

    assert _pair_counts(store, receipt.side_effect_key) == (0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("disguised_field", ["receipt_id", "receipt_type", "side_effect_key"])
async def test_generic_writer_rejects_disguised_str_subclass(
    tmp_path,
    disguised_field: str,
) -> None:
    store, identity = await _prepared_store(tmp_path)
    receipt = RuntimeReceipt(
        receipt_id=(
            _DisguisedStr("rr_self_mod_exact_disguised")
            if disguised_field == "receipt_id"
            else f"rr-disguised-{disguised_field}"
        ),
        receipt_type=(
            _DisguisedStr("self_mod_gate")
            if disguised_field == "receipt_type"
            else "artifact"
        ),
        side_effect_key=(
            _DisguisedStr(f"self_mod:{identity.proposal_id}:promote")
            if disguised_field == "side_effect_key"
            else "artifact:ordinary"
        ),
        status="recorded",
    )

    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.record_runtime_receipt(receipt)
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.record_runtime_receipt_sync(receipt)
    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM runtime_receipts WHERE receipt_id = ?",
            (receipt.receipt_id,),
        ).fetchone()[0] == 0


@pytest.mark.asyncio
async def test_generic_async_and_sync_sinks_reject_varying_receipt_subclass(tmp_path) -> None:
    store, _identity_value = await _prepared_store(tmp_path)
    receipt = _VaryingRuntimeReceipt(
        receipt_id="rr-varying-generic",
        receipt_type="artifact",
        side_effect_key="artifact:ordinary",
        status="recorded",
    )

    with pytest.raises(TypeError, match="exact RuntimeReceipt"):
        await store.record_runtime_receipt(receipt)
    with pytest.raises(TypeError, match="exact RuntimeReceipt"):
        store.record_runtime_receipt_sync(receipt)

    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM runtime_receipts WHERE receipt_id = ?",
            (receipt.receipt_id,),
        ).fetchone()[0] == 0
    assert receipt.__dict__.get("_varying_reads") is None


@pytest.mark.asyncio
async def test_generic_writer_cannot_replace_exact_pair_by_receipt_id(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)
    original = await store.commit_self_mod_receipt_exact(
        identity,
        stage="gate",
        proposal_id=identity.proposal_id,
        status="passed",
        payload={"verdict": "ship"},
    )
    replacement = RuntimeReceipt(
        receipt_id=original.receipt_id,
        receipt_type="artifact",
        side_effect_key="artifact:ordinary",
        status="recorded",
        payload={"replacement": True},
    )

    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.record_runtime_receipt(replacement)
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.record_runtime_receipt_sync(replacement)
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.build_runtime_receipt(
            identity,
            receipt_id=original.receipt_id,
            receipt_type="artifact",
            side_effect_key="artifact:ordinary",
            status="recorded",
        )
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.record_receipt_for_identity(
            identity,
            receipt_id=original.receipt_id,
            receipt_type="artifact",
            side_effect_key="artifact:ordinary",
            status="recorded",
        )
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.record_receipt_for_identity_sync(
            identity,
            receipt_id=original.receipt_id,
            receipt_type="artifact",
            side_effect_key="artifact:ordinary",
            status="recorded",
        )

    replay = await store.commit_self_mod_receipt_exact(
        identity,
        stage="gate",
        proposal_id=identity.proposal_id,
        status="passed",
        payload={"verdict": "ship"},
    )
    assert replay == original
    assert _pair_counts(store, original.side_effect_key) == (1, 1)
    assert _pair_counts(store, replacement.side_effect_key) == (0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage",
    [
        "proposal",
        "self_mod_proposal",
        "gate",
        "self_mod_gate",
        "promote",
        "self_mod_promote",
    ],
)
async def test_generic_writer_legacy_self_mod_rejects_reserved_stages(tmp_path, stage: str) -> None:
    store, identity = await _prepared_store(tmp_path)

    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.record_self_mod_receipt(
            identity,
            stage=stage,
            status="passed",
            proposal_id=identity.proposal_id,
        )
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.record_self_mod_receipt_sync(
            identity,
            stage=stage,
            status="passed",
            proposal_id=identity.proposal_id,
        )


@pytest.mark.asyncio
async def test_combined_event_writer_rejects_reserved_receipt_without_event(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)
    receipt = _reserved_receipt(identity)
    event = SessionEventRecord(
        event_id="event-combined-bypass",
        session_id=identity.session_id,
        ledger_kind="test",
        event_name="combined_bypass",
    )

    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.record_session_event(event, receipt)
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.record_session_event_with_runtime_receipt(event, receipt)
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.record_session_event_with_runtime_receipt_sync(event, receipt)

    with sqlite3.connect(store.db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM session_events WHERE event_id = ?",
            (event.event_id,),
        ).fetchone()[0] == 0


@pytest.mark.asyncio
async def test_combined_event_sinks_reject_varying_receipt_subclass_without_writes(
    tmp_path,
) -> None:
    store, identity = await _prepared_store(tmp_path)
    receipt = _VaryingRuntimeReceipt(
        receipt_id="rr-varying-combined",
        receipt_type="artifact",
        side_effect_key="artifact:ordinary",
        status="recorded",
    )
    events = [
        SessionEventRecord(
            event_id=f"event-varying-{index}",
            session_id=identity.session_id,
            ledger_kind="test",
            event_name="varying_receipt",
        )
        for index in range(3)
    ]

    with pytest.raises(TypeError, match="exact RuntimeReceipt"):
        await store.record_session_event(events[0], receipt)
    with pytest.raises(TypeError, match="exact RuntimeReceipt"):
        await store.record_session_event_with_runtime_receipt(events[1], receipt)
    with pytest.raises(TypeError, match="exact RuntimeReceipt"):
        store.record_session_event_with_runtime_receipt_sync(events[2], receipt)

    with sqlite3.connect(store.db_path) as db:
        event_count = db.execute(
            "SELECT COUNT(*) FROM session_events WHERE event_id LIKE 'event-varying-%'"
        ).fetchone()[0]
        receipt_count = db.execute(
            "SELECT COUNT(*) FROM runtime_receipts WHERE receipt_id = ?",
            (receipt.receipt_id,),
        ).fetchone()[0]
    assert (event_count, receipt_count) == (0, 0)
    assert receipt.__dict__.get("_varying_reads") is None


@pytest.mark.asyncio
async def test_combined_event_sinks_cannot_replace_exact_pair_by_receipt_id(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)
    original = await store.commit_self_mod_receipt_exact(
        identity,
        stage="promote",
        proposal_id=identity.proposal_id,
        status="passed",
        payload={"candidate": "one"},
    )
    replacement = RuntimeReceipt(
        receipt_id=original.receipt_id,
        receipt_type="artifact",
        side_effect_key="artifact:ordinary",
        status="recorded",
    )
    events = [
        SessionEventRecord(
            event_id=f"event-replace-{index}",
            session_id=identity.session_id,
            ledger_kind="test",
            event_name="replace_exact_receipt",
        )
        for index in range(3)
    ]

    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.record_session_event(events[0], replacement)
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.record_session_event_with_runtime_receipt(events[1], replacement)
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.record_session_event_with_runtime_receipt_sync(events[2], replacement)

    replay = await store.commit_self_mod_receipt_exact(
        identity,
        stage="promote",
        proposal_id=identity.proposal_id,
        status="passed",
        payload={"candidate": "one"},
    )
    with sqlite3.connect(store.db_path) as db:
        event_count = db.execute(
            "SELECT COUNT(*) FROM session_events WHERE event_id LIKE 'event-replace-%'"
        ).fetchone()[0]
    assert replay == original
    assert event_count == 0
    assert _pair_counts(store, original.side_effect_key) == (1, 1)
    assert _pair_counts(store, replacement.side_effect_key) == (0, 0)


@pytest.mark.asyncio
async def test_generic_idempotency_leaves_reject_reserved_slot(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)
    side_effect_key = f"self_mod:{identity.proposal_id}:gate"

    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.try_begin_idempotent_side_effect(identity, side_effect_key)
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.try_begin_idempotent_side_effect_with_token(identity, side_effect_key)
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.try_begin_idempotent_side_effect_sync(identity, side_effect_key)
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.complete_idempotent_side_effect(identity, side_effect_key)
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.complete_idempotent_side_effect_sync(identity, side_effect_key)
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.try_reclaim_idempotent_side_effect(
            identity,
            side_effect_key,
            expected_status="stale",
        )
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.try_reclaim_idempotent_side_effect_with_token(
            identity,
            side_effect_key,
            expected_status="stale",
        )

    assert _pair_counts(store, side_effect_key) == (0, 0)


@pytest.mark.asyncio
async def test_generic_idempotency_rejects_disguised_side_effect_key(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)
    side_effect_key = _DisguisedStr(f"self_mod:{identity.proposal_id}:gate")

    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.try_begin_idempotent_side_effect(identity, side_effect_key)
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.try_begin_idempotent_side_effect_with_token(identity, side_effect_key)
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.try_begin_idempotent_side_effect_sync(identity, side_effect_key)
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.complete_idempotent_side_effect(identity, side_effect_key)
    with pytest.raises(ValueError, match="reserved self-mod"):
        store.complete_idempotent_side_effect_sync(identity, side_effect_key)
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.try_reclaim_idempotent_side_effect(
            identity,
            side_effect_key,
            expected_status="stale",
        )
    with pytest.raises(ValueError, match="reserved self-mod"):
        await store.try_reclaim_idempotent_side_effect_with_token(
            identity,
            side_effect_key,
            expected_status="stale",
        )

    assert _pair_counts(store, side_effect_key) == (0, 0)


@pytest.mark.asyncio
async def test_other_self_mod_stages_and_slots_remain_compatible(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)

    for stage in ("apply", "verify", "revert"):
        async_receipt = await store.record_self_mod_receipt(
            identity,
            stage=stage,
            status="recorded",
            proposal_id=identity.proposal_id,
        )
        sync_receipt = store.record_self_mod_receipt_sync(
            identity,
            stage=stage,
            status="recorded-sync",
            proposal_id=identity.proposal_id,
        )
        assert async_receipt.receipt_type == f"self_mod_{stage}"
        assert sync_receipt.receipt_type == f"self_mod_{stage}"

    apply_key = f"self_mod:{identity.proposal_id}:apply"
    assert await store.try_begin_idempotent_side_effect(identity, apply_key) is True
    completed = await store.complete_idempotent_side_effect(identity, apply_key)
    assert completed.status == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_payload",
    [
        {1: "non-string-key"},
        {"nested": {1: "non-string-key"}},
        {"number": float("nan")},
        {"number": float("inf")},
        {"number": float("-inf")},
        {"unsupported": {"set-value"}},
    ],
)
async def test_json_ambiguity_or_nonfinite_rejected_before_database_init(
    tmp_path,
    bad_payload,
) -> None:
    db_path = tmp_path / "runtime.db"
    store = RuntimeStateStore(db_path, include_memory_plane=False)
    identity = _identity()

    with pytest.raises(ValueError):
        await store.commit_self_mod_receipt_exact(
            identity,
            stage="gate",
            proposal_id=identity.proposal_id,
            status="passed",
            payload=bad_payload,
        )

    assert not db_path.exists()


@pytest.mark.asyncio
async def test_duplicate_rendering_string_subclass_keys_rejected_before_database_init(
    tmp_path,
) -> None:
    db_path = tmp_path / "runtime.db"
    store = RuntimeStateStore(db_path, include_memory_plane=False)
    identity = _identity()
    payload = {
        _DuplicateLookingKey("first"): 1,
        _DuplicateLookingKey("second"): 2,
    }
    assert len(payload) == 2

    with pytest.raises(ValueError, match="string object keys"):
        await store.commit_self_mod_receipt_exact(
            identity,
            stage="gate",
            proposal_id=identity.proposal_id,
            status="passed",
            payload=payload,
        )

    assert not db_path.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scalar",
    [_DisguisedStr("value"), _ScalarInt(1), _ScalarFloat(1.5)],
)
async def test_json_scalar_subclasses_rejected_before_database_init(
    tmp_path,
    scalar,
) -> None:
    db_path = tmp_path / "runtime.db"
    store = RuntimeStateStore(db_path, include_memory_plane=False)
    identity = _identity()

    with pytest.raises(ValueError, match="non-JSON value"):
        await store.commit_self_mod_receipt_exact(
            identity,
            stage="gate",
            proposal_id=identity.proposal_id,
            status="passed",
            payload={"scalar": scalar},
        )

    assert not db_path.exists()


@pytest.mark.asyncio
async def test_tuple_and_list_payloads_have_one_canonical_replay(tmp_path) -> None:
    store, identity = await _prepared_store(tmp_path)
    first = await store.commit_self_mod_receipt_exact(
        identity,
        stage="gate",
        proposal_id=identity.proposal_id,
        status="passed",
        payload=_CustomMapping({"items": ("one", {"nested": (2, 3)})}),
    )
    replay = await store.commit_self_mod_receipt_exact(
        identity,
        stage="gate",
        proposal_id=identity.proposal_id,
        status="passed",
        payload={"items": ["one", {"nested": [2, 3]}]},
    )

    assert replay == first
    assert replay.payload["evidence"] == {"items": ["one", {"nested": [2, 3]}]}
