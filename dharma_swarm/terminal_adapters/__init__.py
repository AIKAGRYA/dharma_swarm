"""Compatibility exports for terminal provider adapters.

The canonical provider adapters live under `dharma_swarm.tui.engine.adapters`.
This package keeps the older terminal bridge import path alive.
"""

from __future__ import annotations

from dharma_swarm.tui.engine.adapters import (
    CLAUDE_CAPABILITIES,
    CODEX_CAPABILITIES,
    OPENROUTER_CAPABILITIES,
    Capability,
    ClaudeAdapter,
    CodexAdapter,
    CompletionRequest,
    ModelProfile,
    OpenRouterAdapter,
    ProviderAdapter,
    ProviderConfig,
)

__all__ = [
    "Capability",
    "CompletionRequest",
    "ModelProfile",
    "ProviderAdapter",
    "ProviderConfig",
    "ClaudeAdapter",
    "CLAUDE_CAPABILITIES",
    "CodexAdapter",
    "CODEX_CAPABILITIES",
    "OpenRouterAdapter",
    "OPENROUTER_CAPABILITIES",
]
