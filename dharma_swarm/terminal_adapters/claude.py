"""Compatibility shim for the canonical TUI Claude provider adapter."""

from __future__ import annotations

from dharma_swarm.tui.engine.adapters.claude import (
    CLAUDE_CAPABILITIES,
    ClaudeAdapter,
)

__all__ = ["CLAUDE_CAPABILITIES", "ClaudeAdapter"]
