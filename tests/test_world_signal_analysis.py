from __future__ import annotations

from dharma_swarm.world_signal_analysis import (
    build_world_signal_board,
    incubating_movements,
    promotion_ready_signals,
    render_world_signal_brief,
)


def test_two_independent_public_sources_promote() -> None:
    board = build_world_signal_board(
        [
            {
                "source": "github",
                "category": "tool_release",
                "title": "SubQ agent infrastructure runtime",
                "description": "Agentic coding runtime with benchmark evidence.",
                "relevance_score": 0.86,
                "url": "https://github.com/example/subq",
                "keywords": ["agentic", "github"],
            },
            {
                "source": "hacker_news",
                "category": "tool_release",
                "title": "SubQ agent infrastructure runtime",
                "description": "HN discussion with independent public evidence.",
                "relevance_score": 0.78,
                "url": "https://news.ycombinator.com/item?id=1",
                "keywords": ["agentic"],
            },
        ],
        now="2026-05-13T00:00:00+00:00",
    )

    movement = board["movements"][0]
    assert movement["status"] == "promotion_ready"
    assert movement["independent_sources"] == 2
    promoted = promotion_ready_signals(board)
    assert len(promoted) == 1
    assert promoted[0]["metadata"]["promotion_status"] == "promotion_ready"
    assert len(promoted[0]["metadata"]["iteration_steps"]) == 10


def test_operator_drop_with_url_promotes() -> None:
    board = build_world_signal_board(
        [
            {
                "source": "operator_drop",
                "category": "company",
                "title": "SubQ example signal",
                "description": "Operator spotted a company with concrete evidence.",
                "relevance_score": 0.9,
                "url": "https://subq.ai/",
                "keywords": ["agentic", "startup"],
            }
        ]
    )

    assert board["movements"][0]["status"] == "promotion_ready"


def test_single_public_source_incubates_not_promotes() -> None:
    board = build_world_signal_board(
        [
            {
                "source": "hacker_news",
                "category": "company",
                "title": "Weak exciting world signal",
                "description": "Promising but only one public source.",
                "relevance_score": 0.72,
                "url": "https://news.ycombinator.com/item?id=2",
                "keywords": ["agentic"],
            }
        ]
    )

    assert promotion_ready_signals(board) == []
    assert len(incubating_movements(board)) == 1
    assert "World Signal Brief" in render_world_signal_brief(board)
