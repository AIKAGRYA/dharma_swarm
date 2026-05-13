from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.world_signal_analysis import (
    build_world_signal_board,
    render_world_signal_brief,
    update_source_weights_from_opportunities,
)


def test_world_signal_board_clusters_and_marks_uncertainty() -> None:
    signals = [
        {
            "id": "a",
            "source": "HN",
            "category": "agent_infra",
            "title": "SubQ subquadratic coding agent launch",
            "description": "Long context workflow for AI agents.",
            "relevance_score": 0.92,
            "keywords": ["subquadratic", "agent"],
            "metadata": {
                "raw_source": "hn_agent_search",
                "first_principles_questions": ["What primitive changed?"],
                "iteration_steps": ["Verify the primary source."],
            },
        },
        {
            "id": "b",
            "source": "GitHub",
            "category": "agent_infra",
            "title": "Long context coding agent repo",
            "description": "A repo tracking the same agent workflow.",
            "relevance_score": 0.7,
            "keywords": ["long context", "coding agent"],
            "metadata": {"raw_source": "github_agent_repos"},
        },
    ]

    board = build_world_signal_board(
        signals,
        scout_health={
            "sources": [
                {"source_id": "hn", "reachable": True, "item_count": 1},
                {"source_id": "github", "reachable": True, "item_count": 1},
            ]
        },
    )

    assert board["signal_count"] == 2
    assert board["movements"][0]["movement_id"] == "agent_infra:subquadratic"
    assert board["movements"][0]["corroboration_count"] >= 1
    assert board["movements"][0]["uncertainty"] in {"medium", "high"}
    brief = render_world_signal_brief(board)
    assert "World Signal Brief" in brief
    assert "SubQ" in brief


def test_source_weights_learn_from_ecosystem_outcomes(tmp_path: Path) -> None:
    weights_path = tmp_path / "weights.json"
    board = [
        {
            "domain": "ecosystem_scan",
            "source_inputs": [{"raw_source": "hn_agent_search"}],
            "realized_outcomes": [{"value": 0.8}],
        },
        {
            "domain": "ecosystem_scan",
            "source_inputs": [{"raw_source": "low_quality_feed"}],
            "realized_outcomes": [{"value": 0.2}],
        },
    ]

    weights = update_source_weights_from_opportunities(board, weights_path)

    assert weights["hn_agent_search"] > 1.0
    assert weights["low_quality_feed"] < 1.0
    persisted = json.loads(weights_path.read_text())
    assert persisted == weights
