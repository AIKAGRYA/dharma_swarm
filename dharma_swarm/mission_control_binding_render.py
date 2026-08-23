"""Deterministically render authority JSON from fresh bootstrap owner state."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Sequence

from dharma_swarm.mission_control_binding import (
    AUTHORITY_ACTIONS,
    AUTHORITY_MANIFEST_SCHEMA_VERSION,
    READ_ONLY_EFFECT_MODE,
    CampaignAuthorityManifest,
    CampaignGoalAuthority,
    authority_manifest_digest,
    campaign_workspace_path,
)
from dharma_swarm.mission_control_binding_seed import validate_campaign_tasks
from dharma_swarm.mission_control_bootstrap import BootstrapResult
from dharma_swarm.mission_control_contract import MissionControlError, clean_identifier
from dharma_swarm.mission_control_observed_input import ObservedInputBinding
from dharma_swarm.mission_control_roster import CampaignAgentRoster
from dharma_swarm.models import AgentRole, ProviderType
from dharma_swarm.operator_core.execution_lease import parse_time
from dharma_swarm.task_board import TaskBoard


@dataclass(frozen=True, slots=True)
class CampaignGoalBindingPolicy:
    """The explicit release-owned goal-to-seat and file authority decision."""

    goal_id: str
    agent_name: str
    allowed_files: tuple[str, ...]


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MissionControlError(message)


def _exact_identifier(value: str, label: str) -> str:
    _need(isinstance(value, str), f"{label} must be a string")
    _need(clean_identifier(value, label) == value, f"{label} must be canonical")
    return value


def _allowed_files(value: tuple[str, ...], label: str) -> tuple[str, ...]:
    _need(type(value) is tuple and bool(value), f"{label} must be a nonempty tuple")
    _need(tuple(sorted(value)) == value, f"{label} must be sorted")
    _need(len(set(value)) == len(value), f"{label} contains duplicates")
    for path in value:
        _need(
            isinstance(path, str)
            and path
            and path == path.strip()
            and not path.startswith(("/", "~"))
            and "\\" not in path
            and not set(path) & set("*?[]{}()!|")
            and all(part not in {"", ".", ".."} for part in path.split("/")),
            f"{label} contains a noncanonical relative path",
        )
    return value


def deterministic_read_only_policies(
    bootstrap: BootstrapResult,
    roster: CampaignAgentRoster,
    *,
    verifier_seat_name: str,
) -> tuple[CampaignGoalBindingPolicy, ...]:
    """Assign every goal round-robin across pinned non-verifier roster seats."""
    verifier = [seat for seat in roster.seats if seat.name == verifier_seat_name]
    _need(
        len(verifier) == 1
        and verifier[0].role is AgentRole.VALIDATOR
        and verifier[0].provider is ProviderType.OLLAMA,
        "reserved verifier seat is absent, ambiguous, or foreign",
    )
    producers = tuple(seat for seat in roster.seats if seat.name != verifier_seat_name)
    _need(bool(producers), "campaign roster has no producer seats")
    _need(
        len(set(bootstrap.dependency_order)) == len(bootstrap.dependency_order),
        "bootstrap dependency order contains duplicates",
    )
    policies: list[CampaignGoalBindingPolicy] = []
    for index, goal_id in enumerate(bootstrap.dependency_order):
        workspace = campaign_workspace_path(bootstrap.mission_id, goal_id)
        policies.append(
            CampaignGoalBindingPolicy(
                goal_id=goal_id,
                agent_name=producers[index % len(producers)].name,
                allowed_files=(f"{workspace}/result.md",),
            )
        )
    return tuple(policies)


async def render_campaign_authority_manifest(
    bootstrap: BootstrapResult,
    board: TaskBoard,
    roster: CampaignAgentRoster,
    policies: Sequence[CampaignGoalBindingPolicy],
    observed_inputs: ObservedInputBinding,
    *,
    reserved_agent_names: tuple[str, ...],
    held_out_oracle_manifest_digest: str,
    operator_control_semantics_sha256: str,
    operator_control_authority_binding_sha256: str,
    deployment_authority_topology_sha256: str,
    deployment_authority_credential_clarification_sha256: str,
) -> bytes:
    """Render canonical JSON using task IDs and hashes read from TaskBoard.

    The helper performs no writes.  It fixes every effect mode to read-only;
    release policy must still explicitly assign one pinned seat and a sorted
    canonical allowed-file tuple to every bootstrapped goal.
    """
    _need(bootstrap.mission_id == roster.campaign_id, "bootstrap and roster conflict")
    _need(
        observed_inputs.campaign_id == bootstrap.mission_id
        and observed_inputs.mission_id == bootstrap.mission_id,
        "bootstrap and observed input binding conflict",
    )
    sha256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
    _need(sha256.fullmatch(held_out_oracle_manifest_digest) is not None,
          "held-out oracle manifest digest must be sha256")
    _need(sha256.fullmatch(operator_control_semantics_sha256) is not None,
          "operator control semantics digest must be sha256")
    _need(
        sha256.fullmatch(operator_control_authority_binding_sha256) is not None,
        "operator control authority binding digest must be sha256",
    )
    _need(
        sha256.fullmatch(deployment_authority_topology_sha256) is not None,
        "deployment authority topology digest must be sha256",
    )
    _need(
        sha256.fullmatch(
            deployment_authority_credential_clarification_sha256
        )
        is not None,
        "deployment authority credential clarification digest must be sha256",
    )
    end = parse_time(bootstrap.campaign_deadline)
    _need(
        end is not None
        and end.tzinfo is not None
        and end.isoformat() == bootstrap.campaign_deadline,
        "bootstrap campaign deadline is not canonical",
    )
    _need(roster.expires_at == end, "roster expiry must equal campaign deadline")
    task_ids = dict(bootstrap.goal_task_map)
    goal_digests = dict(bootstrap.goal_contract_digests)
    _need(
        len(task_ids) == len(bootstrap.goal_task_map)
        and len(goal_digests) == len(bootstrap.goal_contract_digests),
        "bootstrap result contains duplicate goal identities",
    )
    _need(
        set(task_ids) == set(goal_digests) == set(bootstrap.dependency_order),
        "bootstrap goal identities conflict",
    )
    observed_by_goal = observed_inputs.by_goal
    _need(set(observed_by_goal) == set(task_ids),
          "observed input binding must map every bootstrap goal")
    policy_by_goal = {policy.goal_id: policy for policy in policies}
    _need(
        len(policy_by_goal) == len(policies) and set(policy_by_goal) == set(task_ids),
        "binding policies must map every bootstrap goal exactly once",
    )
    seat_names = {seat.name for seat in roster.seats}
    _need(len(seat_names) == len(roster.seats), "campaign roster names are ambiguous")
    reserved = {
        _exact_identifier(name, "reserved agent name")
        for name in reserved_agent_names
    }
    _need(
        bool(reserved)
        and len(reserved) == len(reserved_agent_names)
        and reserved.issubset(seat_names),
        "reserved verifier seats must be unique roster members",
    )
    goals: list[CampaignGoalAuthority] = []
    for goal_id in sorted(task_ids):
        policy = policy_by_goal[goal_id]
        _exact_identifier(goal_id, "goal_id")
        agent_name = _exact_identifier(policy.agent_name, f"goal {goal_id} agent_name")
        _need(agent_name in seat_names, f"goal {goal_id} agent is outside the roster")
        _need(
            agent_name not in reserved,
            f"goal {goal_id} assigns a reserved verifier seat",
        )
        task = await board.get(task_ids[goal_id])
        _need(task is not None, f"goal {goal_id} task is missing")
        creation_hash = task.metadata.get("mission_task_creation_hash")
        _need(isinstance(creation_hash, str), f"goal {goal_id} creation hash is missing")
        max_attempts = task.metadata.get("attempt_ceiling")
        _need(
            isinstance(max_attempts, int)
            and not isinstance(max_attempts, bool)
            and max_attempts > 0,
            f"goal {goal_id} attempt ceiling is invalid",
        )
        goals.append(
            CampaignGoalAuthority(
                goal_id=goal_id,
                task_id=task_ids[goal_id],
                goal_contract_sha256=goal_digests[goal_id],
                task_creation_hash=creation_hash,
                effect_mode=READ_ONLY_EFFECT_MODE,
                agent_name=agent_name,
                workspace_path=campaign_workspace_path(bootstrap.mission_id, goal_id),
                allowed_files=_allowed_files(
                    policy.allowed_files, f"goal {goal_id} allowed_files"
                ),
                observed_input_ref=observed_by_goal[goal_id].ref,
                max_attempts=max_attempts,
            )
        )
    manifest = CampaignAuthorityManifest(
        campaign_id=bootstrap.mission_id,
        mission_id=bootstrap.mission_id,
        goal_contract_sha256=bootstrap.contract_digest,
        agent_roster_sha256=roster.manifest_sha256,
        campaign_end=end,
        campaign_end_text=bootstrap.campaign_deadline,
        manifest_digest="",
        observed_input_manifest_digest=observed_inputs.manifest_digest,
        held_out_oracle_manifest_digest=held_out_oracle_manifest_digest,
        operator_control_semantics_sha256=operator_control_semantics_sha256,
        operator_control_authority_binding_sha256=(
            operator_control_authority_binding_sha256
        ),
        deployment_authority_topology_sha256=deployment_authority_topology_sha256,
        deployment_authority_credential_clarification_sha256=(
            deployment_authority_credential_clarification_sha256
        ),
        goals=tuple(goals),
    )
    await validate_campaign_tasks(board, manifest)
    payload: dict[str, Any] = {
        "schema_version": AUTHORITY_MANIFEST_SCHEMA_VERSION,
        "campaign_id": manifest.campaign_id,
        "mission_id": manifest.mission_id,
        "goal_contract_sha256": manifest.goal_contract_sha256,
        "agent_roster_sha256": manifest.agent_roster_sha256,
        "campaign_end": manifest.campaign_end_text,
        "allowed_actions": list(AUTHORITY_ACTIONS),
        "max_usd": 0.0,
        "observed_input_manifest_digest": observed_inputs.manifest_digest,
        "held_out_oracle_manifest_digest": held_out_oracle_manifest_digest,
        "operator_control_semantics_sha256": operator_control_semantics_sha256,
        "operator_control_authority_binding_sha256": (
            operator_control_authority_binding_sha256
        ),
        "deployment_authority_topology_sha256": deployment_authority_topology_sha256,
        "deployment_authority_credential_clarification_sha256": (
            deployment_authority_credential_clarification_sha256
        ),
        "goals": {
            goal.goal_id: {
                "task_id": goal.task_id,
                "goal_contract_sha256": goal.goal_contract_sha256,
                "task_creation_hash": goal.task_creation_hash,
                "effect_mode": goal.effect_mode,
                "agent_name": goal.agent_name,
                "workspace_path": goal.workspace_path,
                "allowed_files": list(goal.allowed_files),
                "max_attempts": goal.max_attempts,
                "max_usd": 0.0,
                "observed_input_ref": goal.observed_input_ref.to_dict(),
            }
            for goal in goals
        },
    }
    payload["manifest_digest"] = authority_manifest_digest(payload)
    return (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


__all__ = [
    "CampaignGoalBindingPolicy",
    "deterministic_read_only_policies",
    "render_campaign_authority_manifest",
]
