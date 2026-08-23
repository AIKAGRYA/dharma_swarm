from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import dharma_swarm.mission_control_binding as binding_module
import dharma_swarm.mission_control_binding_manifest as binding_manifest_module
from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_authority import (
    CAMPAIGN_AUTHORITY_METADATA_KEY,
    FileExecutionLeaseAuthorityVerifier,
)
from dharma_swarm.mission_control_binding import (
    AUTHORITY_ACTIONS,
    AUTHORITY_MANIFEST_SCHEMA_VERSION,
    authority_manifest_digest,
    bind_campaign_authority,
    campaign_workspace_path,
    load_campaign_authority_manifest,
)
from dharma_swarm.mission_control_binding_render import (
    CampaignGoalBindingPolicy,
    deterministic_read_only_policies,
    render_campaign_authority_manifest,
)
from dharma_swarm.mission_control_bootstrap import BootstrapResult
from dharma_swarm.mission_control_contract import MissionControlError, stable_id
from dharma_swarm.mission_control_dispatch import (
    GOVERNANCE_METADATA_KEY,
    DispatchAuthorityEnvelope,
    GovernanceAdmission,
    MissionDispatchRequest,
)
from dharma_swarm.mission_control_execution import OrchestratorMissionAdapter
from dharma_swarm.mission_control_observed_input import (
    ObservedInputBinding,
    ingest_observed_input_manifest,
    observed_input_manifest_digest,
    render_observed_input_manifest,
)
from dharma_swarm.mission_control_roster import (
    CampaignAgentRoster,
    CampaignAgentSeat,
)
from dharma_swarm.models import (
    AgentRole,
    AgentState,
    AgentStatus,
    ProviderType,
    Task,
)
from dharma_swarm.operator_core.execution_lease import (
    content_hash,
    lease_path,
    load_execution_lease,
    record_lease_revocation,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard


CAMPAIGN_ID = "sadhana-10-test"
PORTFOLIO_DIGEST = "sha256:" + "a" * 64
ROSTER_DIGEST = "b" * 64
HELD_OUT_ORACLE_DIGEST = "sha256:" + "d" * 64
OPERATOR_CONTROL_DIGEST = "sha256:" + "e" * 64
OPERATOR_CONTROL_BINDING_DIGEST = "sha256:" + "f" * 64
DEPLOYMENT_TOPOLOGY_DIGEST = "sha256:" + "0" * 64
DEPLOYMENT_CREDENTIAL_DIGEST = "sha256:" + "1" * 64
BOOTSTRAP_SCHEMA = "dharma.sadhana.mission_bootstrap.v1"
GOAL_SCHEMA = "dharma.sadhana.goal_contracts.v1"


@dataclass
class _Roster:
    agents: list[AgentState]

    async def list_agents(self) -> list[AgentState]:
        return list(self.agents)


@dataclass
class _BindingCase:
    control: MissionControl
    board: TaskBoard
    runtime: RuntimeStateStore
    observed_inputs: ObservedInputBinding
    manifest_path: Path
    manifest: dict[str, Any]
    lease_root: Path
    roster: _Roster
    campaign_roster: CampaignAgentRoster
    tasks: dict[str, Task]
    now: datetime


def _goal_digest(index: int) -> str:
    return f"sha256:{index + 1:064x}"


def _agent(
    index: int,
    *,
    identifier: str | None = None,
    name: str | None = None,
    status: AgentStatus = AgentStatus.IDLE,
) -> AgentState:
    return AgentState(
        id=identifier or f"runtime-agent-{index}",
        name=name or f"stable-agent-{index}",
        role=AgentRole.CODER,
        status=status,
        provider=ProviderType.OLLAMA.value,
        model=f"fixture-model-{index}:cloud",
    )


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    payload["manifest_digest"] = authority_manifest_digest(payload)
    path.write_text(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )
    path.chmod(0o600)


@pytest.mark.parametrize("flag", ["O_NOFOLLOW", "O_DIRECTORY"])
def test_authority_manifest_requires_secure_open_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
) -> None:
    payload = {
        "schema_version": AUTHORITY_MANIFEST_SCHEMA_VERSION,
        "manifest_digest": "",
    }
    path = tmp_path / "authority.json"
    _write_manifest(path, payload)
    monkeypatch.delattr(binding_manifest_module.os, flag)

    with pytest.raises(MissionControlError, match="O_NOFOLLOW and O_DIRECTORY"):
        load_campaign_authority_manifest(path)


async def _case(tmp_path: Path, *, goal_count: int = 10) -> _BindingCase:
    board = TaskBoard(tmp_path / "tasks.db")
    runtime = RuntimeStateStore(
        tmp_path / "runtime.db",
        include_memory_plane=False,
    )
    await board.init_db()
    await runtime.init_db()
    control = MissionControl(board, runtime)
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    campaign_end = now + timedelta(days=10)
    await control.create_mission(
        CAMPAIGN_ID,
        title="SADHANA test campaign",
        metadata={
            "sadhana_bootstrap_schema": BOOTSTRAP_SCHEMA,
            "goal_contract_schema": GOAL_SCHEMA,
            "goal_contract_sha256": PORTFOLIO_DIGEST,
            "campaign_id": CAMPAIGN_ID,
            "campaign_deadline": campaign_end.isoformat(),
            "goal_count": goal_count,
            "dispatch_ready": False,
            "dispatch_blocker": "authority_unbound",
        },
    )
    tasks: dict[str, Task] = {}
    agents: list[AgentState] = []
    goals: dict[str, dict[str, Any]] = {}
    for index in range(goal_count):
        goal_id = f"goal-{index + 1:02d}"
        digest = _goal_digest(index)
        view = await control.create_task(
            CAMPAIGN_ID,
            title=goal_id,
            description=f"Complete {goal_id} exactly.",
            idempotency_key=stable_id(
                "sadhana_goal", CAMPAIGN_ID, PORTFOLIO_DIGEST, goal_id
            ),
            created_by="sadhana-bootstrap",
            metadata={
                "sadhana_bootstrap_schema": BOOTSTRAP_SCHEMA,
                "goal_contract_schema": GOAL_SCHEMA,
                "portfolio_contract_sha256": PORTFOLIO_DIGEST,
                "goal_contract_sha256": digest,
                "campaign_id": CAMPAIGN_ID,
                "goal_id": goal_id,
                "goal_dependencies": [],
                "goal_priority": "P2",
                "goal_deadline": campaign_end.isoformat(),
                "attempt_ceiling": 3,
                "cash_ceiling_usd": 0.0,
                "concurrency_ceiling": 1,
                "default_attempt_policy": "bounded",
                "dispatch_ready": False,
                "dispatch_blocker": "authority_unbound",
            },
        )
        task = await board.get(view.task_id)
        assert task is not None
        tasks[goal_id] = task
        agent = _agent(index)
        agents.append(agent)
        goals[goal_id] = {
            "task_id": task.id,
            "goal_contract_sha256": digest,
            "task_creation_hash": task.metadata["mission_task_creation_hash"],
            "effect_mode": "read_only",
            "agent_name": agent.name,
            "workspace_path": campaign_workspace_path(CAMPAIGN_ID, goal_id),
            "allowed_files": [f"campaign/{goal_id}/work.md"],
            "max_attempts": 3,
            "max_usd": 0.0,
        }
    manifest: dict[str, Any] = {
        "schema_version": AUTHORITY_MANIFEST_SCHEMA_VERSION,
        "campaign_id": CAMPAIGN_ID,
        "mission_id": CAMPAIGN_ID,
        "goal_contract_sha256": PORTFOLIO_DIGEST,
        "agent_roster_sha256": ROSTER_DIGEST,
        "campaign_end": campaign_end.isoformat(),
        "allowed_actions": list(AUTHORITY_ACTIONS),
        "max_usd": 0.0,
        "observed_input_manifest_digest": "",
        "held_out_oracle_manifest_digest": HELD_OUT_ORACLE_DIGEST,
        "operator_control_semantics_sha256": OPERATOR_CONTROL_DIGEST,
        "operator_control_authority_binding_sha256": (
            OPERATOR_CONTROL_BINDING_DIGEST
        ),
        "deployment_authority_topology_sha256": DEPLOYMENT_TOPOLOGY_DIGEST,
        "deployment_authority_credential_clarification_sha256": (
            DEPLOYMENT_CREDENTIAL_DIGEST
        ),
        "goals": goals,
        "manifest_digest": "",
    }
    bootstrap = BootstrapResult(
        mission_id=CAMPAIGN_ID,
        contract_digest=PORTFOLIO_DIGEST,
        campaign_deadline=campaign_end.isoformat(),
        dependency_order=tuple(sorted(tasks)),
        goal_task_map=tuple((goal_id, tasks[goal_id].id) for goal_id in sorted(tasks)),
        goal_contract_digests=tuple(
            (goal_id, tasks[goal_id].metadata["goal_contract_sha256"])
            for goal_id in sorted(tasks)
        ),
        canary_goal_id=sorted(tasks)[0],
        canary_task_id=tasks[sorted(tasks)[0]].id,
    )
    source_payload: dict[str, Any] = {
        "schema_version": "dharma.sadhana.observed_input_source.v1",
        "campaign_id": CAMPAIGN_ID,
        "mission_id": CAMPAIGN_ID,
        "portfolio_contract_sha256": PORTFOLIO_DIGEST,
        "goals": {},
    }
    for goal_id in sorted(tasks):
        content = f"Observed fixture state for {goal_id}; verify independently.\n"
        source_payload["goals"][goal_id] = {
            "goal_contract_sha256": tasks[goal_id].metadata["goal_contract_sha256"],
            "observed_at": now.isoformat(),
            "epistemic_state": "observed_unverified",
            "authority_scope": "prompt_context_only",
            "media_type": "text/markdown; charset=utf-8",
            "content": content,
            "content_sha256": "sha256:" + hashlib.sha256(content.encode()).hexdigest(),
        }
    source_payload["manifest_digest"] = observed_input_manifest_digest(source_payload)
    source_path = tmp_path / "observed-inputs.source.json"
    source_path.write_text(
        json.dumps(
            source_payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )
    source_path.chmod(0o600)
    observed_path = tmp_path / "observed-inputs.json"
    observed_path.write_bytes(
        await render_observed_input_manifest(source_path, bootstrap, board, now=now)
    )
    observed_path.chmod(0o600)
    observed_inputs = await ingest_observed_input_manifest(observed_path, board, runtime)
    manifest["observed_input_manifest_digest"] = observed_inputs.manifest_digest
    for goal_id, bound in observed_inputs.by_goal.items():
        manifest["goals"][goal_id]["observed_input_ref"] = bound.ref.to_dict()
    manifest_path = tmp_path / "authority-manifest.json"
    _write_manifest(manifest_path, manifest)
    campaign_roster = CampaignAgentRoster(
        campaign_id=CAMPAIGN_ID,
        objective_sha256="c" * 64,
        activation_at=now - timedelta(minutes=1),
        expires_at=campaign_end,
        catalog_observed_at=now - timedelta(minutes=1),
        catalog_models=tuple(agent.model.removesuffix(":cloud") for agent in agents),
        seats=tuple(
            CampaignAgentSeat(
                name=agent.name,
                role=agent.role,
                provider=ProviderType.OLLAMA,
                model=agent.model,
                family=f"family-{index}",
                thread=f"thread-{index}",
                system_prompt="Bound fixture seat.",
            )
            for index, agent in enumerate(agents)
        ),
        manifest_sha256=ROSTER_DIGEST,
    )
    return _BindingCase(
        control=control,
        board=board,
        runtime=runtime,
        observed_inputs=observed_inputs,
        manifest_path=manifest_path,
        manifest=manifest,
        lease_root=tmp_path / "leases",
        roster=_Roster(agents),
        campaign_roster=campaign_roster,
        tasks=tasks,
        now=now,
    )


def _index_lines(case: _BindingCase) -> list[str]:
    path = case.lease_root / "index.jsonl"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


@pytest.mark.asyncio
async def test_renderer_derives_task_ids_and_hashes_from_bootstrap_owner_state(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=2)
    goal_ids = tuple(sorted(case.tasks))
    bootstrap = BootstrapResult(
        mission_id=CAMPAIGN_ID,
        contract_digest=PORTFOLIO_DIGEST,
        campaign_deadline=case.manifest["campaign_end"],
        dependency_order=goal_ids,
        goal_task_map=tuple((goal_id, case.tasks[goal_id].id) for goal_id in goal_ids),
        goal_contract_digests=tuple(
            (goal_id, case.tasks[goal_id].metadata["goal_contract_sha256"])
            for goal_id in goal_ids
        ),
        canary_goal_id=goal_ids[0],
        canary_task_id=case.tasks[goal_ids[0]].id,
    )
    policies = tuple(
        CampaignGoalBindingPolicy(
            goal_id=goal_id,
            agent_name=case.manifest["goals"][goal_ids[0]]["agent_name"],
            allowed_files=tuple(case.manifest["goals"][goal_id]["allowed_files"]),
        )
        for goal_id in goal_ids
    )

    first = await render_campaign_authority_manifest(
        bootstrap,
        case.board,
        case.campaign_roster,
        policies,
        case.observed_inputs,
        reserved_agent_names=(
            case.manifest["goals"][goal_ids[1]]["agent_name"],
        ),
        held_out_oracle_manifest_digest=HELD_OUT_ORACLE_DIGEST,
        operator_control_semantics_sha256=OPERATOR_CONTROL_DIGEST,
        operator_control_authority_binding_sha256=OPERATOR_CONTROL_BINDING_DIGEST,
        deployment_authority_topology_sha256=DEPLOYMENT_TOPOLOGY_DIGEST,
        deployment_authority_credential_clarification_sha256=(
            DEPLOYMENT_CREDENTIAL_DIGEST
        ),
    )
    second = await render_campaign_authority_manifest(
        bootstrap,
        case.board,
        case.campaign_roster,
        policies,
        case.observed_inputs,
        reserved_agent_names=(
            case.manifest["goals"][goal_ids[1]]["agent_name"],
        ),
        held_out_oracle_manifest_digest=HELD_OUT_ORACLE_DIGEST,
        operator_control_semantics_sha256=OPERATOR_CONTROL_DIGEST,
        operator_control_authority_binding_sha256=OPERATOR_CONTROL_BINDING_DIGEST,
        deployment_authority_topology_sha256=DEPLOYMENT_TOPOLOGY_DIGEST,
        deployment_authority_credential_clarification_sha256=(
            DEPLOYMENT_CREDENTIAL_DIGEST
        ),
    )
    rendered = tmp_path / "rendered-authority.json"
    rendered.write_bytes(first)
    rendered.chmod(0o600)
    loaded = load_campaign_authority_manifest(rendered)

    assert second == first
    assert loaded.mission_id == bootstrap.mission_id
    assert {goal.task_id for goal in loaded.goals} == set(dict(bootstrap.goal_task_map).values())
    assert {
        goal.task_creation_hash for goal in loaded.goals
    } == {
        task.metadata["mission_task_creation_hash"] for task in case.tasks.values()
    }

    reserved = case.manifest["goals"][goal_ids[1]]["agent_name"]
    conflicting = tuple(
        replace(policy, agent_name=reserved)
        if policy.goal_id == goal_ids[1]
        else policy
        for policy in policies
    )
    with pytest.raises(MissionControlError, match="reserved verifier seat"):
        await render_campaign_authority_manifest(
            bootstrap,
            case.board,
            case.campaign_roster,
            conflicting,
            case.observed_inputs,
            reserved_agent_names=(reserved,),
            held_out_oracle_manifest_digest=HELD_OUT_ORACLE_DIGEST,
            operator_control_semantics_sha256=OPERATOR_CONTROL_DIGEST,
            operator_control_authority_binding_sha256=(
                OPERATOR_CONTROL_BINDING_DIGEST
            ),
            deployment_authority_topology_sha256=DEPLOYMENT_TOPOLOGY_DIGEST,
            deployment_authority_credential_clarification_sha256=(
                DEPLOYMENT_CREDENTIAL_DIGEST
            ),
        )


@pytest.mark.asyncio
async def test_default_policy_round_robins_only_non_verifier_seats(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=2)
    goal_ids = tuple(sorted(case.tasks))
    bootstrap = BootstrapResult(
        mission_id=CAMPAIGN_ID,
        contract_digest=PORTFOLIO_DIGEST,
        campaign_deadline=case.manifest["campaign_end"],
        dependency_order=goal_ids,
        goal_task_map=tuple((goal_id, case.tasks[goal_id].id) for goal_id in goal_ids),
        goal_contract_digests=tuple(
            (goal_id, case.tasks[goal_id].metadata["goal_contract_sha256"])
            for goal_id in goal_ids
        ),
        canary_goal_id=goal_ids[0],
        canary_task_id=case.tasks[goal_ids[0]].id,
    )
    verifier_name = case.campaign_roster.seats[1].name
    roster = replace(
        case.campaign_roster,
        seats=(
            case.campaign_roster.seats[0],
            replace(case.campaign_roster.seats[1], role=AgentRole.VALIDATOR),
        ),
    )

    policies = deterministic_read_only_policies(
        bootstrap,
        roster,
        verifier_seat_name=verifier_name,
    )

    assert {policy.agent_name for policy in policies} == {roster.seats[0].name}
    assert all(
        policy.allowed_files
        == (f"{campaign_workspace_path(CAMPAIGN_ID, policy.goal_id)}/result.md",)
        for policy in policies
    )


@pytest.mark.asyncio
async def test_exact_ten_goal_binding_is_idempotent_and_preserves_seed_provenance(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)

    first = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    assert len(first.tasks) == 10
    assert first.lease_writes == 10
    assert first.metadata_writes == 10


    for bound in first.tasks:
        task = await case.board.get(bound.task_id)
        assert task is not None
        assert task.metadata["dispatch_ready"] is False
        assert task.metadata["dispatch_blocker"] == "authority_unbound"
        authority = task.metadata[CAMPAIGN_AUTHORITY_METADATA_KEY]
        governance = task.metadata[GOVERNANCE_METADATA_KEY]
        assert authority["claimed_principal"] == bound.principal_id
        assert authority["request_id"] == bound.request_id
        assert authority["max_usd"] == 0
        assert authority["allowed_files"] == governance["allowed_files"]
        assert authority["route_lock"] == {
            "schema_version": "dharma.sadhana.campaign_route_lock.v1",
            "task_id": task.id,
            "principal_id": bound.principal_id,
            "provider": task.metadata["preferred_provider"],
            "model": task.metadata["preferred_model"],
            "allow_provider_routing": False,
        }
        lease = load_execution_lease(case.lease_root, bound.authority_ref)
        for field in (
            "operator_control_semantics_sha256",
            "operator_control_authority_binding_sha256",
            "deployment_authority_topology_sha256",
            "deployment_authority_credential_clarification_sha256",
        ):
            assert authority[field] == governance[field] == lease[field] == case.manifest[field]
        assert lease["issued_to"] == bound.principal_id
        assert lease["correlation_id"] == bound.request_id
        assert lease["allowed_actions"] == list(AUTHORITY_ACTIONS)
        assert lease["allowed_paths"] == governance["allowed_files"]
        assert lease["budget"]["max_usd"] == 0
        assert lease["expires_at"] == case.manifest["campaign_end"]

    second = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now + timedelta(seconds=1),
    )
    assert second.lease_writes == 0
    assert second.metadata_writes == 0
    assert second.tasks == first.tasks
    assert len(_index_lines(case)) == 10


@pytest.mark.asyncio
async def test_reserved_verifier_seat_cannot_receive_producer_authority(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path)
    reserved = case.manifest["goals"]["goal-01"]["agent_name"]

    with pytest.raises(MissionControlError, match="reserved verifier seat"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            reserved_agent_names=(reserved,),
            now=case.now,
        )

    assert not list(case.lease_root.glob("*.json"))
    assert _index_lines(case) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "duplicate"])
async def test_required_agent_name_must_resolve_to_exactly_one_live_state(
    tmp_path: Path,
    failure: str,
) -> None:
    case = await _case(tmp_path, goal_count=2)
    required = case.roster.agents[0]
    if failure == "missing":
        case.roster.agents = case.roster.agents[1:]
    else:
        case.roster.agents.append(
            _agent(99, identifier="duplicate-id", name=required.name)
        )

    with pytest.raises(MissionControlError, match="not exactly one live state"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            now=case.now,
        )

    assert not case.lease_root.exists()
    for task in case.tasks.values():
        current = await case.board.get(task.id)
        assert current is not None
        assert CAMPAIGN_AUTHORITY_METADATA_KEY not in current.metadata


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["roster_digest", "model_drift", "roster_end"])
async def test_authority_is_bound_to_the_exact_pinned_runtime_roster(
    tmp_path: Path,
    failure: str,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    if failure == "roster_digest":
        case.manifest["agent_roster_sha256"] = "d" * 64
        _write_manifest(case.manifest_path, case.manifest)
    elif failure == "model_drift":
        case.roster.agents[0] = case.roster.agents[0].model_copy(
            update={"model": "stale-model:cloud"}
        )
    else:
        case.campaign_roster = replace(
            case.campaign_roster,
            expires_at=case.campaign_roster.expires_at - timedelta(seconds=1),
        )

    with pytest.raises(MissionControlError, match="roster|drifted"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            now=case.now,
        )

    assert not case.lease_root.exists()


@pytest.mark.asyncio
async def test_busy_principal_binds_identity_without_claiming_task(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    case.roster.agents[0] = case.roster.agents[0].model_copy(
        update={"status": AgentStatus.BUSY, "current_task": "other-task"}
    )

    result = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )

    task = await case.board.get(result.tasks[0].task_id)
    assert task is not None
    assert task.assigned_to is None
    assert task.status.value == "pending"
    assert result.tasks[0].principal_id == case.roster.agents[0].id


@pytest.mark.asyncio
async def test_lease_first_and_missing_lease_partials_recover_without_duplicate_index(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=2)
    first = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    first_bound, second_bound = first.tasks
    first_task = await case.board.get(first_bound.task_id)
    second_task = await case.board.get(second_bound.task_id)
    assert first_task is not None and second_task is not None
    first_metadata = dict(first_task.metadata)
    first_metadata.pop(CAMPAIGN_AUTHORITY_METADATA_KEY)
    first_metadata.pop(GOVERNANCE_METADATA_KEY)
    await case.board.update_task(first_task.id, metadata=first_metadata)
    lease_path(case.lease_root, second_bound.authority_ref).unlink()

    recovered = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now + timedelta(seconds=1),
    )

    assert recovered.lease_writes == 1
    assert recovered.metadata_writes == 2
    assert len(_index_lines(case)) == 3


@pytest.mark.asyncio
async def test_restart_id_rebinding_refreshes_each_lease_once(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=2)
    first = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    case.roster.agents = [
        agent.model_copy(update={"id": f"restart-{agent.id}"})
        for agent in case.roster.agents
    ]

    rebound = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now + timedelta(minutes=1),
    )
    assert rebound.lease_writes == 2
    assert rebound.metadata_writes == 2
    assert {task.principal_id for task in rebound.tasks} == {
        agent.id for agent in case.roster.agents
    }
    assert {task.authority_ref for task in rebound.tasks} == {
        task.authority_ref for task in first.tasks
    }
    assert len(_index_lines(case)) == 4

    unchanged = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now + timedelta(minutes=2),
    )
    assert unchanged.lease_writes == 0
    assert unchanged.metadata_writes == 0
    assert len(_index_lines(case)) == 4


@pytest.mark.asyncio
async def test_owner_execution_stamp_survives_fresh_process_rebind(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    first = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    bound = first.tasks[0]
    task = await case.board.get(bound.task_id)
    assert task is not None
    runtime = RuntimeStateStore(tmp_path / "runtime.db", include_memory_plane=False)
    adapter = OrchestratorMissionAdapter(  # type: ignore[arg-type]
        None,
        case.control,
        case.board,
        runtime,
    )
    expected = adapter._expected_identity(CAMPAIGN_ID, task.id, "default", 0)
    await case.board.update_task(
        task.id,
        metadata=adapter._stamp_metadata(
            task,
            mission_id=CAMPAIGN_ID,
            dispatch_key="default",
            attempt_generation=0,
            expected=expected,
        ),
    )
    index_before = _index_lines(case)
    lease_before = lease_path(case.lease_root, bound.authority_ref).read_bytes()

    reopened_board = TaskBoard(tmp_path / "tasks.db")
    reopened_runtime = RuntimeStateStore(
        tmp_path / "runtime.db",
        include_memory_plane=False,
    )
    await reopened_board.init_db()
    await reopened_runtime.init_db()
    reopened_control = MissionControl(reopened_board, reopened_runtime)
    rebound = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=reopened_control,
        board=reopened_board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now + timedelta(seconds=1),
    )

    assert rebound.lease_writes == 0
    assert rebound.metadata_writes == 0
    assert _index_lines(case) == index_before
    assert lease_path(case.lease_root, bound.authority_ref).read_bytes() == lease_before


@pytest.mark.asyncio
async def test_foreign_partial_state_is_rejected_before_any_write(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=2)
    first = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    early, late = first.tasks
    early_task = await case.board.get(early.task_id)
    late_task = await case.board.get(late.task_id)
    assert early_task is not None and late_task is not None
    early_metadata = dict(early_task.metadata)
    early_metadata.pop(CAMPAIGN_AUTHORITY_METADATA_KEY)
    await case.board.update_task(early.task_id, metadata=early_metadata)
    late_metadata = dict(late_task.metadata)
    late_authority = dict(late_metadata[CAMPAIGN_AUTHORITY_METADATA_KEY])
    late_authority["workspace_path"] = "foreign/workspace"
    late_metadata[CAMPAIGN_AUTHORITY_METADATA_KEY] = late_authority
    await case.board.update_task(late.task_id, metadata=late_metadata)
    before_index = list(_index_lines(case))

    with pytest.raises(MissionControlError, match="foreign workspace_path"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            now=case.now + timedelta(seconds=1),
        )

    still_early = await case.board.get(early.task_id)
    assert still_early is not None
    assert CAMPAIGN_AUTHORITY_METADATA_KEY not in still_early.metadata
    assert _index_lines(case) == before_index


@pytest.mark.asyncio
async def test_foreign_nested_route_lock_is_rejected_before_any_write(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    first = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    task = await case.board.get(first.tasks[0].task_id)
    assert task is not None
    metadata = dict(task.metadata)
    authority = dict(metadata[CAMPAIGN_AUTHORITY_METADATA_KEY])
    authority["route_lock"] = {
        **authority["route_lock"],
        "provider": "foreign-provider",
        "allow_provider_routing": True,
    }
    metadata[CAMPAIGN_AUTHORITY_METADATA_KEY] = authority
    await case.board.update_task(task.id, metadata=metadata)
    before_index = _index_lines(case)

    with pytest.raises(MissionControlError, match="foreign route_lock"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            now=case.now + timedelta(seconds=1),
        )

    assert _index_lines(case) == before_index


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["actions", "budget", "paths", "correlation"])
async def test_foreign_lease_scope_is_rejected_not_silently_repaired(
    tmp_path: Path,
    field: str,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    first = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    bound = first.tasks[0]
    lease = load_execution_lease(case.lease_root, bound.authority_ref)
    if field == "actions":
        lease["allowed_actions"].append("extra_action")
    elif field == "budget":
        lease["budget"]["max_usd"] = 1.0
    elif field == "paths":
        lease["allowed_paths"] = ["foreign/path"]
    else:
        lease["correlation_id"] = "foreign-correlation"
    lease["content_hash"] = content_hash(lease)
    path = lease_path(case.lease_root, bound.authority_ref)
    path.write_text(json.dumps(lease, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(MissionControlError, match="foreign|budget conflicts"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            now=case.now + timedelta(seconds=1),
        )

    assert len(_index_lines(case)) == 1


@pytest.mark.asyncio
async def test_expired_campaign_and_lease_end_overrun_fail_closed(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    with pytest.raises(MissionControlError, match="expired"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            now=case.now + timedelta(days=11),
        )

    first = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    bound = first.tasks[0]
    lease = load_execution_lease(case.lease_root, bound.authority_ref)
    lease["expires_at"] = (case.now + timedelta(days=11)).isoformat()
    lease["content_hash"] = content_hash(lease)
    lease_path(case.lease_root, bound.authority_ref).write_text(
        json.dumps(lease, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(MissionControlError, match="expiry conflicts"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            now=case.now + timedelta(seconds=1),
        )


@pytest.mark.asyncio
async def test_write_capable_manifest_is_fenced_without_enforced_sandbox(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    case.manifest["goals"]["goal-01"]["effect_mode"] = "write"
    _write_manifest(case.manifest_path, case.manifest)

    with pytest.raises(MissionControlError, match="enforced workspace sandbox"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            now=case.now,
        )

    assert not case.lease_root.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("description", "Drifted definition of done."),
        ("goal_dependencies", ["foreign-goal"]),
        ("goal_priority", "P0"),
        ("concurrency_ceiling", 2),
        ("default_attempt_policy", "foreign-policy"),
    ],
)
async def test_seed_static_contract_drift_fails_before_authority_writes(
    tmp_path: Path,
    field: str,
    value: Any,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    task = next(iter(case.tasks.values()))
    if field == "description":
        await case.board.update_task(task.id, description=value)
    else:
        await case.board.update_task(
            task.id,
            metadata={**task.metadata, field: value},
        )

    with pytest.raises(MissionControlError, match="conflicts|invalid"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            now=case.now,
        )

    assert not case.lease_root.exists()


@pytest.mark.asyncio
async def test_other_sadhana_campaign_does_not_occupy_exact_namespace(
    tmp_path: Path,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    await case.control.create_mission("other-sadhana", title="Other campaign")
    await case.control.create_task(
        "other-sadhana",
        title="other-goal",
        metadata={
            "sadhana_bootstrap_schema": BOOTSTRAP_SCHEMA,
            "campaign_id": "other-sadhana",
            "goal_id": "other-goal",
        },
    )

    result = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )

    assert len(result.tasks) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("restart", [False, True])
async def test_revoked_deterministic_lease_never_resurrects_on_rerun(
    tmp_path: Path,
    restart: bool,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    first = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    bound = first.tasks[0]
    record_lease_revocation(case.lease_root, bound.authority_ref, reason="operator stop")
    task_before = await case.board.get(bound.task_id)
    lease_before = lease_path(case.lease_root, bound.authority_ref).read_bytes()
    index_before = list(_index_lines(case))
    if restart:
        case.roster.agents[0] = case.roster.agents[0].model_copy(
            update={"id": "restart-agent-id"}
        )
        reopened_board = TaskBoard(tmp_path / "tasks.db")
        reopened_runtime = RuntimeStateStore(
            tmp_path / "runtime.db",
            include_memory_plane=False,
        )
        await reopened_board.init_db()
        await reopened_runtime.init_db()
        case.board = reopened_board
        case.control = MissionControl(reopened_board, reopened_runtime)

    with pytest.raises(MissionControlError, match="revoked"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            now=case.now + timedelta(seconds=1),
        )

    assert await case.board.get(bound.task_id) == task_before
    assert lease_path(case.lease_root, bound.authority_ref).read_bytes() == lease_before
    assert _index_lines(case) == index_before


@pytest.mark.asyncio
async def test_revocation_between_plan_and_write_never_projects_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    original_write = binding_module.write_execution_lease

    def revoke_then_write(lease: dict[str, Any], root: Path):
        record_lease_revocation(root, lease["lease_id"], reason="concurrent operator stop")
        return original_write(lease, root)

    monkeypatch.setattr(binding_module, "write_execution_lease", revoke_then_write)
    with pytest.raises(MissionControlError, match="revoked"):
        await bind_campaign_authority(
            manifest_path=case.manifest_path,
            mission_control=case.control,
            board=case.board,
            agent_pool=case.roster,
            campaign_roster=case.campaign_roster,
            observed_inputs=case.observed_inputs,
            runtime_state=case.runtime,
            lease_root=case.lease_root,
            now=case.now,
        )

    task = await case.board.get(next(iter(case.tasks.values())).id)
    assert task is not None
    assert CAMPAIGN_AUTHORITY_METADATA_KEY not in task.metadata
    assert GOVERNANCE_METADATA_KEY not in task.metadata


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("goal_id", "foreign-goal"),
        ("portfolio_contract_sha256", "sha256:" + "e" * 64),
        ("goal_contract_sha256", "sha256:" + "f" * 64),
        ("manifest_digest", "sha256:" + "0" * 64),
        ("agent_roster_sha256", "1" * 64),
        ("campaign_end", "2030-01-09T00:00:00+00:00"),
        ("expires_at", "2030-01-09T00:00:00+00:00"),
        ("agent_name", "foreign-agent"),
        ("workspace_path", "foreign/workspace"),
        ("allowed_paths", ["foreign/path"]),
        ("effect_mode", "write"),
    ],
)
async def test_file_verifier_rejects_every_foreign_campaign_lineage_field(
    tmp_path: Path,
    field: str,
    value: Any,
) -> None:
    case = await _case(tmp_path, goal_count=1)
    result = await bind_campaign_authority(
        manifest_path=case.manifest_path,
        mission_control=case.control,
        board=case.board,
        agent_pool=case.roster,
        campaign_roster=case.campaign_roster,
        observed_inputs=case.observed_inputs,
        runtime_state=case.runtime,
        lease_root=case.lease_root,
        now=case.now,
    )
    bound = result.tasks[0]
    lease = load_execution_lease(case.lease_root, bound.authority_ref)
    lease[field] = value
    lease["content_hash"] = content_hash(lease)
    lease_path(case.lease_root, bound.authority_ref).write_text(
        json.dumps(lease, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    task = await case.board.get(bound.task_id)
    assert task is not None
    authority = dict(task.metadata[CAMPAIGN_AUTHORITY_METADATA_KEY])
    authority["authority_digest"] = lease["content_hash"]
    await case.board.update_task(
        task.id,
        metadata={**task.metadata, CAMPAIGN_AUTHORITY_METADATA_KEY: authority},
    )
    request = MissionDispatchRequest.new(
        case.manifest["mission_id"],
        task.id,
        dispatch_key=bound.dispatch_key,
        claimed_principal=bound.principal_id,
    )
    envelope = DispatchAuthorityEnvelope(
        claimed_principal=bound.principal_id,
        mission_id=request.mission_id,
        task_id=task.id,
        dispatch_key=bound.dispatch_key,
        authority_ref=bound.authority_ref,
        authority_digest=lease["content_hash"],
    )
    admission = GovernanceAdmission(
        subject_id="fixture-subject",
        subject_digest="fixture-subject-digest",
        principal=bound.principal_id,
        request_digest="fixture-request-digest",
        reasons=(),
        required_receipts=(),
        reduced_authority={},
    )

    with pytest.raises(
        MissionControlError,
        match="authority|lineage|sandbox|observed prompt",
    ):
        await FileExecutionLeaseAuthorityVerifier(
            case.lease_root,
            case.board,
        ).verify(envelope, request=request, admission=admission)
