from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.operator_core.command_spine import (
    CoherenceDelta,
    OperatorCommandRequest,
    RustReadinessSignal,
    evaluate_rust_readiness,
    plan_operator_command,
    record_human_yds_rating,
    review_agentops_reports,
    work_packet_to_dict,
)


def test_plan_operator_command_drafts_agentops_packet_without_execution() -> None:
    plan = plan_operator_command(
        OperatorCommandRequest(
            prompt="Build the operator command spine and add regression tests",
            branch="chore/operator-command-spine",
            worktree="/tmp/dharma_swarm_command_spine",
            allowed_files=[
                "dharma_swarm/operator_core/**",
                "tests/test_operator_command_spine.py",
                "docs/governance/**",
            ],
        )
    )

    packet = work_packet_to_dict(plan.work_packet)

    assert plan.primary_skill in {"architect", "builder", "validator"}
    assert plan.work_packet.requires_human_scope is False
    assert isinstance(plan.coherence_delta, CoherenceDelta)
    assert plan.coherence_delta.organ_touched == "command_spine"
    assert "OrganStateFact" in plan.coherence_delta.proof_read
    assert packet["branch"] == "chore/operator-command-spine"
    assert packet["worktree"] == "/tmp/dharma_swarm_command_spine"
    assert packet["commit"]["allowed"] is False
    assert packet["approval"]["before_commit"] is True
    assert "dharma_swarm/operator_core/**" in packet["allowed_files"]
    assert "api/**" in packet["forbidden_files"]
    assert "coherence_delta" not in packet


def test_plan_operator_command_marks_inferred_scope_for_human_approval() -> None:
    plan = plan_operator_command(
        OperatorCommandRequest(prompt="Improve the AgentOps Kaizen governance flow")
    )

    assert plan.work_packet.requires_human_scope is True
    assert plan.work_packet.scope_confidence == "inferred-low"
    assert plan.coherence_delta.organ_touched == "agentops"
    assert "inferred" in plan.coherence_delta.new_drift_risk
    assert any("human scope approval" in warning for warning in plan.warnings)
    assert plan.next_step.startswith("tighten allowed_files")


def test_review_agentops_reports_summarizes_green_report(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "agentops" / "job-green" / "20260505"
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(
        json.dumps(
            {
                "job_id": "job-green",
                "status": "passed",
                "gates": [{"name": "pytest", "passed": True, "exit_code": 0}],
                "scope": {"passed": True, "changed_files": ["docs/a.md"], "violations": []},
                "approval": {"before_commit": False, "before_merge": True},
                "commit_hash": "abc123",
                "commit_decision": "commit permitted",
            }
        ),
        encoding="utf-8",
    )

    review = review_agentops_reports([tmp_path / "reports" / "agentops"])

    assert review.reports_reviewed == 1
    assert review.summaries[0].gates == "all green"
    assert review.summaries[0].scope == "scope clean"
    assert review.summaries[0].commit == "commit created"
    assert review.next_recommendation == "promote the successful packet pattern into a playbook candidate"


def test_review_agentops_reports_prioritizes_failed_gate(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "job_id": "job-red",
                "status": "failed",
                "gates": [{"name": "pytest", "passed": False, "exit_code": 1}],
                "scope": {"passed": True, "changed_files": ["a.py"], "violations": []},
                "approval": {"before_commit": True, "before_merge": True},
                "commit_decision": "one or more gates failed",
            }
        ),
        encoding="utf-8",
    )

    review = review_agentops_reports([report])

    assert review.summaries[0].gates == "some red"
    assert "failed gate" in review.summaries[0].waste_patterns
    assert review.next_recommendation == "fix the first failed gate before expanding scope"


def test_record_human_yds_rating_appends_authoritative_jsonl(tmp_path: Path) -> None:
    ledger = tmp_path / "yds" / "human_quality_ratings.jsonl"

    rating = record_human_yds_rating(
        ledger_path=ledger,
        artifact="artifact://operator-command-spine",
        rating="5.12a",
        source="Dhyana",
        human_comment="useful spine",
        timestamp="2026-05-05T00:00:00+00:00",
    )

    assert rating.source == "dhyana"
    rows = ledger.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    payload = json.loads(rows[0])
    assert payload["artifact"]["uri"] == "artifact://operator-command-spine"
    assert payload["rating_value"] == "5.12a"
    assert payload["operator_id"] == "dhyana"


def test_record_human_yds_rating_rejects_ai_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="human/operator/dhyana"):
        record_human_yds_rating(
            ledger_path=tmp_path / "ratings.jsonl",
            artifact="artifact://x",
            rating="5.10",
            source="ai",
        )


def test_rust_readiness_keeps_python_until_boundary_is_stable() -> None:
    decision = evaluate_rust_readiness(
        RustReadinessSignal(
            component="operator command spine",
            deterministic=True,
            boundary_stable=False,
            has_green_tests=True,
            security_critical=True,
        )
    )

    assert decision.decision == "keep_python"
    assert "boundary is not stable" in decision.reasons


def test_rust_readiness_marks_only_stable_deterministic_components() -> None:
    decision = evaluate_rust_readiness(
        RustReadinessSignal(
            component="scope diff validator",
            deterministic=True,
            boundary_stable=True,
            has_green_tests=True,
            security_critical=True,
        )
    )

    assert decision.decision == "rust_candidate"
    assert "FFI/CLI contract" in decision.next_step
