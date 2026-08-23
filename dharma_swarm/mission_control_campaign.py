"""Durable campaign reconciliation over canonical Mission Control owners."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_contract import (
    MissionControlError,
    MissionSnapshot,
    TaskView,
    clean_identifier,
    stable_id,
    utc_now,
)
from dharma_swarm.mission_control_evidence import (
    ACCEPTANCE_RECEIPT_TYPE,
    IndependentAcceptance,
    canonical_served_models as _canonical_served_models,
    candidate_output_digest,
    json_value as _json_value,
)
from dharma_swarm.mission_control_execution import (
    EXECUTION_METADATA_KEY,
    OrchestratorMissionAdapter,
    OwnerExecutionObservation,
    OwnerExecutionRef,
)
from dharma_swarm.mission_control_operator_authority import (
    CampaignOperatorApplication,
    CampaignOperatorAuthority,
    OperatorControlRequestLike,
)
from dharma_swarm.mission_control_operator_state import (
    initial_operator_control_state,
    validate_operator_control_state,
)
from dharma_swarm.mission_control_verifier import CampaignAcceptanceEvidenceVerifier
from dharma_swarm.models import TaskStatus
from dharma_swarm.runtime_state import RuntimeReceipt, RuntimeStateStore, SessionState
from dharma_swarm.task_board import TaskBoard

CAMPAIGN_SESSION_PREFIX = "mission_campaign:"
CAMPAIGN_CYCLE_RECEIPT_TYPE = "mission_campaign_cycle"
CAMPAIGN_CONTROL_RECEIPT_TYPE = "mission_campaign_control"
CAMPAIGN_SCHEMA_VERSION = "dharma.mission_control.campaign.v1"
_RECEIPT_SCAN_LIMIT = 10_000
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
_MISSION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")


class CampaignTaskDispatcher(Protocol):
    async def dispatch(self, task: TaskView) -> OwnerExecutionRef: ...


class OwnerExecutionReader(Protocol):
    async def recover(
        self,
        mission_id: str,
        task_id: str,
        *,
        dispatch_key: str = "default",
    ) -> OwnerExecutionRef | None: ...

    async def observe(self, ref: OwnerExecutionRef) -> OwnerExecutionObservation: ...


@dataclass(frozen=True, slots=True)
class CampaignConfig:
    mission_id: str
    operator_id: str = "operator"
    canary_task_id: str = ""
    max_dispatch_per_cycle: int = 4
    cycle_interval_seconds: float = 5.0
    freshness_seconds: float = 30.0
    held_out_oracle_digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.mission_id, str) or not _MISSION_ID_RE.fullmatch(
            self.mission_id
        ):
            raise ValueError("mission_id must be 1-200 URL-safe characters")
        if clean_identifier(self.operator_id, "operator_id") != self.operator_id:
            raise ValueError("operator_id must be canonical")
        if self.canary_task_id and (
            clean_identifier(self.canary_task_id, "canary_task_id")
            != self.canary_task_id
        ):
            raise ValueError("canary_task_id must be canonical")
        dispatch_limit = self.max_dispatch_per_cycle
        if (
            not isinstance(dispatch_limit, int)
            or isinstance(dispatch_limit, bool)
            or not 1 <= dispatch_limit <= 100
        ):
            raise ValueError("max_dispatch_per_cycle must be from 1 to 100")
        for field, value in (
            ("cycle_interval_seconds", self.cycle_interval_seconds),
            ("freshness_seconds", self.freshness_seconds),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{field} must be a positive finite number")
        if self.freshness_seconds > 3600:
            raise ValueError("freshness_seconds must be at most 3600")
        if self.held_out_oracle_digest and not _SHA256_RE.fullmatch(
            self.held_out_oracle_digest
        ):
            raise ValueError("held_out_oracle_digest must be sha256")

    @property
    def session_id(self) -> str:
        return CAMPAIGN_SESSION_PREFIX + self.mission_id

    @property
    def digest(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class CampaignSnapshot:
    mission_id: str
    session_id: str
    config_digest: str
    generation: int
    cycle_sequence: int
    freshness_seconds: float
    mission_snapshot: MissionSnapshot
    owner_executions: tuple[OwnerExecutionObservation, ...]
    campaign_status: str
    supervisor_state: str
    writer_lock_held: bool
    latest_cycle_at: datetime | None
    transport_state: str
    model_execution_state: str
    acceptance_state: str
    candidate_task_ids: tuple[str, ...]
    accepted_task_ids: tuple[str, ...]
    rejected_task_ids: tuple[str, ...]
    conflicting_acceptance_task_ids: tuple[str, ...]
    canary_acceptance: str
    invalid_acceptance_receipts: int
    operator_control_state: dict[str, Any]
    errors: tuple[str, ...]
    observed_at: datetime
    authority: str = "TaskBoard+RuntimeStateStore+owner execution projection"
    proves_process_liveness: bool = False
    proves_model_execution: bool = False
    proves_semantic_acceptance: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _json_value(self)


class CampaignSupervisor:
    """One restart-safe reconciliation loop with no private task ledger."""

    def __init__(
        self,
        config: CampaignConfig,
        mission_control: MissionControl,
        board: TaskBoard,
        runtime_state: RuntimeStateStore,
        owner_reader: OwnerExecutionReader,
        *,
        dispatcher: CampaignTaskDispatcher | None = None,
    ) -> None:
        self.config = config
        self._control = mission_control
        self._board = board
        self._runtime = runtime_state
        self._owner_reader = owner_reader
        self._dispatcher = dispatcher
        self._operator_authority = CampaignOperatorAuthority(
            runtime_state,
            mission_id=config.mission_id,
            session_id=config.session_id,
            config_digest=config.digest,
        )
        self._acceptance_evidence = CampaignAcceptanceEvidenceVerifier(
            runtime_state,
            mission_id=config.mission_id,
            session_id=config.session_id,
            held_out_oracle_digest=config.held_out_oracle_digest,
        )

    async def start(self) -> SessionState:
        if await self._control.get_mission(self.config.mission_id) is None:
            raise MissionControlError(
                f"mission {self.config.mission_id!r} was not found"
            )
        now = utc_now()
        existing = await self._runtime.get_session(self.config.session_id)
        if existing is not None:
            recorded = str(existing.metadata.get("config_digest") or "")
            if recorded != self.config.digest:
                raise MissionControlError(
                    "campaign already exists with conflicting config"
                )
            self._session_generation(existing)
            if (
                existing.status in {"active", "paused"}
                and existing.metadata.get("stop_requested") is False
            ):
                if existing.status == "paused":
                    raw_state = existing.metadata.get("operator_control_state")
                    try:
                        state = validate_operator_control_state(
                            raw_state,
                            expected_generation=self._session_generation(existing),
                        )
                    except ValueError as exc:
                        raise MissionControlError(
                            "paused campaign has invalid control-state evidence"
                        ) from exc
                    if state["control_state"] != "PAUSED":
                        raise MissionControlError(
                            "paused campaign has conflicting control-state evidence"
                        )
                return existing
            if (
                existing.status == "stopped"
                or existing.metadata.get("stop_requested") is True
            ):
                raise MissionControlError(
                    "stopped campaign restart requires separately admitted authority"
                )
            raise MissionControlError("campaign session status is invalid")
        else:
            generation = 1
            created_at = now
        session = SessionState(
            session_id=self.config.session_id,
            operator_id=self.config.operator_id,
            status="active",
            metadata={
                "schema_version": CAMPAIGN_SCHEMA_VERSION,
                "mission_id": self.config.mission_id,
                "config": asdict(self.config),
                "config_digest": self.config.digest,
                "generation": generation,
                "last_cycle_sequence": 0,
                "last_cycle_receipt_id": "",
                "stop_requested": False,
                "started_at": now.isoformat(),
                "operator_control_state": initial_operator_control_state(generation),
            },
            created_at=created_at,
            updated_at=now,
        )
        control_receipt = self._control_receipt("start", generation, now)
        if existing is None:
            stored = await self._runtime.insert_session_if_absent(
                session,
                atomic_receipt=control_receipt,
            )
            if stored is None:
                raise MissionControlError("campaign start lost its create fence")
        else:
            stored = await self._runtime.compare_and_swap_session(
                existing,
                session,
                atomic_receipt=control_receipt,
            )
            if stored is None:
                raise MissionControlError("campaign start lost its session fence")
        return stored

    async def stop(self) -> SessionState:
        existing = await self._require_campaign_session()
        if (
            existing.status == "stopped"
            and existing.metadata.get("stop_requested") is True
        ):
            return existing
        now = utc_now()
        if now <= existing.updated_at:
            now = existing.updated_at + timedelta(microseconds=1)
        stopped = SessionState(
            session_id=existing.session_id,
            operator_id=existing.operator_id,
            status="stopped",
            current_task_id=existing.current_task_id,
            active_bundle_id=existing.active_bundle_id,
            metadata={
                **existing.metadata,
                "stop_requested": True,
                "stop_requested_at": now.isoformat(),
            },
            created_at=existing.created_at,
            updated_at=now,
        )
        generation = self._session_generation(existing)
        stored = await self._runtime.compare_and_swap_session(
            existing,
            stopped,
            atomic_receipt=self._control_receipt("stop", generation, now),
        )
        if stored is None:
            raise MissionControlError("campaign stop lost its session fence")
        return stored

    async def cycle(self, *, writer_lock_held: bool = True) -> CampaignSnapshot:
        session = await self._require_campaign_session()
        if (
            session.status == "stopped"
            or session.metadata.get("stop_requested") is True
        ):
            return await self.status(writer_lock_held=writer_lock_held)
        if session.status not in {"active", "paused"}:
            raise MissionControlError("campaign session status is invalid")
        snapshot = await self._require_snapshot()
        errors: list[str] = []
        refs = await self._recover_owner_refs(snapshot, errors)
        existing_observations = await self._observe_refs(refs, errors)
        accepted_rows, rejected_rows, _ = await self._acceptance_verdicts(
            existing_observations,
        )
        accepted_dependencies = accepted_rows - rejected_rows
        dispatched = 0
        if self._dispatcher is not None and session.status == "active":
            for task in snapshot.tasks:
                if dispatched >= self.config.max_dispatch_per_cycle:
                    break
                if task.status != TaskStatus.PENDING or task.task_id in refs:
                    continue
                if not await self._ready(task.task_id, accepted_dependencies):
                    continue
                current = await self._require_campaign_session()
                if current.status != "active" or current.metadata.get("stop_requested"):
                    break
                try:
                    refs[task.task_id] = await self._dispatcher.dispatch(task)
                    dispatched += 1
                except Exception as exc:
                    errors.append(f"dispatch:{task.task_id}:{type(exc).__name__}:{exc}")
        refreshed = await self._require_snapshot()
        refs.update(await self._recover_owner_refs(refreshed, errors))
        observations = await self._observe_refs(refs, errors)
        await self._record_cycle(
            dispatched=dispatched,
            refs=refs,
            errors=errors,
        )
        return await self._build_status(
            refreshed,
            observations,
            writer_lock_held=writer_lock_held,
            errors=tuple(errors),
        )

    async def effects_enabled(self) -> bool:
        """Return exact dispatch/verifier eligibility for the current generation."""
        session = await self._require_campaign_session()
        return bool(
            session.status == "active"
            and session.metadata.get("stop_requested") is False
        )

    async def apply_operator_control_result(
        self,
        request: OperatorControlRequestLike,
        operator_login: str,
        source_envelope_sha256: str,
    ) -> CampaignOperatorApplication:
        """Apply the mobile adapter's verified request without importing transport."""
        return await self._operator_authority.apply(
            request,
            operator_login,
            source_envelope_sha256,
        )

    async def apply_operator_control(
        self,
        request: OperatorControlRequestLike,
        operator_login: str,
        source_envelope_sha256: str,
    ) -> Any:
        """Exact three-argument callback consumed by the mobile reconciler."""
        result = await self.apply_operator_control_result(
            request,
            operator_login,
            source_envelope_sha256,
        )
        return result.as_mobile_application()

    async def status(self, *, writer_lock_held: bool = False) -> CampaignSnapshot:
        snapshot = await self._require_snapshot()
        errors: list[str] = []
        refs = await self._recover_owner_refs(snapshot, errors)
        observations = await self._observe_refs(refs, errors)
        return await self._build_status(
            snapshot,
            observations,
            writer_lock_held=writer_lock_held,
            errors=tuple(errors),
        )

    async def accept(self, acceptance: IndependentAcceptance) -> RuntimeReceipt:
        if acceptance.mission_id != self.config.mission_id:
            raise MissionControlError("acceptance names a foreign mission")
        session = await self._require_campaign_session()
        if session.status != "active" or session.metadata.get("stop_requested") is True:
            raise MissionControlError("campaign stopped before acceptance promotion")
        task = await self._board.get(acceptance.task_id)
        if task is None or task.metadata.get("mission_id") != self.config.mission_id:
            raise MissionControlError("acceptance task was not found in the mission")
        if acceptance.accepted and task.metadata.get("goal_id") == "G10_SAFETY_TCB":
            if acceptance.oracle_kind != "deterministic_held_out":
                raise MissionControlError(
                    "G10 acceptance requires held-out oracle evidence"
                )
        marker = task.metadata.get(EXECUTION_METADATA_KEY)
        if not isinstance(marker, dict):
            raise MissionControlError("acceptance task has no owner execution marker")
        raw_dispatch_key = marker.get("dispatch_key", "default")
        if not isinstance(raw_dispatch_key, str):
            raise MissionControlError("owner dispatch key has a foreign shape")
        dispatch_key = clean_identifier(raw_dispatch_key, "dispatch_key")
        if dispatch_key != raw_dispatch_key:
            raise MissionControlError("owner dispatch key must be canonical")
        ref = await self._owner_reader.recover(
            acceptance.mission_id,
            acceptance.task_id,
            dispatch_key=dispatch_key,
        )
        if ref is None:
            raise MissionControlError("acceptance producer execution was not found")
        observation = await self._owner_reader.observe(ref)
        if not observation.succeeded or not observation.terminal:
            raise MissionControlError("producer output is not a completed candidate")
        if (
            acceptance.producer_run_id,
            acceptance.producer_agent_id,
        ) != (ref.run_id, ref.agent_id):
            raise MissionControlError("acceptance names a foreign producer")
        if (
            candidate_output_digest(observation.result)
            != acceptance.producer_output_digest
        ):
            raise MissionControlError("acceptance does not bind the candidate output")
        (
            producer_started_at,
            producer_completed_at,
        ) = await self._acceptance_evidence.producer_times(ref)
        verifier_receipts = await self._acceptance_evidence.require_verifier_evidence(
            acceptance,
            producer_started_at=producer_started_at,
            producer_completed_at=producer_completed_at,
        )
        await self._acceptance_evidence.require_model_family_evidence(
            acceptance,
            ref,
            verifier_receipts,
            producer_started_at=producer_started_at,
            producer_completed_at=producer_completed_at,
        )
        receipt = RuntimeReceipt(
            receipt_id=acceptance.acceptance_id,
            receipt_type=ACCEPTANCE_RECEIPT_TYPE,
            status="accepted" if acceptance.accepted else "rejected",
            run_id=acceptance.verifier_run_id,
            task_id=ref.task_id,
            correlation_id=self.config.session_id,
            causation_id=ref.run_id,
            agent_id=acceptance.verifier_agent_id,
            idempotency_key=stable_id("acceptance", acceptance.acceptance_id),
            side_effect_key=f"mission_acceptance:{acceptance.acceptance_id}",
            payload=acceptance.to_payload(),
            created_at=acceptance.observed_at,
        )
        previous = await self._runtime.list_runtime_receipts(
            correlation_id=self.config.session_id,
            receipt_type=ACCEPTANCE_RECEIPT_TYPE,
            limit=_RECEIPT_SCAN_LIMIT,
        )
        if len(previous) >= _RECEIPT_SCAN_LIMIT:
            raise MissionControlError("acceptance receipt scan saturated")
        matches = [item for item in previous if item.receipt_id == receipt.receipt_id]
        if matches:
            if len(matches) != 1 or matches[0] != receipt:
                raise MissionControlError(
                    "acceptance identity already has conflicting evidence"
                )
            return matches[0]
        return await self._runtime.insert_runtime_receipt_exact(receipt)

    async def _build_status(
        self,
        snapshot: MissionSnapshot,
        observations: tuple[OwnerExecutionObservation, ...],
        *,
        writer_lock_held: bool,
        errors: tuple[str, ...],
    ) -> CampaignSnapshot:
        session = await self._require_campaign_session()
        generation = self._session_generation(session)
        raw_operator_state = session.metadata.get("operator_control_state")
        if raw_operator_state is None:
            if session.status == "paused":
                raise MissionControlError(
                    "paused campaign has no control-state evidence"
                )
            operator_control_state = initial_operator_control_state(generation)
        else:
            try:
                operator_control_state = validate_operator_control_state(
                    raw_operator_state,
                    expected_generation=generation,
                )
            except ValueError as exc:
                raise MissionControlError(
                    "campaign operator control state is invalid"
                ) from exc
        latest_cycle = await self._latest_cycle()
        latest_cycle_at = latest_cycle.created_at if latest_cycle is not None else None
        now = utc_now()
        if session.status == "stopped" or session.metadata.get("stop_requested"):
            supervisor_state = "stopped"
        elif latest_cycle_at is None:
            supervisor_state = "unobserved"
        elif now - latest_cycle_at > timedelta(seconds=self.config.freshness_seconds):
            supervisor_state = "stale_lock" if writer_lock_held else "stale"
        elif writer_lock_held:
            supervisor_state = "running"
        else:
            supervisor_state = "fresh_cycle_no_writer"

        receipts = await self._owner_receipts(observations)
        accepted_rows, rejected_rows, invalid = await self._acceptance_verdicts(
            observations
        )
        conflicting = accepted_rows & rejected_rows
        accepted = accepted_rows - conflicting
        rejected = rejected_rows - conflicting
        candidates = tuple(
            sorted(
                observation.ref.task_id
                for observation in observations
                if observation.succeeded
                and observation.ref.task_id not in accepted_rows
                and observation.ref.task_id not in rejected_rows
            )
        )
        transport_observed = any(
            receipt.receipt_type.startswith(("a2a_", "nats_")) for receipt in receipts
        )
        model_observed = bool(await self._owner_served_models(observations))
        acceptance_state = (
            "conflicting"
            if conflicting
            else "accepted"
            if accepted
            else "rejected"
            if rejected
            else "candidate_only"
            if candidates
            else "unobserved"
        )
        canary = self.config.canary_task_id
        canary_acceptance = (
            "not_configured"
            if not canary
            else "conflicting"
            if canary in conflicting
            else "accepted"
            if canary in accepted
            else "rejected"
            if canary in rejected
            else "candidate"
            if canary in candidates
            else "unobserved"
        )
        return CampaignSnapshot(
            mission_id=self.config.mission_id,
            session_id=self.config.session_id,
            config_digest=self.config.digest,
            generation=generation,
            cycle_sequence=latest_cycle.payload["sequence"] if latest_cycle else 0,
            freshness_seconds=self.config.freshness_seconds,
            mission_snapshot=snapshot,
            owner_executions=observations,
            campaign_status=session.status,
            supervisor_state=supervisor_state,
            writer_lock_held=writer_lock_held,
            latest_cycle_at=latest_cycle_at,
            transport_state="observed" if transport_observed else "unobserved",
            model_execution_state="observed" if model_observed else "unobserved",
            acceptance_state=acceptance_state,
            candidate_task_ids=candidates,
            accepted_task_ids=tuple(sorted(accepted)),
            rejected_task_ids=tuple(sorted(rejected)),
            conflicting_acceptance_task_ids=tuple(sorted(conflicting)),
            canary_acceptance=canary_acceptance,
            invalid_acceptance_receipts=invalid,
            operator_control_state=operator_control_state,
            errors=errors,
            observed_at=now,
            proves_process_liveness=supervisor_state == "running",
            proves_model_execution=model_observed,
            proves_semantic_acceptance=bool(accepted),
        )

    async def _recover_owner_refs(
        self,
        snapshot: MissionSnapshot,
        errors: list[str],
    ) -> dict[str, OwnerExecutionRef]:
        refs: dict[str, OwnerExecutionRef] = {}
        for task in snapshot.tasks:
            marker = task.metadata.get(EXECUTION_METADATA_KEY)
            if marker is None:
                continue
            if not isinstance(marker, dict):
                errors.append(f"recover:{task.task_id}:foreign-marker")
                continue
            raw_dispatch_key = marker.get("dispatch_key", "default")
            if not isinstance(raw_dispatch_key, str):
                errors.append(f"recover:{task.task_id}:foreign-dispatch-key")
                continue
            try:
                dispatch_key = clean_identifier(raw_dispatch_key, "dispatch_key")
            except MissionControlError:
                errors.append(f"recover:{task.task_id}:invalid-dispatch-key")
                continue
            if dispatch_key != raw_dispatch_key:
                errors.append(f"recover:{task.task_id}:noncanonical-dispatch-key")
                continue
            try:
                ref = await self._owner_reader.recover(
                    self.config.mission_id,
                    task.task_id,
                    dispatch_key=dispatch_key,
                )
                if ref is None:
                    errors.append(f"recover:{task.task_id}:missing-owner-record")
                else:
                    refs[task.task_id] = ref
            except Exception as exc:
                errors.append(f"recover:{task.task_id}:{type(exc).__name__}:{exc}")
        return refs

    async def _observe_refs(
        self,
        refs: Mapping[str, OwnerExecutionRef],
        errors: list[str],
    ) -> tuple[OwnerExecutionObservation, ...]:
        observations: list[OwnerExecutionObservation] = []
        for task_id, ref in sorted(refs.items()):
            try:
                observations.append(await self._owner_reader.observe(ref))
            except Exception as exc:
                errors.append(f"observe:{task_id}:{type(exc).__name__}:{exc}")
        return tuple(observations)

    async def _ready(
        self,
        task_id: str,
        accepted_dependency_ids: set[str],
    ) -> bool:
        task = await self._board.get(task_id)
        if task is None or task.status != TaskStatus.PENDING or task.blocked_by:
            return False
        for dependency_id in task.depends_on:
            dependency = await self._board.get(dependency_id)
            if (
                dependency is None
                or dependency.status != TaskStatus.COMPLETED
                or dependency_id not in accepted_dependency_ids
            ):
                return False
        return True

    async def _owner_receipts(
        self,
        observations: tuple[OwnerExecutionObservation, ...],
    ) -> list[RuntimeReceipt]:
        receipts: list[RuntimeReceipt] = []
        for observation in observations:
            rows = await self._runtime.list_runtime_receipts(
                run_id=observation.ref.run_id,
                limit=_RECEIPT_SCAN_LIMIT,
            )
            receipts.extend(rows)
        return receipts

    async def _owner_served_models(
        self,
        observations: tuple[OwnerExecutionObservation, ...],
    ) -> set[str]:
        models: set[str] = set()
        for observation in observations:
            identity = await self._runtime.get_execution_identity(
                observation.ref.run_id
            )
            if identity is None:
                continue
            receipts = await self._runtime.list_runtime_receipts(
                run_id=observation.ref.run_id,
                limit=_RECEIPT_SCAN_LIMIT,
            )
            if len(receipts) >= _RECEIPT_SCAN_LIMIT:
                raise MissionControlError("owner model receipt scan saturated")
            models.update(_canonical_served_models(receipts, identity=identity))
        return models

    async def _acceptance_verdicts(
        self,
        observations: tuple[OwnerExecutionObservation, ...],
    ) -> tuple[set[str], set[str], int]:
        producers = {item.ref.task_id: item for item in observations if item.succeeded}
        receipts = await self._runtime.list_runtime_receipts(
            correlation_id=self.config.session_id,
            receipt_type=ACCEPTANCE_RECEIPT_TYPE,
            limit=_RECEIPT_SCAN_LIMIT,
        )
        if len(receipts) >= _RECEIPT_SCAN_LIMIT:
            raise MissionControlError("acceptance receipt scan saturated")
        accepted: set[str] = set()
        rejected: set[str] = set()
        invalid = 0
        for receipt in receipts:
            if receipt.receipt_type != ACCEPTANCE_RECEIPT_TYPE:
                continue
            try:
                verdict = IndependentAcceptance.from_payload(receipt.payload)
                producer = producers.get(verdict.task_id)
                if producer is None or (
                    verdict.mission_id,
                    verdict.producer_run_id,
                    verdict.producer_agent_id,
                ) != (
                    self.config.mission_id,
                    producer.ref.run_id,
                    producer.ref.agent_id,
                ):
                    raise MissionControlError("acceptance producer binding is invalid")
                if (
                    receipt.run_id != verdict.verifier_run_id
                    or receipt.task_id != verdict.task_id
                    or receipt.agent_id != verdict.verifier_agent_id
                    or receipt.correlation_id != self.config.session_id
                    or receipt.causation_id != verdict.producer_run_id
                    or receipt.receipt_id != verdict.acceptance_id
                    or receipt.idempotency_key
                    != stable_id("acceptance", verdict.acceptance_id)
                    or receipt.side_effect_key
                    != f"mission_acceptance:{verdict.acceptance_id}"
                    or receipt.created_at != verdict.observed_at
                ):
                    raise MissionControlError("acceptance receipt carrier is invalid")
                if (
                    candidate_output_digest(producer.result)
                    != verdict.producer_output_digest
                ):
                    raise MissionControlError("acceptance output digest is invalid")
                (
                    producer_started_at,
                    producer_completed_at,
                ) = await self._acceptance_evidence.producer_times(producer.ref)
                verifier_receipts = (
                    await self._acceptance_evidence.require_verifier_evidence(
                        verdict,
                        producer_started_at=producer_started_at,
                        producer_completed_at=producer_completed_at,
                    )
                )
                await self._acceptance_evidence.require_model_family_evidence(
                    verdict,
                    producer.ref,
                    verifier_receipts,
                    producer_started_at=producer_started_at,
                    producer_completed_at=producer_completed_at,
                )
                expected_status = "accepted" if verdict.accepted else "rejected"
                if receipt.status != expected_status:
                    raise MissionControlError("acceptance receipt status conflicts")
                if verdict.accepted:
                    accepted.add(verdict.task_id)
                else:
                    rejected.add(verdict.task_id)
            except (KeyError, TypeError, ValueError, MissionControlError):
                invalid += 1
        return accepted, rejected, invalid

    async def _latest_cycle(self) -> RuntimeReceipt | None:
        session = await self._require_campaign_session()
        sequence = session.metadata.get("last_cycle_sequence")
        receipt_id = session.metadata.get("last_cycle_receipt_id")
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence < 0
            or not isinstance(receipt_id, str)
            or (sequence == 0) != (receipt_id == "")
        ):
            raise MissionControlError("campaign latest-cycle pointer is invalid")
        if sequence == 0:
            return None
        generation = self._session_generation(session)
        row = await self._runtime.get_runtime_receipt(receipt_id)
        expected_id = stable_id(
            "mission_campaign_cycle",
            self.config.mission_id,
            str(generation),
            str(sequence),
        )
        if row is None or (
            row.receipt_id != expected_id
            or row.receipt_type != CAMPAIGN_CYCLE_RECEIPT_TYPE
            or row.correlation_id != self.config.session_id
            or row.payload.get("schema_version") != CAMPAIGN_SCHEMA_VERSION
            or row.payload.get("mission_id") != self.config.mission_id
            or row.payload.get("generation") != generation
            or row.payload.get("sequence") != sequence
        ):
            raise MissionControlError("campaign latest-cycle evidence is foreign")
        return row

    async def _record_cycle(
        self,
        *,
        dispatched: int,
        refs: Mapping[str, OwnerExecutionRef],
        errors: list[str],
    ) -> None:
        session = await self._require_campaign_session()
        if (
            session.status not in {"active", "paused"}
            or session.metadata.get("stop_requested") is True
        ):
            raise MissionControlError(
                "campaign stopped before cycle evidence committed"
            )
        generation = self._session_generation(session)
        previous = session.metadata.get("last_cycle_sequence", 0)
        if isinstance(previous, bool) or not isinstance(previous, int) or previous < 0:
            raise MissionControlError("campaign cycle sequence is invalid")
        sequence = previous + 1
        now = utc_now()
        if now <= session.updated_at:
            now = session.updated_at + timedelta(microseconds=1)
        receipt_id = stable_id(
            "mission_campaign_cycle",
            self.config.mission_id,
            str(generation),
            str(sequence),
        )
        receipt = RuntimeReceipt(
            receipt_id=receipt_id,
            receipt_type=CAMPAIGN_CYCLE_RECEIPT_TYPE,
            status="partial" if errors else "completed",
            run_id=stable_id(
                "mission_campaign_run",
                self.config.mission_id,
                str(generation),
            ),
            correlation_id=self.config.session_id,
            agent_id="mission-control-supervisor",
            idempotency_key=receipt_id,
            side_effect_key=f"mission_campaign_cycle:{generation}:{sequence}",
            payload={
                "schema_version": CAMPAIGN_SCHEMA_VERSION,
                "mission_id": self.config.mission_id,
                "generation": generation,
                "sequence": sequence,
                "dispatched": dispatched,
                "owner_execution_ids": sorted(ref.run_id for ref in refs.values()),
                "errors": errors,
                "proves_process_liveness": False,
                "proves_model_execution": False,
                "proves_semantic_acceptance": False,
            },
            created_at=now,
        )
        updated = SessionState(
            session_id=session.session_id,
            operator_id=session.operator_id,
            status=session.status,
            current_task_id=session.current_task_id,
            active_bundle_id=session.active_bundle_id,
            metadata={
                **session.metadata,
                "last_cycle_sequence": sequence,
                "last_cycle_receipt_id": receipt_id,
            },
            created_at=session.created_at,
            updated_at=now,
        )
        if (
            await self._runtime.compare_and_swap_session(
                session,
                updated,
                atomic_receipt=receipt,
            )
            is None
        ):
            raise MissionControlError("campaign cycle lost its session fence")

    def _control_receipt(
        self,
        action: str,
        generation: int,
        now: datetime,
    ) -> RuntimeReceipt:
        return RuntimeReceipt(
            receipt_id=stable_id(
                "mission_campaign_control",
                self.config.mission_id,
                action,
                str(generation),
            ),
            receipt_type=CAMPAIGN_CONTROL_RECEIPT_TYPE,
            status=action,
            run_id=stable_id("mission_campaign_run", self.config.mission_id),
            correlation_id=self.config.session_id,
            agent_id=self.config.operator_id,
            payload={
                "schema_version": CAMPAIGN_SCHEMA_VERSION,
                "mission_id": self.config.mission_id,
                "action": action,
                "generation": generation,
                "preserves_queued_work": True,
            },
            created_at=now,
        )

    async def _require_snapshot(self) -> MissionSnapshot:
        snapshot = await self._control.get_snapshot(self.config.mission_id)
        if snapshot is None:
            raise MissionControlError(
                f"mission {self.config.mission_id!r} was not found"
            )
        if any(row.mission_id != self.config.mission_id for row in snapshot.receipts):
            raise MissionControlError("mission snapshot contains a foreign receipt")
        return snapshot

    async def _require_campaign_session(self) -> SessionState:
        session = await self._runtime.get_session(self.config.session_id)
        if session is None:
            raise MissionControlError("campaign has not been started")
        if (
            session.metadata.get("schema_version") != CAMPAIGN_SCHEMA_VERSION
            or session.metadata.get("mission_id") != self.config.mission_id
            or session.metadata.get("config_digest") != self.config.digest
        ):
            raise MissionControlError("campaign session has a foreign identity")
        self._session_generation(session)
        return session

    @staticmethod
    def _session_generation(session: SessionState) -> int:
        generation = session.metadata.get("generation")
        if isinstance(generation, bool) or not isinstance(generation, int):
            raise MissionControlError("campaign session generation is invalid")
        if generation < 1:
            raise MissionControlError("campaign session generation must be positive")
        return generation


def observer_only_adapter(
    mission_control: MissionControl,
    board: TaskBoard,
    runtime_state: RuntimeStateStore,
) -> OrchestratorMissionAdapter:
    """Construct the existing owner validator without an execution capability."""
    return OrchestratorMissionAdapter(  # type: ignore[arg-type]
        None,
        mission_control,
        board,
        runtime_state,
    )


__all__ = [
    "CAMPAIGN_CONTROL_RECEIPT_TYPE",
    "CAMPAIGN_CYCLE_RECEIPT_TYPE",
    "CAMPAIGN_SCHEMA_VERSION",
    "CampaignConfig",
    "CampaignSnapshot",
    "CampaignSupervisor",
    "observer_only_adapter",
]
