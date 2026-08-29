from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dharma_swarm.a2a.candidate_transport_contract import secure_private_file
from dharma_swarm.a2a.nats_transport_support import NATS_ENVELOPE_SCHEMA
from dharma_swarm.forge_lab.candidate_envelope import (
    CandidateEnvelope,
    EvidenceBinding,
    TerminalDisposition,
    TerminalState,
    sign_candidate_envelope,
)
from dharma_swarm.forge_lab.candidate_store import CandidateStore
from dharma_swarm.forge_lab.candidate_transport import (
    CANDIDATE_DELIVERY_SCHEMA,
    CandidateHandlingResult,
    CandidateJetStreamTransport,
    CandidateTransportConfig,
    CandidateTransportError,
    ConnectionSecurity,
    TopologyDriftError,
)
from dharma_swarm.forge_lab.promotion_controller import LeaseVerification


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _at(seconds: int = 0) -> str:
    value = datetime(2026, 8, 27, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    return value.isoformat().replace("+00:00", "Z")


def _evidence(name: str) -> EvidenceBinding:
    return EvidenceBinding(
        schema=f"test.{name}.v1",
        receipt_id=f"receipt-{name}",
        sha256=_sha(name),
        issuer=f"issuer-{name}",
        created_at=_at(),
    )


def _public(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def _signed():
    key = Ed25519PrivateKey.generate()
    envelope = CandidateEnvelope(
        candidate_id="cand_transport",
        revision=1,
        predecessor_envelope_id="",
        correlation_id="corr-transport",
        idempotency_key="idem-transport",
        source_run_id="run-transport",
        source_task_id="task-transport",
        source_sha="1" * 40,
        controller_sha="2" * 40,
        harness_sha="3" * 40,
        evaluator_sha="4" * 40,
        target_sha="5" * 40,
        base_sha="6" * 40,
        patch_sha256=_sha("patch"),
        dependencies_sha256=_sha("deps"),
        toolchain_sha256=_sha("tools"),
        artifact_sha256=_sha("artifact"),
        configuration_sha256=_sha("config"),
        provider_attestation=_evidence("provider"),
        budget_receipt=_evidence("budget"),
        evaluation_receipt=_evidence("source-eval"),
        provenance_receipt=_evidence("provenance"),
        task_identity="swebench::django-12209",
        holdout_identity="holdout::django-12209::v1",
        parent_lineage=("cand_parent",),
        evaluation_outcome="source_pass",
        evaluation_comparable=True,
        authority_id="rsi-controller",
        lease_id="rsi-lease-transport",
        lease_expires_at=_at(400),
        created_at=_at(),
        expires_at=_at(300),
        attempt=1,
        fence=13,
        terminal_disposition=TerminalDisposition(
            state=TerminalState.SUBMITTED,
            reason_code="submitted_for_delivery",
            receipt_id="submit-transport",
            at=_at(),
        ),
    )
    return sign_candidate_envelope(
        envelope,
        signing_key=key,
        authority_epoch_sha256=_sha("source-epoch"),
    ), key


class _Missing(RuntimeError):
    code = 404


def _dict(config):
    if isinstance(config, dict):
        return dict(config)
    names = config.__dataclass_fields__
    return {name: getattr(config, name) for name in names}


@dataclass
class _Ack:
    stream: str
    seq: int
    duplicate: bool = False


class _JetStream:
    def __init__(self) -> None:
        self.streams = {}
        self.consumers = {}
        self.published = []
        self.message_ids = set()
        self.failures = 0
        self.add_calls = 0
        self.fail_after_add_call = 0

    async def stream_info(self, name):
        if name not in self.streams:
            raise _Missing("stream not found")
        return {"config": self.streams[name]}

    async def add_stream(self, *, config):
        payload = _dict(config)
        self.streams[payload["name"]] = payload
        self.add_calls += 1
        if self.fail_after_add_call == self.add_calls:
            raise RuntimeError("injected crash after topology mutation")

    async def delete_stream(self, name):
        self.streams.pop(name, None)
        for key in list(self.consumers):
            if key[0] == name:
                self.consumers.pop(key)

    async def consumer_info(self, stream, consumer):
        if (stream, consumer) not in self.consumers:
            raise _Missing("consumer not found")
        return {"config": self.consumers[(stream, consumer)]}

    async def add_consumer(self, stream, *, config):
        payload = _dict(config)
        self.consumers[(stream, payload["durable_name"])] = payload
        self.add_calls += 1
        if self.fail_after_add_call == self.add_calls:
            raise RuntimeError("injected crash after topology mutation")

    async def delete_consumer(self, stream, consumer):
        self.consumers.pop((stream, consumer), None)

    async def publish(self, subject, payload, *, headers=None, timeout=None):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("injected publish failure")
        message_id = (headers or {}).get("Nats-Msg-Id", "")
        duplicate = message_id in self.message_ids
        self.message_ids.add(message_id)
        self.published.append((subject, payload, headers))
        stream = (
            "FOUNDRY_RSI_CANDIDATES_DLQ_V1"
            if subject.endswith("dlq.v1")
            else "FOUNDRY_RSI_CANDIDATES_V1"
        )
        return _Ack(stream=stream, seq=len(self.published), duplicate=duplicate)


class _Lease:
    def __init__(self, *, allowed=True, wrong_fence=False, **overrides):
        self.allowed = allowed
        self.wrong_fence = wrong_fence
        self.overrides = overrides

    async def verify(self, **request):
        payload = dict(
            allowed=self.allowed,
            reason_code="verified" if self.allowed else "refused",
            authority_id=request["authority_id"],
            lease_id=request["lease_id"],
            candidate_id=request["candidate_id"],
            envelope_id=request["envelope_id"],
            fence=request["fence"] + (1 if self.wrong_fence else 0),
            expires_at=request["lease_expires_at"],
            required_scope=request["required_scope"],
            verified_at=request["now"],
            verifier_receipt_sha256=_sha("lease") if self.allowed else "",
        )
        payload.update(self.overrides)
        return LeaseVerification(**payload)


class _Message:
    def __init__(self, subject, data, *, headers=None, deliveries=1):
        self.subject = subject
        self.data = data
        self.headers = headers
        self.num_delivered = deliveries
        self.acked = 0
        self.nacked = 0
        self.nak_delays = []

    async def ack(self):
        self.acked += 1

    async def nak(self, *, delay=None):
        self.nacked += 1
        self.nak_delays.append(delay)


async def _transport(tmp_path, *, lease=None, security=None):
    signed, key = _signed()
    js = _JetStream()
    store = CandidateStore(tmp_path / "terminal.jsonl", experiment_id="transport")
    await store.load()
    transport = CandidateJetStreamTransport(
        trusted_source_public_keys=[_public(key)],
        terminal_store=store,
        lease_verifier=lease or _Lease(),
        jetstream=js,
        security=security or ConnectionSecurity(True, True, "candidate-test", "test-auth"),
        sleep=lambda _: _no_sleep(),
    )
    return transport, js, store, signed


async def _no_sleep():
    return None


async def _install_exact_topology(transport, js) -> None:
    desired = transport.desired_topology()
    for name, config in desired["streams"].items():
        js.streams[name] = dict(config)
    js.consumers[(transport.config.stream_name, transport.config.consumer_name)] = dict(
        desired["consumer"]
    )


@pytest.mark.asyncio
async def test_topology_is_exact_versioned_and_refuses_drift(tmp_path) -> None:
    transport, js, _, _ = await _transport(tmp_path)

    await _install_exact_topology(transport, js)
    first = await transport.ensure_topology()
    second = await transport.ensure_topology()

    assert first["created"] == []
    assert second["created"] == []
    js.streams["FOUNDRY_RSI_CANDIDATES_V1"]["max_bytes"] += 1
    with pytest.raises(TopologyDriftError, match="max_bytes"):
        await transport.ensure_topology()


@pytest.mark.asyncio
async def test_runtime_topology_check_never_creates_missing_resources_by_default(tmp_path) -> None:
    transport, js, _, _ = await _transport(tmp_path)
    with pytest.raises(TopologyDriftError, match="required candidate topology is missing"):
        await transport.ensure_topology()
    assert js.streams == {} and js.consumers == {}


@pytest.mark.asyncio
async def test_receipted_nkey_provision_recovers_partial_failure_and_rolls_back(tmp_path) -> None:
    seed_text = "SUAKYRHVIOREXV7EUZTBHUHL7NUMHPMAS7QMDU3GTIUWEI5LDNOXD43IZY"
    public_nkey = "UD466L6EBCM3YY5HEGHJANNTN4LSKTSUXTH7RILHCKEQMQHTBNLHJJXT"
    seed = tmp_path / "provisioner.nk"
    seed.write_text(seed_text + "\n", encoding="ascii")
    seed.chmod(0o600)
    js = _JetStream()
    store = CandidateStore(tmp_path / "unused.jsonl", experiment_id="topology-operation")
    await store.load()
    transport = CandidateJetStreamTransport(
        trusted_source_public_keys=(),
        terminal_store=store,
        lease_verifier=None,
        config=CandidateTransportConfig(
            nkey_file=str(seed), nkey_public_key=public_nkey,
        ),
        jetstream=js,
        security=ConnectionSecurity(True, False, public_nkey, "nkey-seed-file"),
    )
    receipt_path = tmp_path / "topology-operation.json"
    js.fail_after_add_call = 1
    with pytest.raises(TopologyDriftError, match="reconcile or roll back"):
        await transport.provision_topology(receipt_path=receipt_path, now=_at())
    failed = json.loads(receipt_path.read_text())
    assert failed["state"] == "failed_recoverable"
    assert failed["created_resources"] == ["stream:FOUNDRY_RSI_CANDIDATES_V1"]
    assert seed_text not in receipt_path.read_text()

    js.fail_after_add_call = 0
    complete = await transport.provision_topology(receipt_path=receipt_path, now=_at(1))
    assert complete["state"] == "complete"
    assert set(complete["created_resources"]) == {
        "stream:FOUNDRY_RSI_CANDIDATES_V1",
        "stream:FOUNDRY_RSI_CANDIDATES_DLQ_V1",
        "consumer:FOUNDRY_RSI_CANDIDATES_V1:foundry_rsi_evaluator_v1",
    }
    assert (await transport.ensure_topology())["status"] == "ok"

    rolled_back = await transport.rollback_topology(
        receipt_path=receipt_path, now=_at(2)
    )
    assert rolled_back["state"] == "rollback_complete"
    assert js.streams == {} and js.consumers == {}


@pytest.mark.asyncio
async def test_topology_provision_ignores_crash_orphan_and_serializes_concurrent_calls(
    tmp_path,
) -> None:
    class _YieldingJetStream(_JetStream):
        async def add_stream(self, *, config):
            await asyncio.sleep(0)
            return await super().add_stream(config=config)

        async def add_consumer(self, stream, *, config):
            await asyncio.sleep(0)
            return await super().add_consumer(stream, config=config)

    seed_text = "SUAKYRHVIOREXV7EUZTBHUHL7NUMHPMAS7QMDU3GTIUWEI5LDNOXD43IZY"
    public_nkey = "UD466L6EBCM3YY5HEGHJANNTN4LSKTSUXTH7RILHCKEQMQHTBNLHJJXT"
    seed = tmp_path / "provisioner.nk"
    seed.write_text(seed_text + "\n", encoding="ascii")
    seed.chmod(0o600)
    js = _YieldingJetStream()
    store = CandidateStore(tmp_path / "unused.jsonl", experiment_id="locked-topology")
    await store.load()
    transport = CandidateJetStreamTransport(
        trusted_source_public_keys=(), terminal_store=store, lease_verifier=None,
        config=CandidateTransportConfig(nkey_file=str(seed), nkey_public_key=public_nkey),
        jetstream=js,
        security=ConnectionSecurity(True, False, public_nkey, "nkey-seed-file"),
    )
    receipt_path = tmp_path / "topology-operation.json"
    orphan = receipt_path.with_name(
        f".{receipt_path.name}.{'f' * 64}.tmp"
    )
    orphan.write_text("simulated killed writer", encoding="utf-8")
    orphan.chmod(0o600)

    first, second = await asyncio.gather(
        transport.provision_topology(receipt_path=receipt_path, now=_at()),
        transport.provision_topology(receipt_path=receipt_path, now=_at(1)),
    )

    assert first["operation_id"] == second["operation_id"]
    assert first["state"] == second["state"] == "complete"
    assert js.add_calls == 3
    assert orphan.read_text(encoding="utf-8") == "simulated killed writer"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["state"] == "complete"
    assert receipt["created_resources"] == first["created_resources"]


@pytest.mark.asyncio
async def test_provision_refuses_partial_topology_without_bound_journal(tmp_path) -> None:
    seed_text = "SUAKYRHVIOREXV7EUZTBHUHL7NUMHPMAS7QMDU3GTIUWEI5LDNOXD43IZY"
    public_nkey = "UD466L6EBCM3YY5HEGHJANNTN4LSKTSUXTH7RILHCKEQMQHTBNLHJJXT"
    seed = tmp_path / "provisioner.nk"
    seed.write_text(seed_text + "\n", encoding="ascii")
    seed.chmod(0o600)
    js = _JetStream()
    store = CandidateStore(tmp_path / "unused.jsonl", experiment_id="partial-topology")
    await store.load()
    transport = CandidateJetStreamTransport(
        trusted_source_public_keys=(), terminal_store=store, lease_verifier=None,
        config=CandidateTransportConfig(nkey_file=str(seed), nkey_public_key=public_nkey),
        jetstream=js,
        security=ConnectionSecurity(True, False, public_nkey, "nkey-seed-file"),
    )
    first_name, first_config = next(iter(transport.desired_topology()["streams"].items()))
    js.streams[first_name] = dict(first_config)
    with pytest.raises(TopologyDriftError, match="partial candidate topology"):
        await transport.provision_topology(
            receipt_path=tmp_path / "partial-operation.json", now=_at()
        )
    assert set(js.streams) == {first_name} and js.consumers == {}


@pytest.mark.asyncio
async def test_topology_normalizes_raw_nats_nanoseconds_but_not_real_drift(tmp_path) -> None:
    transport, js, _, _ = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    for stream in js.streams.values():
        stream["max_age"] = int(stream["max_age"] * 1_000_000_000)
        stream["duplicate_window"] = int(stream["duplicate_window"] * 1_000_000_000)
    consumer = js.consumers[(transport.config.stream_name, transport.config.consumer_name)]
    consumer["ack_wait"] = int(consumer["ack_wait"] * 1_000_000_000)
    consumer["backoff"] = tuple(int(value * 1_000_000_000) for value in consumer["backoff"])

    assert (await transport.ensure_topology())["status"] == "ok"
    js.streams[transport.config.stream_name]["max_age"] += 1_000_000_000
    with pytest.raises(TopologyDriftError, match="max_age"):
        await transport.ensure_topology()


@pytest.mark.asyncio
async def test_unauthenticated_or_non_tls_connection_refuses_before_topology(tmp_path) -> None:
    transport, _, _, _ = await _transport(
        tmp_path,
        security=ConnectionSecurity(False, False, "", ""),
    )
    with pytest.raises(CandidateTransportError, match="requires authentication"):
        await transport.ensure_topology()


@pytest.mark.asyncio
async def test_authenticated_non_tls_is_explicitly_loopback_only(tmp_path) -> None:
    transport, _, _, _ = await _transport(
        tmp_path,
        security=ConnectionSecurity(True, False, "loopback-nkey", "nkey-seed-file"),
    )
    await _install_exact_topology(transport, transport.jetstream)
    assert (await transport.ensure_topology())["status"] == "ok"
    with pytest.raises(CandidateTransportError, match="non-loopback.*require TLS"):
        CandidateTransportConfig(endpoint="nats://10.0.0.9:4222", require_tls=False)
    remote = CandidateTransportConfig(endpoint="tls://nats.example.test:4222", require_tls=True)
    assert remote.require_tls is True


def test_nkey_seed_configuration_binds_public_identity_without_seed_contents() -> None:
    public = "UD466L6EBCM3YY5HEGHJANNTN4LSKTSUXTH7RILHCKEQMQHTBNLHJJXT"
    config = CandidateTransportConfig(
        nkey_file="/run/credentials/foundry-rsi/nkey.seed",
        nkey_public_key=public,
    )
    assert config.nkey_public_key == public
    assert not hasattr(config, "nkey_seed_contents")
    with pytest.raises(CandidateTransportError, match="public user NKey"):
        CandidateTransportConfig(nkey_file="/private/seed")


@pytest.mark.parametrize(
    "overrides",
    (
        {"require_auth": False},
        {"ack_wait_s": float("nan")},
        {"publish_timeout_s": 0.0},
        {"subject": "dharma.foundry_rsi.*.v1"},
        {"dlq_subject": "dharma.foundry_rsi.candidate.v1"},
        {"dlq_stream_name": "FOUNDRY_RSI_CANDIDATES_V1"},
    ),
)
def test_transport_config_rejects_unsafe_auth_timing_and_topology(overrides) -> None:
    with pytest.raises(CandidateTransportError):
        CandidateTransportConfig(**overrides)


def test_private_auth_files_reject_symlinks_and_open_modes(tmp_path) -> None:
    seed = tmp_path / "seed.nk"
    seed.write_text("fixture", encoding="utf-8")
    seed.chmod(0o644)
    with pytest.raises(ValueError, match="mode-0600"):
        secure_private_file(str(seed), "NKey seed", root_owned=True)
    seed.chmod(0o600)
    alias = tmp_path / "seed-link.nk"
    alias.symlink_to(seed)
    with pytest.raises(ValueError, match="regular file"):
        secure_private_file(str(alias), "NKey seed", root_owned=True)


@pytest.mark.asyncio
async def test_publish_retries_with_stable_message_id_and_requires_puback(tmp_path) -> None:
    transport, js, _, signed = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    js.failures = 1

    first = await transport.publish(signed, now=_at(30))
    duplicate = await transport.publish(signed, now=_at(31))

    assert first.attempts == 2
    assert duplicate.duplicate is True
    assert js.published[0][2]["Nats-Msg-Id"] == signed.envelope.envelope_id
    assert js.published[0][2]["Dharma-Fence"] == "13"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state", (TerminalState.REFUSED, TerminalState.PROMOTED, TerminalState.CANARY_PASSED)
)
async def test_transport_rejects_already_terminal_candidate_revisions(tmp_path, state) -> None:
    submitted, key = _signed()
    derived = submitted.envelope.derive_terminal(
        TerminalDisposition(state, "already_terminal", "terminal-receipt", _at(10))
    )
    signed = sign_candidate_envelope(
        derived, signing_key=key, authority_epoch_sha256=_sha("source-epoch")
    )
    js = _JetStream()
    store = CandidateStore(tmp_path / "terminal.jsonl", experiment_id="lifecycle")
    await store.load()
    transport = CandidateJetStreamTransport(
        trusted_source_public_keys=[_public(key)], terminal_store=store,
        lease_verifier=_Lease(), jetstream=js,
        security=ConnectionSecurity(True, True, "candidate-test", "test-auth"),
    )
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    with pytest.raises(CandidateTransportError, match="genesis submitted"):
        await transport.publish(signed, now=_at(30))

    lease_sha = _sha("lease")
    wire = {
        "schema": NATS_ENVELOPE_SCHEMA,
        "kind": "candidate",
        "message_id": derived.envelope_id,
        "subject": transport.config.subject,
        "correlation_id": derived.correlation_id,
        "causation_id": derived.predecessor_envelope_id,
        "created_at": _at(30),
        "requires_ack": True,
        "lease_verification_sha256": lease_sha,
        "payload": {"schema": CANDIDATE_DELIVERY_SCHEMA, "signed_envelope": signed.to_dict()},
    }
    headers = {
        "Nats-Msg-Id": derived.envelope_id,
        "Dharma-Nats-Schema": NATS_ENVELOPE_SCHEMA,
        "Dharma-Candidate-Schema": CANDIDATE_DELIVERY_SCHEMA,
        "Dharma-Envelope-Id": derived.envelope_id,
        "Dharma-Correlation-Id": derived.correlation_id,
        "Dharma-Idempotency-Key": derived.idempotency_key,
        "Dharma-Fence": str(derived.fence),
        "Dharma-Lease-Verification": lease_sha,
    }
    result = await transport.consume(
        _Message(
            transport.config.subject,
            json.dumps(wire, sort_keys=True, separators=(",", ":")).encode(),
            headers=headers,
        ),
        lambda _: None,
        now=_at(30),
    )
    assert result.action == "dlq" and "genesis submitted" in result.error


@pytest.mark.asyncio
async def test_publish_rejects_pre_creation_time_and_every_lease_binding_mismatch(tmp_path) -> None:
    transport, js, _, signed = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    with pytest.raises(CandidateTransportError, match="future"):
        await transport.publish(signed, now=_at(-1))
    for index, override in enumerate((
        {"candidate_id": "other-candidate"},
        {"envelope_id": "f" * 64},
        {"required_scope": "other.scope"},
        {"verified_at": _at(29)},
    )):
        other, other_js, _, other_signed = await _transport(
            tmp_path / f"binding-{index}", lease=_Lease(**override)
        )
        await _install_exact_topology(other, other_js)
        await other.ensure_topology()
        with pytest.raises(CandidateTransportError, match="lease refused"):
            await other.publish(other_signed, now=_at(30))


@pytest.mark.asyncio
async def test_consume_persists_before_ack_and_redelivery_is_idempotent(tmp_path) -> None:
    transport, js, store, signed = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    await transport.publish(signed, now=_at(30))
    _, data, headers = js.published[0]
    calls = 0

    async def handler(received):
        nonlocal calls
        calls += 1
        return CandidateHandlingResult(
            disposition=TerminalDisposition(
                state=TerminalState.EVALUATED,
                reason_code="foundry_evaluated",
                receipt_id="foundry-eval-receipt",
                at=_at(40),
            ),
            transport_receipt_id="consume-receipt",
            evaluation_receipt_sha256=_sha("foundry-eval"),
        )

    first_message = _Message(transport.config.subject, data, headers=headers)
    duplicate_message = _Message(transport.config.subject, data, headers=headers, deliveries=2)
    first = await transport.consume(first_message, handler, now=_at(40))
    duplicate = await transport.consume(duplicate_message, handler, now=_at(41))

    assert first.disposition == "evaluated"
    assert duplicate.duplicate is True
    assert first_message.acked == duplicate_message.acked == 1
    assert calls == 1
    assert await store.latest_terminal(
        candidate_id=signed.envelope.candidate_id,
        envelope_id=signed.envelope.envelope_id,
    ) is not None


@pytest.mark.asyncio
async def test_transient_failure_naks_with_backoff_then_redelivery_succeeds(tmp_path) -> None:
    transport, js, _, signed = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    await transport.publish(signed, now=_at(30))
    calls = 0

    async def handler(received):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary evaluator outage")
        return CandidateHandlingResult(
            TerminalDisposition(TerminalState.EVALUATED, "recovered", "eval-2", _at(42)),
            "consume-2",
        )

    _, data, headers = js.published[0]
    first = _Message(transport.config.subject, data, headers=headers, deliveries=1)
    with pytest.raises(CandidateTransportError, match="will retry"):
        await transport.consume(first, handler, now=_at(40))
    second = _Message(transport.config.subject, data, headers=headers, deliveries=2)
    result = await transport.consume(second, handler, now=_at(42))

    assert first.nak_delays == [60.0]
    assert result.disposition == "evaluated"
    assert calls == 2


@pytest.mark.asyncio
async def test_max_delivery_publishes_durable_dlq_then_acks_original(tmp_path) -> None:
    transport, js, store, signed = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    await transport.publish(signed, now=_at(30))

    async def poison(received):
        raise RuntimeError("poison candidate")

    _, data, headers = js.published[0]
    message = _Message(transport.config.subject, data, headers=headers, deliveries=4)
    result = await transport.consume(message, poison, now=_at(50))

    assert result.action == "dlq"
    assert result.disposition == "dead_lettered"
    assert message.acked == 1 and message.nacked == 0
    assert js.published[-1][0] == transport.config.dlq_subject
    terminal = await store.latest_terminal(
        candidate_id=signed.envelope.candidate_id,
        envelope_id=signed.envelope.envelope_id,
    )
    assert terminal["terminal"]["disposition"]["state"] == "dead_lettered"


@pytest.mark.asyncio
async def test_final_delivery_dlq_failure_is_recovered_from_durable_outbox(tmp_path) -> None:
    transport, js, store, signed = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    await transport.publish(signed, now=_at(30))
    _, data, headers = js.published[0]
    js.failures = transport.config.publish_attempts

    async def poison(received):
        raise RuntimeError("poison candidate")

    message = _Message(transport.config.subject, data, headers=headers, deliveries=4)
    with pytest.raises(CandidateTransportError, match="durable in the outbox"):
        await transport.consume(message, poison, now=_at(50))
    assert message.acked == 0 and message.nacked == 1
    assert len(await store.pending_dlq_outbox()) == 1

    reconciled = await transport.reconcile_dlq_outbox(now=_at(51))
    assert len(reconciled["delivered"]) == 1
    assert await store.pending_dlq_outbox() == []
    terminal = await store.latest_terminal(
        candidate_id=signed.envelope.candidate_id,
        envelope_id=signed.envelope.envelope_id,
    )
    assert terminal["terminal"]["disposition"]["state"] == "dead_lettered"


@pytest.mark.asyncio
async def test_malformed_outer_wire_is_terminal_and_delivery_count_is_clamped(tmp_path) -> None:
    transport, js, store, _ = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    message = _Message(transport.config.subject, b"[]", deliveries=0)

    result = await transport.consume(message, lambda _: None, now=_at(30))

    assert result.action == "dlq" and message.acked == 1
    dlq = json.loads(js.published[-1][1])
    assert dlq["payload"]["reason_code"] == "candidate_wire_invalid"
    assert dlq["payload"]["delivery_count"] == 1
    assert await store.pending_dlq_outbox() == []


@pytest.mark.asyncio
async def test_malformed_dlq_redelivery_after_source_ack_crash_converges(tmp_path) -> None:
    transport, js, store, _ = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()

    class _AckCrash(_Message):
        async def ack(self):
            self.acked += 1
            raise RuntimeError("simulated crash after DLQ delivery")

    first = _AckCrash(transport.config.subject, b"[]", deliveries=1)
    with pytest.raises(RuntimeError, match="simulated crash"):
        await transport.consume(first, lambda _: None, now=_at(30))
    assert len(js.published) == 1
    assert await store.pending_dlq_outbox() == []

    redelivery = _Message(transport.config.subject, b"[]", deliveries=4)
    result = await transport.consume(redelivery, lambda _: None, now=_at(50))
    assert result.action == "dlq" and result.duplicate is True
    assert redelivery.acked == 1
    assert len(js.published) == 1
    rows = [
        CandidateStore._row(entry)
        for entry in store.archive._entries.values()
        if CandidateStore._row(entry).get("state") == "dlq_pending"
    ]
    assert len(rows) == 1
    assert rows[0]["created_at"] == _at(30)
    assert rows[0]["wire"]["payload"]["delivery_count"] == 1


@pytest.mark.asyncio
async def test_outer_metadata_and_headers_must_bind_signed_envelope(tmp_path) -> None:
    transport, js, _, signed = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    await transport.publish(signed, now=_at(30))
    subject, data, headers = js.published[0]
    wire = json.loads(data)
    wire["correlation_id"] = "rewritten"
    message = _Message(
        subject,
        json.dumps(wire, sort_keys=True, separators=(",", ":")).encode(),
        headers=headers,
    )
    assert (await transport.consume(message, lambda _: None, now=_at(40))).action == "dlq"

    second = _Message(subject, data, headers={**headers, "Dharma-Fence": "999"})
    assert (await transport.consume(second, lambda _: None, now=_at(41))).action == "dlq"

    missing = _Message(subject, data)
    assert (await transport.consume(missing, lambda _: None, now=_at(42))).action == "dlq"
    extra = _Message(subject, data, headers={**headers, "Dharma-Unbound": "injected"})
    assert (await transport.consume(extra, lambda _: None, now=_at(43))).action == "dlq"


@pytest.mark.asyncio
async def test_wire_rejects_noncanonical_and_duplicate_key_json(tmp_path) -> None:
    transport, js, _, signed = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    await transport.publish(signed, now=_at(30))
    subject, data, headers = js.published[0]

    whitespace = _Message(subject, data + b"\n", headers=headers)
    assert (await transport.consume(whitespace, lambda _: None, now=_at(40))).action == "dlq"
    duplicate_data = data.replace(b'{"causation_id":', b'{"causation_id":"injected","causation_id":', 1)
    duplicate = _Message(subject, duplicate_data, headers=headers)
    assert (await transport.consume(duplicate, lambda _: None, now=_at(41))).action == "dlq"


@pytest.mark.asyncio
async def test_wire_lease_receipt_must_match_current_exact_verification(tmp_path) -> None:
    transport, js, _, signed = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    await transport.publish(signed, now=_at(30))
    subject, data, headers = js.published[0]
    rewritten_digest = _sha("unrelated-lease-verification")
    wire = json.loads(data)
    wire["lease_verification_sha256"] = rewritten_digest
    rewritten = json.dumps(wire, sort_keys=True, separators=(",", ":")).encode()
    message = _Message(
        subject,
        rewritten,
        headers={**headers, "Dharma-Lease-Verification": rewritten_digest},
    )
    result = await transport.consume(message, lambda _: None, now=_at(40))
    assert result.action == "dlq"
    assert "lease receipt" in result.error


@pytest.mark.asyncio
async def test_wire_enforces_configured_bound_on_actual_envelope_lifetime(tmp_path) -> None:
    transport, js, store, signed = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    await transport.publish(signed, now=_at(30))
    subject, data, headers = js.published[0]
    restricted = CandidateJetStreamTransport(
        trusted_source_public_keys=(),
        terminal_store=store,
        lease_verifier=_Lease(),
        config=CandidateTransportConfig(max_candidate_lifetime_s=60),
        jetstream=js,
        security=ConnectionSecurity(True, True, "candidate-test", "test-auth"),
    )
    await restricted.ensure_topology()
    result = await restricted.consume(
        _Message(subject, data, headers=headers), lambda _: None, now=_at(40)
    )
    assert result.action == "dlq"
    assert "configured lifetime bound" in result.error


@pytest.mark.asyncio
async def test_expired_or_wrong_fence_never_reaches_handler(tmp_path) -> None:
    transport, js, _, signed = await _transport(tmp_path)
    await _install_exact_topology(transport, js)
    await transport.ensure_topology()
    await transport.publish(signed, now=_at(30))
    called = False

    async def handler(received):
        nonlocal called
        called = True

    _, data, headers = js.published[0]
    expired = _Message(transport.config.subject, data, headers=headers)
    result = await transport.consume(expired, handler, now=_at(301))
    assert result.action == "dlq" and result.disposition == "expired"
    assert called is False
    terminal = await transport.terminal_store.latest_terminal(
        candidate_id=signed.envelope.candidate_id,
        envelope_id=signed.envelope.envelope_id,
    )
    assert terminal["terminal"]["disposition"]["at"] == signed.envelope.expires_at

    other, other_js, _, other_signed = await _transport(tmp_path / "wrong", lease=_Lease(wrong_fence=True))
    await _install_exact_topology(other, other_js)
    await other.ensure_topology()
    # Publish itself fails closed on a mismatched fence attestation.
    with pytest.raises(CandidateTransportError, match="lease refused"):
        await other.publish(other_signed, now=_at(30))
    assert other_js.published == []


@pytest.mark.asyncio
async def test_disposable_authenticated_real_jetstream_round_trip(tmp_path, monkeypatch) -> None:
    import secrets
    import shutil
    import socket
    import subprocess
    import sys
    import time

    pytest.importorskip("nats")
    server = shutil.which("nats-server")
    if server is None:
        pytest.skip("nats-server is unavailable")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    username = "candidate_fixture"
    password = secrets.token_urlsafe(24)
    config_path = tmp_path / "nats.conf"
    store_path = tmp_path / "jetstream"
    config_path.write_text(
        "\n".join(
            (
                f"listen: 127.0.0.1:{port}",
                f"jetstream {{ store_dir: {store_path!s} }}",
                "authorization {",
                "  users = [",
                f'    {{ user: "{username}", password: "{password}" }}',
                "  ]",
                "}",
            )
        ),
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [server, "-c", str(config_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.05):
                    break
            except OSError:
                if process.poll() is not None:
                    pytest.fail("disposable nats-server exited before readiness")
                time.sleep(0.05)
        else:
            pytest.fail("disposable nats-server did not become ready")
        monkeypatch.setenv("FOUNDRY_RSI_TEST_NATS_USER", username)
        monkeypatch.setenv("FOUNDRY_RSI_TEST_NATS_PASSWORD", password)
        signed, key = _signed()
        terminal_store = CandidateStore(tmp_path / "real-terminal.jsonl", experiment_id="real-js")
        await terminal_store.load()
        transport = CandidateJetStreamTransport(
            trusted_source_public_keys=[_public(key)],
            terminal_store=terminal_store,
            lease_verifier=_Lease(),
            config=CandidateTransportConfig(
                endpoint=f"nats://127.0.0.1:{port}",
                require_tls=False,
                username_env="FOUNDRY_RSI_TEST_NATS_USER",
                password_env="FOUNDRY_RSI_TEST_NATS_PASSWORD",
            ),
        )
        await transport.connect()
        desired = transport.desired_topology()
        for expected in desired["streams"].values():
            await transport.jetstream.add_stream(config=transport._stream_config(expected))
        await transport.jetstream.add_consumer(
            transport.config.stream_name,
            config=transport._consumer_config(desired["consumer"]),
        )
        topology = await transport.ensure_topology()
        first = await transport.publish(signed, now=_at(30))
        duplicate = await transport.publish(signed, now=_at(31))
        subscription = await transport.jetstream.pull_subscribe_bind(
            stream=transport.config.stream_name,
            consumer=transport.config.consumer_name,
        )
        messages = await subscription.fetch(1, timeout=2)

        async def handler(received):
            return CandidateHandlingResult(
                TerminalDisposition(TerminalState.EVALUATED, "real_js_pass", "real-js-eval", _at(40)),
                "real-js-consume",
                _sha("real-js-evaluation"),
            )

        consumed = await transport.consume(messages[0], handler, now=_at(40))
        assert topology["status"] == "ok"
        assert first.stream == transport.config.stream_name
        assert duplicate.duplicate is True
        assert consumed.disposition == "evaluated"
        await transport.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.asyncio
async def test_disposable_real_nkey_provision_and_receipted_rollback(tmp_path) -> None:
    import shutil
    import socket
    import subprocess
    import sys
    import time

    pytest.importorskip("nats")
    server, cli = shutil.which("nats-server"), shutil.which("nats")
    if server is None or cli is None:
        pytest.skip("nats-server or nats CLI is unavailable")
    seed = tmp_path / "provisioner.nk"
    subprocess.run(
        [cli, "auth", "nkey", "gen", "user", "--output", str(seed)],
        check=True, text=True, capture_output=True,
    )
    seed.chmod(0o600)
    public_nkey = subprocess.run(
        [cli, "auth", "nkey", "show", str(seed)],
        check=True, text=True, capture_output=True,
    ).stdout.strip()
    manifest = json.loads(subprocess.run(
        [
            sys.executable,
            "scripts/forge_lab/nats-foundry-rsi-topology-v1",
            "--provisioner-nkey", public_nkey,
            "--publisher-nkey", "UDM3NS6Q66CDRMAW4DQ7VPWMCWYK6LMEJLYTMYWPFH2Y6A6A2VJIA42W",
            "--consumer-nkey", "UBAFW3IITXG5LA47A2WCE6RP2HY2N3ZEBEXLKE2SF5EH7RNJTXFUYMRS",
        ],
        check=True, text=True, capture_output=True,
    ).stdout)
    provisioner_acl = next(
        item for item in manifest["acl_users"] if item["role"] == "topology_provisioner"
    )["permissions"]
    assert "dharma.foundry_rsi.candidate.v1" not in provisioner_acl["publish"]
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    config_path = tmp_path / "nkey-nats.conf"
    config_path.write_text(
        "\n".join((
            f"listen: 127.0.0.1:{port}",
            f"jetstream {{ store_dir: {tmp_path / 'nkey-js'} }}",
            "authorization { users = [",
            f'  {{ nkey: "{public_nkey}", permissions: {{ '
            f'publish: {json.dumps(provisioner_acl["publish"])}, '
            f'subscribe: {json.dumps(provisioner_acl["subscribe"])} }} }}',
            "] }",
        )),
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [server, "-c", str(config_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    try:
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.05):
                    break
            except OSError:
                if process.poll() is not None:
                    pytest.fail("disposable NKey NATS exited before readiness")
                time.sleep(0.05)
        else:
            pytest.fail("disposable NKey NATS did not become ready")
        store = CandidateStore(tmp_path / "nkey-terminal.jsonl", experiment_id="nkey-topology")
        await store.load()
        transport = CandidateJetStreamTransport(
            trusted_source_public_keys=(), terminal_store=store, lease_verifier=None,
            config=CandidateTransportConfig(
                endpoint=f"nats://127.0.0.1:{port}",
                nkey_file=str(seed), nkey_public_key=public_nkey,
            ),
        )
        await transport.connect()
        receipt = tmp_path / "real-topology-operation.json"
        provisioned = await transport.provision_topology(receipt_path=receipt, now=_at())
        assert provisioned["state"] == "complete"
        assert (await transport.ensure_topology())["status"] == "ok"
        rolled_back = await transport.rollback_topology(receipt_path=receipt, now=_at(1))
        assert rolled_back["state"] == "rollback_complete"
        with pytest.raises(Exception):
            await transport.jetstream.stream_info(transport.config.stream_name)
        with pytest.raises(Exception):
            await transport.jetstream.stream_info(transport.config.dlq_stream_name)
        await transport.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
