"""Leader-serialized bounded rotation of exact pre-provider campaign attempts."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.mission_control import MissionControl
from dharma_swarm.mission_control_authority import (
    CAMPAIGN_AUTHORITY_METADATA_KEY,
    GovernedCampaignTaskDispatcher,
)
from dharma_swarm.mission_control_binding import (
    AUTHORITY_ACTIONS,
    AgentRoster,
    CampaignAuthorityManifest,
    CampaignGoalAuthority,
    _authority_envelope,
    _build_lease,
    _current_revocations,
    _governance_contract,
    _index_has_lease,
    _lease_lineage,
    _read_only_routing,
    _require_lease_lineage,
    _require_not_revoked,
    _resolve_principals,
    load_campaign_authority_manifest,
)
from dharma_swarm.mission_control_binding_seed import validate_campaign_tasks
from dharma_swarm.mission_control_contract import MissionControlError, stable_id, task_view, utc_now
from dharma_swarm.mission_control_dispatch import MissionDispatchRequest
from dharma_swarm.mission_control_execution_support import owner_execution_identity
from dharma_swarm.mission_control_task_attempts import validate_campaign_terminal_attempt
from dharma_swarm.mission_control_roster import CampaignAgentRoster
from dharma_swarm.models import AgentState, Task, TaskStatus
from dharma_swarm.operator_core.execution_lease import (
    ExecutionLeaseError,
    content_hash,
    lease_path,
    load_execution_lease,
    parse_time,
    validate_execution_lease,
    write_execution_lease,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.task_board import TaskBoard


@dataclass(frozen=True, slots=True)
class CampaignAttemptReconciliation:
    advanced_task_ids: tuple[str, ...]
    exhausted_task_ids: tuple[str, ...]
    blocked: tuple[str, ...]
    lease_writes: int


@dataclass(frozen=True, slots=True)
class _AttemptPlan:
    task: Task
    goal: CampaignGoalAuthority
    authority: dict[str, Any]
    expected_identity: dict[str, str]
    runtime_state: str
    next_lease: dict[str, Any] | None
    write_lease: bool
    next_authority: dict[str, Any] | None
    next_governance: dict[str, Any] | None
    next_routing: dict[str, Any] | None

    @property
    def exhausted(self) -> bool:
        return self.next_lease is None


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MissionControlError(message)


def _validate_lease(
    lease: dict[str, Any],
    *,
    manifest: CampaignAuthorityManifest,
    goal: CampaignGoalAuthority,
    task: Task,
    principal: AgentState,
    request: MissionDispatchRequest,
    revoked: set[str],
    observed_at: datetime,
) -> None:
    lease_id = str(lease.get("lease_id") or "")
    _require_lease_lineage(
        lease,
        _lease_lineage(manifest, goal, task, request, lease_id),
    )
    validation = validate_execution_lease(
        lease,
        now=observed_at,
        agent_uid=principal.id,
        task_id=task.id,
        requested_actions=AUTHORITY_ACTIONS,
        requested_paths=goal.allowed_files,
        revoked_lease_ids=revoked,
    )
    expires_at = parse_time(lease.get("expires_at"))
    budget = lease.get("budget")
    _need(
        validation.valid
        and lease.get("issued_to") == principal.id
        and lease.get("correlation_id") == request.request_id
        and expires_at == manifest.campaign_end
        and isinstance(budget, dict)
        and budget.get("max_usd") == 0.0
        and budget.get("max_model_calls") == 1
        and lease.get("content_hash") == content_hash(lease),
        "next attempt execution lease is not exact",
    )


class CampaignAttemptReconciler:
    """Advance only exact durable ``dispatch_indeterminate`` generations."""

    def __init__(
        self,
        *,
        manifest_path: Path | str,
        mission_control: MissionControl,
        board: TaskBoard,
        runtime_state: RuntimeStateStore,
        agent_pool: AgentRoster,
        campaign_roster: CampaignAgentRoster,
        lease_root: Path | str,
    ) -> None:
        self._manifest_path = Path(manifest_path)
        self._control = mission_control
        self._board = board
        self._runtime = runtime_state
        self._pool = agent_pool
        self._roster = campaign_roster
        self._lease_root = Path(lease_root).expanduser().absolute()
        self._lock = asyncio.Lock()

    async def reconcile(
        self,
        *,
        now: datetime | None = None,
    ) -> CampaignAttemptReconciliation:
        async with self._lock:
            return await self._reconcile(now=now)

    async def _reconcile(
        self,
        *,
        now: datetime | None,
    ) -> CampaignAttemptReconciliation:
        observed_at = now or utc_now()
        _need(
            isinstance(observed_at, datetime) and observed_at.tzinfo is not None,
            "attempt reconciler clock must be timezone-aware",
        )
        observed_at = observed_at.astimezone(timezone.utc)
        manifest = load_campaign_authority_manifest(self._manifest_path)
        _need(manifest.campaign_end > observed_at, "campaign authority has expired")
        _need(
            self._roster.campaign_id == manifest.campaign_id
            and self._roster.manifest_sha256 == manifest.agent_roster_sha256
            and self._roster.expires_at == manifest.campaign_end,
            "attempt reconciler roster is foreign",
        )
        _need(
            await self._control.get_mission(manifest.mission_id) is not None,
            "attempt reconciler mission was not found",
        )
        _need(
            self._lease_root.is_absolute() and not self._lease_root.is_symlink(),
            "attempt reconciler lease root is unsafe",
        )
        if self._lease_root.exists():
            _need(self._lease_root.is_dir(), "attempt reconciler lease root is not a directory")
        tasks = await validate_campaign_tasks(self._board, manifest)
        principals = await _resolve_principals(self._pool, manifest, self._roster)
        revoked = _current_revocations(self._lease_root)
        goals = {goal.goal_id: goal for goal in manifest.goals}

        # Read and validate the entire mission before the first runtime/lease/board write.
        plans: list[_AttemptPlan] = []
        blocked: list[str] = []
        for goal_id in sorted(tasks):
            task = tasks[goal_id]
            recovery = task.metadata.get("campaign_dispatch_recovery")
            if recovery is None:
                continue
            authority = task.metadata.get(CAMPAIGN_AUTHORITY_METADATA_KEY)
            if task.status not in {TaskStatus.CANCELLED, TaskStatus.FAILED}:
                blocked.append(f"{task.id}:recovery_marker_on_nonterminal_task")
                continue
            try:
                authority = validate_campaign_terminal_attempt(task)
                GovernedCampaignTaskDispatcher._require_typed_authority(
                    task_view(task, manifest.mission_id), authority
                )
                generation = authority["attempt_generation"]
                maximum = authority["max_attempts"]
                expected = owner_execution_identity(
                    manifest.mission_id,
                    task.id,
                    authority["dispatch_key"],
                    generation,
                )
                marker = task.metadata.get("mission_control_owner_execution")
                _need(
                    isinstance(marker, dict)
                    and all(marker.get(key) == value for key, value in expected.items()),
                    "owner attempt identity is foreign",
                )
                runtime_state = await self._runtime.inspect_campaign_dispatch_indeterminate(
                    mission_id=manifest.mission_id,
                    task_id=task.id,
                    run_id=expected["run_id"],
                    claim_id=expected["claim_id"],
                    agent_id=authority["claimed_principal"],
                    idempotency_key=expected["idempotency_key"],
                    attempt_generation=generation,
                )
                if runtime_state in {"effect_observed", "conflict"}:
                    blocked.append(f"{task.id}:runtime_{runtime_state}")
                    continue
                if generation + 1 >= maximum:
                    plans.append(
                        _AttemptPlan(
                            task, goals[goal_id], authority, expected, runtime_state,
                            None, False, None, None, None,
                        )
                    )
                    continue
                goal = goals[goal_id]
                principal = principals[goal.agent_name]
                next_generation = generation + 1
                dispatch_key = stable_id(
                    "sadhana_dispatch",
                    manifest.campaign_id,
                    goal.goal_id,
                    str(next_generation),
                )
                request = MissionDispatchRequest.new(
                    manifest.mission_id,
                    task.id,
                    dispatch_key=dispatch_key,
                    claimed_principal=principal.id,
                    attempt_generation=next_generation,
                )
                desired = _build_lease(manifest, goal, task, principal, request, observed_at)
                lease_id = str(desired["lease_id"])
                _require_not_revoked(self._lease_root, lease_id)
                path = lease_path(self._lease_root, lease_id)
                existing = load_execution_lease(self._lease_root, lease_id) if path.exists() else None
                lease = existing or desired
                _validate_lease(
                    lease,
                    manifest=manifest,
                    goal=goal,
                    task=task,
                    principal=principal,
                    request=request,
                    revoked=revoked,
                    observed_at=observed_at,
                )
                plans.append(
                    _AttemptPlan(
                        task=task,
                        goal=goal,
                        authority=authority,
                        expected_identity=expected,
                        runtime_state=runtime_state,
                        next_lease=lease,
                        write_lease=existing is None
                        or not _index_has_lease(self._lease_root, lease_id),
                        next_authority=_authority_envelope(
                            manifest, goal, principal, request, lease
                        ),
                        next_governance=_governance_contract(
                            manifest, goal, next_generation
                        ),
                        next_routing=_read_only_routing(principal),
                    )
                )
            except (ExecutionLeaseError, OSError, ValueError, json.JSONDecodeError) as exc:
                blocked.append(f"{task.id}:{type(exc).__name__}:{exc}")
            except MissionControlError as exc:
                blocked.append(f"{task.id}:MissionControlError:{exc}")
        if blocked:
            return CampaignAttemptReconciliation((), (), tuple(blocked), 0)

        advanced: list[str] = []
        exhausted: list[str] = []
        lease_writes = 0
        for plan in plans:
            expected = plan.expected_identity
            state = await self._runtime.resolve_campaign_dispatch_indeterminate(
                mission_id=manifest.mission_id,
                task_id=plan.task.id,
                run_id=expected["run_id"],
                claim_id=expected["claim_id"],
                agent_id=plan.authority["claimed_principal"],
                idempotency_key=expected["idempotency_key"],
                attempt_generation=plan.authority["attempt_generation"],
            )
            _need(
                state in {"absent", "terminalized", "already_terminal"},
                f"goal {plan.goal.goal_id} runtime changed after validation",
            )
            if plan.exhausted:
                outcome = await self._board.advance_campaign_dispatch_attempt(
                    plan.task.id,
                    expected_status=plan.task.status,
                    expected_agent_id=plan.authority["claimed_principal"],
                    expected_metadata=dict(plan.task.metadata),
                    next_authority=plan.authority,
                    next_governance=plan.task.metadata["mission_control_governance"],
                    next_routing={},
                )
                _need(outcome == "exhausted", "exhausted attempt row changed")
                exhausted.append(plan.task.id)
                continue
            assert plan.next_lease is not None
            assert plan.next_authority is not None
            assert plan.next_governance is not None
            assert plan.next_routing is not None
            lease_id = str(plan.next_lease["lease_id"])
            if plan.write_lease:
                _require_not_revoked(self._lease_root, lease_id)
                written = write_execution_lease(plan.next_lease, self._lease_root)
                _need(
                    written == lease_path(self._lease_root, lease_id),
                    "next attempt lease writer returned foreign path",
                )
                lease_writes += 1
            _require_not_revoked(self._lease_root, lease_id)
            _need(
                load_execution_lease(self._lease_root, lease_id) == plan.next_lease,
                "next attempt lease readback conflicts",
            )
            outcome = await self._board.advance_campaign_dispatch_attempt(
                plan.task.id,
                expected_status=plan.task.status,
                expected_agent_id=plan.authority["claimed_principal"],
                expected_metadata=dict(plan.task.metadata),
                next_authority=plan.next_authority,
                next_governance=plan.next_governance,
                next_routing=plan.next_routing,
            )
            _need(outcome == "advanced", "campaign attempt row changed after validation")
            advanced.append(plan.task.id)
        return CampaignAttemptReconciliation(
            tuple(advanced), tuple(exhausted), (), lease_writes
        )


__all__ = ["CampaignAttemptReconciler", "CampaignAttemptReconciliation"]
