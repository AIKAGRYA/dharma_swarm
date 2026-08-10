from __future__ import annotations

from dharma_swarm.forge_lab.evaluation_plan import build_evaluation_plan
from dharma_swarm.forge_lab.paired_evaluation import (
    PairObservation,
    aggregate_paired_observations,
    build_paired_cells,
    task_clustered_bootstrap_ci,
)


BASELINE = "cand_aaaaaaaaaaaaaaaa"


def _plan():
    def record(task_id):
        return {
            "task_id": task_id,
            "task": {"task_id": task_id},
            "contamination_state": "fresh_post_cutoff",
        }

    return build_evaluation_plan(
        campaign_id="paired-unit",
        split_tasks={
            "train": [record("task-train")],
            "explore": [record("task-a"), record("task-b")],
            "confirm": [record("task-a-confirm"), record("task-b-confirm")],
            "holdout": [record("task-a-holdout"), record("task-b-holdout")],
        },
        repeat_seeds=[3, 7],
        baseline_candidate_id=BASELINE,
        baseline_genome_sha256="a" * 64,
        evaluator_identity={"grader": "unit"},
        created_at="2026-08-10T00:00:00Z",
    )


def _cells(split: str = "explore"):
    plan = _plan()
    return build_paired_cells(
        protocol_sha256=plan.plan_sha256,
        baseline_candidate_id=BASELINE,
        candidate_id="cand_challenger",
        split=split,
        task_ids=plan.task_ids(split),
        repeat_seeds=plan.repeat_seeds,
        seed_support="unsupported",
    )


def test_cells_pair_same_task_repeat_and_have_stable_distinct_ids() -> None:
    cells = _cells()
    again = _cells()

    assert cells == again
    assert len(cells) == 4
    assert len({cell.pair_id for cell in cells}) == 4
    assert len({cell.baseline_eval_id for cell in cells}) == 4
    assert len({cell.candidate_eval_id for cell in cells}) == 4
    assert all(cell.baseline_eval_id != cell.candidate_eval_id for cell in cells)
    assert all(set(cell.arm_order) == {"baseline", "candidate"} for cell in cells)
    assert all(cell.seed_support == "unsupported" for cell in cells)

    other_challenger = build_paired_cells(
        protocol_sha256=_plan().plan_sha256,
        baseline_candidate_id=BASELINE,
        candidate_id="cand_other",
        split="explore",
        task_ids=["task-a", "task-b"],
        repeat_seeds=[3, 7],
    )
    assert [cell.baseline_eval_id for cell in other_challenger] == [
        cell.baseline_eval_id for cell in cells
    ]
    assert [cell.pair_id for cell in other_challenger] != [cell.pair_id for cell in cells]


def test_complete_explore_grid_is_selection_eligible_without_claim() -> None:
    cells = _cells()
    observations = [
        PairObservation.from_cell(
            cell,
            baseline_score=0.0,
            candidate_score=1.0 if cell.task_id == "task-a" else 0.0,
        )
        for cell in cells
    ]

    result = aggregate_paired_observations(
        cells,
        observations,
        bootstrap_samples=100,
        bootstrap_seed=9,
        evaluation_plan=_plan(),
    )

    assert result["complete"] is True
    assert result["budget_valid"] is True
    assert result["selection_eligible"] is True
    assert result["decision_eligible"] is False
    assert result["clustered_ci"]["n_tasks"] == 2
    assert result["clustered_ci"]["n_pairs"] == 4
    assert result["clustered_ci"]["mean"] == 0.5
    assert result["positive_lift_claimed"] is False


def test_missing_or_budget_invalid_pair_fails_closed() -> None:
    cells = _cells()
    observations = [
        PairObservation.from_cell(
            cell,
            baseline_score=0.0,
            candidate_score=1.0,
            budget_valid=cell != cells[0],
        )
        for cell in cells[:-1]
    ]

    result = aggregate_paired_observations(
        cells, observations, bootstrap_samples=20, evaluation_plan=_plan()
    )

    assert result["complete"] is False
    assert result["selection_eligible"] is False
    assert result["budget_valid"] is False
    assert result["missing_pair_ids"] == [cells[-1].pair_id]
    assert result["invalid_pair_ids"] == [cells[0].pair_id]


def test_unbound_caller_defined_grid_cannot_be_selection_evidence() -> None:
    cells = _cells()
    observations = [
        PairObservation.from_cell(cell, baseline_score=0.0, candidate_score=1.0)
        for cell in cells[:1]
    ]
    result = aggregate_paired_observations(cells[:1], observations, bootstrap_samples=20)

    assert result["grid_complete"] is True
    assert result["plan_bound"] is False
    assert result["complete"] is False
    assert result["selection_eligible"] is False
    assert "unbound_evaluation_plan" in result["blockers"]


def test_grid_with_wrong_baseline_cannot_bind_to_frozen_plan() -> None:
    plan = _plan()
    cells = build_paired_cells(
        protocol_sha256=plan.plan_sha256,
        baseline_candidate_id="cand_bbbbbbbbbbbbbbbb",
        candidate_id="cand_challenger",
        split="explore",
        task_ids=plan.task_ids("explore"),
        repeat_seeds=plan.repeat_seeds,
    )
    observations = [
        PairObservation.from_cell(cell, baseline_score=0.0, candidate_score=1.0)
        for cell in cells
    ]

    result = aggregate_paired_observations(
        cells, observations, bootstrap_samples=20, evaluation_plan=plan
    )

    assert result["plan_bound"] is False
    assert result["selection_eligible"] is False
    assert "expected_cells_do_not_match_frozen_plan" in result["blockers"]


def test_confirm_grid_is_decision_not_search_selection_evidence() -> None:
    cells = _cells("confirm")
    observations = [
        PairObservation.from_cell(cell, baseline_score=0.0, candidate_score=0.0)
        for cell in cells
    ]
    result = aggregate_paired_observations(
        cells,
        observations,
        bootstrap_samples=20,
        evaluation_plan=_plan(),
        min_decision_tasks=2,
    )

    assert result["complete"] is True
    assert result["selection_eligible"] is False
    assert result["decision_eligible"] is True

    underpowered = aggregate_paired_observations(
        cells,
        observations,
        bootstrap_samples=20,
        evaluation_plan=_plan(),
    )
    assert underpowered["complete"] is True
    assert underpowered["decision_eligible"] is False
    assert underpowered["minimum_decision_tasks"] == 500


def test_bootstrap_clusters_repeats_by_task_instead_of_flattening_cells() -> None:
    # Flat-cell averaging would report +0.8.  The task-level estimand gives
    # each of the two independent tasks one vote and therefore reports zero.
    ci = task_clustered_bootstrap_ci(
        {"task-many-repeats": [1.0] * 9, "task-one-repeat": [-1.0]},
        samples=100,
        seed=4,
    )

    assert ci["n_tasks"] == 2
    assert ci["n_pairs"] == 10
    assert ci["mean"] == 0.0
