"""Tests for dharma_swarm.a2a.registry_hydrator — receipts → NodeRegistry wire.

Verifies:
- Onboarding receipts hydrate into RemoteNode entries
- Capabilities are read from the agent card (not invented)
- Idempotent re-hydration updates rather than fails
- Malformed receipt lines are skipped without aborting
- Status default is "unknown" (health_check is the operational witness)
- discover() finds hydrated agents by capability after status promotion
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.a2a.node_registry import NodeRegistry
from dharma_swarm.a2a.registry_hydrator import hydrate_from_receipts
from dharma_swarm.roaming_onboarding import (
    RoamingAgentRegistration,
    onboard_roaming_agent,
)


@pytest.mark.asyncio
async def test_hydrate_single_receipt(tmp_path: Path) -> None:
    home = tmp_path / ".dharma"
    await onboard_roaming_agent(
        RoamingAgentRegistration(
            callsign="perplexity-computer",
            harness="perplexity_computer",
            role="external_evidence_worker",
            department="synthesis",
            team_id="dharma_swarm",
            endpoint="local://perplexity-computer",
            capabilities=("synthesis", "verdict_reconciliation"),
            registration_source="hydrator-test",
        ),
        dharma_home=home,
    )

    registry = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    nodes = hydrate_from_receipts(registry, dharma_home=home)

    assert len(nodes) == 1
    pc = registry.get("perplexity-computer")
    assert pc is not None
    assert pc.endpoint == "local://perplexity-computer"
    assert pc.status == "unknown"  # health_check is the operational witness
    assert set(pc.capabilities) >= {"synthesis", "verdict_reconciliation"}
    assert pc.metadata["harness"] == "perplexity_computer"
    assert pc.metadata["receipt_id"].startswith("onboard-perplexity-computer-")


@pytest.mark.asyncio
async def test_hydrate_multiple_receipts(tmp_path: Path) -> None:
    home = tmp_path / ".dharma"
    for callsign, caps in [
        ("perplexity-computer", ("synthesis", "verdict_reconciliation")),
        ("devin-roaming", ("infrastructure", "ci_wiring")),
        ("hermes", ("doctrinal_review", "index_keeping")),
    ]:
        await onboard_roaming_agent(
            RoamingAgentRegistration(
                callsign=callsign,
                harness=f"{callsign}_harness",
                role="external",
                capabilities=caps,
                registration_source="hydrator-test",
            ),
            dharma_home=home,
        )

    registry = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    nodes = hydrate_from_receipts(registry, dharma_home=home)

    assert len(nodes) == 3
    assert {n.node_id for n in nodes} == {
        "perplexity-computer",
        "devin-roaming",
        "hermes",
    }


@pytest.mark.asyncio
async def test_hydrate_idempotent(tmp_path: Path) -> None:
    """Running hydration twice should not duplicate or fail."""
    home = tmp_path / ".dharma"
    await onboard_roaming_agent(
        RoamingAgentRegistration(
            callsign="perplexity-computer",
            harness="perplexity_computer",
            role="external",
            capabilities=("synthesis",),
            registration_source="hydrator-test",
        ),
        dharma_home=home,
    )

    registry = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    hydrate_from_receipts(registry, dharma_home=home)
    hydrate_from_receipts(registry, dharma_home=home)

    assert registry.count() == 1


@pytest.mark.asyncio
async def test_hydrate_then_discover(tmp_path: Path) -> None:
    """After hydration + status promotion, discover() finds the agent."""
    home = tmp_path / ".dharma"
    await onboard_roaming_agent(
        RoamingAgentRegistration(
            callsign="perplexity-computer",
            harness="perplexity_computer",
            role="external",
            capabilities=("synthesis",),
            registration_source="hydrator-test",
        ),
        dharma_home=home,
    )

    registry = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    hydrate_from_receipts(registry, dharma_home=home)

    # discover() filters by status; hydration defaults to "unknown"
    assert registry.discover("synthesis") == []

    # Operational witness (health_check) would normally do this; for in-process
    # use we promote manually
    pc = registry.get("perplexity-computer")
    assert pc is not None
    pc.status = "online"
    found = registry.discover("synthesis")
    assert [n.node_id for n in found] == ["perplexity-computer"]


def test_hydrate_skips_malformed_receipts(tmp_path: Path) -> None:
    """Malformed JSONL lines are skipped, valid ones still hydrate."""
    home = tmp_path / ".dharma"
    receipts_dir = home / "onboarding"
    receipts_dir.mkdir(parents=True)
    cards_dir = home / "a2a" / "cards"
    cards_dir.mkdir(parents=True)

    # Hand-write a receipts.jsonl with one malformed and one valid line
    (receipts_dir / "receipts.jsonl").write_text(
        "this is not json\n"
        + json.dumps(
            {
                "receipt_id": "onboard-test-123",
                "agent_uid": "test-agent",
                "callsign": "test-agent",
                "harness": "test",
                "endpoint": "local://test",
                "department": "",
                "team_id": "",
                "created_at": "2026-05-30T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    registry = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    nodes = hydrate_from_receipts(registry, dharma_home=home)

    assert len(nodes) == 1
    assert nodes[0].node_id == "test-agent"


def test_hydrate_no_receipts_file_returns_empty(tmp_path: Path) -> None:
    """Hydrating against a missing receipts file is a no-op, not an error."""
    home = tmp_path / ".dharma"  # never created
    registry = NodeRegistry(nodes_path=tmp_path / "nodes.json")
    nodes = hydrate_from_receipts(registry, dharma_home=home)
    assert nodes == []
    assert registry.count() == 0
