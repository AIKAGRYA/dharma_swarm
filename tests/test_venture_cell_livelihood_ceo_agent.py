from __future__ import annotations

import json

import pytest

from dharma_swarm.venture_cell.livelihood_loom.ceo_agent import (
    AGENT_ID,
    CALLSIGN,
    build_external_worker_registration,
    build_runtime_fields,
    build_system_prompt,
    register_livelihood_loom_ceo,
)


def test_livelihood_loom_ceo_registration_packet_is_bounded(tmp_path):
    worker = build_external_worker_registration(dharma_home=tmp_path / ".dharma")
    assert worker.agent_uid == AGENT_ID
    assert worker.callsign == CALLSIGN
    assert worker.role == "livelihood_loom_ceo"
    assert worker.department == "venture_cell"
    assert worker.authority.value == "sandbox_write"
    assert worker.autonomy_policy.requires_approval is True
    assert worker.autonomy_policy.can_write_source is False
    assert worker.workspace_policy.repo_writes_allowed is False
    assert worker.metadata["cell_id"] == "livelihood_loom"
    assert worker.metadata["mission_id"] == "livelihood_loom_pilot_001"
    assert worker.metadata["human_governor"] == "dhyana"
    assert worker.metadata["parent_plane"] == "jagat_kalyan"
    assert worker.metadata["capital_boundary"] == "dharma_capital_read_only_aggregated_signals"
    assert "queue_external_action" in worker.metadata["allowed_internal_tools"]
    assert "trading_alpha_extraction" in worker.metadata["forbidden_actions"]
    assert worker.metadata["external_action_mode"] == "human_approved_only"
    assert worker.metadata["external_authority"] == "none_without_approval"
    assert worker.metadata["no_autonomous_capital_decision"] is True


def test_livelihood_loom_ceo_prompt_and_runtime_fields_point_to_charter(tmp_path):
    prompt = build_system_prompt(repo_root=tmp_path)
    assert "Livelihood Loom CEO" in prompt
    assert "human-governed approval queue" in prompt
    fields = build_runtime_fields(dharma_home=tmp_path / ".dharma", repo_root=tmp_path)
    names = {field["name"] for field in fields}
    assert {
        "system_prompt",
        "charter_path",
        "safe_bootstrap_command",
        "cultivation_cycle_command",
        "internal_lane_commands",
    } <= names


@pytest.mark.asyncio
async def test_register_livelihood_loom_ceo_writes_dock_card_and_agent_registry(tmp_path):
    home = tmp_path / ".dharma"
    result = await register_livelihood_loom_ceo(
        dharma_home=home,
        repo_root=tmp_path,
        agents_dir=tmp_path / "ginko_agents",
    )
    assert result["agent_uid"] == AGENT_ID
    assert (home / "external_agents" / AGENT_ID / "registration.json").exists()
    assert (home / "agents" / AGENT_ID / "living_agent.json").exists()
    assert (home / "a2a" / "cards" / f"{CALLSIGN}.json").exists()

    identity = json.loads(
        (tmp_path / "ginko_agents" / AGENT_ID / "identity.json").read_text(
            encoding="utf-8"
        )
    )
    assert identity["name"] == AGENT_ID
    assert identity["role"] == "livelihood_loom_ceo"
    runtime_fields = json.loads(
        (tmp_path / "ginko_agents" / AGENT_ID / "runtime_fields.json").read_text(
            encoding="utf-8"
        )
    )
    assert runtime_fields["agent"] == AGENT_ID
    assert any(field["name"] == "safe_bootstrap_command" for field in runtime_fields["fields"])
    assert any(
        field["name"] == "cultivation_cycle_command"
        for field in runtime_fields["fields"]
    )
    assert any(field["name"] == "budget_policy" for field in runtime_fields["fields"])
