from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dharma_swarm.forge_v1.forge_v2 import native_runner_contract as nrc
from dharma_swarm.forge_v1.forge_v2 import pr_suite_grader
from dharma_swarm.forge_v1.forge_v2 import taskbed_ledger
from dharma_swarm.forge_v1 import swebench_real


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def test_prediction_for_task_uses_mapping_and_rejects_global_patch_for_multi_task() -> None:
    assert nrc.prediction_for_task({"task_predictions": {"task-a": "PATCH A"}}, "task-a", task_count=2) == "PATCH A"
    assert nrc.prediction_for_task({"predictions": {"task-a": "PATCH B"}}, "task-a", task_count=2) == "PATCH B"
    assert nrc.prediction_for_task({"patch": "GLOBAL"}, "task-a", task_count=2) == ""
    assert nrc.prediction_for_task({"patch": "GLOBAL"}, "task-a", task_count=1) == "GLOBAL"


def test_default_native_grade_dispatches_pr_suite_prediction(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    def fake_task_row_for_id(task_id: str, *, db_path):
        captured["task_id"] = task_id
        captured["db_path"] = str(db_path)
        return {"task_id": task_id, "instance_id": task_id, "source_kind": "post_cutoff_pr_suite"}

    def fake_grade_pr_suite_prediction(instance, model_patch, **kwargs):
        captured["instance"] = dict(instance)
        captured["model_patch"] = model_patch
        captured["kwargs"] = kwargs
        return pr_suite_grader.GradeResult(
            resolved=True,
            seconds=1.5,
            error=None,
            receipt_path=str(tmp_path / "grade.json"),
            receipt_sha256="grade-sha",
        )

    monkeypatch.setattr(pr_suite_grader, "task_row_for_id", fake_task_row_for_id)
    monkeypatch.setattr(pr_suite_grader, "grade_pr_suite_prediction", fake_grade_pr_suite_prediction)
    result = nrc.default_native_grade(
        {
            "task_id": "pr::pallets/click#3208",
            "candidate_packet": {
                "candidate_id": "cand",
                "task_predictions": {"pr::pallets/click#3208": "diff --git a/x b/x\n"},
            },
            "request": {
                "task_ids": ["pr::pallets/click#3208"],
                "worker_config": {
                    "taskbed_db": str(tmp_path / "taskbed.db"),
                    "grade_timeout": 123,
                    "receipt_root": str(tmp_path / "receipts"),
                    "work_root": str(tmp_path / "work"),
                },
            },
        }
    )

    assert result["status"] == "resolved"
    assert result["resolved"] is True
    assert result["grader"] == "pr_suite"
    assert result["grader_receipt_sha256"] == "grade-sha"
    assert captured["task_id"] == "pr::pallets/click#3208"
    assert captured["model_patch"] == "diff --git a/x b/x\n"
    assert captured["kwargs"]["timeout"] == 123
    assert str(captured["kwargs"]["receipt_root"]).endswith("receipts")
    assert str(captured["kwargs"]["work_root"]).endswith("work")


def test_default_native_grade_missing_prediction_is_unresolved_not_infra() -> None:
    result = nrc.default_native_grade(
        {
            "task_id": "pr::pallets/click#3208",
            "candidate_packet": {"candidate_id": "cand", "task_predictions": {}},
            "request": {"task_ids": ["pr::pallets/click#3208"]},
        }
    )

    assert result["status"] == "unresolved"
    assert result["resolved"] is False
    assert result["grade_error"] == "missing_task_prediction"
    assert result["blockers"] == ["missing_task_prediction"]


def test_run_native_runner_request_uses_default_pr_suite_grade(monkeypatch, tmp_path: Path) -> None:
    def fake_task_row_for_id(task_id: str, *, db_path):
        return {"task_id": task_id, "instance_id": task_id, "source_kind": "post_cutoff_pr_suite"}

    def fake_grade_pr_suite_prediction(instance, model_patch, **_kwargs):
        return pr_suite_grader.GradeResult(
            resolved=True,
            seconds=0.1,
            error=None,
            receipt_path=str(tmp_path / "grade.json"),
            receipt_sha256="grade-sha",
        )

    monkeypatch.setattr(pr_suite_grader, "task_row_for_id", fake_task_row_for_id)
    monkeypatch.setattr(pr_suite_grader, "grade_pr_suite_prediction", fake_grade_pr_suite_prediction)
    request_write = nrc.write_native_runner_request(
        run_id="native-default-grade",
        output_root=tmp_path / "requests",
        split="explore",
        candidate_packet={
            "candidate_id": "cand",
            "task_predictions": {"pr::pallets/click#3208": "diff --git a/x b/x\n"},
        },
        task_allocation={"allocation_id": "explore-a", "task_ids": ["pr::pallets/click#3208"]},
        worker_config={"taskbed_db": str(tmp_path / "taskbed.db")},
    )

    manifest = nrc.run_native_runner_request(
        request_dir=request_write["request_dir"],
        result_root=tmp_path / "worker-result",
    )

    assert manifest["written_receipt_count"] == 1
    assert manifest["resume_plan_after"]["completed_task_ids"] == ["pr::pallets/click#3208"]
    receipt = _read_json(next((tmp_path / "worker-result" / "task_receipts").glob("*.json")))
    assert receipt["grader"] == "pr_suite"
    assert receipt["resolved"] is True


def test_is_swebench_task_id_detects_standard_ids() -> None:
    assert nrc.is_swebench_task_id("django__django-12209") is True
    assert nrc.is_swebench_task_id("sympy__sympy-22914") is True
    assert nrc.is_swebench_task_id("pr::pallets/click#3208") is False
    assert nrc.is_swebench_task_id("plain-task") is False


def test_default_native_grade_dispatches_swebench_inline_instance(monkeypatch) -> None:
    captured: dict = {}

    def fake_verify_prediction(instance, model_patch, **kwargs):
        captured["instance"] = dict(instance)
        captured["model_patch"] = model_patch
        captured["kwargs"] = kwargs
        return True

    monkeypatch.setattr(swebench_real, "verify_prediction", fake_verify_prediction)
    result = nrc.default_native_grade(
        {
            "task_id": "django__django-12209",
            "candidate_packet": {
                "candidate_id": "cand",
                "task_predictions": {"django__django-12209": "diff --git a/x b/x\n"},
                "task_instances": {"django__django-12209": {"instance_id": "django__django-12209", "repo": "django/django"}},
            },
            "request": {
                "run_id": "native-run",
                "task_ids": ["django__django-12209"],
                "worker_config": {
                    "grade_timeout": 321,
                    "swebench_namespace": "swebench",
                    "swebench_run_id": "unit-swebench-run",
                },
            },
        }
    )

    assert result["status"] == "resolved"
    assert result["resolved"] is True
    assert result["grader"] == "swebench"
    assert result["swebench_run_id"] == "unit-swebench-run"
    assert captured["instance"]["instance_id"] == "django__django-12209"
    assert captured["model_patch"] == "diff --git a/x b/x\n"
    assert captured["kwargs"]["timeout"] == 321
    assert captured["kwargs"]["namespace"] == "swebench"


def test_default_native_grade_loads_swebench_instance_when_not_embedded(monkeypatch) -> None:
    captured: dict = {}

    def fake_verified_instances(*, instance_ids):
        captured["instance_ids"] = instance_ids
        return [{"instance_id": instance_ids[0], "repo": "sympy/sympy"}]

    def fake_verify_prediction(instance, model_patch, **_kwargs):
        captured["instance"] = dict(instance)
        captured["model_patch"] = model_patch
        return False

    monkeypatch.setattr(swebench_real, "verified_instances", fake_verified_instances)
    monkeypatch.setattr(swebench_real, "verify_prediction", fake_verify_prediction)
    result = nrc.default_native_grade(
        {
            "task_id": "sympy__sympy-22914",
            "candidate_packet": {
                "candidate_id": "cand",
                "task_predictions": {"sympy__sympy-22914": "diff --git a/y b/y\n"},
            },
            "request": {"run_id": "native-run", "task_ids": ["sympy__sympy-22914"], "worker_config": {}},
        }
    )

    assert captured["instance_ids"] == ["sympy__sympy-22914"]
    assert captured["instance"]["repo"] == "sympy/sympy"
    assert captured["model_patch"] == "diff --git a/y b/y\n"
    assert result["status"] == "unresolved"
    assert result["resolved"] is False
    assert result["grader"] == "swebench"


def test_run_native_runner_request_writes_grade_only_receipts_and_syncs(tmp_path: Path) -> None:
    request_write = nrc.write_native_runner_request(
        run_id="native-worker-1",
        output_root=tmp_path / "requests",
        split="explore",
        candidate_packet={"candidate_id": "candidate-a", "task_predictions": {"task-a": "patch"}},
        task_allocation={"allocation_id": "explore-a", "task_ids": ["task-a", "task-b"]},
    )
    calls: list[dict] = []

    def fake_grade(payload: dict) -> dict:
        calls.append(payload)
        return {
            "status": "resolved" if payload["task_id"] == "task-a" else "unresolved",
            "resolved": payload["task_id"] == "task-a",
            "grade_seconds": 1.25,
        }

    manifest = nrc.run_native_runner_request(
        request_dir=request_write["request_dir"],
        result_root=tmp_path / "worker-result",
        grade_fn=fake_grade,
        worker_label="unit-x86-worker",
    )

    assert [call["task_id"] for call in calls] == ["task-a", "task-b"]
    assert manifest["schema"] == nrc.WORKER_RESULT_SCHEMA
    assert manifest["written_receipt_count"] == 2
    assert manifest["source_of_truth_mutated"] is False
    assert manifest["live_apply_performed"] is False
    assert manifest["promotion_gate"] == nrc.PROMOTION_GATE
    receipt_files = sorted((tmp_path / "worker-result" / "task_receipts").glob("*.json"))
    assert len(receipt_files) == 2
    receipt = _read_json(receipt_files[0])
    assert receipt["schema"] == nrc.TASK_RECEIPT_SCHEMA
    assert receipt["worker_label"] == "unit-x86-worker"
    assert receipt["source_of_truth_mutated"] is False

    sync_manifest = nrc.sync_remote_receipts(
        remote_result_root=tmp_path / "worker-result",
        local_sync_root=tmp_path / "synced",
        expected_run_id="native-worker-1",
    )
    assert sync_manifest["receipt_count"] == 2
    assert sync_manifest["archive_fitness_mutated"] is False


def test_run_native_runner_request_skips_completed_receipts_on_resume(tmp_path: Path) -> None:
    request_write = nrc.write_native_runner_request(
        run_id="native-worker-2",
        output_root=tmp_path / "requests",
        split="explore",
        candidate_packet={"candidate_id": "candidate-a"},
        task_allocation={"allocation_id": "explore-a", "task_ids": ["task-a", "task-b"]},
    )
    result_root = tmp_path / "worker-result"
    receipt_dir = result_root / "task_receipts"
    receipt_dir.mkdir(parents=True)
    (receipt_dir / "task-a-existing.json").write_text(
        json.dumps(
            {
                "schema": nrc.TASK_RECEIPT_SCHEMA,
                "run_id": "native-worker-2",
                "candidate_id": "candidate-a",
                "task_id": "task-a",
                "status": "resolved",
                "resolved": True,
                "source_of_truth_mutated": False,
                "promotion_gate": nrc.PROMOTION_GATE,
            }
        ),
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_grade(payload: dict) -> dict:
        calls.append(payload["task_id"])
        return {"status": "unresolved", "resolved": False}

    manifest = nrc.run_native_runner_request(
        request_dir=request_write["request_dir"],
        result_root=result_root,
        grade_fn=fake_grade,
    )

    assert calls == ["task-b"]
    assert manifest["existing_receipt_count"] == 1
    assert manifest["written_receipt_count"] == 1
    assert manifest["resume_plan_before"]["completed_task_ids"] == ["task-a"]
    assert manifest["resume_plan_after"]["completed_task_ids"] == ["task-a", "task-b"]


def test_run_native_runner_request_receipts_infra_failure_then_retries(tmp_path: Path) -> None:
    request_write = nrc.write_native_runner_request(
        run_id="native-worker-3",
        output_root=tmp_path / "requests",
        split="explore",
        candidate_packet={"candidate_id": "candidate-a"},
        task_allocation={"allocation_id": "explore-a", "task_ids": ["task-a"]},
        max_infra_retries=2,
    )
    result_root = tmp_path / "worker-result"
    calls = 0

    def flaky_grade(payload: dict) -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("docker unavailable")
        return {"status": "resolved", "resolved": True}

    first = nrc.run_native_runner_request(
        request_dir=request_write["request_dir"],
        result_root=result_root,
        grade_fn=flaky_grade,
    )
    assert first["written_receipt_count"] == 1
    assert first["resume_plan_after"]["remaining_tasks"] == [
        {"task_id": "task-a", "next_attempt": 2, "prior_infra_failures": 1}
    ]

    second = nrc.run_native_runner_request(
        request_dir=request_write["request_dir"],
        result_root=result_root,
        grade_fn=flaky_grade,
    )
    assert calls == 2
    assert second["written_receipt_count"] == 1
    assert second["resume_plan_after"]["completed_task_ids"] == ["task-a"]
    assert second["resume_plan_after"]["remaining_tasks"] == []


def test_run_native_runner_request_refuses_mutating_request_authority(tmp_path: Path) -> None:
    request_write = nrc.write_native_runner_request(
        run_id="native-worker-4",
        output_root=tmp_path / "requests",
        split="explore",
        candidate_packet={"candidate_id": "candidate-a"},
        task_allocation={"allocation_id": "explore-a", "task_ids": ["task-a"]},
    )
    request_path = Path(request_write["request_path"])
    request = _read_json(request_path)
    request["authority"]["live_apply_allowed"] = "true"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    with pytest.raises(ValueError, match="request_authority:live_apply_allowed"):
        nrc.run_native_runner_request(
            request_dir=request_write["request_dir"],
            result_root=tmp_path / "worker-result",
            grade_fn=lambda _payload: {"status": "resolved"},
        )


def test_orchestrate_native_request_allocates_from_taskbed_and_is_grade_only(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    _seed_taskbed(db, ["pr::pallets/click#3208", "pr::pallets/werkzeug#3147", "pr::pallets/click#3211"])

    orchestration = nrc.orchestrate_native_request(
        run_id="native-orch-1",
        candidate_packet={"candidate_id": "scaffold_window_9000", "genome": {"arm": "verify_chain", "window_chars": 9000}},
        split="explore",
        count=2,
        epoch_id="epoch-orch",
        output_root=tmp_path / "runs",
        taskbed_db=db,
    )

    assert orchestration["schema"] == nrc.ORCHESTRATION_SCHEMA
    assert orchestration["split"] == "explore"
    assert orchestration["source_of_truth_mutated"] is False
    assert orchestration["promotion_gate"] == nrc.PROMOTION_GATE
    # allocation came from the real ledger (2 distinct fresh tasks)
    assert orchestration["allocation_receipt"]["task_count"] == 2
    assert len(orchestration["allocation_receipt"]["task_ids"]) == 2

    request_dir = Path(orchestration["request"]["request_dir"])
    request = _read_json(request_dir / "native_runner_request.json")
    assert request["task_ids"] == orchestration["allocation_receipt"]["task_ids"]
    assert request["authority"]["live_apply_allowed"] is False
    assert (request_dir / "orchestration.json").exists()


def test_orchestrate_native_request_keeps_explore_and_confirm_separated(tmp_path: Path) -> None:
    # The ledger must not hand a CONFIRM allocation any task already used for
    # EXPLORE; the orchestrator inherits that separation for free.
    db = tmp_path / "taskbed.db"
    _seed_taskbed(db, ["fresh-0", "fresh-1", "fresh-2"])

    explore = nrc.orchestrate_native_request(
        run_id="native-explore",
        candidate_packet={"candidate_id": "cand"},
        split="explore",
        count=1,
        epoch_id="epoch-sep",
        output_root=tmp_path / "runs",
        taskbed_db=db,
    )
    confirm = nrc.orchestrate_native_request(
        run_id="native-confirm",
        candidate_packet={"candidate_id": "cand"},
        split="confirm",
        count=2,
        min_count=2,
        epoch_id="epoch-sep",
        output_root=tmp_path / "runs",
        taskbed_db=db,
    )

    explore_ids = set(explore["allocation_receipt"]["task_ids"])
    confirm_ids = set(confirm["allocation_receipt"]["task_ids"])
    assert explore_ids.isdisjoint(confirm_ids)
    assert confirm["allocation_receipt"]["explore_separate_from_confirm"] is True


def test_orchestrate_then_run_worker_end_to_end(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    _seed_taskbed(db, ["fresh-0", "fresh-1"])

    orchestration = nrc.orchestrate_native_request(
        run_id="native-e2e",
        candidate_packet={"candidate_id": "cand"},
        split="explore",
        count=2,
        epoch_id="epoch-e2e",
        output_root=tmp_path / "runs",
        taskbed_db=db,
    )
    request_dir = orchestration["request"]["request_dir"]

    manifest = nrc.run_native_runner_request(
        request_dir=request_dir,
        result_root=tmp_path / "worker-result",
        grade_fn=lambda payload: {"status": "resolved", "resolved": True},
    )
    assert manifest["written_receipt_count"] == 2
    assert manifest["resume_plan_after"]["remaining_tasks"] == []
    assert sorted(manifest["resume_plan_after"]["completed_task_ids"]) == ["fresh-0", "fresh-1"]


def test_cli_execute_request_dir_runs_default_worker(tmp_path: Path) -> None:
    request_write = nrc.write_native_runner_request(
        run_id="native-cli-worker",
        output_root=tmp_path / "requests",
        split="explore",
        candidate_packet={"candidate_id": "cand", "patch": "diff --git a/x b/x\n"},
        task_allocation={"allocation_id": "alloc", "task_ids": ["task-a"]},
    )
    result_root = tmp_path / "result"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "dharma_swarm.forge_v1.forge_v2.native_runner_contract",
            "--execute-request-dir",
            request_write["request_dir"],
            "--result-root",
            str(result_root),
            "--json",
        ],
        cwd="/Users/dhyana/ds_forge_spine_v0",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stderr
    manifest = json.loads(proc.stdout)
    assert manifest["schema"] == nrc.WORKER_RESULT_SCHEMA
    assert manifest["written_receipt_count"] == 1
    assert manifest["source_of_truth_mutated"] is False
    receipt = _read_json(next((result_root / "task_receipts").glob("*.json")))
    assert receipt["status"] == "unresolved"
    assert receipt["grade_error"] == "unsupported_task_family"


def test_cli_orchestrated_dry_run_syncs_and_resumes_without_predictions(tmp_path: Path) -> None:
    """Level-0 native proof: real taskbed allocation, no model patch, no grading mutation.

    Missing predictions are intentionally used here as the safe dry-run candidate:
    the default worker must emit deterministic unresolved receipts, treat those
    receipts as terminal for resume, and let the local orchestrator sync them as
    grade-only evidence.
    """
    db = tmp_path / "taskbed.db"
    _seed_taskbed(db, ["pr::pallets/click#3420", "pr::pallets/click#3534"])
    requests_root = tmp_path / "requests"
    result_root = tmp_path / "worker-result"

    orchestrate = subprocess.run(
        [
            sys.executable,
            "-m",
            "dharma_swarm.forge_v1.forge_v2.native_runner_contract",
            "--run-id",
            "native-cli-dry-proof",
            "--candidate-id",
            "dry_missing_predictions",
            "--split",
            "explore",
            "--count",
            "2",
            "--epoch-id",
            "epoch-native-dry-proof",
            "--taskbed-db",
            str(db),
            "--output-root",
            str(requests_root),
            "--json",
        ],
        cwd="/Users/dhyana/ds_forge_spine_v0",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert orchestrate.returncode == 0, orchestrate.stderr
    orchestration = json.loads(orchestrate.stdout)
    request_dir = orchestration["request"]["request_dir"]
    assert orchestration["allocation_receipt"]["task_count"] == 2

    first = subprocess.run(
        [
            sys.executable,
            "-m",
            "dharma_swarm.forge_v1.forge_v2.native_runner_contract",
            "--execute-request-dir",
            request_dir,
            "--result-root",
            str(result_root),
            "--json",
        ],
        cwd="/Users/dhyana/ds_forge_spine_v0",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert first.returncode == 0, first.stderr
    first_manifest = json.loads(first.stdout)
    assert first_manifest["written_receipt_count"] == 2
    assert first_manifest["resume_plan_after"]["remaining_tasks"] == []
    assert sorted(first_manifest["resume_plan_after"]["completed_task_ids"]) == [
        "pr::pallets/click#3420",
        "pr::pallets/click#3534",
    ]

    second = subprocess.run(
        [
            sys.executable,
            "-m",
            "dharma_swarm.forge_v1.forge_v2.native_runner_contract",
            "--execute-request-dir",
            request_dir,
            "--result-root",
            str(result_root),
            "--json",
        ],
        cwd="/Users/dhyana/ds_forge_spine_v0",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert second.returncode == 0, second.stderr
    second_manifest = json.loads(second.stdout)
    assert second_manifest["existing_receipt_count"] == 2
    assert second_manifest["written_receipt_count"] == 0
    assert second_manifest["resume_plan_before"]["remaining_tasks"] == []

    receipts = sorted((result_root / "task_receipts").glob("*.json"))
    assert len(receipts) == 2
    for path in receipts:
        receipt = _read_json(path)
        assert receipt["status"] == "unresolved"
        assert receipt["grade_error"] == "missing_task_prediction"
        assert receipt["source_of_truth_mutated"] is False
        assert receipt["live_apply_performed"] is False
        assert receipt["archive_fitness_mutated"] is False
        assert receipt["promotion_gate"] == nrc.PROMOTION_GATE

    sync_manifest = nrc.sync_remote_receipts(
        remote_result_root=result_root,
        local_sync_root=tmp_path / "synced",
        expected_run_id="native-cli-dry-proof",
    )
    assert sync_manifest["schema"] == nrc.SYNC_SCHEMA
    assert sync_manifest["receipt_count"] == 2
    assert (Path(sync_manifest["local_sync_dir"]) / "sync_manifest.json").exists()
    assert sync_manifest["source_of_truth_mutated"] is False


def test_orchestrate_native_request_blocks_underpowered_confirm(tmp_path: Path) -> None:
    db = tmp_path / "taskbed.db"
    _seed_taskbed(db, ["fresh-0"])

    with pytest.raises(taskbed_ledger.TaskbedLedgerError, match="insufficient_confirm_tasks"):
        nrc.orchestrate_native_request(
            run_id="native-underpowered",
            candidate_packet={"candidate_id": "cand"},
            split="confirm",
            count=2,
            min_count=2,
            epoch_id="epoch-under",
            output_root=tmp_path / "runs",
            taskbed_db=db,
        )


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


def test_plan_resume_converges_for_unmodeled_statuses() -> None:
    # A task whose receipts use a status outside the completed/quarantine/infra
    # vocabularies (e.g. a worker "error" or a real forge closeout) must still
    # count toward the retry budget so resume terminates instead of returning it
    # as fresh forever.
    request = {
        "run_id": "native-smoke-1",
        "candidate_id": "candidate-a",
        "task_ids": ["task-weird"],
        "max_infra_retries": 2,
    }
    receipts = [{"task_id": "task-weird", "status": "error"} for _ in range(3)]
    plan = nrc.plan_resume(request, receipts)

    assert plan["remaining_tasks"] == []
    assert plan["quarantined_tasks"] == [
        {
            "task_id": "task-weird",
            "reason": "attempts_exhausted",
            "attempts": 3,
            "infra_failures": 0,
            "statuses": ["error", "error", "error"],
            "max_infra_retries": 2,
        }
    ]


def test_plan_resume_counts_unmodeled_attempts_toward_budget_before_exhaustion() -> None:
    # Under budget, an unmodeled prior attempt is retried with an advanced
    # attempt counter (not reset to 1), so progress is bounded and auditable.
    request = {
        "run_id": "native-smoke-1",
        "candidate_id": "candidate-a",
        "task_ids": ["task-weird"],
        "max_infra_retries": 2,
    }
    plan = nrc.plan_resume(request, [{"task_id": "task-weird", "status": "error"}])

    assert plan["quarantined_tasks"] == []
    assert plan["remaining_tasks"] == [
        {"task_id": "task-weird", "next_attempt": 2, "prior_infra_failures": 0}
    ]


def test_validate_no_source_mutation_fails_closed_on_nonbool_truthy() -> None:
    # A remote worker's JSON receipt may encode booleans as strings/ints. The
    # guard must fail closed on any positive assertion, not only Python True.
    for flag in ("source_of_truth_mutated", "live_apply_performed", "archive_fitness_mutated"):
        for truthy in ("true", "True", "1", "yes", 1):
            with pytest.raises(ValueError):
                nrc.validate_no_source_mutation({flag: truthy}, label="probe")


def test_validate_no_source_mutation_allows_explicit_false_forms() -> None:
    # Falsey / absent claims remain allowed so honest receipts pass.
    for value in (False, "false", "no", 0, ""):
        nrc.validate_no_source_mutation(
            {
                "source_of_truth_mutated": value,
                "live_apply_performed": value,
                "archive_fitness_mutated": value,
                "promotion_gate": nrc.PROMOTION_GATE,
            },
            label="probe",
        )


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


def test_sync_remote_receipts_refuses_string_encoded_mutation_claim(tmp_path: Path) -> None:
    # Real workers serialize JSON; a string "true" must not slip past the sync
    # boundary just because it is not a Python bool.
    remote = tmp_path / "remote" / "native-run-1"
    remote.mkdir(parents=True)
    (remote / "result_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "native-run-1",
                "source_of_truth_mutated": "true",
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
    assert manifest["archive_fitness_mutated"] is False
    assert manifest["promotion_gate"] == nrc.PROMOTION_GATE
