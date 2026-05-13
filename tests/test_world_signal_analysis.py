from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.world_signal_analysis import (
    build_world_signal_board,
    promotion_ready_signals,
    render_world_signal_brief,
    update_source_weights_from_opportunities,
)
from dharma_swarm.world_signal_incubator import write_incubations


def test_single_source_high_upside_incubates_not_promotes(tmp_path: Path) -> None:
    board = build_world_signal_board([
        {
            "id": "a",
            "source": "HN",
            "category": "agent_infra",
            "title": "SubQ subquadratic coding agent launch",
            "description": "Long context workflow for AI agents.",
            "relevance_score": 0.92,
            "keywords": ["subquadratic", "agent"],
            "url": "https://example.test/subq",
            "metadata": {"raw_source": "hn_agent_search"},
        }
    ])

    movement = board["movements"][0]
    assert movement["promotion_status"] == "incubating"
    assert promotion_ready_signals(board) == []

    updates = write_incubations([movement], output_dir=tmp_path / "incubations")
    assert len(updates) == 1
    assert Path(updates[0]["incubation_markdown_path"]).exists()
    assert "Pass 3: Evolve" in Path(updates[0]["incubation_markdown_path"]).read_text()


def test_operator_drop_with_url_promotes() -> None:
    board = build_world_signal_board([
        {
            "id": "op",
            "source": "operator_drop",
            "category": "agent_infra",
            "title": "SubQ long context coding agent company",
            "description": "Subquadratic inference workflow for AI agents.",
            "relevance_score": 0.91,
            "keywords": ["subquadratic", "agent"],
            "url": "https://example.test/subq",
            "metadata": {"raw_source": "operator_drop"},
        }
    ])

    assert board["movements"][0]["promotion_status"] == "promotion_ready"
    rows = promotion_ready_signals(board)
    assert len(rows) == 1
    assert rows[0]["metadata"]["promotion_status"] == "promotion_ready"


def test_two_independent_sources_promote() -> None:
    board = build_world_signal_board([
        {
            "id": "a",
            "source": "HN",
            "category": "agent_infra",
            "title": "Long context coding agent repo",
            "description": "Agent workflow.",
            "relevance_score": 0.75,
            "keywords": ["long context", "agent"],
            "url": "https://example.test/a",
            "metadata": {"raw_source": "hn"},
        },
        {
            "id": "b",
            "source": "GitHub",
            "category": "agent_infra",
            "title": "Long context coding agent repo",
            "description": "Agent workflow.",
            "relevance_score": 0.72,
            "keywords": ["long context", "agent"],
            "url": "https://example.test/b",
            "metadata": {"raw_source": "github"},
        },
    ])

    assert board["promotion_ready_count"] == 1
    assert promotion_ready_signals(board)
    assert "World Signal Brief" in render_world_signal_brief(board)


def test_source_weights_learn_from_ecosystem_outcomes(tmp_path: Path) -> None:
    weights_path = tmp_path / "weights.json"
    board = [
        {"domain": "ecosystem_scan", "source_inputs": [{"raw_source": "hn"}], "realized_outcomes": [{"value": 0.8}]},
        {"domain": "ecosystem_scan", "source_inputs": [{"raw_source": "low"}], "realized_outcomes": [{"value": 0.2}]},
    ]
    weights = update_source_weights_from_opportunities(board, weights_path)
    assert weights["hn"] > 1.0
    assert weights["low"] < 1.0
    assert json.loads(weights_path.read_text()) == weights
