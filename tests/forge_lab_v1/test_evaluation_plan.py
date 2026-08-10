from __future__ import annotations

import json

import pytest

from dharma_swarm.forge_lab.evaluation_plan import (
    EvaluationPlanError,
    assert_frozen_tasks,
    build_evaluation_plan,
    build_evaluation_plan_from_overlay,
    frozen_task_mismatches,
    load_evaluation_plan,
    write_evaluation_plan,
)
from dharma_swarm.forge_lab.ids import content_digest


def _record(task_id: str, *, statement: str | None = None) -> dict:
    return {
        "task_id": task_id,
        "task": {"task_id": task_id, "problem_statement": statement or f"repair {task_id}"},
        "source": "unit",
        "taskbed": "frozen",
        "contamination_state": "fresh_post_cutoff",
        "provenance": {"receipt": f"receipt-{task_id}"},
        "created_at": "2026-08-10T00:00:00Z",
    }


def _plan():
    return build_evaluation_plan(
        campaign_id="campaign-1",
        split_tasks={
            "train": [_record("train-1")],
            "explore": [_record("explore-1")],
            "confirm": [_record("confirm-1")],
            "holdout": [_record("holdout-1")],
        },
        repeat_seeds=[11, 29],
        baseline_candidate_id="cand_aaaaaaaaaaaaaaaa",
        baseline_genome_sha256="a" * 64,
        evaluator_identity={"base_sha": "abc123", "grader": "unit-v1"},
        created_at="2026-08-10T01:00:00Z",
    )


def test_plan_freezes_four_disjoint_splits_and_content_hashes() -> None:
    plan = _plan()

    assert plan.repeat_seeds == (11, 29)
    assert plan.task_ids("train") == ("train-1",)
    assert plan.task_ids("holdout") == ("holdout-1",)
    assert len(plan.plan_sha256) == 64
    assert plan.train[0].content_sha256 == content_digest(_record("train-1")["task"])
    assert plan.to_dict()["logical_to_physical"] == {
        "train": "explore",
        "explore": "explore",
        "confirm": "confirm",
        "holdout": "confirm",
    }


def test_plan_write_is_atomic_idempotent_and_refuses_drift(tmp_path) -> None:
    path = tmp_path / "evaluation_plan.json"
    plan = _plan()

    assert write_evaluation_plan(path, plan) == plan
    assert write_evaluation_plan(path, plan).plan_sha256 == plan.plan_sha256
    assert load_evaluation_plan(path) == plan

    changed = build_evaluation_plan(
        campaign_id="campaign-1",
        split_tasks={
            "train": [_record("train-1", statement="changed")],
            "explore": [_record("explore-1")],
            "confirm": [_record("confirm-1")],
            "holdout": [_record("holdout-1")],
        },
        repeat_seeds=[11, 29],
        baseline_candidate_id="cand_aaaaaaaaaaaaaaaa",
        baseline_genome_sha256="a" * 64,
        evaluator_identity={"base_sha": "abc123", "grader": "unit-v1"},
        created_at="2026-08-10T01:00:00Z",
    )
    with pytest.raises(EvaluationPlanError, match="different content"):
        write_evaluation_plan(path, changed)


def test_plan_detects_task_content_and_provenance_changes() -> None:
    plan = _plan()
    records = {
        task_id: _record(task_id)
        for task_id in ("train-1", "explore-1", "confirm-1", "holdout-1")
    }
    assert_frozen_tasks(plan, records.__getitem__)

    records["confirm-1"] = _record("confirm-1", statement="silently replaced")
    assert frozen_task_mismatches(plan, records.__getitem__) == ["confirm-1"]
    with pytest.raises(EvaluationPlanError, match="confirm-1"):
        assert_frozen_tasks(plan, records.__getitem__)


def test_plan_materializes_exact_persisted_overlay() -> None:
    records = {
        task_id: _record(task_id)
        for task_id in ("train-1", "explore-1", "confirm-1", "holdout-1")
    }
    overlay = {
        "schema": "forge_v2.campaign_task_overlay.v1",
        "campaign_id": "campaign-overlay",
        "frozen": True,
        "logical_to_physical": {
            "train": "explore",
            "explore": "explore",
            "confirm": "confirm",
            "holdout": "confirm",
        },
        "logical_splits": {
            "train": ["train-1"],
            "explore": ["explore-1"],
            "confirm": ["confirm-1"],
            "holdout": ["holdout-1"],
        },
        "all_splits_disjoint": True,
        "confirm_pool_contamination_clean": True,
    }
    overlay["overlay_sha256"] = content_digest(overlay)
    plan = build_evaluation_plan_from_overlay(
        overlay_receipt=overlay,
        task_loader=records.__getitem__,
        repeat_seeds=[5],
        baseline_candidate_id="cand_aaaaaaaaaaaaaaaa",
        baseline_genome_sha256="a" * 64,
        evaluator_identity={"grader": "unit"},
        created_at="2026-08-10T01:00:00Z",
    )

    assert plan.campaign_id == "campaign-overlay"
    assert plan.task_ids("holdout") == ("holdout-1",)


def test_plan_rejects_overlap_duplicate_seeds_and_digest_tampering(tmp_path) -> None:
    common = dict(
        campaign_id="campaign-1",
        baseline_candidate_id="cand_aaaaaaaaaaaaaaaa",
        baseline_genome_sha256="a" * 64,
        evaluator_identity={"grader": "unit"},
        created_at="2026-08-10T01:00:00Z",
    )
    with pytest.raises(EvaluationPlanError, match="appears in both"):
        build_evaluation_plan(
            split_tasks={
                "train": [_record("same")],
                "explore": [_record("same")],
                "confirm": [_record("c")],
                "holdout": [_record("h")],
            },
            repeat_seeds=[1],
            **common,
        )
    with pytest.raises(EvaluationPlanError, match="unique"):
        build_evaluation_plan(
            split_tasks={
                "train": [_record("t")],
                "explore": [_record("e")],
                "confirm": [_record("c")],
                "holdout": [_record("h")],
            },
            repeat_seeds=[1, 1],
            **common,
        )

    mismatched_identity = dict(common)
    mismatched_identity["baseline_candidate_id"] = "cand_bbbbbbbbbbbbbbbb"
    with pytest.raises(EvaluationPlanError, match="does not match"):
        build_evaluation_plan(
            split_tasks={
                "train": [_record("t")],
                "explore": [_record("e")],
                "confirm": [_record("c")],
                "holdout": [_record("h")],
            },
            repeat_seeds=[1],
            **mismatched_identity,
        )

    contaminated = _record("c")
    contaminated["contamination_state"] = "possible_pretrain"
    with pytest.raises(EvaluationPlanError, match="contamination-clean"):
        build_evaluation_plan(
            split_tasks={
                "train": [_record("t")],
                "explore": [_record("e")],
                "confirm": [contaminated],
                "holdout": [_record("h")],
            },
            repeat_seeds=[1],
            **common,
        )

    path = tmp_path / "plan.json"
    path.write_text(json.dumps({**_plan().to_dict(), "campaign_id": "tampered"}))
    with pytest.raises(EvaluationPlanError, match="digest mismatch"):
        load_evaluation_plan(path)
