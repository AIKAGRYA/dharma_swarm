from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dharma_swarm.operator_core.operating_facts import (
    OperatingFactBundle,
    OperatingFactInputs,
    append_human_yds_rating,
    build_operating_fact_bundle,
    bundle_to_dict,
    load_agentops_run_facts,
    load_human_yds_rating_facts,
    load_telic_value_facts,
    organ_boundary_map,
    organ_state_facts,
    rust_membrane_candidates,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_telic_db(path: Path, rows: list[tuple[str, str, dict[str, object], str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE objects (
                id TEXT PRIMARY KEY,
                type_name TEXT NOT NULL,
                properties TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO objects (id, type_name, properties, created_at) VALUES (?, ?, ?, ?)",
            [(obj_id, type_name, json.dumps(props), created_at) for obj_id, type_name, props, created_at in rows],
        )
        conn.commit()
    finally:
        conn.close()


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
    telic_db = tmp_path / "ontology.db"
    _write_telic_db(
        telic_db,
        [
            ("out_1", "Outcome", {"proposal_id": "prop_1", "success": True}, "2026-05-09T00:00:00Z"),
            ("ve_1", "ValueEvent", {"outcome_id": "out_1", "composite_value": 0.9}, "2026-05-09T00:01:00Z"),
            ("contrib_1", "Contribution", {"value_event_id": "ve_1", "attributed_value": 0.9}, "2026-05-09T00:02:00Z"),
        ],
    )

    bundle = build_operating_fact_bundle(
        OperatingFactInputs(
            agentops_reports_dir=agentops_root,
            kaizen_reports_dir=kaizen_root,
            yds_ratings_path=yds,
            burn_report_path=burn,
            revenue_notes_path=revenue,
            telic_ontology_db_path=telic_db,
        )
    )

    assert bundle.missing_sources == ()
    assert bundle.agentops[0].commit_state == "commit_created"
    assert bundle.kaizen[0].next_recommendation == "request human YDS rating"
    assert bundle.human_yds[0].authoritative is True
    assert bundle.burn[0].total_cost_usd == 0.03
    assert bundle.revenue[0].keywords == ("wedge", "pricing")
    assert bundle.telic_value[0].linked_chains == 1


def test_telic_value_facts_bind_complete_value_chain(tmp_path: Path) -> None:
    telic_db = tmp_path / "ontology.db"
    _write_telic_db(
        telic_db,
        [
            ("out_1", "Outcome", {"proposal_id": "prop_1", "success": True}, "2026-05-09T00:00:00Z"),
            ("ve_1", "ValueEvent", {"outcome_id": "out_1", "composite_value": 0.8}, "2026-05-09T00:01:00Z"),
            ("contrib_1", "Contribution", {"value_event_id": "ve_1", "attributed_value": 0.8}, "2026-05-09T00:02:00Z"),
        ],
    )

    facts = load_telic_value_facts(telic_db)
    states = {fact.name: fact for fact in organ_state_facts(OperatingFactBundle(telic_value=tuple(facts)))}

    assert facts[0].outcome_count == 1
    assert facts[0].value_event_count == 1
    assert facts[0].contribution_count == 1
    assert facts[0].linked_chains == 1
    assert states["telic_value"].coherence_state == "bound"


def test_telic_value_facts_keep_orphan_rows_partial(tmp_path: Path) -> None:
    telic_db = tmp_path / "ontology.db"
    _write_telic_db(
        telic_db,
        [
            ("out_1", "Outcome", {"proposal_id": "prop_1", "success": True}, "2026-05-09T00:00:00Z"),
            ("ve_1", "ValueEvent", {"outcome_id": "missing_outcome"}, "2026-05-09T00:01:00Z"),
            ("contrib_1", "Contribution", {"value_event_id": "ve_1"}, "2026-05-09T00:02:00Z"),
        ],
    )

    facts = load_telic_value_facts(telic_db)
    states = {fact.name: fact for fact in organ_state_facts(OperatingFactBundle(telic_value=tuple(facts)))}

    assert facts[0].orphan_value_events == ("ve_1",)
    assert facts[0].orphan_contributions == ("contrib_1",)
    assert states["telic_value"].coherence_state == "partial"


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
