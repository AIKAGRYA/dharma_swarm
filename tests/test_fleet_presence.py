"""Tests for durable NATS fleet-heartbeat projection."""

from __future__ import annotations

import asyncio
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

import pytest

import dharma_swarm.a2a.fleet_presence as fp
from dharma_swarm.a2a.agent_card import AgentCard, CardRegistry
from dharma_swarm.a2a.agent_directory import AgentDirectory
from dharma_swarm.a2a.node_registry import NodeRegistry, RemoteNode
from dharma_swarm.runtime_state import RuntimeStateStore

DEVIN_UID = "devin-roaming-2987d222"
HEARTBEAT_AT = "2026-07-14T15:30:00+00:00"
NOW = datetime.fromisoformat(HEARTBEAT_AT)
SUBJECT = f"dharma.agent.{DEVIN_UID}.presence"


# fmt: off
class _Message:
    def __init__(
        self, data: bytes, *, subject: str = SUBJECT, fail_ack: bool = False,
        fail_nak: bool = False, probe: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.data, self.subject, self.headers = data, subject, {}
        self.fail_ack, self.fail_nak, self.probe = fail_ack, fail_nak, probe
        self.acked = self.nacked = 0

    async def ack(self) -> None:
        if self.fail_ack:
            raise RuntimeError("broker ack failed")
        if self.probe:
            await self.probe()
        self.acked += 1

    async def nak(self) -> None:
        if self.fail_nak:
            raise RuntimeError("broker nak failed")
        self.nacked += 1


class _CountingNodes(NodeRegistry):
    def __init__(self, path: Path) -> None:
        super().__init__(path, clock=lambda: NOW)
        self.heartbeat_writes = 0

    def record_heartbeat(self, node_id: str, **kwargs: Any) -> RemoteNode:
        before = self.get(node_id)
        result = super().record_heartbeat(node_id, **kwargs)
        self.heartbeat_writes += before != self.get(node_id)
        return result


class _FaultRuntime(RuntimeStateStore):
    def __init__(self, path: Path, mode: str, nodes: NodeRegistry | None = None) -> None:
        super().__init__(path)
        self.mode, self.nodes, self.raced = mode, nodes, False
        self.reclaimed_identity: Any = None
        self.reclaim_token: Any = None

    async def record_receipt_for_identity(self, identity: Any, **kwargs: Any) -> Any:
        attempt = kwargs.get("receipt_type") == "fleet_presence_attempt"
        if attempt and self.mode in {"receipt", "newer"}:
            if self.mode == "newer":
                assert self.nodes
                self.nodes.record_heartbeat(
                    "devin", last_heartbeat="2026-07-14T15:31:00+00:00", status="degraded",
                    metadata={"agent_uid": DEVIN_UID, "presence_message_id": "presence_newer"},
                    canonical_agent_uid=DEVIN_UID,
                )
            raise RuntimeError("runtime receipt failed after newer heartbeat" if self.mode == "newer" else "runtime receipt failed after node persistence")
        receipt = await super().record_receipt_for_identity(identity, **kwargs)
        if attempt and self.mode == "reclaim" and not self.raced:
            self.raced = True
            key = str(kwargs["side_effect_key"])
            owned = await self.get_idempotency_record(identity.idempotency_key, key)
            assert owned
            await super().complete_idempotent_side_effect(identity, key, status="failed", expected_updated_at=owned.updated_at)
            failed = await self.get_idempotency_record(identity.idempotency_key, key)
            assert failed
            self.reclaimed_identity = identity.with_updates(run_id=f"{identity.run_id}-reclaimed", claim_id=f"{identity.claim_id}-reclaimed")
            self.reclaim_token = await self.try_reclaim_idempotent_side_effect_with_token(
                self.reclaimed_identity, key, expected_status="failed", expected_updated_at=failed.updated_at
            )
            assert self.reclaim_token
        return receipt


class _AmbiguousRuntime(RuntimeStateStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.fail_receipt, self.fail_read = True, False

    async def record_side_effect_complete(self, *args: Any, **kwargs: Any) -> Any:
        if self.fail_receipt and kwargs.get("status", "completed") == "completed":
            self.fail_receipt, self.fail_read = False, True
            raise RuntimeError("completion receipt failed after CAS commit")
        return await super().record_side_effect_complete(*args, **kwargs)

    async def get_idempotency_record(self, *args: Any, **kwargs: Any) -> Any:
        if self.fail_read:
            self.fail_read = False
            raise RuntimeError("reconciliation read failed")
        return await super().get_idempotency_record(*args, **kwargs)


class _Subscription:
    unsubscribed = False
    async def unsubscribe(self) -> None:
        self.unsubscribed = True


class _JetStream:
    def __init__(self) -> None:
        self.subscription, self.kwargs = _Subscription(), {}
    async def subscribe(self, subject: str, **kwargs: Any) -> _Subscription:
        self.kwargs = {"subject": subject, **kwargs}
        return self.subscription


class _Connection:
    def __init__(self) -> None:
        self.js, self.drained = _JetStream(), False
    def jetstream(self) -> _JetStream:
        return self.js
    async def drain(self) -> None:
        self.drained = True


def _cards(tmp: Path, *, hermes: bool = False, empty: bool = False) -> CardRegistry:
    cards = CardRegistry(tmp / "cards")
    if not empty:
        cards.register(AgentCard(name="devin", agent_uid=DEVIN_UID, status="idle"))
    if hermes:
        cards.register(AgentCard(name="hermes", agent_uid="hermes-m5", status="idle"))
    return cards


def _nodes(tmp: Path) -> NodeRegistry:
    return NodeRegistry(tmp / "nodes.json", clock=lambda: NOW)


def _projector(
    tmp: Path, *, cards: CardRegistry | None = None, nodes: NodeRegistry | None = None,
    runtime: RuntimeStateStore | None = None, **kwargs: Any,
) -> fp.FleetPresenceProjector:
    return fp.FleetPresenceProjector(
        card_registry=cards or _cards(tmp), node_registry=nodes or _nodes(tmp),
        runtime_state=runtime or RuntimeStateStore(tmp / "runtime.db"), clock=lambda: NOW, **kwargs,
    )


def _legacy(*, sender: str = "devin", uid: str = DEVIN_UID, packet: str = "hb-001", subject: str = SUBJECT) -> bytes:
    return json.dumps({
        "schema_version": "dharma.a2a.send.v1", "packet_id": packet, "timestamp": HEARTBEAT_AT,
        "from": sender, "to": "fleet", "kind": "heartbeat", "route": "a2a", "subject": subject,
        "content": json.dumps({"agent_uid": uid, "status": "online", "messages_received": 7, "uptime_s": 123.5}),
    }, sort_keys=True).encode()


def _canonical(*, sender: str = "devin", uid: str = DEVIN_UID, message_id: str = "hb-canonical", subject: str = SUBJECT) -> bytes:
    return json.dumps({
        "schema": "dharma.nats.envelope.v1", "message_id": message_id, "subject": subject,
        "from_agent": sender, "to_agent": "fleet", "actor": {"from_agent": sender, "to_agent": "fleet"},
        "kind": "heartbeat", "created_at": HEARTBEAT_AT, "requires_ack": True,
        "payload": {"schema": "dharma.a2a.fleet_heartbeat.v1", "agent_uid": uid, "status": "online",
                    "metadata": {"load": 0.25, "active_tasks": 2}},
    }, sort_keys=True).encode()


def test_node_registry_record_heartbeat_is_identity_checked_and_persisted(tmp_path: Path) -> None:
    nodes = _nodes(tmp_path)
    with pytest.raises(ValueError, match="Unknown"):
        nodes.record_heartbeat("unknown", last_heartbeat=HEARTBEAT_AT, status="online")
    nodes.register(RemoteNode("devin", status="unknown", metadata={"agent_uid": DEVIN_UID, "kept": True}))
    node = nodes.record_heartbeat(
        "devin", last_heartbeat=HEARTBEAT_AT, status="online", metadata={"messages_received": 7},
        canonical_agent_uid=DEVIN_UID,
    )
    assert node.status == "online" and node.metadata["kept"] is True
    assert NodeRegistry(tmp_path / "nodes.json", clock=lambda: NOW).get("devin") == node


@pytest.mark.parametrize(("payload", "subject", "compat", "field", "value"), [(_legacy(subject=fp.FLEET_HEARTBEAT_SUBJECT), fp.FLEET_HEARTBEAT_SUBJECT, True, "messages_received", 7), (_canonical(), SUBJECT, True, "load", 0.25)])
@pytest.mark.asyncio
async def test_valid_legacy_and_canonical_heartbeats_project(tmp_path: Path, payload: bytes, subject: str, compat: bool, field: str, value: Any) -> None:
    nodes, message = _nodes(tmp_path), _Message(payload, subject=subject)
    result = await _projector(tmp_path, nodes=nodes, compatibility_mode=compat).consume_message(message)
    node = nodes.get("devin")
    assert result.status == "projected" and result.agent_uid == DEVIN_UID
    assert message.acked == 1 and message.nacked == 0 and node
    assert node.status == "online" and node.last_heartbeat == HEARTBEAT_AT and node.metadata[field] == value


@pytest.mark.parametrize("case", ["payload_mismatch", "unknown", "envelope_subject_mismatch", "subject_uid_mismatch", "legacy_without_compat"])
@pytest.mark.asyncio
async def test_identity_rejections_nak_without_registry_pollution(tmp_path: Path, case: str) -> None:
    cards, payload, subject = _cards(tmp_path), _canonical(), SUBJECT
    if case == "payload_mismatch":
        cards, payload = _cards(tmp_path, hermes=True), _canonical(uid="hermes-m5")
    elif case == "unknown":
        cards, payload = _cards(tmp_path, empty=True), _canonical(sender="intruder", uid="intruder")
    elif case == "envelope_subject_mismatch":
        subject = "dharma.agent.hermes-m5.presence"
    elif case == "subject_uid_mismatch":
        subject, payload = "dharma.agent.hermes-m5.presence", _canonical(subject="dharma.agent.hermes-m5.presence")
    else:
        subject, payload = fp.FLEET_HEARTBEAT_SUBJECT, _legacy(subject=fp.FLEET_HEARTBEAT_SUBJECT)
    nodes, message = _nodes(tmp_path), _Message(payload, subject=subject)
    with pytest.raises(fp.FleetPresenceError, match="mismatch|unknown|compatibility"):
        await _projector(tmp_path, cards=cards, nodes=nodes, compatibility_mode=case == "subject_uid_mismatch").consume_message(message)
    assert message.nacked == 1 and message.acked == 0 and nodes.count() == 0


@pytest.mark.asyncio
async def test_duplicate_and_ack_failure_preserve_one_completed_projection(tmp_path: Path) -> None:
    runtime, nodes = RuntimeStateStore(tmp_path / "runtime.db"), _CountingNodes(tmp_path / "nodes.json")
    projector, data = _projector(tmp_path, nodes=nodes, runtime=runtime), _legacy()
    first = await projector.consume_message(_Message(data))
    duplicate = await projector.consume_message(_Message(data))
    assert first.status == "projected" and duplicate.status == "duplicate" and duplicate.duplicate
    with pytest.raises(fp.FleetPresenceError, match="ack failed"):
        await projector.consume_message(_Message(data, fail_ack=True))
    heartbeat, identity = fp.parse_fleet_heartbeat(data, transport_subject=SUBJECT), fp._execution_identity(fp.parse_fleet_heartbeat(data, transport_subject=SUBJECT), DEVIN_UID)
    record = await runtime.get_idempotency_record(identity.idempotency_key, f"fleet_presence:{DEVIN_UID}:{heartbeat.message_id}")
    assert record and record.status == "completed" and nodes.heartbeat_writes == 1


@pytest.mark.asyncio
async def test_in_progress_delivery_does_not_steal_owner(tmp_path: Path) -> None:
    data, runtime = _legacy(), RuntimeStateStore(tmp_path / "runtime.db")
    heartbeat = fp.parse_fleet_heartbeat(data, transport_subject=SUBJECT)
    identity, key = fp._execution_identity(heartbeat, DEVIN_UID), f"fleet_presence:{DEVIN_UID}:{heartbeat.message_id}"
    await runtime.record_execution_identity(identity, source="test")
    assert await runtime.try_begin_idempotent_side_effect(identity, key)
    message = _Message(data)
    with pytest.raises(fp.FleetPresenceError, match="in progress"):
        await _projector(tmp_path, runtime=runtime).consume_message(message)
    record = await runtime.get_idempotency_record(identity.idempotency_key, key)
    assert record and record.status == "started" and message.nacked == 1


@pytest.mark.asyncio
async def test_reclaimed_owner_blocks_stale_original_completion(tmp_path: Path) -> None:
    runtime, nodes = _FaultRuntime(tmp_path / "runtime.db", "reclaim"), _nodes(tmp_path)
    message = _Message(_legacy())
    with pytest.raises(fp.FleetPresenceError, match="lease lost"):
        await _projector(tmp_path, nodes=nodes, runtime=runtime).consume_message(message)
    heartbeat = fp.parse_fleet_heartbeat(message.data, transport_subject=SUBJECT)
    record = await runtime.get_idempotency_record(runtime.reclaimed_identity.idempotency_key, f"fleet_presence:{DEVIN_UID}:{heartbeat.message_id}")
    assert record and record.status == "started" and record.updated_at == runtime.reclaim_token
    assert nodes.count() == 0 and message.nacked == 1


@pytest.mark.parametrize("node_state", ["preserved", "missing", "newer"])
@pytest.mark.asyncio
async def test_ambiguous_cas_redelivery_repairs_without_overwriting_newer(tmp_path: Path, node_state: str) -> None:
    data, runtime, nodes = _legacy(), _AmbiguousRuntime(tmp_path / "runtime.db"), _CountingNodes(tmp_path / "nodes.json")
    projector, first = _projector(tmp_path, nodes=nodes, runtime=runtime), _Message(data)
    with pytest.raises(fp.FleetPresenceError, match="completion receipt") as raised:
        await projector.consume_message(first)
    assert any("CAS outcome unknown" in note for note in getattr(raised.value, "__notes__", []))
    if node_state == "missing":
        assert nodes.unregister("devin")
    elif node_state == "newer":
        nodes.record_heartbeat(
            "devin", last_heartbeat="2026-07-14T15:31:00+00:00", status="degraded",
            metadata={"agent_uid": DEVIN_UID, "presence_message_id": "presence_newer"}, canonical_agent_uid=DEVIN_UID,
        )
    result = await projector.consume_message(_Message(data))
    current, heartbeat = nodes.get("devin"), fp.parse_fleet_heartbeat(data, transport_subject=SUBJECT)
    assert result.status == "duplicate" and current
    assert current.metadata["presence_message_id"] == ("presence_newer" if node_state == "newer" else heartbeat.message_id)
    receipts = await runtime.list_runtime_receipts(receipt_type="fleet_presence")
    assert not [receipt for receipt in receipts if receipt.status == "projection_failed"]


@pytest.mark.asyncio
async def test_node_and_runtime_persist_before_ack(tmp_path: Path) -> None:
    path, runtime = tmp_path / "nodes.json", RuntimeStateStore(tmp_path / "runtime.db")
    async def probe() -> None:
        assert json.loads(path.read_text())[0]["last_heartbeat"] == HEARTBEAT_AT
        attempts = await runtime.list_runtime_receipts(receipt_type="fleet_presence_attempt")
        record = await runtime.get_idempotency_record(attempts[0].idempotency_key, attempts[0].side_effect_key)
        assert attempts[0].status == "prepared" and record and record.status == "completed"
    message = _Message(_canonical(), probe=probe)
    await _projector(tmp_path, nodes=NodeRegistry(path, clock=lambda: NOW), runtime=runtime).consume_message(message)
    assert message.acked == 1


@pytest.mark.parametrize("path_case", ["directory", "parent_file"])
@pytest.mark.asyncio
async def test_node_persistence_failure_naks_and_rolls_back(tmp_path: Path, path_case: str) -> None:
    target = tmp_path / "bad"
    if path_case == "directory":
        target.mkdir()
    else:
        target.write_text("occupied")
        target /= "nodes.json"
    nodes, message = NodeRegistry(target, clock=lambda: NOW), _Message(_legacy())
    with pytest.raises(fp.FleetPresenceError, match="persist|File exists"):
        await _projector(tmp_path, nodes=nodes).consume_message(message)
    assert nodes.count() == 0 and message.nacked == 1


@pytest.mark.parametrize("mode", ["receipt", "newer"])
@pytest.mark.asyncio
async def test_runtime_failure_compensates_without_erasing_newer(tmp_path: Path, mode: str) -> None:
    nodes, path = _nodes(tmp_path), tmp_path / "nodes.json"
    nodes.register(RemoteNode("devin", status="degraded", last_heartbeat="2026-07-14T15:29:00+00:00", metadata={"agent_uid": DEVIN_UID, "nested": {"keep": True}}))
    before, before_bytes = copy.deepcopy(nodes.get("devin")), path.read_bytes()
    runtime, message = _FaultRuntime(tmp_path / "runtime.db", mode, nodes), _Message(_legacy())
    with pytest.raises(fp.FleetPresenceError, match="runtime receipt"):
        await _projector(tmp_path, nodes=nodes, runtime=runtime).consume_message(message)
    current = nodes.get("devin")
    if mode == "receipt":
        assert current == before and path.read_bytes() == before_bytes
    else:
        assert current and current.last_heartbeat.endswith("15:31:00+00:00") and current.metadata["presence_message_id"] == "presence_newer"
    assert message.nacked == 1


INVALID = [
    b'{"kind":"heartbeat","payload":',
    _legacy().replace(b"123.5", b"NaN"),
    _canonical().replace(b"0.25", b"Infinity"),
    _canonical().replace(b'"active_tasks": 2', b'"active_tasks": ' + b"9" * 5_000),
    _legacy().replace(HEARTBEAT_AT.encode(), b"not-a-timestamp"),
    _canonical().replace(HEARTBEAT_AT.encode(), b"0001-01-01T00:00:00+23:59"),
]


@pytest.mark.parametrize("data", INVALID)
@pytest.mark.asyncio
async def test_strict_boundary_errors_nak_without_pollution(tmp_path: Path, data: bytes) -> None:
    with pytest.raises(fp.InvalidFleetPresenceEnvelope):
        fp.parse_fleet_heartbeat(data, transport_subject=SUBJECT)
    nodes, message = _nodes(tmp_path), _Message(data)
    with pytest.raises(fp.InvalidFleetPresenceEnvelope):
        await _projector(tmp_path, nodes=nodes).consume_message(message)
    assert message.nacked == 1 and nodes.count() == 0


@pytest.mark.asyncio
async def test_nak_failure_preserves_primary_error(tmp_path: Path) -> None:
    message = _Message(b'{"payload":', fail_nak=True)
    with pytest.raises(fp.InvalidFleetPresenceEnvelope) as raised:
        await _projector(tmp_path).consume_message(message)
    assert any("broker NAK failed" in note for note in getattr(raised.value, "__notes__", []))


@pytest.mark.asyncio
async def test_agent_directory_exposes_heartbeat_without_becoming_authority(tmp_path: Path) -> None:
    cards, nodes = _cards(tmp_path), _nodes(tmp_path)
    await _projector(tmp_path, cards=cards, nodes=nodes).consume_message(_Message(_canonical()))
    entry = await AgentDirectory(card_registry=cards, node_registry=nodes, dharma_home=tmp_path / "home").get(DEVIN_UID)
    assert entry and entry.last_heartbeat == HEARTBEAT_AT and entry.status == "online"


def test_presence_config_env_and_subject_policy_safety(monkeypatch: pytest.MonkeyPatch) -> None:
    config = fp.FleetPresenceConsumerConfig.from_env({
        "NATS_URL": "nats://broker:4222", "NATS_USER": "fleet", "NATS_PASSWORD": "secret",
        "NATS_STREAM": "PRESENCE", "NATS_SUBJECT": "dharma.agent.*.presence", "NATS_CONSUMER": "presence",
    })
    assert (config.url, config.stream, config.durable) == ("nats://broker:4222", "PRESENCE", "presence")
    assert "secret" not in repr(config) and fp.FleetPresenceConsumerConfig().subject == fp.DEFAULT_PRESENCE_SUBJECT
    with pytest.raises(fp.FleetPresenceConfigurationError, match="shared"):
        fp.FleetPresenceConsumerConfig(subject="dharma.a2a.fleet")
    assert fp.FleetPresenceConsumerConfig(subject="dharma.a2a.fleet", compatibility_mode=True).compatibility_mode
    monkeypatch.setattr(fp.hashlib, "sha256", lambda *_: pytest.fail("identity derived for invalid subject"))
    with pytest.raises(fp.InvalidFleetPresenceEnvelope, match="subject"):
        fp.parse_fleet_heartbeat(_canonical(subject="dharma.a2a.other"), transport_subject="dharma.a2a.other", compatibility_mode=True)
@pytest.mark.parametrize("kind", ["registration", "task"])
@pytest.mark.asyncio
async def test_shared_compatibility_acks_nonheartbeat_traffic(tmp_path: Path, kind: str) -> None:
    payload = json.loads(_legacy())
    payload["kind"] = kind
    message = _Message(json.dumps(payload).encode(), subject="dharma.a2a.fleet")
    result = await _projector(tmp_path, compatibility_mode=True).consume_message(message)
    assert result.status == "skipped" and message.acked == 1 and message.nacked == 0


@pytest.mark.asyncio
async def test_future_timestamp_cannot_poison_following_valid_heartbeat(tmp_path: Path) -> None:
    nodes, projector = _nodes(tmp_path), _projector(tmp_path, nodes=_nodes(tmp_path), max_future_skew_s=30)
    projector.node_registry = nodes
    future = _Message(_legacy().replace(HEARTBEAT_AT.encode(), b"2099-01-01T00:00:00+00:00"))
    with pytest.raises(fp.InvalidFleetPresenceEnvelope, match="future"):
        await projector.consume_message(future)
    valid = _Message(_legacy(packet="valid-after-future"))
    await projector.consume_message(valid)
    assert future.nacked == 1 and valid.acked == 1 and nodes.get("devin").last_heartbeat == HEARTBEAT_AT


@pytest.mark.asyncio
async def test_defensive_reads_and_staleness_block_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    current, nodes = [NOW], NodeRegistry(tmp_path / "nodes.json", clock=lambda: current[0])
    source = RemoteNode("devin", status="online", last_heartbeat=HEARTBEAT_AT, metadata={"agent_uid": DEVIN_UID})
    nodes.register(source)
    source.metadata["outside"] = True
    alias = nodes.get("devin")
    assert alias
    alias.status, alias.metadata["inside"] = "offline", True
    assert nodes.get("devin").status == "online" and "inside" not in nodes.list_all()[0].metadata
    current[0] += timedelta(seconds=901)
    assert nodes.get("devin").status == "offline"
    from api.routers import fleet
    monkeypatch.setattr(fleet, "_get_registry", lambda: nodes)
    with pytest.raises(Exception) as blocked:
        await fleet.dispatch_task({"node_id": "devin", "capability": "x", "message": "x"})
    assert getattr(blocked.value, "status_code", None) == 503


def test_concurrent_heartbeats_leave_one_atomic_latest_snapshot(tmp_path: Path) -> None:
    nodes = _nodes(tmp_path)
    def write(offset: int) -> None:
        observed = (NOW + timedelta(seconds=offset)).isoformat()
        nodes.record_heartbeat(
            "devin", last_heartbeat=observed, status="online",
            metadata={"agent_uid": DEVIN_UID, "presence_message_id": f"m{offset}"}, canonical_agent_uid=DEVIN_UID,
        )
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, reversed(range(20))))
    assert nodes.get("devin").last_heartbeat == (NOW + timedelta(seconds=19)).isoformat()
    assert len(json.loads((tmp_path / "nodes.json").read_text())) == 1


@pytest.mark.asyncio
async def test_consumer_loop_starts_and_cancels_without_network(tmp_path: Path) -> None:
    connection, calls = _Connection(), []
    async def connect(**kwargs: Any) -> _Connection:
        calls.append(kwargs)
        return connection
    ready = asyncio.get_running_loop().create_future()
    task = asyncio.create_task(fp.run_fleet_presence_consumer(_projector(tmp_path), config=fp.FleetPresenceConsumerConfig(), connect=connect, ready=ready))
    await asyncio.wait_for(ready, 1)
    assert calls[0]["servers"] == [fp.DEFAULT_PRESENCE_URL]
    assert connection.js.kwargs["subject"] == fp.DEFAULT_PRESENCE_SUBJECT and connection.js.kwargs["manual_ack"] is True
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert connection.js.subscription.unsubscribed and connection.drained


@pytest.mark.asyncio
async def test_consumer_startup_failure_is_reported_to_readiness(tmp_path: Path) -> None:
    async def fail(**kwargs: Any) -> Any:
        raise RuntimeError("broker unavailable")
    ready = asyncio.get_running_loop().create_future()
    task = asyncio.create_task(fp.run_fleet_presence_consumer(_projector(tmp_path), connect=fail, ready=ready))
    with pytest.raises(RuntimeError, match="broker unavailable"):
        await ready
    with pytest.raises(RuntimeError, match="broker unavailable"):
        await task


@pytest.mark.asyncio
async def test_api_presence_lifespan_opt_in_start_cancel_and_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import api.main as api_main
    monkeypatch.setattr(api_main, "_state", {"card_registry": _cards(tmp_path), "node_registry": _nodes(tmp_path)})
    monkeypatch.delenv("DHARMA_FLEET_PRESENCE_ENABLED", raising=False)
    assert await api_main._start_fleet_presence_consumer() is None
    lifespan_names = api_main.lifespan.__wrapped__.__code__.co_names
    assert "_start_fleet_presence_consumer" in lifespan_names
    assert "_stop_fleet_presence_consumer" in lifespan_names
    monkeypatch.setenv("DHARMA_FLEET_PRESENCE_ENABLED", "1")
    monkeypatch.setenv("DHARMA_FLEET_PRESENCE_SUBJECT", fp.DEFAULT_PRESENCE_SUBJECT)
    monkeypatch.setenv("DHARMA_STATE_DIR", str(tmp_path / "canonical-state"))
    cancelled = asyncio.Event()
    runtime_paths: list[Path] = []
    async def running(*args: Any, **kwargs: Any) -> None:
        runtime_paths.append(args[0].runtime_state.db_path)
        kwargs["ready"].set_result(None)
        try:
            await asyncio.Future()
        finally:
            cancelled.set()
    monkeypatch.setattr(fp, "run_fleet_presence_consumer", running)
    task = await api_main._start_fleet_presence_consumer()
    assert task and not task.done()
    assert runtime_paths == [tmp_path / "canonical-state" / "runtime.db"]
    await api_main._stop_fleet_presence_consumer()
    assert cancelled.is_set()
    async def failing(*args: Any, **kwargs: Any) -> None:
        error = RuntimeError("presence startup failed")
        kwargs["ready"].set_exception(error)
        raise error
    monkeypatch.setattr(fp, "run_fleet_presence_consumer", failing)
    with pytest.raises(RuntimeError, match="presence startup failed"):
        await api_main._start_fleet_presence_consumer()
# fmt: on
