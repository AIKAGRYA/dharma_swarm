from __future__ import annotations

from pathlib import Path

from dharma_swarm.dgm_loop import DGMResult
from dharma_swarm.forge_v1.forge_v2 import rsi_conductor


def _fake_dgm_result() -> DGMResult:
    receipt = {
        "kind": "forge_v2_run",
        "mission_class": "verifier_role",
        "arm": "verify_chain",
        "class_null": "self_moa",
        "n_pairs": 1,
        "contrast_vs_class_null": {"n": 1, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        "split_contrasts": {
            "explore": {"n": 1, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
            "confirm": {"n": 0, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        },
        "contamination_state": {"state": "possible_pretrain"},
        "budget_matched_proof": {
            "cap_tokens": 60000,
            "cap_usd": 0.25,
            "any_invalid": False,
            "self_moa_pass_rate": 1.0,
            "verify_chain_pass_rate": 1.0,
        },
        "closeout": "inconclusive_low_power",
        "attempts": [
            {
                "task_id": "fresh-task-1",
                "split": "explore",
                "arm": "self_moa",
                "class_null": "self_moa",
                "replicate": 0,
                "generator": "deepseek-ai/deepseek-v4-pro",
                "verifier": None,
                "resolved": True,
                "grade_seconds": 1.0,
                "budget": {"cap_tokens": 60000, "spent_tokens": 10, "total_cost_usd": 0.001},
                "invalid": False,
            },
            {
                "task_id": "fresh-task-1",
                "split": "explore",
                "arm": "verify_chain",
                "class_null": "self_moa",
                "replicate": 0,
                "generator": "deepseek-ai/deepseek-v4-pro",
                "verifier": "kimi-for-coding",
                "resolved": True,
                "grade_seconds": 1.0,
                "budget": {"cap_tokens": 60000, "spent_tokens": 10, "total_cost_usd": 0.001},
                "invalid": False,
            },
        ],
    }
    return DGMResult(
        source_file="forge_scaffold::verify_chain",
        fitness_after=0.0,
        forge_grade={
            "real_grade": True,
            "fitness": 0.0,
            "ci": receipt["contrast_vs_class_null"],
            "closeout": "inconclusive_low_power",
            "promote_eligible": False,
            "blockers": [
                "promotion_requires_confirm_split",
                "closeout_inconclusive_low_power",
                "confirm_ci_lower<=0",
            ],
            "runner_receipt": receipt,
        },
        promote_eligible=False,
        promotion_blockers=[
            "promotion_requires_confirm_split",
            "closeout_inconclusive_low_power",
            "confirm_ci_lower<=0",
        ],
        applied=False,
        shadow_mode=True,
    )


def test_conductor_blocks_when_taskbed_is_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rsi_conductor, "RUN_ROOT", tmp_path / "runs")

    result = rsi_conductor.run_conductor(
        label="unit_empty_taskbed",
        taskbed_db=tmp_path / "taskbed.db",
        taskbed_split="confirm",
        taskbed_count=1,
        taskbed_min_confirm_count=1,
        epoch_id="epoch-test",
    )

    assert result["status"] == "blocked_with_evidence"
    assert result["blocked_stage"] == "taskbed_allocation"
    assert "insufficient_confirm_tasks" in result["error"]
    assert Path(result["run_dir"], "conductor_closeout.json").exists()


def test_conductor_emits_packet_guard_and_refuses_promotion(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rsi_conductor, "RUN_ROOT", tmp_path / "runs")

    def fake_dgm_runner(genome, instance_ids, *, split):
        assert genome["arm"] == "verify_chain"
        assert instance_ids == ["fresh-task-1"]
        assert split == "explore"
        return _fake_dgm_result()

    result = rsi_conductor.run_conductor(
        label="unit_conductor",
        genome={"arm": "verify_chain"},
        instance_ids=["fresh-task-1"],
        split="explore",
        epoch_id="epoch-test",
        dgm_runner=fake_dgm_runner,
        operator_lease={"lease_id": "unit"},
    )

    run_dir = Path(result["run_dir"])
    assert result["status"] == "complete"
    assert result["shadow_mode"] is True
    assert result["applied"] is False
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "task_manifest.jsonl").exists()
    assert result["packet_guard_review"]["deterministic_review"]["verdict"] in {
        "blocked_with_evidence",
        "revise_protocol",
    }
    assert result["promotion_verdict"]["decision"] == "refused"
    assert "promotion_packet:e4_confirm_full_500" in result["promotion_verdict"]["blockers"]
