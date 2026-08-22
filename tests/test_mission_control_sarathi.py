from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from dharma_swarm.holon_system.sarathi.plan import (
    PlannedDelegation,
    plan_dedup_key,
)
from dharma_swarm.mission_control import MissionControl, MissionControlError
from dharma_swarm.mission_control_contract import stable_id
from dharma_swarm.mission_control_dispatch import GovernanceAdmission
from dharma_swarm.mission_control_sarathi import (
    SARATHI_METADATA_KEY,
    SARATHI_SCHEMA_VERSION,
    AcceptedMissionTask,
    MissionProposal,
    SarathiMissionAdapter,
    SarathiMissionError,
)
from dharma_swarm.models import TaskStatus
from dharma_swarm.operator_core.governed_work_admission import (
    GovernedWorkAdmission,
    GovernedWorkRequest,
    WorkKind,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard


@pytest.fixture
async def mission_control(tmp_path: Path) -> MissionControl:
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    board = TaskBoard(tmp_path / "tasks.db")
    await runtime.init_db()
    await board.init_db()
    return MissionControl(board, runtime)


def _delegation(
    *,
    action: str = "check status of proof fixtures",
    recipient: str = "worker-a",
    channel: str = "mailbox",
    summary: str = "Inspect proof fixtures",
    body: str = "Read and report fixture status",
    depends_on: tuple[str, ...] = (),
    metadata: Any = None,
) -> PlannedDelegation:
    return PlannedDelegation(
        action=action,
        recipient=recipient,
        channel=channel,
        summary=summary,
        body=body,
        depends_on=depends_on,
        metadata={"sarathi_kind": "review"} if metadata is None else metadata,
    )


def _request(
    proposal: MissionProposal,
    **changes: Any,
) -> GovernedWorkRequest:
    values: dict[str, Any] = {
        "request_id": proposal.admission_request_id,
        "agent_uid": proposal.recipient,
        "work_kind": proposal.work_kind,
        "intent": proposal.gate_input,
        "risk_tier": proposal.risk_tier,
        "context_quorum_ok": False,
        "mission_contract_present": False,
        "workspace_lease_present": False,
        "metadata": {
            "schema_version": SARATHI_SCHEMA_VERSION,
            "mission_id": proposal.mission_id,
            "proposal_id": proposal.proposal_id,
            "proposal_digest": proposal.proposal_digest,
            "plan_key": proposal.plan_key,
            "channel": proposal.channel,
            "recipient": proposal.recipient,
        },
    }
    values.update(changes)
    return GovernedWorkRequest(**values)


async def _ready(
    control: MissionControl,
    delegation: PlannedDelegation | None = None,
    *,
    mission_id: str = "m-alpha",
) -> tuple[SarathiMissionAdapter, MissionProposal, GovernedWorkRequest, GovernanceAdmission]:
    if await control.get_mission(mission_id) is None:
        await control.create_mission(mission_id, title="Alpha")
    adapter = SarathiMissionAdapter(control)
    proposal = adapter.propose(mission_id, delegation or _delegation())
    request = _request(proposal)
    return adapter, proposal, request, adapter.admit(proposal, request)


def test_proposal_identity_is_deterministic_mission_scoped_and_write_free() -> None:
    class NoOwnerCalls:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"owner call during propose: {name}")

    delegation = _delegation(depends_on=("spec",))
    adapter = SarathiMissionAdapter(NoOwnerCalls())  # type: ignore[arg-type]
    first = adapter.propose("mission-a", delegation)
    second = adapter.propose("mission-a", delegation)
    other_mission = adapter.propose("mission-b", delegation)

    assert first == second
    assert first.plan_key == plan_dedup_key(delegation)
    assert first.proposal_id == stable_id(
        "sarathi_proposal", "mission-a", first.plan_key
    )
    assert other_mission.plan_key == first.plan_key
    assert other_mission.proposal_id != first.proposal_id
    assert first.proposal_only is True
    assert first.confers_dispatch_authority is False
    assert first.proves_executor_liveness is False


@pytest.mark.parametrize(
    ("delegation", "message"),
    [
        (_delegation(channel="unknown"), "invalid Sarathi channel"),
        (_delegation(summary="   "), "summary is required"),
        (_delegation(depends_on=("spec", "spec")), "must be unique"),
        (_delegation(depends_on=(" spec ",)), "surrounding whitespace"),
        (_delegation(metadata={1: "value"}), "keys must be strings"),
        (_delegation(metadata={"nested": {1: "value"}}), "keys must be strings"),
        (_delegation(metadata={"not_json": object()}), "JSON-serializable"),
        (_delegation(metadata={"not_finite": float("nan")}), "JSON-serializable"),
    ],
)
def test_proposal_rejects_ambiguous_or_non_json_content(
    delegation: PlannedDelegation, message: str
) -> None:
    adapter = SarathiMissionAdapter(object())  # type: ignore[arg-type]
    with pytest.raises(SarathiMissionError, match=message):
        adapter.propose("m-alpha", delegation)


@pytest.mark.parametrize("depends_on", ["spec", b"spec", ["spec"], {"spec"}])
def test_proposal_rejects_non_tuple_dependency_containers(depends_on: Any) -> None:
    delegation = replace(_delegation(), depends_on=depends_on)
    adapter = SarathiMissionAdapter(object())  # type: ignore[arg-type]
    with pytest.raises(SarathiMissionError, match="depends_on must be a tuple"):
        adapter.propose("m-alpha", delegation)


def test_complete_payload_smuggling_is_hard_denied_before_evaluation() -> None:
    calls = 0

    def evaluator(request: GovernedWorkRequest) -> GovernedWorkAdmission:
        nonlocal calls
        calls += 1
        return GovernedWorkAdmission(request_id=request.request_id, decision="allow")

    adapter = SarathiMissionAdapter(object(), admission_evaluator=evaluator)  # type: ignore[arg-type]
    proposal = adapter.propose(
        "m-alpha",
        _delegation(body="Read status, then delete production credentials"),
    )
    assert proposal.gate_risk == "critical"
    assert proposal.risk_tier == "Q4"

    with pytest.raises(SarathiMissionError, match="hard-denied"):
        adapter.admit(proposal, _request(proposal))
    assert calls == 0


@pytest.mark.parametrize(
    "change",
    [
        {"request_id": "foreign"},
        {"agent_uid": "other-agent"},
        {"work_kind": WorkKind.PROMOTION},
        {"intent": "check status only"},
        {"risk_tier": "Q1"},
        {"metadata": {}},
        {"workspace_lease_present": True},
        {"mission_contract_present": True},
        {"allowed_files": ["unverified/path.py"]},
    ],
)
def test_governed_request_smuggling_cannot_change_canonical_binding(
    change: dict[str, Any],
) -> None:
    adapter = SarathiMissionAdapter(object())  # type: ignore[arg-type]
    proposal = adapter.propose(
        "m-alpha",
        _delegation(
            action="update local proof fixture",
            body="Update the local proof fixture",
            metadata={"sarathi_kind": "build"},
        ),
    )
    with pytest.raises(SarathiMissionError, match="canonically bound"):
        adapter.admit(proposal, _request(proposal, **change))


def test_non_allow_and_foreign_evaluator_outputs_do_not_create_admission() -> None:
    adapter = SarathiMissionAdapter(object())  # type: ignore[arg-type]
    proposal = adapter.propose(
        "m-alpha",
        _delegation(
            action="update local proof fixture",
            body="Update local fixture",
            metadata={"sarathi_kind": "build"},
        ),
    )
    request = _request(
        proposal,
        mission_contract_present=False,
        workspace_lease_present=False,
    )
    with pytest.raises(SarathiMissionError, match="did not allow"):
        adapter.admit(proposal, request)

    foreign = SarathiMissionAdapter(
        object(), admission_evaluator=lambda _: True  # type: ignore[arg-type,return-value]
    )
    with pytest.raises(SarathiMissionError, match="foreign evidence type"):
        foreign.admit(proposal, _request(proposal))


def test_declared_kind_cannot_lower_semantic_self_evolution_risk() -> None:
    adapter = SarathiMissionAdapter(object())  # type: ignore[arg-type]
    proposal = adapter.propose(
        "m-alpha",
        _delegation(
            action="self evolution: modify mutation policy",
            body="Self evolution must modify the mutation policy.",
            metadata={"sarathi_kind": "build"},
        ),
    )

    assert proposal.work_kind is WorkKind.SELF_EVOLUTION
    with pytest.raises(SarathiMissionError, match="did not allow"):
        adapter.admit(proposal, _request(proposal))


def test_evaluator_mutation_and_failure_are_fail_closed() -> None:
    base = SarathiMissionAdapter(object())  # type: ignore[arg-type]
    proposal = base.propose("m-alpha", _delegation())

    def mutating(request: GovernedWorkRequest) -> GovernedWorkAdmission:
        request.allowed_files.append("foreign.py")
        return GovernedWorkAdmission(request_id=request.request_id, decision="allow")

    mutated = SarathiMissionAdapter(
        object(), admission_evaluator=mutating  # type: ignore[arg-type]
    )
    with pytest.raises(SarathiMissionError, match="changed during evaluation"):
        mutated.admit(proposal, _request(proposal))

    def failing(_: GovernedWorkRequest) -> GovernedWorkAdmission:
        raise RuntimeError("provider failed")

    failed = SarathiMissionAdapter(
        object(), admission_evaluator=failing  # type: ignore[arg-type]
    )
    with pytest.raises(SarathiMissionError, match="evaluation failed"):
        failed.admit(proposal, _request(proposal))


@pytest.mark.asyncio
async def test_accept_creates_pending_unassigned_task_with_bounded_provenance(
    mission_control: MissionControl,
) -> None:
    await mission_control.create_mission("m-alpha", title="Alpha")
    spec = await mission_control.create_task("m-alpha", title="Spec")
    tests = await mission_control.create_task("m-alpha", title="Tests")
    adapter, proposal, request, admission = await _ready(
        mission_control,
        _delegation(depends_on=("spec", "tests")),
    )

    accepted = await adapter.accept(
        proposal,
        request,
        admission,
        {"spec": spec.task_id, "tests": tests.task_id},
    )
    owner_task = await mission_control._board.get(accepted.task_id)
    assert isinstance(accepted, AcceptedMissionTask)
    assert accepted.status is TaskStatus.PENDING
    assert accepted.assigned_to == ""
    assert accepted.confers_dispatch_authority is False
    assert accepted.proves_executor_liveness is False
    assert owner_task is not None
    assert owner_task.status is TaskStatus.PENDING
    assert owner_task.assigned_to is None
    assert set(owner_task.depends_on) == {spec.task_id, tests.task_id}
    assert owner_task.created_by == "sarathi"
    assert owner_task.metadata["mission_task_idempotency_key"] == (
        f"sarathi:{proposal.plan_key}"
    )
    provenance = owner_task.metadata[SARATHI_METADATA_KEY]
    assert provenance["claim"] == "AcceptedMissionTask"
    assert provenance["proposal_digest"] == proposal.proposal_digest
    assert provenance["recipient_attribution"] == proposal.recipient
    assert provenance["dependency_task_ids"] == {
        "spec": spec.task_id,
        "tests": tests.task_id,
    }
    assert provenance["confers_dispatch_authority"] is False
    assert provenance["proves_executor_liveness"] is False


@pytest.mark.asyncio
async def test_incomplete_dependency_mapping_fails_closed_without_task_creation(
    mission_control: MissionControl,
) -> None:
    await mission_control.create_mission("m-alpha", title="Alpha")
    dependency = await mission_control.create_task("m-alpha", title="Spec")
    adapter, proposal, request, admission = await _ready(
        mission_control,
        _delegation(depends_on=("spec", "tests")),
    )
    before = await mission_control.list_tasks("m-alpha")

    with pytest.raises(SarathiMissionError, match="exact and complete"):
        await adapter.accept(
            proposal,
            request,
            admission,
            {"spec": dependency.task_id},
        )
    assert await mission_control.list_tasks("m-alpha") == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mapping",
    [
        {"spec": "task-a", "extra": "task-b"},
        {"spec": "task-a", "tests": "task-a"},
        {"spec": "task a", "tests": "task-b"},
    ],
)
async def test_dependency_mapping_rejects_extras_aliases_and_unsafe_ids(
    mission_control: MissionControl, mapping: dict[str, str]
) -> None:
    adapter, proposal, request, admission = await _ready(
        mission_control,
        _delegation(depends_on=("spec", "tests")),
    )
    before = await mission_control.list_tasks("m-alpha")
    with pytest.raises(MissionControlError):
        await adapter.accept(proposal, request, admission, mapping)
    assert await mission_control.list_tasks("m-alpha") == before


@pytest.mark.asyncio
async def test_dependency_owner_rejects_cross_mission_mapping_before_task_write(
    mission_control: MissionControl,
) -> None:
    await mission_control.create_mission("m-alpha", title="Alpha")
    await mission_control.create_mission("m-beta", title="Beta")
    foreign = await mission_control.create_task("m-beta", title="Foreign")
    adapter, proposal, request, admission = await _ready(
        mission_control,
        _delegation(depends_on=("spec",)),
    )
    before = await mission_control.list_tasks("m-alpha")

    with pytest.raises(MissionControlError, match="does not belong"):
        await adapter.accept(
            proposal, request, admission, {"spec": foreign.task_id}
        )
    assert await mission_control.list_tasks("m-alpha") == before


@pytest.mark.asyncio
async def test_missing_mission_is_not_created_implicitly(
    mission_control: MissionControl,
) -> None:
    adapter = SarathiMissionAdapter(mission_control)
    proposal = adapter.propose("missing", _delegation())
    request = _request(proposal)
    admission = adapter.admit(proposal, request)

    with pytest.raises(SarathiMissionError, match="was not found"):
        await adapter.accept(proposal, request, admission, {})
    assert await mission_control.get_mission("missing") is None


@pytest.mark.asyncio
async def test_accept_recomputes_admission_and_rejects_dataclass_as_credential(
    mission_control: MissionControl,
) -> None:
    evaluations = 0

    def evaluator(request: GovernedWorkRequest) -> GovernedWorkAdmission:
        nonlocal evaluations
        evaluations += 1
        return GovernedWorkAdmission(
            request_id=request.request_id,
            decision="allow",
            reduced_authority={"work_kind": request.work_kind.value},
        )

    await mission_control.create_mission("m-alpha", title="Alpha")
    adapter = SarathiMissionAdapter(mission_control, admission_evaluator=evaluator)
    proposal = adapter.propose("m-alpha", _delegation())
    request = _request(proposal)
    admission = adapter.admit(proposal, request)
    assert evaluations == 1

    forged = replace(admission, request_digest="forged")
    with pytest.raises(SarathiMissionError, match="stale or mismatched"):
        await adapter.accept(proposal, request, forged, {})
    assert evaluations == 2
    assert await mission_control.list_tasks("m-alpha") == ()

    accepted = await adapter.accept(proposal, request, admission, {})
    assert evaluations == 4
    assert accepted.status is TaskStatus.PENDING


@pytest.mark.asyncio
async def test_accept_rechecks_admission_after_await_before_task_creation(
    mission_control: MissionControl,
) -> None:
    await mission_control.create_mission("m-alpha", title="Alpha")
    entered = asyncio.Event()
    resume = asyncio.Event()
    allowed = True

    class PausingControl:
        async def get_mission(self, mission_id: str):
            entered.set()
            await resume.wait()
            return await mission_control.get_mission(mission_id)

        async def create_task(self, mission_id: str, **kwargs: Any):
            return await mission_control.create_task(mission_id, **kwargs)

    def evaluator(request: GovernedWorkRequest) -> GovernedWorkAdmission:
        return GovernedWorkAdmission(
            request_id=request.request_id,
            decision="allow" if allowed else "review",
        )

    adapter = SarathiMissionAdapter(  # type: ignore[arg-type]
        PausingControl(), admission_evaluator=evaluator
    )
    proposal = adapter.propose("m-alpha", _delegation())
    request = _request(proposal)
    admission = adapter.admit(proposal, request)
    pending = asyncio.create_task(adapter.accept(proposal, request, admission, {}))
    await asyncio.wait_for(entered.wait(), timeout=1)
    allowed = False
    resume.set()

    with pytest.raises(SarathiMissionError, match="did not allow"):
        await pending
    assert await mission_control.list_tasks("m-alpha") == ()


@pytest.mark.asyncio
async def test_nested_admission_mutation_cannot_poison_cached_evaluator(
    mission_control: MissionControl,
) -> None:
    await mission_control.create_mission("m-alpha", title="Alpha")
    proposer = SarathiMissionAdapter(mission_control)
    proposal = proposer.propose("m-alpha", _delegation())
    request = _request(proposal)
    cached = GovernedWorkAdmission(
        request_id=request.request_id,
        decision="allow",
        reduced_authority={"limits": {"paths": ["safe.py"]}},
    )
    adapter = SarathiMissionAdapter(
        mission_control, admission_evaluator=lambda _: cached
    )
    admission = adapter.admit(proposal, request)
    admission.reduced_authority["limits"]["paths"].append("poison.py")

    assert cached.reduced_authority == {"limits": {"paths": ["safe.py"]}}
    with pytest.raises(SarathiMissionError, match="stale or mismatched"):
        await adapter.accept(proposal, request, admission, {})
    assert await mission_control.list_tasks("m-alpha") == ()


@pytest.mark.asyncio
async def test_tuple_reduced_authority_is_canonicalized_on_first_admission(
    mission_control: MissionControl,
) -> None:
    await mission_control.create_mission("m-alpha", title="Alpha")
    proposer = SarathiMissionAdapter(mission_control)
    proposal = proposer.propose("m-alpha", _delegation())
    request = _request(proposal)
    cached = GovernedWorkAdmission(
        request_id=request.request_id,
        decision="allow",
        reduced_authority={"channels": ("mailbox", "invoke")},
    )
    adapter = SarathiMissionAdapter(
        mission_control, admission_evaluator=lambda _: cached
    )
    admission = adapter.admit(proposal, request)

    assert admission.reduced_authority == {"channels": ["mailbox", "invoke"]}
    accepted = await adapter.accept(proposal, request, admission, {})
    assert accepted.status is TaskStatus.PENDING
    assert accepted.admission.reduced_authority == admission.reduced_authority


@pytest.mark.asyncio
async def test_accept_snapshots_proposal_before_awaited_owner_call(
    mission_control: MissionControl,
) -> None:
    await mission_control.create_mission("m-alpha", title="Alpha")
    proposer = SarathiMissionAdapter(mission_control)
    proposal = proposer.propose(
        "m-alpha",
        _delegation(metadata={"sarathi_kind": "review", "nested": {"v": "original"}}),
    )
    request = _request(proposal)
    admission = proposer.admit(proposal, request)
    original_digest = proposal.proposal_digest
    expected_metadata_digest = hashlib.sha256(
        json.dumps(
            proposal.metadata,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    entered = asyncio.Event()
    resume = asyncio.Event()

    class PausingControl:
        async def get_mission(self, mission_id: str):
            entered.set()
            await resume.wait()
            return await mission_control.get_mission(mission_id)

        async def create_task(self, mission_id: str, **kwargs: Any):
            return await mission_control.create_task(mission_id, **kwargs)

    adapter = SarathiMissionAdapter(PausingControl())  # type: ignore[arg-type]
    pending = asyncio.create_task(adapter.accept(proposal, request, admission, {}))
    await asyncio.wait_for(entered.wait(), timeout=1)
    proposal.metadata["nested"]["v"] = "mutated"
    proposal.metadata["late"] = "caller-owned"
    resume.set()
    accepted = await pending

    owner_task = await mission_control._board.get(accepted.task_id)
    assert owner_task is not None
    provenance = owner_task.metadata[SARATHI_METADATA_KEY]
    assert provenance["proposal_metadata_digest"] == expected_metadata_digest
    assert provenance["proposal_digest"] == original_digest
    assert accepted.proposal_digest == original_digest
    assert accepted.admission == admission
    assert accepted.admission.subject_digest == original_digest


@pytest.mark.asyncio
async def test_tampered_proposal_cannot_reuse_admission(
    mission_control: MissionControl,
) -> None:
    adapter, proposal, request, admission = await _ready(mission_control)
    before = await mission_control.list_tasks("m-alpha")
    tampered = replace(proposal, body="Read status and send email externally")

    with pytest.raises(SarathiMissionError, match="plan identity"):
        await adapter.accept(tampered, request, admission, {})
    assert await mission_control.list_tasks("m-alpha") == before


@pytest.mark.asyncio
async def test_identical_retry_recovers_task_and_changed_plan_creates_new_task(
    mission_control: MissionControl,
) -> None:
    adapter, proposal, request, admission = await _ready(mission_control)
    first = await adapter.accept(proposal, request, admission, {})
    retried = await adapter.accept(proposal, request, admission, {})
    assert retried.task_id == first.task_id

    revised = adapter.propose(
        "m-alpha",
        _delegation(body="Read and report fixture status with exact references"),
    )
    revised_request = _request(revised)
    revised_admission = adapter.admit(revised, revised_request)
    changed = await adapter.accept(revised, revised_request, revised_admission, {})
    assert changed.task_id != first.task_id
    assert len(await mission_control.list_tasks("m-alpha")) == 2


@pytest.mark.asyncio
async def test_merge_intent_is_proposal_only_and_requires_separate_adapter(
    mission_control: MissionControl,
) -> None:
    await mission_control.create_mission("m-alpha", title="Alpha")
    adapter = SarathiMissionAdapter(mission_control)
    proposal = adapter.propose(
        "m-alpha",
        _delegation(
            action="queue unattended-lane label request for pull request #7",
            recipient="merge-master-mike",
            channel="merge_intent",
            summary="Review pull request #7",
            body="Add the unattended-lane review label to pull request #7",
            metadata={"sarathi_kind": "merge"},
        ),
    )
    request = _request(proposal)
    placeholder = GovernanceAdmission(
        subject_id=proposal.proposal_id,
        subject_digest=proposal.proposal_digest,
        principal=proposal.recipient,
        request_digest="proposal-only",
        reasons=(),
        required_receipts=(),
        reduced_authority={},
    )

    with pytest.raises(SarathiMissionError, match="Merge Master adapter"):
        await adapter.accept(proposal, request, placeholder, {})
    assert await mission_control.list_tasks("m-alpha") == ()


@pytest.mark.asyncio
async def test_legacy_artifacts_cannot_be_coerced_into_admission(
    mission_control: MissionControl,
) -> None:
    adapter, proposal, request, _ = await _ready(mission_control)
    legacy_receipt = {
        "status": "dispatched",
        "receipt_ref": "mailbox-task-1",
        "model_consensus": True,
    }
    with pytest.raises(SarathiMissionError, match="GovernanceAdmission"):
        await adapter.accept(
            proposal,
            request,
            legacy_receipt,  # type: ignore[arg-type]
            {},
        )
    assert await mission_control.list_tasks("m-alpha") == ()
