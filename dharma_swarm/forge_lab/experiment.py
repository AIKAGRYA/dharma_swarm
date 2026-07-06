"""Forge Lab EXPLORE generational chassis."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.evolution_safety import evaluate_mutation, is_scratch_worktree
from dharma_swarm.evolution_safety_runtime import RuntimeCodeIdentity, safety_summary
from dharma_swarm.forge_lab.candidate_store import CandidateStore, safe_membrane
from dharma_swarm.forge_lab.freeform_explore import explore_law_summary
from dharma_swarm.forge_lab.mutation import mutate_genome, seed_genome
from dharma_swarm.forge_lab.selection import draw_parents
from dharma_swarm.forge_lab.worktree import (
    ScratchWorktree,
    close_scratch_worktree,
    create_marked_scratch_worktree,
)
from dharma_swarm.forge_v1.forge_v2.taskbed_ledger import (
    TaskbedLedgerError,
    allocate_explore,
    allocation_rows,
)
from dharma_swarm.forge_v1.forge_v2.pr_suite_grader import grade_pr_suite_prediction


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    category: str = "agent_evolution"
    generations: int = 1
    children: int = 2
    novelty_pressure: float = 0.7
    rng_seed: int = 7
    source_repo: Path = field(default_factory=Path.cwd)
    base_ref: str = "origin/main"
    archive_root: Path = field(default_factory=lambda: Path.home() / ".dharma" / "evolution_archive")
    worktree_root: Path | None = None
    taskbed_db: Path | None = None
    task_count: int = 0
    max_usd: float = 0.0
    keep_worktree: bool = False
    use_taskbed: bool = False

    @property
    def archive_dir(self) -> Path:
        return self.archive_root.expanduser() / self.category / self.experiment_id


@dataclass(frozen=True)
class GradeOutcome:
    fitness: dict[str, Any]
    behavior: dict[str, Any]
    receipt: dict[str, Any]


def estimate_cost(config: ExperimentConfig) -> dict[str, Any]:
    planned_children = int(config.generations) * int(config.children)
    return {
        "planned_children": planned_children,
        "planned_seed_grades": 1,
        "planned_total_grade_observations": planned_children + 1,
        "max_usd": float(config.max_usd),
        "external_contact": False,
        "model_calls": False,
        "live_mutation": False,
    }


def _shape_score(genome: dict[str, Any]) -> float:
    """Deterministic local smoke fitness, not a powered claim."""

    score = 0.15
    score += 0.10 if bool(genome.get("verify_gate", False)) else 0.0
    score += min(0.20, 0.04 * float(genome.get("k_candidates", 1) or 1))
    score += 0.08 if str(genome.get("prompt_template_id", "")).endswith("_v1") else 0.0
    score += 0.04 if int(genome.get("window_chars", 0) or 0) >= 11000 else 0.0
    score += 0.03 if int(genome.get("per_call_tokens", 0) or 0) >= 6000 else 0.0
    notes = list(genome.get("notes") or [])
    score += min(0.10, 0.01 * len(notes))
    return max(0.0, min(1.0, score))


def _grade_taskbed_empty_patch(
    *,
    task_rows: list[dict[str, Any]],
    genome: dict[str, Any],
    receipt_dir: Path,
) -> tuple[int, list[dict[str, Any]]]:
    solved = 0
    receipts: list[dict[str, Any]] = []
    patches = dict(genome.get("patches") or {})
    for row in task_rows:
        task = dict(row.get("task") or row)
        task_id = str(task.get("task_id") or task.get("instance_id") or row.get("task_id") or "")
        patch = str(patches.get(task_id, ""))
        result = grade_pr_suite_prediction(
            task,
            patch,
            timeout=60,
            receipt_root=receipt_dir,
        )
        solved += int(result.resolved)
        receipts.append(
            {
                "task_id": task_id,
                "resolved": result.resolved,
                "error": result.error,
                "receipt_path": result.receipt_path,
                "receipt_sha256": result.receipt_sha256,
            }
        )
    return solved, receipts


def grade_genome_explore(
    *,
    genome: dict[str, Any],
    archive_dir: Path,
    task_rows: list[dict[str, Any]] | None = None,
) -> GradeOutcome:
    tier = "explore-smoke-local"
    solved_task_ids: list[str] = []
    grade_receipts: list[dict[str, Any]] = []
    if task_rows:
        tier = "explore-fast-pr-suite"
        solved, grade_receipts = _grade_taskbed_empty_patch(
            task_rows=task_rows,
            genome=genome,
            receipt_dir=archive_dir / "grade_receipts",
        )
        solved_task_ids = [
            str(item["task_id"]) for item in grade_receipts if item.get("resolved") is True
        ]
        score = solved / max(1, len(task_rows))
    else:
        score = _shape_score(genome)
    receipt = {
        "schema": "forge_lab.explore_grade.v0",
        "tier": tier,
        "score": score,
        "solved_task_ids": solved_task_ids,
        "grade_receipts": grade_receipts,
        "positive_lift_claim": False,
        "created_at": _now_iso(),
    }
    return GradeOutcome(
        fitness={
            "score": score,
            "weighted": score,
            "structure": _shape_score(genome),
            "efficiency": 1.0 if len(json.dumps(genome, default=str)) < 4000 else 0.5,
        },
        behavior={"solved_task_ids": solved_task_ids},
        receipt=receipt,
    )


def _allocate_task_rows(config: ExperimentConfig) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not config.use_taskbed or config.task_count <= 0:
        return None, []
    db_path = config.taskbed_db if config.taskbed_db is not None else None
    kwargs: dict[str, Any] = {
        "count": config.task_count,
        "epoch_id": config.experiment_id,
        "lane_id": "forge_lab_chassis",
    }
    if db_path is not None:
        kwargs["db_path"] = db_path
    try:
        allocation = allocate_explore(**kwargs)
        rows_kwargs = {"allocation_id": allocation["allocation_id"]}
        if db_path is not None:
            rows_kwargs["db_path"] = db_path
        return allocation, allocation_rows(**rows_kwargs)
    except TaskbedLedgerError as exc:
        return {"blocked": str(exc)}, []


def _preflight(config: ExperimentConfig, scratch: ScratchWorktree) -> dict[str, Any]:
    scratch_ok, _marker, scratch_reason = is_scratch_worktree(scratch.repo)
    decision = evaluate_mutation(
        target_workspace=scratch.repo,
        requested_live=False,
        runtime_state_available=False,
    )
    identity = RuntimeCodeIdentity.capture(scratch.repo).to_dict()
    return {
        "schema": "forge_lab.run_manifest.v0",
        "experiment_id": config.experiment_id,
        "category": config.category,
        "created_at": _now_iso(),
        "law": explore_law_summary(),
        "config": {
            **asdict(config),
            "source_repo": str(config.source_repo),
            "archive_root": str(config.archive_root),
            "worktree_root": str(config.worktree_root) if config.worktree_root else "",
            "taskbed_db": str(config.taskbed_db) if config.taskbed_db else "",
        },
        "cost_estimate": estimate_cost(config),
        "scratch_worktree": {
            "path": str(scratch.repo),
            "git_base_sha": scratch.git_base_sha,
            "is_scratch": scratch_ok,
            "reason": scratch_reason,
        },
        "safety": safety_summary(scratch.repo),
        "mutation_decision": decision.__dict__,
        "runtime_code_identity": identity,
        "membrane": {
            **safe_membrane(),
            "marked_scratch_worktree": scratch_ok,
            "no_live_daemon_mutation": bool(decision.allowed and decision.effective_shadow and not decision.requested_live),
            "budget_cap_recorded": config.max_usd >= 0.0,
        },
    }


async def run_experiment(config: ExperimentConfig) -> dict[str, Any]:
    rng = random.Random(config.rng_seed)
    config.archive_dir.mkdir(parents=True, exist_ok=True)
    scratch = create_marked_scratch_worktree(
        experiment_id=config.experiment_id,
        category=config.category,
        archive_path=config.archive_dir,
        source_repo=config.source_repo,
        base_ref=config.base_ref,
        worktree_root=config.worktree_root,
    )
    store = CandidateStore(config.archive_dir)
    generation_receipts: list[dict[str, Any]] = []
    try:
        manifest = _preflight(config, scratch)
        _write_json(config.archive_dir / "run_manifest.json", manifest)
        allocation, task_rows = _allocate_task_rows(config)
        if allocation is not None:
            _write_json(config.archive_dir / "task_allocation.json", allocation)

        await store.load()
        if not store.graded_records():
            seed = seed_genome()
            grade = grade_genome_explore(genome=seed, archive_dir=config.archive_dir, task_rows=task_rows)
            await store.append(
                genome=seed,
                parent_id=None,
                experiment_id=config.experiment_id,
                category=config.category,
                generation=0,
                loop_iteration=0,
                state="graded",
                role="seed_baseline",
                fitness=grade.fitness,
                behavior=grade.behavior,
                operator="seed_baseline",
                notes="seed baseline; EXPLORE closeout cannot claim positive lift",
                benchmark_receipt=grade.receipt,
            )

        for loop_iteration in range(1, config.generations + 1):
            await store.load()
            draws = draw_parents(
                store.records(),
                children=config.children,
                rng=rng,
                novelty_pressure=config.novelty_pressure,
            )
            generated: list[dict[str, Any]] = []
            for slot, draw in enumerate(draws):
                mutation = mutate_genome(draw.parent.genome, rng=rng)
                generation = draw.parent.generation + 1
                if mutation.blocked:
                    record = await store.append(
                        genome=mutation.genome,
                        parent_id=draw.parent.candidate_id,
                        experiment_id=config.experiment_id,
                        category=config.category,
                        generation=generation,
                        loop_iteration=loop_iteration,
                        state="blocked",
                        fitness={"score": 0.0, "weighted": 0.0},
                        operator=mutation.operator,
                        raw_output=mutation.raw_output,
                        notes=mutation.blocker,
                        artifacts=mutation.artifacts,
                    )
                else:
                    grade = grade_genome_explore(
                        genome=mutation.genome,
                        archive_dir=config.archive_dir,
                        task_rows=task_rows,
                    )
                    record = await store.append(
                        genome=mutation.genome,
                        parent_id=draw.parent.candidate_id,
                        experiment_id=config.experiment_id,
                        category=config.category,
                        generation=generation,
                        loop_iteration=loop_iteration,
                        state="graded",
                        fitness=grade.fitness,
                        behavior=grade.behavior,
                        operator=mutation.operator,
                        raw_output=mutation.raw_output,
                        artifacts=mutation.artifacts,
                        benchmark_receipt=grade.receipt,
                    )
                generated.append(
                    {
                        "slot": slot,
                        "parent_id": draw.parent.candidate_id,
                        "parent_weight": draw.weight,
                        "child_count_before": draw.child_count,
                        "candidate_id": record.candidate_id,
                        "state": record.state,
                        "fitness": record.fitness,
                    }
                )
            receipt = {
                "schema": "forge_lab.generation_receipt.v0",
                "experiment_id": config.experiment_id,
                "loop_iteration": loop_iteration,
                "rng_seed": config.rng_seed,
                "novelty_pressure": config.novelty_pressure,
                "children": generated,
                "created_at": _now_iso(),
            }
            generation_receipts.append(receipt)
            _write_json(config.archive_dir / "generations" / f"{loop_iteration:04d}.json", receipt)

        await store.load()
        graded = store.graded_records()
        best = max(graded, key=lambda item: item.weighted_fitness) if graded else None
        closeout = {
            "schema": "forge_lab.closeout.v0",
            "experiment_id": config.experiment_id,
            "category": config.category,
            "closeout_state": "inconclusive_low_power",
            "positive_lift_claim": False,
            "reason": "EXPLORE smoke creates traffic and lineage; it is not powered for lift.",
            "candidate_count": len(store.records()),
            "graded_count": len(graded),
            "best_candidate_id": best.candidate_id if best else "",
            "best_fitness": best.weighted_fitness if best else 0.0,
            "archive_dir": str(config.archive_dir),
            "created_at": _now_iso(),
        }
        _write_json(config.archive_dir / "closeout.json", closeout)
        return closeout
    finally:
        close_scratch_worktree(scratch, source_repo=config.source_repo, keep_worktree=config.keep_worktree)


def config_from_args(args: argparse.Namespace) -> ExperimentConfig:
    return ExperimentConfig(
        experiment_id=args.experiment_id,
        category=args.category,
        generations=args.generations,
        children=args.children,
        novelty_pressure=args.novelty_pressure,
        rng_seed=args.rng_seed,
        source_repo=Path(args.source_repo).expanduser(),
        base_ref=args.base_ref,
        archive_root=Path(args.archive_root).expanduser(),
        worktree_root=Path(args.worktree_root).expanduser() if args.worktree_root else None,
        taskbed_db=Path(args.taskbed_db).expanduser() if args.taskbed_db else None,
        task_count=args.task_count,
        max_usd=args.max_usd,
        keep_worktree=args.keep_worktree,
        use_taskbed=args.use_taskbed,
    )


def run_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return asyncio.run(run_experiment(config_from_args(args)))
