from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.world_signal_analysis import (
    build_world_signal_board,
    render_world_signal_brief,
    update_source_weights_from_opportunities,
)


def test_world_signal_board_clusters_and_marks_uncertainty(tmp_path: Path) -> None:
    health = tmp_path / "world_scout_health.json"
    health.write_text(
        json.dumps(
            {
                "observed_at": "2026-05-12T00:00:00Z",
                "fetch_enabled": True,
                "source_count": 6,
                "reachable_count": 5,
                "item_count": 42,
            }
        ),
        encoding="utf-8",
    )
    signals = [
        {
            "id": "subq-a",
            "source": "world_scout_go:product_company",
            "source_url": "https://subq.ai/",
            "category": "model_release",
            "title": "SubQ claims subquadratic long-context LLM for coding agents",
            "relevance_score": 0.96,
            "keywords": ["subquadratic", "long context", "coding agents"],
            "metadata": {"claims_self_reported": True},
        },
        {
            "id": "subq-b",
            "source": "world_scout_go:practitioner",
            "source_url": "https://news.ycombinator.com/item?id=1",
            "category": "model_release",
            "title": "Practitioners discuss SubQ long context coding agents",
            "relevance_score": 0.82,
            "keywords": ["long context", "coding agents"],
            "metadata": {},
        },
    ]

    board = build_world_signal_board(signals, scout_health=health)

    assert board["scout_health"]["reachable_count"] == 5
    assert board["signals"][0]["movement_id"] == "model_release:subquadratic"
    assert board["signals"][0]["corroboration_count"] >= 1
    assert board["signals"][0]["recommended_move"] in {"teardown", "prototype"}
    brief = render_world_signal_brief(board)
    assert "World Signal Brief" in brief
    assert "SubQ claims" in brief


def test_source_weights_learn_from_ecosystem_outcomes(tmp_path: Path) -> None:
    board = tmp_path / "opportunity_board.json"
    weights = tmp_path / "world_source_weights.json"
    board.write_text(
        json.dumps(
            [
                {
                    "domain": "ecosystem_scan",
                    "source_inputs": [
                        {"source": "zeitgeist", "raw_source": "world_scout_go:product_company"}
                    ],
                    "realized_outcomes": [{"success": True}, {"success": False}],
                }
            ]
        ),
        encoding="utf-8",
    )

    payload = update_source_weights_from_opportunities(
        opportunity_board=board,
        weights_path=weights,
    )

    source = payload["sources"]["world_scout_go:product_company"]
    assert source["success"] == 1
    assert source["failure"] == 1
    assert weights.exists()
