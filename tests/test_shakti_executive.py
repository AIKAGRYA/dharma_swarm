from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from dharma_swarm.shakti_executive import ShaktiExecutive
from dharma_swarm.shakti_executive.inputs import read_all_signals


def test_shakti_executive_dry_run_does_not_write_board(tmp_path: Path) -> None:
    state = tmp_path / "dharma"
    _write_zeitgeist(
        state,
        {
            "id": "zg-1",
            "source": "manual",
            "category": "threat",
            "title": "Preprint may scoop participation ratio result",
            "relevance_score": 0.9,
            "keywords": ["preprint", "arxiv", "mechanistic interpretability"],
            "description": "External threat to the current research lane.",
        },
    )

    result = ShaktiExecutive(state).run(write=False, top_k=3, min_score=40.0)

    assert result.dry_run is True
    assert result.scanned_signals == 1
    assert result.selected_candidates == 1
    assert result.board_count_after == 0
    assert not (state / "meta" / "opportunity_board.json").exists()


def test_shakti_executive_publishes_and_deduplicates_board(tmp_path: Path) -> None:
    state = tmp_path / "dharma"
    _write_scout_report(state)
    executive = ShaktiExecutive(state)

    first = executive.run(write=True, top_k=5, min_score=40.0)
    second = executive.run(write=True, top_k=5, min_score=40.0)

    board = json.loads((state / "meta" / "opportunity_board.json").read_text())
    assert first.board_count_after == 1
    assert second.board_count_after == 1
    assert len(board) == 1
    assert board[0]["domain"] == "internal_maintenance"
    assert board[0]["factor_scores"]["telos_alignment"] >= 0.6
    assert "evidence_signals" in board[0]
    assert (state / "meta" / "shakti_executive_latest.md").exists()
    assert list((state / "meta").glob("opportunity_board.json.bak.*"))


def test_shakti_executive_preview_uses_recognition_and_directives(tmp_path: Path) -> None:
    state = tmp_path / "dharma"
    meta = state / "meta"
    meta.mkdir(parents=True)
    (meta / "recognition_seed.md").write_text(
        "Revenue wedge with welfare proof and verified execution.",
        encoding="utf-8",
    )
    (meta / "operator_directives.md").write_text(
        "- Build the smallest proof of governed agent execution now.\n",
        encoding="utf-8",
    )

    preview = ShaktiExecutive(state).preview(top_k=5, min_score=30.0)

    assert len(preview) == 2
    assert preview[0]["final_score"] >= preview[1]["final_score"]
    assert any(row["thesis"] == "operator_directive" for row in preview)


def test_shakti_executive_reads_feedback_surfaces(tmp_path: Path) -> None:
    state = tmp_path / "dharma"
    _write_ontology_feedback(state)
    _write_dispatcher_health(state)
    _write_campaign_manifest(state)
    _write_darwin_archive(state)

    signals = read_all_signals(state)
    sources = {signal.source for signal in signals}
    categories = {signal.category for signal in signals}

    assert {"telic:Outcome", "telic:ValueEvent", "telic:Contribution"} <= sources
    assert "dispatcher_health" in categories
    assert "campaign_feedback" in categories
    assert "sealed_packet_archive" in categories

    preview = ShaktiExecutive(state).preview(top_k=10, min_score=30.0)
    assert any(
        source["source"] == "telic:Outcome"
        for row in preview
        for source in row["source_inputs"]
    )


def test_shakti_executive_turns_world_signal_into_strategic_opportunity(tmp_path: Path) -> None:
    state = tmp_path / "dharma"
    _write_zeitgeist(
        state,
        {
            "id": "world-subq",
            "source": "world_zeitgeist",
            "category": "company",
            "title": "SubQ managed agent runtime",
            "description": "Public world signal about managed agent execution infrastructure.",
            "relevance_score": 0.84,
            "keywords": ["agentic", "startup", "runtime"],
            "metadata": {
                "raw_source": "github",
                "url": "https://example.com/subq",
                "promotion_status": "promotion_ready",
                "first_principles_questions": ["What primitive is being proven?"],
                "iteration_steps": ["Verify public sources."],
                "strategic_moves": ["research", "prototype_smallest_governed_version"],
            },
        },
    )

    preview = ShaktiExecutive(state).preview(top_k=5, min_score=45.0)

    assert preview
    row = preview[0]
    assert row["domain"] == "ecosystem_scan"
    assert row["thesis"] == "ecosystem_signal"
    assert row["title"].startswith("World signal:")
    assert row["source_inputs"][0]["raw_source"] == "github"
    assert row["strategic_vision"]["first_principles_questions"] == ["What primitive is being proven?"]


def _write_zeitgeist(state: Path, row: dict[str, object]) -> None:
    meta = state / "meta"
    meta.mkdir(parents=True)
    (meta / "zeitgeist.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


def _write_scout_report(state: Path) -> None:
    report = {
        "domain": "architecture",
        "model": "unit-test",
        "findings": [
            {
                "title": "Module budget gate blocks opportunity refill tests",
                "severity": "high",
                "category": "bug",
                "description": "The refill seam is actionable and testable.",
                "file_path": "dharma_swarm/curriculum_engine.py",
                "line_number": 29,
                "confidence": 0.92,
                "actionable": True,
                "suggested_action": "Add the missing board-to-frontier conversion.",
            }
        ],
    }
    scout_dir = state / "scouts" / "architecture"
    scout_dir.mkdir(parents=True)
    (scout_dir / "latest.json").write_text(json.dumps(report), encoding="utf-8")


def _write_ontology_feedback(state: Path) -> None:
    state.mkdir(parents=True)
    conn = sqlite3.connect(state / "ontology.db")
    try:
        conn.execute(
            """
            CREATE TABLE objects (
                id TEXT PRIMARY KEY,
                type_name TEXT NOT NULL,
                properties TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL DEFAULT 'test',
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        rows = [
            (
                "outcome_1",
                "Outcome",
                {
                    "task_id": "task_1",
                    "agent_id": "agent_a",
                    "success": False,
                    "error": "scope stage failed",
                },
            ),
            (
                "value_1",
                "ValueEvent",
                {
                    "task_id": "task_1",
                    "agent_id": "agent_a",
                    "task_type": "stage_doc",
                    "composite_value": 0.2,
                },
            ),
            (
                "contribution_1",
                "Contribution",
                {
                    "agent_id": "agent_a",
                    "task_type": "stage_doc",
                    "attributed_value": 0.3,
                    "credit_share": 1.0,
                },
            ),
        ]
        for idx, (obj_id, type_name, props) in enumerate(rows):
            created = f"2026-05-07T00:00:0{idx}Z"
            conn.execute(
                """
                INSERT INTO objects
                (id, type_name, properties, created_at, created_by, updated_at, version)
                VALUES (?, ?, ?, ?, 'test', ?, 1)
                """,
                (obj_id, type_name, json.dumps(props), created, created),
            )
        conn.commit()
    finally:
        conn.close()


def _write_dispatcher_health(state: Path) -> None:
    meta = state / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "opportunity_dispatcher.health.json").write_text(
        json.dumps({
            "consecutive_failures": 2,
            "last_run_pending_count": 5,
            "last_run_dispatched": 0,
            "last_run_observed_in_flight": 1,
            "last_run_errors": ["gate blocked"],
        }),
        encoding="utf-8",
    )


def _write_campaign_manifest(state: Path) -> None:
    manifest = state / "campaigns" / "opp_1" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps({
            "opportunity_id": "opp_1",
            "title": "Feedback closure",
            "domain": "internal_maintenance",
            "stages": {
                "scope": {"status": "completed"},
                "validate": {"status": "failed"},
            },
        }),
        encoding="utf-8",
    )


def _write_darwin_archive(state: Path) -> None:
    archive = state / "evolution" / "archive.jsonl"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text(
        json.dumps({
            "id": "archive_1",
            "component": "tools/build_protocol/cli.py",
            "change_type": "sealed_packet",
            "description": "Shadow-applied packet",
            "test_results": {
                "pass_rate": 1.0,
                "sealed_packet": {
                    "shadow": True,
                    "diff_missing": False,
                },
            },
        }) + "\n",
        encoding="utf-8",
    )
