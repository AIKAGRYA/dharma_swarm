from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from dharma_swarm.a2a.agent_presence import list_agent_presence


def test_agent_registry_presence_flags_stale_heartbeats(tmp_path: Path) -> None:
    root = tmp_path / "agents"
    codex = root / "codex_composer"
    codex.mkdir(parents=True)
    codex.joinpath("living_agent.json").write_text(
        json.dumps(
            {
                "agent_uid": "codex_composer",
                "callsign": "codex_composer",
                "status": "active",
                "last_seen_at": "2026-06-12T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    agents = list_agent_presence(
        agents_root=root,
        a2a_bus_root=tmp_path / "a2a_bus",
        now=datetime(2026, 6, 12, 3, 0, tzinfo=timezone.utc),
    )

    codex_presence = next(a for a in agents if a.agent_uid == "codex_composer")
    assert codex_presence.heartbeat_status == "RED"
    assert codex_presence.age_hours == 3.0
    missing = next(a for a in agents if a.agent_uid == "fable_composer")
    assert missing.status == "missing"
    assert missing.heartbeat_status == "RED"
    fable_cc = next(a for a in agents if a.agent_uid == "fable_claude_code")
    assert fable_cc.status == "missing"
    assert fable_cc.heartbeat_status == "RED"
