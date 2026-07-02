from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.dgm_loop import DGMResult
from dharma_swarm.forge_v1.forge_v2 import rsi_conductor
from dharma_swarm.forge_v1.forge_v2 import taskbed_ledger


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


def _seed_taskbed(db_path: Path, task_ids: list[str]) -> None:
    taskbed_ledger.register_tasks(
        [
            {
                "task_id": task_id,
                "created_at": f"2026-06-01T00:00:{idx:02d}Z",
                "contamination_state": "fresh_heldout",
                "provenance": {"contamination_state": "fresh_heldout"},
            }
            for idx, task_id in enumerate(task_ids)
        ],
        db_path=db_path,
        source="post_cutoff_pr_suite",
        taskbed="fresh_pr_suite",
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


def test_conductor_preserves_full_track_a_genome_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rsi_conductor, "RUN_ROOT", tmp_path / "runs")

    def fake_dgm_runner(genome, instance_ids, *, split):
        assert genome["arm"] == "verify_chain"
        assert genome["window_chars"] == 9000
        assert genome["selection_strategy"] == "verify_chain"
        assert genome["verifier"] == "deepseek-v4-pro:cloud"
        assert instance_ids == ["fresh-task-1"]
        assert split == "explore"
        return _fake_dgm_result()

    result = rsi_conductor.run_conductor(
        label="unit_conductor_genome",
        genome={
            "arm": "verify_chain",
            "generator": "glm-5.2",
            "verifier": "deepseek-v4-pro:cloud",
            "window_chars": 9000,
            "selection_strategy": "verify_chain",
        },
        instance_ids=["fresh-task-1"],
        split="explore",
        epoch_id="epoch-test",
        dgm_runner=fake_dgm_runner,
        operator_lease={"lease_id": "unit"},
    )

    run_manifest = json.loads((Path(result["run_dir"]) / "run_manifest.json").read_text(encoding="utf-8"))
    config = run_manifest["config"]
    assert config["window_chars"] == 9000
    assert config["selection_strategy"] == "verify_chain"
    assert result["promotion_verdict"]["decision"] == "refused"


def test_conductor_native_request_only_writes_grade_only_request(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rsi_conductor, "RUN_ROOT", tmp_path / "runs")
    db = tmp_path / "taskbed.db"
    _seed_taskbed(db, ["pr::pallets/click#3420", "pr::pallets/click#3534"])

    result = rsi_conductor.run_native_request_only(
        label="unit_native_conductor",
        genome={"arm": "verify_chain", "window_chars": 9000},
        split="explore",
        epoch_id="epoch-native",
        taskbed_db=db,
        taskbed_count=2,
        taskbed_candidate_id="scaffold_window_9000",
        native_run_id="native-from-conductor",
        native_output_root=tmp_path / "native_requests",
    )

    run_dir = Path(result["run_dir"])
    request_path = Path(result["request_path"])
    request = json.loads(request_path.read_text(encoding="utf-8"))

    assert result["status"] == "native_request_written"
    assert result["native_request_only"] is True
    assert result["dgm_runner_attempted"] is False
    assert result["packet_guard_attempted"] is False
    assert result["promotion_attempted"] is False
    assert result["source_of_truth_mutated"] is False
    assert result["live_apply_performed"] is False
    assert result["archive_fitness_mutated"] is False
    assert result["promotion_gate"] == "verify_promotion_only"
    assert result["task_count"] == 2
    assert (run_dir / "conductor_closeout.json").exists()
    assert (run_dir / "state.json").exists()
    assert request["run_id"] == "native-from-conductor"
    assert request["split"] == "explore"
    assert request["candidate_packet"]["candidate_id"] == "scaffold_window_9000"
    assert request["candidate_packet"]["genome"]["window_chars"] == 9000
    assert request["authority"]["live_apply_allowed"] is False
    assert request["authority"]["official_score_claimed"] is False
    assert request["authority"]["promotion_gate"] == "verify_promotion_only"
    assert request["task_ids"] == result["taskbed_allocation"]["task_ids"]


def test_conductor_native_request_only_cli_path(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(rsi_conductor, "RUN_ROOT", tmp_path / "runs")
    db = tmp_path / "taskbed.db"
    _seed_taskbed(db, ["pr::pallets/click#3420"])

    rc = rsi_conductor.main(
        [
            "--native-request-only",
            "--label",
            "unit_native_cli",
            "--split",
            "explore",
            "--taskbed-count",
            "1",
            "--epoch-id",
            "epoch-native-cli",
            "--taskbed-db",
            str(db),
            "--native-run-id",
            "native-cli-from-conductor",
            "--native-output-root",
            str(tmp_path / "native_requests"),
            "--native-candidate-json",
            json.dumps({"candidate_id": "cli-candidate"}),
            "--json",
        ]
    )

    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    request = json.loads(Path(result["request_path"]).read_text(encoding="utf-8"))
    assert result["status"] == "native_request_written"
    assert result["native_request_only"] is True
    assert result["promotion_attempted"] is False
    assert request["run_id"] == "native-cli-from-conductor"
    assert request["candidate_packet"]["candidate_id"] == "cli-candidate"
    assert request["authority"]["source_of_truth_mutation_allowed"] is False
