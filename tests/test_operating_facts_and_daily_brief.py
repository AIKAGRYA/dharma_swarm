from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.daily_operating_brief import (
    DailyOperatingBriefInputs,
    build_daily_operating_brief,
    render_markdown,
)
from dharma_swarm.operator_core.operating_facts import (
    OperatingFactBundle,
    OperatingFactInputs,
    append_human_yds_rating,
    build_operating_fact_bundle,
    bundle_to_dict,
    load_agentops_run_facts,
    load_human_yds_rating_facts,
    organ_boundary_map,
    organ_state_facts,
    rust_membrane_candidates,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_organ_boundaries_keep_distinct_truth_owners() -> None:
    boundaries = organ_boundary_map()

    assert boundaries["agentops"].owns == "bounded repo execution facts"
    assert "HumanQualityRatingFact" in boundaries["human_yds"].emits
    assert "agentops" in boundaries["daily_operating_brief"].may_read
    assert "daily_operating_brief" in boundaries["agentops"].must_not_mutate
    assert "human_yds" in boundaries["telic_value"].must_not_mutate


def test_rust_candidates_are_mechanical_membranes_only() -> None:
    candidates = {boundary.name for boundary in rust_membrane_candidates()}

    assert {"agentops", "human_yds", "burn_cost"} <= candidates
    assert "command_spine" not in candidates
    assert "daily_operating_brief" not in candidates
    assert "telic_value" not in candidates


def test_load_agentops_run_facts_normalizes_report_shape(tmp_path: Path) -> None:
    report_path = tmp_path / "reports" / "agentops" / "job-red" / "20260505" / "report.json"
    _write_json(
        report_path,
        {
            "job_id": "job-red",
            "status": "failed",
            "branch": "chore/red",
            "worktree": "/tmp/red",
            "gates": [{"name": "pytest", "passed": False, "exit_code": 1}],
            "scope": {
                "passed": False,
                "changed_files": ["api/main.py"],
                "violations": [{"path": "api/main.py"}],
            },
            "approval": {"before_commit": True, "before_merge": True},
            "commit_decision": "one or more gates failed",
        },
    )

    facts = load_agentops_run_facts(tmp_path / "reports" / "agentops")

    assert len(facts) == 1
    fact = facts[0]
    assert fact.job_id == "job-red"
    assert fact.gate_state == "some_red"
    assert fact.scope_state == "scope_violation"
    assert fact.failed_gates == ("pytest",)
    assert fact.scope_violations == ("api/main.py",)


def test_organ_state_facts_project_declared_vs_observed_state(tmp_path: Path) -> None:
    report_path = tmp_path / "reports" / "agentops" / "job-red" / "20260505" / "report.json"
    _write_json(
        report_path,
        {
            "job_id": "job-red",
            "status": "failed",
            "branch": "chore/red",
            "worktree": "/tmp/red",
            "gates": [{"name": "pytest", "passed": False, "exit_code": 1}],
            "scope": {"passed": True, "changed_files": ["docs/a.md"], "violations": []},
            "approval": {"before_commit": True, "before_merge": True},
            "commit_decision": "one or more gates failed",
        },
    )
    runs = load_agentops_run_facts(tmp_path / "reports" / "agentops")
    bundle = OperatingFactBundle(agentops=tuple(runs), missing_sources=("KaizenReview reports",))

    states = {fact.name: fact for fact in organ_state_facts(bundle)}
    payload = bundle_to_dict(bundle)

    assert states["agentops"].coherence_state == "drifted"
    assert states["kaizen_review"].coherence_state == "declared_only"
    assert states["telic_value"].coherence_state == "unknown"
    assert payload["organ_states"][0]["name"] == "agentops"


def test_operating_fact_bundle_reads_all_organs_without_mutating(tmp_path: Path) -> None:
    agentops_root = tmp_path / "agentops"
    _write_json(
        agentops_root / "job-green" / "20260505" / "report.json",
        {
            "job_id": "job-green",
            "status": "passed",
            "branch": "chore/green",
            "worktree": "/tmp/green",
            "gates": [{"name": "pytest", "passed": True, "exit_code": 0}],
            "scope": {"passed": True, "changed_files": ["docs/a.md"], "violations": []},
            "approval": {"before_commit": False, "before_merge": True},
            "commit_hash": "abc123",
            "commit_decision": "commit permitted",
        },
    )
    kaizen_root = tmp_path / "kaizen"
    _write_json(
        kaizen_root / "latest" / "kaizen_review.json",
        {
            "jobs_reviewed": 1,
            "next_work_packet_recommendation": "request human YDS rating",
            "waste_patterns": [],
            "stop_doing_items": [],
            "playbook_update_candidates": ["Promote the green packet shape."],
            "human_yds_rating": None,
        },
    )
    yds = tmp_path / "yds.jsonl"
    append_human_yds_rating(
        yds,
        artifact_uri="git://commit/abc123",
        rating="5.12a",
        human_note="clear useful artifact",
    )
    burn = tmp_path / "burn.jsonl"
    burn.write_text(
        json.dumps({"provider": "openrouter", "total_tokens": 12, "estimated_cost_usd": 0.03})
        + "\n",
        encoding="utf-8",
    )
    revenue = tmp_path / "revenue.md"
    revenue.write_text("- pricing wedge: Campaign X-Ray diagnostic\n", encoding="utf-8")

    bundle = build_operating_fact_bundle(
        OperatingFactInputs(
            agentops_reports_dir=agentops_root,
            kaizen_reports_dir=kaizen_root,
            yds_ratings_path=yds,
            burn_report_path=burn,
            revenue_notes_path=revenue,
        )
    )

    assert bundle.missing_sources == ()
    assert bundle.agentops[0].commit_state == "commit_created"
    assert bundle.kaizen[0].next_recommendation == "request human YDS rating"
    assert bundle.human_yds[0].authoritative is True
    assert bundle.burn[0].total_cost_usd == 0.03
    assert bundle.revenue[0].keywords == ("wedge", "pricing")


def test_non_human_yds_records_are_advisory_only(tmp_path: Path) -> None:
    yds = tmp_path / "yds.jsonl"
    yds.write_text(
        json.dumps(
            {
                "artifact": "repo://docs/a.md",
                "rating": "5.12a",
                "source": "ai",
                "human_comment": "model guessed this",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    facts = load_human_yds_rating_facts(yds)

    assert facts[0].authoritative is False


def test_daily_operating_brief_consumes_operating_fact_bundle(tmp_path: Path) -> None:
    agentops_root = tmp_path / "agentops"
    _write_json(
        agentops_root / "job-red" / "20260505" / "report.json",
        {
            "job_id": "job-red",
            "status": "failed",
            "branch": "chore/red",
            "worktree": "/tmp/red",
            "gates": [{"name": "pytest", "passed": False, "exit_code": 1}],
            "scope": {"passed": True, "changed_files": ["docs/a.md"], "violations": []},
            "approval": {"before_commit": True, "before_merge": True},
            "commit_decision": "one or more gates failed",
        },
    )

    brief = build_daily_operating_brief(
        DailyOperatingBriefInputs(
            agentops_reports_dir=agentops_root,
            now=datetime(2026, 5, 5, tzinfo=timezone.utc),
        )
    )
    markdown = render_markdown(brief)

    assert brief.date == "2026-05-05"
    assert "AgentOps `job-red` has red gate(s): pytest." in brief.gate_health
    assert brief.next_highest_leverage_move == ["fix failed gate(s) for AgentOps `job-red`"]
    assert "Do not expand `job-red` until failed gates are fixed." in brief.stop_doing
    assert any("`agentops` is `drifted`" in item for item in brief.coherence_state)
    assert "## 8. Coherence state" in markdown
    assert "## 9. Next highest-leverage move" in markdown
