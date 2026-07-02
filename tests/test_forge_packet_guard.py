from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.forge_v1.forge_v2 import packet_guard, scheduler, taskbed_ledger


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_full_packet(packet: Path, *, task_count: int = 500, status: str = "positive_lift_candidate") -> None:
    arms = [
        "frontier_single_full_budget",
        "best_of_n_same_model",
        "same_budget_self_moa",
        "planner_builder_verifier_no_a2a",
        "full_a2a_swarm",
    ]
    _write_json(
        packet / "run_manifest.json",
        {
            "schema_version": "test",
            "benchmark_family": "synthetic",
            "task_count": task_count,
            "taskbed_allocation": {
                "split": "confirm",
                "task_count": task_count,
                "explore_separate_from_confirm": True,
                "contamination_clean": True,
            },
        },
    )
    _write_json(packet / "model_roster.json", {"arms": [{"arm": arm, "model": "test-model"} for arm in arms]})
    _write_jsonl(packet / "task_manifest.jsonl", [{"task_id": f"task-{idx}", "split": "confirm"} for idx in range(task_count)])
    _write_jsonl(
        packet / "results.jsonl",
        [
            {
                "task_id": f"task-{idx}",
                "arm": arm,
                "candidate_ok": True,
                "score": 1.0 if arm == "full_a2a_swarm" else 0.9,
            }
            for idx in range(task_count)
            for arm in arms
        ],
    )
    _write_jsonl(packet / "budget_ledger.jsonl", [{"arm": arm, "total_tokens": 1000} for arm in arms])
    _write_jsonl(
        packet / "coordination_edges.jsonl",
        [
            {"edge_kind": "swarm_only_win", "final_use_proof": True, "from": "planner", "to": "builder"},
            {"edge_kind": "swarm_only_win", "final_use_proof": True, "from": "verifier", "to": "builder"},
            {"edge_kind": "swarm_only_win", "final_use_proof": False, "from": "critic", "to": "builder"},
        ],
    )
    (packet / "control_comparison.md").write_text("# Control comparison\n", encoding="utf-8")
    (packet / "failure_taxonomy.md").write_text("# Failure taxonomy\n", encoding="utf-8")
    (packet / "decision_record.md").write_text(f"# Decision\n\nVerdict: `{status}`\n", encoding="utf-8")
    _write_json(
        packet / "swarm_lift_report.json",
        {
            "schema_version": "forge_swarm_lift_report.v1",
            "status": status,
            "task_count": task_count,
            "rubric_item_count": 300,
            "swarm_lift": 0.06,
            "paired_bootstrap_ci": {"lower": 0.01, "upper": 0.11, "n": task_count},
            "taskbed_allocation": {
                "split": "confirm",
                "task_count": task_count,
                "explore_separate_from_confirm": True,
                "contamination_clean": True,
            },
            "authority": {
                "trainer_built": False,
                "production_router_mutated": False,
                "archive_fitness_mutated": False,
                "official_score_claimed": False,
                "public_submission_performed": False,
                "external_confirmed": False,
            },
        },
    )


def _write_low_power_smoke_packet(packet: Path, *, status: str = "inconclusive_low_power") -> None:
    _write_json(
        packet / "run_manifest.json",
        {
            "schema_version": "test",
            "benchmark_family": "pr_suite",
            "status": status,
            "task_count": 1,
            "taskbed_allocation": {
                "split": "explore",
                "task_count": 1,
                "explore_separate_from_confirm": True,
                "contamination_clean": None,
            },
        },
    )
    _write_json(
        packet / "model_roster.json",
        {"arms": [{"arm": "self_moa"}, {"arm": "verify_chain"}], "generator": "test", "verifier": "test"},
    )
    _write_jsonl(packet / "task_manifest.jsonl", [{"task_id": "pr::example/repo#1", "split": "explore"}])
    _write_jsonl(
        packet / "results.jsonl",
        [
            {"task_id": "pr::example/repo#1", "arm": "self_moa", "candidate_ok": True, "score": 0.0},
            {"task_id": "pr::example/repo#1", "arm": "verify_chain", "candidate_ok": True, "score": 0.0},
        ],
    )
    _write_jsonl(
        packet / "budget_ledger.jsonl",
        [
            {
                "task_id": "pr::example/repo#1",
                "arm": "self_moa",
                "cap_tokens": 60000,
                "cap_usd": 0.25,
                "actual_cost_usd": 0.0035,
            },
            {
                "task_id": "pr::example/repo#1",
                "arm": "verify_chain",
                "cap_tokens": 60000,
                "cap_usd": 0.25,
                "actual_cost_usd": 0.0067,
            },
        ],
    )
    _write_jsonl(packet / "coordination_edges.jsonl", [])
    (packet / "control_comparison.md").write_text("# Control comparison\n", encoding="utf-8")
    (packet / "failure_taxonomy.md").write_text("# Failure taxonomy\n", encoding="utf-8")
    (packet / "decision_record.md").write_text(f"# Decision\n\nVerdict: `{status}`\n", encoding="utf-8")


def test_low_power_smoke_only_reports_expected_power_blockers(tmp_path: Path) -> None:
    packet = tmp_path / "low_power_smoke"
    _write_low_power_smoke_packet(packet)

    deterministic = packet_guard.run_guard(packet_dir=packet)["deterministic_review"]
    codes = {finding["code"] for finding in deterministic["findings"]}

    assert deterministic["verdict"] == "revise_protocol"
    assert deterministic["budget_parity"]["status"] == "pass"
    assert deterministic["budget_parity"]["basis"] == "cap_tokens"
    assert codes == {"low_power_under_3_tasks", "below_e4_confirm_floor"}


def test_positive_claim_still_requires_controls_and_final_use_proof(tmp_path: Path) -> None:
    packet = tmp_path / "positive_missing_proofs"
    _write_low_power_smoke_packet(packet, status="positive_lift_candidate")
    _write_json(
        packet / "swarm_lift_report.json",
        {
            "status": "positive_lift_candidate",
            "task_count": 10,
            "swarm_lift": 0.06,
            "paired_bootstrap_ci": {"lower": 0.01, "upper": 0.11, "n": 10},
            "taskbed_allocation": {"split": "explore", "task_count": 10},
        },
    )

    deterministic = packet_guard.run_guard(packet_dir=packet)["deterministic_review"]
    codes = {finding["code"] for finding in deterministic["findings"]}

    assert deterministic["verdict"] == "blocked_with_evidence"
    assert "control_arms_incomplete" in codes
    assert "final_use_proof_missing" in codes


def test_superiority_claim_is_blocked_for_low_power_partial_packet(tmp_path: Path) -> None:
    packet = tmp_path / "partial"
    packet.mkdir()
    _write_json(
        packet / "swarm_lift_report.json",
        {
            "status": "positive_lift_candidate",
            "task_count": 10,
            "swarm_lift": 0.02,
            "paired_bootstrap_ci": {"lower": -0.01, "upper": 0.05, "n": 10},
            "authority": {"archive_fitness_mutated": False},
        },
    )

    review = packet_guard.run_guard(packet_dir=packet, claim_text="Dharma Swarm beats the best single model")
    deterministic = review["deterministic_review"]

    assert deterministic["verdict"] == "blocked_with_evidence"
    codes = {finding["code"] for finding in deterministic["findings"]}
    assert "minimum_packet_incomplete" in codes
    assert "superiority_claim_forbidden" in codes
    assert deterministic["claim_superiority_requested"] is True


def test_full_packet_can_pass_for_next_scale_without_nim(tmp_path: Path) -> None:
    packet = tmp_path / "full"
    _write_full_packet(packet)

    review = packet_guard.run_guard(packet_dir=packet)
    deterministic = review["deterministic_review"]

    assert deterministic["verdict"] == "pass_for_next_scale"
    assert deterministic["task_count"] == 500
    assert deterministic["taskbed_power"]["full_confirm"] is True
    assert deterministic["canonical_arm_coverage"]["full_a2a_swarm"] is True
    assert deterministic["invalid_run_rate"] == 0.0
    assert deterministic["final_use_ratio"] >= 0.30
    assert (packet / "nvidia_guard_review.json").exists()
    assert (packet / "nvidia_guard_review.md").exists()


def test_underpowered_confirm_taskbed_is_blocked(tmp_path: Path) -> None:
    packet = tmp_path / "underpowered"
    _write_full_packet(packet, task_count=20)

    deterministic = packet_guard.run_guard(packet_dir=packet)["deterministic_review"]

    assert deterministic["verdict"] == "blocked_with_evidence"
    codes = {finding["code"] for finding in deterministic["findings"]}
    assert "confirm_taskbed_underpowered" in codes


def test_scheduler_canonical_packet_has_no_missing_guard_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "RUN_ROOT", tmp_path)
    scheduler.run_scheduler(
        instances=["a", "b"],
        n_explore=1,
        replicates=1,
        budget_cap=60000,
        campaign_budget_usd=0.25,
        per_call_tokens=3500,
        k_self_moa=1,
        grade_timeout=1200,
        timeout_s=240,
        strategy="explore",
        roster_n=14,
        generator="glm-5.2",
        verifier="moonshotai/kimi-k2.6",
        arms=["verify_chain"],
        mix_models=[],
        label="guard",
        max_campaigns=1,
        duration_hours=None,
        total_budget_usd=5.0,
        invalid_run_cap=2,
        sleep_seconds=0.0,
        dry_run=True,
    )
    packet = next(tmp_path.iterdir())
    collected = packet_guard.collect_packet(packet)
    deterministic = packet_guard.run_guard(packet_dir=packet)["deterministic_review"]

    assert [name for name, meta in collected["files"].items() if not meta["exists"]] == []
    assert deterministic["verdict"] == "revise_protocol"
    assert "minimum_packet_incomplete" not in {finding["code"] for finding in deterministic["findings"]}


def test_scheduler_full_confirm_packet_can_pass_guard_with_runner_final_use(tmp_path: Path, monkeypatch) -> None:
    run_root = tmp_path / "runs"
    db = tmp_path / "taskbed.db"
    monkeypatch.setattr(scheduler, "RUN_ROOT", run_root)
    taskbed_ledger.register_tasks(
        [
            {
                "task_id": f"fresh-{idx:03d}",
                "created_at": "2026-07-01T00:00:00Z",
                "contamination_state": "fresh_heldout",
                "provenance": {"contamination_state": "fresh_heldout", "source": "post_cutoff_pr_suite"},
            }
            for idx in range(packet_guard.MIN_CONFIRM_N)
        ],
        db_path=db,
        source="post_cutoff_pr_suite",
        taskbed="fresh_pr_suite",
    )
    arms = list(packet_guard.CANONICAL_CONTROL_ARM_ALIASES)

    def fake_runner(instances, *_args, **kwargs):
        arm = kwargs["arm"]
        attempts = [
            {
                "task_id": task_id,
                "split": "confirm",
                "arm": arm,
                "replicate": 0,
                "resolved": arm == "full_a2a_swarm",
                "budget": {"total_cost_usd": 0.001, "spent_tokens": 1000, "cap_tokens": 1000},
                "invalid": False,
            }
            for task_id in instances
        ]
        return {
            "arm": arm,
            "class_null": "same_budget_self_moa",
            "closeout": "positive_lift_candidate",
            "n_pairs": len(instances),
            "contrast_vs_class_null": {
                "n": len(instances),
                "mean": 0.06,
                "lower": 0.01,
                "upper": 0.11,
                "p_le_0": 0.01,
            },
            "split_contrasts": {
                "confirm": {
                    "n": len(instances),
                    "mean": 0.06,
                    "lower": 0.01,
                    "upper": 0.11,
                    "p_le_0": 0.01,
                }
            },
            "critic_verdict": {"ran": False},
            "contamination_state": {"state": "fresh_heldout"},
            "budget_matched_proof": {"any_invalid": False},
            "attempts": attempts,
            "coordination_edges": [
                {"edge_kind": "swarm_only_win", "from": "planner", "to": "builder", "final_use_proof": True},
                {"edge_kind": "swarm_only_win", "from": "verifier", "to": "builder", "final_use_proof": True},
                {"edge_kind": "swarm_only_win", "from": "critic", "to": "builder", "final_use_proof": False},
            ],
            "next_experiment": "synthetic native packet pass regression",
        }

    scheduler.run_scheduler(
        instances=["legacy"],
        n_explore=0,
        replicates=1,
        budget_cap=60000,
        campaign_budget_usd=0.25,
        per_call_tokens=3500,
        k_self_moa=1,
        grade_timeout=1200,
        timeout_s=240,
        strategy="explore",
        roster_n=14,
        generator="glm-5.2",
        verifier="moonshotai/kimi-k2.6",
        arms=arms,
        mix_models=[],
        label="native_guard_pass",
        max_campaigns=len(arms),
        duration_hours=None,
        total_budget_usd=10.0,
        invalid_run_cap=2,
        sleep_seconds=0.0,
        epoch_id="epoch-guard-pass",
        taskbed_db=db,
        taskbed_split="confirm",
        taskbed_count=packet_guard.MIN_CONFIRM_N,
        taskbed_allocation_id="confirm-native-guard-pass",
        runner=fake_runner,
    )
    packet = next(run_root.iterdir())

    review = packet_guard.run_guard(packet_dir=packet)
    deterministic = review["deterministic_review"]

    assert deterministic["verdict"] == "pass_for_next_scale"
    assert deterministic["task_count"] == packet_guard.MIN_CONFIRM_N
    assert deterministic["taskbed_power"]["full_confirm"] is True
    assert deterministic["taskbed_power"]["clean_confirm"] is True
    assert all(deterministic["canonical_arm_coverage"].values())
    assert deterministic["budget_parity"]["status"] == "pass"
    assert deterministic["invalid_run_rate"] == 0.0
    assert deterministic["final_use_ratio"] >= 0.30
    assert not deterministic["findings"]


def test_live_nim_failure_is_recorded_without_crashing(monkeypatch, tmp_path: Path) -> None:
    packet = tmp_path / "full"
    _write_full_packet(packet)

    async def fake_call(*_args, **_kwargs):
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(packet_guard, "call_nvidia_nim", fake_call)
    review = packet_guard.run_guard(packet_dir=packet, with_nim=True)

    assert review["deterministic_review"]["verdict"] == "pass_for_next_scale"
    assert review["nvidia_nim_review"]["verdict"] == "revise_protocol"
    assert review["nvidia_nim_review"]["failure_type"] == "TimeoutError"
