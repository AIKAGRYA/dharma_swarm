"""Foreground shape, resource, wall-clock, and single-flight experiment gates."""

from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable

from dharma_swarm.forge_lab.experiment_identity import _git_identity
from dharma_swarm.forge_lab.experiment_runtime import (
    ExperimentConfig,
    Seams,
    _config_digest,
    _control_state_root,
    _cost_estimate,
)
from dharma_swarm.forge_lab.run_guard import (
    RunGuard,
    RunLimits,
    host_resources,
    require_host_resources,
)


async def run_guarded(
    cfg: ExperimentConfig,
    seams: Seams | None,
    body: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    limits = _run_limits(cfg)
    limits.validate()
    if cfg.dry_run:
        return await body(cfg, seams)
    identity = _git_identity(cfg.source_repo)
    root = _control_state_root(cfg)
    require_host_resources(
        host_resources(), min_mem_available_bytes=cfg.min_mem_available_bytes,
        min_swap_free_bytes=cfg.min_swap_free_bytes,
    )
    with RunGuard(
        root, campaign_id=cfg.category, request_id=f"experiment-{time.time_ns()}",
        release_commit=str(identity.get("head_sha") or ""),
        config_digest=_config_digest(cfg), wall_seconds=cfg.max_wall_seconds,
    ) as guard:
        return await body(cfg, seams, run_guard=guard)


def _run_limits(cfg: ExperimentConfig) -> RunLimits:
    if cfg.evaluation_protocol not in {"legacy_v0", "paired_frozen_v1"}:
        raise ValueError(f"unknown evaluation_protocol: {cfg.evaluation_protocol}")
    paired = cfg.evaluation_protocol == "paired_frozen_v1"
    repeat_count = len(cfg.paired_repeat_seeds) if paired else 1
    tasks_per_split = (max(cfg.paired_train_tasks, cfg.paired_explore_tasks,
                           cfg.paired_confirm_tasks, cfg.paired_holdout_tasks)
                       if paired else cfg.tasks_per_generation)
    estimate = _cost_estimate(cfg)
    planned_candidates = 1 + cfg.generations * cfg.children
    if paired and not cfg.dry_run:
        try:
            campaign_usd = Decimal(str(cfg.max_experiment_usd))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("paired production requires explicit positive max_experiment_usd") from exc
        if not campaign_usd.is_finite() or campaign_usd <= 0:
            raise ValueError("paired production requires explicit positive max_experiment_usd")
        total_usd_micros = int(campaign_usd * 1_000_000)
    else:
        total_usd_micros = max(
            1, int(cfg.budget_cap_usd * 1_000_000) * planned_candidates
        )
    return RunLimits(
        generations=cfg.generations, children_per_generation=cfg.children,
        tasks_per_split=tasks_per_split, repeat_count=repeat_count,
        total_tokens=cfg.max_experiment_tokens,
        total_usd_micros=total_usd_micros,
        total_requests=max(1, int(estimate["est_llm_calls_min"])),
        wall_seconds=cfg.max_wall_seconds,
    )


__all__ = ["_run_limits", "run_guarded"]
