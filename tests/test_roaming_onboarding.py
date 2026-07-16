from __future__ import annotations

import asyncio
import json

from dharma_swarm.roaming_onboarding import (
    RoamingAgentRegistration,
    onboard_roaming_agent,
)
from dharma_swarm.telemetry_plane import TelemetryPlaneStore


def test_onboard_roaming_agent_writes_canonical_surfaces(tmp_path) -> None:
    home = tmp_path / ".dharma"

    async def scenario():
        receipt = await onboard_roaming_agent(
            RoamingAgentRegistration(
                callsign="kimi-claw-phone",
                harness="openclaw_mobile",
                role="analyst",
                department="research",
                squad_id="transit",
                team_id="dharma_swarm",
                model="moonshotai/kimi-k2.5",
                provider="moonshot",
                endpoint="openclaw://kimi-claw-phone",
                capabilities=("research", "synthesis"),
                registration_source="test",
            ),
            dharma_home=home,
        )
        telemetry = TelemetryPlaneStore(home / "state" / "runtime.db")
        identity = await telemetry.get_agent_identity("kimi-claw-phone")
        roster = await telemetry.list_team_roster(
            team_id="dharma_swarm",
            agent_id="kimi-claw-phone",
            limit=10,
        )
        return receipt, identity, roster

    receipt, identity, roster = asyncio.run(scenario())

    dock_path = home / "agents" / "kimi-claw-phone" / "living_agent.json"
    embodiments_path = home / "agents" / "kimi-claw-phone" / "embodiments.jsonl"
    card_path = home / "a2a" / "cards" / "kimi-claw-phone.json"
    receipt_path = home / "onboarding" / "receipts" / f"{receipt.receipt_id}.json"

    assert dock_path.exists()
    assert embodiments_path.exists()
    assert card_path.exists()
    assert receipt_path.exists()

    dock = json.loads(dock_path.read_text(encoding="utf-8"))
    card = json.loads(card_path.read_text(encoding="utf-8"))
    stored_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert dock["agent_uid"] == "kimi-claw-phone"
    assert dock["current_embodiment"]["harness"] == "openclaw_mobile"
    assert card["metadata"]["agent_uid"] == "kimi-claw-phone"
    assert card["role"] == "analyst"
    assert stored_receipt["callsign"] == "kimi-claw-phone"

    assert identity is not None
    assert identity.department == "research"
    assert identity.metadata["harness"] == "openclaw_mobile"
    assert roster[0].role == "analyst"


def test_onboard_roaming_agent_persists_distinct_uid_on_card(tmp_path) -> None:
    home = tmp_path / ".dharma"
    receipt = asyncio.run(
        onboard_roaming_agent(
            RoamingAgentRegistration(
                callsign="display-seat",
                agent_uid="stable-worker-uid",
                harness="codex_cli",
                role="reviewer",
                registration_source="test-distinct-uid",
            ),
            dharma_home=home,
        )
    )

    card = json.loads(
        (home / "a2a" / "cards" / "display-seat.json").read_text(encoding="utf-8")
    )

    assert receipt.agent_uid == "stable-worker-uid"
    assert card["name"] == "display-seat"
    assert card["agent_uid"] == "stable-worker-uid"
    assert card["metadata"]["agent_uid"] == "stable-worker-uid"
    assert card["supported_interfaces"][0]["agent_uid"] == "stable-worker-uid"
    assert (
        card["supported_interfaces"][0]["subject"]
        == "dharma.agent.stable-worker-uid.inbox"
    )


def test_onboard_roaming_agent_reuses_uid_and_serial(tmp_path) -> None:
    home = tmp_path / ".dharma"

    async def scenario():
        first = await onboard_roaming_agent(
            RoamingAgentRegistration(
                callsign="kimi-claw-phone",
                harness="openclaw_mobile",
                role="analyst",
                registration_source="first-pass",
            ),
            dharma_home=home,
        )
        second = await onboard_roaming_agent(
            RoamingAgentRegistration(
                callsign="kimi-claw-phone",
                harness="claude_code_vps",
                role="analyst",
                endpoint="ssh://example-vps",
                registration_source="second-pass",
            ),
            dharma_home=home,
        )
        return first, second

    first, second = asyncio.run(scenario())

    dock = json.loads(
        (home / "agents" / "kimi-claw-phone" / "living_agent.json").read_text(encoding="utf-8")
    )
    embodiment_lines = (
        home / "agents" / "kimi-claw-phone" / "embodiments.jsonl"
    ).read_text(encoding="utf-8").strip().splitlines()

    assert first.agent_uid == second.agent_uid == "kimi-claw-phone"
    assert dock["serial"] == "AGT-KIMI_CLAW_PHONE"
    assert dock["current_embodiment"]["harness"] == "claude_code_vps"
    assert len(embodiment_lines) == 2
