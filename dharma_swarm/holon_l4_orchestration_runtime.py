"""Shared read-only orchestration runtime for L4 HOLON proofs."""
from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from dharma_swarm.holon_l4_smoke import L4SmokeConfig, run_l4_supervised_smoke
from dharma_swarm.intent_router import DecomposedTask, TaskIntent
from dharma_swarm.models import AgentConfig, AgentRole, ProviderType


class _NoopAdvancedMemory:
    async def remember(self, **kwargs: object) -> None:
        return None

    async def consolidate(self) -> None:
        return None


class _NoopSleepTimeAgent:
    async def consolidate_knowledge(self, *args: object, **kwargs: object) -> list:
        return []


async def _noop_record_task_completion(*args: object, **kwargs: object) -> None:
    return None


def deterministic_l4_decompose(mission: str) -> DecomposedTask:
    return DecomposedTask(
        original=mission,
        sub_tasks=[
            TaskIntent(
                task="Map SwarmManager L4 runtime organs",
                primary_skill="cartographer",
            ),
            TaskIntent(
                task="Verify bounded HOLON execution receipts",
                primary_skill="validator",
            ),
        ],
        total_agents=2,
        has_parallel_work=True,
    )


async def run_l4_smoke_with_readonly_swarm_manager(
    config: L4SmokeConfig,
    *,
    state_dir: Path | str,
) -> dict[str, Any]:
    """Run an L4 smoke cycle with a read-only SwarmManager orchestration organ.

    This helper is intentionally importable so the one-shot smoke script and the
    long-running service prove orchestration through the same path.
    """
    import dharma_swarm.sleep_time_agent as sleep_time_agent
    import dharma_swarm.telos_tracker as telos_tracker
    from dharma_swarm.swarm import SwarmManager

    old_read_only_boot = os.environ.get("DHARMA_READ_ONLY_BOOT")
    old_fast_boot = os.environ.get("DHARMA_FAST_BOOT")
    old_sleep_time_agent = sleep_time_agent.SleepTimeAgent
    old_record_task_completion = telos_tracker.record_task_completion
    os.environ["DHARMA_READ_ONLY_BOOT"] = "1"
    os.environ["DHARMA_FAST_BOOT"] = "1"
    sleep_time_agent.SleepTimeAgent = _NoopSleepTimeAgent
    telos_tracker.record_task_completion = _noop_record_task_completion

    swarm = None
    try:
        swarm = SwarmManager(state_dir=Path(state_dir))
        await swarm.init()
        if swarm._agent_pool is None or swarm._orchestrator is None:
            raise RuntimeError("read-only SwarmManager did not initialize agent pool/orchestrator")
        for name, role, model in (
            (
                "l4-holon-smoke-architect",
                AgentRole.ARCHITECT,
                "deterministic-architect",
            ),
            (
                "l4-holon-smoke-validator",
                AgentRole.VALIDATOR,
                "deterministic-validator",
            ),
        ):
            await swarm._agent_pool.spawn(
                AgentConfig(
                    name=name,
                    role=role,
                    provider=ProviderType.OLLAMA,
                    model=model,
                    system_prompt="Return concise deterministic proof notes.",
                    metadata={"state_dir": str(state_dir)},
                ),
                provider=None,
                message_bus=swarm._message_bus,
                advanced_memory=_NoopAdvancedMemory(),
            )
        return await run_l4_supervised_smoke(
            replace(
                config,
                enable_orchestration_probe=True,
                orchestration_orchestrator=swarm._orchestrator,
                orchestration_decomposer=(
                    config.orchestration_decomposer or deterministic_l4_decompose
                ),
            )
        )
    finally:
        if swarm is not None:
            await swarm.shutdown(drain_timeout=1.0)
        sleep_time_agent.SleepTimeAgent = old_sleep_time_agent
        telos_tracker.record_task_completion = old_record_task_completion
        if old_read_only_boot is None:
            os.environ.pop("DHARMA_READ_ONLY_BOOT", None)
        else:
            os.environ["DHARMA_READ_ONLY_BOOT"] = old_read_only_boot
        if old_fast_boot is None:
            os.environ.pop("DHARMA_FAST_BOOT", None)
        else:
            os.environ["DHARMA_FAST_BOOT"] = old_fast_boot


__all__ = [
    "deterministic_l4_decompose",
    "run_l4_smoke_with_readonly_swarm_manager",
]
