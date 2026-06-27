"""Tests for live insight promotion into Darwin's pending proposal queue."""

from __future__ import annotations

import json
from pathlib import Path

from dharma_swarm.insight_evolution_bridge import promote_insights_to_pending_proposals


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_promotes_world_zeitgeist_row_to_darwin_proposal_once(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    meta = state / "meta"
    meta.mkdir(parents=True)
    proposals_path = state / "evolution" / "pending_proposals.jsonl"

    (meta / "world_zeitgeist_inbox.jsonl").write_text(
        json.dumps(
            {
                "id": "world-agentic-web",
                "source": "world_zeitgeist",
                "category": "company",
                "title": "Agentic web payment receipts are converging",
                "description": "Public systems are exposing signed receipts for agent actions.",
                "relevance_score": 0.91,
                "url": "https://example.com/agentic-web",
                "metadata": {
                    "movement_id": "movement-1",
                    "promotion_status": "promotion_ready",
                    "source_count": 2,
                    "first_principles_questions": [
                        "What receipt primitive is underneath the surface?"
                    ],
                    "iteration_steps": [
                        "Verify the claim against public primary sources.",
                        "State the smallest 48-hour prototype.",
                    ],
                    "adjacent_searches": [
                        '"agentic web payment receipts" docs',
                    ],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = promote_insights_to_pending_proposals(
        state_dir=state,
        proposals_path=proposals_path,
    )

    assert result.queued == 1
    assert result.candidates_seen == 1
    assert Path(result.receipt_path).exists()

    [proposal] = _jsonl(proposals_path)
    assert proposal["id"].startswith("insight-")
    assert proposal["component"] == "dharma_swarm/world_radar/analysis.py"
    assert proposal["change_type"] == "zeitgeist_insight"
    assert proposal["diff"] == ""
    assert proposal["metadata"]["dispatch_authority"] is False
    assert proposal["metadata"]["apply_authority"] == "darwin_sandbox_only"
    assert proposal["metadata"]["cross_test_status"] == "pending"
    assert len(proposal["metadata"]["evaluator_plan"]) == 5
    assert proposal["metadata"]["world_radar_iteration_steps"][0].startswith("Verify")
    assert proposal["metadata"]["source_refs"][0]["ref"] == "https://example.com/agentic-web"

    second = promote_insights_to_pending_proposals(
        state_dir=state,
        proposals_path=proposals_path,
    )

    assert second.queued == 0
    assert second.skipped_duplicate == 1
    assert len(_jsonl(proposals_path)) == 1


def test_promotes_shakti_opportunity_when_world_inbox_is_empty(tmp_path: Path) -> None:
    state = tmp_path / ".dharma"
    meta = state / "meta"
    meta.mkdir(parents=True)
    proposals_path = state / "evolution" / "pending_proposals.jsonl"

    (meta / "shakti_zeitgeist_state.json").write_text(
        json.dumps(
            {
                "opportunities": [
                    {
                        "opportunity_id": "opp-1",
                        "title": "Runtime policy gates need semantic receipts",
                        "domain": "strategic_infrastructure",
                        "thesis": "Policy-as-code is not enough without semantic proof receipts.",
                        "final_score": 86.0,
                        "evidence_signals": ["sig-1", "sig-2"],
                        "why_now": "Multiple S4 signals point at agent trust pressure.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = promote_insights_to_pending_proposals(
        state_dir=state,
        proposals_path=proposals_path,
    )

    assert result.queued == 1
    [proposal] = _jsonl(proposals_path)
    assert proposal["component"] == "dharma_swarm/evolution.py"
    assert proposal["metadata"]["candidate_source"] == "shakti_zeitgeist_state"
    assert proposal["metadata"]["domain"] == "strategic_infrastructure"
