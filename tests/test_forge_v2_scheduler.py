from __future__ import annotations

import json

import pytest

from dharma_swarm.forge_v1.forge_v2 import scheduler, taskbed_ledger


def _fake_receipt(closeout: str = "inconclusive_low_power", cost: float = 0.01) -> dict:
    invalid = closeout == "invalid_budget"
    return {
        "closeout": closeout,
        "n_pairs": 1,
        "contrast_vs_class_null": {"n": 1, "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
        "split_contrasts": {"explore": {"n": 0}, "confirm": {"n": 1}},
        "critic_verdict": {"ran": False},
        "contamination_state": {"state": "possible_pretrain"},
        "budget_matched_proof": {"any_invalid": closeout == "invalid_budget"},
        "attempts": [
            {
                "task_id": "a",
                "split": "confirm",
                "arm": "self_moa",
                "class_null": "self_moa",
                "replicate": 0,
                "resolved": False,
                "budget": {"total_cost_usd": cost / 2, "spent_tokens": 100, "cap_tokens": 60000},
                "invalid": invalid,
                "invalid_reason": "synthetic invalid" if invalid else None,
            },
            {
                "task_id": "a",
                "split": "confirm",
                "arm": "verify_chain",
                "class_null": "self_moa",
                "replicate": 0,
                "resolved": False,
                "budget": {"total_cost_usd": cost / 2, "spent_tokens": 100, "cap_tokens": 60000},
                "invalid": invalid,
                "invalid_reason": "synthetic invalid" if invalid else None,
            },
        ],
        "next_experiment": "test",
    }


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _task(task_id: str, contamination_state: str = "fresh_heldout") -> dict:
    return {
        "task_id": task_id,
        "created_at": "2026-07-01T00:00:00Z",
        "contamination_state": contamination_state,
        "provenance": {"contamination_state": contamination_state},
    }


def test_cost_from_attempts_sums_attempt_budgets() -> None:
    assert scheduler.cost_from_attempts(_fake_receipt(cost=0.123456)) == 0.123456


def test_stop_reason_order_and_caps() -> None:
    assert scheduler.stop_reason(
        completed=3,
        invalid_runs=0,
        total_cost_usd=0.0,
        start=0.0,
        max_campaigns=3,
        invalid_run_cap=2,
        cost_cap_usd=1.0,
        duration_hours=None,
    ) == scheduler.STOP_MAX_CAMPAIGNS

    assert scheduler.stop_reason(
        completed=1,
        invalid_runs=2,
        total_cost_usd=0.0,
        start=0.0,
        max_campaigns=10,
        invalid_run_cap=2,
        cost_cap_usd=1.0,
        duration_hours=None,
    ) == scheduler.STOP_INVALID

    assert scheduler.stop_reason(
        completed=1,
        invalid_runs=0,
        total_cost_usd=1.0,
        start=0.0,
        max_campaigns=10,
        invalid_run_cap=2,
        cost_cap_usd=1.0,
        duration_hours=None,
    ) == scheduler.STOP_COST


def test_scheduler_dry_run_writes_outer_receipts(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "RUN_ROOT", tmp_path)

    state = scheduler.run_scheduler(
        instances=["a", "b"],
        n_explore=1,
        replicates=2,
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
        label="dry",
        max_campaigns=2,
        duration_hours=None,
        total_budget_usd=5.0,
        invalid_run_cap=2,
        sleep_seconds=0.0,
        dry_run=True,
    )

    assert state["stop_reason"] == scheduler.STOP_MAX_CAMPAIGNS
    assert state["completed_campaigns"] == 2
    assert state["total_cost_usd"] == 0.0

    run_dir = next(tmp_path.iterdir())
    decision = json.loads((run_dir / "decision_record.json").read_text())
    ledger = (run_dir / "campaign_ledger.jsonl").read_text().strip().splitlines()
    assert decision["stop_reason"] == scheduler.STOP_MAX_CAMPAIGNS
    assert len(ledger) == 5
    assert set(scheduler.CANONICAL_PACKET_FILES).issubset({path.name for path in run_dir.iterdir()})
    assert json.loads((run_dir / "run_manifest.json").read_text())["task_count"] == 2
    assert len(_read_jsonl(run_dir / "task_manifest.jsonl")) == 4
    assert len(_read_jsonl(run_dir / "results.jsonl")) == 2
    assert "# Control Comparison" in (run_dir / "control_comparison.md").read_text()
    assert "does not by itself prove promotion" in (run_dir / "decision_record.md").read_text()


def test_scheduler_canonical_packet_uses_attempt_rows(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "RUN_ROOT", tmp_path)

    state = scheduler.run_scheduler(
        instances=["a"],
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
        arms=["verify_chain"],
        mix_models=[],
        label="packet",
        max_campaigns=1,
        duration_hours=None,
        total_budget_usd=5.0,
        invalid_run_cap=2,
        sleep_seconds=0.0,
        runner=lambda *_args, **_kwargs: _fake_receipt(cost=0.02),
    )

    run_dir = next(tmp_path.iterdir())
    assert state["canonical_packet"]["files"] == list(scheduler.CANONICAL_PACKET_FILES)
    assert state["canonical_packet"]["result_rows"] == 2
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    roster = json.loads((run_dir / "model_roster.json").read_text())
    results = _read_jsonl(run_dir / "results.jsonl")
    budgets = _read_jsonl(run_dir / "budget_ledger.jsonl")
    tasks = _read_jsonl(run_dir / "task_manifest.jsonl")

    assert manifest["schema_version"] == "forge_v2.scheduler_canonical_packet.v1"
    assert manifest["status"] == "inconclusive_low_power"
    assert manifest["authority"]["archive_fitness_mutated"] is False
    assert {row["arm"] for row in roster["arms"]} == {"same_budget_self_moa", "self_moa", "verify_chain"}
    assert {row["arm"] for row in results} == {"self_moa", "verify_chain"}
    assert all(row["candidate_ok"] is True for row in results)
    assert sum(row["actual_cost_usd"] for row in budgets) == 0.02
    assert tasks == [
        {
            "campaign_index": 1,
            "instance_id": "a",
            "schema": "forge_v2.task_manifest_row.v1",
            "source": "forge_v2.scheduler",
            "split": "confirm",
            "task_id": "a",
        }
    ]


def test_scheduler_confirm_can_be_allocated_from_taskbed_ledger(tmp_path, monkeypatch) -> None:
    run_root = tmp_path / "runs"
    db = tmp_path / "taskbed.db"
    monkeypatch.setattr(scheduler, "RUN_ROOT", run_root)
    taskbed_ledger.register_tasks(
        [_task("fresh-0"), _task("fresh-1")],
        db_path=db,
        source="post_cutoff_pr_suite",
        taskbed="fresh_pr_suite",
    )

    state = scheduler.run_scheduler(
        instances=["legacy"],
        n_explore=99,
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
        label="confirm",
        max_campaigns=1,
        duration_hours=None,
        total_budget_usd=5.0,
        invalid_run_cap=2,
        sleep_seconds=0.0,
        dry_run=True,
        epoch_id="epoch-1",
        taskbed_db=db,
        taskbed_split="confirm",
        taskbed_count=2,
        taskbed_min_confirm_count=2,
        taskbed_allocation_id="confirm-alloc",
    )

    run_dir = next(run_root.iterdir())
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    tasks = _read_jsonl(run_dir / "task_manifest.jsonl")
    assert state["config"]["instances"] == ["fresh-0", "fresh-1"]
    assert state["campaigns"][0]["n_explore"] == 0
    assert state["taskbed_allocation"]["promotion_eligible_taskbed"] is True
    assert manifest["taskbed_allocation"]["allocation_id"] == "confirm-alloc"
    assert {row["split"] for row in tasks} == {"confirm"}
    assert {row["taskbed_allocation_id"] for row in tasks} == {"confirm-alloc"}


def test_scheduler_explore_can_be_allocated_from_taskbed_ledger(tmp_path, monkeypatch) -> None:
    run_root = tmp_path / "runs"
    db = tmp_path / "taskbed.db"
    monkeypatch.setattr(scheduler, "RUN_ROOT", run_root)
    taskbed_ledger.register_tasks(
        [_task("public-0", "possible_pretrain"), _task("public-1", "possible_pretrain")],
        db_path=db,
        source="public_swebench",
        taskbed="public_swebench",
    )

    state = scheduler.run_scheduler(
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
        arms=["verify_chain"],
        mix_models=[],
        label="explore",
        max_campaigns=1,
        duration_hours=None,
        total_budget_usd=5.0,
        invalid_run_cap=2,
        sleep_seconds=0.0,
        dry_run=True,
        epoch_id="epoch-1",
        taskbed_db=db,
        taskbed_split="explore",
        taskbed_count=2,
        taskbed_allocation_id="explore-alloc",
    )

    run_dir = next(run_root.iterdir())
    tasks = _read_jsonl(run_dir / "task_manifest.jsonl")
    assert state["campaigns"][0]["n_explore"] == 2
    assert state["taskbed_allocation"]["split"] == "explore"
    assert state["taskbed_allocation"]["promotion_eligible_taskbed"] is False
    assert {row["split"] for row in tasks} == {"explore"}


def test_scheduler_refuses_adaptive_sampling_with_taskbed_allocation(tmp_path, monkeypatch) -> None:
    run_root = tmp_path / "runs"
    db = tmp_path / "taskbed.db"
    monkeypatch.setattr(scheduler, "RUN_ROOT", run_root)
    taskbed_ledger.register_tasks([_task("fresh-0")], db_path=db)

    with pytest.raises(ValueError, match="adaptive sampling is disabled"):
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
            arms=["verify_chain"],
            mix_models=[],
            label="refuse",
            max_campaigns=1,
            duration_hours=None,
            total_budget_usd=5.0,
            invalid_run_cap=2,
            sleep_seconds=0.0,
            dry_run=True,
            adaptive=True,
            taskbed_db=db,
            taskbed_split="confirm",
            taskbed_count=1,
            taskbed_min_confirm_count=1,
            taskbed_allocation_id="should-not-allocate",
        )
    assert taskbed_ledger.allocation_rows("should-not-allocate", db_path=db) == []


def test_scheduler_stops_after_invalid_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "RUN_ROOT", tmp_path)

    def fake_runner(*args, **kwargs):
        return _fake_receipt(closeout="invalid_budget", cost=0.02)

    state = scheduler.run_scheduler(
        instances=["a"],
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
        arms=["verify_chain"],
        mix_models=[],
        label="invalid",
        max_campaigns=10,
        duration_hours=None,
        total_budget_usd=5.0,
        invalid_run_cap=2,
        sleep_seconds=0.0,
        runner=fake_runner,
    )

    assert state["stop_reason"] == scheduler.STOP_INVALID
    assert state["completed_campaigns"] == 2
    assert state["invalid_runs"] == 2


def test_scheduler_rotates_arms_and_adapts_from_attempts(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "RUN_ROOT", tmp_path)
    seen = []

    def fake_runner(instances, *args, **kwargs):
        arm = kwargs["arm"]
        seen.append((arm, tuple(instances)))
        attempts = []
        for task in instances:
            self_pass = task == "easy"
            arm_pass = task == "hard" and arm == "mixed_moa"
            for attempt_arm, resolved in (("self_moa", self_pass), (arm, arm_pass)):
                attempts.append(
                    {
                        "task_id": task,
                        "split": "explore",
                        "arm": attempt_arm,
                        "class_null": "self_moa",
                        "replicate": 0,
                        "resolved": resolved,
                        "budget": {"total_cost_usd": 0.001},
                    }
                )
        return {
            "arm": arm,
            "class_null": "self_moa",
            "closeout": "measured_negative",
            "n_pairs": len(instances),
            "contrast_vs_class_null": {"n": len(instances), "mean": 0.0, "lower": 0.0, "upper": 0.0, "p_le_0": 1.0},
            "split_contrasts": {},
            "critic_verdict": {"ran": False},
            "contamination_state": {"state": "possible_pretrain"},
            "budget_matched_proof": {"any_invalid": False},
            "attempts": attempts,
            "next_experiment": "test",
        }

    state = scheduler.run_scheduler(
        instances=["easy", "hard"],
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
        arms=["verify_chain", "mixed_moa"],
        mix_models=["glm-5.2", "moonshotai/kimi-k2.6"],
        label="adaptive",
        max_campaigns=2,
        duration_hours=None,
        total_budget_usd=5.0,
        invalid_run_cap=2,
        sleep_seconds=0.0,
        instance_pool=["easy", "hard", "new"],
        adaptive=True,
        adaptive_target_count=2,
        runner=fake_runner,
    )

    assert state["stop_reason"] == scheduler.STOP_MAX_CAMPAIGNS
    assert seen[0][0] == "verify_chain"
    assert seen[1][0] == "mixed_moa"
    assert seen[1][1] == ("hard", "new")


def test_scheduler_ingests_learning_after_each_campaign(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "RUN_ROOT", tmp_path)
    ingested = []

    def fake_learning_ingester(run_dir, *, store_root, epoch_id):
        ingested.append((run_dir.name, store_root, epoch_id))
        assert (run_dir / "campaign_meta_report.json").exists()
        return {
            "ok": True,
            "run_id": run_dir.name,
            "n_signals": 1,
            "store": {"n_new": len(ingested)},
        }

    state = scheduler.run_scheduler(
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
        label="learn",
        max_campaigns=2,
        duration_hours=None,
        total_budget_usd=5.0,
        invalid_run_cap=2,
        sleep_seconds=0.0,
        dry_run=True,
        ingest_learning=True,
        learning_store_root=tmp_path / "learning",
        epoch_id="overnight_test",
        learning_ingester=fake_learning_ingester,
    )

    assert len(ingested) == 2
    assert all(row[1] == tmp_path / "learning" for row in ingested)
    assert all(row[2] == "overnight_test" for row in ingested)
    assert state["learning_spine"]["ingests"] == 2
    assert state["learning_spine"]["failures"] == 0

    run_dir = next(p for p in tmp_path.iterdir() if p.is_dir() and p.name.startswith("learn_"))
    ledger_events = [
        json.loads(line)["event"]
        for line in (run_dir / "campaign_ledger.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert ledger_events.count("learning_spine_ingest") == 2
