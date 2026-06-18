"""Regression coverage for the Bun terminal stdio bridge."""

from __future__ import annotations

from dharma_swarm.terminal_bridge import TerminalBridge, system_commands_module
from dharma_swarm.terminal_bridge_text import render_model_policy_text


def test_terminal_bridge_loads_tui_command_surface() -> None:
    assert system_commands_module is not None
    assert "status" in system_commands_module._ALL_COMMANDS


def test_terminal_bridge_bootstraps_commands_and_adapters() -> None:
    bridge = TerminalBridge()

    try:
        graph = bridge._build_command_graph_summary()
        assert bridge._adapter_boot_error is None
        assert bridge._commands is not None
        assert {"claude", "codex", "openrouter"}.issubset(bridge._available_provider_ids())
        assert "status" in graph["commands"]
    finally:
        # The constructors do not start provider streams, but keep the close path
        # explicit so future adapter resources do not leak in this test.
        import asyncio

        asyncio.run(bridge.close())


def test_model_policy_summary_uses_canonical_status_projection(monkeypatch) -> None:
    monkeypatch.setattr(
        "dharma_swarm.key_oracle.live_providers",
        lambda: {"claude_code", "codex", "ollama"},
    )
    monkeypatch.setattr("dharma_swarm.model_status._status_data", lambda: None)
    bridge = TerminalBridge()

    try:
        policy = bridge._build_model_policy_summary(
            selected_provider="claude",
            selected_model="claude-opus-4.8",
            strategy="responsive",
        )
        targets = {target["alias"]: target for target in policy["targets"]}

        assert policy["schema_version"] == "dharma.model_status.v1"
        assert targets["opus-4.8"]["selectable"] is True
        assert targets["gpt-5.5"]["selectable"] is True
        assert targets["kimi-k2.6"]["available"] is True
        assert targets["kimi-k2.6"]["selectable"] is False
        assert targets["kimi-k2.6"]["availability_reason"] == "terminal_adapter_missing"

        rendered = render_model_policy_text(policy)
        assert "## Targets" in rendered
        assert "opus-4.8 -> Claude Opus 4.8" in rendered
        assert "kimi-k2.6" in rendered
        assert "terminal_adapter_missing" in rendered
    finally:
        import asyncio

        asyncio.run(bridge.close())
