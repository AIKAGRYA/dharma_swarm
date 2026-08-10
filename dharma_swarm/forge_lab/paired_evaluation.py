"""Deterministic paired-evaluation cells and task-clustered uncertainty.

This module does not call a provider.  It preregisters the exact baseline and
candidate cells a controller must execute, then validates and aggregates the
resulting observations without treating repeated samples from one task as
independent tasks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from dharma_swarm.forge_lab.evaluation_plan import EvaluationPlan, LOGICAL_SPLITS
from dharma_swarm.forge_lab.ids import content_digest
from dharma_swarm.forge_lab.paired_statistics import clustered_bootstrap_ci

PAIR_SCHEMA = "forge_lab.paired_evaluation.v1"
AGGREGATE_SCHEMA = "forge_lab.paired_aggregate.v1"
SEED_SUPPORT_MODES = frozenset({"native", "prompt_nonce", "unsupported"})


class PairedEvaluationError(ValueError):
    """A paired protocol or observation grid is invalid."""


@dataclass(frozen=True)
class EvaluationCell:
    protocol_sha256: str
    baseline_candidate_id: str
    candidate_id: str
    split: str
    task_id: str
    repeat_seed: int
    seed_support: str
    pair_id: str
    baseline_eval_id: str
    candidate_eval_id: str
    arm_order: tuple[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PAIR_SCHEMA,
            "protocol_sha256": self.protocol_sha256,
            "baseline_candidate_id": self.baseline_candidate_id,
            "candidate_id": self.candidate_id,
            "split": self.split,
            "task_id": self.task_id,
            "repeat_seed": self.repeat_seed,
            "seed_support": self.seed_support,
            "pair_id": self.pair_id,
            "baseline_eval_id": self.baseline_eval_id,
            "candidate_eval_id": self.candidate_eval_id,
            "arm_order": list(self.arm_order),
        }


@dataclass(frozen=True)
class PairObservation:
    pair_id: str
    baseline_eval_id: str
    candidate_eval_id: str
    split: str
    task_id: str
    repeat_seed: int
    baseline_score: float
    candidate_score: float
    baseline_valid: bool = True
    candidate_valid: bool = True
    budget_valid: bool = True
    errors: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        try:
            scores_finite = math.isfinite(float(self.baseline_score)) and math.isfinite(
                float(self.candidate_score)
            )
        except (TypeError, ValueError):
            scores_finite = False
        return (
            self.baseline_valid
            and self.candidate_valid
            and self.budget_valid
            and not self.errors
            and scores_finite
        )

    @property
    def difference(self) -> float:
        return float(self.candidate_score) - float(self.baseline_score)

    @classmethod
    def from_cell(
        cls,
        cell: EvaluationCell,
        *,
        baseline_score: float,
        candidate_score: float,
        baseline_valid: bool = True,
        candidate_valid: bool = True,
        budget_valid: bool = True,
        errors: Iterable[str] = (),
    ) -> "PairObservation":
        return cls(
            pair_id=cell.pair_id,
            baseline_eval_id=cell.baseline_eval_id,
            candidate_eval_id=cell.candidate_eval_id,
            split=cell.split,
            task_id=cell.task_id,
            repeat_seed=cell.repeat_seed,
            baseline_score=float(baseline_score),
            candidate_score=float(candidate_score),
            baseline_valid=bool(baseline_valid),
            candidate_valid=bool(candidate_valid),
            budget_valid=bool(budget_valid),
            errors=tuple(str(error) for error in errors),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "baseline_eval_id": self.baseline_eval_id,
            "candidate_eval_id": self.candidate_eval_id,
            "split": self.split,
            "task_id": self.task_id,
            "repeat_seed": self.repeat_seed,
            "baseline_score": self.baseline_score,
            "candidate_score": self.candidate_score,
            "difference": self.difference,
            "baseline_valid": self.baseline_valid,
            "candidate_valid": self.candidate_valid,
            "budget_valid": self.budget_valid,
            "errors": list(self.errors),
            "valid": self.valid,
        }


def pair_id(
    *,
    protocol_sha256: str,
    baseline_candidate_id: str,
    candidate_id: str,
    split: str,
    task_id: str,
    repeat_seed: int,
) -> str:
    """Stable pair identity for one exact task/repeat comparison."""
    payload = _cell_payload(
        protocol_sha256=protocol_sha256,
        baseline_candidate_id=baseline_candidate_id,
        candidate_id=candidate_id,
        split=split,
        task_id=task_id,
        repeat_seed=repeat_seed,
    )
    return f"pair_{content_digest(payload)[:20]}"


def evaluation_id(
    *,
    role: str,
    candidate_id: str,
    protocol_sha256: str | None = None,
    split: str | None = None,
    task_id: str | None = None,
    repeat_seed: int | None = None,
    pair_id: str | None = None,
) -> str:
    """Stable identity for one evaluated arm.

    New callers provide the protocol/task/repeat coordinates.  That keeps an
    incumbent baseline evaluation reusable across multiple challengers in the
    same frozen protocol.  ``pair_id`` remains accepted as a legacy fallback
    for early callers of this additive module.
    """
    if role not in {"baseline", "candidate"}:
        raise PairedEvaluationError("role must be baseline or candidate")
    if not candidate_id:
        raise PairedEvaluationError("candidate_id is required")
    coordinates = (protocol_sha256, split, task_id, repeat_seed)
    if all(value is not None for value in coordinates):
        if not _is_sha256(str(protocol_sha256)) or split not in LOGICAL_SPLITS:
            raise PairedEvaluationError("invalid evaluation protocol coordinates")
        if not str(task_id).strip() or isinstance(repeat_seed, bool) or not isinstance(repeat_seed, int):
            raise PairedEvaluationError("invalid evaluation task/repeat coordinates")
        payload = {
            "schema": PAIR_SCHEMA,
            "protocol_sha256": protocol_sha256,
            "split": split,
            "task_id": task_id,
            "repeat_seed": repeat_seed,
            "role": role,
            "candidate_id": candidate_id,
        }
    elif pair_id and all(value is None for value in coordinates):
        payload = {"pair_id": pair_id, "role": role, "candidate_id": candidate_id}
    else:
        raise PairedEvaluationError(
            "provide either pair_id or complete protocol/split/task/repeat coordinates"
        )
    return f"eval_{content_digest(payload)[:20]}"


def build_paired_cells(
    *,
    protocol_sha256: str,
    baseline_candidate_id: str,
    candidate_id: str,
    split: str,
    task_ids: Iterable[str],
    repeat_seeds: Iterable[int],
    seed_support: str = "unsupported",
) -> tuple[EvaluationCell, ...]:
    """Preregister the complete Cartesian task x repeat paired grid."""
    tasks = tuple(str(task_id).strip() for task_id in task_ids)
    repeats = tuple(repeat_seeds)
    _validate_common(protocol_sha256, baseline_candidate_id, candidate_id, split, seed_support)
    if not tasks or any(not task for task in tasks) or len(set(tasks)) != len(tasks):
        raise PairedEvaluationError("task_ids must be non-empty and unique")
    if (
        not repeats
        or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in repeats)
        or len(set(repeats)) != len(repeats)
    ):
        raise PairedEvaluationError("repeat_seeds must be non-empty unique integers")

    cells: list[EvaluationCell] = []
    for task_id_value in tasks:
        for repeat_seed in repeats:
            pid = pair_id(
                protocol_sha256=protocol_sha256,
                baseline_candidate_id=baseline_candidate_id,
                candidate_id=candidate_id,
                split=split,
                task_id=task_id_value,
                repeat_seed=repeat_seed,
            )
            order = (
                ("baseline", "candidate")
                if int(content_digest({"pair_id": pid, "purpose": "arm_order"})[-1], 16) % 2 == 0
                else ("candidate", "baseline")
            )
            cells.append(
                EvaluationCell(
                    protocol_sha256=protocol_sha256,
                    baseline_candidate_id=baseline_candidate_id,
                    candidate_id=candidate_id,
                    split=split,
                    task_id=task_id_value,
                    repeat_seed=repeat_seed,
                    seed_support=seed_support,
                    pair_id=pid,
                    baseline_eval_id=evaluation_id(
                        protocol_sha256=protocol_sha256,
                        split=split,
                        task_id=task_id_value,
                        repeat_seed=repeat_seed,
                        role="baseline",
                        candidate_id=baseline_candidate_id,
                    ),
                    candidate_eval_id=evaluation_id(
                        protocol_sha256=protocol_sha256,
                        split=split,
                        task_id=task_id_value,
                        repeat_seed=repeat_seed,
                        role="candidate",
                        candidate_id=candidate_id,
                    ),
                    arm_order=order,
                )
            )
    return tuple(cells)


def task_clustered_bootstrap_ci(
    task_differences: Mapping[str, Iterable[float]],
    *,
    samples: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Bootstrap tasks, after averaging repeats within each task.

    This prevents repeat cells from masquerading as additional independent
    tasks.  The estimand weights each task equally even if a caller supplies a
    different number of valid repeats per task.
    """
    return clustered_bootstrap_ci(
        task_differences,
        samples=samples,
        seed=seed,
        alpha=alpha,
        error_type=PairedEvaluationError,
    )


def aggregate_paired_observations(
    expected_cells: Sequence[EvaluationCell],
    observations: Sequence[PairObservation],
    *,
    bootstrap_samples: int = 2000,
    bootstrap_seed: int = 0,
    alpha: float = 0.05,
    evaluation_plan: EvaluationPlan | None = None,
    min_decision_tasks: int = 500,
) -> dict[str, Any]:
    """Validate an exact paired grid and compute task-clustered uncertainty."""
    if (
        isinstance(min_decision_tasks, bool)
        or not isinstance(min_decision_tasks, int)
        or min_decision_tasks <= 0
    ):
        raise PairedEvaluationError("min_decision_tasks must be a positive integer")
    if not expected_cells:
        raise PairedEvaluationError("expected_cells must not be empty")
    splits = {cell.split for cell in expected_cells}
    protocols = {cell.protocol_sha256 for cell in expected_cells}
    baselines = {cell.baseline_candidate_id for cell in expected_cells}
    candidates = {cell.candidate_id for cell in expected_cells}
    if any(len(values) != 1 for values in (splits, protocols, baselines, candidates)):
        raise PairedEvaluationError("expected_cells must describe one protocol contrast and split")

    expected_by_id = {cell.pair_id: cell for cell in expected_cells}
    if len(expected_by_id) != len(expected_cells):
        raise PairedEvaluationError("expected_cells contain duplicate pair IDs")
    observed_by_id: dict[str, PairObservation] = {}
    duplicate_ids: list[str] = []
    for observation in observations:
        if observation.pair_id in observed_by_id:
            duplicate_ids.append(observation.pair_id)
        observed_by_id[observation.pair_id] = observation

    missing = sorted(set(expected_by_id) - set(observed_by_id))
    unexpected = sorted(set(observed_by_id) - set(expected_by_id))
    invalid: list[str] = []
    mismatched: list[str] = []
    task_differences: dict[str, list[float]] = {}
    for pid in sorted(set(expected_by_id) & set(observed_by_id)):
        cell = expected_by_id[pid]
        observation = observed_by_id[pid]
        if (
            observation.baseline_eval_id != cell.baseline_eval_id
            or observation.candidate_eval_id != cell.candidate_eval_id
            or observation.split != cell.split
            or observation.task_id != cell.task_id
            or observation.repeat_seed != cell.repeat_seed
        ):
            mismatched.append(pid)
            continue
        if not observation.valid:
            invalid.append(pid)
            continue
        task_differences.setdefault(cell.task_id, []).append(observation.difference)

    blockers: list[str] = []
    for name, values in (
        ("missing_pairs", missing),
        ("unexpected_pairs", unexpected),
        ("duplicate_pairs", sorted(set(duplicate_ids))),
        ("mismatched_pairs", mismatched),
        ("invalid_pairs", invalid),
    ):
        if values:
            blockers.append(f"{name}:{len(values)}")
    grid_complete = not blockers and len(observed_by_id) == len(expected_by_id)
    plan_bound = False
    if evaluation_plan is None:
        blockers.append("unbound_evaluation_plan")
    else:
        canonical_cells = build_paired_cells(
            protocol_sha256=evaluation_plan.plan_sha256,
            baseline_candidate_id=evaluation_plan.baseline_candidate_id,
            candidate_id=next(iter(candidates)),
            split=next(iter(splits)),
            task_ids=evaluation_plan.task_ids(next(iter(splits))),
            repeat_seeds=evaluation_plan.repeat_seeds,
            seed_support=expected_cells[0].seed_support,
        )
        plan_bound = tuple(expected_cells) == canonical_cells
        if not plan_bound:
            blockers.append("expected_cells_do_not_match_frozen_plan")
    complete = grid_complete and plan_bound
    ci = task_clustered_bootstrap_ci(
        task_differences,
        samples=bootstrap_samples,
        seed=bootstrap_seed,
        alpha=alpha,
    )
    split = next(iter(splits))
    return {
        "schema": AGGREGATE_SCHEMA,
        "protocol_sha256": next(iter(protocols)),
        "baseline_candidate_id": next(iter(baselines)),
        "candidate_id": next(iter(candidates)),
        "split": split,
        "expected_pair_count": len(expected_cells),
        "expected_pair_ids": sorted(expected_by_id),
        "expected_baseline_eval_ids": sorted(
            {cell.baseline_eval_id for cell in expected_cells}
        ),
        "expected_candidate_eval_ids": sorted(
            {cell.candidate_eval_id for cell in expected_cells}
        ),
        "expected_eval_ids": sorted(
            {
                eval_id
                for cell in expected_cells
                for eval_id in (cell.baseline_eval_id, cell.candidate_eval_id)
            }
        ),
        "task_ids": sorted({cell.task_id for cell in expected_cells}),
        "repeat_seeds": sorted({cell.repeat_seed for cell in expected_cells}),
        "seed_support": expected_cells[0].seed_support,
        "valid_pair_count": sum(len(values) for values in task_differences.values()),
        "grid_complete": grid_complete,
        "plan_bound": plan_bound,
        "complete": complete,
        "budget_valid": not invalid and all(observation.budget_valid for observation in observations),
        "selection_eligible": complete and split == "explore",
        "decision_eligible": (
            complete
            and split in {"confirm", "holdout"}
            and ci["n_tasks"] >= min_decision_tasks
        ),
        "minimum_decision_tasks": min_decision_tasks,
        "missing_pair_ids": missing,
        "unexpected_pair_ids": unexpected,
        "duplicate_pair_ids": sorted(set(duplicate_ids)),
        "mismatched_pair_ids": mismatched,
        "invalid_pair_ids": invalid,
        "blockers": blockers,
        "clustered_ci": ci,
        "positive_lift_claimed": False,
        "claim_scope": "measurement_only",
    }


def _cell_payload(
    *,
    protocol_sha256: str,
    baseline_candidate_id: str,
    candidate_id: str,
    split: str,
    task_id: str,
    repeat_seed: int,
) -> dict[str, Any]:
    _validate_common(
        protocol_sha256,
        baseline_candidate_id,
        candidate_id,
        split,
        "unsupported",
        validate_seed_support=False,
    )
    if not str(task_id).strip():
        raise PairedEvaluationError("task_id is required")
    if isinstance(repeat_seed, bool) or not isinstance(repeat_seed, int):
        raise PairedEvaluationError("repeat_seed must be an integer")
    return {
        "schema": PAIR_SCHEMA,
        "protocol_sha256": protocol_sha256,
        "baseline_candidate_id": baseline_candidate_id,
        "candidate_id": candidate_id,
        "split": split,
        "task_id": str(task_id),
        "repeat_seed": repeat_seed,
    }


def _validate_common(
    protocol_sha256: str,
    baseline_candidate_id: str,
    candidate_id: str,
    split: str,
    seed_support: str,
    *,
    validate_seed_support: bool = True,
) -> None:
    if not _is_sha256(protocol_sha256):
        raise PairedEvaluationError("protocol_sha256 must be a full SHA-256 digest")
    if not baseline_candidate_id or not candidate_id:
        raise PairedEvaluationError("baseline_candidate_id and candidate_id are required")
    if baseline_candidate_id == candidate_id:
        raise PairedEvaluationError("baseline and candidate must be distinct")
    if split not in LOGICAL_SPLITS:
        raise PairedEvaluationError(f"unknown logical split: {split}")
    if validate_seed_support and seed_support not in SEED_SUPPORT_MODES:
        raise PairedEvaluationError(f"unknown seed support mode: {seed_support}")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


__all__ = ["AGGREGATE_SCHEMA", "EvaluationCell", "PAIR_SCHEMA", "PairObservation",
           "PairedEvaluationError", "SEED_SUPPORT_MODES", "aggregate_paired_observations",
           "build_paired_cells", "evaluation_id", "pair_id", "task_clustered_bootstrap_ci"]
