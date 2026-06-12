"""Regression coverage for the Bun terminal stdio bridge."""

from __future__ import annotations

from dharma_swarm.terminal_bridge import TerminalBridge, system_commands_module


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
