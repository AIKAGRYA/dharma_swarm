"""Fail-closed preflight and run-manifest construction for the EXPLORE loop.

Leaf module of ``experiment``: owns the membrane fact sheet and the run
manifest the loop records before generation 0. It imports configuration from
``experiment_config`` but never the loop module — dependency direction is
``experiment`` → ``experiment_preflight`` → ``experiment_config``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dharma_swarm.evolution_safety import (
    evaluate_mutation,
    model_spend_allowed,
    safety_summary,
)
from dharma_swarm.forge_lab.experiment_config import ExperimentConfig, Seams
from dharma_swarm.forge_lab.freeform_explore import MEMBRANE_REQUIREMENTS
from dharma_swarm.forge_lab.run_receipts import _closeout, _write_json

RUN_MANIFEST_SCHEMA = "forge_lab.run_manifest.v0"


def initial_membrane() -> dict[str, bool]:
    """Preflight (§7a) membrane facts — fail-closed, each fact recorded."""

    membrane = {name: False for name in MEMBRANE_REQUIREMENTS}
    membrane["no_live_daemon_mutation"] = True  # chassis has no daemon surface
    membrane["no_secret_wallet_or_prod_access"] = True  # keys only via provider layer
    membrane["no_evaluator_grader_safety_or_archive_tamper"] = True  # read-only imports
    membrane["budget_cap_recorded"] = True
    membrane["lineage_recorded"] = True
    return membrane


def admit_scratch_worktree(
    cfg: ExperimentConfig,
    *,
    exp_id: str,
    exp_dir: Path,
    archive_path: Path,
    seams: Seams,
    started_at: str,
    membrane: dict[str, bool],
) -> tuple[Path | None, dict[str, Any] | None]:
    """Admit the marked scratch worktree through the mutation membrane.

    Returns ``(scratch, early_closeout)``: ``early_closeout`` is only populated
    when the spend gate refuses the run, in which case the caller returns it
    immediately without touching the archive.
    """

    if cfg.dry_run:
        membrane["marked_scratch_worktree"] = True  # recorded as dry_run below
        membrane["container_or_equivalent_sandbox"] = True
        return None, None
    spend_ok, spend_reason = model_spend_allowed()
    if not spend_ok:
        closeout = _closeout(
            exp_dir, exp_id, "blocked_with_evidence",
            reasons=[f"spend_gate:{spend_reason}"], started_at=started_at,
            stats={}, merkle_root=None, wall_seconds=0.0,
            scratch_worktree={"path": None, "state": "not_created", "removed": None},
        )
        return None, closeout
    scratch = seams.make_worktree(
        source_repo=cfg.source_repo,
        experiment_id=exp_id,
        archive_path=archive_path,
        category=cfg.category,
    )
    decision = evaluate_mutation(
        target_workspace=scratch, requested_live=False, runtime_state_available=False
    )
    if not (decision.allowed and decision.effective_shadow):
        raise RuntimeError(f"membrane refused scratch worktree: {decision.denial_reason}")
    membrane["marked_scratch_worktree"] = True
    # Production seams admit official SWE-bench Docker grading only.  PR
    # suite tasks are recorded InconclusiveInfrastructure until their
    # brokerless container grader exists; host pytest is never executed.
    membrane["container_or_equivalent_sandbox"] = True
    return scratch, None


def write_run_manifest(
    cfg: ExperimentConfig,
    *,
    exp_id: str,
    exp_dir: Path,
    git_identity: dict[str, Any],
    started_at: str,
    membrane: dict[str, bool],
    scratch: Path | None,
    estimate: dict[str, Any],
) -> dict[str, Any]:
    """Build and atomically install the run manifest; returns it."""

    manifest = {
        "schema": RUN_MANIFEST_SCHEMA,
        "experiment_id": exp_id,
        "category": cfg.category,
        "benchmark": cfg.benchmark,
        # Historical field retained for readers; it is now the actual source
        # HEAD used to run the experiment, not origin/main.
        "git_base_sha": git_identity["head_sha"],
        "git_identity": git_identity,
        "mode": "shadow",
        "dry_run": cfg.dry_run,
        "started_at": started_at,
        "config": {
            k: str(v) if isinstance(v, Path) else v for k, v in vars(cfg).items() if k != "seed_genome"
        },
        "seed_genome": cfg.seed_genome,
        "membrane": membrane,
        "safety": {} if cfg.dry_run else safety_summary(repo_path=scratch),
        "archive_fitness_authority": "one_wire_disabled_explicit_lab_shadow",
        "cost_estimate": estimate,
        "caveats": [
            "explore grading: official SWE-bench Docker; host PR-suite grading is refused as infrastructure-inconclusive",
            "fuel is single-repo (pallets/click) until harvest scales — fitness is click-domain",
            "explore closeouts can never be positive_lift_candidate",
        ],
    }
    _write_json(exp_dir / "run_manifest.json", manifest)
    return manifest
