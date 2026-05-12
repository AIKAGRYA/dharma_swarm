"""Tests for the read-only ShaktiZeitgeistExecutive seam."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.fourfold_action_warrant import CapabilityInventory, EvidenceItem
from dharma_swarm.models import GateDecision
from dharma_swarm.shakti_zeitgeist_executive import (
    DISPATCH_AUTHORITY,
    ExecutiveCycleState,
    ShaktiZeitgeistExecutive,
)


def _state(tmp_path: Path) -> Path:
    state_dir = tmp_path / ".dharma"
    (state_dir / "meta").mkdir(parents=True)
    return state_dir


def _write_zeitgeist(state_dir: Path, rows: list[dict[str, object]]) -> None:
    path = state_dir / "meta" / "zeitgeist.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            payload = {
                "id": row.get("id", "sig"),
                "source": row.get("source", "world_feed"),
                "category": row.get("category", "opportunity"),
                "title": row.get("title", "Signal"),
                "relevance_score": row.get("relevance_score", 0.5),
                "keywords": row.get("keywords", []),
                "description": row.get("description", ""),
                "timestamp": row.get("timestamp", datetime.now(timezone.utc).isoformat()),
            }
            fh.write(json.dumps(payload) + "\n")


def _evidence(count: int) -> list[EvidenceItem]:
    categories = ["root", "code", "tests", "history", "tools"]
    return [
        EvidenceItem(path=f"/repo/evidence_{i}.md", category=categories[i % 5])
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_cycle_consumes_zeitgeist_and_emits_artifacts(tmp_path: Path) -> None:
    state_dir = _state(tmp_path)
    _write_zeitgeist(
        state_dir,
        [
            {
                "id": "zg-threat",
                "category": "threat",
                "title": "New long-context coding model threatens context strategy",
                "relevance_score": 0.9,
                "keywords": ["model", "coding", "long-context"],
            },
            {
                "id": "zg-tool",
                "category": "tool_release",
                "title": "Frontier agentic coding tool release",
                "relevance_score": 0.8,
                "keywords": ["tool", "agentic"],
            },
        ],
    )

    executive = ShaktiZeitgeistExecutive(state_dir=state_dir)
    state = await executive.cycle()

    assert isinstance(state, ExecutiveCycleState)
    assert state.signals_ingested == 2
    assert state.signals_by_source == {"zeitgeist": 2}
    assert state.opportunities
    assert state.warrant_pressure.required_for_next_action
    assert state.dispatch_authority is False

    meta = state_dir / "meta"
    assert (meta / "shakti_zeitgeist_state.json").exists()
    assert (meta / "s4_warrant_pressure.json").exists()
    assert (meta / "s4_warrant_pressure.md").exists()
    assert (meta / "executive_briefs").is_dir()
    assert not (meta / "active_campaigns.json").exists()


@pytest.mark.asyncio
async def test_single_threat_sets_warrant_pressure(tmp_path: Path) -> None:
    state_dir = _state(tmp_path)
    _write_zeitgeist(
        state_dir,
        [
            {
                "id": "zg-threat",
                "category": "threat",
                "title": "New governance bypass threat",
                "relevance_score": 0.9,
                "keywords": ["governance", "dispatch"],
            }
        ],
    )

    state = await ShaktiZeitgeistExecutive(state_dir=state_dir).cycle()

    assert state.warrant_pressure.required_for_next_action
    assert state.warrant_pressure.pressure_score > 0
    assert "active_s4_pressure" in state.warrant_pressure.trigger_reasons


def test_assess_action_uses_fourfold_gate_without_dispatch(tmp_path: Path) -> None:
    state_dir = _state(tmp_path)
    _write_zeitgeist(
        state_dir,
        [
            {
                "id": "zg-threat",
                "category": "threat",
                "title": "Governance pressure in hooks",
                "relevance_score": 0.95,
                "keywords": ["governance", "hook"],
            }
        ],
    )
    paragraph = (
        "This action is bounded to evidence production and read-only executive "
        "pressure. It names the trigger, links the S4 signal to governance risk, "
        "and leaves dispatch authority outside this seam."
    )
    executive = ShaktiZeitgeistExecutive(state_dir=state_dir)

    warrant = executive.assess_action(
        title="Wire governance pressure for operator review",
        description="Writes code but does not dispatch.",
        metadata={"writes_code": True, "governance_impact": True},
        evidence=_evidence(5),
        capabilities=CapabilityInventory(
            skills=["mcp-synergy"],
            mcp_tools=["filesystem.read_multiple_files"],
            plugins=["GitHub"],
            hooks=["pre-commit"],
        ),
        integrated_vision=paragraph,
        connection_map=paragraph,
        meaningful_action=paragraph,
        min_evidence_files=5,
    )

    assert warrant.decision is GateDecision.ALLOW
    assert warrant.zeitgeist_signal_ids
    assert DISPATCH_AUTHORITY is False
    assert not hasattr(executive, "dispatch")
    assert not hasattr(executive, "route")
    assert not hasattr(executive, "execute")


def test_assess_action_blocks_without_evidence(tmp_path: Path) -> None:
    executive = ShaktiZeitgeistExecutive(state_dir=_state(tmp_path))

    warrant = executive.assess_action(
        title="Enable autonomous dispatch",
        metadata={"dispatch_authority": True},
        min_evidence_files=3,
    )

    assert warrant.decision is GateDecision.BLOCK
    assert "dispatch_authority" in warrant.trigger_reasons
    assert any(blocker.startswith("evidence_files<3") for blocker in warrant.blockers)
