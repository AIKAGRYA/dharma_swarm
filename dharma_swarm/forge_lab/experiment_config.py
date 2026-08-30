"""Experiment configuration and injectable seams for the EXPLORE loop.

Leaf module of ``experiment``: owns ``ExperimentConfig``, the ``Seams``
injection surface, and the pre-run cost estimate. It never imports the loop
module — the dependency direction is ``experiment`` → ``experiment_config``
only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from dharma_swarm.forge_lab import grade_explore, worktree
from dharma_swarm.forge_lab.state_io import dharma_home


@dataclass
class ExperimentConfig:
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
    propose_timeout_s: int = 240
    grade_timeout_s: int = 600
    rng_seed: int = 20260706
    lane_id: str = "forge_lab_chassis_v0"
    category: str = "agent_evolution"
    benchmark: str = "taskbed-explore-fresh-pr-suite"
    dry_run: bool = False
    keep_worktree: bool = False
    # The bounded unattended lane owns a fixed logical-call proof and therefore
    # cannot allow the RNG to silently replace its one mutation-model call with
    # a parametric or crossover operator. Interactive EXPLORE keeps the wild
    # stochastic policy by default.
    force_single_llm_mutation: bool = False
    source_repo: Path = field(default_factory=lambda: Path.home() / "dharma_swarm")
    state_root: Path = field(default_factory=lambda: dharma_home() / "evolution_archive")


@dataclass
class Seams:
    """Every external effect, injectable. Production defaults built lazily."""

    grade: grade_explore.GradeSeams | None = None
    pull_task_context: Callable[[str], tuple[dict, dict]] | None = None
    allocate_explore: Callable[..., dict[str, Any]] | None = None
    mutate_complete: Callable[[str], tuple[str, int]] | None = None
    make_worktree: Callable[..., Path] | None = None
    remove_worktree: Callable[..., None] | None = None

    def resolved(self, cfg: ExperimentConfig) -> "Seams":
        if cfg.dry_run:
            return self
        from dharma_swarm.api_keys import bootstrap_runtime_env

        bootstrap_runtime_env()
        grade = self.grade or grade_explore.production_seams()
        if self.pull_task_context is None or self.allocate_explore is None:
            from dharma_swarm.forge_v1.forge_v2.runner import _pull_task_context
            from dharma_swarm.forge_v1.forge_v2.taskbed_ledger import allocate_explore

            pull = self.pull_task_context or _pull_task_context
            alloc = self.allocate_explore or allocate_explore
        else:
            pull, alloc = self.pull_task_context, self.allocate_explore
        mutate = self.mutate_complete
        if mutate is None:
            from dharma_swarm.forge_v1.providers import PoolCompletion

            completion = PoolCompletion(cfg.mutator_model)
            mutate = completion.complete
        return Seams(
            grade=grade,
            pull_task_context=pull,
            allocate_explore=alloc,
            mutate_complete=mutate,
            make_worktree=self.make_worktree or worktree.create_marked_scratch_worktree,
            remove_worktree=self.remove_worktree or worktree.remove_scratch_worktree,
        )


def _cost_estimate(cfg: ExperimentConfig) -> dict[str, Any]:
    candidate_grades = 1 + (cfg.children + 1) * cfg.generations
    observations = candidate_grades * cfg.tasks_per_generation
    return {
        "planned_candidate_grades": candidate_grades,
        "planned_observations": observations,
        "est_llm_calls_min": observations + cfg.children * cfg.generations,
        "est_wall_minutes_rough": round(observations * 1.5, 1),
        "token_ceiling": cfg.max_experiment_tokens,
    }
