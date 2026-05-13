"""Tests for world action authority gating."""

from __future__ import annotations

from dharma_swarm.world_actions import create_website_scaffold


def test_world_action_blocked_by_action_authority_in_enforce(tmp_path, monkeypatch):
    monkeypatch.setenv("DHARMA_ACTION_AUTHORITY_GATE", "enforce")
    output_dir = tmp_path / "site"

    result = create_website_scaffold(
        str(output_dir),
        site_name="Blocked Site",
        purpose="Should not be written",
    )

    assert result.success is False
    assert "ACTION AUTHORITY BLOCK" in result.message
    assert not output_dir.exists()
