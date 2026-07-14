"""Tests for durable NATS fleet-heartbeat projection."""

from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.a2a.agent_card import AgentCard, CardRegistry
from dharma_swarm.a2a.agent_directory import AgentDirectory
from dharma_swarm.a2a.node_registry import NodeRegistry, RemoteNode
from dharma_swarm.runtime_state import RuntimeStateStore


DEVIN_UID = "devin-roaming-2987d222"
HEARTBEAT_AT = "2026-07-14T15:30:00+00:00"


class _FakeMessage:
    def __init__(
        self,
        data: bytes,
        *,
        fail_ack: bool = False,
        fail_nak: bool = False,
    ) -> None:
        self.data = data
        self.fail_ack = fail_ack
        self.fail_nak = fail_nak
        self.acked = 0
        self.nacked = 0

    async def ack(self) -> None:
        if self.fail_ack:
            raise RuntimeError("broker ack failed")
        self.acked += 1

    async def nak(self) -> None:
        if self.fail_nak:
            raise RuntimeError("broker nak failed")
        self.nacked += 1


class _CountingNodeRegistry(NodeRegistry):
    def __init__(self, nodes_path: Path) -> None:
        super().__init__(nodes_path=nodes_path)
        self.heartbeat_writes = 0

    def record_heartbeat(self, node_id: str, **kwargs: Any) -> RemoteNode:
        previous = self.get(node_id)
        result = super().record_heartbeat(node_id, **kwargs)
        if result is not previous:
            self.heartbeat_writes += 1
        return result


class _FailAfterNodeRuntime(RuntimeStateStore):
    async def record_receipt_for_identity(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if (
            kwargs.get("receipt_type") == "fleet_presence_attempt"
            and kwargs.get("status") == "prepared"
        ):
            raise RuntimeError("runtime receipt failed after node persistence")
        return await super().record_receipt_for_identity(*args, **kwargs)


class _NewerHeartbeatThenFailRuntime(RuntimeStateStore):
    def __init__(self, db_path: Path, nodes: NodeRegistry) -> None:
        super().__init__(db_path)
        self.nodes = nodes

    async def record_receipt_for_identity(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if (
            kwargs.get("receipt_type") == "fleet_presence_attempt"
            and kwargs.get("status") == "prepared"
        ):
            self.nodes.record_heartbeat(
                "devin",
                last_heartbeat="2026-07-14T15:31:00+00:00",
                status="degraded",
                metadata={
                    "agent_uid": DEVIN_UID,
                    "presence_message_id": "presence_newer",
                },
                canonical_agent_uid=DEVIN_UID,
            )
            raise RuntimeError("runtime failed after a newer heartbeat arrived")
        return await super().record_receipt_for_identity(*args, **kwargs)


class _ReclaimBeforeCompletionRuntime(RuntimeStateStore):
    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path)
        self.raced = False
        self.reclaimed_identity: Any = None
        self.reclaim_token: Any = None

    async def record_receipt_for_identity(
        self,
        identity: Any,
        **kwargs: Any,
    ) -> Any:
        receipt = await super().record_receipt_for_identity(identity, **kwargs)
        if (
            not self.raced
            and kwargs.get("receipt_type") == "fleet_presence_attempt"
            and kwargs.get("status") == "prepared"
        ):
            self.raced = True
            side_effect_key = str(kwargs["side_effect_key"])
            owned = await self.get_idempotency_record(
                identity.idempotency_key,
                side_effect_key,
            )
            assert owned is not None
            await self.complete_idempotent_side_effect(
                identity,
                side_effect_key,
                status="failed",
                expected_updated_at=owned.updated_at,
            )
            failed = await self.get_idempotency_record(
                identity.idempotency_key,
                side_effect_key,
            )
            assert failed is not None
            self.reclaimed_identity = identity.with_updates(
                run_id=f"{identity.run_id}-reclaimed",
                claim_id=f"{identity.claim_id}-reclaimed",
            )
            self.reclaim_token = (
                await self.try_reclaim_idempotent_side_effect_with_token(
                    self.reclaimed_identity,
                    side_effect_key,
                    expected_status="failed",
                    expected_updated_at=failed.updated_at,
                )
            )
            assert self.reclaim_token is not None
        return receipt


class _AmbiguousPostCasRuntime(RuntimeStateStore):
    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path)
        self.fail_completion_receipt = True
        self.fail_reconciliation_read = False

    async def record_side_effect_complete(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if (
            self.fail_completion_receipt
            and kwargs.get("status", "completed") == "completed"
        ):
            self.fail_completion_receipt = False
            self.fail_reconciliation_read = True
            raise RuntimeError("completion receipt failed after CAS commit")
        return await super().record_side_effect_complete(*args, **kwargs)

    async def get_idempotency_record(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if self.fail_reconciliation_read:
            self.fail_reconciliation_read = False
            raise RuntimeError("reconciliation read failed")
        return await super().get_idempotency_record(*args, **kwargs)


class _InspectingAckMessage(_FakeMessage):
    def __init__(
        self,
        data: bytes,
        *,
        nodes_path: Path,
        runtime_state: RuntimeStateStore,
    ) -> None:
        super().__init__(data)
        self._nodes_path = nodes_path
        self._runtime_state = runtime_state

    async def ack(self) -> None:
        persisted = json.loads(self._nodes_path.read_text(encoding="utf-8"))
        assert persisted[0]["last_heartbeat"] == HEARTBEAT_AT
        receipts = await self._runtime_state.list_runtime_receipts(
            receipt_type="fleet_presence_attempt"
        )
        prepared = [receipt for receipt in receipts if receipt.status == "prepared"]
        assert len(prepared) == 1
        record = await self._runtime_state.get_idempotency_record(
            prepared[0].idempotency_key,
            prepared[0].side_effect_key,
        )
        assert record is not None
        assert record.status == "completed"
        await super().ack()


def _fleet_presence_module() -> Any:
    try:
        return importlib.import_module("dharma_swarm.a2a.fleet_presence")
    except ModuleNotFoundError:
        pytest.fail("fleet presence projector is not implemented")


def _card_registry(tmp_path: Path, *, include_hermes: bool = False) -> CardRegistry:
    cards = CardRegistry(cards_dir=tmp_path / "cards")
    cards.register(AgentCard(name="devin", agent_uid=DEVIN_UID, status="idle"))
    if include_hermes:
        cards.register(AgentCard(name="hermes", agent_uid="hermes-m5", status="idle"))
    return cards


def _legacy_heartbeat(
    *,
    sender: str = "devin",
    agent_uid: str = DEVIN_UID,
    packet_id: str = "devin-hb-001",
) -> bytes:
    return json.dumps(
        {
            "schema_version": "dharma.a2a.send.v1",
            "packet_id": packet_id,
            "timestamp": HEARTBEAT_AT,
            "from": sender,
            "to": "fleet",
            "kind": "heartbeat",
            "route": "a2a",
            "subject": "dharma.a2a.fleet",
            "content": json.dumps(
                {
                    "agent_uid": agent_uid,
                    "status": "online",
                    "messages_received": 7,
                    "uptime_s": 123.5,
                }
            ),
        },
        sort_keys=True,
    ).encode("utf-8")


def _canonical_heartbeat(
    *,
    sender: str = "devin",
    agent_uid: str = DEVIN_UID,
    message_id: str = "fleet-heartbeat-001",
) -> bytes:
    return json.dumps(
        {
            "schema": "dharma.nats.envelope.v1",
            "message_id": message_id,
            "subject": "dharma.a2a.fleet",
            "from_agent": sender,
            "to_agent": "fleet",
            "actor": {"from_agent": sender, "to_agent": "fleet"},
            "kind": "heartbeat",
            "created_at": HEARTBEAT_AT,
            "requires_ack": True,
            "payload": {
                "schema": "dharma.a2a.fleet_heartbeat.v1",
                "agent_uid": agent_uid,
                "status": "online",
                "metadata": {"load": 0.25, "active_tasks": 2},
            },
        },
        sort_keys=True,
    ).encode("utf-8")


def _projector(
    tmp_path: Path,
    *,
    cards: CardRegistry | None = None,
    nodes: NodeRegistry | None = None,
    runtime_state: RuntimeStateStore | None = None,
) -> Any:
    fleet_presence = _fleet_presence_module()
    return fleet_presence.FleetPresenceProjector(
        card_registry=cards or _card_registry(tmp_path),
        node_registry=nodes or NodeRegistry(nodes_path=tmp_path / "nodes.json"),
        runtime_state=runtime_state or RuntimeStateStore(tmp_path / "runtime.db"),
    )


def test_node_registry_record_heartbeat_updates_existing_node_and_persists(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nodes.json"
    registry = NodeRegistry(nodes_path=path)
    registry.register(
        RemoteNode(
            node_id="devin",
            status="unknown",
            metadata={"agent_uid": DEVIN_UID, "preserved": True},
        )
    )

    node = registry.record_heartbeat(
        "devin",
        last_heartbeat=HEARTBEAT_AT,
        status="online",
        metadata={"messages_received": 7},
        canonical_agent_uid=DEVIN_UID,
    )

    assert node.last_heartbeat == HEARTBEAT_AT
    assert node.status == "online"
    assert node.metadata["preserved"] is True
    assert node.metadata["messages_received"] == 7
    reloaded = NodeRegistry(nodes_path=path).get("devin")
    assert reloaded is not None
    assert reloaded.last_heartbeat == HEARTBEAT_AT
    assert reloaded.metadata["agent_uid"] == DEVIN_UID


@pytest.mark.asyncio
async def test_valid_legacy_heartbeat_updates_registered_node(tmp_path: Path) -> None:
    cards = _card_registry(tmp_path)
    nodes = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    nodes.register(
        RemoteNode(
            node_id="devin",
            status="unknown",
            metadata={"agent_uid": DEVIN_UID},
        )
    )
    message = _FakeMessage(_legacy_heartbeat())

    result = await _projector(tmp_path, cards=cards, nodes=nodes).consume_message(
        message
    )

    assert result.status == "projected"
    assert result.agent_uid == DEVIN_UID
    assert message.acked == 1
    assert message.nacked == 0
    node = nodes.get("devin")
    assert node is not None
    assert node.status == "online"
    assert node.last_heartbeat == HEARTBEAT_AT
    assert node.metadata["messages_received"] == 7


@pytest.mark.asyncio
async def test_valid_canonical_heartbeat_projects_card_resolved_node(
    tmp_path: Path,
) -> None:
    cards = _card_registry(tmp_path)
    nodes = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    message = _FakeMessage(_canonical_heartbeat())

    result = await _projector(tmp_path, cards=cards, nodes=nodes).consume_message(
        message
    )

    assert result.status == "projected"
    assert message.acked == 1
    node = nodes.get("devin")
    assert node is not None
    assert node.metadata["agent_uid"] == DEVIN_UID
    assert node.metadata["load"] == 0.25


@pytest.mark.asyncio
async def test_sender_uid_mismatch_is_nacked_without_registry_pollution(
    tmp_path: Path,
) -> None:
    fleet_presence = _fleet_presence_module()
    cards = _card_registry(tmp_path, include_hermes=True)
    nodes = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    message = _FakeMessage(_canonical_heartbeat(agent_uid="hermes-m5"))

    with pytest.raises(fleet_presence.FleetPresenceError, match="mismatch"):
        await _projector(tmp_path, cards=cards, nodes=nodes).consume_message(message)

    assert message.acked == 0
    assert message.nacked == 1
    assert nodes.count() == 0


@pytest.mark.asyncio
async def test_unknown_identity_is_nacked_without_registry_pollution(
    tmp_path: Path,
) -> None:
    fleet_presence = _fleet_presence_module()
    cards = CardRegistry(cards_dir=tmp_path / "cards")
    nodes = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    message = _FakeMessage(
        _canonical_heartbeat(sender="intruder", agent_uid="intruder-agent")
    )

    with pytest.raises(fleet_presence.FleetPresenceError, match="unknown"):
        await _projector(tmp_path, cards=cards, nodes=nodes).consume_message(message)

    assert message.acked == 0
    assert message.nacked == 1
    assert nodes.count() == 0


@pytest.mark.asyncio
async def test_duplicate_delivery_acks_without_repeating_node_persistence(
    tmp_path: Path,
) -> None:
    runtime_state = RuntimeStateStore(tmp_path / "runtime.db")
    nodes = _CountingNodeRegistry(tmp_path / "nodes.json")
    projector = _projector(
        tmp_path,
        nodes=nodes,
        runtime_state=runtime_state,
    )
    first = _FakeMessage(_legacy_heartbeat())
    duplicate = _FakeMessage(_legacy_heartbeat())

    first_result = await projector.consume_message(first)
    duplicate_result = await projector.consume_message(duplicate)

    assert first_result.status == "projected"
    assert duplicate_result.status == "duplicate"
    assert duplicate_result.duplicate is True
    assert nodes.heartbeat_writes == 1
    assert first.acked == duplicate.acked == 1
    receipts = await runtime_state.list_runtime_receipts(
        receipt_type="fleet_presence_attempt"
    )
    assert [receipt.status for receipt in receipts] == ["prepared"]


@pytest.mark.asyncio
async def test_in_progress_delivery_naks_without_overwriting_owner_record(
    tmp_path: Path,
) -> None:
    fleet_presence = _fleet_presence_module()
    data = _legacy_heartbeat()
    heartbeat = fleet_presence.parse_fleet_heartbeat(data)
    identity = fleet_presence._execution_identity(heartbeat, DEVIN_UID)
    side_effect_key = f"fleet_presence:{DEVIN_UID}:{heartbeat.message_id}"
    runtime_state = RuntimeStateStore(tmp_path / "runtime.db")
    await runtime_state.record_execution_identity(identity, source="test")
    assert await runtime_state.try_begin_idempotent_side_effect(
        identity,
        side_effect_key,
        metadata={"owner": "first-delivery"},
    )
    nodes = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    message = _FakeMessage(data)

    with pytest.raises(fleet_presence.FleetPresenceError, match="in progress"):
        await _projector(
            tmp_path,
            nodes=nodes,
            runtime_state=runtime_state,
        ).consume_message(message)

    record = await runtime_state.get_idempotency_record(
        identity.idempotency_key,
        side_effect_key,
    )
    assert record is not None
    assert record.status == "started"
    assert message.acked == 0
    assert message.nacked == 1
    assert nodes.count() == 0


@pytest.mark.asyncio
async def test_reclaimed_owner_blocks_stale_original_completion(tmp_path: Path) -> None:
    fleet_presence = _fleet_presence_module()
    runtime_state = _ReclaimBeforeCompletionRuntime(tmp_path / "runtime.db")
    nodes = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    message = _FakeMessage(_legacy_heartbeat())

    with pytest.raises(fleet_presence.FleetPresenceError, match="lease lost"):
        await _projector(
            tmp_path,
            nodes=nodes,
            runtime_state=runtime_state,
        ).consume_message(message)

    assert runtime_state.reclaimed_identity is not None
    heartbeat = fleet_presence.parse_fleet_heartbeat(message.data)
    side_effect_key = f"fleet_presence:{DEVIN_UID}:{heartbeat.message_id}"
    record = await runtime_state.get_idempotency_record(
        runtime_state.reclaimed_identity.idempotency_key,
        side_effect_key,
    )
    assert record is not None
    assert record.status == "started"
    assert record.run_id == runtime_state.reclaimed_identity.run_id
    assert record.updated_at == runtime_state.reclaim_token
    receipts = await runtime_state.list_runtime_receipts(
        receipt_type="fleet_presence",
    )
    assert [receipt for receipt in receipts if receipt.status == "projected"] == []
    assert nodes.count() == 0
    assert message.acked == 0
    assert message.nacked == 1


@pytest.mark.parametrize("node_state", ["preserved", "missing", "newer"])
@pytest.mark.asyncio
async def test_ambiguous_post_cas_redelivery_reconciles_without_data_loss(
    tmp_path: Path,
    node_state: str,
) -> None:
    fleet_presence = _fleet_presence_module()
    data = _legacy_heartbeat()
    heartbeat = fleet_presence.parse_fleet_heartbeat(data)
    runtime_state = _AmbiguousPostCasRuntime(tmp_path / "runtime.db")
    nodes_path = tmp_path / "nodes.json"
    nodes = _CountingNodeRegistry(nodes_path)
    projector = _projector(
        tmp_path,
        nodes=nodes,
        runtime_state=runtime_state,
    )
    first = _FakeMessage(data)

    with pytest.raises(
        fleet_presence.FleetPresenceError,
        match="completion receipt",
    ) as ambiguous:
        await projector.consume_message(first)

    assert any(
        "CAS outcome unknown" in note
        for note in getattr(ambiguous.value, "__notes__", [])
    )
    assert first.acked == 0
    assert first.nacked == 1
    assert nodes.get("devin") is not None
    if node_state == "missing":
        assert nodes.unregister("devin")
    elif node_state == "newer":
        nodes.record_heartbeat(
            "devin",
            last_heartbeat="2026-07-14T15:31:00+00:00",
            status="degraded",
            metadata={
                "agent_uid": DEVIN_UID,
                "presence_message_id": "presence_newer_after_ambiguity",
            },
            canonical_agent_uid=DEVIN_UID,
        )

    healthy = _FakeMessage(data)
    result = await projector.consume_message(healthy)

    assert result.status == "duplicate"
    assert healthy.acked == 1
    assert healthy.nacked == 0
    current = nodes.get("devin")
    assert current is not None
    expected_message_id = (
        "presence_newer_after_ambiguity"
        if node_state == "newer"
        else heartbeat.message_id
    )
    assert current.metadata["presence_message_id"] == expected_message_id
    assert len(json.loads(nodes_path.read_text(encoding="utf-8"))) == 1
    record = await runtime_state.get_idempotency_record(
        f"idem_presence_{heartbeat.message_id.removeprefix('presence_')}",
        f"fleet_presence:{DEVIN_UID}:{heartbeat.message_id}",
    )
    assert record is not None
    assert record.status == "completed"
    attempts = await runtime_state.list_runtime_receipts(
        receipt_type="fleet_presence_attempt"
    )
    assert any(
        receipt.receipt_id == record.result_receipt_id and receipt.status == "prepared"
        for receipt in attempts
    )
    receipts = await runtime_state.list_runtime_receipts(receipt_type="fleet_presence")
    assert [
        receipt for receipt in receipts if receipt.status == "projection_failed"
    ] == []


@pytest.mark.asyncio
async def test_duplicate_ack_failure_preserves_completed_projection(
    tmp_path: Path,
) -> None:
    fleet_presence = _fleet_presence_module()
    data = _legacy_heartbeat()
    heartbeat = fleet_presence.parse_fleet_heartbeat(data)
    identity = fleet_presence._execution_identity(heartbeat, DEVIN_UID)
    side_effect_key = f"fleet_presence:{DEVIN_UID}:{heartbeat.message_id}"
    runtime_state = RuntimeStateStore(tmp_path / "runtime.db")
    nodes = _CountingNodeRegistry(tmp_path / "nodes.json")
    projector = _projector(
        tmp_path,
        nodes=nodes,
        runtime_state=runtime_state,
    )
    await projector.consume_message(_FakeMessage(data))
    duplicate = _FakeMessage(data, fail_ack=True)

    with pytest.raises(fleet_presence.FleetPresenceError, match="ack failed"):
        await projector.consume_message(duplicate)

    record = await runtime_state.get_idempotency_record(
        identity.idempotency_key,
        side_effect_key,
    )
    assert record is not None
    assert record.status == "completed"
    assert nodes.heartbeat_writes == 1
    assert duplicate.acked == 0
    assert duplicate.nacked == 0


@pytest.mark.asyncio
async def test_node_and_runtime_persistence_complete_before_broker_ack(
    tmp_path: Path,
) -> None:
    nodes_path = tmp_path / "nodes.json"
    runtime_state = RuntimeStateStore(tmp_path / "runtime.db")
    projector = _projector(
        tmp_path,
        nodes=NodeRegistry(nodes_path=nodes_path),
        runtime_state=runtime_state,
    )
    message = _InspectingAckMessage(
        _canonical_heartbeat(),
        nodes_path=nodes_path,
        runtime_state=runtime_state,
    )

    result = await projector.consume_message(message)

    assert result.status == "projected"
    assert message.acked == 1


@pytest.mark.asyncio
async def test_node_persistence_failure_naks_and_rolls_back_registry(
    tmp_path: Path,
) -> None:
    fleet_presence = _fleet_presence_module()
    unwritable_target = tmp_path / "nodes-as-directory"
    unwritable_target.mkdir()
    nodes = NodeRegistry(nodes_path=unwritable_target)
    message = _FakeMessage(_legacy_heartbeat())

    with pytest.raises(fleet_presence.FleetPresenceError, match="persist"):
        await _projector(tmp_path, nodes=nodes).consume_message(message)

    assert message.acked == 0
    assert message.nacked == 1
    assert nodes.count() == 0


@pytest.mark.asyncio
async def test_runtime_failure_after_node_write_restores_registry_exactly(
    tmp_path: Path,
) -> None:
    nodes_path = tmp_path / "nodes.json"
    nodes = NodeRegistry(nodes_path=nodes_path)
    nodes.register(
        RemoteNode(
            node_id="devin",
            endpoint="local://devin",
            status="degraded",
            last_heartbeat="2026-07-14T14:00:00+00:00",
            capabilities=["testing"],
            metadata={"agent_uid": DEVIN_UID, "nested": {"preserve": True}},
        )
    )
    before_node = copy.deepcopy(nodes.get("devin"))
    before_bytes = nodes_path.read_bytes()
    runtime_state = _FailAfterNodeRuntime(tmp_path / "runtime.db")
    message = _FakeMessage(_legacy_heartbeat())

    with pytest.raises(
        _fleet_presence_module().FleetPresenceError,
        match="runtime receipt failed",
    ):
        await _projector(
            tmp_path,
            nodes=nodes,
            runtime_state=runtime_state,
        ).consume_message(message)

    assert nodes.get("devin") == before_node
    assert nodes_path.read_bytes() == before_bytes
    assert message.acked == 0
    assert message.nacked == 1


@pytest.mark.asyncio
async def test_failed_projection_rollback_never_erases_newer_heartbeat(
    tmp_path: Path,
) -> None:
    nodes_path = tmp_path / "nodes.json"
    nodes = NodeRegistry(nodes_path=nodes_path)
    nodes.register(
        RemoteNode(
            node_id="devin",
            status="unknown",
            metadata={"agent_uid": DEVIN_UID},
        )
    )
    runtime_state = _NewerHeartbeatThenFailRuntime(
        tmp_path / "runtime.db",
        nodes,
    )
    message = _FakeMessage(_legacy_heartbeat())

    with pytest.raises(
        _fleet_presence_module().FleetPresenceError,
        match="newer heartbeat",
    ):
        await _projector(
            tmp_path,
            nodes=nodes,
            runtime_state=runtime_state,
        ).consume_message(message)

    current = nodes.get("devin")
    persisted = NodeRegistry(nodes_path=nodes_path).get("devin")
    assert current is not None
    assert persisted is not None
    assert current == persisted
    assert current.last_heartbeat == "2026-07-14T15:31:00+00:00"
    assert current.status == "degraded"
    assert current.metadata["presence_message_id"] == "presence_newer"
    assert message.acked == 0
    assert message.nacked == 1


@pytest.mark.asyncio
async def test_node_parent_creation_failure_also_rolls_back_registry(
    tmp_path: Path,
) -> None:
    fleet_presence = _fleet_presence_module()
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("occupied", encoding="utf-8")
    nodes = NodeRegistry(nodes_path=parent_file / "nodes.json")
    message = _FakeMessage(_legacy_heartbeat())

    with pytest.raises(fleet_presence.FleetPresenceError):
        await _projector(tmp_path, nodes=nodes).consume_message(message)

    assert message.acked == 0
    assert message.nacked == 1
    assert nodes.count() == 0


@pytest.mark.asyncio
async def test_invalid_envelope_is_nacked_without_registry_pollution(
    tmp_path: Path,
) -> None:
    fleet_presence = _fleet_presence_module()
    nodes = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    message = _FakeMessage(b'{"kind":"heartbeat","payload":')

    with pytest.raises(fleet_presence.FleetPresenceError, match="invalid"):
        await _projector(tmp_path, nodes=nodes).consume_message(message)

    assert message.acked == 0
    assert message.nacked == 1
    assert nodes.count() == 0


@pytest.mark.asyncio
async def test_nak_failure_preserves_primary_envelope_error(tmp_path: Path) -> None:
    fleet_presence = _fleet_presence_module()
    message = _FakeMessage(b'{"payload":', fail_nak=True)

    with pytest.raises(fleet_presence.InvalidFleetPresenceEnvelope) as raised:
        await _projector(tmp_path).consume_message(message)

    notes = getattr(raised.value, "__notes__", [])
    assert any("broker NAK failed" in note for note in notes)
    assert message.acked == 0
    assert message.nacked == 0


@pytest.mark.parametrize(
    ("case", "data"),
    [
        ("legacy_nan", _legacy_heartbeat().replace(b"123.5", b"NaN")),
        ("canonical_infinity", _canonical_heartbeat().replace(b"0.25", b"Infinity")),
        (
            "oversized_integer",
            _canonical_heartbeat().replace(
                b'"active_tasks": 2',
                b'"active_tasks": ' + (b"9" * 5_000),
            ),
        ),
        (
            "invalid_timestamp",
            _legacy_heartbeat().replace(HEARTBEAT_AT.encode(), b"not-a-timestamp"),
        ),
        (
            "overflow_timestamp",
            _canonical_heartbeat().replace(
                HEARTBEAT_AT.encode(),
                b"0001-01-01T00:00:00+23:59",
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_strict_boundary_errors_are_invalid_and_nacked(
    tmp_path: Path,
    case: str,
    data: bytes,
) -> None:
    del case
    fleet_presence = _fleet_presence_module()
    with pytest.raises(fleet_presence.InvalidFleetPresenceEnvelope):
        fleet_presence.parse_fleet_heartbeat(data)

    nodes = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    message = _FakeMessage(data)
    with pytest.raises(fleet_presence.InvalidFleetPresenceEnvelope):
        await _projector(tmp_path, nodes=nodes).consume_message(message)

    assert message.acked == 0
    assert message.nacked == 1
    assert nodes.count() == 0


@pytest.mark.asyncio
async def test_agent_directory_exposes_node_heartbeat_projection(
    tmp_path: Path,
) -> None:
    cards = _card_registry(tmp_path)
    nodes = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    await _projector(tmp_path, cards=cards, nodes=nodes).consume_message(
        _FakeMessage(_canonical_heartbeat())
    )
    directory = AgentDirectory(
        card_registry=cards,
        node_registry=nodes,
        dharma_home=tmp_path / "home",
    )

    entry = await directory.get(DEVIN_UID)

    assert entry is not None
    assert entry.last_heartbeat == HEARTBEAT_AT
    assert entry.status == "online"
