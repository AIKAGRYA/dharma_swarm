"""Thin HOLON orchestration wiring over the existing swarm orchestrator.

This module does not create a second orchestrator, task store, model router, or
receipt spine. It loads a HOLON identity, builds a structured subtask plan,
dispatches that plan through ``Orchestrator.fan_out()``, aggregates with
``fan_in()``, and delegates final synthesis to an injected HOLON-owned
synthesizer when the caller has a live-model lease.
"""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from dharma_swarm.holon_bridge import RunningHolon, load_holon
from dharma_swarm.intent_router import DecomposedTask, IntentRouter
from dharma_swarm.models import AgentState, Task, TaskPriority
from dharma_swarm.orchestrator import Orchestrator

ORCHESTRATION_SCHEMA_VERSION = "dharma.holon_orchestration.v1"
HOLON_NO_PROVIDER_TRUTH_SOURCE = "holon_orchestrate.no_provider_execution"

HolonDecomposer = Callable[[str], DecomposedTask]
HolonSynthesizer = Callable[
    [RunningHolon, str, list[dict[str, Any]], str],
    str | Awaitable[str],
]


class HolonOrchestrationError(RuntimeError):
    """Raised when a HOLON orchestration proof cannot be honestly attempted."""


@dataclass(frozen=True)
class HolonOrchestrationConfig:
    name: str
    mission: str
    min_subtasks: int = 2
    min_model_tiers: int = 2
    max_subtasks: int = 4
    require_model_tier_diversity: bool = True
    execution_mode: str = "dispatch_aggregation_probe"
    execution_timeout_seconds: float = 30.0


def _coerce_subtask_plan(decomposition: DecomposedTask) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for index, intent in enumerate(decomposition.sub_tasks, start=1):
        plan.append(
            {
                "index": index,
                "task": intent.task,
                "primary_skill": intent.primary_skill,
                "confidence": intent.confidence,
                "complexity": intent.complexity,
                "risk_level": intent.risk_level,
                "tags": list(intent.tags),
            }
        )
    return plan


def _default_decompose(mission: str) -> DecomposedTask:
    return IntentRouter().decompose(mission)


async def _maybe_await(value: str | Awaitable[str]) -> str:
    if inspect.isawaitable(value):
        return str(await value)
    return str(value)


async def _default_synthesizer(
    holon: RunningHolon,
    mission: str,
    subtask_records: list[dict[str, Any]],
    aggregate: str,
) -> str:
    lines = [
        f"[deterministic synthesis; no live {holon.model} call claimed]",
        f"mission: {mission}",
        f"subtasks: {len(subtask_records)}",
        "aggregate:",
        aggregate.strip(),
    ]
    return "\n".join(line for line in lines if line)


async def _idle_agents(orchestrator: Orchestrator) -> list[AgentState]:
    pool = getattr(orchestrator, "_pool", None)
    if pool is None:
        return []
    get_idle = getattr(pool, "get_idle_agents", None)
    if not callable(get_idle):
        return []
    agents = get_idle()
    if inspect.isawaitable(agents):
        agents = await agents
    return list(agents or [])


def _model_tier(agent: AgentState) -> str:
    provider = str(getattr(agent, "provider", "") or "").strip()
    model = str(getattr(agent, "model", "") or "").strip()
    if provider or model:
        return f"{provider or 'unknown'}:{model or 'unknown'}"
    return f"role:{agent.role.value}"


def _no_provider_runtime_truth(*, reason: str) -> dict[str, Any]:
    return {
        "provider_execution": False,
        "provider_model_applicability": "not_applicable",
        "provider_model_truth_source": HOLON_NO_PROVIDER_TRUTH_SOURCE,
        "no_provider_model_reason": reason,
    }


async def _register_parent_task(
    orchestrator: Orchestrator,
    *,
    title: str,
    description: str,
    metadata: dict[str, Any],
) -> Task:
    board = getattr(orchestrator, "_board", None)
    create = getattr(board, "create", None)
    if callable(create):
        created = create(
            title=title,
            description=description,
            priority=TaskPriority.NORMAL,
            created_by="holon_orchestrate",
            metadata=metadata,
        )
        if inspect.isawaitable(created):
            created = await created
        if isinstance(created, Task):
            return created
    parent = Task(
        title=title,
        description=description,
        priority=TaskPriority.NORMAL,
        created_by="holon_orchestrate",
        metadata=metadata,
    )
    tasks = getattr(board, "tasks", None)
    if isinstance(tasks, list):
        tasks.append(parent)
    return parent


async def _register_subtask(
    orchestrator: Orchestrator,
    *,
    parent_task: Task,
    subtask: dict[str, Any],
    agent: AgentState,
) -> Task:
    title = f"HOLON subtask {subtask['index']}: {subtask['primary_skill']}"
    metadata = {
        "holon_orchestration": True,
        "holon_parent_task_id": parent_task.id,
        "holon_subtask": dict(subtask),
        "director_preferred_agents": [agent.name],
        "coordination_preferred_roles": [agent.role.value],
        **_no_provider_runtime_truth(
            reason="holon_bounded_subtask_execution_no_live_model_call_claimed"
        ),
    }
    board = getattr(orchestrator, "_board", None)
    create = getattr(board, "create", None)
    if callable(create):
        created = create(
            title=title,
            description=str(subtask["task"]),
            priority=TaskPriority.NORMAL,
            created_by="holon_orchestrate",
            metadata=metadata,
        )
        if inspect.isawaitable(created):
            created = await created
        if isinstance(created, Task):
            return created
    task = Task(
        title=title,
        description=str(subtask["task"]),
        priority=TaskPriority.NORMAL,
        created_by="holon_orchestrate",
        metadata=metadata,
    )
    tasks = getattr(board, "tasks", None)
    if isinstance(tasks, list):
        tasks.append(task)
    return task


async def _dispatch_specific_agent(
    orchestrator: Orchestrator,
    *,
    task: Task,
    agent: AgentState,
    parent_task: Task,
) -> Any:
    from dharma_swarm.models import TaskDispatch, TopologyType

    dispatch = TaskDispatch(
        task_id=task.id,
        agent_id=agent.id,
        topology=TopologyType.FAN_OUT,
        timeout_seconds=getattr(orchestrator, "_default_timeout_seconds", 30.0),
        metadata={
            "sub_task_id": task.id,
            "parent_task": parent_task.id,
            "holon_orchestration": True,
            "holon_execution_mode": "bounded_subtask_execution",
            **_no_provider_runtime_truth(
                reason="holon_bounded_subtask_execution_no_live_model_call_claimed"
            ),
        },
    )
    assign_dispatch = getattr(orchestrator, "_assign_dispatch", None)
    if callable(assign_dispatch):
        maybe_awaitable = assign_dispatch(dispatch)
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable
    else:
        pool = getattr(orchestrator, "_pool", None)
        assign = getattr(pool, "assign", None)
        if callable(assign):
            assigned = assign(agent.id, task.id)
            if inspect.isawaitable(assigned):
                await assigned
    return dispatch


async def _wait_for_execution(
    orchestrator: Orchestrator,
    dispatches: list[Any],
    *,
    timeout_seconds: float,
) -> None:
    running_tasks = getattr(orchestrator, "_running_tasks", {})
    if not isinstance(running_tasks, dict):
        return
    tasks = [
        task
        for dispatch in dispatches
        if (task := running_tasks.get(dispatch.task_id)) is not None
    ]
    if not tasks:
        return
    await asyncio.wait(tasks, timeout=max(0.1, float(timeout_seconds)))


async def _task_result(orchestrator: Orchestrator, dispatch: Any) -> str:
    board = getattr(orchestrator, "_board", None)
    get = getattr(board, "get", None)
    if callable(get):
        task = get(dispatch.task_id)
        if inspect.isawaitable(task):
            task = await task
        result = getattr(task, "result", None)
        if result:
            return str(result)
    pool = getattr(orchestrator, "_pool", None)
    get_result = getattr(pool, "get_result", None)
    if callable(get_result):
        result = get_result(dispatch.agent_id)
        if inspect.isawaitable(result):
            result = await result
        if result is not None:
            return str(result)
    return ""


def _subtask_records(
    *,
    subtask_plan: list[dict[str, Any]],
    selected_agents: list[AgentState],
    dispatches: list[Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, (subtask, agent, dispatch) in enumerate(
        zip(subtask_plan, selected_agents, dispatches, strict=False),
        start=1,
    ):
        record = {
            "index": index,
            "task": subtask["task"],
            "primary_skill": subtask.get("primary_skill", ""),
            "agent_id": agent.id,
            "agent_name": agent.name,
            "agent_provider": agent.provider,
            "agent_model": agent.model,
            "agent_model_tier": _model_tier(agent),
            "dispatch_task_id": dispatch.task_id,
            "dispatch_agent_id": dispatch.agent_id,
            "dispatch_topology": dispatch.topology.value,
            "dispatch_metadata": dict(dispatch.metadata),
        }
        dispatch.metadata["holon_subtask"] = {
            key: value for key, value in record.items() if key != "dispatch_metadata"
        }
        dispatch.metadata["holon_orchestration"] = True
        dispatch.metadata["holon_model_tier"] = record["agent_model_tier"]
        records.append(record)
    return records


async def run_holon_orchestration(
    config: HolonOrchestrationConfig,
    *,
    orchestrator: Orchestrator,
    agents_root: Any | None = None,
    decomposer: HolonDecomposer | None = None,
    synthesizer: HolonSynthesizer | None = None,
) -> dict[str, Any]:
    """Run one deterministic HOLON orchestration cycle over existing organs."""
    holon = load_holon(config.name, agents_root=agents_root)
    mission = str(config.mission or "").strip()
    if not mission:
        raise HolonOrchestrationError("mission is required")

    decomposition = (decomposer or _default_decompose)(mission)
    subtask_plan = _coerce_subtask_plan(decomposition)[: max(1, config.max_subtasks)]
    if len(subtask_plan) < config.min_subtasks:
        raise HolonOrchestrationError(
            f"decomposition produced {len(subtask_plan)} subtasks; "
            f"need at least {config.min_subtasks}"
        )

    agents = await _idle_agents(orchestrator)
    selected_agents = agents[: len(subtask_plan)]
    if len(selected_agents) < config.min_subtasks:
        raise HolonOrchestrationError(
            f"only {len(selected_agents)} idle agents available; "
            f"need at least {config.min_subtasks}"
        )
    model_tiers = sorted({_model_tier(agent) for agent in selected_agents})
    if config.require_model_tier_diversity and len(model_tiers) < config.min_model_tiers:
        raise HolonOrchestrationError(
            f"model tier diversity {len(model_tiers)} < {config.min_model_tiers}"
        )

    parent_task = await _register_parent_task(
        orchestrator,
        title=f"HOLON {holon.name} orchestration",
        description=mission,
        metadata={
            "holon_orchestration": True,
            "holon": holon.name,
            "holon_provider_type": holon.provider_type,
            "holon_model": holon.model,
            "holon_subtasks": subtask_plan,
            "holon_required_subtasks": config.min_subtasks,
            "holon_required_model_tiers": config.min_model_tiers,
            "holon_execution_mode": config.execution_mode,
        },
    )
    execution_mode = str(config.execution_mode or "dispatch_aggregation_probe")
    live_specialist_execution_claimed = execution_mode == "bounded_subtask_execution"
    subtask_tasks: list[Task] = []
    if execution_mode == "bounded_subtask_execution":
        dispatches = []
        for subtask, agent in zip(subtask_plan, selected_agents, strict=False):
            subtask_task = await _register_subtask(
                orchestrator,
                parent_task=parent_task,
                subtask=subtask,
                agent=agent,
            )
            subtask_tasks.append(subtask_task)
            dispatch = await _dispatch_specific_agent(
                orchestrator,
                task=subtask_task,
                agent=agent,
                parent_task=parent_task,
            )
            dispatches.append(dispatch)
            await _wait_for_execution(
                orchestrator,
                [dispatch],
                timeout_seconds=config.execution_timeout_seconds,
            )
        results: list[str] = []
        for dispatch in dispatches:
            result = await _task_result(orchestrator, dispatch)
            if result:
                results.append(result)
        aggregate = "\n".join(results)
    else:
        dispatches = await orchestrator.fan_out(parent_task, selected_agents)
        aggregate = await orchestrator.fan_in(dispatches)
    subtask_records = _subtask_records(
        subtask_plan=subtask_plan,
        selected_agents=selected_agents,
        dispatches=dispatches,
    )
    synthesis = await _maybe_await(
        (synthesizer or _default_synthesizer)(
            holon,
            mission,
            subtask_records,
            aggregate,
        )
    )
    synthesis_source = "injected_holon_synthesizer" if synthesizer else "deterministic_default"
    proof_levels = {
        "identity_loaded": bool(holon.name and holon.model and holon.system_prompt),
        "subtasks_planned": len(subtask_plan) >= config.min_subtasks,
        "fan_out_dispatches": len(dispatches) >= config.min_subtasks,
        "model_tier_diversity": len(model_tiers) >= config.min_model_tiers,
        "fan_in_aggregated": bool(aggregate.strip()),
        "synthesis": bool(synthesis.strip()),
    }
    if execution_mode == "bounded_subtask_execution":
        proof_levels["live_specialist_execution"] = (
            len(subtask_tasks) >= config.min_subtasks and bool(aggregate.strip())
        )
    return {
        "schema_version": ORCHESTRATION_SCHEMA_VERSION,
        "execution_mode": execution_mode,
        "holon": {
            "name": holon.name,
            "provider_type": holon.provider_type,
            "model": holon.model,
            "system_prompt_chars": len(holon.system_prompt),
        },
        "mission": mission,
        "parent_task_id": parent_task.id,
        "subtask_task_ids": [task.id for task in subtask_tasks],
        "subtask_plan": subtask_plan,
        "dispatches": [
            {
                "task_id": dispatch.task_id,
                "agent_id": dispatch.agent_id,
                "topology": dispatch.topology.value,
                "metadata": dict(dispatch.metadata),
            }
            for dispatch in dispatches
        ],
        "subtask_records": subtask_records,
        "model_tiers": model_tiers,
        "aggregate": aggregate,
        "synthesis": synthesis,
        "synthesis_source": synthesis_source,
        "live_model_call_claimed": False,
        "live_specialist_execution_claimed": live_specialist_execution_claimed,
        "proof_levels": proof_levels,
        "overall_pass": all(proof_levels.values()),
    }


__all__ = [
    "HolonOrchestrationConfig",
    "HolonOrchestrationError",
    "run_holon_orchestration",
]
