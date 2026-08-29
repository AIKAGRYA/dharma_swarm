"""Authenticated, drift-refusing JetStream lane for RSI candidate envelopes."""
from __future__ import annotations
import asyncio
import hashlib
import inspect
import json
import os
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Mapping, Protocol
from dharma_swarm.a2a.candidate_lease import (
    LeaseVerification, OperatorLeaseVerifier, lease_result_is_exact,
)
from dharma_swarm.a2a.candidate_transport_contract import (
    CandidateContractError, nkey_signature_from_seed_file, parse_candidate_wire,
    prove_nkey_seed_identity, secure_private_file,
    secure_public_file, validate_candidate_config,
)
from dharma_swarm.a2a.candidate_topology_receipt import (
    TOPOLOGY_OPERATION_SCHEMA,
    TopologyOperationLock,
    TopologyReceiptError,
    read_topology_receipt,
    write_topology_receipt,
)
from dharma_swarm.a2a.nats_transport_support import (
    NATS_ENVELOPE_SCHEMA, _ack, _message_delivery_count,
    _nats_endpoint_uses_tls, _normalize_nats_topology_value, _operation_hash,
)
from dharma_swarm.forge_lab.candidate_envelope import SignedCandidateEnvelope, TerminalDisposition, TerminalState
from dharma_swarm.forge_lab.candidate_store import CandidateStore
from dharma_swarm.forge_lab.promotion_controller import _now
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
CANDIDATE_DELIVERY_SCHEMA = "forge_lab.candidate_delivery.v1"
CANDIDATE_DLQ_SCHEMA = "forge_lab.candidate_dlq.v1"
class CandidateTransportError(RuntimeError):
    pass
class TerminalCandidateTransportError(CandidateTransportError):
    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code
class TopologyDriftError(CandidateTransportError):
    pass
class JetStreamLike(Protocol):
    async def publish(self, subject: str, payload: bytes, **kwargs: Any) -> Any: ...
class MessageLike(Protocol):
    subject: str
    data: bytes
    async def ack(self) -> Any: ...
    async def nak(self, **kwargs: Any) -> Any: ...
@dataclass(frozen=True)
class ConnectionSecurity:
    authenticated: bool
    tls: bool
    principal: str
    mechanism: str
    def __post_init__(self) -> None:
        if self.authenticated and (not self.principal or not self.mechanism):
            raise CandidateTransportError("authenticated connection requires principal and mechanism")
@dataclass(frozen=True)
class CandidateTransportConfig:
    endpoint: str = "nats://127.0.0.1:4222"
    subject: str = "dharma.foundry_rsi.candidate.v1"
    dlq_subject: str = "dharma.foundry_rsi.candidate.dlq.v1"
    stream_name: str = "FOUNDRY_RSI_CANDIDATES_V1"
    dlq_stream_name: str = "FOUNDRY_RSI_CANDIDATES_DLQ_V1"
    consumer_name: str = "foundry_rsi_evaluator_v1"
    max_deliveries: int = 4
    ack_wait_s: float = 60.0
    backoff_s: tuple[float, ...] = (60.0, 300.0, 900.0)
    max_age_s: float = 7 * 24 * 60 * 60
    dlq_max_age_s: float = 30 * 24 * 60 * 60
    duplicate_window_s: float = 10 * 60
    max_bytes: int = 512 * 1024 * 1024
    max_message_bytes: int = 8 * 1024 * 1024
    publish_timeout_s: float = 3.0
    publish_attempts: int = 3
    publish_backoff_s: tuple[float, ...] = (0.25, 1.0)
    max_clock_skew_s: float = 5.0
    max_candidate_lifetime_s: float = 24 * 60 * 60
    require_tls: bool = False
    require_auth: bool = True
    credentials_path: str = ""
    tls_ca_path: str = ""
    tls_cert_path: str = ""
    tls_key_path: str = ""
    nkey_file: str = ""
    nkey_public_key: str = ""
    username_env: str = ""
    password_env: str = ""
    def __post_init__(self) -> None:
        try:
            validate_candidate_config(self)
        except CandidateContractError as exc:
            raise CandidateTransportError(str(exc)) from exc
@dataclass(frozen=True)
class CandidatePublishAck:
    envelope_id: str
    stream: str
    seq: int
    duplicate: bool
    attempts: int
    receipt_id: str
@dataclass(frozen=True)
class CandidateHandlingResult:
    disposition: TerminalDisposition
    transport_receipt_id: str
    evaluation_receipt_sha256: str = ""
    def __post_init__(self) -> None:
        if not self.disposition.state.final:
            raise CandidateTransportError("candidate handler must return a final disposition")
        if not self.transport_receipt_id or any(ord(ch) < 32 for ch in self.transport_receipt_id):
            raise CandidateTransportError("candidate handler transport receipt id is invalid")
        digest = self.evaluation_receipt_sha256
        if digest and (len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest)):
            raise CandidateTransportError("candidate handler evaluation receipt digest is invalid")
@dataclass(frozen=True)
class CandidateConsumeAck:
    action: str
    envelope_id: str
    disposition: str
    duplicate: bool = False
    error: str = ""
def _field(config: Any, name: str) -> Any:
    if isinstance(config, Mapping):
        return config.get(name)
    return getattr(config, name, None)
def _config(info: Any) -> Any:
    return _field(info, "config") or info
def _not_found(exc: Exception) -> bool:
    code = str(getattr(exc, "err_code", "") or getattr(exc, "code", ""))
    return code in {"404", "10014", "10059"} or "not found" in str(exc).lower()
async def _maybe(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value
class CandidateJetStreamTransport:
    def __init__(
        self,
        *,
        trusted_source_public_keys: Iterable[str | bytes],
        terminal_store: CandidateStore,
        lease_verifier: OperatorLeaseVerifier | None,
        config: CandidateTransportConfig | None = None,
        jetstream: JetStreamLike | None = None,
        security: ConnectionSecurity | None = None,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    ) -> None:
        self.config = config or CandidateTransportConfig()
        self.trusted_source_public_keys = tuple(trusted_source_public_keys)
        self.terminal_store = terminal_store
        self.lease_verifier = lease_verifier
        self.jetstream = jetstream
        self.security = security
        self.sleep = sleep
        self._connection: Any | None = None
        self._topology_sha256 = ""
        self._nkey_identity_sha256 = ""
    def _require_security(self) -> None:
        if self.security is None:
            raise CandidateTransportError("NATS connection security is unattested")
        if self.config.require_auth and not self.security.authenticated:
            raise CandidateTransportError("dedicated candidate lane requires authentication")
        tls_required = self.config.require_tls or _nats_endpoint_uses_tls(self.config.endpoint)
        if tls_required and not self.security.tls:
            raise CandidateTransportError("dedicated candidate lane requires TLS")
    async def connect(self) -> None:
        if self.jetstream is not None:
            self._require_security()
            return
        import nats
        options: dict[str, Any] = {
            "servers": [self.config.endpoint],
            "name": "foundry-rsi-candidate-v1",
            "allow_reconnect": False,
            "max_reconnect_attempts": 0,
        }
        mechanism = ""
        principal = ""
        try:
            credentials = (
                secure_private_file(self.config.credentials_path, "NATS credentials")
                if self.config.credentials_path else None
            )
            seed = (
                secure_private_file(self.config.nkey_file, "NKey seed", root_owned=True)
                if self.config.nkey_file else None
            )
            if seed is not None:
                proven_public = prove_nkey_seed_identity(
                    str(seed), self.config.nkey_public_key,
                )
                self._nkey_identity_sha256 = canonical_sha256({
                    "schema": "forge_lab.nkey_identity_proof.v1",
                    "public_nkey": proven_public,
                })
            tls_key = (
                secure_private_file(self.config.tls_key_path, "TLS private key")
                if self.config.tls_key_path else None
            )
            tls_cert = (
                secure_public_file(self.config.tls_cert_path, "TLS certificate")
                if self.config.tls_cert_path else None
            )
            tls_ca = (
                secure_public_file(self.config.tls_ca_path, "TLS CA")
                if self.config.tls_ca_path else None
            )
        except CandidateContractError as exc:
            raise CandidateTransportError(str(exc)) from exc
        nkey_seed_path = ""
        if credentials is not None:
            options["user_credentials"] = str(credentials)
            mechanism, principal = "nats-creds", credentials.name
        elif seed is not None:
            nkey_seed_path = str(seed)
            mechanism, principal = "nkey-seed-file", self.config.nkey_public_key
        elif self.config.username_env and self.config.password_env:
            username = os.environ.get(self.config.username_env, "")
            password = os.environ.get(self.config.password_env, "")
            if not username or not password:
                raise CandidateTransportError("configured NATS auth environment is incomplete")
            options.update(user=username, password=password)
            mechanism, principal = "user-password-env", self.config.username_env
        elif tls_cert is not None and tls_key is not None:
            mechanism, principal = "mutual-tls", tls_cert.name
        elif self.config.require_auth:
            raise CandidateTransportError("no authenticated NATS credential source is configured")
        tls_context: ssl.SSLContext | None = None
        if self.config.require_tls or _nats_endpoint_uses_tls(self.config.endpoint) or self.config.tls_ca_path:
            tls_context = ssl.create_default_context(
                cafile=str(tls_ca) if tls_ca else None,
            )
            if tls_cert is not None and tls_key is not None:
                tls_context.load_cert_chain(str(tls_cert), str(tls_key))
            options["tls"] = tls_context
        if nkey_seed_path:
            from nats.aio.client import Client

            connection = Client()
            # nats-py 2.x exposes a signature callback but no public-NKey
            # callback. Set the already-validated public identity before its
            # CONNECT builder runs; the private seed is read only per nonce.
            connection._public_nkey = self.config.nkey_public_key
            connection._auth_configured = True
            options["signature_cb"] = lambda nonce: nkey_signature_from_seed_file(
                nkey_seed_path, nonce
            )
            await connection.connect(**options)
            self._connection = connection
        else:
            self._connection = await nats.connect(**options)
        self.jetstream = self._connection.jetstream()
        self.security = ConnectionSecurity(
            authenticated=bool(mechanism),
            tls=tls_context is not None,
            principal=principal or "unauthenticated",
            mechanism=mechanism or "none",
        )
        self._require_security()
    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
    def desired_topology(self) -> dict[str, Any]:
        common = {
            "retention": "limits", "storage": "file", "discard": "new",
            "max_msgs": -1, "max_bytes": self.config.max_bytes,
            "max_msg_size": self.config.max_message_bytes,
            "duplicate_window": self.config.duplicate_window_s,
            "num_replicas": 1, "deny_delete": False, "deny_purge": True,
            "allow_rollup_hdrs": False,
        }
        return {
            "streams": {
                self.config.stream_name: {
                    "name": self.config.stream_name, "subjects": (self.config.subject,),
                    "max_age": self.config.max_age_s, **common,
                },
                self.config.dlq_stream_name: {
                    "name": self.config.dlq_stream_name, "subjects": (self.config.dlq_subject,),
                    "max_age": self.config.dlq_max_age_s, **common,
                },
            },
            "consumer": {
                "durable_name": self.config.consumer_name,
                "filter_subject": self.config.subject,
                "ack_policy": "explicit", "ack_wait": self.config.ack_wait_s,
                "max_deliver": self.config.max_deliveries,
                "backoff": self.config.backoff_s, "deliver_policy": "all",
                "replay_policy": "instant", "max_ack_pending": 1,
            },
        }
    async def _inspect_topology(self, desired: Mapping[str, Any]) -> dict[str, bool]:
        present: dict[str, bool] = {}
        for name, expected in desired["streams"].items():
            label = f"stream:{name}"
            try:
                info = await self.jetstream.stream_info(name)
            except Exception as exc:
                if not _not_found(exc):
                    raise TopologyDriftError(f"stream inspection failed for {name}: {exc}") from exc
                present[label] = False
            else:
                self._assert_exact(_config(info), expected, label)
                present[label] = True
        consumer = desired["consumer"]
        label = f"consumer:{self.config.stream_name}:{self.config.consumer_name}"
        try:
            info = await self.jetstream.consumer_info(
                self.config.stream_name, self.config.consumer_name
            )
        except Exception as exc:
            if not _not_found(exc):
                raise TopologyDriftError(f"consumer inspection failed: {exc}") from exc
            present[label] = False
        else:
            self._assert_exact(_config(info), consumer, label)
            present[label] = True
        return present

    def _prove_provisioner_identity(self) -> str:
        if (
            self.security is None
            or self.security.mechanism != "nkey-seed-file"
            or self.security.principal != self.config.nkey_public_key
            or not self.config.nkey_file
        ):
            raise CandidateTransportError(
                "topology mutation requires the dedicated provisioner NKey identity"
            )
        try:
            public_nkey = prove_nkey_seed_identity(
                self.config.nkey_file, self.config.nkey_public_key
            )
        except CandidateContractError as exc:
            raise CandidateTransportError(str(exc)) from exc
        proof = canonical_sha256({
            "schema": "forge_lab.nkey_identity_proof.v1",
            "public_nkey": public_nkey,
        })
        self._nkey_identity_sha256 = proof
        return proof

    async def ensure_topology(self, *, create_missing: bool = False) -> dict[str, Any]:
        if self.jetstream is None:
            await self.connect()
        self._require_security()
        if not all(hasattr(self.jetstream, name) for name in (
            "stream_info", "add_stream", "consumer_info", "add_consumer",
        )):
            raise TopologyDriftError("JetStream topology inspection APIs are required")
        if create_missing:
            raise TopologyDriftError(
                "unreceipted topology creation is disabled; use provision_topology"
            )
        desired = self.desired_topology()
        present = await self._inspect_topology(desired)
        missing = [label for label, exists in present.items() if not exists]
        if missing:
            raise TopologyDriftError(f"required candidate topology is missing: {', '.join(missing)}")
        self._topology_sha256 = canonical_sha256(desired)
        return {"status": "ok", "topology_sha256": self._topology_sha256, "created": []}

    async def provision_topology(self, *, receipt_path: Path | str, now: str) -> dict[str, Any]:
        """Serialize and journal one crash-reconcilable topology operation."""

        operation_lock = TopologyOperationLock(receipt_path)
        try:
            await asyncio.to_thread(operation_lock.acquire)
            return await self._provision_topology_locked(
                receipt_path=receipt_path,
                now=now,
                operation_lock=operation_lock,
            )
        finally:
            operation_lock.release()

    async def _provision_topology_locked(
        self,
        *,
        receipt_path: Path | str,
        now: str,
        operation_lock: TopologyOperationLock,
    ) -> dict[str, Any]:
        """Create an all-absent topology with a pre-state journal and crash recovery."""

        if self.jetstream is None:
            await self.connect()
        self._require_security()
        required = (
            "stream_info", "add_stream", "delete_stream", "consumer_info",
            "add_consumer", "delete_consumer",
        )
        if not all(hasattr(self.jetstream, name) for name in required):
            raise TopologyDriftError("rollback-capable JetStream provisioning APIs are required")
        identity_proof = self._prove_provisioner_identity()
        desired = self.desired_topology()
        topology_sha256 = canonical_sha256(desired)
        timestamp = _now(now).isoformat().replace("+00:00", "Z")
        target = Path(receipt_path)
        try:
            if target.exists() or target.is_symlink():
                receipt = read_topology_receipt(target, operation_lock=operation_lock)
                expected_binding = {
                    "endpoint": self.config.endpoint,
                    "topology_sha256": topology_sha256,
                    "provisioner_public_nkey": self.config.nkey_public_key,
                    "nkey_identity_proof_sha256": identity_proof,
                }
                if any(receipt.get(key) != value for key, value in expected_binding.items()):
                    raise TopologyReceiptError("topology receipt belongs to a different operation")
                if receipt["state"] == "rollback_complete":
                    raise TopologyReceiptError("rolled-back topology operation cannot be resumed")
            else:
                present = await self._inspect_topology(desired)
                operation_id = canonical_sha256({
                    "schema": TOPOLOGY_OPERATION_SCHEMA,
                    "endpoint": self.config.endpoint,
                    "topology_sha256": topology_sha256,
                    "provisioner_public_nkey": self.config.nkey_public_key,
                    "started_at": timestamp,
                })
                receipt = {
                    "schema": TOPOLOGY_OPERATION_SCHEMA,
                    "operation_id": operation_id,
                    "endpoint": self.config.endpoint,
                    "topology_sha256": topology_sha256,
                    "provisioner_public_nkey": self.config.nkey_public_key,
                    "nkey_identity_proof_sha256": identity_proof,
                    "pre_state": {
                        label: {"present": exists} for label, exists in present.items()
                    },
                    "created_resources": [],
                    "removed_resources": [],
                    "state": "in_progress",
                    "events": [{"at": timestamp, "action": "pre_state_recorded"}],
                    "live_promotion_attempted": False,
                    "snapshot_sha256": "",
                }
                values = set(present.values())
                if len(values) > 1:
                    receipt["state"] = "refused_partial_pre_state"
                    receipt["events"].append({
                        "at": timestamp, "action": "partial_pre_state_refused"
                    })
                    write_topology_receipt(
                        target, receipt, operation_lock=operation_lock,
                    )
                    raise TopologyDriftError(
                        "partial candidate topology has no matching operation journal"
                    )
                if values == {True}:
                    receipt["state"] = "complete"
                    receipt["events"].append({"at": timestamp, "action": "verified_existing"})
                    receipt = write_topology_receipt(
                        target, receipt, operation_lock=operation_lock,
                    )
                    self._topology_sha256 = topology_sha256
                    return receipt
                receipt = write_topology_receipt(
                    target, receipt, operation_lock=operation_lock,
                )

            present = await self._inspect_topology(desired)
            for label, before in receipt["pre_state"].items():
                if before.get("present") and not present.get(label):
                    raise TopologyDriftError(f"pre-existing topology resource disappeared: {label}")
                if not before.get("present") and present.get(label) and label not in receipt["created_resources"]:
                    receipt["created_resources"].append(label)
                    receipt["events"].append({
                        "at": timestamp, "action": "reconciled_created", "resource": label,
                    })
                    receipt = write_topology_receipt(
                        target, receipt, operation_lock=operation_lock,
                    )

            resources: list[tuple[str, str, Mapping[str, Any]]] = [
                (f"stream:{name}", "stream", config)
                for name, config in desired["streams"].items()
            ]
            resources.append((
                f"consumer:{self.config.stream_name}:{self.config.consumer_name}",
                "consumer", desired["consumer"],
            ))
            for label, kind, expected in resources:
                if present[label]:
                    continue
                try:
                    if kind == "stream":
                        await self.jetstream.add_stream(config=self._stream_config(expected))
                    else:
                        await self.jetstream.add_consumer(
                            self.config.stream_name,
                            config=self._consumer_config(expected),
                        )
                    checked = await self._inspect_topology(desired)
                    if not checked[label]:
                        raise TopologyDriftError(f"created topology resource is missing: {label}")
                    present = checked
                    if label not in receipt["created_resources"]:
                        receipt["created_resources"].append(label)
                    receipt["events"].append({
                        "at": timestamp, "action": "created", "resource": label,
                    })
                    receipt = write_topology_receipt(
                        target, receipt, operation_lock=operation_lock,
                    )
                except Exception as exc:
                    try:
                        reconciled = await self._inspect_topology(desired)
                        if reconciled.get(label) and label not in receipt["created_resources"]:
                            receipt["created_resources"].append(label)
                    except Exception:
                        pass
                    receipt["state"] = "failed_recoverable"
                    receipt["events"].append({
                        "at": timestamp,
                        "action": "creation_failed",
                        "resource": label,
                        "error_type": type(exc).__name__,
                    })
                    write_topology_receipt(
                        target, receipt, operation_lock=operation_lock,
                    )
                    raise TopologyDriftError(
                        f"topology creation failed; reconcile or roll back via {target}"
                    ) from exc
            receipt["state"] = "complete"
            receipt["events"].append({"at": timestamp, "action": "provision_complete"})
            receipt = write_topology_receipt(
                target, receipt, operation_lock=operation_lock,
            )
        except TopologyReceiptError as exc:
            raise TopologyDriftError(str(exc)) from exc
        self._topology_sha256 = topology_sha256
        return receipt

    async def rollback_topology(self, *, receipt_path: Path | str, now: str) -> dict[str, Any]:
        """Serialize rollback against the same durable operation journal."""

        operation_lock = TopologyOperationLock(receipt_path)
        try:
            await asyncio.to_thread(operation_lock.acquire)
            return await self._rollback_topology_locked(
                receipt_path=receipt_path,
                now=now,
                operation_lock=operation_lock,
            )
        finally:
            operation_lock.release()

    async def _rollback_topology_locked(
        self,
        *,
        receipt_path: Path | str,
        now: str,
        operation_lock: TopologyOperationLock,
    ) -> dict[str, Any]:
        """Delete only exact resources proven created by the bound operation journal."""

        if self.jetstream is None:
            await self.connect()
        self._require_security()
        if not all(hasattr(self.jetstream, name) for name in (
            "stream_info", "delete_stream", "consumer_info", "delete_consumer",
        )):
            raise TopologyDriftError("rollback-capable JetStream APIs are required")
        identity_proof = self._prove_provisioner_identity()
        target = Path(receipt_path)
        timestamp = _now(now).isoformat().replace("+00:00", "Z")
        desired = self.desired_topology()
        topology_sha256 = canonical_sha256(desired)
        try:
            receipt = read_topology_receipt(target, operation_lock=operation_lock)
        except TopologyReceiptError as exc:
            raise TopologyDriftError(str(exc)) from exc
        if any((
            receipt["endpoint"] != self.config.endpoint,
            receipt["topology_sha256"] != topology_sha256,
            receipt["provisioner_public_nkey"] != self.config.nkey_public_key,
            receipt["nkey_identity_proof_sha256"] != identity_proof,
        )):
            raise TopologyDriftError("topology rollback receipt binding is invalid")
        if receipt["state"] == "rollback_complete":
            return receipt
        present = await self._inspect_topology(desired)
        created = list(receipt["created_resources"])
        for label, before in receipt["pre_state"].items():
            if not before.get("present") and present.get(label) and label not in created:
                created.append(label)
                receipt["created_resources"].append(label)
                receipt["events"].append({
                    "at": timestamp, "action": "rollback_reconciled_created", "resource": label,
                })
                receipt = write_topology_receipt(
                    target, receipt, operation_lock=operation_lock,
                )
        for label in reversed(created):
            if label in receipt["removed_resources"] or not present.get(label):
                if label not in receipt["removed_resources"]:
                    receipt["removed_resources"].append(label)
                    receipt = write_topology_receipt(
                        target, receipt, operation_lock=operation_lock,
                    )
                continue
            if label.startswith("consumer:"):
                await self.jetstream.delete_consumer(
                    self.config.stream_name, self.config.consumer_name
                )
            else:
                await self.jetstream.delete_stream(label.split(":", 1)[1])
            present = await self._inspect_topology(desired)
            if present.get(label):
                raise TopologyDriftError(f"topology rollback did not remove: {label}")
            receipt["removed_resources"].append(label)
            receipt["events"].append({
                "at": timestamp, "action": "removed", "resource": label,
            })
            receipt = write_topology_receipt(
                target, receipt, operation_lock=operation_lock,
            )
        receipt["state"] = "rollback_complete"
        receipt["events"].append({"at": timestamp, "action": "rollback_complete"})
        receipt = write_topology_receipt(
            target, receipt, operation_lock=operation_lock,
        )
        self._topology_sha256 = ""
        return receipt
    @staticmethod
    def _assert_exact(actual: Any, expected: Mapping[str, Any], label: str) -> None:
        drift: dict[str, Any] = {}
        for name, wanted in expected.items():
            wanted_value = _normalize_nats_topology_value(name, wanted, wanted)
            observed = _normalize_nats_topology_value(name, _field(actual, name), wanted_value)
            if observed != wanted_value:
                drift[name] = {"expected": wanted_value, "observed": observed}
        if drift:
            raise TopologyDriftError(f"{label} topology drift: {json.dumps(drift, sort_keys=True)}")
    @staticmethod
    def _stream_config(expected: Mapping[str, Any]) -> Any:
        try:
            from nats.js.api import DiscardPolicy, RetentionPolicy, StorageType, StreamConfig
        except ImportError:
            return dict(expected)
        payload = dict(expected)
        payload.update(retention=RetentionPolicy.LIMITS, storage=StorageType.FILE, discard=DiscardPolicy.NEW)
        payload["subjects"] = list(payload["subjects"])
        return StreamConfig(**payload)
    @staticmethod
    def _consumer_config(expected: Mapping[str, Any]) -> Any:
        try:
            from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy, ReplayPolicy
        except ImportError:
            return dict(expected)
        payload = dict(expected)
        payload.update(
            ack_policy=AckPolicy.EXPLICIT, deliver_policy=DeliverPolicy.ALL,
            replay_policy=ReplayPolicy.INSTANT, backoff=list(payload["backoff"]),
        )
        return ConsumerConfig(**payload)
    def _require_topology(self) -> None:
        if not self._topology_sha256:
            raise TopologyDriftError("candidate topology must be verified before I/O")
    @staticmethod
    def _require_ingress_lifecycle(envelope: Any) -> None:
        if (
            envelope.revision != 1
            or envelope.predecessor_envelope_id
            or envelope.terminal_disposition.state is not TerminalState.SUBMITTED
        ):
            raise TerminalCandidateTransportError(
                "candidate ingress requires the genesis submitted revision",
                reason_code="candidate_lifecycle_invalid",
            )
    async def _verify_lease(self, envelope: Any, *, now: str, scope: str) -> LeaseVerification:
        if self.lease_verifier is None:
            raise CandidateTransportError("candidate delivery lease verifier is missing")
        current = _now(now)
        if current < _now(envelope.created_at):
            raise TerminalCandidateTransportError(
                "candidate creation time is in the future", reason_code="candidate_not_yet_valid",
            )
        if (
            (_now(envelope.expires_at) - _now(envelope.created_at)).total_seconds()
            > self.config.max_candidate_lifetime_s
        ):
            raise TerminalCandidateTransportError(
                "candidate lifetime exceeds transport policy", reason_code="candidate_lifetime_invalid",
            )
        if envelope.is_expired(now=now) or current >= _now(envelope.lease_expires_at):
            raise TerminalCandidateTransportError(
                "candidate or producer lease is expired", reason_code="candidate_expired",
            )
        result = await _maybe(self.lease_verifier.verify(
            authority_id=envelope.authority_id, lease_id=envelope.lease_id,
            candidate_id=envelope.candidate_id, envelope_id=envelope.envelope_id,
            fence=envelope.fence, lease_expires_at=envelope.lease_expires_at,
            required_scope=scope, now=now,
        ))
        if not isinstance(result, LeaseVerification) or not lease_result_is_exact(
            result,
            authority_id=envelope.authority_id, lease_id=envelope.lease_id,
            candidate_id=envelope.candidate_id, envelope_id=envelope.envelope_id,
            fence=envelope.fence, lease_expires_at=envelope.lease_expires_at,
            required_scope=scope, now=now,
        ):
            reason = result.reason_code if isinstance(result, LeaseVerification) else "invalid_result"
            raise TerminalCandidateTransportError(
                f"candidate delivery lease refused: {reason}", reason_code="candidate_lease_invalid",
            )
        return result
    async def publish(self, signed: SignedCandidateEnvelope, *, now: str) -> CandidatePublishAck:
        self._require_security()
        self._require_topology()
        envelope = signed.envelope
        self._require_ingress_lifecycle(envelope)
        if not signed.verify(trusted_public_keys=self.trusted_source_public_keys):
            raise TerminalCandidateTransportError(
                "candidate source signature is untrusted or invalid", reason_code="candidate_signature_invalid",
            )
        lease = await self._verify_lease(envelope, now=now, scope="foundry_rsi.candidate_delivery")
        message_id = envelope.envelope_id
        wire = {
            "schema": NATS_ENVELOPE_SCHEMA, "kind": "candidate",
            "message_id": message_id, "subject": self.config.subject,
            "correlation_id": envelope.correlation_id,
            "causation_id": envelope.predecessor_envelope_id,
            "created_at": now, "requires_ack": True,
            "lease_verification_sha256": lease.verifier_receipt_sha256,
            "payload": {"schema": CANDIDATE_DELIVERY_SCHEMA, "signed_envelope": signed.to_dict()},
        }
        encoded = json.dumps(wire, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > self.config.max_message_bytes:
            raise CandidateTransportError("candidate envelope exceeds configured message limit")
        headers = {
            "Nats-Msg-Id": message_id, "Dharma-Nats-Schema": NATS_ENVELOPE_SCHEMA,
            "Dharma-Candidate-Schema": CANDIDATE_DELIVERY_SCHEMA,
            "Dharma-Envelope-Id": envelope.envelope_id,
            "Dharma-Correlation-Id": envelope.correlation_id,
            "Dharma-Idempotency-Key": envelope.idempotency_key,
            "Dharma-Fence": str(envelope.fence),
            "Dharma-Lease-Verification": lease.verifier_receipt_sha256,
        }
        error: Exception | None = None
        for attempt in range(1, self.config.publish_attempts + 1):
            try:
                ack = await self.jetstream.publish(
                    self.config.subject, encoded, headers=headers,
                    timeout=self.config.publish_timeout_s,
                )
                stream, seq = str(getattr(ack, "stream", "")), int(getattr(ack, "seq", 0))
                if stream != self.config.stream_name or seq < 1:
                    raise CandidateTransportError("JetStream publish acknowledgement is invalid")
                receipt = "transport_" + _operation_hash(message_id, stream, str(seq))[:24]
                return CandidatePublishAck(
                    envelope_id=envelope.envelope_id, stream=stream, seq=seq,
                    duplicate=bool(getattr(ack, "duplicate", False)), attempts=attempt,
                    receipt_id=receipt,
                )
            except Exception as exc:
                error = exc
                if attempt < self.config.publish_attempts:
                    await self.sleep(self.config.publish_backoff_s[attempt - 1])
        raise CandidateTransportError(f"candidate publish failed after retries: {error}") from error
    async def validate_message(self, message: MessageLike, *, now: str) -> SignedCandidateEnvelope:
        """Authenticate and fence a delivery without acknowledging or evaluating it."""
        self._require_security()
        self._require_topology()
        if message.subject != self.config.subject:
            raise TerminalCandidateTransportError(
                "candidate message subject is invalid", reason_code="candidate_wire_invalid",
            )
        raw_headers = getattr(message, "headers", None)
        headers = raw_headers if isinstance(raw_headers, Mapping) else None
        try:
            signed = parse_candidate_wire(
                message.data, headers=headers, nats_schema=NATS_ENVELOPE_SCHEMA,
                delivery_schema=CANDIDATE_DELIVERY_SCHEMA, subject=self.config.subject,
                now=now, max_message_bytes=self.config.max_message_bytes,
                max_clock_skew_s=self.config.max_clock_skew_s,
                max_candidate_lifetime_s=self.config.max_candidate_lifetime_s,
            )
        except CandidateContractError as wire_exc:
            raise TerminalCandidateTransportError(
                str(wire_exc), reason_code="candidate_wire_invalid",
            ) from wire_exc
        self._require_ingress_lifecycle(signed.envelope)
        if not signed.verify(trusted_public_keys=self.trusted_source_public_keys):
            raise TerminalCandidateTransportError(
                "candidate source signature is untrusted or invalid",
                reason_code="candidate_signature_invalid",
            )
        try:
            lease = await self._verify_lease(
                signed.envelope, now=now, scope="foundry_rsi.candidate_delivery"
            )
        except TerminalCandidateTransportError as lease_error:
            # Parsing and source-signature verification already succeeded, so
            # terminal expiry/lease evidence may safely bind this envelope.
            lease_error.signed_envelope = signed
            raise
        receipt_header = headers.get("Dharma-Lease-Verification") if headers is not None else None
        if isinstance(receipt_header, (list, tuple)):
            receipt_header = receipt_header[0] if len(receipt_header) == 1 else ""
        if receipt_header != lease.verifier_receipt_sha256:
            raise TerminalCandidateTransportError(
                "candidate lease receipt does not match current verification",
                reason_code="candidate_lease_invalid",
            )
        return signed
    async def consume(
        self,
        message: MessageLike,
        handler: Callable[[SignedCandidateEnvelope], Any],
        *,
        now: str,
    ) -> CandidateConsumeAck:
        self._require_security()
        self._require_topology()
        signed: SignedCandidateEnvelope | None = None
        try:
            signed = await self.validate_message(message, now=now)
            envelope = signed.envelope
            prior = await self.terminal_store.latest_terminal(
                candidate_id=envelope.candidate_id, envelope_id=envelope.envelope_id,
            )
            if prior is not None:
                await _ack(message)
                disposition = prior["terminal"]["disposition"]["state"]
                return CandidateConsumeAck("ack", envelope.envelope_id, disposition, duplicate=True)
            result = await _maybe(handler(signed))
            if not isinstance(result, CandidateHandlingResult):
                raise CandidateTransportError("candidate handler returned an invalid result")
            terminal_at = _now(result.disposition.at)
            if not (
                _now(envelope.created_at) <= terminal_at <= _now(now)
                and terminal_at <= _now(envelope.expires_at)
            ):
                raise CandidateTransportError("candidate handler disposition time is invalid")
            await self.terminal_store.append_terminal_disposition(
                candidate_id=envelope.candidate_id, envelope_id=envelope.envelope_id,
                disposition=result.disposition, attempt=envelope.attempt, fence=envelope.fence,
                transport_receipt_id=result.transport_receipt_id,
                evaluation_receipt_sha256=result.evaluation_receipt_sha256,
                allow_external_candidate=True,
            )
            await _ack(message)
            return CandidateConsumeAck(
                "ack", envelope.envelope_id, result.disposition.state.value,
            )
        except Exception as exc:
            if signed is None and isinstance(exc, TerminalCandidateTransportError):
                authenticated = getattr(exc, "signed_envelope", None)
                if isinstance(authenticated, SignedCandidateEnvelope):
                    signed = authenticated
            count = max(1, int(_message_delivery_count(message) or 1))
            if isinstance(exc, TerminalCandidateTransportError) or count >= self.config.max_deliveries:
                return await self._dead_letter(message, signed=signed, now=now, error=exc, count=count)
            await self._nak(message, delay=self.config.backoff_s[min(count - 1, len(self.config.backoff_s) - 1)])
            raise CandidateTransportError(f"candidate consume will retry: {exc}") from exc
    async def _dead_letter(
        self,
        message: MessageLike,
        *,
        signed: SignedCandidateEnvelope | None,
        now: str,
        error: Exception,
        count: int,
    ) -> CandidateConsumeAck:
        envelope = signed.envelope if signed is not None else None
        envelope_id = envelope.envelope_id if envelope else hashlib.sha256(message.data).hexdigest()
        reason = (
            error.reason_code
            if isinstance(error, TerminalCandidateTransportError)
            else "candidate_delivery_exhausted"
        )
        state = TerminalState.EXPIRED if reason == "candidate_expired" else TerminalState.DEAD_LETTERED
        message_id = "dlq_" + _operation_hash(envelope_id, reason)[:32]
        dlq = {
            "schema": NATS_ENVELOPE_SCHEMA, "kind": "event",
            "message_id": message_id,
            "subject": self.config.dlq_subject, "created_at": now, "requires_ack": False,
            "payload": {
                "schema": CANDIDATE_DLQ_SCHEMA, "envelope_id": envelope_id,
                "candidate_id": envelope.candidate_id if envelope else "untrusted",
                "original_sha256": hashlib.sha256(message.data).hexdigest(),
                "delivery_count": count, "max_deliveries": self.config.max_deliveries,
                "reason_code": reason, "error_type": type(error).__name__,
            },
        }
        headers = {"Nats-Msg-Id": message_id, "Dharma-Nats-Schema": NATS_ENVELOPE_SCHEMA}
        disposition = (
            TerminalDisposition(
                state=state, reason_code=reason,
                receipt_id="dlq_terminal_" + _operation_hash(envelope_id, reason)[:20],
                at=envelope.expires_at if state is TerminalState.EXPIRED else now,
            )
            if envelope is not None else None
        )
        try:
            outbox = await self.terminal_store.append_dlq_outbox(
                candidate_id=envelope.candidate_id if envelope else "untrusted",
                envelope_id=envelope_id, message_id=message_id, subject=self.config.dlq_subject,
                wire=dlq, headers=headers, attempt=envelope.attempt if envelope else count,
                fence=envelope.fence if envelope else 1, created_at=now,
                disposition=disposition,
            )
        except Exception as store_exc:
            await self._nak(message, delay=self.config.backoff_s[-1])
            raise CandidateTransportError(
                f"candidate DLQ outbox persistence failed: {store_exc}"
            ) from store_exc
        delivered = await self.terminal_store.dlq_delivery(
            outbox_id=str(outbox["outbox_id"])
        )
        if delivered is not None:
            await _ack(message)
            return CandidateConsumeAck("dlq", envelope_id, state.value, duplicate=True, error=str(error))
        try:
            await self._deliver_outbox(outbox, delivered_at=now)
        except Exception as outbox_exc:
            await self._nak(message, delay=self.config.backoff_s[-1])
            raise CandidateTransportError(
                f"candidate DLQ is durable in the outbox but delivery is pending: {outbox_exc}"
            ) from outbox_exc
        await _ack(message)
        return CandidateConsumeAck("dlq", envelope_id, state.value, error=str(error))
    async def _deliver_outbox(self, outbox: Mapping[str, Any], *, delivered_at: str) -> None:
        error: Exception | None = None
        for attempt in range(1, self.config.publish_attempts + 1):
            try:
                encoded = json.dumps(outbox["wire"], sort_keys=True, separators=(",", ":")).encode()
                ack = await self.jetstream.publish(
                    str(outbox["subject"]), encoded, headers=dict(outbox["headers"]),
                    timeout=self.config.publish_timeout_s,
                )
                stream, seq = str(getattr(ack, "stream", "")), int(getattr(ack, "seq", 0))
                if stream != self.config.dlq_stream_name or seq < 1:
                    raise CandidateTransportError("candidate DLQ publish acknowledgement is invalid")
                disposition_payload = outbox.get("disposition")
                if isinstance(disposition_payload, Mapping):
                    await self.terminal_store.append_terminal_disposition(
                        candidate_id=str(outbox["candidate_id"]), envelope_id=str(outbox["envelope_id"]),
                        disposition=TerminalDisposition.from_dict(disposition_payload),
                        attempt=int(outbox["attempt"]), fence=int(outbox["fence"]),
                        allow_external_candidate=True,
                    )
                await self.terminal_store.mark_dlq_delivered(
                    outbox_id=str(outbox["outbox_id"]), stream=stream, seq=seq,
                    delivered_at=delivered_at,
                )
                return
            except Exception as exc:
                error = exc
                if attempt < self.config.publish_attempts:
                    await self.sleep(self.config.publish_backoff_s[attempt - 1])
        raise CandidateTransportError(f"candidate DLQ delivery failed after retries: {error}") from error
    async def reconcile_dlq_outbox(self, *, now: str) -> dict[str, Any]:
        """Deliver durable pending DLQ rows independently of source redelivery."""
        self._require_security()
        self._require_topology()
        pending = await self.terminal_store.pending_dlq_outbox()
        delivered: list[str] = []
        for outbox in pending:
            await self._deliver_outbox(outbox, delivered_at=now)
            delivered.append(str(outbox["outbox_id"]))
        return {"pending": len(pending), "delivered": delivered}
    @staticmethod
    async def _nak(message: MessageLike, *, delay: float) -> None:
        try:
            await message.nak(delay=delay)
        except TypeError:
            await message.nak()


__all__ = ["CANDIDATE_DELIVERY_SCHEMA", "CANDIDATE_DLQ_SCHEMA", "CandidateConsumeAck",
           "CandidateHandlingResult", "CandidateJetStreamTransport", "CandidatePublishAck",
           "CandidateTransportConfig", "CandidateTransportError", "ConnectionSecurity", "TopologyDriftError"]
