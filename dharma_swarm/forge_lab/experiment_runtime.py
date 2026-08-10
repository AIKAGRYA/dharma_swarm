"""Configuration and external-effect resolution for Forge Lab experiments."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.forge_lab import grade_explore, worktree

async def _offload(function: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Run one blocking seam in an owned executor and join it before returning.

    The host Python's asyncio default executor does not terminate reliably, so
    unattended runs must not leave that global pool behind at loop shutdown.
    """

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="rsi-owned") as executor:
        return await loop.run_in_executor(executor, partial(function, *args, **kwargs))


@dataclass
class ExperimentConfig:
    evaluation_protocol: str = "legacy_v0"
    generations: int = 2
    children: int = 3  # TOTAL per generation
    tasks_per_generation: int = 3
    novelty_pressure: float = 0.7
    solver_model: str = ""
    verifier_model: str = ""
    mutator_model: str = ""
    seed_genome: dict[str, Any] | None = None
    budget_cap_tokens: int = 120_000  # per candidate-grade
    budget_cap_usd: float = 2.0
    soft_token_cap: bool = True
    require_valid_seed: bool = True
    max_experiment_tokens: int = 600_000
    max_experiment_usd: float | None = None
    paired_train_tasks: int = 1
    paired_explore_tasks: int = 1
    paired_confirm_tasks: int = 1
    paired_holdout_tasks: int = 1
    paired_repeat_seeds: tuple[int, ...] = (0,)
    paired_bootstrap_samples: int = 500
    paired_min_decision_tasks: int = 500
    mutation_reservation_tokens: int = 32_768
    mutation_reservation_usd: float = 2.0
    execution_profile: Path | str | None = None
    campaign_id: str = ""
    max_wall_seconds: int = 21_600
    min_mem_available_bytes: int = 900 * 1024 * 1024
    min_swap_free_bytes: int = 256 * 1024 * 1024
    propose_timeout_s: int = 240
    grade_timeout_s: int = 600
    rng_seed: int = 20260706
    lane_id: str = "forge_lab_chassis_v0"
    category: str = "agent_evolution"
    benchmark: str = "taskbed-explore-fresh-pr-suite"
    dry_run: bool = False
    keep_worktree: bool = False
    source_repo: Path = field(default_factory=lambda: Path.home() / "dharma_swarm")
    state_root: Path = field(default_factory=lambda: Path.home() / ".dharma" / "evolution_archive")
    control_state_root: Path | None = None


@dataclass
class Seams:
    """Every external effect, injectable. Production defaults built lazily."""

    grade: grade_explore.GradeSeams | None = None
    pull_task_context: Callable[[str], tuple[dict, dict]] | None = None
    allocate_explore: Callable[..., dict[str, Any]] | None = None
    allocate_campaign_pools: Callable[..., dict[str, Any]] | None = None
    load_task_record: Callable[[str], dict[str, Any]] | None = None
    mutate_complete: Callable[[str], tuple[str, int]] | None = None
    make_worktree: Callable[..., Path] | None = None
    remove_worktree: Callable[..., None] | None = None
    execution_profile: Any | None = None

    def resolved(self, cfg: ExperimentConfig) -> "Seams":
        if cfg.dry_run:
            return self
        from dharma_swarm.api_keys import bootstrap_runtime_env

        bootstrap_runtime_env()
        from dharma_swarm.forge_v1.forge_v2.pr_suite_execution import (
            resolve_execution_profile,
        )

        execution_profile = resolve_execution_profile(
            self.execution_profile or cfg.execution_profile
        )
        grade = self.grade or grade_explore.production_seams()
        grade = replace(
            grade,
            grade_task=_container_only_grade_task(execution_profile),
        )
        if self.pull_task_context is None or self.allocate_explore is None:
            from dharma_swarm.forge_v1.forge_v2.runner import _pull_task_context
            from dharma_swarm.forge_v1.forge_v2.taskbed_ledger import allocate_explore

            pull = self.pull_task_context or _pull_task_context
            alloc = self.allocate_explore or allocate_explore
        else:
            pull, alloc = self.pull_task_context, self.allocate_explore
        campaign_alloc = self.allocate_campaign_pools
        load_task = self.load_task_record
        if cfg.evaluation_protocol == "paired_frozen_v1" and (
            campaign_alloc is None or load_task is None
        ):
            from dharma_swarm.forge_v1.forge_v2.taskbed_ledger import (
                allocate_campaign_pools,
                task_for_id,
            )

            campaign_alloc = campaign_alloc or allocate_campaign_pools
            load_task = load_task or task_for_id
        mutate = self.mutate_complete
        if mutate is None:
            from dharma_swarm.forge_v1.providers import PoolCompletion

            completion = PoolCompletion(cfg.mutator_model)
            mutate = completion.complete
        if cfg.evaluation_protocol == "paired_frozen_v1":
            mutate = partial(
                mutate,
                max_total_tokens=cfg.mutation_reservation_tokens,
            )
        return Seams(
            grade=grade,
            pull_task_context=pull,
            allocate_explore=alloc,
            allocate_campaign_pools=campaign_alloc,
            load_task_record=load_task,
            mutate_complete=mutate,
            make_worktree=self.make_worktree or worktree.create_marked_scratch_worktree,
            remove_worktree=self.remove_worktree or worktree.remove_scratch_worktree,
            execution_profile=execution_profile,
        )


def _container_only_grade_task(execution_profile: Any) -> Callable[..., tuple[bool, float, str | None]]:
    """Bind all production grading to the validated container profile."""

    from dharma_swarm.forge_v1.forge_v2.pr_suite_grader import (
        grade_pr_suite_prediction,
        is_pr_suite_task,
    )

    def grade_task(inst: dict[str, Any], patch: str, *, timeout: int) -> tuple[bool, float, str | None]:
        if not is_pr_suite_task(inst):
            return False, 0.0, "container_only_pr_suite_task_required"
        result = grade_pr_suite_prediction(
            inst,
            patch,
            timeout=timeout,
            execution_profile=execution_profile,
        )
        note = f"receipt={result.receipt_path}"
        if result.error:
            note = f"{result.error}; {note}"
        return bool(result.resolved), float(result.seconds), note

    return grade_task


def _cost_estimate(cfg: ExperimentConfig) -> dict[str, Any]:
    if cfg.evaluation_protocol == "paired_frozen_v1":
        repeats = len(cfg.paired_repeat_seeds)
        candidates = cfg.children * cfg.generations
        search_cells = (cfg.paired_train_tasks + cfg.paired_explore_tasks) * repeats
        decision_cells = (cfg.paired_confirm_tasks + cfg.paired_holdout_tasks) * repeats
        arm_evaluations = search_cells * (1 + candidates) + 2 * decision_cells
        return {
            "planned_candidate_grades": candidates,
            "planned_observations": arm_evaluations,
            "planned_paired_cells": search_cells * candidates + decision_cells,
            "est_llm_calls_min": arm_evaluations + candidates,
            "est_wall_minutes_rough": round(arm_evaluations * 1.5, 1),
            "token_ceiling": cfg.max_experiment_tokens,
        }
    observations = (1 + cfg.children * cfg.generations) * cfg.tasks_per_generation
    return {
        "planned_candidate_grades": 1 + cfg.children * cfg.generations,
        "planned_observations": observations,
        "est_llm_calls_min": observations + cfg.children * cfg.generations,
        "est_wall_minutes_rough": round(observations * 1.5, 1),
        "token_ceiling": cfg.max_experiment_tokens,
    }


def _config_digest(cfg: ExperimentConfig) -> str:
    payload = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(cfg).items()
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _control_state_root(cfg: ExperimentConfig) -> Path:
    if cfg.control_state_root is not None:
        root = cfg.control_state_root
    else:
        configured = os.environ.get("RSI_LAB_STATE", "").strip()
        base = os.environ.get("RSI_LAB_BASE", "").strip()
        if configured:
            root = Path(configured)
        elif base:
            root = Path(base) / "state"
        else:
            raise RuntimeError(
                "canonical control state is unbound; set RSI_LAB_STATE or RSI_LAB_BASE"
            )
    if not root.is_absolute():
        raise RuntimeError("canonical control state must be absolute")
    return root



__all__ = ["ExperimentConfig", "Seams", "_config_digest", "_container_only_grade_task", "_control_state_root", "_cost_estimate", "_offload"]
