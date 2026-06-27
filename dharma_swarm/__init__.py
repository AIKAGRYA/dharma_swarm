"""DHARMA SWARM — Darwin-Heuristic Autonomous Recursive Meta-Agent Swarm."""

from __future__ import annotations

import importlib
from typing import Any

__version__ = "0.1.0"

from dharma_swarm.models import ProviderType  # noqa: F401

__all__ = [
    "ProviderType",
    "ClaudeCodeProvider",
    "CodexProvider",
    "OpenRouterFreeProvider",
]


def __getattr__(name: str) -> Any:
    if name in {"ClaudeCodeProvider", "CodexProvider", "OpenRouterFreeProvider"}:
        providers = importlib.import_module("dharma_swarm.providers")
        return getattr(providers, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
