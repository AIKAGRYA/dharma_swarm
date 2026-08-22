from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

import pytest

from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_contract import (
    MissionControlError,
    stable_id,
    utc_now,
)
from dharma_swarm.mission_control_dispatch import (
    GOVERNANCE_METADATA_KEY,
    LEASE_DISPATCH_ACTION,
    LEASE_WORKSPACE_ACTION,
    DispatchAuthorityEnvelope,
    GovernanceAdmission,
    GovernedMissionDispatcher,
    MissionDispatchRequest,
    VerifiedDispatchAuthority,
)
from dharma_swarm.mission_control_execution import OwnerExecutionRef
from dharma_swarm.models import TaskStatus
from dharma_swarm.operator_core.execution_lease import (
    build_execution_lease,
    content_hash,
)
from dharma_swarm.operator_core.governed_work_admission import (
    GovernedWorkAdmission,
    GovernedWorkRequest,
    WorkKind,
    evaluate_governed_work_admission,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard


MISSION_ID = "mission-governed"
PRINCIPAL = "fixture-principal"
DISPATCH_KEY = "primary"
WORKSPACE_PATH = "bounded/workspace"


class _MissionBoundary:
    def __init__(self, control: MissionControl) -> None:
        self.control = control
        self.lifecycle_calls = 0

    async def get_mission(self, mission_id: str):
        return await self.control.get_mission(mission_id)

    async def start_attempt(self, *args: Any, **kwargs: Any) -> None:
        self.lifecycle_calls += 1
        raise AssertionError("dispatch membrane must not own attempt lifecycle")

    async def heartbeat_lease(self, *args: Any, **kwargs: Any) -> None:
        self.lifecycle_calls += 1
        raise AssertionError("dispatch membrane must not own lease lifecycle")

    async def finish_attempt(self, *args: Any, **kwargs: Any) -> None:
        self.lifecycle_calls += 1
        raise AssertionError("dispatch membrane must not own attempt lifecycle")


class _Verifier:
    def __init__(
        self,
        result: Any,
        *,
        hook: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.result = result
        self.hook = hook
        self.calls = 0
        self.envelopes: list[DispatchAuthorityEnvelope] = []
        self.admissions: list[GovernanceAdmission] = []

    async def verify(
        self,
        envelope: DispatchAuthorityEnvelope,
        *,
        request: MissionDispatchRequest,
        admission: GovernanceAdmission,
    ) -> Any:
        self.calls += 1
        self.envelopes.append(envelope)
        self.admissions.append(admission)
        assert request.claimed_principal == admission.principal
        if self.hook is not None:
            await self.hook()
        return self.result


class _Executor:
    def __init__(self, ref: Any) -> None:
        self.ref = ref
        self.calls = 0
        self.arguments: list[tuple[str, str, str]] = []

    async def dispatch(
        self,
        mission_id: str,
        task_id: str,
        *,
        dispatch_key: str = "default",
    ) -> Any:
        self.calls += 1
        self.arguments.append((mission_id, task_id, dispatch_key))
        return self.ref


class _Evaluator:
    def __init__(self, decision: str = "allow") -> None:
        self.decision = decision
        self.calls = 0

    def __call__(self, request: GovernedWorkRequest) -> GovernedWorkAdmission:
        self.calls += 1
        return GovernedWorkAdmission(
            request_id=request.request_id,
            decision=self.decision,
            reasons=[f"fixture_{self.decision}"],
            required_receipts=[],
            reduced_authority={
                "work_kind": request.work_kind.value,
                "risk_tier": request.risk_tier,
            },
        )


@dataclass
class _Case:
    board: TaskBoard
    boundary: _MissionBoundary
    request: MissionDispatchRequest
    governed: GovernedWorkRequest
    lease: dict[str, Any]
    authority: DispatchAuthorityEnvelope
    verified: VerifiedDispatchAuthority
    verifier: _Verifier
    executor: _Executor
    dispatcher: GovernedMissionDispatcher
    admission: GovernanceAdmission


def _owner_ref(task_id: str) -> OwnerExecutionRef:
    return OwnerExecutionRef(
        backend="fixture-owner",
        mission_id=MISSION_ID,
        task_id=task_id,
        dispatch_key=DISPATCH_KEY,
        run_id=stable_id("fixture_run", MISSION_ID, task_id, DISPATCH_KEY),
        claim_id=stable_id("fixture_claim", MISSION_ID, task_id, DISPATCH_KEY),
        agent_id="fixture-agent",
        idempotency_key=stable_id(
            "fixture_dispatch", MISSION_ID, task_id, DISPATCH_KEY
        ),
        owner_session_id="fixture-owner-session",
    )


def _lease(request: MissionDispatchRequest, **overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "issued_to": request.claimed_principal,
        "task_id": request.task_id,
        "correlation_id": request.request_id,
        "allowed_actions": [LEASE_DISPATCH_ACTION, LEASE_WORKSPACE_ACTION],
        "allowed_paths": [WORKSPACE_PATH],
        "lease_id": "lease-governed-primary",
        "max_seconds": 900,
    }
    values.update(overrides)
    return build_execution_lease(**values)


def _authority_pair(
    request: MissionDispatchRequest,
    lease: dict[str, Any],
    *,
    authority_ref: str | None = None,
    revoked_lease_ids: tuple[str, ...] = (),
) -> tuple[DispatchAuthorityEnvelope, VerifiedDispatchAuthority]:
    ref = authority_ref or str(lease["lease_id"])
    digest = str(lease["content_hash"])
    envelope = DispatchAuthorityEnvelope(
        claimed_principal=request.claimed_principal,
        mission_id=request.mission_id,
        task_id=request.task_id,
        dispatch_key=request.dispatch_key,
        authority_ref=ref,
        authority_digest=digest,
    )
    verified = VerifiedDispatchAuthority(
        authenticated_principal=request.claimed_principal,
        mission_id=request.mission_id,
        task_id=request.task_id,
        dispatch_key=request.dispatch_key,
        authority_ref=ref,
        authority_digest=digest,
        execution_lease=lease,
        revoked_lease_ids=revoked_lease_ids,
    )
    return envelope, verified


async def _case(
    tmp_path: Path,
    *,
    title: str = "Read fixture status",
    description: str = "Inspect the local fixture and return a summary.",
    metadata: dict[str, Any] | None = None,
    evaluator: Callable[[GovernedWorkRequest], GovernedWorkAdmission] | None = None,
) -> _Case:
    tmp_path.mkdir(parents=True, exist_ok=True)
    board = TaskBoard(tmp_path / "tasks.db")
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    await board.init_db()
    await runtime.init_db()
    control = MissionControl(board, runtime)
    await control.create_mission(MISSION_ID, title="Governed mission")
    task_metadata = {
        GOVERNANCE_METADATA_KEY: {"allowed_files": [WORKSPACE_PATH]},
        **dict(metadata or {}),
    }
    task = await control.create_task(
        MISSION_ID,
        title=title,
        description=description,
        idempotency_key="governed-task",
        metadata=task_metadata,
    )
    request = MissionDispatchRequest.new(
        MISSION_ID,
        task.task_id,
        dispatch_key=DISPATCH_KEY,
        claimed_principal=PRINCIPAL,
    )
    lease = _lease(request)
    authority, verified = _authority_pair(request, lease)
    verifier = _Verifier(verified)
    executor = _Executor(_owner_ref(task.task_id))
    boundary = _MissionBoundary(control)
    kwargs = {"admission_evaluator": evaluator} if evaluator is not None else {}
    dispatcher = GovernedMissionDispatcher(
        boundary, board, executor, authority_verifier=verifier,  # type: ignore[arg-type]
        **kwargs,
    )
    governed = await dispatcher.canonical_governed_request(request)
    admission = await dispatcher.admit(request, governed)
    return _Case(
        board,
        boundary,
        request,
        governed,
        lease,
        authority,
        verified,
        verifier,
        executor,
        dispatcher,
        admission,
    )


@pytest.mark.asyncio
async def test_stable_request_authorize_then_dispatch_preserves_claim_boundaries(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)

    assert case.request.request_id == stable_id(
        "mission_dispatch", MISSION_ID, case.request.task_id, DISPATCH_KEY
    )
    assert case.governed.work_kind is WorkKind.LONG_RUNNING
    assert case.admission.decision == "review"
    assert case.verifier.calls == 0
    assert case.executor.calls == 0

    verified = await case.dispatcher.authorize(
        case.request,
        case.governed,
        case.admission,
        case.authority,
    )
    assert verified == case.verified
    assert case.verifier.calls == 1
    assert case.executor.calls == 0

    dispatched = await case.dispatcher.dispatch(
        case.request,
        case.governed,
        case.admission,
        case.authority,
    )
    assert dispatched.execution == case.executor.ref
    assert dispatched.proves_delivery is False
    assert dispatched.proves_executor_liveness is False
    assert dispatched.proves_semantic_outcome is False
    assert dispatched.admission.decision == "allow"
    assert dispatched.admission.request_digest != case.admission.request_digest
    assert dispatched.admission is not case.admission
    assert dispatched.admission.reduced_authority is not case.admission.reduced_authority
    assert case.verifier.calls == 2
    assert case.executor.calls == 1
    assert case.boundary.lifecycle_calls == 0


@pytest.mark.asyncio
async def test_non_read_work_requires_then_uses_exact_authenticated_workspace(
    tmp_path: Path,
) -> None:
    requests: list[GovernedWorkRequest] = []

    def recording_policy(request: GovernedWorkRequest) -> GovernedWorkAdmission:
        requests.append(request.model_copy(deep=True))
        return evaluate_governed_work_admission(request)

    case = await _case(
        tmp_path,
        title="Handle the bounded local fixture",
        description="Perform the bounded operation once.",
        evaluator=recording_policy,
    )
    assert case.governed.work_kind is WorkKind.LONG_RUNNING
    assert case.admission.decision == "review"
    dispatched = await case.dispatcher.dispatch(
        case.request, case.governed, case.admission, case.authority
    )
    assert dispatched.admission.decision == "allow"
    assert [request.workspace_lease_present for request in requests] == [
        False,
        False,
        True,
        True,
    ]
    workspace = requests[-1].metadata["authenticated_workspace"]
    assert workspace["authority_ref"] == case.verified.authority_ref
    assert workspace["authority_digest"] == case.verified.authority_digest
    assert workspace["allowed_paths"] == [WORKSPACE_PATH]
    assert case.verifier.calls == 1
    assert case.executor.calls == 1


@pytest.mark.asyncio
async def test_authority_digest_mismatch_blocks_before_owner_dispatch(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    case.verifier.result = replace(
        case.verified,
        authority_digest="sha256:" + "0" * 64,
    )

    with pytest.raises(MissionControlError, match="verified dispatch authority"):
        await case.dispatcher.dispatch(
            case.request,
            case.governed,
            case.admission,
            case.authority,
        )

    assert case.verifier.calls == 1
    assert case.executor.calls == 0


@pytest.mark.asyncio
async def test_canonical_semantics_block_low_risk_a2a_label_smuggling(
    tmp_path: Path,
) -> None:
    evaluator = _Evaluator()
    contract = {
        "work_kind": WorkKind.A2A_CLAIM.value,
        "workspace_lease_ref": "unrelated-workspace-lease",
        "allowed_files": ["dharma_swarm/mission_control_dispatch.py"],
        "forbidden_files": ["docs/restricted"],
    }
    case = await _case(tmp_path, evaluator=evaluator)
    task = await case.board.get(case.request.task_id)
    assert task is not None
    await case.board.update_task(
        case.request.task_id,
        title="Write a bounded code patch",
        description="Update source implementation and tests in the allowed file.",
        metadata={**task.metadata, GOVERNANCE_METADATA_KEY: contract},
    )
    governed = await case.dispatcher.canonical_governed_request(case.request)

    assert governed.work_kind is WorkKind.CODE_WRITE
    assert governed.risk_tier == "Q2"
    assert governed.mission_contract_present is True
    assert governed.workspace_lease_present is False
    assert governed.allowed_files == contract["allowed_files"]
    assert governed.forbidden_files == contract["forbidden_files"]
    assert "Write a bounded code patch" in governed.intent
    preliminary = await case.dispatcher.admit(case.request, governed)
    assert preliminary.decision == "allow"
    with pytest.raises(MissionControlError, match="workspace scope conflicts"):
        await case.dispatcher.dispatch(
            case.request, governed, preliminary, case.authority
        )

    smuggled = governed.model_copy(
        update={
            "work_kind": WorkKind.A2A_CLAIM,
            "intent": "Inspect a harmless A2A claim.",
            "risk_tier": "Q1",
            "mission_contract_present": False,
            "workspace_lease_present": False,
            "allowed_files": [],
            "forbidden_files": [],
        }
    )
    with pytest.raises(MissionControlError, match="does not bind"):
        await case.dispatcher.admit(case.request, smuggled)
    assert evaluator.calls == 3
    assert case.verifier.calls == 1
    assert case.executor.calls == 0


@pytest.mark.asyncio
async def test_unknown_paraphrased_write_intent_requires_workspace_evidence(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    await case.board.update_task(
        case.request.task_id,
        title="Alter the local implementation and add tests",
        description="",
    )
    governed = await case.dispatcher.canonical_governed_request(case.request)
    assert governed.work_kind is WorkKind.LONG_RUNNING
    assert governed.workspace_lease_present is False
    preliminary = await case.dispatcher.admit(case.request, governed)
    assert preliminary.decision == "review"
    lease = _lease(case.request, allowed_actions=[LEASE_DISPATCH_ACTION])
    authority, verified = _authority_pair(case.request, lease)
    case.verifier.result = verified
    with pytest.raises(MissionControlError, match="does not grant workspace"):
        await case.dispatcher.dispatch(
            case.request, governed, preliminary, authority
        )
    assert case.verifier.calls == 1
    assert case.executor.calls == 0


@pytest.mark.asyncio
async def test_unrelated_task_metadata_workspace_ref_is_not_evidence(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    task = await case.board.get(case.request.task_id)
    assert task is not None
    await case.board.update_task(
        case.request.task_id,
        title="Run the bounded fixture",
        metadata={
            **task.metadata,
            GOVERNANCE_METADATA_KEY: {
                "workspace_lease_ref": "lease-unrelated-to-dispatch-authority",
                "allowed_files": ["bounded/workspace/path"],
            },
        },
    )
    governed = await case.dispatcher.canonical_governed_request(case.request)
    assert governed.work_kind is WorkKind.LONG_RUNNING
    assert governed.workspace_lease_present is False
    assert "authenticated_workspace" not in governed.metadata
    preliminary = await case.dispatcher.admit(case.request, governed)
    lease = _lease(case.request, allowed_paths=["different/workspace/path"])
    authority, verified = _authority_pair(case.request, lease)
    case.verifier.result = verified
    with pytest.raises(MissionControlError, match="workspace scope conflicts"):
        await case.dispatcher.dispatch(
            case.request, governed, preliminary, authority
        )
    assert case.verifier.calls == 1
    assert case.executor.calls == 0


@pytest.mark.asyncio
async def test_safe_prefix_cannot_lower_mixed_write_intent_to_read_only(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    await case.board.update_task(
        case.request.task_id,
        title="Read status, then alter the local implementation and add tests",
    )
    governed = await case.dispatcher.canonical_governed_request(case.request)
    assert governed.work_kind is WorkKind.LONG_RUNNING
    preliminary = await case.dispatcher.admit(case.request, governed)
    assert preliminary.decision == "review"
    assert case.verifier.calls == 0
    assert case.executor.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "path"),
    [
        ("allowed_files", "bounded/workspace/../private/data.txt"),
        ("allowed_files", "/bounded/private/data.txt"),
        ("allowed_files", "~/private/data.txt"),
        ("allowed_files", r"bounded\private\data.txt"),
        ("allowed_files", "bounded//private/data.txt"),
        ("allowed_files", "docs/?/a"),
        ("allowed_files", "docs/[x]/a"),
        ("forbidden_files", "docs/{x,y}/a"),
        ("forbidden_files", "bounded/private/../archive/**"),
    ],
)
async def test_canonical_workspace_scope_rejects_noncanonical_paths_before_digest(
    tmp_path: Path,
    field: str,
    path: str,
) -> None:
    case = await _case(tmp_path)
    task = await case.board.get(case.request.task_id)
    assert task is not None
    contract = {
        "allowed_files": [WORKSPACE_PATH],
        "forbidden_files": ["bounded/private/**"],
    }
    contract[field] = [path]
    await case.board.update_task(
        case.request.task_id,
        metadata={**task.metadata, GOVERNANCE_METADATA_KEY: contract},
    )

    with pytest.raises(MissionControlError, match="noncanonical relative path"):
        await case.dispatcher.canonical_governed_request(case.request)
    assert case.verifier.calls == 0
    assert case.executor.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "bounded/workspace/../private/data.txt",
        "/bounded/private/data.txt",
        "~/private/data.txt",
        r"bounded\private\data.txt",
        "docs/*/a",
        "docs/?/a",
        "docs/[x]/a",
        "docs/{x,y}/a",
        "docs/!(x)/a",
    ],
)
async def test_authenticated_workspace_scope_rejects_noncanonical_paths(
    tmp_path: Path,
    path: str,
) -> None:
    case = await _case(tmp_path)
    lease = dict(case.lease)
    lease["allowed_paths"] = [path]
    lease["content_hash"] = content_hash(lease)
    authority, verified = _authority_pair(case.request, lease)
    case.verifier.result = verified

    with pytest.raises(MissionControlError, match="noncanonical relative path"):
        await case.dispatcher.dispatch(
            case.request, case.governed, case.admission, authority
        )
    assert case.verifier.calls == 1
    assert case.executor.calls == 0


@pytest.mark.asyncio
async def test_intersecting_workspace_globs_are_rejected_before_owner(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    task = await case.board.get(case.request.task_id)
    assert task is not None
    await case.board.update_task(
        case.request.task_id,
        metadata={
            **task.metadata,
            GOVERNANCE_METADATA_KEY: {
                "allowed_files": ["docs/*/a"],
                "forbidden_files": ["docs/x/*"],
            },
        },
    )

    with pytest.raises(MissionControlError, match="noncanonical relative path"):
        await case.dispatcher.canonical_governed_request(case.request)
    assert case.verifier.calls == 0
    assert case.executor.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("allowed", "blocked"),
    [
        ("docs/x/a", "docs/x/a"),
        ("docs/x/a", "docs/x"),
        ("docs/x", "docs/x/a"),
    ],
)
async def test_literal_workspace_prefix_overlap_blocks_owner(
    tmp_path: Path,
    allowed: str,
    blocked: str,
) -> None:
    case = await _case(tmp_path)
    task = await case.board.get(case.request.task_id)
    assert task is not None
    await case.board.update_task(
        case.request.task_id,
        metadata={
            **task.metadata,
            GOVERNANCE_METADATA_KEY: {
                "allowed_files": [allowed],
                "forbidden_files": [blocked],
            },
        },
    )
    governed = await case.dispatcher.canonical_governed_request(case.request)
    preliminary = await case.dispatcher.admit(case.request, governed)
    lease = _lease(case.request, allowed_paths=[allowed])
    authority, verified = _authority_pair(case.request, lease)
    case.verifier.result = verified

    with pytest.raises(MissionControlError, match="includes a forbidden file"):
        await case.dispatcher.dispatch(
            case.request, governed, preliminary, authority
        )
    assert case.verifier.calls == 1
    assert case.executor.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("allowed", "blocked"),
    [
        pytest.param("DOCS/X", "docs/x", id="case-only"),
        pytest.param(
            "docs/caf\u00e9/file",
            "docs/cafe\u0301",
            id="unicode-nfc-versus-nfd",
        ),
    ],
)
async def test_forbidden_overlap_is_casefolded_and_unicode_normalized(
    tmp_path: Path,
    allowed: str,
    blocked: str,
) -> None:
    case = await _case(tmp_path)
    task = await case.board.get(case.request.task_id)
    assert task is not None
    await case.board.update_task(
        case.request.task_id,
        metadata={
            **task.metadata,
            GOVERNANCE_METADATA_KEY: {
                "allowed_files": [allowed],
                "forbidden_files": [blocked],
            },
        },
    )
    governed = await case.dispatcher.canonical_governed_request(case.request)
    preliminary = await case.dispatcher.admit(case.request, governed)
    lease = _lease(case.request, allowed_paths=[allowed])
    authority, verified = _authority_pair(case.request, lease)
    case.verifier.result = verified

    with pytest.raises(MissionControlError, match="includes a forbidden file"):
        await case.dispatcher.dispatch(
            case.request, governed, preliminary, authority
        )
    assert case.verifier.calls == 1
    assert case.executor.calls == 0


@pytest.mark.asyncio
async def test_literal_workspace_prefix_comparison_is_segment_aware(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    task = await case.board.get(case.request.task_id)
    assert task is not None
    allowed = "docs/xy/a"
    await case.board.update_task(
        case.request.task_id,
        metadata={
            **task.metadata,
            GOVERNANCE_METADATA_KEY: {
                "allowed_files": [allowed],
                "forbidden_files": ["docs/x"],
            },
        },
    )
    governed = await case.dispatcher.canonical_governed_request(case.request)
    preliminary = await case.dispatcher.admit(case.request, governed)
    lease = _lease(case.request, allowed_paths=[allowed])
    authority, verified = _authority_pair(case.request, lease)
    case.verifier.result = verified

    result = await case.dispatcher.dispatch(
        case.request, governed, preliminary, authority
    )
    assert result.execution == case.executor.ref
    assert case.verifier.calls == 1
    assert case.executor.calls == 1


@pytest.mark.asyncio
async def test_mutable_admission_changed_during_verifier_fails_closed(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)

    async def mutate_caller_admission() -> None:
        case.admission.reduced_authority["work_kind"] = WorkKind.PROMOTION.value

    case.verifier.hook = mutate_caller_admission
    with pytest.raises(MissionControlError, match="governance admission changed"):
        await case.dispatcher.dispatch(
            case.request, case.governed, case.admission, case.authority
        )
    assert case.verifier.admissions[0] is not case.admission
    assert case.verifier.admissions[0].reduced_authority is not case.admission.reduced_authority
    assert case.executor.calls == 0


@pytest.mark.asyncio
async def test_noncanonical_padded_active_revocation_id_fails_closed(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    case.verifier.result = replace(
        case.verified,
        revoked_lease_ids=(f" {case.lease['lease_id']} ",),
    )
    with pytest.raises(MissionControlError, match="revoked lease_id"):
        await case.dispatcher.dispatch(
            case.request, case.governed, case.admission, case.authority
        )
    assert case.verifier.calls == 1
    assert case.executor.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "variant",
    [
        "wrong_principal",
        "wrong_task",
        "wrong_correlation",
        "missing_action",
        "missing_workspace_action",
        "forbidden_action",
        "expired",
        "future_issued",
        "revoked",
        "lease_ref_mismatch",
        "lease_digest_mismatch",
    ],
)
async def test_strict_execution_lease_binding_blocks_before_dispatch(
    tmp_path: Path,
    variant: str,
) -> None:
    case = await _case(tmp_path)
    lease = dict(case.lease)
    revoked: tuple[str, ...] = ()
    authority_ref: str | None = None

    if variant == "wrong_principal":
        lease["issued_to"] = "foreign-principal"
    elif variant == "wrong_task":
        lease["task_id"] = "foreign-task"
    elif variant == "wrong_correlation":
        lease["correlation_id"] = "foreign-request"
    elif variant == "missing_action":
        lease["allowed_actions"] = ["read"]
    elif variant == "missing_workspace_action":
        lease["allowed_actions"] = [LEASE_DISPATCH_ACTION]
    elif variant == "forbidden_action":
        lease["forbidden_actions"] = [LEASE_DISPATCH_ACTION]
    elif variant == "expired":
        lease = _lease(
            case.request,
            issued_at=utc_now() - timedelta(minutes=10),
            expires_at=utc_now() - timedelta(minutes=5),
        )
    elif variant == "future_issued":
        lease = _lease(
            case.request,
            issued_at=utc_now() + timedelta(minutes=5),
            expires_at=utc_now() + timedelta(minutes=10),
        )
    elif variant == "revoked":
        revoked = (str(lease["lease_id"]),)
    elif variant == "lease_ref_mismatch":
        authority_ref = "lease-foreign-reference"
    elif variant == "lease_digest_mismatch":
        lease["content_hash"] = "sha256:" + "f" * 64

    if variant not in {"expired", "future_issued", "lease_digest_mismatch"}:
        lease["content_hash"] = content_hash(lease)
    authority, verified = _authority_pair(
        case.request,
        lease,
        authority_ref=authority_ref,
        revoked_lease_ids=revoked,
    )
    case.verifier.result = verified

    with pytest.raises(MissionControlError):
        await case.dispatcher.dispatch(
            case.request,
            case.governed,
            case.admission,
            authority,
        )
    assert case.executor.calls == 0


@pytest.mark.asyncio
async def test_self_hashed_lease_or_wrong_verifier_type_is_not_authority(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    case.verifier.result = case.lease

    with pytest.raises(MissionControlError, match="invalid evidence type"):
        await case.dispatcher.dispatch(
            case.request,
            case.governed,
            case.admission,
            case.authority,
        )
    assert case.executor.calls == 0

    case.verifier.result = True
    with pytest.raises(MissionControlError, match="invalid evidence type"):
        await case.dispatcher.dispatch(
            case.request,
            case.governed,
            case.admission,
            case.authority,
        )

    async def verifier_error() -> None:
        raise RuntimeError("owner verifier unavailable")

    case.verifier.hook = verifier_error
    with pytest.raises(MissionControlError, match="verification failed"):
        await case.dispatcher.dispatch(
            case.request,
            case.governed,
            case.admission,
            case.authority,
        )
    assert case.executor.calls == 0

    with pytest.raises(ValueError, match="authority_verifier"):
        GovernedMissionDispatcher(
            case.boundary,  # type: ignore[arg-type]
            case.board,
            case.executor,
            authority_verifier=None,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("description", "metadata"),
    [
        ("Summarize first, then git push the result.", None),
        (
            "Return a harmless summary.",
            {
                "mission_control_sarathi": {
                    "planned_instruction": "send email to an external contact"
                }
            },
        ),
    ],
)
async def test_full_canonical_payload_blocks_benign_summary_smuggling(
    tmp_path: Path,
    description: str,
    metadata: dict[str, Any] | None,
) -> None:
    evaluator = _Evaluator()
    with pytest.raises(MissionControlError, match="not eligible"):
        await _case(
            tmp_path,
            description=description,
            metadata=metadata,
            evaluator=evaluator,
        )
    assert evaluator.calls == 0


@pytest.mark.asyncio
async def test_evaluator_is_rerun_and_review_cannot_reuse_allow_admission(
    tmp_path: Path,
) -> None:
    evaluator = _Evaluator()
    case = await _case(tmp_path, evaluator=evaluator)
    assert evaluator.calls == 1
    evaluator.decision = "review"

    with pytest.raises(MissionControlError, match="preliminary governance admission"):
        await case.dispatcher.dispatch(
            case.request,
            case.governed,
            case.admission,
            case.authority,
        )
    assert evaluator.calls == 2
    assert case.verifier.calls == 0
    assert case.executor.calls == 0


@pytest.mark.asyncio
async def test_task_mutation_during_verification_fails_closed(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)

    async def mutate_task() -> None:
        await case.board.update_task(
            case.request.task_id,
            description="Changed after governance admission.",
        )

    case.verifier.hook = mutate_task
    with pytest.raises(MissionControlError, match="changed during authorization"):
        await case.dispatcher.dispatch(
            case.request,
            case.governed,
            case.admission,
            case.authority,
        )
    assert case.verifier.calls == 1
    assert case.executor.calls == 0


@pytest.mark.asyncio
async def test_authority_identity_mismatch_blocks_before_verifier(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    foreign = replace(case.authority, task_id="foreign-task")

    with pytest.raises(MissionControlError, match="authority envelope"):
        await case.dispatcher.dispatch(
            case.request,
            case.governed,
            case.admission,
            foreign,
        )
    assert case.verifier.calls == 0
    assert case.executor.calls == 0


@pytest.mark.asyncio
async def test_changed_task_or_governed_request_invalidates_admission(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    await case.board.update_task(
        case.request.task_id,
        description="Inspect a different bounded fixture.",
    )
    with pytest.raises(MissionControlError, match="does not bind"):
        await case.dispatcher.dispatch(
            case.request,
            case.governed,
            case.admission,
            case.authority,
        )
    assert case.verifier.calls == 0
    assert case.executor.calls == 0

    second = await _case(tmp_path / "second")
    second.governed.intent = "changed after admission"
    with pytest.raises(MissionControlError, match="does not bind"):
        await second.dispatcher.dispatch(
            second.request,
            second.governed,
            second.admission,
            second.authority,
        )
    assert second.verifier.calls == 0
    assert second.executor.calls == 0


@pytest.mark.asyncio
async def test_owner_retry_repeats_all_gates_without_membrane_cache(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    first = await case.dispatcher.dispatch(
        case.request,
        case.governed,
        case.admission,
        case.authority,
    )
    second = await case.dispatcher.dispatch(
        case.request,
        case.governed,
        case.admission,
        case.authority,
    )

    assert second.execution == first.execution
    assert case.verifier.calls == 2
    assert case.executor.calls == 2
    assert case.executor.arguments == [
        (MISSION_ID, case.request.task_id, DISPATCH_KEY),
        (MISSION_ID, case.request.task_id, DISPATCH_KEY),
    ]


@pytest.mark.asyncio
async def test_owner_runtime_stamp_does_not_change_retry_operation_binding(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    first = await case.dispatcher.dispatch(
        case.request, case.governed, case.admission, case.authority
    )
    task = await case.board.get(case.request.task_id)
    assert task is not None
    owner_stamp = {
        "schema_version": "dharma.mission_control.owner_execution.v1",
        "backend": "orchestrator",
        "mission_id": MISSION_ID,
        "task_id": case.request.task_id,
        "dispatch_key": DISPATCH_KEY,
        "run_id": first.execution.run_id,
    }
    await case.board.update_task(
        case.request.task_id,
        status=TaskStatus.ASSIGNED,
        assigned_to="fixture-agent",
        metadata={
            **task.metadata,
            "mission_control_owner_execution": owner_stamp,
            "runtime_run_id": first.execution.run_id,
        },
    )
    await case.board.update_task(
        case.request.task_id,
        status=TaskStatus.RUNNING,
        metadata=(await case.board.get(case.request.task_id)).metadata,
    )
    await case.board.update_task(case.request.task_id, result="mutable owner projection")

    second = await case.dispatcher.dispatch(
        case.request, case.governed, case.admission, case.authority
    )
    assert second.execution == first.execution
    assert case.verifier.calls == 2
    assert case.executor.calls == 2


@pytest.mark.asyncio
async def test_foreign_owner_reference_is_rejected_after_one_owner_call(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    case.executor.ref = replace(case.executor.ref, mission_id="foreign-mission")

    with pytest.raises(MissionControlError, match="foreign reference"):
        await case.dispatcher.dispatch(
            case.request,
            case.governed,
            case.admission,
            case.authority,
        )
    assert case.executor.calls == 1


@pytest.mark.asyncio
async def test_request_and_governed_identity_are_exactly_bound(tmp_path: Path) -> None:
    case = await _case(tmp_path)
    forged_request = replace(case.request, request_id="request-forged")
    with pytest.raises(MissionControlError, match="stable dispatch identity"):
        await case.dispatcher.admit(forged_request, case.governed)

    foreign_principal = case.governed.model_copy(
        update={"agent_uid": "foreign-principal"}
    )
    with pytest.raises(MissionControlError, match="does not bind"):
        await case.dispatcher.admit(case.request, foreign_principal)
    assert case.verifier.calls == 0
    assert case.executor.calls == 0
