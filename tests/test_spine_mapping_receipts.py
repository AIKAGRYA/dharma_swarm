from __future__ import annotations

import pytest

from dharma_swarm.runtime_state import (
    MAPPING_ID_KINDS,
    RUNTIME_RECEIPT_TYPES,
    RuntimeStateStore,
)
from dharma_swarm.spine.identity import ExecutionIdentity


def _identity() -> ExecutionIdentity:
    return ExecutionIdentity.new(
        task_id="task-map",
        run_id="run-map",
        trace_id="trace-map",
        correlation_id="corr-map",
        claim_id="claim-map",
        idempotency_key="idem-map",
        agent_id="agent-map",
        parent_run_id="run-parent",
    )


@pytest.mark.asyncio
async def test_record_mapping_receipts_cover_slice_c_external_ids(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()
    mappings = {
        "workflow_id": "workflow-map-1",
        "proposal_id": "proposal-map-1",
        "event_id": "event-map-1",
        "message_id": "message-map-1",
        "ontology_action_id": "ontology-action-map-1",
        "engine_artifact_id": "engine-artifact-map-1",
    }

    for id_kind, external_id in mappings.items():
        await store.record_mapping_receipt(
            identity,
            id_kind=id_kind,
            external_id=external_id,
            source=f"slice-c:{id_kind}",
            payload={"surface": id_kind},
        )

    ledger = await store.get_run_ledger(identity.run_id)
    receipts = ledger["mappings"]
    by_kind = {receipt.payload["id_kind"]: receipt for receipt in receipts}

    assert set(mappings) == MAPPING_ID_KINDS
    assert "identity_mapping" in RUNTIME_RECEIPT_TYPES
    assert set(by_kind) == set(mappings)
    for id_kind, external_id in mappings.items():
        receipt = by_kind[id_kind]
        assert receipt.receipt_type == "identity_mapping"
        assert receipt.run_id == identity.run_id
        assert receipt.task_id == identity.task_id
        assert receipt.trace_id == identity.trace_id
        assert receipt.correlation_id == identity.correlation_id
        assert receipt.parent_run_id == identity.parent_run_id
        assert receipt.idempotency_key == identity.idempotency_key
        assert receipt.side_effect_key == f"mapping:{id_kind}:{external_id}"
        assert receipt.payload["external_id"] == external_id
        assert receipt.payload["source"] == f"slice-c:{id_kind}"
        assert receipt.payload["surface"] == id_kind


@pytest.mark.asyncio
async def test_mapping_receipts_are_idempotent_per_run_kind_and_external_id(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()

    first = await store.record_mapping_receipt(
        identity,
        id_kind="workflow_id",
        external_id="workflow-repeat",
        payload={"attempt": 1},
    )
    duplicate = await store.record_mapping_receipt(
        identity,
        id_kind="workflow_id",
        external_id="workflow-repeat",
        payload={"attempt": 2},
    )
    receipts = await store.list_mapping_receipts(
        run_id=identity.run_id,
        id_kind="workflow_id",
        external_id="workflow-repeat",
        limit=10,
    )

    assert first.receipt_id == duplicate.receipt_id
    assert len(receipts) == 1
    assert receipts[0].payload["attempt"] == 2


@pytest.mark.asyncio
async def test_mapping_lookup_returns_run_id_for_each_slice_c_surface(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()

    await store.record_mapping_receipt(
        identity,
        id_kind="proposal_id",
        external_id="proposal-before-event",
    )
    await store.record_mapping_receipt(
        identity,
        id_kind="event_id",
        external_id="event-find",
    )
    store.record_mapping_receipt_sync(
        identity,
        id_kind="engine_artifact_id",
        external_id="engine-artifact-find",
    )

    assert (
        await store.find_run_id_by_mapping("event_id", "event-find")
        == identity.run_id
    )
    assert (
        store.find_run_id_by_mapping_sync(
            "engine_artifact_id",
            "engine-artifact-find",
        )
        == identity.run_id
    )
    event_receipts = await store.list_mapping_receipts(id_kind="event_id", limit=1)
    assert len(event_receipts) == 1
    assert event_receipts[0].payload["external_id"] == "event-find"


@pytest.mark.asyncio
async def test_mapping_receipts_update_identity_optional_fields_without_losing_run_mapping(
    tmp_path,
) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()

    await store.record_mapping_receipt(
        identity,
        id_kind="proposal_id",
        external_id="proposal-canonical",
    )
    await store.record_mapping_receipt(
        identity,
        id_kind="message_id",
        external_id="message-canonical",
    )
    await store.record_mapping_receipt(
        identity,
        id_kind="engine_artifact_id",
        external_id="artifact-canonical",
    )

    loaded = await store.get_execution_identity(identity.run_id)
    assert loaded is not None
    assert loaded.proposal_id == "proposal-canonical"
    assert loaded.message_id == "message-canonical"
    assert loaded.artifact_id == "artifact-canonical"
    assert (
        await store.find_run_id_by_mapping("proposal_id", "proposal-canonical")
        == identity.run_id
    )


@pytest.mark.asyncio
async def test_mapping_receipts_reject_unknown_or_empty_ids(tmp_path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime.db")
    identity = _identity()

    with pytest.raises(ValueError, match="unknown runtime identity mapping kind"):
        await store.record_mapping_receipt(
            identity,
            id_kind="thread_id",
            external_id="thread-1",
        )

    with pytest.raises(ValueError, match="external_id is required"):
        await store.record_mapping_receipt(
            identity,
            id_kind="workflow_id",
            external_id=" ",
        )

    with pytest.raises(ValueError, match="external_id is required"):
        await store.find_run_id_by_mapping("workflow_id", "")

    with pytest.raises(ValueError, match="id_kind is required"):
        await store.list_mapping_receipts(external_id="workflow-1")
