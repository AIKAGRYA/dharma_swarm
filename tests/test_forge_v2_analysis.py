from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.forge_v1.forge_v2.analysis import (
    build_campaign_report,
    choose_adaptive_instances,
    write_campaign_report,
)


def _attempt(task: str, arm: str, resolved: bool, *, campaign: int = 1, replicate: int = 0) -> dict:
    return {
        "task_id": task,
        "split": "confirm",
        "arm": arm,
        "class_null": "self_moa",
        "replicate": replicate,
        "resolved": resolved,
        "budget": {"total_cost_usd": 0.001},
        "_campaign_index": campaign,
    }


def test_choose_adaptive_instances_prefers_hard_then_unobserved() -> None:
    attempts = [
        _attempt("easy", "self_moa", True),
        _attempt("easy", "verify_chain", True),
        _attempt("hard", "self_moa", False),
        _attempt("hard", "verify_chain", False),
    ]

    selected = choose_adaptive_instances(
        ["easy", "hard", "fresh"],
        attempts,
        target_count=2,
    )

    assert selected == ["hard", "fresh"]


def test_campaign_report_aggregates_child_decision_records(tmp_path: Path) -> None:
    child = tmp_path / "forge_root" / "adaptive_c0001_123"
    child.mkdir(parents=True)
    decision = {
        "arm": "verify_chain",
        "class_null": "self_moa",
        "closeout": "measured_negative",
        "attempts": [
            _attempt("easy", "self_moa", True),
            _attempt("easy", "verify_chain", False),
            _attempt("hard", "self_moa", False),
            _attempt("hard", "verify_chain", False),
        ],
    }
    (child / "decision_record.json").write_text(json.dumps(decision), encoding="utf-8")

    run_dir = tmp_path / "scheduler" / "adaptive_20260630T000000Z"
    run_dir.mkdir(parents=True)
    state = {
        "label": "adaptive",
        "completed_campaigns": 1,
        "invalid_runs": 0,
        "total_cost_usd": 0.01,
        "stop_reason": "max_campaigns",
        "config": {"instances": ["easy", "hard"], "instance_pool": ["easy", "hard", "fresh"]},
        "campaigns": [
            {
                "campaign_label": "adaptive_c0001",
                "artifact_dir": str(child),
                "closeout": "measured_negative",
            }
        ],
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    report = build_campaign_report(run_dir, receipt_root=tmp_path / "forge_root")
    json_path, md_path = write_campaign_report(report, run_dir)

    assert report["decision_record_count"] == 1
    assert report["contrasts"]["verify_chain"]["overall"]["mean"] == -0.5
    assert report["task_stats"]["hard"]["hard_for_null"] is True
    assert "mixed_moa" in report["next_policy"]["recommended_arms"]
    assert json_path.exists()
    assert md_path.exists()


def test_adaptive_report_suppresses_positive_promotion(tmp_path: Path) -> None:
    child = tmp_path / "forge_root" / "adaptive_c0001_123"
    child.mkdir(parents=True)
    decision = {
        "arm": "mixed_moa",
        "class_null": "self_moa",
        "closeout": "positive_lift_candidate",
        "attempts": [
            _attempt("hard-a", "self_moa", False, replicate=0),
            _attempt("hard-a", "mixed_moa", True, replicate=0),
            _attempt("hard-b", "self_moa", False, replicate=0),
            _attempt("hard-b", "mixed_moa", True, replicate=0),
            _attempt("hard-c", "self_moa", False, replicate=0),
            _attempt("hard-c", "mixed_moa", True, replicate=0),
        ],
    }
    (child / "decision_record.json").write_text(json.dumps(decision), encoding="utf-8")

    run_dir = tmp_path / "scheduler" / "adaptive_20260630T000000Z"
    run_dir.mkdir(parents=True)
    state = {
        "completed_campaigns": 1,
        "config": {"instances": ["hard-a", "hard-b", "hard-c"], "adaptive": True},
        "campaigns": [{"campaign_label": "adaptive_c0001", "artifact_dir": str(child)}],
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    report = build_campaign_report(run_dir, receipt_root=tmp_path / "forge_root")

    assert report["inference_scope"] == "explore_only_no_promotion"
    assert report["promotion_policy"]["positive_promotion_allowed"] is False
    assert report["learning_state"]["positive_lift_candidates"] == []
    assert report["contrasts"]["mixed_moa"]["promotion_suppressed_reason"]
