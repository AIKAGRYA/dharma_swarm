from __future__ import annotations

import json

from dharma_swarm.forge_prod_contracts.receipts import (
    build_receipt_payload,
    write_scoreboard_report,
)
from dharma_swarm.forge_prod_contracts.scoreboard import (
    ARM_NAMES,
    BudgetPolicy,
    run_offline_scoreboard,
)
from dharma_swarm.forge_prod_contracts.taskbed import (
    CONTAMINATION_STATE,
    default_private_code_repair_tasks,
    grade_candidate_source,
    visible_task_manifest,
)


def test_private_taskbed_withholds_hidden_tests_and_is_seed_stable() -> None:
    tasks = default_private_code_repair_tasks(seed="unit-seed")
    repeated = default_private_code_repair_tasks(seed="unit-seed")
    manifest = visible_task_manifest(tasks)

    assert [task.task_id for task in tasks] == [task.task_id for task in repeated]
    assert manifest["contamination_state"] == CONTAMINATION_STATE
    assert manifest["hidden_tests_withheld"] is True
    assert len(tasks) == 3
    for entry in manifest["tasks"]:
        assert "hidden_test" not in entry
        assert str(entry["hidden_test_sha256"]).startswith("sha256:")
        assert entry["externality_level"] == "local_private_fixture"


def test_hidden_execution_grader_catches_noop_and_accepts_repair() -> None:
    task = default_private_code_repair_tasks()[0]
    noop = grade_candidate_source(task, task.buggy_source)
    repaired = grade_candidate_source(
        task,
        task.buggy_source.replace("* tax_bps / 1000", "* tax_bps / 10000"),
    )

    assert noop.passed is False
    assert noop.score == 0.0
    assert repaired.passed is True
    assert repaired.score == 1.0
    assert "test_hidden.py" in repaired.command[-1]


def test_offline_scoreboard_uses_equal_budget_and_strong_single_baseline() -> None:
    report = run_offline_scoreboard(
        budget_policy=BudgetPolicy(token_budget=900),
        run_id="unit-run",
    )
    payload = report.to_dict()
    summary = payload["summary"]
    arms = summary["arms"]

    assert summary["execution_graded"] is True
    assert summary["equal_budget"] is True
    assert summary["strong_single_baseline"] == "strong_single"
    assert set(arms) == set(ARM_NAMES)
    assert len(payload["rows"]) == len(default_private_code_repair_tasks()) * len(
        ARM_NAMES
    )
    for row in payload["rows"]:
        assert row["budget_cap_tokens"] == 900
        assert row["selected_without_hidden_tests"] is True
        assert row["estimated_tokens"] <= 900

    assert (
        arms["strong_single"]["average_score"] < arms["swarm_topology"]["average_score"]
    )
    assert summary["swarm_lift_vs_strong_single"] > 0


def test_scoreboard_refuses_promotion_for_shadow_first_contract() -> None:
    report = run_offline_scoreboard(run_id="unit-run")
    decision = report.promotion_decision

    assert decision["promotion_allowed"] is False
    assert decision["decision"] == "refuse_promotion_record_candidate_signal"
    assert "shadow_only_first_production_contract" in decision["blocked_gates"]
    assert "no_independent_external_countercheck" in decision["blocked_gates"]


def test_scoreboard_report_and_receipt_are_repeatable(tmp_path) -> None:
    report = run_offline_scoreboard(run_id="unit-run")
    json_path, markdown_path, receipt_path = write_scoreboard_report(report, tmp_path)
    first_json = json_path.read_text(encoding="utf-8")
    first_receipt = receipt_path.read_text(encoding="utf-8")
    write_scoreboard_report(report, tmp_path)

    payload = json.loads(first_json)
    receipt = json.loads(first_receipt)

    assert json_path.read_text(encoding="utf-8") == first_json
    assert receipt_path.read_text(encoding="utf-8") == first_receipt
    assert markdown_path.exists()
    assert payload["task_manifest_sha256"] == receipt["task_manifest_sha256"]
    assert receipt["equal_budget"] is True
    assert receipt["promotion_allowed"] is False
    assert receipt["authority_attestation"]["provider_keys_read"] is False
    assert receipt["authority_attestation"]["router_mutated"] is False
    assert receipt["authority_attestation"]["darwin_apply_called"] is False
    assert receipt["receipt_sha256"].startswith("sha256:")


def test_receipt_payload_points_at_report_artifact(tmp_path) -> None:
    report = run_offline_scoreboard(run_id="unit-run")
    report_path = tmp_path / "scoreboard_report.json"
    receipt = build_receipt_payload(report, report_path)

    assert receipt["run_id"] == "unit-run"
    assert receipt["artifact_path"] == str(report_path)
    assert receipt["artifact_sha256"].startswith("sha256:")
    assert receipt["authority_attestation"]["public_benchmark_submission"] is False
