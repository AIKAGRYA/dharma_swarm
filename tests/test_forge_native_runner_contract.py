from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.forge_v1.forge_v2 import native_runner_contract as nrc


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_write_native_runner_request_is_grade_only_and_prewarmable(tmp_path: Path) -> None:
    result = nrc.write_native_runner_request(
        run_id="native-smoke-1",
        output_root=tmp_path / "requests",
        split="explore",
        candidate_packet={
            "candidate_id": "scaffold_window_9000",
            "track": "scaffold_genome",
            "genome": {"arm": "verify_chain", "window_chars": 9000},
        },
        task_allocation={
            "allocation_id": "explore-a",
            "split": "explore",
            "task_ids": ["pr::pallets/click#3208", "pr::pallets/werkzeug#3147"],
        },
        budget={"cap_tokens": 60000, "cap_usd": 0.25},
        max_infra_retries=2,
    )

    request_dir = Path(result["request_dir"])
    request = _read_json(request_dir / "native_runner_request.json")
    prewarm = _read_json(request_dir / "prewarm_manifest.json")
    tasks = (request_dir / "tasks.jsonl").read_text(encoding="utf-8").splitlines()

    assert request["schema"] == nrc.REQUEST_SCHEMA
    assert request["candidate_packet"]["candidate_id"] == "scaffold_window_9000"
    assert request["task_allocation"]["allocation_id"] == "explore-a"
    assert request["task_ids"] == ["pr::pallets/click#3208", "pr::pallets/werkzeug#3147"]
    assert request["authority"] == {
        "no_source_of_truth_mutation": True,
        "source_of_truth_mutation_allowed": False,
        "live_apply_allowed": False,
        "archive_fitness_mutated": False,
        "official_score_claimed": False,
        "promotion_gate": nrc.PROMOTION_GATE,
    }
    assert prewarm["repos"] == ["pallets/click", "pallets/werkzeug"]
    assert prewarm["docker_namespace"] == "swebench"
    assert len(tasks) == 2
    assert json.loads(tasks[0])["status"] == "pending_native_grade"


def test_build_prewarm_manifest_unions_explicit_and_inferred_inputs() -> None:
    manifest = nrc.build_prewarm_manifest(
        ["pr::pallets/click#3208", "plain-task"],
        repos=["custom/repo"],
        docker_images=["swebench/sweb.eval.x86_64.custom"],
        dependency_cache_keys=["pip:pallets-click"],
    )

    assert manifest["repos"] == ["custom/repo", "pallets/click"]
    assert manifest["docker_images"] == ["swebench/sweb.eval.x86_64.custom"]
    assert manifest["dependency_cache_keys"] == ["pip:pallets-click"]


def test_plan_resume_skips_completed_and_retries_infra_failures() -> None:
    request = {
        "run_id": "native-smoke-1",
        "candidate_id": "candidate-a",
        "task_ids": ["task-complete", "task-retry", "task-fresh"],
        "max_infra_retries": 2,
    }
    plan = nrc.plan_resume(
        request,
        [
            {"task_id": "task-complete", "status": "resolved"},
            {"task_id": "task-retry", "status": "infra_failed", "attempt": 1},
        ],
    )

    assert plan["skip_completed_grades"] is True
    assert plan["completed_task_ids"] == ["task-complete"]
    assert plan["remaining_tasks"] == [
        {"task_id": "task-retry", "next_attempt": 2, "prior_infra_failures": 1},
        {"task_id": "task-fresh", "next_attempt": 1, "prior_infra_failures": 0},
    ]
    assert plan["quarantined_tasks"] == []
    assert plan["no_source_of_truth_mutation"] is True


def test_plan_resume_quarantines_exhausted_infra_and_worker_flaky_tasks() -> None:
    request = {
        "run_id": "native-smoke-1",
        "candidate_id": "candidate-a",
        "task_ids": ["task-exhausted", "task-flaky"],
        "max_infra_retries": 1,
    }
    plan = nrc.plan_resume(
        request,
        [
            {"task_id": "task-exhausted", "status": "infra_failed", "attempt": 1},
            {"task_id": "task-exhausted", "status": "timeout", "attempt": 2},
            {"task_id": "task-flaky", "status": "flaky", "attempt": 1},
        ],
    )

    assert plan["remaining_tasks"] == []
    assert plan["quarantined_tasks"] == [
        {
            "task_id": "task-exhausted",
            "reason": "infra_retry_budget_exhausted",
            "infra_failures": 2,
            "max_infra_retries": 1,
        },
        {"task_id": "task-flaky", "reason": "worker_quarantined_or_flaky", "statuses": ["flaky"]},
    ]


def test_sync_remote_receipts_refuses_source_of_truth_mutation(tmp_path: Path) -> None:
    remote = tmp_path / "remote" / "native-run-1"
    remote.mkdir(parents=True)
    (remote / "result_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "native-run-1",
                "source_of_truth_mutated": True,
                "promotion_gate": nrc.PROMOTION_GATE,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source_of_truth_mutated"):
        nrc.sync_remote_receipts(remote_result_root=remote, local_sync_root=tmp_path / "sync")


def test_sync_remote_receipts_copies_task_receipts_and_writes_manifest(tmp_path: Path) -> None:
    remote = tmp_path / "remote" / "native-run-1"
    receipts = remote / "task_receipts"
    receipts.mkdir(parents=True)
    (remote / "result_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "native-run-1",
                "source_of_truth_mutated": False,
                "live_apply_performed": False,
                "archive_fitness_mutated": False,
                "promotion_gate": nrc.PROMOTION_GATE,
            }
        ),
        encoding="utf-8",
    )
    (receipts / "task-a.json").write_text(
        json.dumps(
            {
                "task_id": "task-a",
                "status": "resolved",
                "resolved": True,
                "source_of_truth_mutated": False,
                "promotion_gate": nrc.PROMOTION_GATE,
            }
        ),
        encoding="utf-8",
    )
    (receipts / "task-b.json").write_text(
        json.dumps(
            {
                "task_id": "task-b",
                "status": "unresolved",
                "resolved": False,
                "source_of_truth_mutated": False,
                "promotion_gate": nrc.PROMOTION_GATE,
            }
        ),
        encoding="utf-8",
    )

    manifest = nrc.sync_remote_receipts(
        remote_result_root=remote,
        local_sync_root=tmp_path / "sync",
        expected_run_id="native-run-1",
    )

    sync_dir = Path(manifest["local_sync_dir"])
    copied = sorted((sync_dir / "task_receipts").glob("*.json"))
    assert manifest["schema"] == nrc.SYNC_SCHEMA
    assert manifest["receipt_count"] == 2
    assert len(copied) == 2
    assert (sync_dir / "sync_manifest.json").exists()
    assert manifest["source_of_truth_mutated"] is False
    assert manifest["live_apply_performed"] is False
    assert manifest["promotion_gate"] == nrc.PROMOTION_GATE
