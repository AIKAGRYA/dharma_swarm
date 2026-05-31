"""Tests for the Dharma Reward Forge v0 loop-closure runner (scripts/runtime/reward_forge_v0.py)."""

from __future__ import annotations

import pathlib
import sys

import pytest

# The runner lives in scripts/runtime/ (A1: no new top-level package files).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "runtime"))

import reward_forge_v0 as forge  # noqa: E402

from dharma_swarm.dharma_eval import DharmaEvalTask  # noqa: E402
from dharma_swarm.evolution_receipt import verify_evolution_receipt  # noqa: E402


def _holdout_task():
    return DharmaEvalTask(
        task_id="ho-1",
        split="holdout",
        domain="repo_repair",
        expected={"status": "ok"},
    )


def test_loop_closes_and_promotes_on_holdout_gain():
    res = forge.run_sealed_forge_task(
        suite_id="forge_v0",
        manifest_hash="sha256:m1",
        holdout_task=_holdout_task(),
        candidate_id="child",
        incumbent_id="incumbent",
        candidate_holdout_output={"status": "ok"},
        baseline_holdout_output={"status": "fail"},
        patch_text="--- a\n+++ b\n+ fix",
        safety_passed=True,
        governance_passed=True,
        rollback_ref="git:abc123",
        min_holdout_improvement=0.5,
        test_commands=["python3 -m pytest tests/test_dharma_eval.py -q"],
        exit_codes=[0],
    )
    # The loop closed: a candidate that beats the sealed holdout reaches human review.
    assert res.review.status == "candidate_for_human_review"
    assert res.holdout_delta == pytest.approx(1.0)
    # Receipt carries all 5 required fields and is hash-verifiable.
    assert res.receipt.patch_hash.startswith("sha256:")
    assert res.receipt.eval_manifest_hash == "sha256:m1"
    assert res.receipt.score == pytest.approx(1.0)
    assert res.receipt.test_commands == ["python3 -m pytest tests/test_dharma_eval.py -q"]
    assert res.receipt.exit_codes == [0]
    assert verify_evolution_receipt(res.receipt)[0] is True
    # External-confirmed receipt grants real fitness.
    assert res.fitness.correctness == pytest.approx(1.0)


def test_no_holdout_gain_does_not_promote():
    res = forge.run_sealed_forge_task(
        suite_id="forge_v0",
        manifest_hash="sha256:m1",
        holdout_task=_holdout_task(),
        candidate_id="child",
        incumbent_id="incumbent",
        candidate_holdout_output={"status": "fail"},  # no better than baseline
        baseline_holdout_output={"status": "fail"},
        patch_text="+ noop",
        safety_passed=True,
        governance_passed=True,
        rollback_ref="git:abc123",
        min_holdout_improvement=0.5,
    )
    assert res.review.status != "candidate_for_human_review"
    assert "min_improvement_not_met:correctness" in res.review.reasons


def test_safety_failure_hard_blocks():
    res = forge.run_sealed_forge_task(
        suite_id="forge_v0",
        manifest_hash="sha256:m1",
        holdout_task=_holdout_task(),
        candidate_id="child",
        incumbent_id="incumbent",
        candidate_holdout_output={"status": "ok"},
        baseline_holdout_output={"status": "fail"},
        patch_text="+ fix",
        safety_passed=False,  # telos/safety gate fails
        governance_passed=True,
        rollback_ref="git:abc123",
        min_holdout_improvement=0.5,
    )
    assert res.review.status == "blocked"


def test_empty_diff_rejected():
    with pytest.raises(ValueError, match="diff"):
        forge.run_sealed_forge_task(
            suite_id="forge_v0",
            manifest_hash="sha256:m1",
            holdout_task=_holdout_task(),
            candidate_id="child",
            incumbent_id="incumbent",
            candidate_holdout_output={"status": "ok"},
            baseline_holdout_output={"status": "fail"},
            patch_text="   ",
            safety_passed=True,
            governance_passed=True,
            rollback_ref="git:abc123",
        )
