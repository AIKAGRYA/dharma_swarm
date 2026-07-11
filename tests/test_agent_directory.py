"""Stable-UID AgentDirectory facade tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from dharma_swarm.a2a.agent_card import AgentCard, AgentSkill, CardRegistry
from dharma_swarm.a2a.node_registry import NodeRegistry, RemoteNode


class _FakeTelemetryStore:
    def __init__(self, records):
        self.records = records

    async def list_agent_identities(self, *, limit: int = 1000):
        return self.records[:limit]


@pytest.mark.asyncio
async def test_agent_directory_merges_sources_by_stable_uid_without_credentials(tmp_path) -> None:
    from dharma_swarm.a2a.agent_directory import AgentDirectory

    home = tmp_path / ".dharma"
    receipts_dir = home / "onboarding"
    receipts_dir.mkdir(parents=True)
    (receipts_dir / "receipts.jsonl").write_text(
        json.dumps(
            {
                "receipt_id": "receipt-hermes",
                "agent_uid": "hermes-m5",
                "callsign": "hermes",
                "harness": "hermes",
                "department": "engineering",
                "team_id": "control-plane",
                "created_at": "2026-07-11T00:00:00+00:00",
                "credential": "receipt-secret",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    cards = CardRegistry(cards_dir=home / "a2a" / "cards")
    cards.register(
        AgentCard(
            name="hermes",
            agent_uid="hermes-m5",
            role="coder",
            status="idle",
            skills=[AgentSkill(name="code_review")],
            metadata={"token": "card-secret"},
        )
    )
    nodes = NodeRegistry(nodes_path=home / "a2a" / "nodes.json")
    nodes.register(
        RemoteNode(
            node_id="hermes",
            endpoint="https://agent.invalid",
            status="online",
            api_key="runtime-secret",
            api_key_env="HERMES_A2A_KEY",
            metadata={"agent_uid": "hermes-m5", "password": "node-secret"},
        )
    )
    telemetry = _FakeTelemetryStore(
        [
            SimpleNamespace(
                agent_id="hermes-m5",
                codename="Hermes",
                department="runtime",
                squad_id="control-plane",
                specialization="implementation",
                status="busy",
                last_active="2026-07-11T01:00:00+00:00",
                metadata={"api_key": "telemetry-secret"},
            )
        ]
    )

    directory = AgentDirectory(
        card_registry=cards,
        node_registry=nodes,
        dharma_home=home,
        telemetry_store=telemetry,
    )
    entries = await directory.list_entries()

    assert len(entries) == 1
    entry = entries[0]
    assert entry.agent_uid == "hermes-m5"
    assert entry.name == "hermes"
    assert entry.status == "online"
    assert entry.capabilities == ["code_review"]
    assert entry.credential_refs == ["env:HERMES_A2A_KEY"]
    assert entry.sources == ["card", "node", "onboarding", "telemetry"]
    serialized = json.dumps(entry.to_dict(), sort_keys=True)
    for secret in ("runtime-secret", "receipt-secret", "card-secret", "node-secret", "telemetry-secret"):
        assert secret not in serialized


@pytest.mark.asyncio
async def test_agent_directory_includes_onboarding_and_telemetry_only_agents(tmp_path) -> None:
    from dharma_swarm.a2a.agent_directory import AgentDirectory

    home = tmp_path / ".dharma"
    receipts_dir = home / "onboarding"
    receipts_dir.mkdir(parents=True)
    (receipts_dir / "receipts.jsonl").write_text(
        json.dumps(
            {
                "receipt_id": "receipt-roamer",
                "agent_uid": "roamer-uid",
                "callsign": "roamer",
                "harness": "external",
                "department": "research",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cards = CardRegistry(cards_dir=home / "a2a" / "cards")
    nodes = NodeRegistry(nodes_path=home / "a2a" / "nodes.json")
    telemetry = _FakeTelemetryStore(
        [SimpleNamespace(agent_id="telemetry-only", codename="Observer", status="idle")]
    )
    directory = AgentDirectory(
        card_registry=cards,
        node_registry=nodes,
        dharma_home=home,
        telemetry_store=telemetry,
    )

    entries = await directory.list_entries()

    assert [entry.agent_uid for entry in entries] == ["roamer-uid", "telemetry-only"]
    roamer = await directory.get("roamer")
    assert roamer is not None
    assert roamer.agent_uid == "roamer-uid"
    assert roamer.onboarding["receipt_id"] == "receipt-roamer"


@pytest.mark.asyncio
async def test_agent_directory_api_returns_credential_safe_entries(monkeypatch) -> None:
    from api.routers import agents
    from dharma_swarm.a2a.agent_directory import AgentDirectoryEntry

    entry = AgentDirectoryEntry(
        agent_uid="stable-agent",
        name="Stable Agent",
        credential_refs=["env:STABLE_AGENT_KEY"],
        sources=["node"],
    )

    class _Directory:
        async def list_entries(self):
            return [entry]

    monkeypatch.setattr(agents, "_get_agent_directory", lambda: _Directory())

    response = await agents.list_agent_directory()

    assert response.status == "ok"
    assert response.data == [entry.to_dict()]
