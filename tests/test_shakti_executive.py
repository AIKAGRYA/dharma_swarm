from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.shakti_executive import ShaktiExecutive


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


def test_cron_handler_shakti_executive_is_opt_in_for_writes(tmp_path: Path) -> None:
    from dharma_swarm.cron_job_runtime import CronJobRunStatus
    from dharma_swarm.cron_runner import execute_cron_job

    state = tmp_path / "dharma"
    _write_zeitgeist(
        state,
        {
            "id": "zg-cron",
            "category": "opportunity",
            "title": "Governed revenue audit service",
            "relevance_score": 0.9,
            "description": "External revenue wedge with governance proof.",
        },
    )

    dry = execute_cron_job({
        "handler": "shakti_executive",
        "state_dir": str(state),
        "top_k": 1,
        "min_score": 30.0,
    })
    assert dry.status == CronJobRunStatus.COMPLETED
    assert "dry_run=True" in dry.output
    assert not (state / "meta" / "opportunity_board.json").exists()

    written = execute_cron_job({
        "handler": "shakti_executive",
        "state_dir": str(state),
        "top_k": 1,
        "min_score": 30.0,
        "write": True,
    })
    assert written.status == CronJobRunStatus.COMPLETED
    assert "dry_run=False" in written.output
    assert (state / "meta" / "opportunity_board.json").exists()


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
