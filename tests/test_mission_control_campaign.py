from __future__ import annotations

import hashlib
import inspect
import json
import os
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import dharma_swarm.task_board as task_board_module
import dharma_swarm.mission_control_operator_runtime as operator_runtime
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_authority import (
    FileExecutionLeaseAuthorityVerifier,
)
from dharma_swarm.mission_control_campaign import (
    CAMPAIGN_CONTROL_RECEIPT_TYPE,
    CAMPAIGN_CYCLE_RECEIPT_TYPE,
    CampaignConfig,
    CampaignSupervisor,
)
from dharma_swarm.mission_control_contract import (
    MissionControlError,
    stable_id,
    utc_now,
)
from dharma_swarm.mission_control_dispatch import (
    CAMPAIGN_LEASE_SCHEMA_VERSION,
    GOVERNANCE_METADATA_KEY,
    LEASE_DISPATCH_ACTION,
    LEASE_WORKSPACE_ACTION,
    DispatchAuthorityEnvelope,
    GovernedMissionDispatcher,
    MissionDispatchRequest,
)
from dharma_swarm.mission_control_evidence import (
    ACCEPTANCE_RECEIPT_TYPE,
    VERIFIER_RESULT_RECEIPT_TYPE,
    IndependentAcceptance,
    candidate_output_digest,
)
from dharma_swarm.mission_control_execution import (
    EXECUTION_METADATA_KEY,
    OwnerExecutionObservation,
    OwnerExecutionRef,
)
from dharma_swarm.mission_control_operator_state import (
    OPERATOR_CONTROL_RECEIPT_TYPE,
    OPERATOR_CONTROL_STATE_FIELDS,
    canonical_utc_timestamp,
    runtime_receipt_content_digest,
    validate_operator_control_state,
)
from dharma_swarm.mission_control_operator_control import (
    ControlInboxPublisher,
    OperatorControlRequest,
)
from dharma_swarm.mission_control_operator_runtime import (
    OPERATOR_HMAC_CREDENTIAL_NAME,
    SADHANA_OPERATOR_CAMPAIGN_ID,
    SYSTEMD_CREDENTIALS_DIRECTORY_ENV,
    load_operator_hmac_credential,
    operator_control_reconciler_from_config,
)
from dharma_swarm.mission_control_service import CampaignService
from dharma_swarm.mission_control_roster import CampaignRosterError
from dharma_swarm.models import AgentRole, ProviderType, TaskStatus
from dharma_swarm.operator_core.execution_lease import (
    build_execution_lease,
    content_hash,
    record_lease_revocation,
    write_execution_lease,
)
from dharma_swarm.runtime_state import (
    ArtifactRecord,
    RuntimeReceipt,
    RuntimeStateStore,
    SessionEventRecord,
)
from dharma_swarm.runtime_state import DelegationRun, TaskClaim
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.task_board import TaskBoard
from scripts.runtime import mission_control_campaign as campaign_runtime

MISSION_ID = "campaign-alpha"


@dataclass(frozen=True)
class _ControlRequest:
    action: str
    request_id: str
    idempotency_key: str
    issued_at: str = "2026-08-23T00:00:00Z"
    expires_at: str = "2026-08-23T00:02:00Z"
    reason: str = "operator requested bounded campaign control"
    reject_time_window: bool = False

    def validate_time_window(self, *, now: datetime | None = None) -> None:
        assert now is not None and now.tzinfo is not None
        if self.reject_time_window:
            raise RuntimeError("expired fixture")


def _identity_receipt(
    identity: ExecutionIdentity,
    *,
    receipt_id: str,
    receipt_type: str,
    payload: dict[str, Any],
    status: str = "completed",
) -> RuntimeReceipt:
    return RuntimeReceipt(
        receipt_id=receipt_id,
        receipt_type=receipt_type,
        status=status,
        run_id=identity.run_id,
        task_id=identity.task_id,
        trace_id=identity.trace_id,
        correlation_id=identity.correlation_id,
        causation_id=identity.causation_id,
        parent_run_id=identity.parent_run_id,
        agent_id=identity.agent_id,
        idempotency_key=identity.idempotency_key,
        payload=payload,
        created_at=utc_now(),
    )


def _provider_receipt(
    identity: ExecutionIdentity,
    *,
    receipt_id: str,
    provider: str,
    model: str,
    truth_source: str = "llm_response",
) -> RuntimeReceipt:
    return _identity_receipt(
        identity,
        receipt_id=receipt_id,
        receipt_type="side_effect_complete",
        payload={
            "receipt": {
                "trace_id": identity.trace_id,
                "task_id": identity.task_id,
                "agent_id": identity.agent_id,
                "claim_id": identity.claim_id,
                "status": "ok",
                "attributes": {
                    "run_id": identity.run_id,
                    "dispatch_idempotency_key": identity.idempotency_key,
                    "served_provider": provider,
                    "served_model": model,
                    "provider_truth_source": truth_source,
                },
            }
        },
    )


class _OwnerReader:
    def __init__(self) -> None:
        self.refs: dict[str, OwnerExecutionRef] = {}
        self.observations: dict[str, OwnerExecutionObservation] = {}

    async def recover(
        self,
        mission_id: str,
        task_id: str,
        *,
        dispatch_key: str = "default",
    ) -> OwnerExecutionRef | None:
        ref = self.refs.get(task_id)
        if ref is not None:
            assert (ref.mission_id, ref.dispatch_key) == (mission_id, dispatch_key)
        return ref

    async def observe(self, ref: OwnerExecutionRef) -> OwnerExecutionObservation:
        return self.observations[ref.task_id]


class _CompletingDispatcher:
    def __init__(
        self,
        board: TaskBoard,
        runtime: RuntimeStateStore,
        reader: _OwnerReader,
    ) -> None:
        self.board = board
        self.runtime = runtime
        self.reader = reader
        self.calls = 0

    async def dispatch(self, task) -> OwnerExecutionRef:
        self.calls += 1
        ref = OwnerExecutionRef(
            backend="fixture-owner",
            mission_id=task.mission_id,
            task_id=task.task_id,
            dispatch_key="default",
            run_id=stable_id("owner_run", task.mission_id, task.task_id, "default"),
            claim_id=stable_id("owner_claim", task.mission_id, task.task_id),
            agent_id="producer-agent",
            idempotency_key=stable_id(
                "owner_dispatch", task.mission_id, task.task_id, "default"
            ),
            owner_session_id="owner-session",
        )
        current = await self.board.get(task.task_id)
        assert current is not None
        await self.board.update_task(
            task.task_id,
            metadata={
                **current.metadata,
                EXECUTION_METADATA_KEY: {"dispatch_key": "default"},
            },
        )
        self.reader.refs[task.task_id] = ref
        completed_at = utc_now()
        identity = ExecutionIdentity.new(
            trace_id=f"trace-{ref.run_id}",
            correlation_id=f"correlation-{ref.run_id}",
            task_id=task.task_id,
            run_id=ref.run_id,
            claim_id=ref.claim_id,
            agent_id=ref.agent_id,
            session_id=ref.owner_session_id,
            idempotency_key=ref.idempotency_key,
        )
        await self.runtime.record_execution_identity(identity, source="fixture-owner")
        await self.runtime.record_task_claim(
            TaskClaim(
                claim_id=ref.claim_id,
                task_id=task.task_id,
                agent_id=ref.agent_id,
                status="completed",
                session_id=ref.owner_session_id,
                claimed_at=completed_at,
                heartbeat_at=completed_at,
                metadata={"mission_id": task.mission_id},
            )
        )
        await self.runtime.record_delegation_run(
            DelegationRun(
                run_id=ref.run_id,
                task_id=task.task_id,
                assigned_to=ref.agent_id,
                assigned_by="fixture-owner",
                claim_id=ref.claim_id,
                session_id=ref.owner_session_id,
                status="completed",
                started_at=completed_at,
                completed_at=completed_at,
                metadata={"mission_id": task.mission_id},
            )
        )
        self.reader.observations[task.task_id] = OwnerExecutionObservation(
            ref=ref,
            task_status=TaskStatus.COMPLETED,
            run_status="completed",
            claim_status="completed",
            stale=False,
            receipt_ids=(),
            terminal=True,
            succeeded=True,
            result="candidate output",
            failure_code="",
            observed_at=utc_now(),
        )
        return ref


async def _stack(
    tmp_path: Path,
    *,
    held_out_oracle_digest: str = "",
    goal_id: str = "",
):
    board = TaskBoard(tmp_path / "tasks.db")
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await board.init_db()
    await runtime.init_db()
    control = MissionControl(board, runtime)
    await control.create_mission(MISSION_ID, title="Campaign Alpha")
    task = await control.create_task(
        MISSION_ID,
        title="Produce a candidate",
        idempotency_key="campaign-candidate",
        metadata={"goal_id": goal_id} if goal_id else None,
    )
    reader = _OwnerReader()
    dispatcher = _CompletingDispatcher(board, runtime, reader)
    supervisor = CampaignSupervisor(
        CampaignConfig(
            MISSION_ID,
            canary_task_id=task.task_id,
            held_out_oracle_digest=held_out_oracle_digest,
        ),
        control,
        board,
        runtime,
        reader,
        dispatcher=dispatcher,
    )
    return board, runtime, control, task, reader, dispatcher, supervisor


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_campaign_config_rejects_nonfinite_timing(invalid: float) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        CampaignConfig(MISSION_ID, cycle_interval_seconds=invalid)


@pytest.mark.parametrize(
    "invalid",
    ["mission/slash", "mission space", "x" * 201, "mïssion", "~mission", "-mission"],
)
def test_campaign_config_rejects_non_url_safe_mission_ids(invalid: str) -> None:
    with pytest.raises(ValueError, match="URL-safe"):
        CampaignConfig(invalid)


def test_campaign_config_bounds_projection_freshness() -> None:
    assert CampaignConfig(MISSION_ID, freshness_seconds=3600).freshness_seconds == 3600
    with pytest.raises(ValueError, match="at most 3600"):
        CampaignConfig(MISSION_ID, freshness_seconds=3600.01)
    with pytest.raises(ValueError, match="max_dispatch_per_cycle"):
        CampaignConfig(MISSION_ID, max_dispatch_per_cycle=1.5)  # type: ignore[arg-type]


def _operator_credential_environment(
    tmp_path: Path,
    secret: bytes,
) -> tuple[Path, dict[str, str]]:
    credentials = tmp_path / "credentials"
    credentials.mkdir(mode=0o700)
    credentials.chmod(0o700)
    credential = credentials / OPERATOR_HMAC_CREDENTIAL_NAME
    credential.write_bytes(secret)
    credential.chmod(0o600)
    return credential, {SYSTEMD_CREDENTIALS_DIRECTORY_ENV: str(credentials)}


def test_operator_runtime_requires_systemd_credential(
    tmp_path: Path,
) -> None:
    with pytest.raises(MissionControlError, match="requires the systemd operator HMAC"):
        operator_control_reconciler_from_config(
            SADHANA_OPERATOR_CAMPAIGN_ID,
            credential_environ={},
        )

    secret = b"sadhana-runtime-hmac-credential-32-bytes"
    _, environment = _operator_credential_environment(tmp_path, secret)
    assert load_operator_hmac_credential(environ=environment) == secret


@pytest.mark.parametrize(
    "custody_fault",
    [
        "directory_mode",
        "file_mode",
        "hardlink",
        "file_symlink",
        "directory_symlink",
        "missing",
    ],
)
def test_operator_runtime_credential_custody_fails_closed(
    tmp_path: Path,
    custody_fault: str,
) -> None:
    secret = b"sadhana-runtime-hmac-credential-32-bytes"
    credential, environment = _operator_credential_environment(tmp_path, secret)
    credentials = credential.parent
    if custody_fault == "directory_mode":
        credentials.chmod(0o755)
    elif custody_fault == "file_mode":
        credential.chmod(0o640)
    elif custody_fault == "hardlink":
        os.link(credential, credentials / "operator-hardlink.hmac")
    elif custody_fault == "file_symlink":
        credential.unlink()
        credential.symlink_to(tmp_path / "foreign-credential")
    elif custody_fault == "directory_symlink":
        alias = tmp_path / "credentials-link"
        alias.symlink_to(credentials, target_is_directory=True)
        environment[SYSTEMD_CREDENTIALS_DIRECTORY_ENV] = str(alias)
    else:
        credential.unlink()

    with pytest.raises(MissionControlError, match="custody|opened exactly") as raised:
        load_operator_hmac_credential(environ=environment)
    error = str(raised.value)
    assert secret.decode() not in error
    assert hashlib.sha256(secret).hexdigest() not in error
    assert str(len(secret)) not in error


@pytest.mark.parametrize("flag", ["O_NOFOLLOW", "O_DIRECTORY"])
def test_operator_runtime_requires_nofollow_directory_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
) -> None:
    secret = b"sadhana-runtime-hmac-credential-32-bytes"
    _, environment = _operator_credential_environment(tmp_path, secret)
    monkeypatch.setattr(operator_runtime.os, flag, 0)

    with pytest.raises(MissionControlError, match="O_NOFOLLOW and O_DIRECTORY"):
        load_operator_hmac_credential(environ=environment)


@pytest.mark.asyncio
async def test_operator_pause_is_atomic_replayable_and_suppresses_dispatch(
    tmp_path: Path,
) -> None:
    _, runtime, _, _, _, dispatcher, supervisor = await _stack(tmp_path)
    await supervisor.start()
    request = _ControlRequest("pause", "pause-one", "pause-idem-one")
    envelope = "sha256:" + "a" * 64

    applied = await supervisor.apply_operator_control_result(
        request,
        "operator@example.com",
        envelope,
    )
    session = await runtime.get_session(supervisor.config.session_id)
    assert session is not None
    assert applied.status == "applied"
    assert session.status == "paused"
    assert (
        set(session.metadata["operator_control_state"]) == OPERATOR_CONTROL_STATE_FIELDS
    )
    assert session.metadata["operator_control_state"] == {
        "schema_version": "dharma.sadhana.operator_control_state.v1",
        "control_state": "PAUSED",
        "campaign_generation": 1,
        "transition_sequence": 1,
        "request_id": request.request_id,
        "idempotency_key": request.idempotency_key,
        "action": "pause",
        "source_envelope_sha256": envelope,
        "authority_receipt_ref": applied.authority_receipt_ref,
        "authority_receipt_sha256": applied.authority_receipt_sha256,
        "authority_applied_at": canonical_utc_timestamp(session.updated_at),
        "effect_state": "unobserved",
        "effect_receipt_ref": "",
        "effect_receipt_sha256": "",
        "effect_observed_at": None,
    }
    assert session.metadata["operator_control_state"]["authority_applied_at"].endswith(
        "Z"
    )
    assert (
        "+00:00"
        not in session.metadata["operator_control_state"]["authority_applied_at"]
    )
    receipt = await runtime.get_runtime_receipt(
        applied.authority_receipt_ref.removeprefix("runtime-receipt:")
    )
    assert receipt is not None
    assert receipt.receipt_type == OPERATOR_CONTROL_RECEIPT_TYPE
    assert runtime_receipt_content_digest(receipt) == applied.authority_receipt_sha256

    paused = await supervisor.cycle(writer_lock_held=True)
    assert dispatcher.calls == 0
    assert paused.campaign_status == "paused"
    assert paused.cycle_sequence == 1
    assert paused.operator_control_state == session.metadata["operator_control_state"]
    after_paused_cycle = await runtime.get_session(supervisor.config.session_id)

    replay = await supervisor.apply_operator_control_result(
        replace(request, reject_time_window=True),
        "operator@example.com",
        envelope,
    )
    assert replay == applied
    assert await runtime.get_session(supervisor.config.session_id) == after_paused_cycle


@pytest.mark.asyncio
async def test_signed_pause_runtime_composition_suppresses_same_cycle_dispatch(
    tmp_path: Path,
) -> None:
    _, runtime, _, _, _, dispatcher, supervisor = await _stack(tmp_path)
    await supervisor.start()
    control_root = tmp_path / "operator-control"
    normal = control_root / "normal"
    emergency = control_root / "emergency"
    inflight = control_root / "inflight"
    applied = control_root / "applied"
    rejected = control_root / "rejected"
    for directory in (normal, emergency, inflight, applied, rejected):
        directory.mkdir(parents=True, exist_ok=True)

    secret = b"sadhana-operator-runtime-composition-secret"
    _, environment = _operator_credential_environment(tmp_path, secret)
    reconciler = operator_control_reconciler_from_config(
        MISSION_ID,
        normal_inbox=normal,
        inflight_inbox=inflight,
        applied_inbox=applied,
        rejected_inbox=rejected,
        credential_environ=environment,
    )
    assert reconciler is not None

    now = datetime.now(timezone.utc)

    def timestamp(value: datetime) -> str:
        return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    request = OperatorControlRequest.from_mapping(
        {
            "action": "pause",
            "request_id": "runtime-pause-one",
            "idempotency_key": "runtime-pause-idem-one",
            "issued_at": timestamp(now - timedelta(seconds=1)),
            "expires_at": timestamp(now + timedelta(seconds=60)),
            "reason": "Pause before the next campaign effect lane",
        }
    )
    publication = ControlInboxPublisher(normal, emergency).publish(
        request,
        operator_login="operator@example.com",
        secret=secret,
        now=now,
    )

    result = await CampaignService(
        supervisor,
        lock_path=tmp_path / "campaign.lock",
        control_gate_path=tmp_path / "campaign.control.lock",
        projection_path=tmp_path / "campaign-status.json",
        operator_control_reconciler=reconciler,
    ).run(max_cycles=1, start_campaign=False)

    session = await runtime.get_session(supervisor.config.session_id)
    assert session is not None
    assert session.status == "paused"
    assert session.metadata["operator_control_state"]["transition_sequence"] == 1
    assert dispatcher.calls == 0
    assert result.snapshot.campaign_status == "paused"
    private_values = (
        secret.decode(),
        hashlib.sha256(secret).hexdigest(),
    )
    projected = json.dumps(result.snapshot.to_dict(), sort_keys=True)
    session_state = json.dumps(session.metadata, sort_keys=True)
    reconciler_state = repr(reconciler)
    assert all(value not in projected for value in private_values)
    assert all(value not in session_state for value in private_values)
    assert all(value not in reconciler_state for value in private_values)
    for length_field in ("credential_length", "hmac_key_length", "secret_length"):
        assert length_field not in projected
        assert length_field not in session_state
    assert not publication.path.exists()
    assert len(tuple(applied.glob("*.control.json"))) == 1
    assert len(tuple(applied.glob("*.terminal.json"))) == 1
    assert not tuple(rejected.iterdir())


@pytest.mark.asyncio
async def test_operator_resume_retains_generation_and_advances_exact_sequence(
    tmp_path: Path,
) -> None:
    _, runtime, _, _, _, _, supervisor = await _stack(tmp_path)
    await supervisor.start()
    await supervisor.apply_operator_control_result(
        _ControlRequest("pause", "pause-one", "pause-idem-one"),
        "operator@example.com",
        "sha256:" + "a" * 64,
    )

    result = await supervisor.apply_operator_control_result(
        _ControlRequest("resume", "resume-one", "resume-idem-one"),
        "operator@example.com",
        "sha256:" + "b" * 64,
    )
    session = await runtime.get_session(supervisor.config.session_id)
    assert session is not None
    assert result.status == "applied"
    assert session.status == "active"
    assert session.metadata["generation"] == 1
    assert session.metadata["operator_control_state"]["control_state"] == "RUNNING"
    assert session.metadata["operator_control_state"]["transition_sequence"] == 2
    assert await supervisor.effects_enabled() is True


@pytest.mark.asyncio
async def test_operator_effect_evidence_cannot_equivocate_at_authority_sequence(
    tmp_path: Path,
) -> None:
    _, runtime, _, _, _, _, supervisor = await _stack(tmp_path)
    await supervisor.start()
    await supervisor.apply_operator_control_result(
        _ControlRequest("pause", "pause-effect", "pause-effect-idem"),
        "operator@example.com",
        "sha256:" + "d" * 64,
    )
    session = await runtime.get_session(supervisor.config.session_id)
    assert session is not None
    forged = dict(session.metadata["operator_control_state"])
    forged.update(
        {
            "effect_state": "observed",
            "effect_receipt_ref": "runtime-receipt:forged-effect",
            "effect_receipt_sha256": "sha256:" + "e" * 64,
            "effect_observed_at": canonical_utc_timestamp(session.updated_at),
        }
    )

    with pytest.raises(ValueError, match="separately admitted receipt transition"):
        validate_operator_control_state(forged, expected_generation=1)


@pytest.mark.asyncio
async def test_new_expired_operator_request_is_rejected_without_session_mutation(
    tmp_path: Path,
) -> None:
    _, runtime, _, _, _, _, supervisor = await _stack(tmp_path)
    before = await supervisor.start()
    request = _ControlRequest(
        "pause",
        "expired-one",
        "expired-idem-one",
        reject_time_window=True,
    )

    rejected = await supervisor.apply_operator_control_result(
        request,
        "operator@example.com",
        "sha256:" + "c" * 64,
    )

    assert rejected.status == "rejected"
    assert rejected.authority_receipt_ref
    assert rejected.authority_receipt_sha256.startswith("sha256:")
    assert await runtime.get_session(supervisor.config.session_id) == before
    stored = await runtime.get_runtime_receipt(
        rejected.authority_receipt_ref.removeprefix("runtime-receipt:")
    )
    assert stored is not None
    assert stored.payload["rejection_reason"] == "time_window_RuntimeError"


@pytest.mark.asyncio
async def test_operator_idempotency_conflict_returns_original_identity_for_quarantine(
    tmp_path: Path,
) -> None:
    _, runtime, _, _, _, _, supervisor = await _stack(tmp_path)
    await supervisor.start()
    original = _ControlRequest("pause", "pause-one", "shared-idem")
    first = await supervisor.apply_operator_control_result(
        original,
        "operator@example.com",
        "sha256:" + "d" * 64,
    )
    after_first = await runtime.get_session(supervisor.config.session_id)

    conflict = await supervisor.apply_operator_control_result(
        _ControlRequest("pause", "foreign-request", "shared-idem"),
        "operator@example.com",
        "sha256:" + "e" * 64,
    )

    assert conflict == first
    assert conflict.request_id == original.request_id
    assert await runtime.get_session(supervisor.config.session_id) == after_first


@pytest.mark.asyncio
async def test_operator_session_cas_loss_defers_without_claiming_a_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, runtime, _, _, _, _, supervisor = await _stack(tmp_path)
    before = await supervisor.start()

    async def lose_cas(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(runtime, "compare_and_swap_session", lose_cas)
    result = await supervisor.apply_operator_control_result(
        _ControlRequest("pause", "pause-lost", "pause-idem-lost"),
        "operator@example.com",
        "sha256:" + "f" * 64,
    )

    assert result.status == "deferred"
    assert result.authority_receipt_ref == ""
    assert result.authority_receipt_sha256 == ""
    assert await runtime.get_session(supervisor.config.session_id) == before
    receipts = await runtime.list_runtime_receipts(
        receipt_type=OPERATOR_CONTROL_RECEIPT_TYPE,
        limit=10,
    )
    assert receipts == []


@pytest.mark.asyncio
async def test_first_start_rolls_back_session_when_control_receipt_conflicts(
    tmp_path: Path,
) -> None:
    _, runtime, _, _, _, _, supervisor = await _stack(tmp_path)
    await runtime.insert_runtime_receipt_exact(
        RuntimeReceipt(
            receipt_id=stable_id(
                "mission_campaign_control",
                MISSION_ID,
                "start",
                "1",
            ),
            receipt_type=CAMPAIGN_CONTROL_RECEIPT_TYPE,
            status="foreign",
            correlation_id=supervisor.config.session_id,
            payload={"mission_id": "foreign"},
            created_at=utc_now(),
        )
    )

    with pytest.raises(ValueError, match="atomic session receipt identity"):
        await supervisor.start()

    assert await runtime.get_session(supervisor.config.session_id) is None


@pytest.mark.asyncio
async def test_completed_owner_output_is_candidate_until_independently_accepted(
    tmp_path: Path,
) -> None:
    _, runtime, _, task, _, dispatcher, supervisor = await _stack(tmp_path)
    await supervisor.start()
    before_cycle = await supervisor.status(writer_lock_held=True)
    assert before_cycle.cycle_sequence == 0
    assert before_cycle.latest_cycle_at is None

    candidate = await supervisor.cycle(writer_lock_held=True)

    assert dispatcher.calls == 1
    assert candidate.candidate_task_ids == (task.task_id,)
    assert candidate.accepted_task_ids == ()
    assert candidate.acceptance_state == "candidate_only"
    assert candidate.canary_acceptance == "candidate"
    assert candidate.proves_semantic_acceptance is False
    assert candidate.mission_snapshot.attempts == ()
    assert len(candidate.owner_executions) == 1

    producer_ref = candidate.owner_executions[0].ref
    await runtime.record_runtime_receipt(
        RuntimeReceipt(
            receipt_id="transport-receipt",
            receipt_type="nats_publish",
            status="acknowledged",
            run_id=producer_ref.run_id,
            task_id=task.task_id,
            agent_id=producer_ref.agent_id,
        )
    )
    producer_identity = await runtime.get_execution_identity(producer_ref.run_id)
    assert producer_identity is not None
    producer_run = await runtime.get_delegation_run(producer_ref.run_id)
    assert producer_run is not None and producer_run.completed_at is not None
    await runtime.record_runtime_receipt(
        _provider_receipt(
            producer_identity,
            receipt_id="configured-model-receipt",
            provider="configured-provider",
            model="configured-only-family",
            truth_source="runner_config",
        )
    )
    configured_only = await supervisor.status(writer_lock_held=True)
    assert configured_only.model_execution_state == "unobserved"
    assert configured_only.proves_model_execution is False
    await runtime.record_runtime_receipt(
        replace(
            _provider_receipt(
                producer_identity,
                receipt_id="model-receipt",
                provider="fixture-provider",
                model="producer-family",
            ),
            created_at=producer_run.completed_at,
        )
    )
    for receipt_id, created_at in (
        (
            "pre-start-model-receipt",
            producer_run.started_at - timedelta(microseconds=1),
        ),
        (
            "post-completion-model-receipt",
            producer_run.completed_at + timedelta(microseconds=1),
        ),
    ):
        await runtime.record_runtime_receipt(
            replace(
                _provider_receipt(
                    producer_identity,
                    receipt_id=receipt_id,
                    provider="fixture-provider",
                    model="outside-window-family",
                ),
                created_at=created_at,
            )
        )
    routed = await supervisor.status(writer_lock_held=True)
    assert routed.transport_state == "observed"
    assert routed.model_execution_state == "observed"
    assert routed.proves_model_execution is True

    evidence_id = "verifier-receipt"
    verifier_identity = ExecutionIdentity.new(
        trace_id="verifier-trace",
        correlation_id="verifier-correlation",
        task_id=task.task_id,
        run_id="verifier-run",
        claim_id="verifier-claim",
        agent_id="verifier-agent",
        session_id="verifier-session",
        idempotency_key="verifier-idempotency",
    )
    await runtime.record_execution_identity(
        verifier_identity,
        source="test-verifier",
    )
    await runtime.record_runtime_receipt(
        replace(
            _provider_receipt(
                verifier_identity,
                receipt_id="old-verifier-provider-receipt",
                provider="verifier-provider",
                model="verifier-family",
            ),
            created_at=producer_run.completed_at - timedelta(microseconds=1),
        )
    )
    await runtime.record_runtime_receipt(
        _identity_receipt(
            verifier_identity,
            receipt_id=evidence_id,
            receipt_type=VERIFIER_RESULT_RECEIPT_TYPE,
            payload={
                "actual_served_provider": "verifier-provider",
                "actual_served_model": "verifier-family",
                "producer_output_digest": candidate_output_digest("candidate output"),
                "accepted": True,
            },
        )
    )
    acceptance = IndependentAcceptance.new(
        mission_id=MISSION_ID,
        task_id=task.task_id,
        producer_run_id=producer_ref.run_id,
        producer_agent_id="producer-agent",
        producer_model_family="producer-family",
        producer_output_digest=candidate_output_digest("candidate output"),
        verifier_run_id="verifier-run",
        verifier_agent_id="verifier-agent",
        verifier_model_family="verifier-family",
        oracle_kind="model",
        accepted=True,
        observed_at=utc_now(),
        rationale="Independent fixture review passed.",
        evidence_receipt_ids=(evidence_id,),
    )
    with pytest.raises(MissionControlError, match="verifier model family"):
        await supervisor.accept(acceptance)
    await runtime.record_runtime_receipt(
        replace(
            _provider_receipt(
                verifier_identity,
                receipt_id="fresh-verifier-provider-receipt",
                provider="verifier-provider",
                model="verifier-family",
            ),
            created_at=acceptance.observed_at,
        )
    )
    outside_window_acceptance = IndependentAcceptance.new(
        mission_id=acceptance.mission_id,
        task_id=acceptance.task_id,
        producer_run_id=acceptance.producer_run_id,
        producer_agent_id=acceptance.producer_agent_id,
        producer_model_family="outside-window-family",
        producer_output_digest=acceptance.producer_output_digest,
        verifier_run_id=acceptance.verifier_run_id,
        verifier_agent_id=acceptance.verifier_agent_id,
        verifier_model_family=acceptance.verifier_model_family,
        oracle_kind=acceptance.oracle_kind,
        accepted=acceptance.accepted,
        observed_at=acceptance.observed_at,
        rationale=acceptance.rationale,
        evidence_receipt_ids=acceptance.evidence_receipt_ids,
    )
    with pytest.raises(MissionControlError, match="producer model family"):
        await supervisor.accept(outside_window_acceptance)
    acceptance_receipt = await supervisor.accept(acceptance)
    assert acceptance_receipt.run_id == acceptance.verifier_run_id
    assert acceptance_receipt.causation_id == producer_ref.run_id
    producer_receipts = await runtime.list_runtime_receipts(
        run_id=producer_ref.run_id,
        limit=100,
    )
    assert acceptance_receipt.receipt_id not in {
        receipt.receipt_id for receipt in producer_receipts
    }
    with pytest.raises(ValueError, match="conflicting evidence"):
        await runtime.insert_runtime_receipt_exact(
            replace(acceptance_receipt, status="rejected")
        )

    accepted = await supervisor.status(writer_lock_held=True)
    assert accepted.accepted_task_ids == (task.task_id,)
    assert accepted.candidate_task_ids == ()
    assert accepted.canary_acceptance == "accepted"
    assert accepted.proves_semantic_acceptance is True

    await runtime.record_runtime_receipt(
        replace(acceptance_receipt, receipt_id="copied-acceptance-carrier")
    )
    copied = await supervisor.status(writer_lock_held=True)
    assert copied.accepted_task_ids == (task.task_id,)
    assert copied.invalid_acceptance_receipts == 1

    with pytest.raises(ValueError, match="immutable runtime receipt"):
        await runtime.record_runtime_receipt(
            replace(
                acceptance_receipt,
                payload={**acceptance_receipt.payload, "rationale": "tampered"},
            )
        )
    preserved = await supervisor.status(writer_lock_held=True)
    assert preserved.accepted_task_ids == (task.task_id,)
    assert preserved.invalid_acceptance_receipts == 1


def test_same_generator_verifier_is_rejected_except_held_out_oracle() -> None:
    values: dict[str, Any] = {
        "mission_id": MISSION_ID,
        "task_id": "task-alpha",
        "producer_run_id": "producer-run",
        "producer_agent_id": "same-agent",
        "producer_model_family": "same-family",
        "producer_output_digest": candidate_output_digest("candidate output"),
        "verifier_run_id": "verifier-run",
        "verifier_agent_id": "same-agent",
        "verifier_model_family": "same-family",
        "accepted": True,
        "observed_at": utc_now(),
        "rationale": "Deterministic validation result.",
        "evidence_receipt_ids": ("oracle-receipt",),
    }
    with pytest.raises(MissionControlError, match="must be independent"):
        IndependentAcceptance.new(oracle_kind="model", **values)

    held_out = IndependentAcceptance.new(
        oracle_kind="deterministic_held_out",
        oracle_digest="sha256:" + "a" * 64,
        **values,
    )
    assert held_out.oracle_kind == "deterministic_held_out"


@pytest.mark.asyncio
async def test_g10_model_acceptance_is_rejected_without_writing_receipt(
    tmp_path: Path,
) -> None:
    _, runtime, _, task, _, _, supervisor = await _stack(
        tmp_path,
        goal_id="G10_SAFETY_TCB",
    )
    await supervisor.start()
    acceptance = IndependentAcceptance.new(
        mission_id=MISSION_ID,
        task_id=task.task_id,
        producer_run_id="producer-run",
        producer_agent_id="producer-agent",
        producer_model_family="producer-family",
        producer_output_digest=candidate_output_digest("candidate output"),
        verifier_run_id="verifier-run",
        verifier_agent_id="verifier-agent",
        verifier_model_family="distinct-verifier-family",
        oracle_kind="model",
        accepted=True,
        observed_at=utc_now(),
        rationale="Distinct-family model verdict must not accept the safety TCB.",
        evidence_receipt_ids=("verifier-receipt",),
    )

    with pytest.raises(MissionControlError, match="held-out oracle"):
        await supervisor.accept(acceptance)
    assert (
        await runtime.list_runtime_receipts(
            correlation_id=supervisor.config.session_id,
            receipt_type=ACCEPTANCE_RECEIPT_TYPE,
            limit=100,
        )
        == []
    )


@pytest.mark.asyncio
async def test_projection_rejects_foreign_nested_receipt_mission(
    tmp_path: Path,
) -> None:
    _, runtime, control, task, _, _, supervisor = await _stack(tmp_path)
    await supervisor.start()
    attempt = await control.start_attempt(MISSION_ID, task.task_id, "native-agent")
    identity = await runtime.get_execution_identity(attempt.attempt_id)
    assert identity is not None
    await runtime.record_runtime_receipt(
        _identity_receipt(
            identity,
            receipt_id="foreign-mission-receipt",
            receipt_type="test_observation",
            payload={"mission_id": "foreign-mission"},
        )
    )

    with pytest.raises(MissionControlError, match="foreign receipt"):
        await supervisor.status(writer_lock_held=True)


@pytest.mark.asyncio
async def test_stop_preserves_queued_work_and_refuses_unauthorized_restart(
    tmp_path: Path,
) -> None:
    board, runtime, control, task, reader, dispatcher, supervisor = await _stack(
        tmp_path
    )
    await supervisor.start()
    await supervisor.cycle(writer_lock_held=True)
    assert dispatcher.calls == 1

    await supervisor.stop()
    stopped_session = await runtime.get_session(supervisor.config.session_id)
    assert stopped_session is not None
    stop_receipt = await runtime.get_runtime_receipt(
        stable_id("mission_campaign_control", MISSION_ID, "stop", "1")
    )
    assert stop_receipt is not None
    assert await runtime.upsert_session(stopped_session) == stopped_session
    resurrected_metadata = {**stopped_session.metadata, "stop_requested": False}
    for metadata in (
        resurrected_metadata,
        {
            key: value
            for key, value in resurrected_metadata.items()
            if key != "schema_version"
        },
    ):
        resurrection = replace(
            stopped_session,
            status="active",
            metadata=metadata,
            updated_at=stopped_session.updated_at + timedelta(microseconds=1),
        )
        with pytest.raises(ValueError, match="reserved campaign session"):
            await runtime.upsert_session(resurrection)
        with pytest.raises(ValueError, match="reserved campaign session"):
            await runtime.compare_and_swap_session(stopped_session, resurrection)
        with pytest.raises(ValueError, match="campaign"):
            await runtime.compare_and_swap_session(
                stopped_session,
                resurrection,
                atomic_receipt=stop_receipt,
            )
    cycle_receipt = await runtime.get_runtime_receipt(
        str(stopped_session.metadata["last_cycle_receipt_id"])
    )
    assert cycle_receipt is not None
    conflicting_cycle = replace(
        cycle_receipt,
        status="partial" if cycle_receipt.status == "completed" else "completed",
    )
    event = SessionEventRecord(
        event_id="campaign-event-async",
        session_id=stopped_session.session_id,
        ledger_kind="test",
        event_name="attempted_mutation",
        task_id="forged-current-task",
        created_at=stopped_session.updated_at + timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="immutable runtime receipt"):
        await runtime.record_session_event_with_runtime_receipt(
            event,
            conflicting_cycle,
        )
    with pytest.raises(ValueError, match="immutable runtime receipt"):
        runtime.record_session_event_with_runtime_receipt_sync(
            replace(event, event_id="campaign-event-sync"),
            conflicting_cycle,
        )
    await runtime.record_session_event(
        replace(event, event_id="campaign-event-allowed")
    )
    assert await runtime.get_session(stopped_session.session_id) == stopped_session
    assert await runtime.get_runtime_receipt(cycle_receipt.receipt_id) == cycle_receipt
    queued = await control.create_task(
        MISSION_ID,
        title="Queued after stop",
        idempotency_key="queued-after-stop",
    )
    stopped = await supervisor.cycle(writer_lock_held=True)
    assert stopped.supervisor_state == "stopped"
    assert dispatcher.calls == 1  # durable stop fences every later submission
    stored = await board.get(queued.task_id)
    assert stored is not None and stored.status is TaskStatus.PENDING

    restarted_dispatcher = _CompletingDispatcher(board, runtime, reader)
    restarted = CampaignSupervisor(
        supervisor.config,
        control,
        board,
        runtime,
        reader,
        dispatcher=restarted_dispatcher,
    )
    with pytest.raises(MissionControlError, match="separately admitted authority"):
        await restarted.start()
    snapshot = await restarted.cycle(writer_lock_held=True)
    assert any(item.ref.task_id == task.task_id for item in snapshot.owner_executions)
    assert snapshot.campaign_status == "stopped"
    assert restarted_dispatcher.calls == 0


@pytest.mark.asyncio
async def test_process_restart_adopts_paused_generation_without_resuming(
    tmp_path: Path,
) -> None:
    board, runtime, control, _, reader, dispatcher, supervisor = await _stack(tmp_path)
    started = await supervisor.start()
    await supervisor.apply_operator_control_result(
        _ControlRequest("pause", "pause-restart", "pause-restart-idem"),
        "operator@example.com",
        "sha256:" + "7" * 64,
    )
    paused = await runtime.get_session(supervisor.config.session_id)
    assert paused is not None and paused.status == "paused"

    restarted = CampaignSupervisor(
        supervisor.config,
        control,
        board,
        runtime,
        reader,
        dispatcher=dispatcher,
    )
    adopted = await restarted.start()

    assert adopted == paused
    assert adopted.metadata["generation"] == started.metadata["generation"] == 1
    snapshot = await restarted.cycle(writer_lock_held=True)
    assert snapshot.campaign_status == "paused"
    assert dispatcher.calls == 0


@pytest.mark.asyncio
async def test_cycle_history_is_immutable_and_constant_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, runtime, _, _, _, _, supervisor = await _stack(tmp_path)
    await supervisor.start()

    first = await supervisor.cycle(writer_lock_held=True)
    second = await supervisor.cycle(writer_lock_held=True)

    assert (first.generation, first.cycle_sequence) == (1, 1)
    assert (second.generation, second.cycle_sequence) == (1, 2)
    rows = await runtime.list_runtime_receipts(
        correlation_id=supervisor.config.session_id,
        receipt_type=CAMPAIGN_CYCLE_RECEIPT_TYPE,
        limit=10,
    )
    assert [row.payload["sequence"] for row in rows] == [1, 2]
    assert len({row.receipt_id for row in rows}) == 2
    session = await runtime.get_session(supervisor.config.session_id)
    assert session is not None
    assert session.metadata["last_cycle_sequence"] == 2
    assert session.metadata["last_cycle_receipt_id"] == rows[-1].receipt_id
    with pytest.raises(ValueError, match="cycle receipt carrier"):
        await runtime.insert_runtime_receipt_exact(
            replace(
                rows[-1],
                receipt_id="forged-duplicate-cycle",
                idempotency_key="forged-duplicate-cycle",
                created_at=rows[-1].created_at + timedelta(microseconds=1),
            )
        )
    original_list = runtime.list_runtime_receipts
    cycle_scans = 0

    async def _synthetic_large_history(**filters: Any):
        nonlocal cycle_scans
        if filters.get("receipt_type") == CAMPAIGN_CYCLE_RECEIPT_TYPE:
            cycle_scans += 1
            return [rows[-1]] * 10_001
        return await original_list(**filters)

    monkeypatch.setattr(runtime, "list_runtime_receipts", _synthetic_large_history)
    after_large_history = await supervisor.status(writer_lock_held=True)
    assert after_large_history.cycle_sequence == 2
    assert cycle_scans == 0


@pytest.mark.asyncio
async def test_g10_candidate_dependency_requires_held_out_acceptance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fast_gate,
) -> None:
    oracle_digest = "sha256:" + "b" * 64
    monkeypatch.setattr(
        task_board_module,
        "check_with_reflective_reroute",
        lambda **_: fast_gate,
    )
    board, runtime, control, task, _, dispatcher, supervisor = await _stack(
        tmp_path,
        held_out_oracle_digest=oracle_digest,
        goal_id="G10_SAFETY_TCB",
    )
    dependent = await control.create_task(
        MISSION_ID,
        title="Consume accepted candidate",
        depends_on=[task.task_id],
        idempotency_key="accepted-dependent",
    )
    await supervisor.start()
    candidate = await supervisor.cycle(writer_lock_held=True)
    assert dispatcher.calls == 1
    assert dependent.task_id not in dispatcher.reader.refs

    current = await board.get(task.task_id)
    assert current is not None
    await board.assign(task.task_id, "producer-agent", metadata=current.metadata)
    await board.start(task.task_id)
    await board.complete(task.task_id, result="candidate output")
    await supervisor.cycle(writer_lock_held=True)
    assert dispatcher.calls == 1

    oracle_identity = ExecutionIdentity.new(
        trace_id="oracle-trace",
        correlation_id="oracle-correlation",
        task_id=task.task_id,
        run_id="oracle-run",
        claim_id="oracle-claim",
        agent_id="oracle-agent",
        session_id="oracle-session",
        idempotency_key="oracle-idempotency",
    )
    await runtime.record_execution_identity(
        oracle_identity,
        source="test-oracle",
    )
    await runtime.record_runtime_receipt(
        _identity_receipt(
            oracle_identity,
            receipt_id="oracle-receipt",
            receipt_type=VERIFIER_RESULT_RECEIPT_TYPE,
            payload={
                "producer_output_digest": candidate_output_digest("candidate output"),
                "oracle_manifest_digest": oracle_digest,
                "accepted": True,
                "oracle_evaluator": "fixture-held-out-evaluator",
                "oracle_version": "v1",
            },
        )
    )
    await runtime.record_artifact(
        ArtifactRecord(
            artifact_id="oracle-artifact",
            artifact_kind="mission_held_out_oracle_verdict",
            session_id="oracle-session",
            task_id=task.task_id,
            run_id="oracle-run",
            checksum="sha256:" + "c" * 64,
            metadata={
                "producer_output_digest": candidate_output_digest("candidate output"),
                "oracle_manifest_digest": oracle_digest,
                "accepted": True,
                "oracle_evaluator": "fixture-held-out-evaluator",
                "oracle_version": "v1",
            },
        )
    )
    producer = candidate.owner_executions[0].ref
    acceptance_receipt = await supervisor.accept(
        IndependentAcceptance.new(
            mission_id=MISSION_ID,
            task_id=task.task_id,
            producer_run_id=producer.run_id,
            producer_agent_id=producer.agent_id,
            producer_model_family="producer-family",
            producer_output_digest=candidate_output_digest("candidate output"),
            verifier_run_id="oracle-run",
            verifier_agent_id="oracle-agent",
            verifier_model_family="deterministic-oracle",
            oracle_kind="deterministic_held_out",
            oracle_digest=oracle_digest,
            accepted=True,
            observed_at=utc_now(),
            rationale="Held-out deterministic oracle passed.",
            evidence_receipt_ids=("oracle-receipt",),
            evidence_artifact_ids=("oracle-artifact",),
        )
    )
    assert acceptance_receipt.status == "accepted"
    await supervisor.cycle(writer_lock_held=True)
    assert dispatcher.calls == 2
    assert dependent.task_id in dispatcher.reader.refs


class _EffectExecutor:
    def __init__(self, task_id: str) -> None:
        self.calls = 0
        self.ref = OwnerExecutionRef(
            backend="fixture",
            mission_id=MISSION_ID,
            task_id=task_id,
            dispatch_key="default",
            run_id="owner-run",
            claim_id="owner-claim",
            agent_id="owner-agent",
            idempotency_key="owner-key",
            owner_session_id="owner-session",
        )

    async def dispatch(
        self,
        mission_id: str,
        task_id: str,
        *,
        dispatch_key: str = "default",
        authenticated_principal_id: str = "",
    ) -> OwnerExecutionRef:
        self.calls += 1
        return replace(
            self.ref,
            mission_id=mission_id,
            task_id=task_id,
            dispatch_key=dispatch_key,
        )


class _RevokingBoard:
    def __init__(self, board: TaskBoard, lease_root: Path, lease_id: str) -> None:
        self._board = board
        self._lease_root = lease_root
        self._lease_id = lease_id
        self.calls = 0

    async def get(self, task_id: str):
        self.calls += 1
        if self.calls == 6:
            record_lease_revocation(
                self._lease_root,
                self._lease_id,
                reason="fixture rotation before effect",
            )
        return await self._board.get(task_id)


@pytest.mark.asyncio
async def test_file_authority_reloads_revocation_before_governed_effect(
    tmp_path: Path,
) -> None:
    board = TaskBoard(tmp_path / "tasks.db")
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await board.init_db()
    await runtime.init_db()
    control = MissionControl(board, runtime)
    await control.create_mission(MISSION_ID, title="Governed Campaign")
    task = await control.create_task(
        MISSION_ID,
        title="goal-one",
        description="Return a local summary.",
        idempotency_key="governed-campaign-task",
        metadata={GOVERNANCE_METADATA_KEY: {"allowed_files": ["bounded/workspace"]}},
    )
    request = MissionDispatchRequest.new(
        MISSION_ID,
        task.task_id,
        claimed_principal="campaign-principal",
        attempt_generation=0,
    )
    lease = build_execution_lease(
        issued_to=request.claimed_principal,
        task_id=task.task_id,
        correlation_id=request.request_id,
        lease_id="lease-campaign",
        allowed_actions=[LEASE_DISPATCH_ACTION, LEASE_WORKSPACE_ACTION],
        allowed_paths=["bounded/workspace"],
    )
    observed_content = "Observed revocation fixture; verify independently.\n"
    observed_content_sha256 = (
        "sha256:" + hashlib.sha256(observed_content.encode()).hexdigest()
    )
    observed_ref = {
        "receipt_id": "observed-receipt-revocation",
        "receipt_sha256": "sha256:" + "1" * 64,
        "artifact_id": "observed-artifact-revocation",
        "artifact_record_sha256": "sha256:" + "2" * 64,
        "content_sha256": observed_content_sha256,
    }
    observed_manifest = "sha256:" + "3" * 64
    held_out_oracle = "sha256:" + "4" * 64
    operator_control = "sha256:" + "5" * 64
    operator_binding = "sha256:" + "7" * 64
    deployment_topology = "sha256:" + "8" * 64
    deployment_credential = "sha256:" + "9" * 64
    lease.update(
        {
            "campaign_authority_schema": CAMPAIGN_LEASE_SCHEMA_VERSION,
            "campaign_id": MISSION_ID,
            "mission_id": MISSION_ID,
            "goal_id": "goal-one",
            "portfolio_contract_sha256": "sha256:" + "a" * 64,
            "goal_contract_sha256": "sha256:" + "b" * 64,
            "manifest_digest": "sha256:" + "c" * 64,
            "observed_input_manifest_digest": observed_manifest,
            "held_out_oracle_manifest_digest": held_out_oracle,
            "operator_control_semantics_sha256": operator_control,
            "operator_control_authority_binding_sha256": operator_binding,
            "deployment_authority_topology_sha256": deployment_topology,
            "deployment_authority_credential_clarification_sha256": (
                deployment_credential
            ),
            "observed_input_ref": observed_ref,
            "agent_roster_sha256": "d" * 64,
            "effect_mode": "read_only",
            "campaign_end": lease["expires_at"],
            "agent_name": "campaign-agent",
            "workspace_path": "workspaces/campaign-goal-one",
            "attempt_generation": 0,
            "max_attempts": 1,
        }
    )
    lease["content_hash"] = content_hash(lease)
    lease_root = tmp_path / "leases"
    write_execution_lease(lease, lease_root)
    stored = await board.get(task.task_id)
    assert stored is not None
    governance = {
        "schema_version": "dharma.sadhana.campaign_governance.v4",
        "campaign_id": MISSION_ID,
        "mission_id": MISSION_ID,
        "goal_id": "goal-one",
        "portfolio_contract_sha256": lease["portfolio_contract_sha256"],
        "goal_contract_sha256": lease["goal_contract_sha256"],
        "manifest_digest": lease["manifest_digest"],
        "observed_input_manifest_digest": observed_manifest,
        "held_out_oracle_manifest_digest": held_out_oracle,
        "operator_control_semantics_sha256": operator_control,
        "operator_control_authority_binding_sha256": operator_binding,
        "deployment_authority_topology_sha256": deployment_topology,
        "deployment_authority_credential_clarification_sha256": (deployment_credential),
        "observed_input_ref": observed_ref,
        "agent_roster_sha256": lease["agent_roster_sha256"],
        "effect_mode": "read_only",
        "campaign_end": lease["campaign_end"],
        "workspace_path": lease["workspace_path"],
        "allowed_files": lease["allowed_paths"],
        "forbidden_files": [],
        "max_usd": 0.0,
        "attempt_generation": 0,
        "max_attempts": 1,
    }
    authority = {
        "schema_version": "dharma.sadhana.campaign_task_authority.v5",
        "campaign_id": MISSION_ID,
        "mission_id": MISSION_ID,
        "goal_id": "goal-one",
        "portfolio_contract_sha256": lease["portfolio_contract_sha256"],
        "goal_contract_sha256": lease["goal_contract_sha256"],
        "manifest_digest": lease["manifest_digest"],
        "observed_input_manifest_digest": observed_manifest,
        "held_out_oracle_manifest_digest": held_out_oracle,
        "operator_control_semantics_sha256": operator_control,
        "operator_control_authority_binding_sha256": operator_binding,
        "deployment_authority_topology_sha256": deployment_topology,
        "deployment_authority_credential_clarification_sha256": (deployment_credential),
        "observed_input_ref": observed_ref,
        "agent_roster_sha256": lease["agent_roster_sha256"],
        "effect_mode": "read_only",
        "campaign_end": lease["campaign_end"],
        "agent_name": lease["agent_name"],
        "claimed_principal": request.claimed_principal,
        "dispatch_key": request.dispatch_key,
        "request_id": request.request_id,
        "workspace_path": lease["workspace_path"],
        "allowed_files": lease["allowed_paths"],
        "max_usd": 0.0,
        "authority_ref": lease["lease_id"],
        "authority_digest": lease["content_hash"],
        "attempt_generation": 0,
        "max_attempts": 1,
        "route_lock": {
            "schema_version": "dharma.sadhana.campaign_route_lock.v1",
            "task_id": task.task_id,
            "principal_id": request.claimed_principal,
            "provider": "ollama",
            "model": "fixture-model:cloud",
            "allow_provider_routing": False,
        },
    }
    await board.update_task(
        task.task_id,
        metadata={
            **stored.metadata,
            "sadhana_bootstrap_schema": "dharma.sadhana.mission_bootstrap.v1",
            "goal_contract_schema": "dharma.sadhana.goal_contracts.v1",
            "campaign_id": MISSION_ID,
            "goal_id": "goal-one",
            "portfolio_contract_sha256": lease["portfolio_contract_sha256"],
            "goal_contract_sha256": lease["goal_contract_sha256"],
            "cash_ceiling_usd": 0.0,
            "attempt_ceiling": 1,
            "attempt_generation": 0,
            "dispatch_ready": False,
            "dispatch_blocker": "authority_unbound",
            "campaign_effect_mode": "read_only",
            "requires_tooling": False,
            "allow_provider_routing": False,
            "provider_allowlist": ["ollama"],
            "preferred_provider": "ollama",
            "preferred_model": "fixture-model:cloud",
            "mission_task_id": task.task_id,
            "mission_observed_input": {
                "schema_version": "dharma.sadhana.observed_input_prompt.v1",
                "campaign_id": MISSION_ID,
                "mission_id": MISSION_ID,
                "goal_id": "goal-one",
                "task_id": task.task_id,
                "manifest_digest": observed_manifest,
                "goal_contract_sha256": lease["goal_contract_sha256"],
                "task_creation_hash": stored.metadata["mission_task_creation_hash"],
                "observed_at": "2026-08-23T00:00:00+00:00",
                "epistemic_state": "observed_unverified",
                "authority_scope": "prompt_context_only",
                "media_type": "text/markdown; charset=utf-8",
                "content": observed_content,
                "content_sha256": observed_content_sha256,
                "observed_input_ref": observed_ref,
            },
            GOVERNANCE_METADATA_KEY: governance,
            "mission_campaign_authority": authority,
        },
    )
    effect = _EffectExecutor(task.task_id)
    revoking_board = _RevokingBoard(board, lease_root, str(lease["lease_id"]))
    dispatcher = GovernedMissionDispatcher(
        control,
        revoking_board,  # type: ignore[arg-type]
        effect,
        authority_verifier=FileExecutionLeaseAuthorityVerifier(
            lease_root,
            revoking_board,  # type: ignore[arg-type]
        ),
    )
    governed = await dispatcher.canonical_governed_request(request)
    admission = await dispatcher.admit(request, governed)
    envelope = DispatchAuthorityEnvelope(
        claimed_principal=request.claimed_principal,
        mission_id=request.mission_id,
        task_id=request.task_id,
        dispatch_key=request.dispatch_key,
        authority_ref=str(lease["lease_id"]),
        authority_digest=str(lease["content_hash"]),
        attempt_generation=0,
    )

    with pytest.raises(MissionControlError, match="revoked"):
        await dispatcher.dispatch(request, governed, admission, envelope)
    assert effect.calls == 0


def test_sadhana_runtime_requires_exact_read_only_empty_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = SimpleNamespace(mission_id="sadhana-10-20260823", fast_boot=False)
    monkeypatch.delenv("DHARMA_READ_ONLY_BOOT", raising=False)
    monkeypatch.delenv("DHARMA_FAST_BOOT", raising=False)
    with pytest.raises(MissionControlError, match="read-only empty boot"):
        campaign_runtime._require_read_only_empty_boot(args)

    monkeypatch.setenv("DHARMA_READ_ONLY_BOOT", "1")
    campaign_runtime._require_read_only_empty_boot(args)
    monkeypatch.setenv("DHARMA_FAST_BOOT", "1")
    with pytest.raises(MissionControlError, match="read-only empty boot"):
        campaign_runtime._require_read_only_empty_boot(args)
    monkeypatch.delenv("DHARMA_FAST_BOOT")
    args.fast_boot = True
    with pytest.raises(MissionControlError, match="read-only empty boot"):
        campaign_runtime._require_read_only_empty_boot(args)


def test_sadhana_runtime_requires_complete_activation_credential_set() -> None:
    fields = {
        "release_sha": "a" * 40,
        "dispatch_activation_receipt": "/run/credentials/unit/dispatch",
        "dashboard_identity_receipt": "/run/credentials/unit/dashboard",
        "runtime_binding_receipt": "/run/credentials/unit/binding",
        "operator_login_file": "/run/credentials/unit/login",
        "control_hmac_key_file": "/run/credentials/unit/hmac",
        "activation_evidence_path": (
            "/run/dharma-sadhana/control/activation/campaign-activation.v1.json"
        ),
    }
    args = SimpleNamespace(mission_id="sadhana-10-20260823", **fields)
    admitted = campaign_runtime._dispatch_activation_paths(args)
    assert admitted["release_sha"] == "a" * 40
    assert admitted["activation_evidence_path"] == Path(
        fields["activation_evidence_path"]
    )

    args.control_hmac_key_file = ""
    with pytest.raises(MissionControlError, match="configuration is partial"):
        campaign_runtime._dispatch_activation_paths(args)


@pytest.mark.asyncio
async def test_sadhana_final_roster_recheck_is_exactly_seven() -> None:
    seats = tuple(
        SimpleNamespace(
            name=f"seat-{index}",
            role=AgentRole.GENERAL,
            provider=ProviderType.OLLAMA,
            model=f"model-{index}:cloud",
        )
        for index in range(7)
    )
    roster = SimpleNamespace(seats=seats)

    class Swarm:
        states = [
            SimpleNamespace(
                name=seat.name,
                role=seat.role,
                provider=seat.provider.value,
                model=seat.model,
            )
            for seat in seats
        ]

        async def list_agents(self) -> list[Any]:
            return list(self.states)

    swarm = Swarm()
    await campaign_runtime._require_exact_final_roster(swarm, roster)
    swarm.states.append(
        SimpleNamespace(
            name="foreign",
            role=AgentRole.GENERAL,
            provider=ProviderType.OLLAMA.value,
            model="foreign:cloud",
        )
    )
    with pytest.raises(CampaignRosterError, match="seven seats"):
        await campaign_runtime._require_exact_final_roster(swarm, roster)


def test_campaign_activation_is_inside_writer_roster_authority_boundary() -> None:
    source = inspect.getsource(campaign_runtime.run_campaign)
    ordered = (
        "_acquire_writer_handoff",
        "await swarm.init()",
        "await swarm.list_agents() or await swarm.list_tasks()",
        "ensure_campaign_agent_roster",
        "bind_campaign_authority",
        "_require_exact_final_roster",
        "activate_campaign_session",
        "service.run",
    )
    positions = [source.index(fragment) for fragment in ordered]
    assert positions == sorted(positions)
    assert "start_campaign=False" in source
    assert "observed_node=" not in source
