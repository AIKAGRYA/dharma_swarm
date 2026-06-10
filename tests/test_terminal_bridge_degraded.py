"""Degraded-mode contract for terminal_bridge command graph/registry.

When the terminal_commands import fails (system_commands_module is None),
_build_command_graph_summary and _build_command_registry must emit the
degraded payload instead of crashing with AttributeError on _ALL_COMMANDS.
"""

from __future__ import annotations

import dharma_swarm.terminal_bridge as tb


def _bridge_without_init() -> "tb.TerminalBridge":
    return tb.TerminalBridge.__new__(tb.TerminalBridge)


def test_command_graph_summary_degrades_without_command_modules(monkeypatch) -> None:
    monkeypatch.setattr(tb, "system_commands_module", None)
    bridge = _bridge_without_init()
    summary = bridge._build_command_graph_summary()
    assert summary["degraded"] is True
    assert summary["count"] == 0
    assert summary["commands"] == []
    assert summary["categories"] == {}


def test_command_registry_degrades_without_command_modules(monkeypatch) -> None:
    monkeypatch.setattr(tb, "system_commands_module", None)
    bridge = _bridge_without_init()
    registry = bridge._build_command_registry()
    assert registry["degraded"] is True
    assert registry["count"] == 0
    assert registry["commands"] == []


def test_command_graph_summary_healthy_path_has_no_degraded_flag() -> None:
    if tb.system_commands_module is None:  # environment genuinely degraded
        return
    bridge = _bridge_without_init()
    summary = bridge._build_command_graph_summary()
    assert "degraded" not in summary
    assert summary["count"] > 0
