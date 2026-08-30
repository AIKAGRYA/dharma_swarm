"""Honest closeout assembly for the EXPLORE loop.

Leaf module of ``experiment``: owns the terminal state decision (explore can
never claim positive lift), the scratch-worktree cleanup evidence, and the
final closeout receipt. It never imports the loop module — dependency
direction is ``experiment`` → ``experiment_closeout`` only.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.candidate_store import CandidateStore
from dharma_swarm.forge_lab.experiment_config import ExperimentConfig, Seams
from dharma_swarm.forge_lab.run_receipts import _closeout


async def finalize_closeout(
    cfg: ExperimentConfig,
    *,
    exp_id: str,
    exp_dir: Path,
    store: CandidateStore,
    seams: Seams,
    counters: dict[str, int],
    stopped_early: str,
    started_at: str,
    started_mono: float,
    scratch: Path | None,
    tokens_spent_total: int,
    comparable_observations_total: int,
    infrastructure_observations_total: int,
    generation_observations_total: int,
    budget_observations_total: int,
    seed_soft_cap_exceeded: bool,
) -> dict[str, Any]:
    """Decide the honest terminal state and write the closeout receipt."""

    graded = await store.graded_entries()
    rows = [CandidateStore._row(e) for e in graded]
    seed_rate = next((r.get("pass_rate", 0.0) for r in rows if r.get("role") == "seed_baseline"), 0.0)
    best_rate = max((r.get("pass_rate", 0.0) for r in rows), default=0.0)
    if counters["graded"] == 0:
        state = "blocked_with_evidence"
    elif infrastructure_observations_total:
        state = "inconclusive_infrastructure"
    elif comparable_observations_total == 0 and budget_observations_total:
        state = "inconclusive_budget"
    elif comparable_observations_total == 0 and generation_observations_total:
        state = "inconclusive_generation"
    elif comparable_observations_total > 0 and best_rate <= seed_rate and best_rate == 0.0:
        state = "measured_negative"
    else:
        state = "inconclusive_low_power"  # explore can never claim positive lift
    chain_ok, chain_info = store.archive.merkle_log.verify_chain()
    scratch_worktree = {
        "path": str(scratch) if scratch is not None else None,
        "keep_worktree": cfg.keep_worktree,
        "state": "not_created" if scratch is None else "kept" if cfg.keep_worktree else "pending_cleanup",
        "removed": None if scratch is None or cfg.keep_worktree else False,
    }
    if scratch is not None and not cfg.keep_worktree:
        try:
            seams.remove_worktree(source_repo=cfg.source_repo, repo=scratch, experiment_id=exp_id)
        except Exception as exc:
            scratch_worktree.update(
                {"state": "cleanup_error", "removed": False, "error": f"{type(exc).__name__}:{exc}"}
            )
        else:
            removed = not scratch.exists()
            scratch_worktree.update(
                {"state": "removed" if removed else "remove_unconfirmed", "removed": removed}
            )
    closeout = _closeout(
        exp_dir, exp_id, state,
        reasons=[stopped_early] if stopped_early else [],
        started_at=started_at,
        stats={
            "counters": counters,
            "seed_pass_rate": seed_rate,
            "best_pass_rate": best_rate,
            "tokens_spent_total": tokens_spent_total,
            "comparable_observations_total": comparable_observations_total,
            "infrastructure_observations_total": infrastructure_observations_total,
            "generation_observations_total": generation_observations_total,
            "budget_observations_total": budget_observations_total,
            "n_tasks_per_generation": cfg.tasks_per_generation,
            "seed_soft_token_cap_exceeded": seed_soft_cap_exceeded,
            "soft_token_cap": cfg.soft_token_cap,
            "require_valid_seed": cfg.require_valid_seed,
            "note": "n is far below any powered claim; ranking signal only",
        },
        merkle_root={"verified": bool(chain_ok), "info": str(chain_info)},
        wall_seconds=round(time.monotonic() - started_mono, 1),
        scratch_worktree=scratch_worktree,
    )
    return closeout
