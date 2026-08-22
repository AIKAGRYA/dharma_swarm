"""Governed Mission Control dispatch into the native A2A transport."""
from __future__ import annotations
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Protocol
from dharma_swarm.a2a.a2a_server import A2AMessage, A2ATask, A2ATaskStatus
from dharma_swarm.a2a.nats_transport import A2ANatsTransport, NatsPublishAck
from dharma_swarm.a2a.nats_transport_support import _message_id, _operation_hash
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_contract import (SCHEMA_VERSION as MISSION_SCHEMA_VERSION, MissionControlError, clean_identifier, receipt_matches_identity, session_id as mission_session_id, stable_id)
from dharma_swarm.models import Task, TaskStatus
from dharma_swarm.runtime_state import RuntimeReceipt, RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard
A2A_EXECUTION_SCHEMA_VERSION = "dharma.mission_control.a2a.v1"
_TERMINAL_A2A_STATUSES = frozenset({"completed", "failed", "cancelled", "rejected"})
_A2A_STATUSES = frozenset(status.value for status in A2ATaskStatus)
class A2AAdapterError(MissionControlError): ...
@dataclass(frozen=True, slots=True)
class A2ADispatchRequest:
    mission_id: str
    task_id: str
    dispatch_key: str
    claimed_principal: str
    from_agent: str
    to_agent: str
    capability: str
    instruction: str
@dataclass(frozen=True, slots=True)
class A2ADispatchIntent:
    request: A2ADispatchRequest
    operation_id: str
    operation_digest: str
    external_a2a_task_id: str
    context_id: str
    subject: str
@dataclass(frozen=True, slots=True)
class A2ADispatchAuthorization:
    mission_id: str
    task_id: str
    dispatch_key: str
    authenticated_principal: str
    operation_digest: str
    authority_ref: str
    authority_digest: str
class GovernedA2ADispatchAuthorizer(Protocol):
    async def authorize(self, intent: A2ADispatchIntent) -> A2ADispatchAuthorization: ...
@dataclass(frozen=True, slots=True)
class A2APublishRef:
    mission_id: str
    task_id: str
    dispatch_key: str
    operation_id: str
    operation_digest: str
    external_a2a_task_id: str
    context_id: str
    run_id: str
    trace_id: str
    correlation_id: str
    claim_id: str
    idempotency_key: str
    session_id: str
    target_agent: str
    authority_ref: str
    authority_digest: str
    subject: str
    message_id: str
    receipt_id: str
    stream: str = ""
    seq: int | None = None
    broker_accepted: bool = True
    idempotency_finalized: bool = False
    recovered: bool = False
    proves_handler_contact: bool = False
    proves_semantic_outcome: bool = False
    proves_verified_outcome: bool = False
    proves_executor_liveness: bool = False
    proves_global_uniqueness: bool = False
@dataclass(frozen=True, slots=True)
class A2APublishObservation:
    publish_ref: A2APublishRef
    receipt_ids: tuple[str, ...]
    publish_acknowledged: bool
    consumer_acknowledged: bool
    handler_acknowledged: bool
    semantic_outcome_observed: bool
    semantic_status: str = ""
    verified_outcome: bool = False
    proves_executor_liveness: bool = False
    proves_global_uniqueness: bool = False
class A2AMissionAdapter:
    def __init__(self, mission_control: MissionControl, board: TaskBoard,
                 runtime_state: RuntimeStateStore, transport: A2ANatsTransport, *,
                 authorizer: GovernedA2ADispatchAuthorizer,
                 receipt_scan_limit: int = 200) -> None:
        if receipt_scan_limit < 1:
            raise A2AAdapterError("receipt_scan_limit must be positive")
        self._mission_control = mission_control
        self._board = board
        self._runtime = runtime_state
        self._transport = transport
        self._authorizer = authorizer
        self._receipt_scan_limit = receipt_scan_limit
    async def dispatch(self, request: A2ADispatchRequest) -> A2APublishRef:
        request = self._normalize_request(request)
        task = await self._require_owner_task(request.mission_id, request.task_id, require_ready=True)
        triple = (request.mission_id, request.task_id, request.dispatch_key)
        external_id = stable_id("a2a_task", *triple)
        context_id = stable_id("a2a_context", request.mission_id)
        subject = self._transport.subject_for_task(self._build_task(request, task, external_id, context_id))
        operation_digest = self._operation_digest(request, task, subject=subject)
        intent = A2ADispatchIntent(request, stable_id("a2a_operation", *triple), operation_digest, external_id, context_id, subject)
        authorization = await self._authorizer.authorize(intent)
        self._require_authorization(intent, authorization)
        await self._revalidate_intent(intent)
        identity = self._identity(intent, authorization)
        recovered = await self._recover_publish(intent, identity, recovered=True)
        if recovered is not None:
            return recovered
        a2a_task = await self._revalidate_intent(intent)
        refreshed = await self._authorizer.authorize(intent)
        self._require_authorization(intent, refreshed)
        if refreshed != authorization:
            raise A2AAdapterError("A2A authority changed before transport publish")
        a2a_task = await self._revalidate_intent(intent)
        recorded = await self._runtime.record_execution_identity(
            identity,
            source="mission_control.a2a.dispatch",
        )
        self._require_identity(
            identity,
            recorded,
            operation_digest=intent.operation_digest,
        )
        exact_external = await self._unique_external_identity(
            intent.external_a2a_task_id
        )
        if exact_external is None:
            raise A2AAdapterError("external A2A identity is missing before publish")
        self._require_identity(
            identity,
            exact_external,
            operation_digest=intent.operation_digest,
        )
        identity = exact_external
        a2a_task.metadata.update({**identity.metadata, "session_id": identity.session_id})
        try:
            ack = await self._transport.publish_task(a2a_task, identity=identity)
            self._require_ack(intent, ack)
        except Exception:
            recovered = await self._recover_publish(intent, identity, recovered=True)
            if recovered is not None:
                return recovered
            raise
        durable = await self._recover_publish(intent, identity, recovered=False)
        if durable is None:
            raise A2AAdapterError("transport returned an ACK without durable publish evidence")
        return durable
    async def observe(self, publish_ref: A2APublishRef) -> A2APublishObservation:
        self._require_ref_shape(publish_ref)
        await self._require_owner_task(publish_ref.mission_id, publish_ref.task_id,
                                       require_ready=False)
        identity = self._identity_from_ref(publish_ref)
        loaded, receipts = await self._load_evidence(
            identity,
            operation_digest=publish_ref.operation_digest,
            external_id=publish_ref.external_a2a_task_id,
        )
        successes = self._transport_acks(receipts, loaded, "nats_publish", "publish_ack")
        matched = next((receipt for receipt in successes
                        if receipt.receipt_id == publish_ref.receipt_id), None)
        payload = matched.payload if matched is not None else {}
        if (not publish_ref.broker_accepted or matched is None
                or publish_ref.subject != payload.get("subject")
                or publish_ref.message_id != (payload.get("message_id") or loaded.message_id)
                or publish_ref.authority_ref != loaded.metadata.get("authority_ref")
                or publish_ref.authority_digest != loaded.metadata.get("authority_digest")):
            raise A2AAdapterError("publish reference does not join durable A2A evidence")
        finalized = await self._idempotency_finalized(loaded, matched)
        proof_flags = (publish_ref.proves_handler_contact, publish_ref.proves_semantic_outcome,
                       publish_ref.proves_verified_outcome,
                       publish_ref.proves_executor_liveness,
                       publish_ref.proves_global_uniqueness)
        if (publish_ref.stream != str(payload.get("stream") or "")
                or publish_ref.seq != (payload.get("seq") if isinstance(payload.get("seq"), int) else None)
                or publish_ref.idempotency_finalized != finalized or any(proof_flags)):
            raise A2AAdapterError("publish reference contains unproven transport or outcome claims")
        consumer_acknowledged = bool(
            self._transport_acks(receipts, loaded, "nats_consume", "consumer_ack")
        )
        handler_receipts = self._handler_receipts(receipts, loaded)
        semantic_statuses = {
            receipt.status
            for receipt in handler_receipts
            if receipt.status in _TERMINAL_A2A_STATUSES
        }
        if len(semantic_statuses) > 1:
            raise A2AAdapterError("conflicting A2A semantic outcome receipts")
        return A2APublishObservation(
            publish_ref, tuple(r.receipt_id for r in receipts), True,
            consumer_acknowledged, bool(handler_receipts), bool(semantic_statuses),
            next(iter(semantic_statuses), ""))
    async def _require_owner_task(
        self, mission_id: str, task_id: str, *, require_ready: bool
    ) -> Task:
        mission = await self._mission_control.get_mission(mission_id)
        if (
            mission is None
            or mission.mission_id != mission_id
            or mission.metadata.get("schema_version") != MISSION_SCHEMA_VERSION
        ):
            raise A2AAdapterError(f"mission {mission_id!r} is not canonical")
        task = await self._board.get(task_id)
        if (
            task is None
            or task.id != task_id
            or task.metadata.get("mission_id") != mission_id
            or task.metadata.get("schema_version") != MISSION_SCHEMA_VERSION
        ):
            raise A2AAdapterError(f"task {task_id!r} is not in the mission")
        owner_dependencies = await self._board.get_dependencies(task_id)
        if sorted(owner_dependencies) != sorted(task.depends_on):
            raise A2AAdapterError("task dependency projection conflicts with owner state")
        for dependency_id in owner_dependencies:
            dependency = await self._board.get(dependency_id)
            if (
                dependency is None
                or dependency.metadata.get("mission_id") != mission_id
                or dependency.metadata.get("schema_version") != MISSION_SCHEMA_VERSION
            ):
                raise A2AAdapterError(f"dependency {dependency_id!r} is not in the mission")
            if require_ready and dependency.status != TaskStatus.COMPLETED:
                raise A2AAdapterError(f"dependency {dependency_id!r} is not completed")
        if require_ready and (
            task.status != TaskStatus.PENDING or bool(task.assigned_to)
        ):
            raise A2AAdapterError("A2A dispatch requires a pending, unassigned mission task")
        return task
    async def _revalidate_intent(self, intent: A2ADispatchIntent) -> A2ATask:
        request = intent.request
        task = await self._require_owner_task(request.mission_id, request.task_id,
                                              require_ready=True)
        a2a_task = self._build_task(request, task, intent.external_a2a_task_id, intent.context_id)
        subject = self._transport.subject_for_task(a2a_task)
        if subject != intent.subject or self._operation_digest(
                request, task, subject=subject) != intent.operation_digest:
            raise A2AAdapterError("canonical A2A operation changed after authorization")
        return a2a_task
    @staticmethod
    def _normalize_request(request: A2ADispatchRequest) -> A2ADispatchRequest:
        if not isinstance(request, A2ADispatchRequest):
            raise A2AAdapterError("dispatch requires A2ADispatchRequest")
        fields = ("mission_id", "task_id", "dispatch_key", "claimed_principal",
                  "from_agent", "to_agent", "capability")
        values = {field: clean_identifier(getattr(request, field), field)
                  for field in fields}
        values["instruction"] = str(request.instruction or "").strip()
        if not values["instruction"]:
            raise A2AAdapterError("instruction is required")
        return A2ADispatchRequest(**values)
    @staticmethod
    def _operation_digest(request: A2ADispatchRequest, task: Task, *, subject: str) -> str:
        payload = {
            "schema_version": A2A_EXECUTION_SCHEMA_VERSION,
            "request": asdict(request),
            "subject": subject,
            "task": {
                "title": task.title,
                "description": task.description,
                "priority": task.priority.value,
                "created_by": task.created_by,
                "depends_on": sorted(task.depends_on),
                "metadata": task.metadata,
            },
        }
        try:
            encoded = json.dumps(
                payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise A2AAdapterError("A2A operation is not JSON-serializable") from exc
        return hashlib.sha256(encoded).hexdigest()
    @staticmethod
    def _require_authorization(intent: A2ADispatchIntent,
                               authorization: A2ADispatchAuthorization) -> None:
        request = intent.request
        if type(authorization) is not A2ADispatchAuthorization:
            raise A2AAdapterError("authorizer returned an untyped authorization")
        expected = (request.mission_id, request.task_id, request.dispatch_key,
                    request.claimed_principal, intent.operation_digest)
        observed = (authorization.mission_id, authorization.task_id,
                    authorization.dispatch_key, authorization.authenticated_principal,
                    authorization.operation_digest)
        if observed != expected:
            raise A2AAdapterError("authorization does not bind the exact A2A operation")
        values = (authorization.authority_ref, authorization.authority_digest)
        if any(not isinstance(value, str) or not value or value != value.strip()
               or any(char.isspace() for char in value) for value in values):
            raise A2AAdapterError("authority ref and digest must be exact nonempty strings")
    @staticmethod
    def _build_task(request: A2ADispatchRequest, task: Task,
                    external_id: str, context_id: str) -> A2ATask:
        created_at = task.created_at.isoformat()
        return A2ATask(
            id=external_id,
            context_id=context_id,
            from_agent=request.from_agent,
            to_agent=request.to_agent,
            history=[A2AMessage.text(request.instruction)],
            capability=request.capability,
            dharma_task_id=request.task_id,
            created_at=created_at,
            updated_at=created_at,
        )
    @staticmethod
    def _identity(intent: A2ADispatchIntent,
                  authorization: A2ADispatchAuthorization) -> ExecutionIdentity:
        request = intent.request
        triple = (request.mission_id, request.task_id, request.dispatch_key)
        identity = ExecutionIdentity(
            stable_id("a2a_trace", *triple), stable_id("a2a_correlation", *triple[:2]),
            request.task_id, stable_id("a2a_run", *triple),
            stable_id("a2a_claim", *triple), stable_id("a2a_dispatch", *triple),
            agent_id=request.to_agent,
            session_id=mission_session_id(request.mission_id),
            external_a2a_task_id=intent.external_a2a_task_id,
            metadata={
                **asdict(authorization),
                "schema_version": A2A_EXECUTION_SCHEMA_VERSION,
                "operation_id": intent.operation_id,
                "context_id": intent.context_id,
                "subject": intent.subject,
                "capability": request.capability,
            },
        )
        return identity.with_updates(
            message_id=_message_id(intent.subject, intent.external_a2a_task_id, identity),
            metadata={"nats_operation_hash": _operation_hash(
                intent.subject, intent.external_a2a_task_id, identity.correlation_id
            )},
        )
    async def _load_evidence(self, expected: ExecutionIdentity, *, operation_digest: str,
                             external_id: str,
                             ) -> tuple[ExecutionIdentity, list[RuntimeReceipt]]:
        loaded = await self._runtime.get_execution_identity(expected.run_id)
        exact_external = await self._unique_external_identity(external_id)
        if loaded is None:
            if exact_external is not None:
                raise A2AAdapterError("external A2A identity conflicts with stable run identity")
            raise A2AAdapterError("stable A2A execution identity is missing")
        self._require_identity(expected, loaded, operation_digest=operation_digest)
        if exact_external is None or exact_external.run_id != loaded.run_id:
            raise A2AAdapterError("external A2A identity conflicts with stable run identity")
        self._require_identity(
            expected,
            exact_external,
            operation_digest=operation_digest,
        )
        loaded = exact_external
        receipts = await self._runtime.list_runtime_receipts(
            run_id=expected.run_id, limit=self._receipt_scan_limit + 1
        )
        if len(receipts) > self._receipt_scan_limit:
            raise A2AAdapterError("A2A receipt scan saturated; evidence is incomplete")
        for receipt in receipts:
            if not receipt_matches_identity(receipt, loaded):
                raise A2AAdapterError(f"receipt {receipt.receipt_id!r} has foreign identity")
        return loaded, receipts
    async def _recover_publish(self, intent: A2ADispatchIntent,
                               identity: ExecutionIdentity, *, recovered: bool,
                               ) -> A2APublishRef | None:
        if await self._runtime.get_execution_identity(identity.run_id) is None:
            foreign = await self._unique_external_identity(
                intent.external_a2a_task_id
            )
            if foreign is not None:
                raise A2AAdapterError("external A2A task identity is already foreign")
            return None
        loaded, receipts = await self._load_evidence(
            identity,
            operation_digest=intent.operation_digest,
            external_id=intent.external_a2a_task_id,
        )
        successes = self._transport_acks(receipts, loaded, "nats_publish", "publish_ack")
        if not successes:
            return None
        primary = successes[0]
        finalized = await self._idempotency_finalized(loaded, primary)
        payload = primary.payload
        core = (intent.request.mission_id, intent.request.task_id,
                intent.request.dispatch_key, intent.operation_id, intent.operation_digest,
                intent.external_a2a_task_id, intent.context_id, loaded.run_id,
                loaded.trace_id, loaded.correlation_id, loaded.claim_id,
                loaded.idempotency_key, loaded.session_id, loaded.agent_id,
                str(loaded.metadata.get("authority_ref") or ""),
                str(loaded.metadata.get("authority_digest") or ""),
                str(payload.get("subject") or ""),
                str(payload.get("message_id") or loaded.message_id), primary.receipt_id)
        return A2APublishRef(
            *core,
            stream=str(payload.get("stream") or ""),
            seq=payload.get("seq") if isinstance(payload.get("seq"), int) else None,
            idempotency_finalized=finalized,
            recovered=recovered,
        )
    async def _unique_external_identity(
        self,
        external_id: str,
    ) -> ExecutionIdentity | None:
        matches = await self._runtime.list_execution_identities_by_external_a2a_task(
            external_id,
            limit=2,
        )
        if len(matches) > 1:
            raise A2AAdapterError("external A2A task identity is ambiguous")
        return matches[0] if matches else None
    @staticmethod
    def _require_identity(expected: ExecutionIdentity, loaded: ExecutionIdentity, *,
                          operation_digest: str) -> None:
        fields = ("run_id", "trace_id", "correlation_id", "task_id", "claim_id",
                  "idempotency_key", "agent_id", "session_id", "external_a2a_task_id",
                  "message_id")
        if any(getattr(expected, field) != getattr(loaded, field) for field in fields):
            raise A2AAdapterError("stored A2A execution identity conflicts with dispatch")
        if loaded.metadata.get("operation_digest") != operation_digest or any(
            loaded.metadata.get(key) != value for key, value in expected.metadata.items()
        ):
            raise A2AAdapterError("stored A2A operation digest conflicts with dispatch")
    @staticmethod
    def _transport_acks(receipts: list[RuntimeReceipt], identity: ExecutionIdentity,
                        receipt_type: str, ack_contract: str) -> list[RuntimeReceipt]:
        successes: list[RuntimeReceipt] = []
        expected = (identity.external_a2a_task_id, identity.metadata.get("subject"),
                    identity.message_id, identity.metadata.get("nats_operation_hash"),
                    "ack", ack_contract)
        for receipt in receipts:
            if receipt.receipt_type != receipt_type or receipt.status != "ack":
                continue
            payload = receipt.payload
            observed = (payload.get("external_a2a_task_id"), payload.get("subject"),
                        payload.get("message_id"), payload.get("operation_hash"),
                        payload.get("action"), payload.get("ack_contract"))
            base = f"{receipt_type}:{expected[1]}:{expected[0]}"
            retry = f"{base}:retry:"
            if (observed != expected or not (receipt.side_effect_key == base
                    or (receipt.side_effect_key.startswith(retry)
                        and len(receipt.side_effect_key) > len(retry)))):
                raise A2AAdapterError(f"malformed {receipt_type} acknowledgement")
            successes.append(receipt)
        if len(successes) > 1:
            raise A2AAdapterError(f"ambiguous {receipt_type} acknowledgement evidence")
        return successes
    @staticmethod
    def _handler_receipts(receipts: list[RuntimeReceipt],
                          identity: ExecutionIdentity) -> list[RuntimeReceipt]:
        matches: list[RuntimeReceipt] = []
        expected = (identity.external_a2a_task_id, identity.metadata.get("context_id"),
                    identity.metadata.get("capability"))
        base_key = f"a2a_handler:{expected[0]}:{expected[2]}"
        for receipt in receipts:
            if receipt.receipt_type != "a2a_task":
                continue
            payload = receipt.payload
            if receipt.status not in _A2A_STATUSES or (
                    payload.get("external_a2a_task_id"), payload.get("context_id"),
                    payload.get("capability")) != expected or not (
                    receipt.side_effect_key == base_key
                    or (receipt.side_effect_key.startswith(f"{base_key}:retry:") and receipt.side_effect_key != f"{base_key}:retry:")):
                raise A2AAdapterError("malformed A2A handler receipt")
            matches.append(receipt)
        return matches
    async def _idempotency_finalized(self, identity: ExecutionIdentity,
                                     receipt: RuntimeReceipt) -> bool:
        record = await self._runtime.get_idempotency_record(
            identity.idempotency_key, receipt.side_effect_key)
        base_key = f"nats_publish:{identity.metadata.get('subject')}:{identity.external_a2a_task_id}"
        metadata = record.metadata if record is not None else {}
        if (record is None or record.status not in {"started", "completed", "skipped"}
            or not (receipt.side_effect_key == base_key
                    or receipt.side_effect_key.startswith(f"{base_key}:retry:"))
            or record.run_id != identity.run_id
            or record.task_id != identity.task_id
            or record.trace_id != identity.trace_id
            or record.correlation_id != identity.correlation_id
            or metadata.get("external_a2a_task_id") != identity.external_a2a_task_id
            or metadata.get("subject") != identity.metadata.get("subject")
            or metadata.get("message_id") != identity.message_id
            or metadata.get("operation_hash") != identity.metadata.get("nats_operation_hash")
            or (record.status in {"completed", "skipped"}
                and record.result_receipt_id != receipt.receipt_id)
        ):
            raise A2AAdapterError("publish idempotency record has foreign identity")
        return record.status in {"completed", "skipped"}
    @staticmethod
    def _require_ack(intent: A2ADispatchIntent, ack: NatsPublishAck) -> None:
        if not isinstance(ack, NatsPublishAck) or (
                ack.task_id, ack.subject, ack.action) != (
                intent.external_a2a_task_id, intent.subject, "ack") or (
                ack.status not in {"ack", "duplicate"}):
            raise A2AAdapterError("transport returned a conflicting publish acknowledgement")
    @staticmethod
    def _require_ref_shape(publish_ref: A2APublishRef) -> None:
        if not isinstance(publish_ref, A2APublishRef):
            raise A2AAdapterError("observe requires A2APublishRef")
        triple = (publish_ref.mission_id, publish_ref.task_id, publish_ref.dispatch_key)
        prefixes = ("a2a_task", "a2a_operation", "a2a_run", "a2a_trace",
                    "a2a_claim", "a2a_dispatch")
        fields = ("external_a2a_task_id", "operation_id", "run_id", "trace_id",
                  "claim_id", "idempotency_key")
        expected = [stable_id(prefix, *triple) for prefix in prefixes]
        expected += [stable_id("a2a_context", triple[0]),
                     stable_id("a2a_correlation", *triple[:2]),
                     mission_session_id(triple[0])]
        observed = [getattr(publish_ref, field) for field in fields]
        observed += [publish_ref.context_id, publish_ref.correlation_id, publish_ref.session_id]
        if observed != expected:
            raise A2AAdapterError("publish reference has conflicting stable identity")
    @staticmethod
    def _identity_from_ref(publish_ref: A2APublishRef) -> ExecutionIdentity:
        metadata = {
            "schema_version": A2A_EXECUTION_SCHEMA_VERSION,
            "mission_id": publish_ref.mission_id, "dispatch_key": publish_ref.dispatch_key,
            "operation_id": publish_ref.operation_id,
            "operation_digest": publish_ref.operation_digest,
            "context_id": publish_ref.context_id, "authority_ref": publish_ref.authority_ref,
            "authority_digest": publish_ref.authority_digest, "subject": publish_ref.subject,
            "nats_operation_hash": _operation_hash(
                publish_ref.subject, publish_ref.external_a2a_task_id, publish_ref.correlation_id),
        }
        return ExecutionIdentity(
            publish_ref.trace_id, publish_ref.correlation_id, publish_ref.task_id,
            publish_ref.run_id, publish_ref.claim_id, publish_ref.idempotency_key,
            agent_id=publish_ref.target_agent, session_id=publish_ref.session_id,
            external_a2a_task_id=publish_ref.external_a2a_task_id,
            message_id=publish_ref.message_id,
            metadata=metadata)
