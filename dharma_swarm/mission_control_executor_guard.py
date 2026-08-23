"""Campaign-only executor selection and atomic reservation guards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from dharma_swarm.models import (
    AgentState,
    AgentStatus,
    Task,
    TaskDispatch,
    TaskStatus,
    TopologyType,
    _new_id,
)

_AUTHORITY_KEY = "mission_campaign_authority"
_BOOTSTRAP_SCHEMA = "dharma.sadhana.mission_bootstrap.v1"
_AUTHORITY_SCHEMA = "dharma.sadhana.campaign_task_authority.v4"
_AUTHORITY_FIELDS = frozenset(
    {
        "schema_version",
        "campaign_id",
        "mission_id",
        "goal_id",
        "portfolio_contract_sha256",
        "goal_contract_sha256",
        "manifest_digest",
        "observed_input_manifest_digest",
        "held_out_oracle_manifest_digest",
        "operator_control_semantics_sha256",
        "operator_control_authority_binding_sha256",
        "deployment_authority_topology_sha256",
        "deployment_authority_credential_clarification_sha256",
        "observed_input_ref",
        "agent_roster_sha256",
        "effect_mode",
        "campaign_end",
        "agent_name",
        "claimed_principal",
        "dispatch_key",
        "request_id",
        "workspace_path",
        "allowed_files",
        "max_usd",
        "authority_ref",
        "authority_digest",
        "attempt_generation",
        "max_attempts",
    }
)


def _exact_text(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and value
        and value == value.strip()
        and not any(char.isspace() for char in value)
    )


class OrchestratorAgentPool(Protocol):
    async def get_idle_agents(self) -> list[AgentState]: ...
    async def assign(self, agent_id: str, task_id: str) -> None: ...
    async def release(self, agent_id: str) -> None: ...
    async def get_result(self, agent_id: str) -> str | None: ...
    async def get(self, agent_id: str) -> Any: ...


class OrchestratorTaskBoard(Protocol):
    async def get_ready_tasks(self) -> list[Task]: ...
    async def update_task(self, task_id: str, **fields: Any) -> None: ...
    async def get(self, task_id: str) -> Task | None: ...


class ReservablePool(OrchestratorAgentPool, Protocol):
    async def get(self, agent_id: str) -> Any: ...

    async def reserve(
        self,
        agent_id: str,
        task_id: str,
        *,
        reservation_token: object | None = None,
    ) -> bool: ...

    async def release_reservation(
        self,
        agent_id: str,
        task_id: str,
        *,
        reservation_token: object | None = None,
    ) -> bool: ...


class CampaignBoard(OrchestratorTaskBoard, Protocol):
    async def compare_and_swap_campaign_status(
        self, expected: Task, **fields: Any
    ) -> Task | None: ...

    async def resolve_campaign_pre_effect_failure(
        self,
        task_id: str,
        *,
        expected_status: TaskStatus,
        expected_agent_id: str | None,
        expected_metadata: dict[str, Any],
        authenticated_principal: str,
        provider_task_scheduled: bool = False,
    ) -> str: ...


@dataclass(frozen=True)
class CampaignDispatchPlan:
    """Exact principal, generation, dispatch, and local reservation capability."""

    principal: str
    generation: int
    dispatch: TaskDispatch
    reservation_token: dict[str, Any]

    @property
    def reservation_key(self) -> tuple[str, str, int]:
        return (self.dispatch.task_id, self.principal, self.generation)


AssignDispatch = Callable[..., Awaitable[bool]]


def campaign_principal(task: Task | None) -> tuple[bool, str]:
    """Return marker presence separately from its exact nested principal."""
    if task is None or not isinstance(task.metadata, dict):
        return False, ""
    metadata = task.metadata
    bound = bool(
        _AUTHORITY_KEY in metadata
        or metadata.get("sadhana_bootstrap_schema") == _BOOTSTRAP_SCHEMA
    )
    authority = metadata.get(_AUTHORITY_KEY)
    principal = authority.get("claimed_principal") if isinstance(authority, dict) else ""
    routing_safe = bool(
        metadata.get("campaign_effect_mode") == "read_only"
        and metadata.get("requires_tooling") is False
        and metadata.get("allow_provider_routing") is False
        and type(metadata.get("provider_allowlist")) is list
        and len(metadata["provider_allowlist"]) == 1
        and metadata["provider_allowlist"][0] == metadata.get("preferred_provider")
        and _exact_text(metadata.get("preferred_provider"))
        and _exact_text(metadata.get("preferred_model"))
    )
    observed_safe = False
    if isinstance(authority, dict):
        try:
            from dharma_swarm.mission_control_observed_input import (
                render_bound_observed_input_prompt,
            )

            render_bound_observed_input_prompt(metadata)
            observed_safe = True
        except Exception:
            observed_safe = False
    typed = bool(
        isinstance(authority, dict)
        and set(authority) == _AUTHORITY_FIELDS
        and authority.get("schema_version") == _AUTHORITY_SCHEMA
        and authority.get("campaign_id") == authority.get("mission_id")
        and authority.get("campaign_id") == metadata.get("campaign_id")
        and authority.get("goal_id") == metadata.get("goal_id")
        and authority.get("portfolio_contract_sha256")
        == metadata.get("portfolio_contract_sha256")
        and authority.get("goal_contract_sha256")
        == metadata.get("goal_contract_sha256")
        and authority.get("effect_mode") == "read_only"
        and authority.get("max_usd") == 0
        and not isinstance(authority.get("max_usd"), bool)
        and type(authority.get("allowed_files")) is list
        and isinstance(authority.get("attempt_generation"), int)
        and not isinstance(authority.get("attempt_generation"), bool)
        and isinstance(authority.get("max_attempts"), int)
        and not isinstance(authority.get("max_attempts"), bool)
        and authority.get("max_attempts") == metadata.get("attempt_ceiling")
        and 0 <= authority["attempt_generation"] < authority["max_attempts"]
        and observed_safe
        and routing_safe
    )
    if not typed or not _exact_text(principal):
        principal = ""
    return bound, principal


def campaign_claim_id(task: Task | None, metadata: dict[str, Any]) -> str:
    """Reuse only a typed campaign generation's precommitted claim identity."""
    if campaign_principal(task)[0]:
        existing = metadata.get("claim_id")
        if _exact_text(existing):
            return existing
    return _new_id()


async def transition_campaign_running(
    board: CampaignBoard,
    expected: Task,
    dispatch: TaskDispatch,
    metadata: dict[str, Any],
) -> Task:
    return await transition_campaign_status(
        board,
        expected,
        new_status=TaskStatus.RUNNING,
        assigned_to=dispatch.agent_id,
        metadata=metadata,
    )


def exact_idle_principal(
    idle: list[AgentState],
    principal: str,
) -> AgentState | None:
    matches = [
        agent
        for agent in idle
        if agent.id == principal and agent.status is AgentStatus.IDLE
    ]
    return matches[0] if len(matches) == 1 else None


def plan_campaign_dispatch(
    task: Task,
    idle: list[AgentState],
    topology: TopologyType | Any,
    authenticated_principal: str,
    timeout_seconds: float,
) -> CampaignDispatchPlan | None:
    """Build a campaign dispatch only for the exact authenticated idle seat."""
    bound, principal = campaign_principal(task)
    if (
        not bound
        or topology is not TopologyType.PIPELINE
        or not principal
        or authenticated_principal != principal
    ):
        return None
    selected = exact_idle_principal(idle, principal)
    authority = task.metadata.get(_AUTHORITY_KEY, {})
    generation = authority.get("attempt_generation")
    if selected is None or not isinstance(generation, int) or isinstance(generation, bool):
        return None
    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id=selected.id,
        topology=topology,
        timeout_seconds=timeout_seconds,
        metadata={"attempt_generation": generation},
    )
    token = {
        "reservation_id": f"campaign_reservation_{_new_id()}",
        "attempt_generation": generation,
        "provider_task_scheduled": False,
    }
    return CampaignDispatchPlan(principal, generation, dispatch, token)


async def dispatch_exact_campaign(
    pool: ReservablePool,
    board: CampaignBoard,
    reservations: dict[tuple[str, str, int], dict[str, Any]],
    task: Task,
    topology: TopologyType | Any,
    authenticated_principal: str,
    timeout_seconds: float,
    assign_dispatch: AssignDispatch,
    effect_fence: Callable[[], Awaitable[None]] | None,
) -> list[TaskDispatch]:
    """Plan, run, and recover the exact campaign-only dispatch boundary."""
    plan = plan_campaign_dispatch(
        task,
        await pool.get_idle_agents(),
        topology,
        authenticated_principal,
        timeout_seconds,
    )
    if plan is None or effect_fence is None:
        return []
    try:
        assigned = await assign_dispatch(
            plan.dispatch,
            authenticated_principal_id=plan.principal,
            reservation_token=plan.reservation_token,
            campaign_effect_fence=effect_fence,
        )
    except BaseException:
        await recover_unstarted_campaign_dispatch(pool, board, reservations, plan)
        raise
    return [plan.dispatch] if assigned else []


async def reserve_and_assign_campaign(
    pool: ReservablePool,
    board: CampaignBoard,
    reservations: dict[tuple[str, str, int], dict[str, Any]],
    task: Task,
    dispatch: TaskDispatch,
    principal: str,
    reservation_token: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[Any | None, Task]:
    """Atomically reserve the principal then CAS the task to ASSIGNED."""
    reserved, runner = await reserve_campaign_execution(
        pool, task, dispatch, principal, reservation_token
    )
    if not reserved:
        return None, task
    generation = int(dispatch.metadata["attempt_generation"])
    reservations[(dispatch.task_id, principal, generation)] = reservation_token
    assigned = await transition_campaign_status(
        board,
        task,
        new_status=TaskStatus.ASSIGNED,
        assigned_to=dispatch.agent_id,
        metadata=metadata,
    )
    return runner, assigned


def mark_campaign_provider_scheduled(
    reservations: dict[tuple[str, str, int], dict[str, Any]],
    dispatch: TaskDispatch,
    principal: str,
    token: dict[str, Any],
) -> None:
    """Close the process-local recovery window after provider scheduling."""
    token["provider_task_scheduled"] = True
    key = (dispatch.task_id, principal, int(dispatch.metadata["attempt_generation"]))
    if reservations.get(key) is token:
        reservations.pop(key, None)


async def recover_campaign_dispatch_before_provider(
    pool: ReservablePool,
    board: CampaignBoard,
    reservations: dict[tuple[str, str, int], dict[str, Any]],
    dispatch: TaskDispatch,
    principal: str,
    reservation_token: dict[str, Any],
) -> bool:
    """Recover the exact live dispatch token before its provider boundary."""
    generation = int(dispatch.metadata["attempt_generation"])
    key = (dispatch.task_id, principal, generation)
    if reservations.get(key) is not reservation_token:
        return False
    reservations.pop(key, None)
    return await recover_campaign_reservation(
        pool,
        board,
        dispatch.task_id,
        principal,
        attempt_generation=generation,
        reservation_token=reservation_token,
        provider_task_scheduled=False,
    )


async def recover_unstarted_campaign_dispatch(
    pool: ReservablePool,
    board: CampaignBoard,
    reservations: dict[tuple[str, str, int], dict[str, Any]],
    plan: CampaignDispatchPlan,
) -> bool:
    """Recover only the locally owned reservation installed by this dispatch."""
    token = plan.reservation_token
    if reservations.get(plan.reservation_key) is not token:
        return False
    reservations.pop(plan.reservation_key, None)
    return await recover_campaign_reservation(
        pool,
        board,
        plan.dispatch.task_id,
        plan.principal,
        attempt_generation=plan.generation,
        reservation_token=token,
        provider_task_scheduled=bool(token["provider_task_scheduled"]),
    )


async def transition_campaign_status(
    board: CampaignBoard,
    expected: Task,
    *,
    new_status: TaskStatus,
    assigned_to: str,
    metadata: dict[str, Any],
) -> Task:
    """Perform an exact campaign board CAS or fail without fallback mutation."""
    updated = await board.compare_and_swap_campaign_status(
        expected,
        new_status=new_status,
        assigned_to=assigned_to,
        metadata=metadata,
    )
    if updated is None:
        raise RuntimeError(f"campaign task changed before {new_status.value.upper()} CAS")
    return updated


async def reserve_campaign_execution(
    pool: ReservablePool,
    task: Task | None,
    dispatch: TaskDispatch,
    authenticated_principal: str,
    reservation_token: object,
) -> tuple[bool, Any | None]:
    """Recheck read-only routing, then atomically reserve the exact runner."""
    if task is None or dispatch.agent_id != authenticated_principal:
        return False, None
    metadata = task.metadata if isinstance(task.metadata, dict) else {}
    authority = metadata.get(_AUTHORITY_KEY)
    runner = await pool.get(dispatch.agent_id)
    state = getattr(runner, "state", None)
    safe = bool(
        isinstance(authority, dict)
        and authority.get("claimed_principal") == authenticated_principal
        and authority.get("effect_mode") == "read_only"
        and metadata.get("campaign_effect_mode") == "read_only"
        and metadata.get("requires_tooling") is False
        and metadata.get("allow_provider_routing") is False
        and state is not None
        and metadata.get("provider_allowlist") == [state.provider]
        and metadata.get("preferred_provider") == state.provider
        and metadata.get("preferred_model") == state.model
    )
    if not safe or not await pool.reserve(
        dispatch.agent_id,
        dispatch.task_id,
        reservation_token=reservation_token,
    ):
        return False, None
    return True, runner


async def recover_campaign_reservation(
    pool: ReservablePool,
    board: CampaignBoard,
    task_id: str,
    principal: str,
    *,
    attempt_generation: int,
    reservation_token: object,
    provider_task_scheduled: bool = False,
) -> bool:
    """Resolve exact pre-provider board state, then release its reservation."""
    task = await board.get(task_id)
    bound, nested = campaign_principal(task)
    if not bound or nested != principal or task is None:
        return False
    metadata = task.metadata
    marker = metadata.get("mission_control_owner_execution")
    required = {
        "schema_version",
        "backend",
        "mission_id",
        "task_id",
        "dispatch_key",
        "run_id",
        "idempotency_key",
        "trace_id",
        "correlation_id",
        "claim_id",
        "attempt_generation",
    }
    authority = metadata.get(_AUTHORITY_KEY)
    valid_stamp = bool(
        isinstance(marker, dict)
        and set(marker) == required
        and marker.get("schema_version")
        == "dharma.mission_control.owner_execution.v2"
        and marker.get("backend") == "orchestrator"
        and marker.get("task_id") == task_id
        and isinstance(authority, dict)
        and marker.get("mission_id") == authority.get("mission_id")
        and marker.get("dispatch_key") == authority.get("dispatch_key")
        and marker.get("attempt_generation")
        == authority.get("attempt_generation")
        == attempt_generation
        and all(
            marker.get(key) == metadata.get(key)
            for key in (
                "run_id",
                "claim_id",
                "idempotency_key",
                "trace_id",
                "correlation_id",
            )
        )
    )
    if not valid_stamp:
        return False
    expected_agent = None if task.status is TaskStatus.PENDING else principal
    outcome = await board.resolve_campaign_pre_effect_failure(
        task_id,
        expected_status=task.status,
        expected_agent_id=expected_agent,
        expected_metadata=dict(metadata),
        authenticated_principal=principal,
        provider_task_scheduled=provider_task_scheduled,
    )
    if outcome not in {"pending", "indeterminate"}:
        return False
    return await pool.release_reservation(
        principal,
        task_id,
        reservation_token=reservation_token,
    )


__all__ = [
    "CampaignDispatchPlan",
    "OrchestratorAgentPool",
    "OrchestratorTaskBoard",
    "campaign_claim_id",
    "campaign_principal",
    "dispatch_exact_campaign",
    "exact_idle_principal",
    "mark_campaign_provider_scheduled",
    "plan_campaign_dispatch",
    "recover_campaign_reservation",
    "recover_campaign_dispatch_before_provider",
    "recover_unstarted_campaign_dispatch",
    "reserve_and_assign_campaign",
    "reserve_campaign_execution",
    "transition_campaign_status",
    "transition_campaign_running",
]
