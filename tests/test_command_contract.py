"""Parity gate: cross-reference CLI ↔ TUI ↔ terminal_bridge command surfaces.

This test ensures no command surface drifts silently from the others.
See docs/plans/OPERATOR_COMMAND_VISION.md for the long-term architecture.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cli_top_level_commands() -> set[str]:
    """Return the set of top-level CLI subcommand names from _build_parser()."""
    from dharma_swarm.dgc_cli import _build_parser

    parser = _build_parser()
    for action in parser._subparsers._actions:
        if hasattr(action, "_parser_class"):
            return set(action.choices.keys())
    return set()


def _terminal_bridge_request_types() -> set[str]:
    """Return the set of request types handled by the terminal bridge."""
    src = (Path(__file__).resolve().parent.parent / "dharma_swarm" / "terminal_bridge.py").read_text()
    return set(re.findall(r'request_type\s*==\s*["\']([^"\']+)["\']', src))


def _tui_slash_commands() -> set[str]:
    """Return the set of TUI slash commands from system_commands.py."""
    mod = importlib.import_module("dharma_swarm.tui.commands.system_commands")
    return set(getattr(mod, "_ALL_COMMANDS", set()))


def _terminal_commands_modules() -> list[str]:
    """Return the list of domain module names under terminal_commands/."""
    pkg_dir = Path(__file__).resolve().parent.parent / "dharma_swarm" / "terminal_commands"
    return sorted(
        f.stem
        for f in pkg_dir.glob("*.py")
        if not f.name.startswith("_") and f.name != "__init__.py"
    )


def _cmd_functions_in_module(module_name: str) -> set[str]:
    """Return the set of cmd_* function names defined in a terminal_commands module."""
    mod = importlib.import_module(f"dharma_swarm.terminal_commands.{module_name}")
    return {name for name in dir(mod) if name.startswith("cmd_") and callable(getattr(mod, name))}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTerminalCommandsPackage:
    """Verify the extracted terminal_commands/ package is well-formed."""

    def test_every_domain_module_has_cmd_functions(self):
        """Each domain module must define at least one cmd_* function."""
        for mod_name in _terminal_commands_modules():
            fns = _cmd_functions_in_module(mod_name)
            assert fns, f"terminal_commands/{mod_name}.py has no cmd_* functions"

    def test_no_module_exceeds_line_budget(self):
        """No terminal_commands module should exceed 525 lines (soft ceiling)."""
        pkg_dir = Path(__file__).resolve().parent.parent / "dharma_swarm" / "terminal_commands"
        for f in pkg_dir.glob("*.py"):
            if f.name == "__init__.py":
                continue
            lines = len(f.read_text().splitlines())
            assert lines <= 525, f"{f.name} has {lines} lines (budget: 525)"

    def test_all_cmd_functions_importable_from_dgc_cli(self):
        """Every cmd_* in terminal_commands/ must be importable via dgc_cli (backward compat)."""
        import dharma_swarm.dgc_cli as cli

        all_cmds: set[str] = set()
        for mod_name in _terminal_commands_modules():
            all_cmds |= _cmd_functions_in_module(mod_name)

        missing = {name for name in all_cmds if not hasattr(cli, name)}
        assert not missing, f"cmd_* functions not importable from dgc_cli: {missing}"


class TestCommandSurfaceParity:
    """Cross-reference CLI ↔ TUI ↔ terminal_bridge command sets."""

    def test_cli_commands_exist(self):
        """CLI must have at least 80 top-level commands (currently ~90)."""
        cmds = _cli_top_level_commands()
        assert len(cmds) >= 80, f"Only {len(cmds)} CLI commands found"

    def test_terminal_bridge_types_exist(self):
        """Terminal bridge must handle at least 15 request types."""
        types = _terminal_bridge_request_types()
        assert len(types) >= 15, f"Only {len(types)} bridge request types found"

    def test_tui_slash_commands_exist(self):
        """TUI must define at least 20 slash commands."""
        cmds = _tui_slash_commands()
        assert len(cmds) >= 20, f"Only {len(cmds)} TUI slash commands found"

    def test_status_command_present_on_all_surfaces(self):
        """'status' must be available on CLI, TUI, and terminal bridge."""
        assert "status" in _cli_top_level_commands()
        assert "status" in _tui_slash_commands()
        assert "status" in _terminal_bridge_request_types()

    def test_tui_commands_have_cli_counterparts(self):
        """Most TUI slash commands should have a CLI counterpart.

        Some TUI-only commands (help, clear, reset, etc.) are expected.
        This test flags significant drift.
        """
        tui_only_ok = {"help", "clear", "reset", "cancel", "paste", "copy",
                       "copylast", "btw", "chat", "thread", "plan", "net",
                       "self", "logs", "git", "truth", "corpus", "archive",
                       "darwin", "runtime",
                       # TUI-specific views (no CLI equivalent yet):
                       "evidence", "trishula", "openclaw", "moltbook", "notes"}
        tui = _tui_slash_commands()
        cli = _cli_top_level_commands()
        drift = tui - cli - tui_only_ok
        assert not drift, f"TUI commands with no CLI counterpart: {drift}"

    def test_surface_inventory_snapshot(self):
        """Informational: print surface counts for humans reviewing the PR."""
        cli_count = len(_cli_top_level_commands())
        tui_count = len(_tui_slash_commands())
        bridge_count = len(_terminal_bridge_request_types())
        modules = _terminal_commands_modules()
        cmd_count = sum(len(_cmd_functions_in_module(m)) for m in modules)
        print(f"\n  CLI commands:       {cli_count}")
        print(f"  TUI slash commands: {tui_count}")
        print(f"  Bridge req types:   {bridge_count}")
        print(f"  terminal_commands/: {len(modules)} modules, {cmd_count} cmd_* functions")
