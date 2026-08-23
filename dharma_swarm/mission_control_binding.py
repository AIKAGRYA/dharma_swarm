"""Bind one bootstrapped campaign to exact runtime principals and leases.

The bootstrap's ``dispatch_ready=false`` marker is immutable provenance: it
says the seed itself supplied no authority.  Current dispatch authority is the
separately typed ``mission_campaign_authority`` envelope plus its exact
file-backed execution lease.  TaskBoard metadata and lease files remain the
canonical owners; this module adds no registry or ledger.

The campaign writer serializes calls to :func:`bind_campaign_authority` in the
production CLI.  Writes are deliberately lease-first and metadata-second so a
restart can reconcile its own deterministic partial state.  This is not a
cross-process transaction or a fleet-wide exactly-once claim.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_authority import (
    CAMPAIGN_AUTHORITY_METADATA_KEY,
    CAMPAIGN_AUTHORITY_SCHEMA_VERSION,
    SADHANA_BOOTSTRAP_SCHEMA_VERSION,
    SADHANA_GOAL_CONTRACT_SCHEMA_VERSION,
    load_campaign_revocations_strict,
)
from dharma_swarm.mission_control_binding_seed import validate_campaign_tasks
from dharma_swarm.mission_control_contract import (
    SCHEMA_VERSION,
    MissionControlError,
    clean_identifier,
    stable_id,
    utc_now,
)
from dharma_swarm.mission_control_dispatch import (
    CAMPAIGN_LEASE_SCHEMA_VERSION,
    GOVERNANCE_METADATA_KEY,
    MissionDispatchRequest,
)
from dharma_swarm.mission_control_binding_manifest import (
    AUTHORITY_ACTIONS,
    AUTHORITY_MANIFEST_MAX_BYTES,
    AUTHORITY_MANIFEST_SCHEMA_VERSION,
    READ_ONLY_EFFECT_MODE,
    CampaignAuthorityManifest,
    CampaignGoalAuthority,
    authority_manifest_digest,
    campaign_workspace_path,
    load_campaign_authority_manifest,
)
from dharma_swarm.mission_control_observed_input import (
    OBSERVED_INPUT_METADATA_KEY,
    OBSERVED_INPUT_REF_KEY,
    BoundObservedInput,
    ObservedInputBinding,
    validate_observed_input_binding,
)
from dharma_swarm.mission_control_roster import CampaignAgentRoster
from dharma_swarm.models import AgentState, AgentStatus, Task
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.operator_core.execution_lease import (
    DEFAULT_FORBIDDEN_ACTIONS,
    ExecutionLeaseError,
    build_execution_lease,
    content_hash,
    lease_path,
    load_execution_lease,
    parse_time,
    safe_lease_id,
    validate_execution_lease,
    write_execution_lease,
)
from dharma_swarm.task_board import TaskBoard


CAMPAIGN_GOVERNANCE_SCHEMA_VERSION = "dharma.sadhana.campaign_governance.v4"
AUTHORITY_ISSUER = "sadhana-campaign-supervisor"
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
_LIVE_AGENT_STATUSES = frozenset(
    {AgentStatus.IDLE, AgentStatus.INACTIVE, AgentStatus.BUSY, AgentStatus.STARTING}
)


class AgentRoster(Protocol):
    async def list_agents(self) -> list[AgentState]: ...


@dataclass(frozen=True, slots=True)
class BoundCampaignTask:
    goal_id: str
    task_id: str
    agent_name: str
    principal_id: str
    dispatch_key: str
    request_id: str
    workspace_path: str
    authority_ref: str
    authority_digest: str
    attempt_generation: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class CampaignAuthorityBinding:
    campaign_id: str
    mission_id: str
    manifest_digest: str
    agent_roster_sha256: str
    campaign_end: str
    tasks: tuple[BoundCampaignTask, ...]
    lease_writes: int
    metadata_writes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "mission_id": self.mission_id,
            "manifest_digest": self.manifest_digest,
            "agent_roster_sha256": self.agent_roster_sha256,
            "campaign_end": self.campaign_end,
            "task_count": len(self.tasks),
            "lease_writes": self.lease_writes,
            "metadata_writes": self.metadata_writes,
            "tasks": [
                {
                    "goal_id": item.goal_id,
                    "task_id": item.task_id,
                    "agent_name": item.agent_name,
                    "principal_id": item.principal_id,
                    "dispatch_key": item.dispatch_key,
                    "request_id": item.request_id,
                    "workspace_path": item.workspace_path,
                    "authority_ref": item.authority_ref,
                    "authority_digest": item.authority_digest,
                    "attempt_generation": item.attempt_generation,
                    "max_attempts": item.max_attempts,
                }
                for item in self.tasks
            ],
        }


@dataclass(frozen=True, slots=True)
class _BindingPlan:
    task: Task
    goal: CampaignGoalAuthority
    principal: AgentState
    lease: dict[str, Any]
    metadata: dict[str, Any]
    write_lease: bool
    write_metadata: bool
    bound: BoundCampaignTask


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MissionControlError(message)


def _current_revocations(root: Path) -> set[str]:
    try:
        return load_campaign_revocations_strict(root)
    except (ExecutionLeaseError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise MissionControlError("execution lease revocations are malformed") from exc


def _require_not_revoked(root: Path, lease_id: str) -> None:
    _need(
        lease_id not in _current_revocations(root),
        "deterministic execution lease is revoked",
    )


def _exact_identifier(value: Any, label: str) -> str:
    _need(isinstance(value, str), f"{label} must be a string")
    cleaned = clean_identifier(value, label)
    _need(cleaned == value, f"{label} must be canonical")
    return cleaned


def _exact_sha256(value: Any, label: str) -> str:
    _need(isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None,
          f"{label} must be sha256")
    return value


def _zero_usd(value: Any, label: str) -> float:
    _need(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and float(value) == 0.0,
        f"{label} must be exactly zero",
    )
    return 0.0


def _positive_int(value: Any, label: str) -> int:
    _need(
        isinstance(value, int) and not isinstance(value, bool) and value > 0,
        f"{label} must be a positive integer",
    )
    return value


def _relative_path(value: Any, label: str) -> str:
    _need(isinstance(value, str) and value == value.strip() and value,
          f"{label} must be a nonempty canonical path")
    _need(
        not value.startswith(("/", "~"))
        and "\\" not in value
        and not set(value) & set("*?[]{}()!|")
        and ":" not in value.split("/", 1)[0]
        and all(part not in {"", ".", ".."} and not part.startswith("~")
                for part in value.split("/")),
        f"{label} must be a canonical relative path",
    )
    return value


def _allowed_files(value: Any, label: str) -> tuple[str, ...]:
    _need(type(value) is list and bool(value), f"{label} must be a nonempty list")
    paths = tuple(_relative_path(item, f"{label} item") for item in value)
    _need(len(set(paths)) == len(paths), f"{label} contains duplicates")
    _need(list(paths) == sorted(paths), f"{label} must be sorted")
    return paths


def _exact_observed_ref(value: Any, goal_id: str) -> dict[str, Any]:
    _need(type(value) is dict, f"goal {goal_id} observed input ref must be an object")
    expected = {
        "receipt_id",
        "receipt_sha256",
        "artifact_id",
        "artifact_record_sha256",
        "content_sha256",
    }
    _need(set(value) == expected, f"goal {goal_id} observed input ref fields conflict")
    return value


def _canonical_time(value: Any, label: str) -> tuple[str, datetime]:
    _need(isinstance(value, str) and value, f"{label} must be a timestamp")
    parsed = parse_time(value)
    _need(
        parsed is not None
        and parsed.tzinfo is not None
        and parsed.isoformat() == value,
        f"{label} must be a canonical timezone-aware ISO timestamp",
    )
    return value, parsed


def _governance_contract(
    manifest: CampaignAuthorityManifest,
    goal: CampaignGoalAuthority,
    attempt_generation: int,
) -> dict[str, Any]:
    return {
        "schema_version": CAMPAIGN_GOVERNANCE_SCHEMA_VERSION,
        "campaign_id": manifest.campaign_id,
        "mission_id": manifest.mission_id,
        "goal_id": goal.goal_id,
        "portfolio_contract_sha256": manifest.goal_contract_sha256,
        "goal_contract_sha256": goal.goal_contract_sha256,
        "manifest_digest": manifest.manifest_digest,
        "observed_input_manifest_digest": manifest.observed_input_manifest_digest,
        "held_out_oracle_manifest_digest": manifest.held_out_oracle_manifest_digest,
        "operator_control_semantics_sha256": manifest.operator_control_semantics_sha256,
        "operator_control_authority_binding_sha256": (
            manifest.operator_control_authority_binding_sha256
        ),
        "deployment_authority_topology_sha256": (
            manifest.deployment_authority_topology_sha256
        ),
        "deployment_authority_credential_clarification_sha256": (
            manifest.deployment_authority_credential_clarification_sha256
        ),
        OBSERVED_INPUT_REF_KEY: goal.observed_input_ref.to_dict(),
        "agent_roster_sha256": manifest.agent_roster_sha256,
        "effect_mode": goal.effect_mode,
        "campaign_end": manifest.campaign_end_text,
        "workspace_path": goal.workspace_path,
        "allowed_files": list(goal.allowed_files),
        "forbidden_files": [],
        "max_usd": 0.0,
        "attempt_generation": attempt_generation,
        "max_attempts": goal.max_attempts,
    }


def _authority_envelope(
    manifest: CampaignAuthorityManifest,
    goal: CampaignGoalAuthority,
    principal: AgentState,
    request: MissionDispatchRequest,
    lease: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": CAMPAIGN_AUTHORITY_SCHEMA_VERSION,
        "campaign_id": manifest.campaign_id,
        "mission_id": manifest.mission_id,
        "goal_id": goal.goal_id,
        "portfolio_contract_sha256": manifest.goal_contract_sha256,
        "goal_contract_sha256": goal.goal_contract_sha256,
        "manifest_digest": manifest.manifest_digest,
        "observed_input_manifest_digest": manifest.observed_input_manifest_digest,
        "held_out_oracle_manifest_digest": manifest.held_out_oracle_manifest_digest,
        "operator_control_semantics_sha256": manifest.operator_control_semantics_sha256,
        "operator_control_authority_binding_sha256": (
            manifest.operator_control_authority_binding_sha256
        ),
        "deployment_authority_topology_sha256": (
            manifest.deployment_authority_topology_sha256
        ),
        "deployment_authority_credential_clarification_sha256": (
            manifest.deployment_authority_credential_clarification_sha256
        ),
        OBSERVED_INPUT_REF_KEY: goal.observed_input_ref.to_dict(),
        "agent_roster_sha256": manifest.agent_roster_sha256,
        "effect_mode": goal.effect_mode,
        "campaign_end": manifest.campaign_end_text,
        "agent_name": goal.agent_name,
        "claimed_principal": principal.id,
        "dispatch_key": request.dispatch_key,
        "request_id": request.request_id,
        "workspace_path": goal.workspace_path,
        "allowed_files": list(goal.allowed_files),
        "max_usd": 0.0,
        "attempt_generation": request.attempt_generation,
        "max_attempts": goal.max_attempts,
        "authority_ref": lease["lease_id"],
        "authority_digest": lease["content_hash"],
    }


def _lease_lineage(
    manifest: CampaignAuthorityManifest,
    goal: CampaignGoalAuthority,
    task: Task,
    request: MissionDispatchRequest,
    lease_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": "dharma.execution_lease.v1",
        "lease_id": lease_id,
        "issuer": AUTHORITY_ISSUER,
        "task_id": task.id,
        "correlation_id": request.request_id,
        "custody_grade": "Q1",
        "allowed_actions": list(AUTHORITY_ACTIONS),
        "allowed_paths": list(goal.allowed_files),
        "forbidden_actions": list(DEFAULT_FORBIDDEN_ACTIONS),
        "verifier_policy": {
            "worker_cannot_self_verify": True,
            "required_verifiers": ["deterministic"],
        },
        "authority": "read_only_until_execution_lease",
        "campaign_authority_schema": CAMPAIGN_LEASE_SCHEMA_VERSION,
        "campaign_id": manifest.campaign_id,
        "mission_id": manifest.mission_id,
        "goal_id": goal.goal_id,
        "portfolio_contract_sha256": manifest.goal_contract_sha256,
        "goal_contract_sha256": goal.goal_contract_sha256,
        "manifest_digest": manifest.manifest_digest,
        "observed_input_manifest_digest": manifest.observed_input_manifest_digest,
        "held_out_oracle_manifest_digest": manifest.held_out_oracle_manifest_digest,
        "operator_control_semantics_sha256": manifest.operator_control_semantics_sha256,
        "operator_control_authority_binding_sha256": (
            manifest.operator_control_authority_binding_sha256
        ),
        "deployment_authority_topology_sha256": (
            manifest.deployment_authority_topology_sha256
        ),
        "deployment_authority_credential_clarification_sha256": (
            manifest.deployment_authority_credential_clarification_sha256
        ),
        OBSERVED_INPUT_REF_KEY: goal.observed_input_ref.to_dict(),
        "agent_roster_sha256": manifest.agent_roster_sha256,
        "effect_mode": goal.effect_mode,
        "campaign_end": manifest.campaign_end_text,
        "agent_name": goal.agent_name,
        "workspace_path": goal.workspace_path,
        "attempt_generation": request.attempt_generation,
        "max_attempts": goal.max_attempts,
    }


def _build_lease(
    manifest: CampaignAuthorityManifest,
    goal: CampaignGoalAuthority,
    task: Task,
    principal: AgentState,
    request: MissionDispatchRequest,
    now: datetime,
) -> dict[str, Any]:
    remaining = max(1, math.ceil((manifest.campaign_end - now).total_seconds()))
    attempts = task.metadata.get("attempt_ceiling")
    _need(
        isinstance(attempts, int) and not isinstance(attempts, bool) and attempts > 0,
        f"goal {goal.goal_id} attempt ceiling is invalid",
    )
    _need(attempts == goal.max_attempts, f"goal {goal.goal_id} max attempts conflicts")
    lease_id = stable_id(
        "sadhana_lease",
        manifest.campaign_id,
        task.id,
        request.dispatch_key,
        str(request.attempt_generation),
    )
    lease = build_execution_lease(
        issued_to=principal.id,
        issuer=AUTHORITY_ISSUER,
        task_id=task.id,
        correlation_id=request.request_id,
        custody_grade="Q1",
        allowed_actions=AUTHORITY_ACTIONS,
        allowed_paths=goal.allowed_files,
        forbidden_actions=DEFAULT_FORBIDDEN_ACTIONS,
        max_seconds=remaining,
        max_model_calls=1,
        max_usd=0.0,
        issued_at=now,
        expires_at=manifest.campaign_end,
        lease_id=lease_id,
    )
    lease.update(
        _lease_lineage(manifest, goal, task, request, lease_id)
    )
    lease["content_hash"] = content_hash(lease)
    return lease


def _require_lease_lineage(
    lease: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> None:
    for key, value in expected.items():
        _need(lease.get(key) == value, f"existing execution lease has foreign {key}")
    budget = lease.get("budget")
    _need(isinstance(budget, Mapping), "existing execution lease budget is invalid")
    _need(
        budget.get("max_model_calls") == 1
        and not isinstance(budget.get("max_usd"), bool)
        and budget.get("max_usd") == 0.0,
        "existing execution lease budget conflicts",
    )
    _need(
        isinstance(budget.get("max_seconds"), int)
        and not isinstance(budget.get("max_seconds"), bool)
        and budget["max_seconds"] > 0,
        "existing execution lease duration budget is invalid",
    )
    _need(lease.get("content_hash") == content_hash(lease),
          "existing execution lease content hash conflicts")


def _index_has_lease(root: Path, lease_id: str) -> bool:
    index = root / "index.jsonl"
    if not index.exists():
        return False
    _need(not index.is_symlink(), "execution lease index must not be a symlink")
    found = False
    try:
        lines = index.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise MissionControlError("execution lease index could not be read") from exc
    for line_number, line in enumerate(lines, start=1):
        _need(bool(line.strip()), f"execution lease index row {line_number} is empty")
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MissionControlError(
                f"execution lease index row {line_number} is invalid"
            ) from exc
        _need(
            isinstance(payload, dict) and payload.get("event") == "lease_written",
            f"execution lease index row {line_number} has a foreign shape",
        )
        if payload.get("lease_id") == lease_id:
            found = True
    return found


def _require_existing_authority_lineage(
    authority: Mapping[str, Any],
    manifest: CampaignAuthorityManifest,
    goal: CampaignGoalAuthority,
    request: MissionDispatchRequest,
    lease_id: str,
) -> None:
    expected = {
        "schema_version": CAMPAIGN_AUTHORITY_SCHEMA_VERSION,
        "campaign_id": manifest.campaign_id,
        "mission_id": manifest.mission_id,
        "goal_id": goal.goal_id,
        "portfolio_contract_sha256": manifest.goal_contract_sha256,
        "goal_contract_sha256": goal.goal_contract_sha256,
        "manifest_digest": manifest.manifest_digest,
        "observed_input_manifest_digest": manifest.observed_input_manifest_digest,
        "held_out_oracle_manifest_digest": manifest.held_out_oracle_manifest_digest,
        "operator_control_semantics_sha256": manifest.operator_control_semantics_sha256,
        "operator_control_authority_binding_sha256": (
            manifest.operator_control_authority_binding_sha256
        ),
        "deployment_authority_topology_sha256": (
            manifest.deployment_authority_topology_sha256
        ),
        "deployment_authority_credential_clarification_sha256": (
            manifest.deployment_authority_credential_clarification_sha256
        ),
        OBSERVED_INPUT_REF_KEY: goal.observed_input_ref.to_dict(),
        "agent_roster_sha256": manifest.agent_roster_sha256,
        "effect_mode": goal.effect_mode,
        "campaign_end": manifest.campaign_end_text,
        "agent_name": goal.agent_name,
        "dispatch_key": request.dispatch_key,
        "request_id": request.request_id,
        "workspace_path": goal.workspace_path,
        "allowed_files": list(goal.allowed_files),
        "max_usd": 0.0,
        "attempt_generation": request.attempt_generation,
        "max_attempts": goal.max_attempts,
        "authority_ref": lease_id,
    }
    for key, value in expected.items():
        _need(authority.get(key) == value, f"existing task authority has foreign {key}")
    _exact_identifier(authority.get("claimed_principal"), "existing claimed_principal")
    _exact_sha256(authority.get("authority_digest"), "existing authority_digest")
    _need(set(authority) == {*expected, "claimed_principal", "authority_digest"},
          "existing task authority has foreign fields")


def _read_only_routing(principal: AgentState) -> dict[str, Any]:
    return {
        "campaign_effect_mode": READ_ONLY_EFFECT_MODE,
        "requires_tooling": False,
        "allow_provider_routing": False,
        "provider_allowlist": [principal.provider],
        "preferred_provider": principal.provider,
        "preferred_model": principal.model,
    }


async def _resolve_principals(
    roster: AgentRoster,
    manifest: CampaignAuthorityManifest,
    campaign_roster: CampaignAgentRoster,
) -> dict[str, AgentState]:
    agents = await roster.list_agents()
    _need(type(agents) is list, "agent roster must return a list")
    live: list[AgentState] = []
    for agent in agents:
        _need(type(agent) is AgentState, "agent roster returned a foreign state type")
        if agent.status in _LIVE_AGENT_STATUSES:
            _exact_identifier(agent.id, "AgentState.id")
            _exact_identifier(agent.name, "AgentState.name")
            live.append(agent)
    seats = {seat.name: seat for seat in campaign_roster.seats}
    _need(
        len(seats) == len(campaign_roster.seats),
        "campaign roster contains duplicate stable names",
    )
    required_names = {goal.agent_name for goal in manifest.goals}
    _need(
        required_names <= set(seats),
        "authority manifest names a principal outside the pinned campaign roster",
    )
    resolved: dict[str, AgentState] = {}
    for name in sorted(required_names):
        matches = [agent for agent in live if agent.name == name]
        _need(len(matches) == 1, f"required agent name {name!r} is not exactly one live state")
        principal = matches[0]
        seat = seats[name]
        _need(
            principal.role is seat.role
            and principal.provider == seat.provider.value
            and principal.model == seat.model,
            f"required agent name {name!r} drifted from the pinned campaign roster",
        )
        resolved[name] = principal
    ids_to_names: dict[str, set[str]] = {}
    for name, agent in resolved.items():
        ids_to_names.setdefault(agent.id, set()).add(name)
    _need(all(len(names) == 1 for names in ids_to_names.values()),
          "one live AgentState ID carries multiple required names")
    return resolved


def _plan_task(
    manifest: CampaignAuthorityManifest,
    goal: CampaignGoalAuthority,
    task: Task,
    principal: AgentState,
    root: Path,
    revoked_lease_ids: set[str],
    now: datetime,
    observed: BoundObservedInput,
) -> _BindingPlan:
    _need(
        observed.goal_id == goal.goal_id
        and observed.task_id == task.id
        and observed.ref == goal.observed_input_ref,
        f"goal {goal.goal_id} observed input binding conflicts",
    )
    existing_prompt = task.metadata.get(OBSERVED_INPUT_METADATA_KEY)
    if existing_prompt is not None:
        _need(existing_prompt == observed.prompt,
              f"goal {goal.goal_id} existing observed prompt is foreign")
    raw_authority = task.metadata.get(CAMPAIGN_AUTHORITY_METADATA_KEY)
    generation = 0
    if raw_authority is not None:
        _need(type(raw_authority) is dict, "existing task authority has an invalid shape")
        generation = raw_authority.get("attempt_generation")
        _need(
            isinstance(generation, int)
            and not isinstance(generation, bool)
            and 0 <= generation < goal.max_attempts,
            "existing task attempt generation is invalid",
        )
    dispatch_key = stable_id(
        "sadhana_dispatch",
        manifest.campaign_id,
        goal.goal_id,
        str(generation),
    )
    request = MissionDispatchRequest.new(
        manifest.mission_id,
        task.id,
        dispatch_key=dispatch_key,
        claimed_principal=principal.id,
        attempt_generation=generation,
    )
    desired = _build_lease(manifest, goal, task, principal, request, now)
    lease_id = str(desired["lease_id"])
    _need(safe_lease_id(lease_id) == lease_id, "deterministic lease identity is unsafe")
    _need(lease_id not in revoked_lease_ids, "deterministic execution lease is revoked")
    expected_lineage = _lease_lineage(
        manifest, goal, task, request, lease_id
    )
    path = lease_path(root, lease_id)
    _need(not path.is_symlink(), "execution lease path must not be a symlink")
    existing: dict[str, Any] | None = None
    if path.exists():
        try:
            existing = load_execution_lease(root, lease_id)
        except (ExecutionLeaseError, OSError, json.JSONDecodeError) as exc:
            raise MissionControlError("existing execution lease is malformed") from exc
        _require_lease_lineage(existing, expected_lineage)
        _need(existing.get("expires_at") == manifest.campaign_end_text,
              "existing execution lease expiry conflicts with campaign end")
        issued = parse_time(existing.get("issued_at"))
        _need(issued is not None and issued <= now, "existing execution lease is not yet valid")
    authority: Mapping[str, Any] | None = None
    if raw_authority is not None:
        _need(type(raw_authority) is dict, "existing task authority has an invalid shape")
        authority = raw_authority
        _require_existing_authority_lineage(
            authority, manifest, goal, request, lease_id
        )
        if existing is not None and authority.get("claimed_principal") == existing.get("issued_to"):
            _need(
                authority.get("authority_digest") == existing.get("content_hash"),
                "existing task authority digest conflicts with its lease",
            )
    governance = _governance_contract(manifest, goal, generation)
    raw_governance = task.metadata.get(GOVERNANCE_METADATA_KEY)
    if raw_governance is not None:
        _need(raw_governance == governance, "existing task governance is foreign")
    routing = _read_only_routing(principal)
    for key, value in routing.items():
        if key in task.metadata:
            _need(
                task.metadata[key] == value,
                f"existing task routing has foreign {key}",
            )
    if "mission_task_id" in task.metadata:
        _need(
            task.metadata["mission_task_id"] == task.id,
            "existing task identity coordinate is foreign",
        )

    lease = desired if existing is None else existing
    write_lease = existing is None
    if existing is not None:
        validation = validate_execution_lease(
            existing,
            now=now,
            agent_uid=principal.id,
            task_id=task.id,
            requested_actions=AUTHORITY_ACTIONS,
            requested_paths=goal.allowed_files,
        )
        if not validation.valid:
            old_principal = _exact_identifier(existing.get("issued_to"), "lease issued_to")
            _need(
                old_principal != principal.id
                and all("does not match agent" in error for error in validation.errors),
                "existing execution lease is invalid: " + "; ".join(validation.errors),
            )
            lease = desired
            write_lease = True
        elif existing.get("issued_to") != principal.id:
            lease = desired
            write_lease = True
        elif not _index_has_lease(root, lease_id):
            write_lease = True
    assert lease is not None
    expected_authority = _authority_envelope(
        manifest, goal, principal, request, lease
    )
    metadata = {
        **task.metadata,
        **routing,
        "mission_task_id": task.id,
        GOVERNANCE_METADATA_KEY: governance,
        CAMPAIGN_AUTHORITY_METADATA_KEY: expected_authority,
        OBSERVED_INPUT_METADATA_KEY: observed.prompt,
    }
    bound = BoundCampaignTask(
        goal_id=goal.goal_id,
        task_id=task.id,
        agent_name=goal.agent_name,
        principal_id=principal.id,
        dispatch_key=dispatch_key,
        request_id=request.request_id,
        workspace_path=goal.workspace_path,
        authority_ref=str(lease["lease_id"]),
        authority_digest=str(lease["content_hash"]),
        attempt_generation=generation,
        max_attempts=goal.max_attempts,
    )
    return _BindingPlan(
        task=task,
        goal=goal,
        principal=principal,
        lease=dict(lease),
        metadata=metadata,
        write_lease=write_lease,
        write_metadata=metadata != task.metadata,
        bound=bound,
    )


async def bind_campaign_authority(
    *,
    manifest_path: Path | str,
    mission_control: MissionControl,
    board: TaskBoard,
    agent_pool: AgentRoster,
    campaign_roster: CampaignAgentRoster,
    observed_inputs: ObservedInputBinding,
    runtime_state: RuntimeStateStore,
    lease_root: Path | str,
    reserved_agent_names: tuple[str, ...] = (),
    now: datetime | None = None,
) -> CampaignAuthorityBinding:
    """Validate the complete campaign, then reconcile exact leases and metadata."""
    observed_at = now or utc_now()
    _need(
        isinstance(observed_at, datetime) and observed_at.tzinfo is not None,
        "binding clock must be timezone-aware",
    )
    observed_at = observed_at.astimezone(timezone.utc)
    manifest = load_campaign_authority_manifest(manifest_path)
    reserved = {_exact_identifier(item, "reserved agent name") for item in reserved_agent_names}
    _need(
        len(reserved) == len(reserved_agent_names)
        and not reserved.intersection(goal.agent_name for goal in manifest.goals),
        "authority manifest assigns work to a reserved verifier seat",
    )
    _need(
        observed_inputs.campaign_id == manifest.campaign_id
        and observed_inputs.mission_id == manifest.mission_id
        and observed_inputs.manifest_digest == manifest.observed_input_manifest_digest,
        "authority manifest conflicts with observed input binding",
    )
    observed_by_goal = observed_inputs.by_goal
    _need(
        set(observed_by_goal) == {goal.goal_id for goal in manifest.goals},
        "observed input binding must map every authority goal exactly",
    )
    await validate_observed_input_binding(observed_inputs, board, runtime_state)
    _need(manifest.campaign_end > observed_at, "campaign authority has expired")
    _need(
        all(goal.effect_mode == READ_ONLY_EFFECT_MODE for goal in manifest.goals),
        "write-capable campaign dispatch requires an enforced workspace sandbox",
    )
    _need(
        campaign_roster.campaign_id == manifest.campaign_id
        and campaign_roster.manifest_sha256 == manifest.agent_roster_sha256,
        "authority manifest conflicts with the pinned campaign roster",
    )
    _need(
        campaign_roster.expires_at == manifest.campaign_end,
        "campaign roster expiry conflicts with the exact campaign end",
    )
    mission = await mission_control.get_mission(manifest.mission_id)
    _need(mission is not None, "authority manifest mission was not found")
    metadata = mission.metadata
    expected_mission = {
        "schema_version": SCHEMA_VERSION,
        "mission_id": manifest.mission_id,
        "sadhana_bootstrap_schema": SADHANA_BOOTSTRAP_SCHEMA_VERSION,
        "goal_contract_schema": SADHANA_GOAL_CONTRACT_SCHEMA_VERSION,
        "goal_contract_sha256": manifest.goal_contract_sha256,
        "campaign_id": manifest.campaign_id,
        "campaign_deadline": manifest.campaign_end_text,
        "goal_count": len(manifest.goals),
        "dispatch_ready": False,
        "dispatch_blocker": "authority_unbound",
    }
    for key, value in expected_mission.items():
        _need(metadata.get(key) == value, f"campaign mission {key} conflicts")

    tasks = await validate_campaign_tasks(board, manifest)
    principals = await _resolve_principals(agent_pool, manifest, campaign_roster)
    root = Path(lease_root).expanduser().absolute()
    _need(not root.is_symlink(), "execution lease root must not be a symlink")
    if root.exists():
        _need(root.is_dir(), "execution lease root must be a directory")
    revoked_lease_ids = _current_revocations(root)

    # Validate every task, roster seat, lease, index, and partial before write 1.
    plans = tuple(
        _plan_task(
            manifest,
            goal,
            tasks[goal.goal_id],
            principals[goal.agent_name],
            root,
            revoked_lease_ids,
            observed_at,
            observed_by_goal[goal.goal_id],
        )
        for goal in manifest.goals
    )

    lease_writes = 0
    metadata_writes = 0
    for plan in plans:
        if plan.write_lease:
            _require_not_revoked(root, plan.bound.authority_ref)
            try:
                written = write_execution_lease(plan.lease, root)
            except (ExecutionLeaseError, OSError, ValueError) as exc:
                raise MissionControlError(
                    f"goal {plan.goal.goal_id} execution lease write failed"
                ) from exc
            _need(written == lease_path(root, plan.bound.authority_ref),
                  "execution lease writer returned a foreign path")
            lease_writes += 1
        if plan.write_metadata:
            _require_not_revoked(root, plan.bound.authority_ref)
            updated = await board.compare_and_swap_campaign_metadata(
                plan.task,
                metadata=plan.metadata,
            )
            _need(updated is not None,
                  f"goal {plan.goal.goal_id} changed before authority metadata CAS")
            metadata_writes += 1
        _require_not_revoked(root, plan.bound.authority_ref)
        current = await board.get(plan.task.id)
        _need(current is not None and current.metadata == plan.metadata,
              f"goal {plan.goal.goal_id} metadata readback conflicts")
        exact = load_execution_lease(root, plan.bound.authority_ref)
        _need(exact == plan.lease, f"goal {plan.goal.goal_id} lease readback conflicts")

    return CampaignAuthorityBinding(
        campaign_id=manifest.campaign_id,
        mission_id=manifest.mission_id,
        manifest_digest=manifest.manifest_digest,
        agent_roster_sha256=manifest.agent_roster_sha256,
        campaign_end=manifest.campaign_end_text,
        tasks=tuple(plan.bound for plan in plans),
        lease_writes=lease_writes,
        metadata_writes=metadata_writes,
    )


__all__ = [
    "AUTHORITY_ACTIONS",
    "AUTHORITY_MANIFEST_SCHEMA_VERSION",
    "AUTHORITY_MANIFEST_MAX_BYTES",
    "CAMPAIGN_GOVERNANCE_SCHEMA_VERSION",
    "BoundCampaignTask",
    "CampaignAuthorityBinding",
    "CampaignAuthorityManifest",
    "CampaignGoalAuthority",
    "authority_manifest_digest",
    "bind_campaign_authority",
    "campaign_workspace_path",
    "load_campaign_authority_manifest",
]
